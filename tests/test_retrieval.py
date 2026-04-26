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
ROOT = Path(__file__).resolve().parent.parent
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

    RAG_SYSTEM = (
        "You are a mental-health information assistant. "
        "Your answers must be grounded EXCLUSIVELY in the context passages provided. "
        "Rules:\n"
        "1. Only describe techniques, exercises, symptoms, or treatments that are "
        "explicitly stated in the context. Do NOT draw on general knowledge.\n"
        "2. Do NOT invent exercise names, technique steps, or source citations that "
        "are not present word-for-word in the context.\n"
        "3. If the context contains relevant information, answer directly and concisely "
        "using that information.\n"
        "4. If the context does not cover the question, say: 'My sources don't include "
        "specific information on [topic]. The available context covers [nearest topic] — "
        "would that help?' Do not attempt an answer from memory."
    )

    BARE_SYSTEM = (
        "You are a mental-health information assistant. "
        "Answer accurately and concisely."
    )

    def call_llm(prompt: str, system: str = BARE_SYSTEM,
                 temperature: float = 0.6) -> str:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            temperature=temperature,
            max_tokens=512,
        )
        return response.choices[0].message.content.strip()

    # The RAG pipeline calls llm_func(prompt) with a single argument.
    # Lower temperature for RAG: grounded responses need less creativity.
    def rag_llm(prompt: str) -> str:
        return call_llm(prompt, system=RAG_SYSTEM, temperature=0.2)

    return call_llm, rag_llm, model


def bare_llm_call(llm_func, query: str) -> str:
    """Call the LLM with no retrieval context — plain Q&A prompt."""
    return llm_func(f"Question: {query}\n\nAnswer:")


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
    context_passages: list[str] | None = None,
):
    print(f"\n{SEPARATOR}")
    print(f"QUERY : {query}")
    print(f"ROUTE : {route}")
    print(SEPARATOR)

    if context_passages:
        print(f"\n[RETRIEVED CONTEXT]  ({len(context_passages)} passages)")
        for i, p in enumerate(context_passages, 1):
            # Show just the label + first 120 chars so it doesn't flood output
            preview = p[:120].replace("\n", " ")
            print(f"  {i}. {preview}…")

    print(f"\n[BARE LLM]  ({bare_time:.1f}s)")
    print(_wrap(bare_answer))

    print(f"\n[RAG]       ({rag_time:.1f}s)")
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
    parser.add_argument("--debug", action="store_true",
                        help="Show retrieved passages before each RAG answer")
    args = parser.parse_args()

    # -- Queries --
    if args.queries:
        queries = json.loads(Path(args.queries).read_text(encoding="utf-8"))
    else:
        queries = DEFAULT_QUERIES

    # -- LLM --
    #-- LM Studio --
    print("\nConnecting to LM Studio…")
    bare_llm, rag_llm, model_id = build_llm(args.host, args.model)
    #-- Ollama --
    #print("\nConnecting to Ollama…")
    #llm_func, model_id = build_llm(args.host, args.model)
    print(f"  Model: {model_id}")
    print(f"  Host:  {args.host}")

    # -- RAG pipeline --
    print("\nLoading RAG pipeline (this takes ~30s the first time)…")
    from retrieval.rag_pipeline import MentalHealthRAG, _format_passages
    from retrieval.query_router import route_query

    rag = MentalHealthRAG(debug=args.debug)
    print("  Pipeline ready.\n")

    # -- Run queries --
    for i, query in enumerate(queries, 1):
        print(f"\nQuery {i}/{len(queries)}: {query}")

        # Bare LLM
        t0 = time.time()
        bare_ans = bare_llm_call(bare_llm, query)
        bare_t = time.time() - t0

        # RAG (fresh history each query so they're independent)
        rag.clear_history()
        t0 = time.time()
        rag_ans = rag.generate_response(query, rag_llm, top_k_docs=args.top_k)
        rag_t = time.time() - t0

        route = route_query(query)
        passages = rag._last_passages if args.debug else None
        print_comparison(query, bare_ans, bare_t, rag_ans, rag_t, route, passages)

    print(f"\n{SEPARATOR}")
    print("Done.")


if __name__ == "__main__":
    main()
