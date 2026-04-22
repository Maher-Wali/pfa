# Mental Health RAG System — Architecture & Documentation

## Overview

A **Retrieval-Augmented Generation (RAG)** system for mental health information.
Given a user question, the system retrieves relevant passages from two curated knowledge bases and passes them to a local LLM to generate a grounded, accurate answer.

The system is split into **4 sequential stages**:

```
Stage 1          Stage 2              Stage 3           Stage 4
Scraping    →    Preprocessing   →    Indexing     →    Retrieval + LLM
```

---

## Directory Structure

```
pfa/
├── scraping/                        # Stage 1 — data collection
│   ├── run_db1.py                   # Runner: executes all DB1 scrapers
│   ├── run_db2.py                   # Runner: executes all DB2 scrapers
│   ├── utils/
│   │   ├── common.py                # BaseScraper (HTTP, retries, saving)
│   │   └── pdf_extractor.py         # PDF download + text extraction utility
│   ├── db1_clinical/                # Clinical knowledge scrapers
│   │   ├── nhs.py                   # NHS Mental Health Conditions
│   │   ├── nice.py                  # NICE Clinical Guidelines
│   │   ├── nimh.py                  # NIMH Health Topics
│   │   ├── who_mhgap.py             # WHO mhGAP Intervention Guide
│   │   ├── mind_uk.py               # Mind UK
│   │   ├── mental_health_foundation.py
│   │   ├── beyond_blue.py           # Beyond Blue (Australia)
│   │   ├── mayo_clinic.py           # Mayo Clinic Diseases & Conditions
│   │   └── helpguide.py
│   └── db2_therapy/                 # Therapy technique scrapers
│       ├── therapist_aid.py
│       ├── getselfhelp.py
│       ├── anxiety_canada.py
│       ├── act_mindfully.py
│       ├── self_compassion.py
│       ├── positive_psychology.py
│       ├── dbt_selfhelp.py
│       ├── iapt.py
│       └── simply_psychology.py
│
├── pipeline/                        # Stage 2 & 3 — preprocessing + indexing
│   ├── prepare_db1.py               # Clean, chunk, prefix DB1 raw records
│   ├── prepare_db2.py               # Clean, LLM-enrich, chunk DB2 records
│   ├── build_vectors.py             # Embed chunks and upsert into Pinecone
│   └── utils.py                     # clean_text, sentence_chunk, prefix builders
│
├── retrieval/                       # Stage 4 — query-time retrieval & generation
│   ├── rag_pipeline.py              # MentalHealthRAG: main orchestrator class
│   ├── hybrid_retriever.py          # BM25 + dense hybrid search
│   ├── query_router.py              # Keyword-based DB router
│   └── rrf_rerank.py                # RRF fusion + CrossEncoder reranking
│
├── data/
│   ├── raw/
│   │   ├── db1_clinical/            # Output of Stage 1 DB1 scrapers
│   │   │   ├── nhs/nhs_clinical.json
│   │   │   ├── nimh/nimh_clinical.json
│   │   │   ├── mayo_clinic/mayo_clinic_clinical.json
│   │   │   └── ...
│   │   └── db2_therapy/             # Output of Stage 1 DB2 scrapers
│   │       └── ...
│   └── processed/
│       ├── db1_chunks.json          # Output of prepare_db1.py
│       └── db2_chunks.json          # Output of prepare_db2.py
│
├── test_retrieval.py                # RAG vs bare-LLM comparison script
├── requirements.txt                 # Full pinned dependencies
└── scraping/requirements.txt        # Scraping-only dependencies
```

---

## Stage 1 — Scraping

**Entry points:** `scraping/run_db1.py`, `scraping/run_db2.py`

### Two knowledge bases

| | DB1 — Clinical Knowledge | DB2 — Therapy Techniques |
|---|---|---|
| **Question answered** | What is this disorder? | How do I manage it? |
| **Content** | Symptoms, causes, risk factors, diagnosis, treatment | CBT/DBT/ACT exercises, coping skills, worksheets |
| **Sources** | NHS, NICE, NIMH, WHO, Mind UK, MHF, Beyond Blue, Mayo Clinic | Therapist Aid, GetSelfHelp, ACT Mindfully, DBT Self Help, etc. |
| **Runner** | `scraping/run_db1.py` | `scraping/run_db2.py` |
| **Output** | `data/raw/db1_clinical/<source>/` | `data/raw/db2_therapy/<source>/` |

### BaseScraper (`scraping/utils/common.py`)

All scrapers inherit from `BaseScraper`. It provides:

