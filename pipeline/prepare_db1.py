"""
Stage 1 — DB1 Clinical Knowledge Preparation
=============================================
Reads all raw DB1 JSON files, cleans, chunks, and writes
data/processed/db1_chunks.json ready for build_vectors.py.

Output schema (one dict per chunk):
  {
    "text":     str,   # context-prefixed chunk text fed to the embedder
    "metadata": {
      "condition":   str,
      "section":     str,
      "source":      str,
      "source_url":  str,
      "icd11_code":  str | None,
      "chunk_index": int,   # 0-based position within the parent record
    }
  }
"""
import json
import sys
from pathlib import Path

# Allow running from any working directory
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.utils import clean_text, sentence_chunk, db1_prefix

RAW_DIR    = ROOT / "data" / "raw" / "db1_clinical"
OUT_FILE   = ROOT / "data" / "processed" / "db1_chunks.json"

# Records shorter than this (words) after cleaning are skipped entirely
MIN_WORDS  = 40

# Condition name aliases: when a source uses a broad/different name, expand the
# BM25-visible prefix so queries using any alias can match via keyword overlap.
CONDITION_ALIASES: dict[str, list[str]] = {
    "Anxiety Disorders":   ["Generalised Anxiety Disorder", "GAD", "social anxiety", "panic disorder"],
    "Anxiety":             ["Generalised Anxiety Disorder", "GAD", "anxiety disorder"],
    "Anxiety, Panic and Phobias": ["Generalised Anxiety Disorder", "GAD", "panic disorder", "phobia"],
}


def load_raw_records() -> list[dict]:
    """Load every non-empty DB1 JSON file."""
    records = []
    for json_file in sorted(RAW_DIR.rglob("*.json")):
        data = json.loads(json_file.read_text(encoding="utf-8"))
        if not data:
            print(f"  [skip] {json_file.name} — empty")
            continue
        records.extend(data)
        print(f"  {json_file.name}: {len(data)} records")
    return records


def process_record(rec: dict) -> list[dict]:
    """Clean, chunk, and prefix one raw DB1 record into a list of chunk dicts."""
    content   = clean_text(rec.get("content", ""))
    condition = rec.get("condition", "Unknown")
    section   = rec.get("section", "other")
    source    = rec.get("source", "Unknown")
    url       = rec.get("source_url", "")
    icd11     = rec.get("icd11_code")

    if len(content.split()) < MIN_WORDS:
        return []

    # Expand condition name with aliases so BM25 can match variant query terms
    aliases = CONDITION_ALIASES.get(condition, [])
    display_condition = condition if not aliases else f"{condition} ({', '.join(aliases)})"

    chunks = sentence_chunk(content, target_words=200, overlap_words=30)
    result = []
    for i, chunk in enumerate(chunks):
        prefixed = db1_prefix(display_condition, section, source, chunk)
        result.append({
            "text": prefixed,
            "metadata": {
                "condition":   condition,
                "section":     section,
                "source":      source,
                "source_url":  url,
                "icd11_code":  icd11,
                "chunk_index": i,
            },
        })
    return result


def main():
    print("=" * 60)
    print("DB1 Preparation")
    print("=" * 60)

    print("\nLoading raw records...")
    records = load_raw_records()
    print(f"\nTotal raw records: {len(records)}")

    print("\nChunking...")
    all_chunks: list[dict] = []
    skipped = 0

    for rec in records:
        chunks = process_record(rec)
        if not chunks:
            skipped += 1
        all_chunks.extend(chunks)

    print(f"  Records skipped (< {MIN_WORDS} words): {skipped}")
    print(f"  Total chunks produced:                 {len(all_chunks)}")

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(
        json.dumps(all_chunks, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\nSaved to: {OUT_FILE}")

    # Quick section breakdown
    section_counts: dict[str, int] = {}
    for c in all_chunks:
        sec = c["metadata"]["section"]
        section_counts[sec] = section_counts.get(sec, 0) + 1
    print("\nChunk distribution by section:")
    for sec, count in sorted(section_counts.items(), key=lambda x: -x[1]):
        print(f"  {sec:<25} {count:>5}")


if __name__ == "__main__":
    main()
