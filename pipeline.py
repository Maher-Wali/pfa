import os
from dataclasses import dataclass

from openai import OpenAI

from safety_classifier.classifier import SafetyClassifier
from retrieval.rag_pipeline import MentalHealthRAG

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CLASSIFIER_PATH = os.path.join(os.path.dirname(__file__), "output/part_4/part_4")

CRISIS_RESOURCES = """I'm concerned about what you've shared and I want to make sure you're safe.

Please reach out to a crisis support line right now:
- International Association for Suicide Prevention: https://www.iasp.info/resources/Crisis_Centres/
- Crisis Text Line (US): Text HOME to 741741
- Samaritans (UK): 116 123
- If you are in immediate danger, please call your local emergency services (911, 999, 112).

You don't have to face this alone — a trained counsellor is available right now."""

SYSTEM_PROMPT = """You are a supportive mental health companion. You are NOT a therapist, psychiatrist, or doctor.

Guidelines:
- Always acknowledge and validate the person's emotions before offering any information.
- Ask one open question per turn — never pepper the person with multiple questions.
- Do not diagnose, label symptoms, or speculate about what condition someone may have.
- Do not offer unsolicited advice or minimise what the person is feeling.
- Do not tell someone they "should" feel a certain way.
- When someone describes chronic or worsening difficulties, gently surface the option of speaking with a professional — this is not reserved only for acute crisis.
- Ground your responses in the provided context where relevant, but never recite it verbatim.
- Keep responses warm, concise, and human."""

# LLM config — override with environment variables.
# Defaults work with LM Studio running locally (Server tab → Start Server).
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "http://localhost:1234/v1")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "lm-studio")
LLM_MODEL = os.environ.get("LLM_MODEL", "")  # empty = auto-detect first loaded model

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


def _llm_call(prompt: str) -> str:
    response = _get_llm_client().chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
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

    answer = _get_rag().generate_response(
        user_query=message,
        llm_func=_llm_call,
        # Therapy DB is currently inactive — all queries go to clinical.
        force_target="clinical",
    )

    return PipelineResponse(text=answer, is_crisis=False)
