# retrieval/rag_pipeline.py
#
# Dual RAG orchestrator.
#
# Clinical route:
#   query rewrite -> clinical hybrid retrieval -> RRF -> rerank -> Self-RAG
#   sufficiency check -> optional refined retrieval -> grounded answer
#
# Therapy route:
#   structured MGPRAG parse -> therapy hybrid retrieval -> metadata precision
#   boosts -> RRF -> rerank -> Self-RAG sufficiency check -> optional refined
#   retrieval -> grounded supportive answer

from __future__ import annotations

import json
import re
from typing import Any, Callable, List, Tuple

from langchain_core.documents import Document

from retrieval.hybrid_retriever import HybridRetriever
from retrieval.rrf_rerank import RerankedRRF


_CLINICAL_INDEX = "mental-health-clinical"
_THERAPY_INDEX = "mental-health-therapy"


THERAPY_PLAN_KEYS = (
    "problem",
    "intent",
    "emotional_state",
    "candidate_techniques",
    "candidate_modalities",
    "search_queries",
)


def _extract_json_object(raw: str) -> dict[str, Any] | None:
    """Parse a JSON object while tolerating code fences and surrounding text."""
    if not raw:
        return None

    text = raw.strip()
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) >= 3:
            text = parts[1].strip()
            if text.startswith("json"):
                text = text[4:].strip()

    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except Exception:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None

    try:
        data = json.loads(text[start : end + 1])
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _clean_string_list(value: Any, max_items: int = 6) -> list[str]:
    if isinstance(value, str):
        items = [value]
    elif isinstance(value, list):
        items = value
    else:
        return []

    cleaned: list[str] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, str):
            continue
        text = item.strip()
        key = text.lower()
        if text and key not in seen:
            cleaned.append(text)
            seen.add(key)
        if len(cleaned) >= max_items:
            break
    return cleaned


