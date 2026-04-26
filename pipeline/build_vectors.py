"""
Stage 2 — Embedding & Indexing
================================
Reads data/processed/db1_chunks.json and db2_chunks.json,
embeds each chunk with BAAI/bge-base-en-v1.5, and upserts
into two separate Pinecone serverless indexes:

  mental-health-clinical
  mental-health-therapy

Key decisions (see vectordbs.drawio):
  - Batch size 100: Pinecone recommends ≤100 vectors per upsert call
  - L2-normalised embeddings: cosine metric in Pinecone
  - Separate indexes: query router selects one before ANN search

Usage:
  python pipeline/build_vectors.py              # build both
  python pipeline/build_vectors.py --db db1     # only clinical
  python pipeline/build_vectors.py --db db2     # only therapy
  python pipeline/build_vectors.py --reset      # delete & rebuild
"""
import json
import os
import argparse
import sys
import time
from pathlib import Path
from typing import Any
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

PROCESSED_DIR = ROOT / "data" / "processed"

DB_CONFIG = {
    "db1": {
        "chunks_file":    PROCESSED_DIR / "db1_chunks.json",
        "index_name":     "mental-health-clinical",
        "metadata_keys":  ["condition", "section", "source", "source_url",
                           "icd11_code", "chunk_index"],
    },
    "db2": {
        "chunks_file":    PROCESSED_DIR / "db2_chunks.json",
        "index_name":     "mental-health-therapy",
        "metadata_keys":  ["technique_name", "modality", "source", "source_url",
                           "chunk_type", "chunk_index"],
    },
}

EMBED_MODEL  = "BAAI/bge-base-en-v1.5"
EMBED_DIM    = 768
BATCH_SIZE   = 100   # Pinecone recommended max per upsert


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_readable(text: str) -> bool:
    """
    Return True if *text* looks like natural English prose.

    Rejects chunks that are Brotli/gzip binary garbage or PDF font-encoding
    failures — both produce very low letter density and short average word
    length.  Threshold values chosen from empirical analysis of known-good
    (NHS, ACT Mindfully) vs known-bad (Beyond Blue, Self-Compassion.org pre-fix)
    chunks.
    """
    if not text or len(text) < 30:
        return False
    letter_ratio = sum(c.isalpha() for c in text) / len(text)
    words = text.split()
    avg_word_len = sum(len(w) for w in words) / max(len(words), 1)
    return letter_ratio >= 0.50 and avg_word_len >= 2.5


def _clean_metadata(meta: dict, allowed_keys: list[str]) -> dict:
    """
    Pinecone metadata values must be str | int | float | bool | list[str].
    - Keep only allowed_keys to avoid schema drift between runs.
    - Coerce lists to comma-separated string.
    - Replace None with empty string.
    """
    out = {}
    for key in allowed_keys:
        val = meta.get(key)
        if val is None:
            out[key] = ""
        elif isinstance(val, list):
            out[key] = ", ".join(str(v) for v in val)
        else:
            out[key] = val
    return out


def _batches(items: list, size: int):
    """Yield successive slices of *items* of length *size*."""
    for i in range(0, len(items), size):
        yield items[i : i + size]


def _wait_for_index(pc, index_name: str, timeout: int = 120):
    """Poll until the index is ready."""
    start = time.time()
    while time.time() - start < timeout:
        desc = pc.describe_index(index_name)
        if desc.status.get("ready", False):
            return
        print(f"  Waiting for index '{index_name}' to be ready...")
        time.sleep(5)
    raise TimeoutError(f"Index '{index_name}' not ready after {timeout}s")


# ---------------------------------------------------------------------------
# Indexer
# ---------------------------------------------------------------------------