- **`get(url)`** — HTTP GET with 3 retries, exponential backoff (5s, 10s, 15s), rotating User-Agent headers, 20s timeout. Returns a `BeautifulSoup` object or `None`.
- **`download_bytes(url)`** — Raw binary download for PDFs.
- **`save(records, filename)`** — Serialises a list of dicts to JSON under `data/raw/<db>/<source>/`.
- **`strip_boilerplate(soup, selectors)`** — Removes nav, footer, ads and other non-content elements in-place.
- **`clean(text)`** — Collapses whitespace, strips `[edit]` markers.
- Rate limiting: random delay of 1.5–3.5s between every request (`_wait()`).

### DB1 scraper record schema

Every DB1 scraper produces records of this shape:

```json
{
  "condition":    "Depression",
  "aliases":      ["MDD", "major depressive disorder"],
  "source":       "Mayo Clinic",
  "source_url":   "https://www.mayoclinic.org/...",
  "section":      "symptoms",
  "content":      "Feelings of sadness, tearfulness...",
  "icd11_code":   "6A70",
  "last_scraped": "2026-04-16"
}
```

**`section` values** used across DB1 scrapers:

| Value | Meaning |
|---|---|
| `overview` | General description / what the condition is |
| `symptoms` | Signs and symptoms |
| `causes` | Causes and contributing factors |
| `risk_factors` | Who is at risk |
| `diagnosis` | How it is diagnosed |
| `treatment` | Treatment options (medication, therapy) |
| `self_help` | Coping strategies, lifestyle changes |
| `when_to_seek_help` | When and how to get professional help |
| `living_with` | Managing day-to-day life |
| `other` | Boilerplate, links, promotions — filtered out in pipeline |

### Mayo Clinic scraper (`scraping/db1_clinical/mayo_clinic.py`)

Mayo Clinic blocks standard HTTP requests via Cloudflare WAF (TLS fingerprint inspection). This scraper overrides the inherited `get()` method to use **`curl_cffi`** with `impersonate="chrome124"`, which replicates Chrome's TLS handshake and bypasses the 403.

- 19 conditions covered, each with 2 sub-pages (`symptoms-causes`, `diagnosis-treatment`)
- Only sections in `{symptoms, causes, risk_factors, diagnosis, treatment, self_help}` are kept (`KEEP_SECTIONS`)
- URLs are hardcoded because Mayo Clinic appends opaque numeric IDs (e.g. `syc-20356007`) that cannot be derived from slugs

### DB2 scraper record schema

```json
{
  "technique_name":    "Progressive Muscle Relaxation",
  "modality":          "relaxation",
  "raw_content":       "PMR involves tensing and releasing...",
  "source":            "Therapist Aid",
  "source_url":        "https://...",
  "target_conditions": [],
  "steps":             null,
  "when_to_use":       null,
  "difficulty":        null,
  "estimated_time":    null,
  "last_scraped":      "2026-04-16"
}
```

The `steps`, `when_to_use`, `difficulty`, and `estimated_time` fields are `null` at scrape time — they are populated by LLM enrichment in Stage 2.

---

## Stage 2 — Preprocessing

**Entry points:** `pipeline/prepare_db1.py`, `pipeline/prepare_db2.py`

### DB1 preparation (`pipeline/prepare_db1.py`)

1. Loads all JSON files under `data/raw/db1_clinical/` recursively.
2. Skips records with fewer than 40 words after cleaning.
3. Cleans text with `clean_text()` (encoding artefact removal, whitespace normalisation).
4. Chunks each record's content with `sentence_chunk()` into ~200-word overlapping segments.
5. Prepends a **context prefix** to each chunk.
6. Saves to `data/processed/db1_chunks.json`.

### DB2 preparation (`pipeline/prepare_db2.py`)

Same steps as DB1, plus an **LLM enrichment pass** using Claude Haiku (`claude-haiku-4-5`):

- Sends each record's `raw_content` to Claude with a structured extraction prompt.
- Claude fills in `steps`, `when_to_use`, `target_conditions`, `difficulty`, `estimated_time`.
- A **summary chunk** is built from these structured fields (compact, scannable).
- Both summary chunk + prose chunks are emitted per technique.

Run with `--no-llm` to skip enrichment (for testing without an API key).

### Shared utilities (`pipeline/utils.py`)

**`clean_text(text)`**
Strips encoding artefacts common in scraped sources (UTF-8/Latin-1 mangling, em-dash corruption), removes `[edit]` markers, collapses whitespace.

**`sentence_chunk(text, target_words=200, overlap_words=30)`**
Splits text into overlapping chunks that respect sentence boundaries:
1. Splits text into sentences using a regex heuristic (boundary: `.!?` followed by uppercase).
2. Greedily accumulates sentences until the next sentence would exceed `target_words`.
3. Starts the next chunk by replaying the last `overlap_words` worth of sentences (so context is not lost at chunk boundaries).
4. Chunks shorter than 30 words are merged into the previous one.

