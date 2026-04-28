from __future__ import annotations

from typing import List

from langchain_core.documents import Document

from retrieval.hybrid_retriever import HybridRetriever
from retrieval.rrf_rerank import RerankedRRF


class RAGStore:
    def __init__(
        self,
        index_name: str,
        embedding_model_name: str,
        reranker_model_name: str,
        bm25_weight: float = 0.55,
        dense_weight: float = 0.45,
        debug: bool = False,
    ):
        self.retriever = HybridRetriever(
            index_name=index_name,
            embedding_model_name=embedding_model_name,
            bm25_weight=bm25_weight,
            dense_weight=dense_weight,
            debug=debug,
        )

        self.reranker = RerankedRRF(model_name=reranker_model_name)

    def retrieve(self, query: str, top_k: int = 5) -> List[Document]:
        docs = self.retriever.hybrid_search(query, k=top_k * 4)
        return self.reranker.rerank(query, docs, top_k=top_k)


def format_context(docs: List[Document], max_chars_per_doc: int = 1800) -> str:
    blocks: list[str] = []

    for i, doc in enumerate(docs, start=1):
        text = doc.page_content.replace("\n", " ").strip()

        if len(text) > max_chars_per_doc:
            text = text[:max_chars_per_doc].rsplit(" ", 1)[0] + "..."

        source = (
            doc.metadata.get("source")
            or doc.metadata.get("title")
            or doc.metadata.get("condition")
            or "retrieved_doc"
        )

        blocks.append(f"[Doc {i} | {source}]\n{text}")

    return "\n\n".join(blocks)