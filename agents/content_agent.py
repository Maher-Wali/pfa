from __future__ import annotations

from agents.config import Settings, get_settings
from agents.utils import (
    strip_dashes,
    strip_emojis,
    strip_critique_bleed,
    _resolve_dual_verdict,
    _filter_hallucinated_must_fix,
    _cap_must_fix,
)
from agents.database import ConversationDB
from agents.llm import build_llm, invoke_text
from agents.prompts import CONTENT_CREATOR_SYSTEM, CONTENT_CRITIC_SYSTEM, CONTENT_REVISER_SYSTEM
from agents.rag import RAGStore, format_context, messages_to_history

_CRITIQUE_MAX_TOKENS = 500
_REVISE_MAX_TOKENS = 2000

# Purely creative/marketing requests where clinical RAG adds noise rather than value
_SKIP_RAG_PATTERNS = (
    "elevator pitch",
    "instagram caption",
    "instagram post",
    "social media caption",
    "app description",
    "product description",
    "service description",
)


def _should_retrieve(user_input: str) -> bool:
    lower = user_input.lower()
    return not any(p in lower for p in _SKIP_RAG_PATTERNS)


class ContentCreationAgent:
    INFORMATIONAL = True  # keyword-heavy queries suit BM25-dominant retrieval

    def __init__(
        self,
        settings: Settings | None = None,
        db: ConversationDB | None = None,
        debug: bool = False,
    ):
        self.settings = settings or get_settings()
        self.db = db or ConversationDB(self.settings.sqlite_db_path)

        self.llm = build_llm(self.settings, temperature=0.4)

        self.rag = RAGStore(
            index_name=self.settings.db1_index_name,
            therapy_index_name=self.settings.db1_index_name,
            embedding_model_name=self.settings.embedding_model_name,
            reranker_model_name=self.settings.reranker_model_name,
            debug=debug,
        )

    def create_conversation(
        self,
        user_id: str,
        title: str | None = None,
    ) -> str:
        return self.db.create_conversation(
            user_id=user_id,
            mode="content_creation",
            title=title,
        )

    def respond(
        self,
        user_id: str,
        user_input: str,
        conversation_id: str | None = None,
    ) -> dict:
        if conversation_id is None:
            conversation_id = self.create_conversation(user_id=user_id)

        self.db.add_message(
            conversation_id=conversation_id,
            role="user",
            content=user_input,
        )

        recent_messages = self.db.get_recent_messages(
            conversation_id=conversation_id,
            limit=6,
        )
        history = messages_to_history(recent_messages)
        llm_func = lambda prompt: invoke_text(self.llm, "", prompt)

        if _should_retrieve(user_input):
            docs = self.rag.retrieve(
                query=user_input,
                top_k=self.settings.top_k_docs,
                informational=self.INFORMATIONAL,
                retrieval_mode="clinical",
                history=history,
                llm_func=llm_func,
            )
        else:
            docs = []
        context = format_context(docs)

        draft = self._draft(
            user_input=user_input,
            context=context,
            recent_messages=recent_messages,
        )
        critique = self._critique(
            user_input=user_input,
            context=context,
            draft=draft,
        )

        if "VERDICT: APPROVED" in critique and "VERDICT: NEEDS_REVISION" not in critique:
            final_answer = strip_emojis(strip_dashes(draft))
        else:
            revised = self._revise(
                user_input=user_input,
                context=context,
                draft=draft,
                critique=critique,
            )
            final_answer = strip_emojis(strip_dashes(strip_critique_bleed(revised)))

        rag_docs = [
            {
                "source": (
                    doc.metadata.get("technique_name")
                    or doc.metadata.get("source")
                    or doc.metadata.get("title")
                    or doc.metadata.get("condition")
                    or f"Doc {i}"
                ),
                "text": doc.page_content.replace("\n", " ").strip()[:400],
            }
            for i, doc in enumerate(docs, 1)
        ]

        retrieval_mode = "clinical" if docs else "none"
        self.db.add_message(
            conversation_id=conversation_id,
            role="assistant",
            content=final_answer,
            metadata={
                "retrieval_mode": retrieval_mode,
                "draft": draft,
                "critique": critique,
                "rag_docs": rag_docs,
            },
        )

        return {
            "conversation_id": conversation_id,
            "mode": "content_creation",
            "answer": final_answer,
            "critique": critique,
        }

    def compare(self, user_input: str) -> dict:
        """One-shot retrieval + generation without writing to the DB. For the /compare route."""
        llm_func = lambda prompt: invoke_text(self.llm, "", prompt)
        docs = self.rag.retrieve(
            query=user_input,
            top_k=self.settings.top_k_docs,
            informational=self.INFORMATIONAL,
            history=[],
            llm_func=llm_func,
        ) if _should_retrieve(user_input) else []
        context = format_context(docs)
        draft = self._draft(user_input=user_input, context=context, recent_messages=[])
        critique = self._critique(user_input=user_input, context=context, draft=draft)
        if "VERDICT: APPROVED" in critique and "VERDICT: NEEDS_REVISION" not in critique:
            answer = strip_emojis(strip_dashes(draft))
        else:
            answer = strip_emojis(strip_dashes(strip_critique_bleed(
                self._revise(user_input=user_input, context=context, draft=draft, critique=critique)
            )))

        passages = [
            {
                "source": (
                    doc.metadata.get("source")
                    or doc.metadata.get("title")
                    or doc.metadata.get("condition")
                    or f"Doc {i}"
                ),
                "text": doc.page_content.replace("\n", " ").strip()[:600],
            }
            for i, doc in enumerate(docs, 1)
        ]

        return {"answer": answer, "passages": passages, "critique": critique}

    def compare_selfrag(self, user_input: str) -> dict:
        """Same as compare() but retrieval uses the Self-RAG sufficiency-check loop."""
        llm_func = lambda prompt: invoke_text(self.llm, "", prompt)
        docs, selfrag_state = self.rag.retrieve_selfrag(
            query=user_input,
            top_k=self.settings.top_k_docs,
            informational=self.INFORMATIONAL,
            llm_func=llm_func,
        )
        context = format_context(docs)
        draft = self._draft(user_input=user_input, context=context, recent_messages=[])
        critique = self._critique(user_input=user_input, context=context, draft=draft)
        if "VERDICT: APPROVED" in critique and "VERDICT: NEEDS_REVISION" not in critique:
            answer = strip_emojis(strip_dashes(draft))
        else:
            answer = strip_emojis(strip_dashes(strip_critique_bleed(
                self._revise(user_input=user_input, context=context, draft=draft, critique=critique)
            )))

        passages = [
            {
                "source": (
                    doc.metadata.get("source")
                    or doc.metadata.get("title")
                    or doc.metadata.get("condition")
                    or f"Doc {i}"
                ),
                "text": doc.page_content.replace("\n", " ").strip()[:600],
            }
            for i, doc in enumerate(docs, 1)
        ]

        return {
            "answer": answer,
            "passages": passages,
            "critique": critique,
            "selfrag_state": selfrag_state,
        }

    def _draft(
        self,
        user_input: str,
        context: str,
        recent_messages: list[dict],
    ) -> str:
        history = "\n".join(
            f"{m['role']}: {m['content']}" for m in recent_messages
        )

        lower = user_input.lower()
        format_hint = ""
        if "single tweet" in lower or "one tweet" in lower:
            format_hint = "\nFormat requirement: output exactly one tweet with no numbering. Must not exceed 280 characters.\n"
        elif "tweet" in lower or "twitter thread" in lower:
            format_hint = "\nFormat requirement: each tweet must be its own paragraph, numbered (e.g. 1/5, 2/5), and must not exceed 280 characters.\n"

        prompt = f"""
Recent conversation:
{history}

Retrieved context:
{context}
{format_hint}
User request:
{user_input}

Create the best possible content.
Ask no follow-up unless absolutely necessary.
""".strip()

        return invoke_text(self.llm, CONTENT_CREATOR_SYSTEM, prompt)

    def _critique(
        self,
        user_input: str,
        context: str,
        draft: str,
    ) -> str:
        prompt = f"""
User request:
{user_input}

Retrieved context:
{context}

Draft answer:
{draft}
""".strip()

        raw = invoke_text(self.llm, CONTENT_CRITIC_SYSTEM, prompt, max_tokens=_CRITIQUE_MAX_TOKENS)
        raw = _resolve_dual_verdict(raw)
        raw = _filter_hallucinated_must_fix(raw, draft)
        return _cap_must_fix(raw)

    def _revise(
        self,
        user_input: str,
        context: str,
        draft: str,
        critique: str,
    ) -> str:
        prompt = f"""
User request:
{user_input}

Retrieved context:
{context}

Draft answer:
{draft}

Critique:
{critique}
""".strip()

        return invoke_text(self.llm, CONTENT_REVISER_SYSTEM, prompt, max_tokens=_REVISE_MAX_TOKENS)
