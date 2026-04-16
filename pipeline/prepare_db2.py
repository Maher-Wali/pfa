"""
Stage 1 — DB2 Therapy Techniques Preparation
=============================================
Reads all raw DB2 JSON files, runs an LLM enrichment pass to populate
structured fields (steps, when_to_use, target_conditions, difficulty),
chunks the prose, and writes data/processed/db2_chunks.json.

Two types of chunks are emitted per technique:
  1. Prose chunks  — overlapping sentence-boundary chunks of raw_content
  2. Summary chunk — a single structured chunk built from the LLM-extracted
                     fields (steps, when_to_use, etc.), prefixed identically.
     This gives the retriever a compact, scannable entry point for each
     technique alongside the full prose.

LLM enrichment uses the Anthropic API (claude-haiku-4-5).
Set ANTHROPIC_API_KEY in the environment before running.
Pass --no-llm to skip enrichment and chunk raw prose only (useful for
testing the pipeline without API access).

Output schema (one dict per chunk):
  {
    "text":      str,
    "metadata": {
      "technique_name":    str,
      "modality":          str,
      "target_conditions": list[str],
      "source":            str,
      "source_url":        str,
      "chunk_type":        "prose" | "summary",
      "chunk_index":       int,
    }
  }
"""
import json
import sys
import argparse
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.utils import clean_text, sentence_chunk, db2_prefix

RAW_DIR  = ROOT / "data" / "raw" / "db2_therapy"
OUT_FILE = ROOT / "data" / "processed" / "db2_chunks.json"

MIN_WORDS = 40

# ---------------------------------------------------------------------------
# LLM enrichment
# ---------------------------------------------------------------------------

ENRICHMENT_PROMPT = """\
You are given a therapy technique article. Extract structured information \
and return ONLY valid JSON with these fields:

{
  "steps": [list of strings — ordered steps to perform the technique, or null if not applicable],
  "when_to_use": "one sentence describing when this technique is appropriate",
  "target_conditions": [list of mental health conditions this technique addresses],
  "difficulty": "low" | "medium" | "high",
  "estimated_time": "e.g. '10-15 minutes' or null if unclear"
}

Be concise. Use null for fields that cannot be determined from the text.

ARTICLE:
{content}
"""


def enrich_record(rec: dict, client) -> dict:
    """
    Call Claude Haiku to populate structured fields from raw_content.
    Returns a copy of the record with fields filled in.
    Gracefully falls back to original values on any API or parse error.
    """
    import anthropic

    content = rec.get("raw_content", "")
    if not content or len(content.split()) < 50:
        return rec

    prompt = ENRICHMENT_PROMPT.format(content=content[:4000])  # cap at 4k chars

    try:
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()

        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        extracted = json.loads(raw)
        enriched = dict(rec)
        enriched["steps"]             = extracted.get("steps")            or rec.get("steps")
        enriched["when_to_use"]       = extracted.get("when_to_use")      or rec.get("when_to_use")
        enriched["target_conditions"] = extracted.get("target_conditions") or rec.get("target_conditions") or []
        enriched["difficulty"]        = extracted.get("difficulty")        or rec.get("difficulty")
        enriched["estimated_time"]    = extracted.get("estimated_time")    or rec.get("estimated_time")
        return enriched

    except Exception as exc:
        print(f"    [warn] enrichment failed for '{rec.get('technique_name', '?')}': {exc}")
        return rec


def build_summary_chunk(rec: dict) -> str | None:
    """
    Build a structured summary string from LLM-extracted fields.
    Returns None if there is not enough structured data to make it useful.
    """
    parts = []

    technique = rec.get("technique_name", "")
    modality  = rec.get("modality", "")
    if technique:
        parts.append(f"Technique: {technique}")
    if modality:
        parts.append(f"Modality: {modality}")

    targets = rec.get("target_conditions") or []
    if targets:
        parts.append(f"Target conditions: {', '.join(targets)}")

    when = rec.get("when_to_use")
    if when:
        parts.append(f"When to use: {when}")

    difficulty = rec.get("difficulty")
    est_time   = rec.get("estimated_time")
    if difficulty:
        parts.append(f"Difficulty: {difficulty}")
    if est_time:
        parts.append(f"Estimated time: {est_time}")

    steps = rec.get("steps") or []
    if steps:
        steps_text = " | ".join(f"{i+1}. {s}" for i, s in enumerate(steps[:8]))
        parts.append(f"Steps: {steps_text}")

    if len(parts) < 3:
        return None

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Record processing
# ---------------------------------------------------------------------------

