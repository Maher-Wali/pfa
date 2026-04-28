from __future__ import annotations

from agents.classifier import MentalSafetyClassifier
from agents.config import Settings, get_settings
from agents.database import ConversationDB
from agents.llm import build_llm, invoke_text
from agents.prompts import (
    CRITIC_SYSTEM,
    MOCK_SAFETY_NUMBERS,
    REVISER_SYSTEM,
    SAFE_MODE_SYSTEM,
    THERAPY_AGENT_SYSTEM,
)
from agents.rag import RAGStore, format_context


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

        self.classifier = MentalSafetyClassifier(
            model_name=self.settings.classifier_model_name,
        )

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
            and assistant_count % self.settings.classify_every_agent2_messages == 0
        )

        safety_label = "NOT_CRITICAL"

        if should_classify:
            safety_label = self._classify_recent_conversation(conversation_id)
            self.db.update_safety_status(conversation_id, safety_label)

        if safety_label == "CRITICAL":
            final_answer = self._safe_mode_response(user_input)

            self.db.add_message(
                conversation_id=conversation_id,
                role="assistant",
                content=final_answer,
                metadata={
                    "safe_mode": True,
                    "safety_label": safety_label,
                },
            )

            return {
                "conversation_id": conversation_id,
                "mode": "virtual_therapy",
                "answer": final_answer,
                "safe_mode": True,
                "safety_label": safety_label,
            }

        docs = self.rag.retrieve(
            user_input,
            top_k=self.settings.top_k_docs,
        )
        context = format_context(docs)

        recent_messages = self.db.get_recent_messages(
            conversation_id=conversation_id,
            limit=12,
        )

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
                "safety_label": safety_label,
                "critique": critique,
                "rag_context": context,
            },
        )

        return {
            "conversation_id": conversation_id,
            "mode": "virtual_therapy",
            "answer": final_answer,
            "safe_mode": False,
            "safety_label": safety_label,
            "critique": critique,
        }

    def _draft(
        self,
        user_input: str,
        context: str,
        recent_messages: list[dict],
    ) -> str:
        history = "\n".join(
            f"{message['role']}: {message['content']}"
            for message in recent_messages
        )

        prompt = f"""
Recent conversation:
{history}

Retrieved context:
{context}

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

    def _classify_recent_conversation(
        self,
        conversation_id: str,
    ) -> str:
        recent_messages = self.db.get_recent_messages(
            conversation_id=conversation_id,
            limit=16,
        )

        text = "\n".join(
            f"{message['role']}: {message['content']}"
            for message in recent_messages
        )

        return self.classifier.classify(text)

    def _safe_mode_response(self, user_input: str) -> str:
        prompt = f"""
The conversation was classified as CRITICAL.

User's latest message:
{user_input}

Use these placeholder contacts:
{MOCK_SAFETY_NUMBERS}

Write the next safe-mode message.
""".strip()

        return invoke_text(self.llm, SAFE_MODE_SYSTEM, prompt)