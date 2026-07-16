# AskPy — Python Programming Q&A Assistant

An AI-powered Q&A system that answers Python questions for data science learners with
**grounded, cited answers** retrieved from a corpus of Stack Overflow Python Q&A.

---

## Features

- **Grounded answers** — every response is generated only from retrieved Stack Overflow Q&A; the model is instructed to refuse rather than hallucinate.
- **Hybrid retrieval** — dense (semantic) + sparse (BM25 keyword) search fused with Reciprocal Rank Fusion, then re-ranked with Cohere.
- **Metadata pre-filtering** — filter by tags / score / year before search.
- **Confidence scoring + citations** — each answer carries a calibrated confidence and links to its source questions.
- **Multi-turn conversations** — pass a `thread_id` to carry conversation history across follow-up questions (Redis-backed).
- **Agentic mode (`POST /ask/agent`)** — a ReAct-style multi-tool agent that can route to `search_general`, `search_by_tags`, or `search_recent` and loop until it has enough context (capped by `MAX_STEPS`).
- **Input guardrails** — regex-based prompt-injection detection and control-character rejection before the pipeline runs.
- **Two-layer caching** — exact-match cache (Redis) plus a semantic cache (Qdrant) that catches paraphrases of previously answered questions.
- **Optional query classification** — zero-shot (BART-MNLI) tagging of query type (debugging / how-to / conceptual / library-specific / out-of-domain) for routing and logging.
- **Fine-tuned local embeddings** — swap the OpenAI embedder for a locally fine-tuned sentence-transformer (`scripts/finetune_embeddings.py`) via `LOCAL_EMBEDDING_MODEL`.
- **Distributed tracing** — optional Langfuse tracing across cache lookup, retrieval, and generation spans; a no-op when unconfigured.
- **Tested** — pytest suite, an LLM-as-judge live eval harness, and a 30-example golden-set regression gate for CI.

---

## Architecture

```
INGEST-TIME (offline, scripts/ingest.py)
  Kaggle SO dataset ──► curate subset ──► clean HTML
                      ──► embed (OpenAI dense + BM25 sparse, or a fine-tuned local model) ──► Qdrant

QUERY-TIME (online, POST /ask or /ask/agent)
  question ─► guardrails (prompt-injection / control-char check)
           ─► semantic cache check (Qdrant) ─► exact cache check (Redis)
           ─► retrieve:  metadata filter ─► hybrid search (RRF) ─► Cohere rerank ─► top-k
              (agent mode: LLM picks tools — general / by-tags / recent — in a loop)
           ─► ground:    LLM answers from retrieved context (+ confidence + citations)
           ─► cache + return
  Every stage emits an optional Langfuse trace span.
```

**Request flow:** `routers/qa.py → services/guardrails.py → services/qa.py (or services/agent.py) → services/retriever.py (Qdrant) → shared/llm/get_llm_answer.py (OpenAI) → Redis / semantic_cache.py → JSON`

---

## Tech stack

