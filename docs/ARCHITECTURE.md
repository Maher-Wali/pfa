# Mental Health RAG System — Architecture & Documentation

## Overview

A **Retrieval-Augmented Generation (RAG)** system for mental health information.
Given a user question, the system retrieves relevant passages from the clinical knowledge base, passes them through a **draft → critique → revise** self-refinement pipeline, and returns a grounded, high-quality answer.

The system exposes two specialised agents:

| Agent | Purpose | Index |
|---|---|---|
| `VirtualTherapyAgent` | Conversational mental health companion with safety monitoring | `mental-health-clinical` (DB1) |
| `ContentCreationAgent` | Blog posts, captions, informational content creation | `mental-health-clinical` (DB1) |

> DB2 (therapy techniques index) is reserved for future use.

The full lifecycle is split into **4 sequential stages**, plus an **agent layer** on top:

```
Stage 1          Stage 2              Stage 3           Stage 4            Agent Layer
Scraping    →    Preprocessing   →    Indexing     →    Retrieval     →    Agents + Web/CLI
```

---

## Directory Structure

```
pfa/
├── scraping/                        # Stage 1 — data collection
│   ├── run_db1.py
│   ├── run_db2.py
│   ├── utils/
│   │   ├── common.py                # BaseScraper (HTTP, retries, saving)
│   │   └── pdf_extractor.py
│   ├── db1_clinical/                # Clinical knowledge scrapers
│   │   ├── nhs.py, nice.py, nimh.py, who_mhgap.py
│   │   ├── mind_uk.py, mental_health_foundation.py
│   │   ├── beyond_blue.py, mayo_clinic.py, helpguide.py
│   └── db2_therapy/                 # Therapy technique scrapers (future)
│       └── ...
│
├── pipeline/                        # Stage 2 & 3
│   ├── prepare_db1.py
│   ├── prepare_db2.py
│   ├── build_vectors.py
│   └── utils.py
│
├── retrieval/                       # Stage 4 — query-time retrieval
│   ├── rag_pipeline.py              # MentalHealthRAG orchestrator
│   ├── hybrid_retriever.py          # BM25 + dense hybrid search
│   ├── query_router.py              # Keyword-based DB router
│   └── rrf_rerank.py                # RRF fusion + CrossEncoder reranking
│
├── agents/                          # Agent layer
│   ├── therapy_agent.py             # VirtualTherapyAgent
│   ├── content_agent.py             # ContentCreationAgent
│   ├── rag.py                       # RAGStore wrapper + context formatting
│   ├── prompts.py                   # System prompts for all agent roles
│   ├── llm.py                       # LLMClient (LM Studio / Anthropic)
│   ├── database.py                  # ConversationDB (SQLite)
│   ├── config.py                    # Settings (env vars / .env)
│   ├── web_app.py                   # FastAPI web interface
│   └── cli.py                       # Terminal interface
│
├── safety_classifier/               # Safety classification model
│   ├── classifier.py                # SafetyClassifier (probability threshold)
│   └── train.py                     # Training script
│
├── session/
│   ├── users.py                     # UserStore — accounts, profiles (SQLite)
│   └── store.py                     # SessionStore — sessions, turns (SQLite)
│
├── templates/                       # Jinja2 HTML templates
├── static/                          # CSS / JS assets
│
├── data/
│   ├── raw/
│   │   ├── db1_clinical/
│   │   └── db2_therapy/
│   └── processed/
│       ├── db1_chunks.json
│       └── db2_chunks.json
│
├── test_retrieval.py
├── requirements.txt
└── scraping/requirements.txt
```

---

## Stages 1–3 — Scraping, Preprocessing, Indexing

These stages are unchanged from the original pipeline. See the **Stage 1**, **Stage 2**, and **Stage 3** sections below for details. Their outputs feed into the agent layer at runtime.

### Stage 1 — Scraping

**Entry points:** `scraping/run_db1.py`, `scraping/run_db2.py`

#### Two knowledge bases

| | DB1 — Clinical Knowledge | DB2 — Therapy Techniques |
|---|---|---|
| **Content** | Symptoms, causes, risk factors, diagnosis, treatment | CBT/DBT/ACT exercises, coping skills |
| **Sources** | NHS, NICE, NIMH, WHO, Mind UK, MHF, Beyond Blue, Mayo Clinic | Therapist Aid, GetSelfHelp, ACT Mindfully, etc. |
| **Status** | Active (both agents retrieve from this) | Scraped; indexing deferred |

#### BaseScraper (`scraping/utils/common.py`)

