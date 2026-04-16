# retrieval/hybrid_retriever.py
#
# Hybrid BM25 + dense retriever over a single ChromaDB collection.
# Ported from medai with no logic changes — it is already collection-agnostic.

import re
import os
import chromadb
import numpy as np
from typing import List
from langchain_core.documents import Document
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer

# Avoid OpenMP conflicts when torch and llama.cpp are both loaded
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"


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
        persist_directory: str,
        collection_name: str,
        bm25_weight: float = 0.65,
        dense_weight: float = 0.35,
        embedding_model_name: str = "BAAI/bge-base-en-v1.5",
        debug: bool = False,
    ):
        self.bm25_weight = bm25_weight
        self.dense_weight = dense_weight
        self.embedding_model_name = embedding_model_name
        self.debug = debug

        self.client = chromadb.PersistentClient(path=persist_directory)
        self.collection = self.client.get_collection(collection_name)

        print(f"Loading embedding model: {embedding_model_name}")
        self.embedding_model = SentenceTransformer(embedding_model_name)

        self._load_documents()
        self._init_bm25()

    # ------------------------------------------------------------------
    # Initialisation helpers
    # ------------------------------------------------------------------

    def _load_documents(self):
        data = self.collection.get(include=["documents", "metadatas", "embeddings"])

        self.docs: List[Document] = []
        self.normalized_texts: List[str] = []

        for doc_text, meta, emb in zip(
            data["documents"], data["metadatas"], data["embeddings"]
        ):
            if emb is not None and len(emb) > 0:
                self.docs.append(Document(page_content=doc_text, metadata=meta))
                self.normalized_texts.append(_normalize_for_bm25(doc_text))

        if not self.docs:
            raise ValueError(
                f"No documents with embeddings found in collection "
                f"'{self.collection.name}'."
            )

        print(f"Loaded {len(self.docs)} documents from '{self.collection.name}'")

    def _init_bm25(self):
        tokenized = [t.split() for t in self.normalized_texts]
        self.bm25 = BM25Okapi(tokenized)
        print(f"BM25 index built ({len(self.docs)} docs)")

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

        results = self.collection.query(
            query_embeddings=[query_emb.tolist()],
            n_results=len(self.docs),
            include=["distances"],
        )

        distances = np.array(results["distances"][0], dtype=float)

        # Paranoia: ChromaDB may return fewer results than requested
        if len(distances) != len(self.docs):
            if self.debug:
                print(
                    f"Warning: dense results ({len(distances)}) != "
                    f"doc count ({len(self.docs)})"
                )
            min_len = min(len(distances), len(self.docs))
            distances = distances[:min_len]

        return 1.0 / (1.0 + distances)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def hybrid_search(self, query: str, k: int = 10) -> List[Document]:
        bm25 = self._bm25_scores(query)
        dense = self._dense_scores(query)

        min_len = min(len(bm25), len(dense))
        bm25 = bm25[:min_len]
        dense = dense[:min_len]

        bm25_norm = (bm25 - bm25.min()) / (bm25.max() - bm25.min() + 1e-12)
        dense_norm = (dense - dense.min()) / (dense.max() - dense.min() + 1e-12)

        final = self.bm25_weight * bm25_norm + self.dense_weight * dense_norm
        top_idx = np.argsort(final)[::-1][:k]

        results = []
        for idx in top_idx:
            doc = self.docs[idx].copy()
            doc.metadata["hybrid_score"] = float(final[idx])
            doc.metadata["bm25_score"] = float(bm25_norm[idx])
            doc.metadata["dense_score"] = float(dense_norm[idx])
            results.append(doc)

        if self.debug:
            print("Top hybrid scores:", [r.metadata["hybrid_score"] for r in results[:5]])

        return results
