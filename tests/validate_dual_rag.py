"""
Validate the dual MGPRAG + Self-RAG routing without external services.

This script uses small fake retrievers/rerankers so it does not require
Pinecone, LM Studio, or model downloads. It proves the orchestration and routing
contracts; use the app normally for live end-to-end validation.

Run:
  python tests/validate_dual_rag.py
"""

from __future__ import annotations

import py_compile
import sys
import types
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _install_dependency_stubs() -> None:
    """Let this orchestration check run even before requirements are installed."""

    dotenv_mod = types.ModuleType("dotenv")
    dotenv_mod.load_dotenv = lambda *args, **kwargs: None
    sys.modules.setdefault("dotenv", dotenv_mod)

    openai_mod = types.ModuleType("openai")
    openai_mod.OpenAI = object
    sys.modules.setdefault("openai", openai_mod)

    safety_mod = types.ModuleType("safety_classifier.classifier")

    class StubSafetyClassifier:
        def __init__(self, *args, **kwargs):
            pass

        def is_crisis(self, text: str) -> bool:
            return False

    safety_mod.SafetyClassifier = StubSafetyClassifier
    sys.modules.setdefault("safety_classifier.classifier", safety_mod)

    @dataclass
    class StubDocument:
        page_content: str
        metadata: dict = field(default_factory=dict)

        def copy(self):
            return StubDocument(self.page_content, dict(self.metadata))

    langchain_mod = types.ModuleType("langchain_core")
    documents_mod = types.ModuleType("langchain_core.documents")
    documents_mod.Document = StubDocument
    sys.modules.setdefault("langchain_core", langchain_mod)
    sys.modules.setdefault("langchain_core.documents", documents_mod)

    hybrid_mod = types.ModuleType("retrieval.hybrid_retriever")

    class StubHybridRetriever:
        def __init__(self, *args, **kwargs):
            pass

    hybrid_mod.HybridRetriever = StubHybridRetriever
    sys.modules.setdefault("retrieval.hybrid_retriever", hybrid_mod)

    rrf_mod = types.ModuleType("retrieval.rrf_rerank")

    class StubRRF:
        def __init__(self, *args, **kwargs):
            pass

    rrf_mod.RerankedRRF = StubRRF
    sys.modules.setdefault("retrieval.rrf_rerank", rrf_mod)


_install_dependency_stubs()

from langchain_core.documents import Document

import chat_pipeline
from retrieval.rag_pipeline import MentalHealthRAG, _THERAPY_INDEX


class FakeRetriever:
    def __init__(self, index_name: str):
        self.index_name = index_name
        self.calls: list[str] = []

    def hybrid_search(
        self,
        query: str,
        k: int = 10,
        bm25_weight: float | None = None,
        dense_weight: float | None = None,
    ) -> list[Document]:
        self.calls.append(query)
        if self.index_name == "mental-health-clinical":
            return [
                Document(
                    page_content="Anxiety disorders can involve persistent worry, fear, and physical tension.",
                    metadata={"condition": "anxiety disorder", "section": "symptoms"},
                )
            ]

        return [
            Document(
                page_content=(
                    "Technique: grounding. Try naming five things you can see, "
                    "four you can feel, three you can hear, two you can smell, "
                    "and one you can taste."
                ),
                metadata={
                    "technique_name": "5-4-3-2-1 Grounding",
                    "modality": "mindfulness",
                    "chunk_type": "summary",
                    "chunk_index": 0,
                },
            )
        ]


class FakeReranker:
    def reciprocal_rank_fusion(self, doc_lists: list[list[Document]], k: int = 60) -> list[Document]:
        return [doc for docs in doc_lists for doc in docs]

    def rerank(self, query: str, docs: list[Document], top_k: int = 5) -> list[Document]:
        return docs[:top_k]


def build_fake_rag() -> MentalHealthRAG:
    rag = MentalHealthRAG.__new__(MentalHealthRAG)
    rag.debug = False
    rag.clinical = FakeRetriever("mental-health-clinical")
    rag.therapy = FakeRetriever(_THERAPY_INDEX)
    rag.reranker = FakeReranker()
    rag.chat_history = []
    rag._last_passages = []
    rag._last_retrieval_mode = "clinical"
    rag._last_therapy_plan = None
    rag._last_self_rag = None
    rag._last_refined_queries = []
    return rag