- **`get(url)`** — HTTP GET with 3 retries, exponential backoff, rotating User-Agent, 20s timeout.
- **`download_bytes(url)`** — Raw binary download for PDFs.
- **`save(records, filename)`** — Serialises records to JSON under `data/raw/<db>/<source>/`.
- **`strip_boilerplate(soup, selectors)`** — Removes nav/footer/ads in-place.
- **`clean(text)`** — Collapses whitespace, strips `[edit]` markers.
- Rate limiting: random delay of 1.5–3.5s between requests.

#### DB1 scraper record schema

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

`section` values: `overview`, `symptoms`, `causes`, `risk_factors`, `diagnosis`, `treatment`, `self_help`, `when_to_seek_help`, `living_with`, `other` (filtered out in pipeline).

#### Mayo Clinic scraper

Overrides `get()` to use **`curl_cffi`** with `impersonate="chrome124"` to bypass Cloudflare WAF TLS fingerprint inspection. 19 conditions, 2 sub-pages each.

---

### Stage 2 — Preprocessing

**Entry points:** `pipeline/prepare_db1.py`, `pipeline/prepare_db2.py`

1. Load raw JSON → skip records under 40 words → clean text → sentence-chunk (~200 words, 30-word overlap) → prepend context prefix → save processed chunks.
2. DB2 adds an **LLM enrichment pass** (Claude Haiku) to fill structured fields (`steps`, `when_to_use`, `difficulty`, `estimated_time`). Pass `--no-llm` to skip.

**`db1_prefix`** format:
```
Condition: Depression | Section: symptoms | Source: Mayo Clinic
<chunk text>
```

---

### Stage 3 — Vector Indexing

**Entry point:** `pipeline/build_vectors.py`

- Embedding model: **`BAAI/bge-base-en-v1.5`** (768-dim, L2-normalised)
- Pinecone serverless indexes (AWS us-east-1, cosine metric):

| Index name | Dimension | Status |
|---|---|---|
| `mental-health-clinical` | 768 | Active — both agents |
| `mental-health-therapy` | 768 | Built; not yet queried |

Chunks are upserted in batches of 100. The `text` metadata field stores chunk text for retrieval without a separate document store.

```bash
python pipeline/build_vectors.py              # build both
python pipeline/build_vectors.py --db db1     # clinical only
python pipeline/build_vectors.py --reset      # delete and rebuild
```

---

## Stage 4 — Retrieval (`retrieval/`)

**Entry point:** `retrieval/rag_pipeline.py` — class `MentalHealthRAG`

The retrieval pipeline is shared by both agents via the `RAGStore` wrapper (`agents/rag.py`).

### Full retrieval pipeline (5 steps)

```
User question + chat history
     │
     ▼
1. Query Rewriter (LLM) ──────────► 3 standalone search queries
     │
     ▼
2. Query Router (keywords) ────────► "clinical" | "therapy" | "both"
     │
     ▼
3. Hybrid Retriever ───────────────► BM25 + Dense cosine (weights vary by agent)
     │                               runs per rewritten query
     ▼
4. RRF Fusion ─────────────────────► merge 3 ranked lists into one
     │
     ▼
5. CrossEncoder Reranker ──────────► (query, passage) pair scoring
     │
     ▼
Top-k LangChain Document objects
```

**BM25 weights** are adjusted per agent context:
- `informational=True` (ContentCreationAgent): `bm25=0.70`, `dense=0.30`
- `informational=False` (VirtualTherapyAgent): `bm25=0.35`, `dense=0.65`

**BM25 caching:** The retriever pickles the BM25 index and document list to `data/cache/` on first load so subsequent startups do not re-fetch all vectors from Pinecone.

### `RAGStore` (`agents/rag.py`)

Thin wrapper that:
- Calls `MentalHealthRAG.retrieve()` with chat history and an `llm_func` for query rewriting.
- `format_context()` formats returned Documents into numbered context blocks (max 1800 chars per doc) for the LLM prompt.
- `messages_to_history()` converts flat DB message rows into `(user, assistant)` turn pairs expected by the retriever.

---

## Agent Layer (`agents/`)

### Configuration (`agents/config.py`)

All settings are loaded from environment variables (or a `.env` file):

| Setting | Default | Notes |
|---|---|---|
| `llm_base_url` | `http://localhost:1234/v1` | LM Studio OpenAI-compatible endpoint |
| `db1_index_name` | `mental-health-clinical` | Pinecone index for both agents |
| `db2_index_name` | `mental-health-clinical` | Reserved |
| `embedding_model_name` | `BAAI/bge-base-en-v1.5` | |
| `reranker_model_name` | `cross-encoder/ms-marco-MiniLM-L-6-v2` | |
| `classifier_model_name` | `maherwali/mental-safety-classifier` | Safety classifier |
| `top_k_docs` | `5` | Retrieved passages per query |
| `classify_every_n_turns` | `4` | Safety check frequency |
| `sqlite_db_path` | `data/conversations.sqlite3` | Conversation storage |

