"""
Stage 2 — Embedding & Indexing
================================
Reads data/processed/db1_chunks.json and db2_chunks.json,
embeds each chunk with BAAI/bge-base-en-v1.5, and upserts
into two separate ChromaDB persistent collections:

  data/vectordb/clinical/  ->  collection: mental_health_clinical
  data/vectordb/therapy/   ->  collection: mental_health_therapy

Key decisions (see vectordbs.drawio):
  - Batch size 5 000: eliminates per-document overhead (~100× faster than medai)
  - L2-normalised embeddings: cosine similarity via dot product (ChromaDB default)
  - Separate collections: query router selects one before ANN search

Usage:
  python pipeline/build_vectors.py              # build both
  python pipeline/build_vectors.py --db db1     # only clinical
  python pipeline/build_vectors.py --db db2     # only therapy
  python pipeline/build_vectors.py --reset      # drop & rebuild
"""
import json
import argparse
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

PROCESSED_DIR = ROOT / "data" / "processed"
VECTORDB_DIR  = ROOT / "data" / "vectordb"

DB_CONFIG = {
    "db1": {
        "chunks_file":    PROCESSED_DIR / "db1_chunks.json",
        "chroma_dir":     VECTORDB_DIR / "clinical",
        "collection":     "mental_health_clinical",
        "metadata_keys":  ["condition", "section", "source", "source_url",
                           "icd11_code", "chunk_index"],
    },
    "db2": {
        "chunks_file":    PROCESSED_DIR / "db2_chunks.json",
        "chroma_dir":     VECTORDB_DIR / "therapy",
        "collection":     "mental_health_therapy",
        "metadata_keys":  ["technique_name", "modality", "source", "source_url",
                           "chunk_type", "chunk_index"],
    },
}

EMBED_MODEL  = "BAAI/bge-base-en-v1.5"
BATCH_SIZE   = 5_000


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
    ChromaDB metadata values must be str | int | float | bool.
    - Keep only allowed_keys to avoid schema drift between runs.
    - Coerce lists (e.g. target_conditions) to a comma-separated string.
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


# ---------------------------------------------------------------------------
# Indexer
# ---------------------------------------------------------------------------

def build_collection(db_key: str, reset: bool = False):
    import chromadb
    from sentence_transformers import SentenceTransformer

    cfg = DB_CONFIG[db_key]
    chunks_file  = cfg["chunks_file"]
    chroma_dir   = cfg["chroma_dir"]
    coll_name    = cfg["collection"]
    meta_keys    = cfg["metadata_keys"]

    print(f"\n{'='*60}")
    print(f"Building: {coll_name}")
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

    print(f"  Embedding {len(texts)} chunks (batch={BATCH_SIZE})...")
    embeddings = model.encode(
        texts,
        batch_size=64,          # encoding batch (GPU memory)
        show_progress_bar=True,
        normalize_embeddings=True,   # L2 norm -> cosine via dot product
        convert_to_numpy=True,
    )
    print(f"  Embedding shape: {embeddings.shape}")

    # -- ChromaDB --
    chroma_dir.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(chroma_dir))

    if reset:
        try:
            client.delete_collection(coll_name)
            print(f"  Dropped existing collection: {coll_name}")
        except Exception:
            pass

    collection = client.get_or_create_collection(
        name=coll_name,
        metadata={"hnsw:space": "cosine"},
    )

    existing = collection.count()
    if existing > 0 and not reset:
        print(f"  Collection already has {existing} items. Use --reset to rebuild.")
        return

    # -- Batch upsert --
    # Why 5 000: safe upper bound for ChromaDB; eliminates per-call overhead
    # that made medai's per-document loop ~100× slower.
    print(f"\n  Upserting in batches of {BATCH_SIZE}...")
    total = 0
    for batch_ids, batch_embs, batch_docs, batch_metas in zip(
        _batches(ids, BATCH_SIZE),
        _batches(embeddings.tolist(), BATCH_SIZE),
        _batches(texts, BATCH_SIZE),
        _batches(metadatas, BATCH_SIZE),
    ):
        collection.upsert(
            ids=batch_ids,
            embeddings=batch_embs,
            documents=batch_docs,
            metadatas=batch_metas,
        )
        total += len(batch_ids)
        print(f"    {total}/{len(chunks)} upserted")

    final_count = collection.count()
    print(f"\n  Done. Collection '{coll_name}' now has {final_count} items.")
    print(f"  Persisted to: {chroma_dir}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Build ChromaDB vector collections")
    parser.add_argument(
        "--db",
        choices=["db1", "db2", "both"],
        default="both",
        help="Which collection to build (default: both)",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Drop and rebuild existing collections",
    )
    args = parser.parse_args()

    targets = ["db1", "db2"] if args.db == "both" else [args.db]

    for db_key in targets:
        build_collection(db_key, reset=args.reset)

    print("\nAll done.")
    print(f"  Clinical DB -> {VECTORDB_DIR / 'clinical'}")
    print(f"  Therapy DB  -> {VECTORDB_DIR / 'therapy'}")


if __name__ == "__main__":
    main()
