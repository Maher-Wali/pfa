from __future__ import annotations

import re


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
