"""
test_truncation.py — Passage truncation comparison
===================================================
Runs 5 queries through the retrieval stack and shows each passage twice:
  • Truncated  — current behaviour (max_len=500 chars)
  • Full       — no truncation

No LLM required — retrieval only.

Usage:
  python tests/test_truncation.py
  python tests/test_truncation.py --top-k 5
"""

from __future__ import annotations

import sys
import textwrap
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ModuleNotFoundError:
    pass

from retrieval.hybrid_retriever import HybridRetriever
from retrieval.rrf_rerank import RerankedRRF
from retrieval.rag_pipeline import _format_passages

QUERIES = [
    "What are the main symptoms of generalised anxiety disorder?",
    "How is PTSD treated?",
    "What causes bipolar disorder?",
    "How does CBT help with depression?",
    "What happens during a panic attack?",
]

SEP  = "=" * 80
SEP2 = "-" * 80


def _wrap(text: str, width: int = 76, indent: str = "    ") -> str:
    out = []
    for line in text.strip().split("\n"):
        if line.strip():
            out.append(
                textwrap.fill(line, width=width,
                              initial_indent=indent, subsequent_indent=indent)
            )
        else:
            out.append("")
    return "\n".join(out)


def main() -> None:
    parser = argparse.ArgumentParser(description="Passage truncation comparison")
    parser.add_argument("--top-k", type=int, default=5,
                        help="Number of passages to compare (default: 5)")
    args = parser.parse_args()

    print("Loading retriever (fetches Pinecone corpus — ~30 s first time)…")
    retriever = HybridRetriever(index_name="mental-health-clinical")
    reranker  = RerankedRRF()
    print("Ready.\n")

    for i, query in enumerate(QUERIES, 1):
        print(SEP)
        print(f"QUERY {i}/{len(QUERIES)}: {query}")
        print(SEP)

        # Retrieve + rerank — identical for both conditions
        docs     = retriever.hybrid_search(query, k=args.top_k * 3)
        fused    = reranker.reciprocal_rank_fusion([docs])
        top_docs = reranker.rerank(query, fused, top_k=args.top_k * 2)
        top_docs = top_docs[:args.top_k]

        truncated = _format_passages(top_docs, max_len=500)
        full      = _format_passages(top_docs, max_len=10_000)

        total_trunc = sum(len(p) for p in truncated)
        total_full  = sum(len(p) for p in full)

        # --- Truncated ---
        print(f"\n  TRUNCATED (current — 500 chars max)")
        print(f"  Total context sent to LLM: {total_trunc} chars")
        print(SEP2)
        for j, p in enumerate(truncated, 1):
            print(f"\n  [Passage {j}]  {len(p)} chars")
            print(_wrap(p))

        # --- Full ---
        print(f"\n  FULL (no truncation)")
        print(f"  Total context sent to LLM: {total_full} chars  "
              f"(+{total_full - total_trunc} vs truncated)")
        print(SEP2)
        for j, (p_full, p_trunc) in enumerate(zip(full, truncated), 1):
            delta = len(p_full) - len(p_trunc)
            print(f"\n  [Passage {j}]  {len(p_full)} chars  (+{delta} chars vs truncated)")
            print(_wrap(p_full))

        print()

    print(SEP)
    print("Done.")


if __name__ == "__main__":
    main()
