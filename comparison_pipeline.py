"""
comparison_pipeline.py — full pipeline vs. bare LLM
=====================================================
For each query, runs two paths and prints them side-by-side:

  • BARE LLM   — model only, no retrieval, no safety classifier
  • PIPELINE   — safety classifier → RAG → grounded LLM response
                 (crisis queries short-circuit to crisis resources)

Usage:
  1. Start LM Studio and load a model (Server tab → Start Server).
  2. python comparison_pipeline.py
  3. Optional flags:
       --model    <model-id>   LM Studio model ID (default: auto-detect)
       --host     <url>        LM Studio base URL  (default: http://localhost:1234)
       --top-k    <n>          RAG passages passed to LLM (default: 5)
       --queries  <path>       JSON file with a list of query strings
       --debug                 Show retrieved passage previews
"""

from __future__ import annotations

import os
import sys
import time
import json
import textwrap
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

DEFAULT_QUERIES = [
    "What are the main symptoms of generalised anxiety disorder?",
    "Give me a practical DBT distress tolerance exercise I can do right now.",
    "How does CBT help with depression, and what are the core techniques?",
    "What is the difference between bipolar I and bipolar II disorder?",
    "Explain the ACT concept of cognitive defusion with an example.",
]

BARE_SYSTEM = (
    "You are a mental-health information assistant. "
    "Answer accurately and concisely."
)

SEP = "=" * 72


# ---------------------------------------------------------------------------
# LLM client
# ---------------------------------------------------------------------------

def _build_client(host: str, model: str | None):
    try:
        from openai import OpenAI
    except ImportError:
        print("ERROR: 'openai' package not found.  Run:  pip install openai")
        sys.exit(1)

    client = OpenAI(base_url=f"{host}/v1", api_key="lm-studio")

    if model is None:
        try:
            model = client.models.list().data[0].id
            print(f"  Auto-detected model: {model}")
        except Exception as e:
            print(f"ERROR: Could not reach LM Studio at {host}.\n  {e}")
            sys.exit(1)

    return client, model


def _bare_call(client, model: str, query: str) -> str:
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": BARE_SYSTEM},
            {"role": "user", "content": f"Question: {query}\n\nAnswer:"},
        ],
        temperature=0.6,
        max_tokens=512,
    )
    return response.choices[0].message.content.strip()


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

def _wrap(text: str, width: int = 70, indent: str = "  ") -> str:
    lines = text.strip().split("\n")
    out = []
    for line in lines:
        if line.strip():
            out.append(textwrap.fill(line, width=width,
                                     initial_indent=indent,
                                     subsequent_indent=indent))
        else:
            out.append("")
    return "\n".join(out)


def _print_result(
    query: str,
    bare_answer: str,
    bare_time: float,
    pipeline_answer: str,
    pipeline_time: float,
    is_crisis: bool,
    passages: list[str] | None,
):
    print(f"\n{SEP}")
    print(f"QUERY    : {query}")
    if is_crisis:
        print("FLAGGED  : crisis — safety classifier intercepted")
    print(SEP)

    if passages:
        print(f"\n[RETRIEVED PASSAGES]  ({len(passages)})")
        for i, p in enumerate(passages, 1):
            preview = p[:120].replace("\n", " ")
            print(f"  {i}. {preview}…")

    print(f"\n[BARE LLM]   ({bare_time:.1f}s)")
    print(_wrap(bare_answer))

    label = "PIPELINE (crisis)" if is_crisis else "PIPELINE (RAG)"
    print(f"\n[{label}]  ({pipeline_time:.1f}s)")
    print(_wrap(pipeline_answer))
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Full pipeline vs bare-LLM comparison")
    parser.add_argument("--model", default=None)
    parser.add_argument("--host", default="http://localhost:1234")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--queries", default=None)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    queries = (
        json.loads(Path(args.queries).read_text(encoding="utf-8"))
        if args.queries
        else DEFAULT_QUERIES
    )

    # Connect to LM Studio
    print("\nConnecting to LM Studio…")
    client, model_id = _build_client(args.host, args.model)
    print(f"  Model : {model_id}")
    print(f"  Host  : {args.host}")

    # Point pipeline.py at the same LM Studio instance
    os.environ.setdefault("LLM_BASE_URL", f"{args.host}/v1")
    os.environ.setdefault("LLM_MODEL", model_id)

    # Load pipeline (imports safety classifier + RAG — takes ~30s first time)
    print("\nLoading pipeline (safety classifier + RAG)…")
    import pipeline
    print("  Pipeline ready.\n")

    for i, query in enumerate(queries, 1):
        print(f"Query {i}/{len(queries)}: {query}")

        t0 = time.time()
        bare_ans = _bare_call(client, model_id, query)
        bare_t = time.time() - t0

        t0 = time.time()
        result = pipeline.run(query)
        pipeline_t = time.time() - t0

        passages = None
        if args.debug and not result.is_crisis:
            rag = pipeline._get_rag()
            passages = getattr(rag, "_last_passages", None)

        _print_result(
            query, bare_ans, bare_t,
            result.text, pipeline_t,
            result.is_crisis, passages,
        )

    print(f"\n{SEP}")
    print("Done.")


if __name__ == "__main__":
    main()