| Concern | Choice |
|---|---|
| API framework | FastAPI + Uvicorn |
| Vector DB | Qdrant (hybrid: dense + sparse, plus a separate semantic-cache collection) |
| Embeddings | OpenAI `text-embedding-3-small` (768-d), or a locally fine-tuned `sentence-transformers` model |
| Sparse / keyword | `fastembed` BM25 (local, no GPU) |
| Reranker | Cohere Rerank |
| LLM | OpenAI `gpt-4o-mini` (also drives the agent's tool calls) |
| Exact cache | Redis |
| Semantic cache | Qdrant similarity lookup (paraphrase matching) |
| Query classification (optional) | `facebook/bart-large-mnli` zero-shot classifier |
| Tracing (optional) | Langfuse |
| Config | pydantic-settings |
| Testing / eval | pytest, LLM-as-judge (GPT-4o), golden-set regression gate |

---

## Project structure

```
AskPy/
├── app.py                     # FastAPI factory + /health, /health/ready, trace middleware
├── config.py                  # typed settings (pydantic-settings)
├── routers/
│   ├── router.py               # mounts the API routes
│   └── qa.py                   # POST /ask, POST /ask/agent, GET /cache/stats
├── services/
│   ├── retriever.py            # pre-filter → hybrid search → rerank (+ two-stage Matryoshka)
│   ├── qa.py                   # orchestration: guardrails → cache → retrieve → ground → cache
│   ├── agent.py                 # multi-tool ReAct agent (search_general/by_tags/recent)
│   ├── agentic_qa.py            # single-tool, single-round agent variant
│   ├── guardrails.py            # prompt-injection + control-character input checks
│   ├── semantic_cache.py        # Qdrant-backed paraphrase cache
│   ├── query_classifier.py      # optional zero-shot query-type classification
│   ├── tag_extractor.py         # regex extraction of known library names from a question
│   └── schemas.py               # request/response models
├── shared/
│   ├── llm/                    # OpenAI client, embeddings, grounded-answer generation, conversation context
│   ├── storage/                # qdrant.py (vector store) + redis.py (cache)
│   ├── tracing.py               # optional Langfuse tracing (no-op when unconfigured)
│   └── logging/                # structured logging
├── scripts/
│   ├── ingest.py                 # build the Qdrant index from the dataset
│   ├── finetune_embeddings.py    # fine-tune a sentence-transformer on generated triplets
│   ├── finetune_dpo.py           # DPO fine-tuning of an LLM on preference pairs
│   ├── generate_finetune_data.py # build (query, positive, negative) triplets
│   ├── generate_sft_data.py      # build SFT training data
│   ├── generate_dpo_data.py      # build DPO preference pairs
│   ├── eval_ndcg.py / eval_ndcg_compare.py  # retrieval quality (NDCG) evaluation
│   ├── threshold_sweep.py        # calibrate the semantic-cache similarity threshold
│   └── compare_chunks.py         # inspect/compare retrieved chunks
├── models/                       # fine-tuned local embedding model artifacts
├── tests/                       # pytest suite
└── evals/
    ├── run_evals.py               # live eval → RESULTS.md (+ LLM-as-judge)
    ├── judge.py                   # LLM-as-judge scoring (relevance/faithfulness/source_fit)
    ├── golden.py                  # 30-example labeled golden set
    └── check_regression.py       # compares current run vs. baseline, gates CI
```

---

## Getting started

### Prerequisites
- Python 3.12+
- Accounts/keys: **OpenAI**, **Qdrant Cloud** (free tier), **Kaggle** (API token)
- Optional: **Redis** (answer cache) and **Cohere** (reranker) — both degrade gracefully if absent

### Setup
```bash
git clone <your-repo-url>
cd AskPy

python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env        # then fill in your keys
```

### Environment variables
See [`.env.example`](.env.example) / [`config.py`](config.py). Required: `OPENAI_API_KEY`.
`QDRANT_URL` / `QDRANT_API_KEY` are optional at boot (so `/health` works before ingestion is
configured) but required for retrieval to work. Everything else degrades gracefully if unset:

| Variable | Purpose |
|---|---|
| `REDIS_URL` | exact-match answer cache + conversation history |
| `COHERE_API_KEY` | reranker |
| `LOCAL_EMBEDDING_MODEL` | path to a fine-tuned local embedding model (skips OpenAI embeddings) |
| `SEMANTIC_CACHE_THRESHOLD` | similarity cutoff for the semantic cache (default `0.94`) |
| `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` | enable Langfuse tracing |
| `ENABLE_QUERY_CLASSIFICATION` | turn on zero-shot query-type logging (requires `torch` + `transformers`) |
| `KAGGLE_API_TOKEN` | only needed for `scripts/ingest.py` |

---

## Data ingestion

Build the vector index from the
[Stack Overflow Python Q&A](https://www.kaggle.com/datasets/stackoverflow/pythonquestions) dataset:

```bash
python -m scripts.ingest --min-score 10 --max-docs 20000
```

This downloads the dataset (via the Kaggle API), keeps the top questions by score joined to
their best answer, embeds them (dense + sparse), and upserts to Qdrant. Re-runs are idempotent.

---

## Running the API

```bash
uvicorn app:app --port 3000        # or: make dev
```

- API base path: `/api`
- Interactive docs: http://localhost:3000/docs

### Endpoints

**`GET /api/health`** — liveness check.

**`GET /api/health/ready`** — readiness probe (checks Redis, returns 503 while draining on shutdown).

**`POST /api/ask`** — answer a Python question.

```bash
curl -s -X POST http://localhost:3000/api/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "How do I reverse a list in Python?"}'
```

Response:
```json
{
  "answer": "You can reverse a list using slicing: L[::-1] ...",
  "confidence": 0.74,
  "sources": [
    {
      "title": "How can I reverse a list in python?",
      "url": "https://stackoverflow.com/questions/3940128",
      "excerpt": "slice with [::-1]",
      "similarity": 0.88
    }
  ],
  "cached": false
}
```

Request body: `question` (3–2000 chars, required), `top_k` (1–20, optional), `min_year`
(only retrieve answers from this year onward, optional), `thread_id` (carries multi-turn
conversation history, optional).

**`POST /api/ask/agent`** — same question, answered by a multi-tool ReAct agent that can
choose between `search_general`, `search_by_tags`, and `search_recent` across up to 4 steps.

```bash
curl -s -X POST http://localhost:3000/api/ask/agent \
  -H "Content-Type: application/json" \
  -d '{"question": "whats the modern way to open a file in python?"}'
```

Response adds `steps` (the tools called, with args and chunk counts) and `total_chunks` in
place of `sources`/`cached`.

**`GET /api/cache/stats`** — live semantic-cache hit/miss counters since last restart.

---

## Testing

**Unit / integration suite** (fast, mocked — no network or keys):
```bash
pytest          # or: make test
```

**Live eval report** (hits the real pipeline, writes `evals/RESULTS.md`):
```bash
python -m evals.run_evals              # full eval with LLM-as-judge
python -m evals.run_evals --skip-judge # heuristic only, no extra API calls
python -m evals.run_evals --no-cache   # bypass Redis so every answer is computed fresh
# or: make eval / make eval-fast / make eval-fresh
```
Runs 10 diverse queries (basics, pandas, decorators, async, error handling, …) plus a deliberate
out-of-domain edge case, recording each answer, confidence, sources, latency, and a quality
observation. An LLM-as-judge layer (`evals/judge.py`, GPT-4o) additionally scores each answer on
**relevance**, **faithfulness**, and **source fit** so retrieval and generation failures can be
told apart.

**Regression gate** (compares a fresh run against a committed baseline, exits non-zero on
regression — wire into CI before deploy):
```bash
make eval           # run_evals --no-cache, then check_regression
make eval-promote   # after manually reviewing a change, promote current → baseline
```
`evals/golden.py` holds a 30-example labeled golden set (expected substrings / refusal
expectations) used for offline evaluation independent of the live judge.

---

## Deployment


The service is a single **stateless** FastAPI app — it queries managed Qdrant Cloud and the
OpenAI/Cohere APIs, so it deploys as one web service (a `Procfile` defines the start command).
Redis is optional; the live instance runs cache-less.

Will be deployed live soon.

---