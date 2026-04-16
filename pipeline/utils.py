"""
Shared utilities for both prepare_db1.py and prepare_db2.py.

Key decisions (see vectordbs.drawio for full rationale):
  - Sentence-boundary chunking: preserves semantic completeness vs. word-count splits
  - Context prefix: embeds topic signal into the vector alongside the prose
  - clean_text: normalises encoding artefacts present in MHF and WHO records
"""
import re
from typing import Iterator


# ---------------------------------------------------------------------------
# Text cleaning
# ---------------------------------------------------------------------------

# Characters that appear as encoding artefacts in several scraped sources
# (UTF-8 decoded as latin-1, em-dash mangled, etc.)
_ARTEFACT_RE = re.compile(r"[^\x00-\x7F\u00A0-\u024F\u2000-\u206F\u2010-\u2027\u2030-\u205E\u2060-\u2FFF]")
_WHITESPACE_RE = re.compile(r"\s+")
_EDIT_TAG_RE = re.compile(r"\[edit\]", re.IGNORECASE)


def clean_text(text: str) -> str:
    """Normalise whitespace, strip encoding artefacts and [edit] markers."""
    if not text:
        return ""
    text = _EDIT_TAG_RE.sub("", text)
    text = _ARTEFACT_RE.sub(" ", text)
    text = _WHITESPACE_RE.sub(" ", text)
    return text.strip()


# ---------------------------------------------------------------------------
# Sentence tokeniser (no heavy NLP dependency)
# ---------------------------------------------------------------------------

# Sentence boundary: period/!/? followed by whitespace and an uppercase letter,
# or a closing quote/paren then space+uppercase. Handles most English prose.
_SENT_BOUNDARY = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"\(\[])")


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences using a lightweight regex heuristic."""
    parts = _SENT_BOUNDARY.split(text)
    return [p.strip() for p in parts if p.strip()]


# ---------------------------------------------------------------------------
# Chunker
# ---------------------------------------------------------------------------

def sentence_chunk(
    text: str,
    target_words: int = 200,
    overlap_words: int = 30,
) -> list[str]:
    """
    Split *text* into overlapping chunks that respect sentence boundaries.

    Strategy:
      1. Split text into sentences.
      2. Greedily accumulate sentences until adding the next would exceed
         target_words.
      3. Start the next chunk by replaying the last `overlap_words` worth of
         sentences from the current chunk (overlap by sentence, not by word).
      4. Never emit a chunk shorter than 30 words (merged into the previous).

    Returns a list of chunk strings.
    """
    sentences = _split_sentences(text)
    if not sentences:
        return []

    chunks: list[str] = []
    current: list[str] = []
    current_wc = 0

    for sent in sentences:
        wc = len(sent.split())
        if current_wc + wc > target_words and current:
            chunk_text = " ".join(current)
            if len(chunk_text.split()) >= 30:
                chunks.append(chunk_text)
            # Build overlap: walk back from end of current until we have
            # overlap_words words worth of sentences
            overlap: list[str] = []
            overlap_wc = 0
            for s in reversed(current):
                sw = len(s.split())
                if overlap_wc + sw > overlap_words:
                    break
                overlap.insert(0, s)
                overlap_wc += sw
            current = overlap + [sent]
            current_wc = overlap_wc + wc
        else:
            current.append(sent)
            current_wc += wc

    # Flush remainder
    if current:
        remainder = " ".join(current)
        if chunks and len(remainder.split()) < 30:
            # Too short — merge into previous chunk
            chunks[-1] = chunks[-1] + " " + remainder
        else:
            chunks.append(remainder)

    return chunks


# ---------------------------------------------------------------------------
# Context prefix builders
# ---------------------------------------------------------------------------

def db1_prefix(condition: str, section: str, source: str, chunk: str) -> str:
    """
    Prepend clinical topic context before the chunk text.

    Why: without this, 'symptoms include persistent sadness' embeds identically
    regardless of whether it comes from a Depression or Anxiety record. The
    prefix shifts the vector toward the correct clinical neighbourhood.
    """
    return f"Condition: {condition} | Section: {section} | Source: {source}\n{chunk}"


def db2_prefix(technique: str, modality: str, source: str, chunk: str) -> str:
    """
    Prepend therapy technique context before the chunk text.
    """
    return f"Technique: {technique} | Modality: {modality} | Source: {source}\n{chunk}"
