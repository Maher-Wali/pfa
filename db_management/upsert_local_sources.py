"""
upsert_local_sources.py
-----------------------
Upserts local db1 chunks into the Pinecone clinical index for sources
that are not already represented there. Does not touch existing vectors.

Sources already in Pinecone (skipped):
  Mind UK, NHS, Mayo Clinic, WHO, NIMH, NICE

Sources to add from local db1_chunks.json:
  Better Health Channel, CAMH, MedlinePlus,
  Mental Health Foundation, Royal College of Psychiatrists

Usage:
  python upsert_local_sources.py
  python upsert_local_sources.py --dry-run   # show what would be upserted, no writes
"""

from __future__ import annotations

import os
import sys
import json
import re
import argparse
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent
CHUNKS_FILE = ROOT / "data" / "processed" / "db1_chunks.json"
INDEX_NAME = "mental-health-clinical"
EMBED_MODEL = "BAAI/bge-base-en-v1.5"
BATCH_SIZE = 100

# Sources already in Pinecone — skip these
ALREADY_IN_PINECONE = {
    "Mind UK",
    "NHS",
    "Mayo Clinic",
    "WHO",
    "NIMH",
    "NICE",
}


def _slug(source: str) -> str:
    """Turn a source name into a safe ID prefix, e.g. 'Better Health Channel' -> 'better-health-channel'."""
    return re.sub(r"[^a-z0-9]+", "-", source.lower()).strip("-")


def main() -> None:
    parser = argparse.ArgumentParser(description="Upsert missing local sources into Pinecone")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would be upserted without writing anything")
    args = parser.parse_args()

    api_key = os.environ.get("PINECONE_API_KEY")
    if not api_key:
        print("ERROR: PINECONE_API_KEY not set.")
        sys.exit(1)

    # -- Load local chunks --
    print(f"Loading {CHUNKS_FILE}...")
    chunks = json.loads(CHUNKS_FILE.read_text(encoding="utf-8"))
    print(f"  {len(chunks)} total chunks in local file")

    # -- Filter to missing sources only --
    to_add = [c for c in chunks if c["metadata"].get("source") not in ALREADY_IN_PINECONE]

    if not to_add:
        print("Nothing to add — all local sources are already in Pinecone.")
        return

    # Show breakdown
    from collections import Counter
    by_source = Counter(c["metadata"]["source"] for c in to_add)
    print(f"\n  Chunks to upsert ({len(to_add)} total):")
    for src, count in sorted(by_source.items(), key=lambda x: -x[1]):
        print(f"    {count:>5}  —  {src}")

    if args.dry_run:
        print("\n[dry-run] No data written.")
        return

    # -- Embed --
    from sentence_transformers import SentenceTransformer
    print(f"\nLoading embedding model: {EMBED_MODEL} (CPU)")
    model = SentenceTransformer(EMBED_MODEL, device="cpu")

    texts = [c["text"] for c in to_add]
    print(f"Embedding {len(texts)} chunks...")
    embeddings = model.encode(
        texts,
        batch_size=32,
        show_progress_bar=True,
        normalize_embeddings=True,
        convert_to_numpy=True,
    )

    # -- Upsert --
    from pinecone import Pinecone
    pc = Pinecone(api_key=api_key)
    index = pc.Index(INDEX_NAME)

    # Build IDs: <source-slug>-<position> to avoid colliding with existing db1-N ids
    source_counters: dict[str, int] = {}
    ids = []
    for c in to_add:
        src = c["metadata"]["source"]
        slug = _slug(src)
        n = source_counters.get(slug, 0)
        ids.append(f"local-{slug}-{n}")
        source_counters[slug] = n + 1

    # Metadata: keep allowed keys + text
    meta_keys = ["condition", "section", "source", "source_url", "icd11_code", "chunk_index"]

    def clean_meta(meta: dict, text: str) -> dict:
        out = {}
        for k in meta_keys:
            val = meta.get(k)
            if val is None:
                out[k] = ""
            elif isinstance(val, list):
                out[k] = ", ".join(str(v) for v in val)
            else:
                out[k] = val
        out["text"] = text
        return out

    print(f"\nUpserting to '{INDEX_NAME}' in batches of {BATCH_SIZE}...")
    total = 0
    for i in range(0, len(to_add), BATCH_SIZE):
        batch_slice = slice(i, i + BATCH_SIZE)
        vectors = [
            {
                "id": vid,
                "values": emb.tolist(),
                "metadata": clean_meta(c["metadata"], text),
            }
            for vid, emb, c, text in zip(
                ids[batch_slice],
                embeddings[batch_slice],
                to_add[batch_slice],
                texts[batch_slice],
            )
        ]
        index.upsert(vectors=vectors)
        total += len(vectors)
        print(f"  {total}/{len(to_add)} upserted")

    print(f"\nDone. {total} chunks added to '{INDEX_NAME}'.")
    print("Run inspect_pinecone.py to verify.")


if __name__ == "__main__":
    main()
