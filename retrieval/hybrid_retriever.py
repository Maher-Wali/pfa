# retrieval/hybrid_retriever.py
#
# Hybrid BM25 + dense retriever over a single Pinecone index.
# BM25 runs locally in-memory; dense search uses Pinecone's cosine index.

import re
import os
import json
import pickle
import numpy as np
from pathlib import Path
from typing import List
from langchain_core.documents import Document
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer
from pinecone import Pinecone

# Avoid OpenMP conflicts when torch and llama.cpp are both loaded
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

_CACHE_DIR = Path(__file__).parent.parent / "data" / "cache"


def _normalize_for_bm25(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


class HybridRetriever:
    """
    Weighted hybrid retrieval: BM25 + dense cosine similarity.

    Both score arrays are min-max normalised before combining, so
    bm25_weight + dense_weight need not sum to 1 (but usually do).
    """

    def __init__(
        self,
        index_name: str,
        bm25_weight: float = 0.65,
        dense_weight: float = 0.35,
        embedding_model_name: str = "BAAI/bge-base-en-v1.5",
        debug: bool = False,
    ):
        self.index_name = index_name
        self.bm25_weight = bm25_weight
        self.dense_weight = dense_weight
        self.embedding_model_name = embedding_model_name
        self.debug = debug

        pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])
        self.index = pc.Index(index_name)

        print(f"Loading embedding model: {embedding_model_name}")
        self.embedding_model = SentenceTransformer(embedding_model_name)

        self._load_documents()

    # ------------------------------------------------------------------
    # Cache helpers
    # ------------------------------------------------------------------

    def _cache_paths(self):
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        base = _CACHE_DIR / self.index_name
        return base.with_suffix(".pkl"), base.with_name(self.index_name + "_meta.json")

    def _pinecone_vector_count(self) -> int:
        stats = self.index.describe_index_stats()
        return stats.total_vector_count

    def _load_cache(self, expected_count: int):
        pkl_path, meta_path = self._cache_paths()
        if not pkl_path.exists() or not meta_path.exists():
            return False
        meta = json.loads(meta_path.read_text())
        if meta.get("vector_count") != expected_count:
            return False
        with open(pkl_path, "rb") as f:
            cached = pickle.load(f)
        self.docs = cached["docs"]
        self.doc_ids = cached["doc_ids"]
        self.bm25 = cached["bm25"]
        print(f"BM25 loaded from cache ({len(self.docs)} docs)")
        return True

    def _write_cache(self, vector_count: int):
        pkl_path, meta_path = self._cache_paths()
        with open(pkl_path, "wb") as f:
            pickle.dump({"docs": self.docs, "doc_ids": self.doc_ids, "bm25": self.bm25}, f)
        meta_path.write_text(json.dumps({"vector_count": vector_count}))
        print(f"BM25 cache written ({len(self.docs)} docs)")

    # ------------------------------------------------------------------
    # Initialisation helpers
    # ------------------------------------------------------------------

    def _load_documents(self):
        """
        Load BM25 index and document store from disk cache when possible.
        Falls back to fetching all vectors from Pinecone and rebuilds cache.
        Cache is invalidated when the Pinecone vector count changes.
        """
        self.docs: List[Document] = []
        self.doc_ids: List[str] = []

        vector_count = self._pinecone_vector_count()

        if self._load_cache(vector_count):
            return

        print(f"Cache miss — fetching {vector_count} vectors from '{self.index_name}'")
        normalized_texts: List[str] = []

        all_ids = []
        for id_batch in self.index.list():
            all_ids.extend(id_batch)

        if not all_ids:
            raise ValueError(f"No vectors found in index '{self.index_name}'.")

        for i in range(0, len(all_ids), 100):
            batch_ids = all_ids[i : i + 100]
            fetched = self.index.fetch(ids=batch_ids)
            for vid, vec_data in fetched.vectors.items():
                meta = vec_data.metadata or {}
                text = meta.pop("text", "")
                if text:
                    self.docs.append(Document(page_content=text, metadata=meta))
                    normalized_texts.append(_normalize_for_bm25(text))
                    self.doc_ids.append(vid)

        if not self.docs:
            raise ValueError(
                f"No documents with text metadata found in index '{self.index_name}'."
            )

        print(f"Loaded {len(self.docs)} documents from '{self.index_name}'")
        tokenized = [t.split() for t in normalized_texts]
        self.bm25 = BM25Okapi(tokenized)
        print(f"BM25 index built ({len(self.docs)} docs)")
        self._write_cache(vector_count)

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    def _bm25_scores(self, query: str) -> np.ndarray:
        tokens = _normalize_for_bm25(query).split()
        return np.array(self.bm25.get_scores(tokens), dtype=float)

    def _dense_scores(self, query: str) -> np.ndarray:
        query_emb = self.embedding_model.encode(
            [query],
            convert_to_numpy=True,
            normalize_embeddings=True,
        )[0]

        # Pinecone enforces a top_k limit of 10 000
        top_k = min(len(self.docs), 10_000)
        results = self.index.query(
            vector=query_emb.tolist(),
            top_k=top_k,
            include_metadata=False,
        )

        if not hasattr(results, "matches"):
            return np.zeros(len(self.docs), dtype=float)

        score_map = {m.id: m.score for m in results.matches}
        scores = np.array(
            [score_map.get(did, 0.0) for did in self.doc_ids],
            dtype=float,
        )
        return scores

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def hybrid_search(
        self,
        query: str,
        k: int = 10,
        bm25_weight: float | None = None,
        dense_weight: float | None = None,
        min_score: float | None = None,
    ) -> List[Document]:
        bm25_w = bm25_weight if bm25_weight is not None else self.bm25_weight
        dense_w = dense_weight if dense_weight is not None else self.dense_weight

        bm25 = self._bm25_scores(query)
        dense = self._dense_scores(query)

        min_len = min(len(bm25), len(dense))
        bm25 = bm25[:min_len]
        dense = dense[:min_len]

        bm25_norm = (bm25 - bm25.min()) / (bm25.max() - bm25.min() + 1e-12)
        dense_norm = (dense - dense.min()) / (dense.max() - dense.min() + 1e-12)

        final = bm25_w * bm25_norm + dense_w * dense_norm
        top_idx = np.argsort(final)[::-1][:k]

        results = []
        for idx in top_idx:
            score = float(final[idx])
            if min_score is not None and score < min_score:
                break
            doc = self.docs[idx].copy()
            doc.metadata["hybrid_score"] = score
            doc.metadata["bm25_score"] = float(bm25_norm[idx])
            doc.metadata["dense_score"] = float(dense_norm[idx])
            results.append(doc)

        if self.debug:
            print("Top hybrid scores:", [r.metadata["hybrid_score"] for r in results[:5]])

        return results
