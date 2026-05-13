import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

from openai import OpenAI

from retrieval.rag_pipeline import MentalHealthRAG
from safety_classifier.classifier import SafetyClassifier
from session.store import SessionStore
from session.users import User, UserStore


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CLASSIFIER_PATH = "maherwali/mental-safety-classifier"

CRISIS_RESOURCES = """I'm concerned about what you've shared and I want to make sure you're safe.

Please reach out to a crisis support line right now:
- International Association for Suicide Prevention: https://www.iasp.info/resources/Crisis_Centres/
- Crisis Text Line (US): Text HOME to 741741
- Samaritans (UK): 116 123
- If you are in immediate danger, please call your local emergency services (911, 999, 112).

You don't have to face this alone. A trained counsellor is available right now."""

SYSTEM_PROMPT_COMPANION = """You are a supportive mental health companion. You are NOT a therapist, psychiatrist, or doctor.

Guidelines:
- Always acknowledge and validate the person's emotions before offering information.
- Ask at most one open question per turn.
- Do not diagnose, label symptoms, or speculate about what condition someone may have.
- When the person asks for coping help, offer one practical technique or exercise at a time.
- Ground coping suggestions in the provided therapy context; do not invent steps.
- If the retrieved context is weak, say so briefly rather than guessing.
- Do not minimise what the person is feeling.
- Do not tell someone they "should" feel a certain way.
- When someone describes chronic or worsening difficulties, gently surface the option of speaking with a professional.
- Keep responses warm, concise, and human."""

SYSTEM_PROMPT_INFORMATIONAL = """You are a mental health information assistant. You provide clear, accurate answers grounded in the context passages provided.

Guidelines:
- Answer the question directly and concisely using the provided context.
- Do not draw on general knowledge; only use information present in the context.
- If the context does not cover the question, say so clearly rather than guessing.
- Do not add unsolicited emotional support or ask follow-up questions.
- Use plain language; avoid jargon unless it was in the question."""

_INFORMATIONAL_STARTERS = {
    "what",
    "why",
    "when",
    "who",
    "which",
    "where",
    "explain",
    "describe",
    "define",
    "list",
    "tell",
    "what's",
}

_CLINICAL_FACTUAL_PATTERNS = (
    "what is",
    "what are",
    "what causes",
    "what can cause",
    "symptoms of",
    "signs of",
    "difference between",
    "how does",
    "how do you diagnose",
    "diagnostic criteria",
    "explain",
    "define",
)

_THERAPY_ACTION_PATTERNS = (
    "what can i do",
    "what should i do",
    "how do i calm",
    "how can i calm",
    "calm down",
    "help me",
    "coping",
    "cope with",
    "grounding",
    "breathing",
    "breath",
    "exercise",
    "technique",
    "strategy",
    "skill",
    "self-help",
    "self help",
    "mindfulness",
    "meditation",
    "cbt exercise",
    "dbt",
    "distress tolerance",
    "thought challenging",
    "cognitive restructuring",
    "defusion",
    "overthinking",
    "rumination",
    "racing thoughts",
    "spiral",
    "panic right now",
    "intrusive thoughts",
)

_PERSONAL_DISTRESS_PATTERNS = (
    "i feel",
    "i am feeling",
    "i'm feeling",
    "i keep",
    "i can't stop",
    "i cannot stop",
    "i am overwhelmed",
    "i'm overwhelmed",
    "my anxiety",
    "my thoughts",
)

LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "http://localhost:1234/v1")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "lm-studio")
LLM_MODEL = os.environ.get("LLM_MODEL", "")


# ---------------------------------------------------------------------------
# Response type
# ---------------------------------------------------------------------------


@dataclass
class PipelineResponse:
    text: str
    is_crisis: bool


# ---------------------------------------------------------------------------
# Lazy singletons
# ---------------------------------------------------------------------------

_classifier: SafetyClassifier | None = None
_rag: MentalHealthRAG | None = None
_llm_client: OpenAI | None = None
_session_store: SessionStore | None = None
_user_store: UserStore | None = None


def _get_classifier() -> SafetyClassifier:
    global _classifier
    if _classifier is None:
        _classifier = SafetyClassifier(CLASSIFIER_PATH)
    return _classifier


def _get_rag() -> MentalHealthRAG:
    global _rag
    if _rag is None:
        _rag = MentalHealthRAG()
    return _rag


def _get_session_store() -> SessionStore:
    global _session_store
    if _session_store is None:
        _session_store = SessionStore()
    return _session_store


def _get_user_store() -> UserStore:
    global _user_store
    if _user_store is None:
        _user_store = UserStore()
    return _user_store


