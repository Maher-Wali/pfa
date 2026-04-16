# retrieval/rrf_rerank.py
#
# Reciprocal Rank Fusion + CrossEncoder reranking.
# Ported from medai — collection-agnostic, no changes needed.

from typing import List
from langchain_core.documents import Document
from sentence_transformers import CrossEncoder


class RerankedRRF:
    """
    Two-stage post-retrieval fusion and reranking:
      1. RRF — fuse N ranked lists from multi-query retrieval into one list.
      2. CrossEncoder — score (query, passage) pairs and return the top-k.
    """

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        print(f"Loading reranker: {model_name}")
        self.model = CrossEncoder(model_name)
        print("Reranker ready")

    # ------------------------------------------------------------------
    # Stage 1 — Reciprocal Rank Fusion
    # ------------------------------------------------------------------

    def reciprocal_rank_fusion(
        self, doc_lists: List[List[Document]], k: int = 60
    ) -> List[Document]:
        """
        Merge multiple ranked lists into one using RRF.

        Deduplication is by object identity (id(doc)) so the same passage
        retrieved by two different queries contributes to one combined score.
        """
        scores: dict = {}
        doc_map: dict = {}

        for doc_list in doc_lists:
            for rank, doc in enumerate(doc_list):
                doc_id = id(doc)
                if doc_id not in scores:
                    scores[doc_id] = 0.0
                    doc_map[doc_id] = doc
                scores[doc_id] += 1.0 / (k + rank + 1)

        sorted_ids = sorted(scores, key=lambda x: scores[x], reverse=True)
        return [doc_map[did] for did in sorted_ids]

    # ------------------------------------------------------------------
    # Stage 2 — CrossEncoder reranking
    # ------------------------------------------------------------------

    def rerank(self, query: str, docs: List[Document], top_k: int = 5) -> List[Document]:
        """Score (query, passage) pairs and return the top-k."""
        if not docs:
            return []

        pairs = [[query, doc.page_content] for doc in docs]
        scores = self.model.predict(pairs, batch_size=32, show_progress_bar=False)

        ranked = sorted(zip(docs, scores), key=lambda x: x[1], reverse=True)
        return [doc for doc, _ in ranked[:top_k]]
