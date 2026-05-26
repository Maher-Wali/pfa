# Mental Health Companion

A RAG-powered web application that provides two AI-driven modes: a conversational virtual therapy companion and a mental health content creation assistant. Built on a dual Pinecone vector index, a draft → critique → revise self-refinement pipeline, and a fine-tuned safety classifier for crisis detection.

---

## Agents

| Agent | Purpose |
|---|---|
| **Virtual Therapy Agent** | Conversational mental health support with safety monitoring, crisis detection, and user profile personalisation |
| **Content Creation Agent** | Generates mental health blog posts, captions, and informational content — including AI images via FLUX.1-dev |

---

## Architecture

```
Stage 1          Stage 2              Stage 3           Stage 4            Agent Layer
Scraping    →    Preprocessing   →    Indexing     →    Retrieval     →    Agents + Web / CLI
```

**Retrieval pipeline (per query):**
```
User question + chat history
        │
        ▼
1. Query Rewriter (LLM)       →  3 standalone search queries
2. Query Router (keywords)    →  "clinical" | "therapy" | "both"
3. Hybrid Retriever           →  BM25 + dense cosine, per rewritten query
4. RRF Fusion                 →  merge 3 ranked lists
5. CrossEncoder Reranker      →  (query, passage) pair scoring
        │
        ▼
   Top-k passages → LLM draft → critique → revise → response
```

Full technical detail: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)

---

## Key Components

- **Dual Pinecone indexes** — `mental-health-clinical` (1 632 chunks) and `mental-health-therapy` (4 188 chunks), embedded with `BAAI/bge-base-en-v1.5`
- **Hybrid retrieval** — BM25 (weight adjusted per agent) + dense cosine, fused with RRF, reranked with `cross-encoder/ms-marco-MiniLM-L-6-v2`
- **Safety classifier** — `maherwali/mental-safety-classifier` on HuggingFace; runs every N turns; switches agent to crisis mode (warm amber UI, grounding response, crisis contacts) on positive detection
- **LLM backend** — LM Studio (local, OpenAI-compatible) with Anthropic SDK as a drop-in alternative
- **Profile extractor** — Silent LLM pass infers user age, goals, job, and relationship status from conversation history to personalise therapy responses

---

## Data Sources

**Clinical knowledge (DB1):** NHS, NICE, NIMH, WHO mhGAP, CCI

**Therapy techniques (DB2):** Therapist Aid, Anxiety Canada, Self-Compassion.org, Positive Psychology

---

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
pip install -r scraping/requirements.txt
```

### 2. Environment variables

```bash
PINECONE_API_KEY=...
DATABASE_URL=postgresql://postgres.[ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres

# Optional
ANTHROPIC_API_KEY=...         # use Claude instead of LM Studio
IMAGE_GENERATION_KEY=...      # HuggingFace token for FLUX.1-dev image generation
```

### 3. Scrape, preprocess, and index (one-time)

```bash
cd scraping && python run_db1.py
python pipeline/prepare_db1.py
python pipeline/build_vectors.py --db db1
```

### 4. Start LM Studio, load a model, then run

```bash
# Web interface
uvicorn web_app:app --reload

# CLI
python -m agents.cli
```

---

## Tests

```bash
python tests/test_retrieval.py
python tests/test_classifier.py
python tests/validate_dual_rag.py
```

---

> **Disclaimer:** This project is for educational and research purposes only. It is not a substitute for professional mental health care.