def _get_llm_client() -> OpenAI:
    global _llm_client, LLM_MODEL
    if _llm_client is None:
        _llm_client = OpenAI(base_url=LLM_BASE_URL, api_key=LLM_API_KEY)
        if not LLM_MODEL:
            LLM_MODEL = _llm_client.models.list().data[0].id
            print(f"LM Studio model: {LLM_MODEL}")
    return _llm_client


# ---------------------------------------------------------------------------
# Routing and prompt context
# ---------------------------------------------------------------------------


def _contains_any(text: str, patterns: tuple[str, ...]) -> bool:
    return any(pattern in text for pattern in patterns)


def _route_retrieval_mode(message: str) -> str:
    """
    Route only after crisis interception has already run.

    Personal coping, coaching, and intervention requests use therapy MGPRAG.
    Factual mental-health questions use clinical Self-RAG.
    """
    text = " ".join(message.strip().lower().split())
    if not text:
        return "clinical"

    if _contains_any(text, _THERAPY_ACTION_PATTERNS):
        return "therapy"

    if _contains_any(text, _PERSONAL_DISTRESS_PATTERNS):
        return "therapy"

    if _contains_any(text, _CLINICAL_FACTUAL_PATTERNS):
        return "clinical"

    first = text.split()[0]
    if first in _INFORMATIONAL_STARTERS:
        return "clinical"

    padded = f" {text} "
    return "therapy" if any(token in padded for token in (" i ", " me ", " my ")) else "clinical"


def _is_informational(message: str) -> bool:
    """Compatibility helper used by the Streamlit comparison view."""
    return _route_retrieval_mode(message) == "clinical"


def _build_profile_block(user: User) -> str:
    goals_str = ", ".join(user.goals) if user.goals else "not specified"
    lines = [
        "User profile (use this to personalise your responses; do not recite these facts back verbatim):",
        f"- Age: {user.age}",
        f"- Mood baseline: {user.mood_baseline}/10 (their typical day-to-day level)",
        f"- Goals: {goals_str}",
    ]
    if user.country:
        lines.append(f"- Country: {user.country}")
    if user.job:
        lines.append(f"- Job: {user.job}")
    if user.relationship_status:
        lines.append(f"- Relationship status: {user.relationship_status}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# LLM call
# ---------------------------------------------------------------------------


def _llm_call(prompt: str, system_prompt: str = SYSTEM_PROMPT_COMPANION) -> str:
    response = _get_llm_client().chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        temperature=0.45,
    )
    return response.choices[0].message.content or ""


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def create_session(user_id: str) -> str:
    """Create a new session linked to user_id and return its ID."""
    return _get_session_store().create_session(user_id=user_id)


_CLASSIFY_EVERY_N_TURNS: int = 4
_HISTORY_TURN_LIMIT: int = 6


def run(message: str, session_id: str) -> PipelineResponse:
    store = _get_session_store()

    if not store.session_exists(session_id):
        raise ValueError(f"Unknown session: {session_id!r}. Call create_session() first.")

    if _get_classifier().is_crisis(message):
        store.append_turn(session_id, message, CRISIS_RESOURCES)
        return PipelineResponse(text=CRISIS_RESOURCES, is_crisis=True)

    turn_count = store.count_turns(session_id)
    if turn_count > 0 and turn_count % _CLASSIFY_EVERY_N_TURNS == 0:
        recent = store.load_history(session_id, limit=_HISTORY_TURN_LIMIT)
        conversation_text = "\n".join(
            f"user: {u}\nassistant: {a}" for u, a in recent
        )
        if _get_classifier().is_crisis(conversation_text):
            store.append_turn(session_id, message, CRISIS_RESOURCES)
            return PipelineResponse(text=CRISIS_RESOURCES, is_crisis=True)

    retrieval_mode = _route_retrieval_mode(message)
    is_info = retrieval_mode == "clinical"
    base_prompt = (
        SYSTEM_PROMPT_INFORMATIONAL
        if retrieval_mode == "clinical"
        else SYSTEM_PROMPT_COMPANION
    )

    user_id = store.get_user_id(session_id)
    user = _get_user_store().get_by_id(user_id) if user_id else None
    system_prompt = (
        base_prompt + "\n\n" + _build_profile_block(user) if user else base_prompt
    )

    rag = _get_rag()
    rag.chat_history = store.load_history(session_id, limit=_HISTORY_TURN_LIMIT)

    answer = rag.generate_response(
        user_query=message,
        llm_func=lambda prompt: _llm_call(prompt, system_prompt),
        informational=is_info,
        retrieval_mode=retrieval_mode,
    )

    store.append_turn(session_id, message, answer)

    return PipelineResponse(text=answer, is_crisis=False)
