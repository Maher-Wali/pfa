from __future__ import annotations

from typing import Callable, List, Tuple

from langchain_core.documents import Document

from retrieval.rag_pipeline import MentalHealthRAG


class RAGStore:
    def __init__(
        self,
        index_name: str,
        embedding_model_name: str,
        reranker_model_name: str,
        debug: bool = False,
    ):
        self._rag = MentalHealthRAG(
            clinical_index=index_name,
            reranker_model=reranker_model_name,
            debug=debug,
        )

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        informational: bool = True,
        history: List[Tuple[str, str]] | None = None,
        llm_func: Callable[[str], str] | None = None,
    ) -> List[Document]:
        self._rag.chat_history = history or []
        if llm_func is not None:
            return self._rag.retrieve(
                user_query=query,
                llm_func=llm_func,
                top_k_docs=top_k,
                informational=informational,
            )
        return self._rag.clinical.hybrid_search(query, k=top_k)


def messages_to_history(messages: list[dict]) -> list[tuple[str, str]]:
    """Convert a flat role/content message list into (user, assistant) turn pairs."""
    history: list[tuple[str, str]] = []
    i = 0
    while i < len(messages) - 1:
        if messages[i]["role"] == "user" and messages[i + 1]["role"] == "assistant":
            history.append((messages[i]["content"], messages[i + 1]["content"]))
            i += 2
        else:
            i += 1
    return history


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