**`db1_prefix(condition, section, source, chunk)`**
```
Condition: Depression | Section: symptoms | Source: Mayo Clinic
<chunk text>
```
Without this prefix, identical sentences scraped for different conditions would receive identical embedding vectors. The prefix shifts each vector into the correct clinical neighbourhood.

**`db2_prefix(technique, modality, source, chunk)`**
```
Technique: Progressive Muscle Relaxation | Modality: relaxation | Source: Therapist Aid
<chunk text>
```

### Chunk schema (both DBs)

```json
{
  "text": "Condition: Depression | Section: symptoms | Source: NHS\nFeelings of sadness...",
  "metadata": {
    "condition":   "Depression",
    "section":     "symptoms",
    "source":      "NHS",
    "source_url":  "https://...",
    "icd11_code":  "6A70",
    "chunk_index": 0
  }
}
```

---

## Stage 3 — Vector Indexing

**Entry point:** `pipeline/build_vectors.py`

### Embedding model

**`BAAI/bge-base-en-v1.5`** — a 768-dimension English embedding model, fast and well-suited for retrieval tasks. Embeddings are **L2-normalised** so cosine similarity reduces to dot product.

### Pinecone indexes

Vectors are stored in **Pinecone serverless indexes** (AWS us-east-1, cosine metric).

| Index name | Dimension | Key metadata fields |
|---|---|---|
| `mental-health-clinical` | 768 | `condition`, `section`, `source`, `icd11_code`, `text` |
| `mental-health-therapy` | 768 | `technique_name`, `modality`, `chunk_type`, `text` |

The `text` metadata field stores the original chunk text so the retriever can reconstruct documents at query time without a separate document store.

