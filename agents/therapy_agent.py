from __future__ import annotations

from agents.config import Settings, get_settings
from safety_classifier.classifier import SafetyClassifier
from agents.database import ConversationDB
from agents.llm import build_llm, invoke_text
from agents.prompts import (
    CRITIC_SYSTEM,
    REVISER_SYSTEM,
    SAFE_MODE_SYSTEM,
    THERAPY_AGENT_SYSTEM,
)
from agents.rag import RAGStore, format_context, messages_to_history
from session.users import User, UserStore


def _build_profile_block(user: User) -> str | None:
    if not user:
        return None
    goals_str = ", ".join(user.goals) if user.goals else "not specified"
    lines = [
        "User profile (use this to personalise your responses — do not recite these facts back verbatim):",
        f"- Mood baseline: {user.mood_baseline}/10",
        f"- Goals: {goals_str}",
    ]
    if user.age:
        lines.append(f"- Age: {user.age}")
    if user.country:
        lines.append(f"- Country: {user.country}")
    if user.job:
        lines.append(f"- Job: {user.job}")
    if user.relationship_status:
        lines.append(f"- Relationship status: {user.relationship_status}")
    return "\n".join(lines)


class VirtualTherapyAgent:
    def __init__(
        self,
        settings: Settings | None = None,
        db: ConversationDB | None = None,
        debug: bool = False,
    ):
        self.settings = settings or get_settings()
        self.db = db or ConversationDB(self.settings.sqlite_db_path)

        self.llm = build_llm(self.settings, temperature=0.35)

        self.rag = RAGStore(
            index_name=self.settings.db2_index_name,
            embedding_model_name=self.settings.embedding_model_name,
            reranker_model_name=self.settings.reranker_model_name,
            debug=debug,
        )

        self.classifier = SafetyClassifier(self.settings.classifier_model_name)

        self.user_store = UserStore()

    def create_conversation(
        self,
        user_id: str,
        title: str | None = None,
    ) -> str:
        return self.db.create_conversation(
            user_id=user_id,
            mode="virtual_therapy",
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

        assistant_count = self.db.count_assistant_messages(conversation_id)
        should_classify = (
            assistant_count > 0
            and assistant_count % self.settings.classify_every_n_turns == 0
        )

        is_crisis = False

        if should_classify:
            is_crisis = self._classify_recent_conversation(conversation_id)
            self.db.update_safety_status(conversation_id, "CRITICAL" if is_crisis else "SAFE")

        if is_crisis:
            final_answer = self._safe_mode_response(user_input)

            self.db.add_message(
                conversation_id=conversation_id,
                role="assistant",
                content=final_answer,
                metadata={"safe_mode": True},
            )

            return {
                "conversation_id": conversation_id,
                "mode": "virtual_therapy",
                "answer": final_answer,
                "safe_mode": True,
            }

        recent_messages = self.db.get_recent_messages(
            conversation_id=conversation_id,
            limit=12,
        )
        history = messages_to_history(recent_messages)
        llm_func = lambda prompt: invoke_text(self.llm, "", prompt)

        docs = self.rag.retrieve(
            query=user_input,
            top_k=self.settings.top_k_docs,
            informational=False,
            history=history,
            llm_func=llm_func,
        )
        context = format_context(docs)

        user = self.user_store.get_by_id(user_id)
        profile_block = _build_profile_block(user) if user else None

        draft = self._draft(
            user_input=user_input,
            context=context,
            recent_messages=recent_messages,
            profile_block=profile_block,
        )

        critique = self._critique(
            user_input=user_input,
            context=context,
            draft=draft,
        )

        final_answer = self._revise(
            user_input=user_input,
            context=context,
            draft=draft,
            critique=critique,
        )

        self.db.add_message(
            conversation_id=conversation_id,
            role="assistant",
            content=final_answer,
            metadata={
                "safe_mode": False,
                "critique": critique,
                "rag_context": context,
            },
        )

        return {
            "conversation_id": conversation_id,
            "mode": "virtual_therapy",
            "answer": final_answer,
            "safe_mode": False,
            "critique": critique,
        }

    def compare(self, user_input: str) -> dict:
        """One-shot retrieval + generation without writing to the DB. For the /compare route."""
        llm_func = lambda prompt: invoke_text(self.llm, "", prompt)
        docs = self.rag.retrieve(
            query=user_input,
            top_k=self.settings.top_k_docs,
            informational=False,
            history=[],
            llm_func=llm_func,
        )
        context = format_context(docs)
        draft = self._draft(user_input=user_input, context=context, recent_messages=[])
        critique = self._critique(user_input=user_input, context=context, draft=draft)
        answer = self._revise(user_input=user_input, context=context, draft=draft, critique=critique)

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

    def _draft(
        self,
        user_input: str,
        context: str,
        recent_messages: list[dict],
        profile_block: str | None = None,
    ) -> str:
        history = "\n".join(
            f"{m['role']}: {m['content']}" for m in recent_messages
        )

        profile_section = f"\n{profile_block}\n" if profile_block else ""

        prompt = f"""
Recent conversation:
{history}

Retrieved context:
{context}
{profile_section}
User message:
{user_input}

Respond supportively and practically.
""".strip()

        return invoke_text(self.llm, THERAPY_AGENT_SYSTEM, prompt)

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

        return invoke_text(self.llm, CRITIC_SYSTEM, prompt)

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

        return invoke_text(self.llm, REVISER_SYSTEM, prompt)

    def _classify_recent_conversation(self, conversation_id: str) -> bool:
        recent_messages = self.db.get_recent_messages(
            conversation_id=conversation_id,
            limit=16,
        )

        text = "\n".join(
            f"{m['role']}: {m['content']}" for m in recent_messages
        )

        return self.classifier.is_crisis(text)

    def _safe_mode_response(self, user_input: str) -> str:
        prompt = f"""
The conversation was classified as CRITICAL.

User's latest message:
{user_input}

Write the next safe-mode message.
""".strip()

        return invoke_text(self.llm, SAFE_MODE_SYSTEM, prompt)
