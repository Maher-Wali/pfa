# retrieval/query_router.py
#
# Lightweight keyword-based router that decides which vector DB(s) a query
# should be sent to.
#
# Design rationale
# ----------------
# Two collections serve different information needs:
#
#   clinical  — disorders, symptoms, diagnosis, medications, ICD codes,
#               epidemiology, risk factors, prognosis.
#
#   therapy   — coping techniques, exercises, worksheets, CBT/DBT/ACT
#               skills, mindfulness, relaxation, grounding.
#
# A query is routed to "both" when it contains signals from neither or
# both categories, which is the safe default — it costs more but avoids
# silently missing relevant passages.
#
# No LLM is needed here; keyword overlap is cheap and accurate enough for
# this domain split.  The caller can always override via the `force`
# parameter.

from __future__ import annotations
import re
from typing import Literal

RouteTarget = Literal["clinical", "therapy", "both"]

# ---------------------------------------------------------------------------
# Keyword sets
# ---------------------------------------------------------------------------

_CLINICAL_KEYWORDS = {
    # Conditions / nosology
    "disorder", "condition", "disease", "syndrome", "illness", "diagnosis",
    "diagnose", "diagnostic", "icd", "dsm", "comorbid", "comorbidity",
    # Symptom / aetiology vocabulary
    "symptom", "symptoms", "sign", "signs", "cause", "causes", "aetiology",
    "etiology", "pathology", "pathophysiology", "onset", "episode",
    # Clinical management
    "treatment", "medication", "drug", "antidepressant", "antipsychotic",
    "ssri", "snri", "prescribe", "prescription", "dose", "dosage",
    "hospitali", "inpatient", "outpatient", "referral",
    # Epidemiology / prognosis
    "prevalence", "incidence", "prognosis", "mortality", "risk factor",
    "risk factors", "epidemiology",
    # Named disorders (common search terms)
    "depression", "anxiety", "ptsd", "ocd", "bipolar", "schizophrenia",
    "adhd", "autism", "eating disorder", "anorexia", "bulimia", "phobia",
    "panic disorder", "social anxiety", "generalized anxiety", "gad",
    "major depressive", "dysthymia", "cyclothymia", "bpd",
    "borderline personality", "narcissistic", "psychosis", "mania",
    "hypomania", "dissociation", "dissociative",
}

_THERAPY_KEYWORDS = {
    # Technique / skill vocabulary
    "technique", "techniques", "exercise", "exercises", "skill", "skills",
    "strategy", "strategies", "tool", "tools", "worksheet", "worksheets",
    "practice", "practices", "activity", "activities", "intervention",
    # Therapy modalities
    "cbt", "cognitive behavioral", "cognitive behavioural", "dbt",
    "dialectical behavior", "dialectical behaviour", "act ",
    "acceptance and commitment", "mbct", "mindfulness-based",
    "psychotherapy", "therapy", "counselling", "counseling",
    "exposure therapy", "behavioral activation", "behavioural activation",
    "schema therapy", "emdr",
    # Coping / self-help vocabulary
    "coping", "cope", "manage", "managing", "self-help", "self help",
    "grounding", "relaxation", "breathing", "breath", "meditation",
    "mindfulness", "acceptance", "defusion", "values", "committed action",
    "thought record", "thought challenging", "cognitive restructuring",
    "behavioural experiment", "behavioral experiment", "journaling",
    "journalling", "gratitude", "self-compassion", "self compassion",
    "distress tolerance", "emotion regulation", "interpersonal effectiveness",
    "radical acceptance",
    # Outcome / process words common in therapy content
    "homework", "session", "therapist", "client", "psychoeducation",
    "psycho-education", "psychoeducational",
}

# Pre-compile a single tokenisation regex for speed
_WORD_RE = re.compile(r"[a-z0-9]+(?:[- ][a-z0-9]+)*")


def _tokens(text: str) -> set[str]:
    """Lower-case the text and extract word/phrase tokens."""
    lowered = text.lower()
    # Single words
    words = set(re.findall(r"[a-z0-9]+", lowered))
    # Two-word phrases (catches "risk factor", "self help", etc.)
    word_list = lowered.split()
    bigrams = {f"{word_list[i]} {word_list[i+1]}" for i in range(len(word_list) - 1)}
    return words | bigrams


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def route_query(query: str, force: RouteTarget | None = None) -> RouteTarget:
    """
    Return the target collection(s) for *query*.

    Parameters
    ----------
    query:
        The raw user query string.
    force:
        If provided, skip keyword analysis and return this value directly.
        Useful for callers that already know the domain.

    Returns
    -------
    "clinical"  — route only to the clinical disorders DB
    "therapy"   — route only to the therapy techniques DB
    "both"      — query both DBs and merge results with RRF
    """
    if force is not None:
        return force

    tokens = _tokens(query)

    has_clinical = bool(tokens & _CLINICAL_KEYWORDS)
    has_therapy = bool(tokens & _THERAPY_KEYWORDS)

    if has_clinical and not has_therapy:
        return "clinical"
    if has_therapy and not has_clinical:
        return "therapy"

    # Ambiguous or no signal → safe default
    return "both"
