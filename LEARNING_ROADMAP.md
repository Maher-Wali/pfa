# Learning Roadmap — Mental Health RAG + Multi-Agent System

## What we are building

A RAG (Retrieval-Augmented Generation) system with multiple LLM agents, where each
agent is responsible for a specific domain:

- **Clinical agent** — answers "what is X disorder", symptoms, causes, diagnosis
- **Therapy agent** — answers "how to cope with X", techniques, exercises
- **Crisis detection agent** — detects urgency and routes accordingly
- **Orchestrator agent** — receives the user query and decides which domain agent handles it

The knowledge bases (DB1 clinical, DB2 therapy) are already built. The next step is
wrapping retrieval into agents and connecting them with an orchestrator.

---

## 1. Foundations

### Python (intermediate)
What to learn:
- Classes and inheritance — the entire scraper system is built on `BaseScraper` (`scraping/utils/common.py`)
- `async/await` — needed when multiple agents run in parallel
- Decorators, context managers, type hints
- `pathlib`, `json`, `re`, `os.environ`

### HTTP & Web
What to learn:
- How HTTP requests work (headers, status codes, sessions, retries)
- Why TLS fingerprinting blocks bots — relevant to Mayo Clinic (`scraping/db1_clinical/mayo_clinic.py`)
- HTML structure and CSS selectors — for writing new scrapers
- Libraries: `requests`, `BeautifulSoup`, `curl_cffi`

---

## 2. RAG — the core of this project

Understand every layer that is already implemented before extending it.

### Embeddings & Vector Search
What to learn:
- What an embedding is: text → fixed-size vector of numbers
- Why similar meaning produces similar vectors (cosine similarity)
- `sentence-transformers` library — how `BAAI/bge-base-en-v1.5` works
- Pinecone — managed vector database: creating indexes, upserting vectors, querying
- L2 normalisation and why dot product equals cosine similarity after normalisation

Where it is used in this project:
- Embedding model loaded in `pipeline/build_vectors.py`
- Pinecone indexes built in `pipeline/build_vectors.py:build_index`
- Dense scoring in `retrieval/hybrid_retriever.py:_dense_scores`

### Chunking Strategy
What to learn:
- Why you cannot embed a whole document at once (context window limits, precision loss)
- Sentence-boundary chunking vs fixed-size chunking
- Why overlapping chunks matter — context is not lost at boundaries
- Context prefixing — why topic metadata is prepended before embedding

Where it is used in this project:
- Chunker implemented in `pipeline/utils.py:sentence_chunk` (target 200 words, 30-word overlap)
- Context prefix built in `pipeline/utils.py:db1_prefix` and `db2_prefix`
- Applied in `pipeline/prepare_db1.py:62` and `pipeline/prepare_db2.py:191`

### Hybrid Search
What to learn:
- BM25 — term frequency / inverse document frequency scoring
- When BM25 beats dense search: exact medical terms, drug names, ICD codes
- When dense beats BM25: paraphrase, synonyms, general meaning
- How to combine both: min-max normalisation then weighted sum

Where it is used in this project:
- Full implementation in `retrieval/hybrid_retriever.py:HybridRetriever`
- BM25 weight 0.65, dense weight 0.35 (clinical terms justify higher BM25 weight)
- Score combination in `retrieval/hybrid_retriever.py:hybrid_search`

### Reranking
What to learn:
- Why a two-stage approach: retrieve many candidates cheaply, then rerank the top ones accurately
- Bi-encoder (fast, independent scoring) vs Cross-encoder (slow, joint scoring)
- Reciprocal Rank Fusion — how to merge multiple ranked lists into one

Where it is used in this project:
- RRF fusion in `retrieval/rrf_rerank.py:reciprocal_rank_fusion`
- CrossEncoder reranking in `retrieval/rrf_rerank.py:rerank`
- Model used: `cross-encoder/ms-marco-MiniLM-L-6-v2`

### Query Routing
What to learn:
- Why two separate DBs need a router (clinical facts vs therapy techniques)
- Keyword-based routing vs LLM-based routing (speed vs flexibility)
- How bigram tokenisation improves multi-word keyword matching

Where it is used in this project:
- Full implementation in `retrieval/query_router.py:route_query`
- Returns `"clinical"`, `"therapy"`, or `"both"`
- Called per rewritten query in `retrieval/rag_pipeline.py:237`

---

## 3. LLMs

### How LLMs work (conceptually)
What to learn:
- Tokens, context window, temperature, max_tokens
- System prompt vs user prompt vs assistant turn
- Why grounded prompts ("answer ONLY from context") reduce hallucination
- ChatML format — the `<|im_start|>` / `<|im_end|>` token format

Where it is used in this project:
- Grounded prompt built in `retrieval/rag_pipeline.py:258`
- Query rewriting prompt in `retrieval/rag_pipeline.py:54`
- DB2 enrichment prompt in `pipeline/prepare_db2.py:54`

### Using LLMs via API
What to learn:
- **Anthropic SDK** — `client.messages.create(model, messages, max_tokens)`
- **OpenAI-compatible API** — used by LM Studio locally
- Structured output extraction: asking the LLM to return valid JSON
- Token cost estimation (Haiku is cheapest, used for enrichment)

Where it is used in this project:
- Anthropic SDK in `pipeline/prepare_db2.py:79` (Claude Haiku for DB2 enrichment)
- OpenAI client in `test_retrieval.py:63` (LM Studio local server)

