"""
test_retrieval.py — RAG vs. bare-LLM comparison
=================================================
Runs a set of test queries and prints two responses side-by-side:
  • Bare LLM  — just the model, no retrieval context
  • RAG       — MentalHealthRAG pipeline (hybrid search + rerank + grounded prompt)

Usage:
  1. Install Ollama (brew install ollama) and pull a model:
       ollama pull qwen2.5
     Default endpoint: http://localhost:11434
  2. python test_retrieval.py
  3. Optional flags:
       --model   <model-id>   Ollama model name (default: auto-detects first loaded)
       --host    <url>        Ollama server URL (default: http://localhost:11434)
       --top-k   <n>          Passages passed to LLM (default: 5)
       --queries <path>       JSON file with a list of query strings
"""

from __future__ import annotations

import sys
import time
import json
import textwrap
import argparse
from pathlib import Path

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv()
# ---------------------------------------------------------------------------
# Ensure project root is on sys.path
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


# ---------------------------------------------------------------------------
# Default test queries — mix of clinical, therapy, and ambiguous
# ---------------------------------------------------------------------------
DEFAULT_QUERIES = [
    "What are the main symptoms of generalised anxiety disorder?",
    "Give me a practical DBT distress tolerance exercise I can do right now.",
    "How does CBT help with depression, and what are the core techniques?",
    "What is the difference between bipolar I and bipolar II disorder?",
    "Explain the ACT concept of cognitive defusion with an example.",
]

SEPARATOR = "=" * 72


# ---------------------------------------------------------------------------
# LLM wrapper (LM Studio local server — OpenAI-compatible API)
# ---------------------------------------------------------------------------

def build_llm(host: str, model: str | None):
    """
    Returns a callable  (prompt: str) -> str  that hits the LM Studio API.
    """
    try:
        from openai import OpenAI
    except ImportError:
        print("ERROR: 'openai' package not found.  Run:  pip install openai")
        sys.exit(1)

    client = OpenAI(base_url=f"{host}/v1", api_key="ollama")

    # Auto-detect model if not specified
    if model is None:
        try:
            models = client.models.list()
            model = models.data[0].id
            print(f"  Auto-detected model: {model}")
        except Exception as e:
            print(f"ERROR: Could not reach Ollama at {host}.\n  {e}")
            print("  Make sure Ollama is running with a model loaded (ollama pull qwen2.5).")
            sys.exit(1)

    def call_llm(prompt: str) -> str:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.6,
            max_tokens=512,
        )
        return response.choices[0].message.content.strip()

    return call_llm, model


def bare_llm_call(llm_func, query: str) -> str:
    """Call the LLM with no retrieval context — plain Q&A prompt."""
    prompt = (
        "You are a mental-health information assistant. "
        "Answer the following question as accurately and concisely as possible.\n\n"
        f"Question: {query}\n\nAnswer:"
    )
    return llm_func(prompt)


# ---------------------------------------------------------------------------
# Pretty printing
# ---------------------------------------------------------------------------

def _wrap(text: str, width: int = 70, indent: str = "  ") -> str:
    lines = text.strip().split("\n")
    wrapped = []
    for line in lines:
        if line.strip():
            wrapped.append(
                textwrap.fill(line, width=width, initial_indent=indent,
                              subsequent_indent=indent)
            )
        else:
            wrapped.append("")
    return "\n".join(wrapped)


def print_comparison(
    query: str,
    bare_answer: str,
    bare_time: float,
    rag_answer: str,
    rag_time: float,
    route: str,
):
    print(f"\n{SEPARATOR}")
    print(f"QUERY: {query}")
    print(f"ROUTE: {route}")
    print(SEPARATOR)

    print(f"\n[BARE LLM]  ({bare_time:.1f}s)")
    print(_wrap(bare_answer))

    print(f"\n[RAG]  ({rag_time:.1f}s)")
    print(_wrap(rag_answer))
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="RAG vs bare-LLM comparison")
    parser.add_argument("--model", default=None, help="LM Studio model ID")
    parser.add_argument("--host", default="http://localhost:11434",
                        help="Ollama server URL")
    parser.add_argument("--top-k", type=int, default=5,
                        help="Passages to include in RAG context")
    parser.add_argument("--queries", default=None,
                        help="Path to JSON file with list of query strings")
    args = parser.parse_args()

    # -- Queries --
    if args.queries:
        queries = json.loads(Path(args.queries).read_text(encoding="utf-8"))
    else:
        queries = DEFAULT_QUERIES

    # -- LLM --
    print("\nConnecting to Ollama…")
    llm_func, model_id = build_llm(args.host, args.model)
    print(f"  Model: {model_id}")
    print(f"  Host:  {args.host}")

    # -- RAG pipeline --
    print("\nLoading RAG pipeline (this takes ~30s the first time)…")
    from retrieval.rag_pipeline import MentalHealthRAG
    from retrieval.query_router import route_query

    rag = MentalHealthRAG()
    print("  Pipeline ready.\n")

    # -- Run queries --
    for i, query in enumerate(queries, 1):
        print(f"\nQuery {i}/{len(queries)}: {query}")

        # Bare LLM
        t0 = time.time()
        bare_ans = bare_llm_call(llm_func, query)
        bare_t = time.time() - t0

        # RAG (fresh history each query so they're independent)
        rag.clear_history()
        t0 = time.time()
        rag_ans = rag.generate_response(query, llm_func, top_k_docs=args.top_k)
        rag_t = time.time() - t0

        route = route_query(query)
        print_comparison(query, bare_ans, bare_t, rag_ans, rag_t, route)

    print(f"\n{SEPARATOR}")
    print("Done.")


if __name__ == "__main__":
    main()
