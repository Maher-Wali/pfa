from __future__ import annotations

import re

from agents.config import Settings, get_settings

_CRITIQUE_MAX_TOKENS = 500
_REVISE_MAX_TOKENS = 600


def _strip_double_closing_question(text: str) -> str:
    """Remove extra closing questions: line-level and same-paragraph sentence-level."""
    lines = text.splitlines()
    non_empty_indices = [i for i, l in enumerate(lines) if l.strip()]
    # Line-level: last two non-empty lines both end with '?'
    if len(non_empty_indices) >= 2:
        last = lines[non_empty_indices[-1]].strip()
        second_last = lines[non_empty_indices[-2]].strip()
        if last.endswith("?") and second_last.endswith("?"):
            lines.pop(non_empty_indices[-1])
    text = "\n".join(lines).strip()
    # Sentence-level: two or more '?' in the final paragraph — keep only the last sentence
    paragraphs = [p for p in text.split("\n\n") if p.strip()]
    if paragraphs:
        last_para = paragraphs[-1]
        if last_para.count("?") >= 2:
            sentences = re.split(r"(?<=[.!?])\s+", last_para.strip())
            question_sentences = [s for s in sentences if s.endswith("?")]
            if len(question_sentences) >= 2:
                # Keep only the last question sentence
                non_question = [s for s in sentences if not s.endswith("?")]
                paragraphs[-1] = " ".join(non_question + [question_sentences[-1]])
                text = "\n\n".join(paragraphs).strip()
    return text


from agents.utils import strip_dashes
from safety_classifier.classifier import SafetyClassifier
from agents.database import ConversationDB
from agents.llm import build_llm, invoke_text
from agents.prompts import (
    CRITIC_SYSTEM,
    REVISER_SYSTEM,
    SAFE_MODE_SYSTEM,
    THERAPY_AGENT_SYSTEM,
)
from agents.profile_extractor import extract_profile
from agents.rag import RAGStore, format_context, messages_to_history
from chat_pipeline import _route_retrieval_mode
from session.users import User, UserStore

_EXTRACT_EVERY_INCOMPLETE = 2
_EXTRACT_EVERY_COMPLETE = 4


def _resolve_dual_verdict(critique: str) -> str:
    """If the critic wrote two VERDICT lines (self-correction), keep only the last one."""
    needs = "VERDICT: NEEDS_REVISION"
    approved = "VERDICT: APPROVED"
    has_needs = needs in critique
    has_approved = approved in critique
    if not (has_needs and has_approved):
        return critique
    # Find which verdict appears last and strip the earlier one
    last_needs = critique.rfind(needs)
    last_approved = critique.rfind(approved)
    if last_approved > last_needs:
        # Final verdict is APPROVED — drop the NEEDS_REVISION line and everything after it up to APPROVED
        return critique[last_approved:]
    else:
        # Final verdict is NEEDS_REVISION — drop the APPROVED line
        return critique[:last_approved].rstrip() + "\n" + critique[last_needs:]


def _is_looping_bullet(text: str) -> bool:
    # Detect critic reasoning loops: any 6-word span repeating 3+ times signals a loop.
    words = text.split()
    if len(words) < 30:
        return False
    for i in range(len(words) - 5):
        ngram = " ".join(words[i:i + 6])
        if text.count(ngram) >= 3:
            return True
    return False


def _quote_matches_draft(quote: str, draft: str) -> bool:
    # Check if a quoted phrase (possibly with ellipsis ...) appears in the draft.
    if "..." not in quote:
        return quote in draft
    # Split on ellipsis and require all non-empty fragments (>=4 chars) to appear in draft
    fragments = [f.strip() for f in quote.split("...") if len(f.strip()) >= 4]
    return bool(fragments) and all(f in draft for f in fragments)


def _filter_hallucinated_must_fix(critique: str, draft: str) -> str:
    """Drop MUST_FIX items whose quoted phrase cannot be found verbatim in the draft,
    and drop items that are reasoning loops."""
    if "MUST_FIX:" not in critique:
        return critique
    header, _, must_fix_block = critique.partition("MUST_FIX:")
    lines = must_fix_block.splitlines()
    kept = []
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("-"):
            # Drop non-bullet lines (reasoning prose, "So:", "Actually:", etc.)
            if stripped:
                continue
            kept.append(line)  # preserve blank lines as spacing
            continue
        # Drop looping bullets regardless of quoted phrase content
        if _is_looping_bullet(stripped):
            continue
        # Drop bullets where the critic concluded no violation (clean-rule assessments)
        lower = stripped.lower()
        if any(phrase in lower for phrase in ("no violation", "not a violation", "so no violation")):
            continue
        # Extract quoted phrases (text between " or ")
        quotes = re.findall(r'["""]([^"""]{4,})["""]', stripped)
        if not quotes:
            # No quoted phrase — keep the item (can't verify)
            kept.append(line)
            continue
        # Keep the item only if at least one quoted phrase matches the draft
        if any(_quote_matches_draft(q, draft) for q in quotes):
            kept.append(line)
    surviving = [l for l in kept if l.strip().startswith("-")]
    if not surviving:
        # All MUST_FIX items were hallucinated — convert to APPROVED
        return header.rstrip() + "\nVERDICT: APPROVED"
    return header + "MUST_FIX:" + "\n".join(kept)


