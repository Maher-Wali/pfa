from __future__ import annotations

import json
import re

from agents.llm import invoke_text

_SYSTEM = (
    "You are a silent profile-extraction assistant. "
    "Given a therapy conversation, extract any personal facts the user has revealed. "
    "Return ONLY a JSON object — no prose, no markdown. "
    "Use null for fields you cannot determine with high confidence. "
    "Fields: age (int), goals (list of strings), job (string), relationship_status (string)."
)

_PROMPT_TMPL = """Conversation:
{history}

Return JSON only."""


def extract_profile(llm, messages: list[dict]) -> dict:
    history = "\n".join(
        f"{m['role']}: {m['content']}" for m in messages
    )
    raw = invoke_text(llm, _SYSTEM, _PROMPT_TMPL.format(history=history))

    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return {}

    try:
        data = json.loads(match.group())
    except json.JSONDecodeError:
        return {}

    result = {}
    if isinstance(data.get("age"), int) and data["age"] > 0:
        result["age"] = data["age"]
    if isinstance(data.get("goals"), list) and data["goals"]:
        result["goals"] = [g for g in data["goals"] if isinstance(g, str)]
    for field in ("job", "relationship_status"):
        if isinstance(data.get(field), str) and data[field].strip():
            result[field] = data[field].strip()

    return result