### Running LLMs locally
What to learn:
- LM Studio — how to download, load, and serve models via local API
- GGUF format, quantisation levels (Q4 = fast/small, Q8 = slower/better quality)
- When to use local model vs API (cost, privacy, latency)

Where it is used in this project:
- LM Studio connection in `test_retrieval.py:53`
- Default endpoint: `http://localhost:1234`

---

## 4. Agents — where the project is heading

### Agent Fundamentals
What to learn:
- What an agent is: LLM + tools + memory + decision loop
- ReAct pattern: Reason → Act → Observe → repeat until done
- Tool calling / function calling: how an LLM decides which tool to invoke
- Agent memory: short-term (chat history) vs long-term (vector DB)
- Stopping conditions: when does an agent decide it has finished?

How it maps to this project:
- Chat history already implemented in `retrieval/rag_pipeline.py:169`
- Tool = hybrid_search over a Pinecone index
- Each domain agent wraps one retriever as its primary tool

### Multi-Agent Systems
What to learn:
- How agents communicate: message passing, shared state
- Orchestrator pattern: one agent receives the query and delegates to domain agents
- How to route between agents (extends the keyword router in `retrieval/query_router.py`)
- Parallel agent execution: running clinical + therapy agents simultaneously
- Aggregating results from multiple agents into one coherent answer
- When to use one agent vs multiple (complexity vs maintainability)

Planned architecture for this project:
```
User query
    │
    ▼
Orchestrator Agent
    ├── Clinical Agent   (uses DB1 retriever as tool)
    ├── Therapy Agent    (uses DB2 retriever as tool)
    └── Crisis Agent     (detects urgency, overrides routing)
```

### Frameworks to learn
**LangChain** (already partially used in this project via `langchain-core`)
- Chains, agents, tools, memory, document loaders
- `langchain_core.documents.Document` already used in `retrieval/hybrid_retriever.py:64`
- Start here before moving to LangGraph

**LangGraph** (recommended for the multi-agent system)
- Builds on LangChain — adds stateful, graph-based agent workflows
- Nodes = agents or processing steps
- Edges = routing logic (conditional, based on agent output)
- Ideal for orchestrator → domain agent routing
- Supports cycles (agent loops) and parallel execution

**Anthropic Tool Use**
- Native function/tool calling in Claude API
- Claude decides which tool to call and with what arguments
- Useful for building agents that call the retrievers as structured tools

---

## 5. Data & NLP

What to learn:
- **ICD-11 codes** — the classification system already used in all DB1 records (`icd11_code` field)
- Named Entity Recognition (NER) — extracting condition names and symptoms from free text
- Basic NLP concepts: tokenisation, stopwords, TF-IDF (builds intuition for BM25)
- Evaluation metrics for RAG: faithfulness, answer relevance, context recall

Relevant tool: **RAGAS** — a framework for evaluating RAG pipeline quality automatically.

---

## Suggested Learning Order

```
Week 1–2     Python intermediate + HTTP + BeautifulSoup
             → read and understand scraping/utils/common.py

Week 3–4     Embeddings + Pinecone + basic RAG from scratch
             → read pipeline/utils.py and pipeline/prepare_db1.py

Week 5–6     Hybrid search + reranking
             → read retrieval/hybrid_retriever.py and retrieval/rrf_rerank.py deeply

Week 7–8     LLM APIs (Anthropic + OpenAI) + prompt engineering
             → read pipeline/prepare_db2.py and retrieval/rag_pipeline.py

Week 9–10    LangChain basics → build a simple tool-using agent
             → extend retrieval/rag_pipeline.py with a tool interface

Week 11–12   LangGraph → build the multi-agent orchestrator
             → implement Clinical Agent, Therapy Agent, Orchestrator
```

---

## Applied to this project — what to build next

| Feature | Skills needed | Files to modify or create |
|---|---|---|
| New scrapers (more clinical sources) | BeautifulSoup, CSS selectors | `scraping/db1_clinical/` |
| Better chunking (semantic splitting) | sentence-transformers, NLP | `pipeline/utils.py` |
| Clinical Agent | LangChain agent + tool calling | `retrieval/rag_pipeline.py` |
| Therapy Agent | LangChain agent + tool calling | `retrieval/rag_pipeline.py` |
| Crisis detection agent | LLM classification, safety prompting | new file `retrieval/crisis_agent.py` |
| Orchestrator agent | LangGraph, multi-agent routing | new file `retrieval/orchestrator.py` |
| RAG evaluation | RAGAS framework | new file `eval/evaluate_rag.py` |
| Conversation memory | LangChain memory, vector stores | extend `retrieval/rag_pipeline.py` |

---

## Best Resources

| Topic | Resource |
|---|---|
| RAG fundamentals | LangChain RAG tutorial — python.langchain.com/docs/tutorials/rag |
| Embeddings & sentence-transformers | sbert.net/docs |
| Pinecone | docs.pinecone.io |
| BM25 + hybrid search | "Hybrid Search" — Pinecone learning center |
| LangGraph multi-agent | langchain-ai.github.io/langgraph/tutorials/multi_agent |
| Anthropic API + tool use | docs.anthropic.com/en/docs/tool-use |
| Prompt engineering | docs.anthropic.com/en/docs/build-with-claude/prompt-engineering |
| RAGAS evaluation | docs.ragas.io |
| LM Studio (local LLMs) | lmstudio.ai/docs |
