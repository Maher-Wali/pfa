from __future__ import annotations

import re

_EMOJI_RE = re.compile(
    "[\U00010000-\U0010ffff"
    "\U0001f300-\U0001f9ff"
    "☀-⛿"
    "✀-➿"
    "︀-️"
    "‍"
    "]+",
    flags=re.UNICODE,
)

_CRITIQUE_BLEED_RE = re.compile(
    r"\n*\s*(Critique:|VERDICT:|MUST_FIX:).*",
    flags=re.DOTALL | re.IGNORECASE,
)


def strip_emojis(text: str) -> str:
    return _EMOJI_RE.sub("", text).strip()


def strip_critique_bleed(text: str) -> str:
    """Remove any critique/verdict text the reviser accidentally appended."""
    return _CRITIQUE_BLEED_RE.sub("", text).strip()


def _cap_must_fix(critique: str, max_items: int = 2) -> str:
    """Keep at most max_items bullet points under MUST_FIX."""
    if "MUST_FIX:" not in critique:
        return critique
    header, _, rest = critique.partition("MUST_FIX:")
    lines = rest.splitlines()
    kept, count = [], 0
    for line in lines:
        if line.strip().startswith("-"):
            if count >= max_items:
                continue
            count += 1
        kept.append(line)
    return header + "MUST_FIX:" + "\n".join(kept)


def strip_dashes(text: str) -> str:
    """Replace em/en dashes used as punctuation with commas, then clean up."""
    # Spaced variants first: " — " and " – " -> ", "
    text = re.sub(r"\s*[—–]\s*", ", ", text)
    # Clean up any resulting double commas, comma-period, or leading/trailing comma
    text = re.sub(r",\s*,", ",", text)
    text = re.sub(r",\s*\.", ".", text)
    text = re.sub(r"\(\s*,", "(", text)
    text = re.sub(r",\s*\)", ")", text)
    # Clean up lines that now start with ", "
    text = re.sub(r"^,\s*", "", text, flags=re.MULTILINE)
    return text.strip()


def _resolve_dual_verdict(critique: str) -> str:
    """If the critic wrote two VERDICT lines (self-correction), keep only the last one."""
    needs = "VERDICT: NEEDS_REVISION"
    approved = "VERDICT: APPROVED"
    has_needs = needs in critique
    has_approved = approved in critique
    if not (has_needs and has_approved):
        return critique
    last_needs = critique.rfind(needs)
    last_approved = critique.rfind(approved)
    if last_approved > last_needs:
        return critique[last_approved:]
    else:
        return critique[:last_approved].rstrip() + "\n" + critique[last_needs:]


def _is_looping_bullet(text: str) -> bool:
    """Detect critic reasoning loops: any 6-word span repeating 3+ times signals a loop."""
    words = text.split()
    if len(words) < 30:
        return False
    for i in range(len(words) - 5):
        ngram = " ".join(words[i:i + 6])
        if text.count(ngram) >= 3:
            return True
    return False


def _quote_matches_draft(quote: str, draft: str) -> bool:
    """Check if a quoted phrase (possibly with ellipsis) appears in the draft."""
    if "..." not in quote:
        return quote in draft
    fragments = [f.strip() for f in quote.split("...") if len(f.strip()) >= 4]
    return bool(fragments) and all(f in draft for f in fragments)


# ---------------------------------------------------------------------------
# Retrieval routing
# ---------------------------------------------------------------------------

_INFORMATIONAL_STARTERS = {
    "what", "why", "when", "who", "which", "where",
    "explain", "describe", "define", "list", "tell", "what's",
}

_CLINICAL_FACTUAL_PATTERNS = (
    "what is", "what are", "what causes", "what can cause",
    "symptoms of", "signs of", "difference between",
    "how does", "how do you diagnose", "diagnostic criteria",
    "explain", "define",
)

_THERAPY_ACTION_PATTERNS = (
    "what can i do", "what should i do", "how do i calm", "how can i calm",
    "calm down", "help me", "coping", "cope with", "grounding", "breathing",
    "breath", "exercise", "technique", "strategy", "skill", "self-help",
    "self help", "mindfulness", "meditation", "cbt exercise", "dbt",
    "distress tolerance", "thought challenging", "cognitive restructuring",
    "defusion", "overthinking", "rumination", "racing thoughts", "spiral",
    "panic right now",
)

_PERSONAL_DISTRESS_PATTERNS = (
    "i feel", "i am feeling", "i'm feeling", "i keep",
    "i can't stop", "i cannot stop", "i am overwhelmed", "i'm overwhelmed",
    "my anxiety", "my thoughts",
)


def _contains_any(text: str, patterns: tuple) -> bool:
    return any(pattern in text for pattern in patterns)


def _route_retrieval_mode(message: str) -> str:
    """Route to 'therapy' or 'clinical' retrieval based on message content."""
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
            if stripped:
                continue
            kept.append(line)
            continue
        if _is_looping_bullet(stripped):
            continue
        lower = stripped.lower()
        if any(phrase in lower for phrase in ("no violation", "not a violation", "so no violation")):
            continue
        quotes = re.findall(r'["""]([^"""]{4,})["""]', stripped)
        if not quotes:
            kept.append(line)
            continue
        if any(_quote_matches_draft(q, draft) for q in quotes):
            kept.append(line)
    surviving = [l for l in kept if l.strip().startswith("-")]
    if not surviving:
        return header.rstrip() + "\nVERDICT: APPROVED"
    return header + "MUST_FIX:" + "\n".join(kept)
