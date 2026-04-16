# retrieval/rag_pipeline.py
#
# Dual-collection RAG orchestrator.
#
# Flow
# ----
#   1. Rewrite the user query into 3 standalone search queries (history-aware).
#   2. Route each query to "clinical", "therapy", or "both" via keyword router.
#   3. Run hybrid (BM25 + dense) retrieval on the selected collection(s).
#   4. Fuse all retrieved lists with Reciprocal Rank Fusion.
#   5. Rerank the fused list with a CrossEncoder.
#   6. Filter passages for query-relevant sentences.
#   7. Build a context-grounded prompt and call the LLM.
#   8. Store the exchange in chat history for the next turn.

from __future__ import annotations

import re
import json
from pathlib import Path
from typing import List, Tuple, Callable

from langchain_core.documents import Document

from retrieval.hybrid_retriever import HybridRetriever
from retrieval.rrf_rerank import RerankedRRF
from retrieval.query_router import route_query, RouteTarget


# ---------------------------------------------------------------------------
# Default Pinecone index names
# ---------------------------------------------------------------------------

_CLINICAL_INDEX = "mental-health-clinical"
_THERAPY_INDEX = "mental-health-therapy"


# ---------------------------------------------------------------------------
# Query rewriter  (same logic as medai, kept local to avoid cross-project deps)
# ---------------------------------------------------------------------------

def _rewrite_queries(
    query: str,
    history: List[Tuple[str, str]],
    llm_func: Callable[[str], str],
) -> List[str]:
    """Rewrite *query* into up to 3 standalone search queries using the LLM."""
    history_text = "\n".join(f"User: {u}\nAssistant: {a}" for u, a in history)

    prompt = f"""You are a mental-health information assistant.

Given the conversation and the current question, generate 3 standalone search
queries that capture the full intent. Each query should be self-contained.

Conversation:
{history_text}

Current Question: {query}

Output ONLY valid JSON:
{{"queries": ["q1", "q2", "q3"]}}
"""
    raw = llm_func(prompt)

    try:
        data = json.loads(raw)
        queries = data.get("queries", [])
    except Exception:
        match = re.search(r"\[.*?\]", raw, re.DOTALL)
        queries = json.loads(match.group(0)) if match else []

    queries = [q for q in queries if isinstance(q, str) and q.strip()]
    return queries[:3] if queries else [query]


# ---------------------------------------------------------------------------
# Passage filter  (same logic as medai — keeps only query-relevant sentences)
# ---------------------------------------------------------------------------