Chunks are upserted in batches of 100 (Pinecone's recommended limit per call).

### Environment

Requires `PINECONE_API_KEY` to be set:
```bash
export PINECONE_API_KEY="your-key"
```

### Usage

```bash
python pipeline/build_vectors.py              # build both
python pipeline/build_vectors.py --db db1     # clinical only
python pipeline/build_vectors.py --db db2     # therapy only
python pipeline/build_vectors.py --reset      # delete and rebuild
```

---

## Stage 4 — Retrieval & Generation

**Entry point:** `retrieval/rag_pipeline.py` — class `MentalHealthRAG`

### Full query pipeline (7 steps)

```
User question
     │
     ▼
1. Query Rewriter (LLM) ──────────► 3 standalone search queries
     │
     ▼
2. Query Router (keywords) ────────► "clinical" | "therapy" | "both"
     │
     ▼
3. Hybrid Retriever ───────────────► BM25 (×0.65) + Dense cosine (×0.35)
     │                               runs per rewritten query
     ▼
4. RRF Fusion ─────────────────────► merge 3 ranked lists into one
     │
     ▼
5. CrossEncoder Reranker ──────────► score (query, passage) pairs
     │
     ▼
6. Passage Filter ─────────────────► keep sentences sharing ≥2 tokens with query
     │
     ▼
7. LLM ────────────────────────────► context-grounded answer
```

---

### Step 1 — Query rewriting (`rag_pipeline.py:_rewrite_queries`)

The user's question is rewritten into 3 standalone queries using the LLM, incorporating chat history for follow-up questions. Example:

- User asks: *"what about its treatment?"* (after discussing PTSD)
- Rewritten: *["What is the treatment for PTSD?", "PTSD therapy options", "How is post-traumatic stress disorder treated?"]*

This improves recall by covering multiple phrasings of the same intent.

---

### Step 2 — Query routing (`retrieval/query_router.py:route_query`)

Keyword-based routing — no LLM needed, fast and deterministic.

| Signal in query | Route |
|---|---|
| Clinical keywords only (symptom, diagnosis, medication, disorder…) | `clinical` |
| Therapy keywords only (CBT, coping, mindfulness, exercise…) | `therapy` |
| Both or neither | `both` |

When `"both"` is returned, retrieval runs on both collections and results are merged by RRF.

The `force` parameter lets callers override routing entirely.

---

### Step 3 — Hybrid retrieval (`retrieval/hybrid_retriever.py:HybridRetriever`)

Two complementary search methods run per query:

**BM25** (weight 0.65, `rank_bm25` library)
- Keyword-frequency scoring, runs locally in-memory
- Strong for exact medical terms, drug names, condition codes
- Weak for paraphrase and synonyms

**Dense / semantic** (weight 0.35, `BAAI/bge-base-en-v1.5`)
- Cosine similarity via Pinecone index query
- Strong for paraphrase, general meaning, synonyms
- Weaker for rare terminology

At startup, the retriever fetches all documents from Pinecone (via `index.list()` + `index.fetch()`) to build the local BM25 index. Dense search queries Pinecone directly.

Both score arrays are **min-max normalised** then combined:
```
final_score = 0.65 × bm25_norm + 0.35 × dense_norm
```

BM25 is weighted higher because mental health queries tend to contain specific clinical terms where exact keyword matching outperforms semantic similarity.

---

### Step 4 — RRF fusion (`retrieval/rrf_rerank.py:RerankedRRF.reciprocal_rank_fusion`)

Merges the ranked result lists from all 3 rewritten queries into a single ranked list using **Reciprocal Rank Fusion**:

```
score(doc) += 1 / (k + rank)    for each list where doc appears
```

`k=60` (standard RRF constant). Documents appearing in the top results of multiple queries receive a boosted combined score. Deduplication is by object identity.

---

### Step 5 — CrossEncoder reranking (`retrieval/rrf_rerank.py:RerankedRRF.rerank`)

Model: **`cross-encoder/ms-marco-MiniLM-L-6-v2`**

Unlike embedding similarity (which scores query and passage independently), a CrossEncoder takes both together as input and outputs a single relevance score. This is much more accurate but too slow to run on the full corpus — it only runs on the top candidates from RRF.

Pairs scored: `[user_query, passage_text]` for each candidate.

---

### Step 6 — Passage filtering (`rag_pipeline.py:_filter_passages`)

From each retrieved document, keeps only the sentences that share at least 2 tokens with the query. This strips out boilerplate that survived earlier stages (e.g. promotional text, list headers) and produces tight, relevant excerpts for the LLM context.

Each passage is labelled with the most informative metadata field (`condition` for DB1, `technique_name` for DB2).

---

### Step 7 — LLM generation (`rag_pipeline.py:MentalHealthRAG.generate_response`)

The top passages are assembled into a context block and sent to the LLM with a strict system instruction:

> *"Answer ONLY using the provided context. If the context does not contain the answer, say 'I cannot find this information in the provided context.'"*

The LLM used is whatever is running in **LM Studio** (local, OpenAI-compatible API at `http://localhost:1234`). The prompt format uses ChatML tokens (`<|im_start|>`, `<|im_end|>`).

The answer and original query are appended to `chat_history` for use in the next turn's query rewriting.

---

## Running the full pipeline

### 1 — Install dependencies

```bash
# Scraping dependencies
pip install -r scraping/requirements.txt

# Pipeline + retrieval dependencies
pip install pinecone sentence-transformers rank-bm25 langchain-core anthropic openai
```

### 2 — Scrape

```bash
cd scraping
python run_db1.py    # → data/raw/db1_clinical/
python run_db2.py    # → data/raw/db2_therapy/
```

### 3 — Preprocess

```bash
python pipeline/prepare_db1.py
python pipeline/prepare_db2.py                     # requires ANTHROPIC_API_KEY
python pipeline/prepare_db2.py --no-llm            # skip LLM enrichment
```

### 4 — Build vector indexes

```bash
export PINECONE_API_KEY="your-key"
python pipeline/build_vectors.py
```

### 5 — Test retrieval

```bash
# Start LM Studio and load a model, then:
export PINECONE_API_KEY="your-key"
python test_retrieval.py
python test_retrieval.py --host http://localhost:1234 --top-k 5
```

---

## Key design decisions

| Decision | Rationale |
|---|---|
| Two separate Pinecone indexes | Clinical facts and therapy techniques have different retrieval profiles; separating them gives better precision and enables targeted routing |
| Pinecone serverless (not ChromaDB) | Managed cloud infrastructure, no local persistence to maintain, scales automatically |
| Chunk text stored in Pinecone metadata | Avoids needing a separate document store; the retriever reads text back from the `text` metadata field |
| Context prefix on chunks | Without it, identical sentences from different conditions get the same vector; the prefix shifts embeddings into the correct clinical neighbourhood (`pipeline/utils.py:db1_prefix`) |
| BM25 weighted higher than dense (0.65 vs 0.35) | Mental health queries contain specific clinical terms where exact keyword matching outperforms semantic similarity |
| `curl_cffi` for Mayo Clinic | Cloudflare WAF inspects TLS fingerprints; `curl_cffi` with `impersonate="chrome124"` bypasses the 403 at the TLS handshake level (`scraping/db1_clinical/mayo_clinic.py`) |
| LLM enrichment for DB2 only | Therapy records need structured fields (steps, difficulty) to be useful; clinical records are already well-structured from authoritative sources |
| Sentence-boundary chunking with overlap | Avoids splitting mid-sentence; 30-word overlap ensures context is not lost at chunk boundaries (`pipeline/utils.py:sentence_chunk`) |
| CrossEncoder runs after RRF, not on full corpus | CrossEncoder is accurate but slow; running it only on the top RRF candidates gives quality without cost |
| Keyword router, no LLM routing | Fast, deterministic, and accurate enough for this two-domain split; LLM routing would add latency and a point of failure on every query |