def _first_string(data: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _norm(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").lower()).strip()


def _contains_match(haystack: str, needles: list[str]) -> bool:
    hay = _norm(haystack)
    return bool(hay) and any(
        needle and (_norm(needle) in hay or hay in _norm(needle))
        for needle in needles
    )


def _rewrite_queries(
    query: str,
    history: List[Tuple[str, str]],
    llm_func: Callable[[str], str],
) -> List[str]:
    """Rewrite a clinical/factual query into up to 3 standalone searches."""
    history_text = "\n".join(f"User: {u}\nAssistant: {a}" for u, a in history[-6:])

    prompt = f"""You are a mental-health information retrieval assistant.

Given the conversation and the current question, generate 3 standalone search
queries that capture the full clinical/factual intent. Each query should be
self-contained.

Conversation:
{history_text}

Current question:
{query}

Output ONLY valid JSON:
{{"queries": ["q1", "q2", "q3"]}}
"""
    try:
        data = _extract_json_object(llm_func(prompt)) or {}
        queries = _clean_string_list(data.get("queries"), max_items=3)
    except Exception:
        queries = []

    return queries or [query]


def _fallback_therapy_plan(query: str) -> dict[str, Any]:
    return {
        "problem": query,
        "intent": "",
        "emotional_state": "",
        "candidate_techniques": [],
        "candidate_modalities": [],
        "search_queries": [query],
    }


def parse_therapy_query(
    query: str,
    history: List[Tuple[str, str]],
    llm_func: Callable[[str], str],
) -> dict[str, Any]:
    """
    Parse a therapy/coaching query into MGPRAG retrieval fields.

    The parser is fail-soft: invalid JSON, missing fields, or model errors fall
    back to one raw search query rather than blocking retrieval.
    """
    history_text = "\n".join(f"User: {u}\nAssistant: {a}" for u, a in history[-6:])

    prompt = f"""You are a retrieval planner for a mental-health self-help knowledge base.

Extract the user's practical support need. Do not diagnose. Prefer concrete
therapy skills, coping exercises, and modalities when explicit or strongly
implied by the conversation.

Useful mappings:
- catastrophizing -> CBT, thought challenging
- panic escalation -> breathing, grounding, relaxation
- intrusive thoughts -> CBT, ACT, defusion
- rumination -> cognitive restructuring, mindfulness
- emotional overwhelm -> grounding, DBT, distress tolerance

Conversation:
{history_text}

Current user message:
{query}

Output ONLY valid JSON with exactly these keys:
{{
  "problem": "brief description of the problem or situation",
  "intent": "what practical help is being requested",
  "emotional_state": "brief emotion/state if present, otherwise empty string",
  "candidate_techniques": ["specific techniques or exercises, if any"],
  "candidate_modalities": ["CBT", "DBT", "mindfulness", "ACT", "relaxation", "..."],
  "search_queries": ["q1", "q2", "q3"]
}}
"""
    fallback = _fallback_therapy_plan(query)

    try:
        data = _extract_json_object(llm_func(prompt))
    except Exception:
        data = None

    if not data:
        return fallback

    plan = fallback.copy()
    problem = _first_string(data, ("problem", "user_problem"))
    intent = _first_string(data, ("intent", "therapy_intent"))
    emotional_state = _first_string(data, ("emotional_state",))

    if problem:
        plan["problem"] = problem
    if intent:
        plan["intent"] = intent
    if emotional_state:
        plan["emotional_state"] = emotional_state

    plan["candidate_techniques"] = _clean_string_list(
        data.get("candidate_techniques"),
        max_items=8,
    )
    plan["candidate_modalities"] = _clean_string_list(
        data.get("candidate_modalities") or data.get("modalities"),
        max_items=8,
    )
    plan["search_queries"] = _clean_string_list(
        data.get("search_queries"),
        max_items=3,
    ) or [query]

    return plan


def _format_passages(docs: List[Document], max_len: int = 10_000) -> List[str]:
    passages = []
    for doc in docs:
        text = doc.page_content.replace("\n", " ").strip()
        if len(text) > max_len:
            cut = text[:max_len].rfind(". ")
            text = text[: cut + 1] if cut > max_len // 2 else text[:max_len]
        label = (
            doc.metadata.get("condition")
            or doc.metadata.get("technique_name")
            or doc.metadata.get("source")
            or "Doc"
        )
        passages.append(f"[{label}] {text}")
    return passages


def _format_therapy_passages(docs: List[Document], max_len: int = 10_000) -> List[str]:
    passages = []
    for doc in docs:
        text = doc.page_content.replace("\n", " ").strip()
        if len(text) > max_len:
            cut = text[:max_len].rfind(". ")
            text = text[: cut + 1] if cut > max_len // 2 else text[:max_len]

        parts = [str(doc.metadata.get("technique_name") or "Therapy passage")]
        modality = doc.metadata.get("modality")
        chunk_type = doc.metadata.get("chunk_type")
        if modality:
            parts.append(str(modality))
        if chunk_type:
            parts.append(str(chunk_type))
        passages.append(f"[{' | '.join(parts)}] {text}")
    return passages


def _infer_chunk_type_targets(query: str, plan: dict[str, Any]) -> list[str]:
    combined = " ".join(
        [
            query,
            str(plan.get("intent", "")),
            " ".join(plan.get("search_queries", [])),
        ]
    ).lower()
    practice_terms = (
        "exercise",
        "technique",
        "skill",
        "strategy",
        "coping",
        "grounding",
        "breathing",
        "practice",
        "steps",
        "worksheet",
        "right now",
        "calm down",
    )
    if any(term in combined for term in practice_terms):
        return ["summary", "exercise", "worksheet", "steps", "practice", "prose"]
    return ["summary"]


def _therapy_precision_score(
    doc: Document,
    plan: dict[str, Any],
    query: str,
) -> tuple[float, list[str]]:
    techniques = _clean_string_list(plan.get("candidate_techniques"), max_items=12)
    modalities = _clean_string_list(
        plan.get("candidate_modalities") or plan.get("modalities"),
        max_items=12,
    )
    chunk_targets = _infer_chunk_type_targets(query, plan)

    technique_name = _norm(doc.metadata.get("technique_name"))
    modality = _norm(doc.metadata.get("modality"))
    chunk_type = _norm(doc.metadata.get("chunk_type"))

    score = 0.0
    matches: list[str] = []

    if techniques and _contains_match(technique_name, techniques):
        score += 1.6
        matches.append("technique_name")

    if modalities and _contains_match(modality, modalities):
        score += 1.1
        matches.append("modality")

    if chunk_type and _contains_match(chunk_type, chunk_targets):
        score += 0.7
        matches.append("chunk_type")

    combined_query = _norm(" ".join([query, *plan.get("search_queries", [])]))
    if technique_name and any(
        token in combined_query for token in technique_name.split() if len(token) > 4
    ):
        score += 0.35
        matches.append("technique_token")

    generic_markers = (
        "overview",
        "about",
        "types of",
        "treatments for",
        "research",
        "provider",
        "about us",
        "contact us",
    )
    if any(marker in technique_name for marker in generic_markers):
        score -= 0.25

    return score, matches


def _rank_therapy_docs_by_precision(
    docs: List[Document],
    plan: dict[str, Any],
    query: str,
) -> List[Document]:
    ranked: list[Document] = []
    for doc in docs:
        copy = doc.copy()
        precision, matches = _therapy_precision_score(copy, plan, query)
        copy.metadata["therapy_precision_score"] = precision
        copy.metadata["therapy_precision_matches"] = matches
        copy.metadata["therapy_weighted_score"] = (
            float(copy.metadata.get("hybrid_score", 0.0)) + precision
        )
        ranked.append(copy)

    return sorted(
        ranked,
        key=lambda d: (
            float(d.metadata.get("therapy_weighted_score", 0.0)),
            float(d.metadata.get("hybrid_score", 0.0)),
        ),
        reverse=True,
    )


def _doc_key(doc: Document) -> tuple[str, str, str, str, str]:
    return (
        doc.page_content[:500],
        str(doc.metadata.get("condition", "")),
        str(doc.metadata.get("technique_name", "")),
        str(doc.metadata.get("modality", "")),
        str(doc.metadata.get("chunk_index", "")),
    )


def _dedupe_docs(docs: List[Document]) -> List[Document]:
    seen: set[tuple[str, str, str, str, str]] = set()
    unique: list[Document] = []
    for doc in docs:
        key = _doc_key(doc)
        if key in seen:
            continue
        seen.add(key)
        unique.append(doc)
    return unique


def _parse_self_rag_response(raw: str, has_context: bool) -> dict[str, Any]:
    data = _extract_json_object(raw)
    if not data:
        return {
            "sufficient": bool(has_context),
            "missing_concepts": [],
            "reason": "Fallback sufficiency decision because JSON parsing failed.",
        }

    sufficient = data.get("sufficient")
    if isinstance(sufficient, str):
        sufficient = sufficient.strip().lower() in {"true", "yes", "sufficient"}
    elif not isinstance(sufficient, bool):
        sufficient = bool(has_context)

    return {
        "sufficient": sufficient,
        "missing_concepts": _clean_string_list(
            data.get("missing_concepts"),
            max_items=6,
        ),
        "reason": data.get("reason", "") if isinstance(data.get("reason"), str) else "",
    }


class MentalHealthRAG:
    """
    History-aware dual RAG pipeline over clinical and therapy Pinecone indexes.

    The default retrieval/generation mode is clinical to preserve the original
    public API. Pass retrieval_mode="therapy" or "auto" to use the DB2 path.
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

        print("Initialising clinical retriever...")
        self.clinical = HybridRetriever(
            index_name=clinical_index,
            bm25_weight=bm25_weight,
            dense_weight=dense_weight,
            debug=debug,
        )

        print("Initialising therapy retriever...")
        self.therapy = HybridRetriever(
            index_name=therapy_index,
            bm25_weight=bm25_weight,
            dense_weight=dense_weight,
            debug=debug,
        )

        self.reranker = RerankedRRF(model_name=reranker_model)
        self.chat_history: List[Tuple[str, str]] = []
        self._last_passages: List[str] = []
        self._last_retrieval_mode: str = "clinical"
        self._last_therapy_plan: dict[str, Any] | None = None
        self._last_self_rag: dict[str, Any] | None = None
        self._last_refined_queries: List[str] = []

    def add_to_history(self, user_query: str, assistant_answer: str) -> None:
        self.chat_history.append((user_query, assistant_answer))

    def clear_history(self) -> None:
        self.chat_history.clear()

    def _resolve_retrieval_mode(self, retrieval_mode: str, informational: bool) -> str:
        mode = (retrieval_mode or "clinical").strip().lower()
        if mode == "auto":
            return "clinical" if informational else "therapy"
        if mode not in {"clinical", "therapy"}:
            raise ValueError(
                "retrieval_mode must be 'clinical', 'therapy', or 'auto'."
            )
        return mode

    def _retrieve_clinical_from_queries(
        self,
        user_query: str,
        queries: List[str],
        top_k_docs: int,
        informational: bool,
    ) -> List[Document]:
        bm25_w, dense_w = (0.70, 0.30) if informational else (0.35, 0.65)

        if self.debug:
            print(f"Clinical queries: {queries}")
            print(f"Clinical hybrid weights: BM25={bm25_w}, dense={dense_w}")

        all_lists: List[List[Document]] = []
        for q in queries[:3]:
            docs = self.clinical.hybrid_search(
                q,
                k=top_k_docs * 3,
                bm25_weight=bm25_w,
                dense_weight=dense_w,
            )
            all_lists.append(docs)

        fused = _dedupe_docs(self.reranker.reciprocal_rank_fusion(all_lists))
        return self.reranker.rerank(user_query, fused, top_k=top_k_docs)

    def _retrieve_therapy_from_plan(
        self,
        user_query: str,
        plan: dict[str, Any],
        top_k_docs: int,
        search_queries: List[str] | None = None,
    ) -> List[Document]:
        queries = search_queries or plan.get("search_queries") or [user_query]

        if self.debug:
            print(f"Therapy plan: {json.dumps(plan, ensure_ascii=False)}")
            print(f"Therapy queries: {queries}")

        all_lists: List[List[Document]] = []
        for q in queries[:3]:
            docs = self.therapy.hybrid_search(
                q,
                k=top_k_docs * 4,
                bm25_weight=0.45,
                dense_weight=0.55,
            )
            all_lists.append(_rank_therapy_docs_by_precision(docs, plan, user_query))

        fused = _dedupe_docs(self.reranker.reciprocal_rank_fusion(all_lists))
        fused = _rank_therapy_docs_by_precision(fused, plan, user_query)
        reranked = self.reranker.rerank(user_query, fused, top_k=top_k_docs * 2)
        return _rank_therapy_docs_by_precision(reranked, plan, user_query)[:top_k_docs]

    def _self_rag_check(
        self,
        user_query: str,
        passages: List[str],
        llm_func: Callable[[str], str],
        mode: str,
        plan: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not passages:
            return {
                "sufficient": False,
                "missing_concepts": ["retrieved evidence"],
                "reason": "No passages were retrieved.",
            }

        criteria = (
            "The evidence must support a practical intervention or technique "
            "without requiring invented steps."
            if mode == "therapy"
            else "The evidence must directly support the factual answer and "
            "cover the main clinical concepts."
        )
        plan_text = json.dumps(plan, ensure_ascii=False) if plan else "{}"
        context = "\n".join(passages)
        prompt = f"""You are checking retrieved evidence before answer generation.

Mode: {mode}
User request:
{user_query}

Structured therapy plan, if any:
{plan_text}

Retrieved evidence:
{context}

Does the retrieved evidence sufficiently support answering the user request?
{criteria}

Output ONLY valid JSON:
{{
  "sufficient": true,
  "missing_concepts": [],
  "reason": "brief reason"
}}
"""
        try:
            result = _parse_self_rag_response(llm_func(prompt), has_context=True)
        except Exception:
            result = {
                "sufficient": True,
                "missing_concepts": [],
                "reason": "Fallback sufficiency decision because the check failed.",
            }

        if self.debug:
            print(f"Self-RAG check ({mode}): {result}")
        return result

    def _refine_queries(
        self,
        user_query: str,
        missing_concepts: List[str],
        llm_func: Callable[[str], str],
        mode: str,
        plan: dict[str, Any] | None = None,
    ) -> List[str]:
        missing = ", ".join(missing_concepts) if missing_concepts else "missing details"
        plan_text = json.dumps(plan, ensure_ascii=False) if plan else "{}"
        prompt = f"""Generate refined retrieval queries for a mental-health RAG system.

Mode: {mode}
User request:
{user_query}

Structured therapy plan, if any:
{plan_text}

Missing concepts from the retrieved evidence:
{missing}

Output ONLY valid JSON:
{{"queries": ["q1", "q2", "q3"]}}
"""
        try:
            data = _extract_json_object(llm_func(prompt)) or {}
            queries = _clean_string_list(data.get("queries"), max_items=3)
        except Exception:
            queries = []

        if not queries:
            queries = [f"{user_query} {missing}".strip()]

        self._last_refined_queries = queries
        return queries

    def retrieve(
        self,
        user_query: str,
        llm_func: Callable[[str], str],
        top_k_docs: int = 5,
        informational: bool = True,
        retrieval_mode: str = "clinical",
    ) -> List[Document]:
        """
        Retrieve and rerank without generating an answer.

        The default mode remains clinical for backward compatibility.
        """
        mode = self._resolve_retrieval_mode(retrieval_mode, informational)
        if mode == "therapy":
            return self.retrieve_therapy(user_query, llm_func, top_k_docs=top_k_docs)

        rewritten = _rewrite_queries(user_query, self.chat_history, llm_func)
        docs = self._retrieve_clinical_from_queries(
            user_query=user_query,
            queries=rewritten,
            top_k_docs=top_k_docs,
            informational=informational,
        )
        self._last_passages = _format_passages(docs)
        self._last_retrieval_mode = "clinical"
        self._last_therapy_plan = None
        self._last_self_rag = None
        self._last_refined_queries = []
        return docs

    def retrieve_clinical(
        self,
        user_query: str,
        llm_func: Callable[[str], str],
        top_k_docs: int = 5,
        informational: bool = True,
    ) -> List[Document]:
        return self.retrieve(
            user_query=user_query,
            llm_func=llm_func,
            top_k_docs=top_k_docs,
            informational=informational,
            retrieval_mode="clinical",
        )

    def retrieve_therapy(
        self,
        user_query: str,
        llm_func: Callable[[str], str],
        top_k_docs: int = 5,
    ) -> List[Document]:
        plan = parse_therapy_query(user_query, self.chat_history, llm_func)
        docs = self._retrieve_therapy_from_plan(
            user_query=user_query,
            plan=plan,
            top_k_docs=top_k_docs,
        )
        self._last_passages = _format_therapy_passages(docs)
        self._last_retrieval_mode = "therapy"
        self._last_therapy_plan = plan
        self._last_self_rag = None
        self._last_refined_queries = []
        return docs

    def _clinical_selfrag_docs(
        self,
        user_query: str,
        llm_func: Callable[[str], str],
        top_k_docs: int,
        informational: bool,
    ) -> tuple[List[Document], dict[str, Any]]:
        self._last_refined_queries = []
        queries = _rewrite_queries(user_query, self.chat_history, llm_func)
        docs = self._retrieve_clinical_from_queries(
            user_query=user_query,
            queries=queries,
            top_k_docs=top_k_docs * 2,
            informational=informational,
        )
        passages = _format_passages(docs)[:top_k_docs]
        initial = self._self_rag_check(
            user_query=user_query,
            passages=passages,
            llm_func=llm_func,
            mode="clinical",
        )

        state: dict[str, Any] = {
            "mode": "clinical",
            "initial": initial,
            "retried": False,
            "final": initial,
            "refined_queries": [],
        }

        if not initial.get("sufficient", False):
            refined = self._refine_queries(
                user_query=user_query,
                missing_concepts=initial.get("missing_concepts", []),
                llm_func=llm_func,
                mode="clinical",
            )
            retry_docs = self._retrieve_clinical_from_queries(
                user_query=user_query,
                queries=refined,
                top_k_docs=top_k_docs * 2,
                informational=informational,
            )
            docs = self.reranker.rerank(
                user_query,
                _dedupe_docs([*docs, *retry_docs]),
                top_k=top_k_docs * 2,
            )
            passages = _format_passages(docs)[:top_k_docs]
            final = self._self_rag_check(
                user_query=user_query,
                passages=passages,
                llm_func=llm_func,
                mode="clinical",
            )
            state.update(
                {
                    "retried": True,
                    "final": final,
                    "refined_queries": refined,
                }
            )

        self._last_self_rag = state
        return docs[: top_k_docs * 2], state

    def _therapy_selfrag_docs(
        self,
        user_query: str,
        llm_func: Callable[[str], str],
        top_k_docs: int,
    ) -> tuple[List[Document], dict[str, Any]]:
        self._last_refined_queries = []
        plan = parse_therapy_query(user_query, self.chat_history, llm_func)
        docs = self._retrieve_therapy_from_plan(
            user_query=user_query,
            plan=plan,
            top_k_docs=top_k_docs * 2,
        )
        passages = _format_therapy_passages(docs)[:top_k_docs]
        initial = self._self_rag_check(
            user_query=user_query,
            passages=passages,
            llm_func=llm_func,
            mode="therapy",
            plan=plan,
        )

        state: dict[str, Any] = {
            "mode": "therapy",
            "initial": initial,
            "retried": False,
            "final": initial,
            "refined_queries": [],
        }

        if not initial.get("sufficient", False):
            refined = self._refine_queries(
                user_query=user_query,
                missing_concepts=initial.get("missing_concepts", []),
                llm_func=llm_func,
                mode="therapy",
                plan=plan,
            )
            retry_docs = self._retrieve_therapy_from_plan(
                user_query=user_query,
                plan=plan,
                top_k_docs=top_k_docs * 2,
                search_queries=refined,
            )
            docs = _rank_therapy_docs_by_precision(
                _dedupe_docs([*docs, *retry_docs]),
                plan,
                user_query,
            )
            docs = self.reranker.rerank(user_query, docs, top_k=top_k_docs * 2)
            docs = _rank_therapy_docs_by_precision(docs, plan, user_query)
            passages = _format_therapy_passages(docs)[:top_k_docs]
            final = self._self_rag_check(
                user_query=user_query,
                passages=passages,
                llm_func=llm_func,
                mode="therapy",
                plan=plan,
            )
            state.update(
                {
                    "retried": True,
                    "final": final,
                    "refined_queries": refined,
                }
            )

        self._last_self_rag = state
        self._last_therapy_plan = plan
        return docs[: top_k_docs * 2], state

    def generate_response(
        self,
        user_query: str,
        llm_func: Callable[[str], str],
        top_k_docs: int = 5,
        informational: bool = True,
        retrieval_mode: str = "clinical",
    ) -> str:
        """
        Generate a grounded answer for user_query.

        retrieval_mode="clinical" preserves the original behavior. Use
        "therapy" for MGPRAG + Self-RAG over mental-health-therapy, or "auto"
        to map informational=True to clinical and False to therapy.
        """
        mode = self._resolve_retrieval_mode(retrieval_mode, informational)
        if mode == "therapy":
            return self.generate_therapy_response(
                user_query=user_query,
                llm_func=llm_func,
                top_k_docs=top_k_docs,
            )

        docs, selfrag = self._clinical_selfrag_docs(
            user_query=user_query,
            llm_func=llm_func,
            top_k_docs=top_k_docs,
            informational=informational,
        )
        self._last_passages = _format_passages(docs)[:top_k_docs]
        self._last_retrieval_mode = "clinical"
        self._last_therapy_plan = None

        evidence_status = (
            "sufficient"
            if selfrag.get("final", {}).get("sufficient")
            else "weak or incomplete"
        )
        context = "\n".join(self._last_passages)
        prompt = f"""Context:
{context}

Evidence status after self-check: {evidence_status}

Question:
{user_query}

Answer using only the context. If the evidence is weak or incomplete, say what
the retrieved sources do not cover instead of guessing.

Answer:"""
        answer = llm_func(prompt)
        self.add_to_history(user_query, answer)
        return answer

    def generate_therapy_response(
        self,
        user_query: str,
        llm_func: Callable[[str], str],
        top_k_docs: int = 5,
    ) -> str:
        docs, selfrag = self._therapy_selfrag_docs(
            user_query=user_query,
            llm_func=llm_func,
            top_k_docs=top_k_docs,
        )
        self._last_passages = _format_therapy_passages(docs)[:top_k_docs]
        self._last_retrieval_mode = "therapy"

        evidence_status = (
            "sufficient"
            if selfrag.get("final", {}).get("sufficient")
            else "weak or incomplete"
        )
        context = "\n".join(self._last_passages)
        plan_text = json.dumps(self._last_therapy_plan or {}, ensure_ascii=False)
        prompt = f"""Retrieved therapy context:
{context}

Structured therapy plan:
{plan_text}

Evidence status after self-check: {evidence_status}

User message:
{user_query}

Answer using only the retrieved therapy context. Be supportive and practical,
but do not diagnose, do not claim to be a therapist, and do not invent steps
that are not supported by the context. Offer one concrete technique or exercise
at a time when appropriate. If the retrieved evidence is weak, briefly say so.
If the difficulty sounds persistent, worsening, or hard to manage alone, gently
mention that professional support could help.

Answer:"""
        answer = llm_func(prompt)
        self.add_to_history(user_query, answer)
        return answer