def _filter_passages(
    docs: List[Document],
    query: str,
    max_len: int = 300,
) -> List[str]:
    query_tokens = set(re.findall(r"\w+", query.lower()))
    passages: List[str] = []

    for doc in docs:
        text = doc.page_content.replace("\n", " ").strip()
        sentences = re.split(r"(?<=[.!?])\s+", text)

        relevant = [
            s for s in sentences
            if len(set(re.findall(r"\w+", s.lower())) & query_tokens) >= 2
        ]

        if relevant:
            excerpt = " ".join(relevant)[:max_len]
            # Label the passage with the most informative metadata field
            label = (
                doc.metadata.get("condition")
                or doc.metadata.get("technique_name")
                or doc.metadata.get("source")
                or "Doc"
            )
            passages.append(f"[{label}] {excerpt}")

    return passages


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class MentalHealthRAG:
    """
    History-aware RAG pipeline over two Pinecone indexes:
      • mental-health-clinical  — disorders, symptoms, diagnosis
      • mental-health-therapy   — coping techniques, exercises, skills

    Parameters
    ----------
    clinical_index / therapy_index:
        Pinecone index names.
    reranker_model:
        HuggingFace model ID for the CrossEncoder reranker.
    bm25_weight / dense_weight:
        Hybrid search blend applied to *both* retrievers.
    debug:
        Print intermediate retrieval scores.
    """

    def __init__(
        self,
        clinical_index: str = _CLINICAL_INDEX,
        therapy_index: str = _THERAPY_INDEX,
        reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
        bm25_weight: float = 0.65,
        dense_weight: float = 0.35,
        debug: bool = False,
    ):
        self.debug = debug

        print("Initialising clinical retriever…")
        self.clinical = HybridRetriever(
            index_name=clinical_index,
            bm25_weight=bm25_weight,
            dense_weight=dense_weight,
            debug=debug,
        )

        print("Initialising therapy retriever…")
        self.therapy = HybridRetriever(
            index_name=therapy_index,
            bm25_weight=bm25_weight,
            dense_weight=dense_weight,
            debug=debug,
        )

        self.reranker = RerankedRRF(model_name=reranker_model)
        self.chat_history: List[Tuple[str, str]] = []

    # ------------------------------------------------------------------
    # Chat history
    # ------------------------------------------------------------------

    def add_to_history(self, user_query: str, assistant_answer: str) -> None:
        self.chat_history.append((user_query, assistant_answer))

    def clear_history(self) -> None:
        self.chat_history.clear()

    # ------------------------------------------------------------------
    # Retrieval helpers
    # ------------------------------------------------------------------

    def _retrieve(
        self,
        query: str,
        target: RouteTarget,
        k: int,
    ) -> List[Document]:
        """Run hybrid search on the target collection(s) and return docs."""
        if target == "clinical":
            return self.clinical.hybrid_search(query, k=k)
        if target == "therapy":
            return self.therapy.hybrid_search(query, k=k)
        # "both" — retrieve from each and combine (RRF happens upstream)
        clinical_docs = self.clinical.hybrid_search(query, k=k)
        therapy_docs = self.therapy.hybrid_search(query, k=k)
        return clinical_docs + therapy_docs

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def generate_response(
        self,
        user_query: str,
        llm_func: Callable[[str], str],
        top_k_docs: int = 5,
        force_target: RouteTarget | None = None,
    ) -> str:
        """
        Generate a grounded answer for *user_query*.

        Parameters
        ----------
        user_query:
            The raw user input for this turn.
        llm_func:
            Callable ``(prompt: str) -> str``.  Should wrap your local or
            remote LLM (e.g. ``generate_with_qwen25``).
        top_k_docs:
            Number of passages to include in the final context.
        force_target:
            Override the automatic query router (``"clinical"``,
            ``"therapy"``, or ``"both"``).
        """
        # --- 1. Rewrite query ---
        rewritten = _rewrite_queries(user_query, self.chat_history, llm_func)

        if self.debug:
            print(f"Rewritten queries: {rewritten}")

        # --- 2. Route + retrieve ---
        all_lists: List[List[Document]] = []
        for q in rewritten:
            target = route_query(q, force=force_target)
            if self.debug:
                print(f"  '{q[:60]}' → {target}")
            docs = self._retrieve(q, target, k=top_k_docs * 3)
            all_lists.append(docs)

        # --- 3. Fuse with RRF ---
        fused = self.reranker.reciprocal_rank_fusion(all_lists)

        # --- 4. CrossEncoder rerank ---
        top_docs = self.reranker.rerank(user_query, fused, top_k=top_k_docs * 2)

        # --- 5. Filter to relevant sentences ---
        passages = _filter_passages(top_docs, user_query)

        if not passages:
            return "I don't have enough information in the knowledge base to answer this question."

        context = "\n".join(passages[:top_k_docs])

        # --- 6. Prompt LLM ---
        prompt = (
            "<|im_start|>system\n"
            "You are a mental-health information assistant. "
            "Answer ONLY using the provided context. "
            "If the context does not contain the answer, say "
            "\"I cannot find this information in the provided context.\" "
            "Be concise and do not repeat the instructions.<|im_end|>\n"
            "<|im_start|>user\n"
            f"Context:\n{context}\n\n"
            f"Question:\n{user_query}\n\n"
            "Answer:<|im_end|>\n"
            "<|im_start|>assistant\n"
        )

        answer = llm_func(prompt)

        # --- 7. Store history ---
        self.add_to_history(user_query, answer)

        return answer