def build_index(db_key: str, reset: bool = False):
    from pinecone import Pinecone, ServerlessSpec
    from sentence_transformers import SentenceTransformer

    cfg = DB_CONFIG[db_key]
    chunks_file = cfg["chunks_file"]
    index_name  = cfg["index_name"]
    meta_keys   = cfg["metadata_keys"]

    pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])

    print(f"\n{'='*60}")
    print(f"Building: {index_name}")
    print(f"{'='*60}")

    # -- Load chunks --
    if not chunks_file.exists():
        print(f"  [error] {chunks_file} not found.")
        print(f"  Run prepare_db{db_key[-1]}.py first.")
        return

    chunks: list[dict] = json.loads(chunks_file.read_text(encoding="utf-8"))
    print(f"  Loaded {len(chunks)} chunks from {chunks_file.name}")

    if not chunks:
        print("  Nothing to index.")
        return

    # Drop unreadable chunks (Brotli garbage, PDF font failures, etc.)
    before = len(chunks)
    chunks = [c for c in chunks if _is_readable(c["text"])]
    dropped = before - len(chunks)
    if dropped:
        print(f"  Dropped {dropped}/{before} unreadable chunks ({100*dropped//before}%)")

    if not chunks:
        print("  No readable chunks remain after quality filter.")
        return

    texts     = [c["text"] for c in chunks]
    metadatas = [_clean_metadata(c["metadata"], meta_keys) for c in chunks]
    ids       = [f"{db_key}-{i}" for i in range(len(chunks))]

    # -- Embed --
    print(f"\n  Loading embedding model: {EMBED_MODEL}")
    model = SentenceTransformer(EMBED_MODEL)

    print(f"  Embedding {len(texts)} chunks...")
    embeddings = model.encode(
        texts,
        batch_size=64,
        show_progress_bar=True,
        normalize_embeddings=True,
        convert_to_numpy=True,
    )
    print(f"  Embedding shape: {embeddings.shape}")

    # -- Create or reset Pinecone index --
    existing_indexes = [idx.name for idx in pc.list_indexes()]

    if reset and index_name in existing_indexes:
        pc.delete_index(index_name)
        print(f"  Deleted existing index: {index_name}")
        existing_indexes.remove(index_name)

    if index_name not in existing_indexes:
        print(f"  Creating index: {index_name} (dimension={EMBED_DIM}, metric=cosine)")
        pc.create_index(
            name=index_name,
            dimension=EMBED_DIM,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1"),
        )
        _wait_for_index(pc, index_name)
        print(f"  Index '{index_name}' is ready.")

    index = pc.Index(index_name)

    # Check existing vectors
    stats = index.describe_index_stats()
    existing_count = stats.total_vector_count
    if existing_count > 0 and not reset:
        print(f"  Index already has {existing_count} vectors. Use --reset to rebuild.")
        return

    # -- Batch upsert --
    print(f"\n  Upserting in batches of {BATCH_SIZE}...")
    total = 0
    for batch_ids, batch_embs, batch_metas, batch_texts in zip(
        _batches(ids, BATCH_SIZE),
        _batches(embeddings.tolist(), BATCH_SIZE),
        _batches(metadatas, BATCH_SIZE),
        _batches(texts, BATCH_SIZE),
    ):
        vectors = []
        for vid, emb, meta, text in zip(batch_ids, batch_embs, batch_metas, batch_texts):
            # Store the text in metadata so we can retrieve it later
            full_meta = {**meta, "text": text}
            vectors.append({"id": vid, "values": emb, "metadata": full_meta})

        index.upsert(vectors=vectors)
        total += len(vectors)
        print(f"    {total}/{len(chunks)} upserted")

    # Brief wait for indexing to propagate
    time.sleep(2)
    stats = index.describe_index_stats()
    print(f"\n  Done. Index '{index_name}' now has {stats.total_vector_count} vectors.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Build Pinecone vector indexes")
    parser.add_argument(
        "--db",
        choices=["db1", "db2", "both"],
        default="both",
        help="Which index to build (default: both)",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete and rebuild existing indexes",
    )
    args = parser.parse_args()

    if not os.environ.get("PINECONE_API_KEY"):
        print("ERROR: PINECONE_API_KEY environment variable not set.")
        print("  export PINECONE_API_KEY='your-key'")
        sys.exit(1)

    targets = ["db1", "db2"] if args.db == "both" else [args.db]

    for db_key in targets:
        build_index(db_key, reset=args.reset)

    print("\nAll done.")
    print("  Clinical index -> mental-health-clinical")
    print("  Therapy index  -> mental-health-therapy")


if __name__ == "__main__":
    main()
