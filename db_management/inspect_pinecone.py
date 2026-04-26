"""
inspect_pinecone.py
-------------------
Read-only inspection of existing Pinecone indexes.

Checks:
  - Which indexes exist and their specs (dimension, metric, cloud/region)
  - Vector counts per index
  - Metadata schema of sampled vectors vs what our pipeline expects
  - A few sample passages so you can sanity-check the content

Usage:
  python inspect_pinecone.py
  python inspect_pinecone.py --sample 10   # show more samples per index
"""

from __future__ import annotations

import os
import sys
import argparse
from dotenv import load_dotenv
from pinecone import Pinecone

load_dotenv()

# ---------------------------------------------------------------------------
# Expected schemas — must match pipeline/build_vectors.py DB_CONFIG
# ---------------------------------------------------------------------------

EXPECTED = {
    "mental-health-clinical": {
        "dimension": 768,
        "metric": "cosine",
        "metadata_keys": {"condition", "section", "source", "source_url", "icd11_code", "chunk_index", "text"},
    },
    "mental-health-therapy": {
        "dimension": 768,
        "metric": "cosine",
        "metadata_keys": {"technique_name", "modality", "source", "source_url", "chunk_type", "chunk_index", "text"},
    },
}

SEP = "=" * 64
SEP_THIN = "-" * 64


def _check(label: str, ok: bool, detail: str = "") -> None:
    mark = "OK " if ok else "MISMATCH"
    suffix = f"  ({detail})" if detail else ""
    print(f"  [{mark}] {label}{suffix}")


def inspect_index(pc: Pinecone, name: str, n_samples: int, source_filter: str | None = None) -> None:
    print(f"\n{SEP}")
    print(f"  Index: {name}")
    print(SEP)

    # -- Specs --
    desc = pc.describe_index(name)
    actual_dim = desc.dimension
    actual_metric = desc.metric
    actual_cloud = getattr(desc.spec.serverless, "cloud", "?") if hasattr(desc.spec, "serverless") else "pod"
    actual_region = getattr(desc.spec.serverless, "region", "?") if hasattr(desc.spec, "serverless") else "?"

    print(f"\n  Spec")
    print(SEP_THIN)
    print(f"  Dimension : {actual_dim}")
    print(f"  Metric    : {actual_metric}")
    print(f"  Host      : {actual_cloud} / {actual_region}")

    expected = EXPECTED.get(name)
    if expected:
        _check("dimension", actual_dim == expected["dimension"],
               f"expected {expected['dimension']}, got {actual_dim}")
        _check("metric", actual_metric == expected["metric"],
               f"expected {expected['metric']}, got {actual_metric}")
    else:
        print("  (no expected schema defined for this index)")

    # -- Vector count --
    stats = pc.Index(name).describe_index_stats()
    total = stats.total_vector_count
    print(f"\n  Vectors")
    print(SEP_THIN)
    print(f"  Total     : {total:,}")
    if stats.namespaces:
        for ns, ns_stats in stats.namespaces.items():
            label = ns if ns else "(default)"
            print(f"  Namespace '{label}': {ns_stats.vector_count:,} vectors")

    if total == 0:
        print("  Index is empty — nothing to sample.")
        return

    # -- Fetch all IDs then pull metadata in batches --
    index = pc.Index(name)
    all_ids = []
    for id_batch in index.list():
        all_ids.extend(id_batch)

    from collections import Counter
    source_counts: Counter = Counter()
    all_keys: set[str] = set()
    sample_vectors = []

    for i in range(0, len(all_ids), 100):
        batch = all_ids[i : i + 100]
        fetched = index.fetch(ids=batch)
        for v in fetched.vectors.values():
            meta = v.metadata or {}
            all_keys.update(meta.keys())
            src = meta.get("source", "(unknown)")
            source_counts[src] += 1
            if source_filter:
                if source_filter.lower() in src.lower() and len(sample_vectors) < n_samples:
                    sample_vectors.append(v)
            elif len(sample_vectors) < n_samples:
                sample_vectors.append(v)

    # -- Sources --
    print(f"\n  Sources ({len(source_counts)} unique)")
    print(SEP_THIN)
    for src, count in sorted(source_counts.items(), key=lambda x: -x[1]):
        print(f"  {count:>5} chunks  —  {src}")

    vectors = sample_vectors

    print(f"\n  Metadata schema (from {len(all_ids)} vectors)")
    print(SEP_THIN)
    print(f"  Keys found : {sorted(all_keys)}")

    if expected:
        expected_keys = expected["metadata_keys"]
        missing = expected_keys - all_keys
        extra = all_keys - expected_keys
        _check("all expected keys present", not missing,
               f"missing: {sorted(missing)}" if missing else "")
        if extra:
            print(f"  [INFO   ] Extra keys in index (not in our schema): {sorted(extra)}")

    # -- Sample passages --
    print(f"\n  Sample passages")
    print(SEP_THIN)
    for i, v in enumerate(vectors[:n_samples]):
        meta = v.metadata or {}
        text = meta.get("text", "")
        label = (
            meta.get("condition")
            or meta.get("technique_name")
            or meta.get("source")
            or "?"
        )
        section = meta.get("section") or meta.get("chunk_type") or ""
        preview = text[:200].replace("\n", " ") if text else "(no text in metadata)"
        print(f"\n  [{i+1}] id={v.id}")
        print(f"       label   : {label}  |  section: {section}  |  source: {meta.get('source', '?')}")
        print(f"       text    : {preview}{'…' if len(text) > 200 else ''}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect Pinecone indexes (read-only)")
    parser.add_argument("--sample", type=int, default=5,
                        help="Number of vectors to sample per index (default: 5)")
    parser.add_argument("--index", type=str, default=None,
                        help="Inspect only this index name (default: all)")
    parser.add_argument("--source", type=str, default=None,
                        help="Filter sample passages to this source (case-insensitive substring)")
    args = parser.parse_args()

    api_key = os.environ.get("PINECONE_API_KEY")
    if not api_key:
        print("ERROR: PINECONE_API_KEY environment variable not set.")
        sys.exit(1)

    pc = Pinecone(api_key=api_key)
    all_indexes = [idx.name for idx in pc.list_indexes()]

    if not all_indexes:
        print("No indexes found in this Pinecone account.")
        sys.exit(0)

    print(f"\nIndexes in account: {all_indexes}")

    targets = [args.index] if args.index else all_indexes
    for name in targets:
        if name not in all_indexes:
            print(f"\nIndex '{name}' not found.")
            continue
        inspect_index(pc, name, args.sample, source_filter=args.source)

    print(f"\n{SEP}")
    print("Done. No data was modified.")


if __name__ == "__main__":
    main()
