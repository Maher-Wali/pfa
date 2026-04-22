import os
from dataclasses import dataclass

from dotenv import load_dotenv
load_dotenv()

from openai import OpenAI

from safety_classifier.classifier import SafetyClassifier
from retrieval.rag_pipeline import MentalHealthRAG

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

You don't have to face this alone — a trained counsellor is available right now."""

SYSTEM_PROMPT_COMPANION = """You are a supportive mental health companion. You are NOT a therapist, psychiatrist, or doctor.

Guidelines:
- Always acknowledge and validate the person's emotions before offering any information.
- Ask one open question per turn — never pepper the person with multiple questions.
- Do not diagnose, label symptoms, or speculate about what condition someone may have.
- Do not offer unsolicited advice or minimise what the person is feeling.
- Do not tell someone they "should" feel a certain way.
- When someone describes chronic or worsening difficulties, gently surface the option of speaking with a professional — this is not reserved only for acute crisis.
- Ground your responses in the provided context where relevant, but never recite it verbatim.
- Keep responses warm, concise, and human."""

SYSTEM_PROMPT_INFORMATIONAL = """You are a mental health information assistant. You provide clear, accurate answers grounded in the context passages provided.

Guidelines:
- Answer the question directly and concisely using the provided context.
- Do not draw on general knowledge — only use information present in the context.
- If the context does not cover the question, say so clearly rather than guessing.
- Do not add unsolicited emotional support or ask follow-up questions.
- Use plain language; avoid jargon unless it was in the question."""

_INFORMATIONAL_STARTERS = {
    "what", "how", "why", "when", "who", "which", "where",
    "explain", "describe", "define", "list", "give", "tell",
    "what's", "what are", "what is", "how do", "how does",
    "can you explain", "could you explain",
}


def _is_informational(message: str) -> bool:
    first = message.strip().lower().split()[0] if message.strip() else ""
    return first in _INFORMATIONAL_STARTERS


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


def _get_llm_client() -> OpenAI:
    global _llm_client, LLM_MODEL
    if _llm_client is None:
        _llm_client = OpenAI(base_url=LLM_BASE_URL, api_key=LLM_API_KEY)
        if not LLM_MODEL:
            LLM_MODEL = _llm_client.models.list().data[0].id
            print(f"LM Studio model: {LLM_MODEL}")
    return _llm_client


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
        temperature=0.7,
    )
    return response.choices[0].message.content or ""


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def run(message: str) -> PipelineResponse:
    if _get_classifier().is_crisis(message):
        return PipelineResponse(text=CRISIS_RESOURCES, is_crisis=True)

    system_prompt = (
        SYSTEM_PROMPT_INFORMATIONAL if _is_informational(message)
        else SYSTEM_PROMPT_COMPANION
    )

    answer = _get_rag().generate_response(
        user_query=message,
        llm_func=lambda prompt: _llm_call(prompt, system_prompt),
    )

    return PipelineResponse(text=answer, is_crisis=False)