---

### LLM Client (`agents/llm.py`)

`LLMClient` wraps the OpenAI Python SDK configured to point at **LM Studio** (local model server). The Anthropic SDK is available as a commented-out alternative.

```python
invoke_text(llm, system_prompt, user_message) → str
```

---

### Prompts (`agents/prompts.py`)

| Constant | Used by | Role |
|---|---|---|
| `THERAPY_AGENT_SYSTEM` | VirtualTherapyAgent `_draft` | Supportive companion; max 2 suggestions/turn; ends with open question |
| `CONTENT_CREATOR_SYSTEM` | ContentCreationAgent `_draft` | Professional content writer |
| `CRITIC_SYSTEM` | Both agents `_critique` | Reviews draft for correctness, safety, relevance, tone |
| `REVISER_SYSTEM` | Both agents `_revise` | Improves draft based on critique feedback |
| `SAFE_MODE_SYSTEM` | VirtualTherapyAgent `_safe_mode_response` | Crisis response: grounding, crisis contacts, de-escalation |

---

### VirtualTherapyAgent (`agents/therapy_agent.py`)

#### Per-turn flow

```
User message
     │
     ├─ store user message (ConversationDB)
     │
     ├─ Every N turns: safety classification
     │       └─ if CRITICAL → safe mode response → store → return
     │
     ├─ RAG retrieval (RAGStore.retrieve)
     │
     ├─ _draft()   ← system=THERAPY_AGENT_SYSTEM, context injected, user profile injected
     │
     ├─ _critique() ← system=CRITIC_SYSTEM, reviews draft
     │
     ├─ _revise()  ← system=REVISER_SYSTEM, improves draft using critique
     │
     └─ store final answer (with critique + context in metadata)
```

**User profile personalisation:** The draft prompt includes the user's mood baseline, goals, age, country, job, and relationship status when available.

**Safety classification trigger:** Runs every `classify_every_n_turns` assistant turns. Takes the last 16 messages as a formatted conversation transcript and passes it to the classifier.

---

### ContentCreationAgent (`agents/content_agent.py`)

Same draft → critique → revise pipeline as the therapy agent, without safety classification or user profile personalisation. Uses `informational=True` in RAGStore to favour BM25 (exact keyword matching suits content research queries).

---

### Safety Classifier (`safety_classifier/classifier.py`)

`SafetyClassifier` loads **`maherwali/mental-safety-classifier`** from HuggingFace (sequence classification). Runs on GPU if available, CPU otherwise.

The classifier returns a **boolean** via `is_crisis(text) -> bool`. It computes `softmax` over the model logits and returns `True` when the probability of the crisis class (`index 1`) meets or exceeds a threshold of **0.6**. Any exception during inference is treated as a crisis (fail-safe — never fail open).

When `is_crisis` returns `True`, the agent switches to `SAFE_MODE_SYSTEM` prompt and suppresses normal RAG retrieval for that turn.

---

### Conversation Database (`agents/database.py`)

`ConversationDB` — SQLite storage for multi-turn conversations.

**Schema:**

```
conversations(id, user_id, mode, title, safety_status, created_at, updated_at)
messages(id, conversation_id, role, content, metadata, created_at)
```

- `role`: `user` | `assistant` | `system`
- `metadata`: stores critique text, retrieved context, safe_mode flag per message (JSON-serialised)
- `mode`: `virtual_therapy` | `content_creation`

**Key methods:**

| Method | Notes |
|---|---|
| `create_conversation(user_id, mode, title)` | Returns UUID |
| `add_message(conversation_id, role, content, metadata)` | |
| `get_recent_messages(conversation_id, limit=12)` | Used to build chat history for RAG |
| `get_messages(conversation_id)` | All messages (for chat page render) |
| `list_conversations(user_id, mode)` | Sidebar list |
| `update_safety_status(conversation_id, status)` | Marks conversation CRITICAL or SAFE |
| `count_assistant_messages(conversation_id)` | Triggers safety check every N turns |

---

### User Accounts (`session/users.py`)

`UserStore` — SQLite-backed user account and profile store.

**User fields:** `user_id`, `email`, `age`, `mood_baseline` (1–10), `goals` (list), `country`, `job`, `relationship_status`

Passwords are hashed with **bcrypt**. Profile fields are updated via `update_profile()` (manual) and `update_extracted_fields()` (LLM-inferred — see Profile Extractor below).