def process_record(rec: dict) -> list[dict]:
    """Chunk one DB2 record into prose chunks + optional summary chunk."""
    content   = clean_text(rec.get("raw_content", ""))
    technique = rec.get("technique_name", "Unknown")
    modality  = rec.get("modality", "general")
    source    = rec.get("source", "Unknown")
    url       = rec.get("source_url", "")
    targets   = rec.get("target_conditions") or []

    result: list[dict] = []

    # -- Structured summary chunk (from LLM enrichment) --
    summary = build_summary_chunk(rec)
    if summary:
        prefixed = db2_prefix(technique, modality, source, summary)
        result.append({
            "text": prefixed,
            "metadata": {
                "technique_name":    technique,
                "modality":          modality,
                "target_conditions": targets,
                "source":            source,
                "source_url":        url,
                "chunk_type":        "summary",
                "chunk_index":       0,
            },
        })

    # -- Prose chunks --
    if len(content.split()) < MIN_WORDS:
        return result

    prose_chunks = sentence_chunk(content, target_words=200, overlap_words=30)
    for i, chunk in enumerate(prose_chunks):
        prefixed = db2_prefix(technique, modality, source, chunk)
        result.append({
            "text": prefixed,
            "metadata": {
                "technique_name":    technique,
                "modality":          modality,
                "target_conditions": targets,
                "source":            source,
                "source_url":        url,
                "chunk_type":        "prose",
                "chunk_index":       i,
            },
        })

    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Prepare DB2 therapy chunks")
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Skip LLM enrichment pass (use for testing without API key)",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("DB2 Preparation")
    print("=" * 60)

    # Load raw records
    print("\nLoading raw records...")
    records: list[dict] = []
    for json_file in sorted(RAW_DIR.rglob("*.json")):
        data = json.loads(json_file.read_text(encoding="utf-8"))
        if not data:
            print(f"  [skip] {json_file.name} — empty")
            continue
        records.extend(data)
        print(f"  {json_file.name}: {len(data)} records")

    print(f"\nTotal raw records: {len(records)}")

    # LLM enrichment pass
    if not args.no_llm:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            print("\n[warn] ANTHROPIC_API_KEY not set — skipping enrichment.")
            print("       Run with --no-llm to suppress this warning.")
        else:
            try:
                import anthropic
                client = anthropic.Anthropic(api_key=api_key)
                print(f"\nRunning LLM enrichment on {len(records)} records...")
                for i, rec in enumerate(records):
                    records[i] = enrich_record(rec, client)
                    if (i + 1) % 10 == 0:
                        print(f"  {i+1}/{len(records)} enriched")
                print("  Enrichment complete.")
            except ImportError:
                print("\n[warn] anthropic package not installed — skipping enrichment.")
                print("       pip install anthropic")
    else:
        print("\nLLM enrichment skipped (--no-llm flag).")

    # Chunking
    print("\nChunking...")
    all_chunks: list[dict] = []
    skipped = 0
    summary_count = 0

    for rec in records:
        chunks = process_record(rec)
        if not chunks:
            skipped += 1
        for c in chunks:
            if c["metadata"]["chunk_type"] == "summary":
                summary_count += 1
        all_chunks.extend(chunks)

    prose_count = len(all_chunks) - summary_count
    print(f"  Records skipped (< {MIN_WORDS} words):    {skipped}")
    print(f"  Summary chunks (structured):              {summary_count}")
    print(f"  Prose chunks:                             {prose_count}")
    print(f"  Total chunks:                             {len(all_chunks)}")

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(
        json.dumps(all_chunks, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\nSaved to: {OUT_FILE}")

    # Modality breakdown
    mod_counts: dict[str, int] = {}
    for c in all_chunks:
        mod = c["metadata"]["modality"]
        mod_counts[mod] = mod_counts.get(mod, 0) + 1
    print("\nChunk distribution by modality:")
    for mod, count in sorted(mod_counts.items(), key=lambda x: -x[1]):
        print(f"  {mod:<30} {count:>5}")


if __name__ == "__main__":
    main()
