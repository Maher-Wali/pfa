from __future__ import annotations

from agents.config import Settings, get_settings
from agents.database import ConversationDB
from agents.llm import build_llm, invoke_text
from agents.prompts import CONTENT_CREATOR_SYSTEM, CRITIC_SYSTEM, REVISER_SYSTEM
from agents.rag import RAGStore, format_context


class ContentCreationAgent:
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

        docs = self.rag.retrieve(
            user_input,
            top_k=self.settings.top_k_docs,
        )
        context = format_context(docs)

        draft = self._draft(user_input=user_input, context=context)
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
                "critique": critique,
                "rag_context": context,
            },
        )

        return {
            "conversation_id": conversation_id,
            "mode": "content_creation",
            "answer": final_answer,
            "critique": critique,
        }

    def _draft(self, user_input: str, context: str) -> str:
        prompt = f"""
Retrieved context:
{context}

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