---

### Profile Extractor (`agents/profile_extractor.py`)

`extract_profile(llm, messages)` runs a silent LLM pass over recent conversation messages and returns a dict of inferred user facts.

**Extracted fields:** `age` (int), `goals` (list of strings), `job` (string), `relationship_status` (string). Fields the model cannot determine with high confidence are omitted (not null).

**Trigger — `VirtualTherapyAgent._maybe_extract_profile()`:** Called after every assistant turn. Runs at different intervals depending on profile completeness:

| Profile state | Interval |
|---|---|
| Incomplete | Every 2 assistant turns |
| Complete | Every 4 assistant turns |

Uses the last 20 messages as input. Results are merged into the user record via `UserStore.update_extracted_fields()`. Only fields with confident values are written — existing fields are not cleared.

---

## Web Interface (`agents/web_app.py`)

FastAPI application with Jinja2 templates and session-based auth.

### Routes

| Method | Path | Description |
|---|---|---|
| GET | `/` | Redirect to login or choose-mode |
| GET/POST | `/register` | Account creation |
| GET/POST | `/login` | Authentication |
| GET | `/logout` | Clear session |
| GET | `/choose-mode` | Agent selection page |
| GET | `/conversations/{mode}` | List conversations for mode |
| POST | `/conversations/{mode}/new` | Create conversation, redirect to chat |
| GET | `/chat/{conversation_id}` | Render chat page |
| POST | `/chat/{conversation_id}` | Submit message, redirect back |
| GET/POST | `/profile` | View / update user profile |
| GET/POST | `/compare` | Side-by-side bare-LLM vs RAG comparison |

### Session middleware

`SessionMiddleware` (Starlette) with a secret key stored in the app. `request.session["user_id"]` identifies the logged-in user. `require_user()` enforces auth and redirects to `/login` if unauthenticated.

---

## CLI Interface (`agents/cli.py`)

Menu-driven terminal interface. Supports multi-turn conversation with `/back` (return to menu) and `/quit` commands.

---

## Key Design Decisions

| Decision | Rationale |
|---|---|
| Draft → critique → revise pipeline | Single-pass LLM answers can be factually wrong or poorly toned; the critic catches issues and the reviser fixes them before the user sees anything |
| Both agents use clinical index only | DB2 therapy index is built but not yet wired; routing both agents to DB1 simplifies the retrieval path until DB2 is integrated |
| BM25 weight adjusted per agent | ContentCreationAgent queries are informational (keyword-heavy → 0.70 BM25); VirtualTherapyAgent queries are conversational (paraphrase-heavy → 0.65 dense) |
| Safety classifier runs every N turns, not every turn | CrossEncoder + safety model + draft/critique/revise are already expensive; batching the classifier every 4 turns keeps latency acceptable without missing escalation |
| Safety metadata stored per message | Stores `safe_mode`, `critique`, and retrieved `context` in `metadata` (JSON) so the full decision trace is queryable for debugging and audit |
| BM25 index cached to disk | Fetching all Pinecone vectors at startup is slow; pickling to `data/cache/` means the BM25 index is rebuilt only when the Pinecone data changes |
| Local LLM via LM Studio | No inference cost, no data leaving the machine, Anthropic SDK wired as a drop-in alternative in `agents/llm.py` |
| SQLite for conversations | Zero-infrastructure persistence; sufficient for single-instance deployment |
| Two separate Pinecone indexes | Clinical facts and therapy techniques have different retrieval profiles; separation enables targeted routing when DB2 is activated |
| Context prefix on chunks | Without it, identical sentences from different conditions get the same vector; the prefix shifts embeddings into the correct clinical neighbourhood |
| CrossEncoder runs after RRF, not on full corpus | CrossEncoder is accurate but slow; running it only on top RRF candidates gives quality without cost |

---

## Running the System

### 1 — Install dependencies

```bash
pip install -r requirements.txt
pip install -r scraping/requirements.txt
```

### 2 — Environment

```bash
export PINECONE_API_KEY="your-key"
# Optional: export ANTHROPIC_API_KEY if using Claude as LLM backend
```

### 3 — Scrape + preprocess + index (one-time)

```bash
cd scraping && python run_db1.py
python pipeline/prepare_db1.py
python pipeline/build_vectors.py --db db1
```

### 4 — Start LM Studio, load a model, then run

```bash
# Web interface
uvicorn agents.web_app:app --reload

# CLI
python -m agents.cli
```

### 5 — Test retrieval in isolation

```bash
python test_retrieval.py
python test_retrieval.py --host http://localhost:1234 --top-k 5
```