def make_fake_llm() -> Callable[[str], str]:
    state = {"checks": 0}

    def fake_llm(prompt: str) -> str:
        if "retrieval planner" in prompt:
            return """
            {
              "problem": "panic escalation",
              "intent": "calm down with a grounding exercise",
              "emotional_state": "panicky",
              "candidate_techniques": ["5-4-3-2-1 grounding"],
              "candidate_modalities": ["mindfulness"],
              "search_queries": ["grounding exercise panic", "5-4-3-2-1 grounding"]
            }
            """
        if "standalone search" in prompt:
            return '{"queries": ["anxiety disorder symptoms", "anxiety fear tension"]}'
        if "checking retrieved evidence" in prompt:
            state["checks"] += 1
            if state["checks"] == 1:
                return '{"sufficient": false, "missing_concepts": ["specific technique steps"]}'
            return '{"sufficient": true, "missing_concepts": []}'
        if "Generate refined retrieval queries" in prompt:
            return '{"queries": ["specific grounding technique steps"]}'
        return "Grounded answer from retrieved context."

    return fake_llm


class FakeClassifier:
    def is_crisis(self, text: str) -> bool:
        return True


class FakeStore:
    def __init__(self):
        self.appended: list[tuple[str, str, str]] = []

    def session_exists(self, session_id: str) -> bool:
        return True

    def append_turn(self, session_id: str, message: str, answer: str) -> None:
        self.appended.append((session_id, message, answer))

    def count_turns(self, session_id: str) -> int:
        return 0

    def load_history(self, session_id: str, limit: int = 6) -> list[tuple[str, str]]:
        return []

    def get_user_id(self, session_id: str) -> str | None:
        return None


class ExplodingRAG:
    def generate_response(self, *args, **kwargs) -> str:
        raise AssertionError("RAG should not run for crisis messages")


def assert_routes() -> None:
    assert chat_pipeline._route_retrieval_mode("what is anxiety disorder") == "clinical"
    assert chat_pipeline._route_retrieval_mode("symptoms of depression") == "clinical"
    assert chat_pipeline._route_retrieval_mode("how do I calm down") == "therapy"
    assert chat_pipeline._route_retrieval_mode("CBT exercise for intrusive thoughts") == "therapy"


def assert_crisis_bypass() -> None:
    old_classifier = chat_pipeline._classifier
    old_store = chat_pipeline._session_store
    old_rag = chat_pipeline._rag
    try:
        chat_pipeline._classifier = FakeClassifier()
        chat_pipeline._session_store = FakeStore()
        chat_pipeline._rag = ExplodingRAG()
        result = chat_pipeline.run("I want to die", "session-1")
        assert result.is_crisis is True
        assert "crisis support line" in result.text
    finally:
        chat_pipeline._classifier = old_classifier
        chat_pipeline._session_store = old_store
        chat_pipeline._rag = old_rag


def assert_clinical_selfrag() -> None:
    rag = build_fake_rag()
    answer = rag.generate_response(
        "What are the symptoms of anxiety disorder?",
        make_fake_llm(),
        retrieval_mode="clinical",
    )
    assert answer == "Grounded answer from retrieved context."
    assert rag._last_retrieval_mode == "clinical"
    assert rag.clinical.calls
    assert not rag.therapy.calls
    assert rag._last_self_rag["mode"] == "clinical"
    assert rag._last_self_rag["retried"] is True


def assert_therapy_mgprag_selfrag() -> None:
    rag = build_fake_rag()
    answer = rag.generate_response(
        "How do I calm down during panic?",
        make_fake_llm(),
        retrieval_mode="therapy",
    )
    assert answer == "Grounded answer from retrieved context."
    assert rag.therapy.index_name == _THERAPY_INDEX
    assert rag._last_retrieval_mode == "therapy"
    assert rag.therapy.calls
    assert rag._last_therapy_plan["candidate_modalities"] == ["mindfulness"]
    assert rag._last_self_rag["mode"] == "therapy"
    assert rag._last_self_rag["retried"] is True
    assert "5-4-3-2-1 Grounding" in rag._last_passages[0]


def assert_app_compiles() -> None:
    py_compile.compile(str(ROOT / "app.py"), doraise=True)
    py_compile.compile(str(ROOT / "chat_pipeline.py"), doraise=True)
    py_compile.compile(str(ROOT / "retrieval" / "rag_pipeline.py"), doraise=True)


def main() -> None:
    checks = [
        assert_routes,
        assert_crisis_bypass,
        assert_clinical_selfrag,
        assert_therapy_mgprag_selfrag,
        assert_app_compiles,
    ]
    for check in checks:
        check()
        print(f"OK: {check.__name__}")
    print("All dual RAG validation checks passed.")


if __name__ == "__main__":
    main()