def _build_profile_block(user: User) -> str | None:
    if not user:
        return None
    lines = ["User profile (use this to personalise your responses — do not recite these facts back verbatim):"]
    goals_str = ", ".join(user.goals) if user.goals else None
    if goals_str:
        lines.append(f"- Goals: {goals_str}")
    if user.age:
        lines.append(f"- Age: {user.age}")
    if user.job:
        lines.append(f"- Job: {user.job}")
    if user.relationship_status:
        lines.append(f"- Relationship status: {user.relationship_status}")
    if len(lines) == 1:
        return None
    return "\n".join(lines)


class VirtualTherapyAgent:
    INFORMATIONAL = False  # conversational queries suit dense-dominant retrieval

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
            index_name=self.settings.db1_index_name,
            therapy_index_name=self.settings.db2_index_name,
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

        retrieval_mode = _route_retrieval_mode(user_input)
        docs = self.rag.retrieve(
            query=user_input,
            top_k=self.settings.top_k_docs,
            informational=self.INFORMATIONAL,
            retrieval_mode=retrieval_mode,
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

        last_assistant = next(
            (m["content"] for m in reversed(recent_messages) if m["role"] == "assistant"),
            None,
        )
        critique = self._critique(
            user_input=user_input,
            context=context,
            draft=draft,
            prev_assistant=last_assistant,
        )

        final_answer = strip_dashes(_strip_double_closing_question(self._revise(
            user_input=user_input,
            context=context,
            draft=draft,
            critique=critique,
        )))

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
                "safe_mode": False,
                "retrieval_mode": retrieval_mode,
                "therapy_plan": self.rag._rag._last_therapy_plan,
                "self_rag": self.rag._rag._last_self_rag,
                "draft": draft,
                "critique": critique,
                "rag_docs": rag_docs,
            },
        )

        self._maybe_extract_profile(user_id=user_id, conversation_id=conversation_id)

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
            informational=self.INFORMATIONAL,
            retrieval_mode=_route_retrieval_mode(user_input),
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
                    doc.metadata.get("technique_name")
                    or doc.metadata.get("source")
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
        answer = self._revise(user_input=user_input, context=context, draft=draft, critique=critique)

        passages = [
            {
                "source": (
                    doc.metadata.get("technique_name")
                    or doc.metadata.get("source")
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

    def _maybe_extract_profile(self, user_id: str, conversation_id: str) -> None:
        total = self.db.count_assistant_messages(conversation_id)
        if total < _EXTRACT_EVERY_INCOMPLETE:
            return
        user = self.user_store.get_by_id(user_id)
        interval = _EXTRACT_EVERY_COMPLETE if (user and user.profile_complete) else _EXTRACT_EVERY_INCOMPLETE
        if total % interval != 0:
            return
        messages = self.db.get_recent_messages(conversation_id=conversation_id, limit=20)
        extracted = extract_profile(self.llm, messages)
        if extracted:
            self.user_store.update_extracted_fields(user_id=user_id, **extracted)

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

        last_assistant = next(
            (m["content"] for m in reversed(recent_messages) if m["role"] == "assistant"),
            None,
        )

        asked_questions = [
            sentence.strip()
            for m in recent_messages if m["role"] == "assistant"
            for sentence in re.split(r"(?<=[.?!])\s+", m["content"])
            if sentence.strip().endswith("?")
        ]

        continuity_section = ""
        if last_assistant:
            questions_block = (
                "\nQuestions already asked in this conversation (do NOT ask any of these again, "
                "or anything semantically equivalent):\n"
                + "\n".join(f"- {q}" for q in asked_questions)
                if asked_questions else ""
            )
            continuity_section = (
                f"\nPrevious assistant turn: {last_assistant}\n"
                f"User's reply to that: {user_input}\n"
                "You MUST directly acknowledge what the user just said before anything else. "
                "Do not re-suggest anything they already answered or committed to.\n"
                f"{questions_block}\n"
            )

        prompt = f"""
Recent conversation:
{history}

Retrieved context:
{context}
{profile_section}{continuity_section}
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
        prev_assistant: str | None = None,
    ) -> str:
        prev_section = f"\nPrevious assistant turn:\n{prev_assistant}\n" if prev_assistant else ""
        prompt = f"""
User request:
{user_input}

Retrieved context:
{context}
{prev_section}
Draft answer:
{draft}
""".strip()

        raw = invoke_text(self.llm, CRITIC_SYSTEM, prompt, max_tokens=_CRITIQUE_MAX_TOKENS)
        raw = _resolve_dual_verdict(raw)
        return _filter_hallucinated_must_fix(raw, draft)

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

        return invoke_text(self.llm, REVISER_SYSTEM, prompt, max_tokens=_REVISE_MAX_TOKENS)

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
