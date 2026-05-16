from __future__ import annotations

from agents.config import Settings, get_settings
from agents.database import ConversationDB
from agents.llm import build_llm, invoke_text
from agents.prompts import CONTENT_CREATOR_SYSTEM, CRITIC_SYSTEM, REVISER_SYSTEM
from agents.rag import RAGStore, format_context, messages_to_history


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
            limit=12,
        )
        history = messages_to_history(recent_messages)
        llm_func = lambda prompt: invoke_text(self.llm, "", prompt)

        docs = self.rag.retrieve(
            query=user_input,
            top_k=self.settings.top_k_docs,
            retrieval_mode="clinical",
            history=history,
            llm_func=llm_func,
        )
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
        final_answer = self._revise(
            user_input=user_input,
            context=context,
            draft=draft,
            critique=critique,
        )

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

        self.db.add_message(
            conversation_id=conversation_id,
            role="assistant",
            content=final_answer,
            metadata={
                "retrieval_mode": "clinical",
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
            informational=True,
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
    ) -> str:
        history = "\n".join(
            f"{m['role']}: {m['content']}" for m in recent_messages
        )

        prompt = f"""
Recent conversation:
{history}

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
