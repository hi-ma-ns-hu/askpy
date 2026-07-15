# Vidhya — Python Programming Q&A Assistant

An AI-powered Q&A system that answers Python questions for data science learners with
**grounded, cited answers** retrieved from a corpus of Stack Overflow Python Q&A.

Built as a retrieval-augmented generation (RAG) pipeline behind a FastAPI service.

> **Live demo:** https://analyticsvidhya-production.up.railway.app/api/health
> (try `POST /api/ask` — see [API usage](#endpoints) below)

---

## Features

- **Grounded answers** — every response is generated only from retrieved Stack Overflow Q&A; the model is instructed to refuse rather than hallucinate.
- **Hybrid retrieval** — dense (semantic) + sparse (BM25 keyword) search fused with Reciprocal Rank Fusion, then re-ranked with Cohere.
- **Metadata pre-filtering** — filter by tags / score before search.
- **Confidence scoring + citations** — each answer carries a calibrated confidence and links to its source questions.
- **Answer caching** — repeated questions are served instantly from Redis.
- **Tested** — pytest suite + a live eval harness over diverse queries.

---

## Architecture

```
INGEST-TIME (offline, scripts/ingest.py)
  Kaggle SO dataset ──► curate subset ──► clean HTML
                      ──► embed (OpenAI 768-d dense + BM25 sparse) ──► Qdrant

QUERY-TIME (online, POST /ask)
  question ─► cache check (Redis)
           ─► retrieve:  metadata filter ─► hybrid search (RRF) ─► Cohere rerank ─► top-k
           ─► ground:    LLM answers from retrieved context (+ confidence + citations)
           ─► cache + return
```

**Request flow:** `routers/qa.py → services/qa.py → services/retriever.py (Qdrant) → shared/llm/get_llm_answer.py (OpenAI) → Redis → JSON`

---

## Tech stack

| Concern | Choice |
|---|---|
| API framework | FastAPI + Uvicorn |
| Vector DB | Qdrant (hybrid: dense + sparse) |
| Embeddings | OpenAI `text-embedding-3-small` (768-d) |
| Sparse / keyword | `fastembed` BM25 (local, no GPU) |
| Reranker | Cohere Rerank |
| LLM | OpenAI `gpt-4o-mini` |
| Cache | Redis |
| Config | pydantic-settings |
| Testing | pytest |

---

## Project structure

```
vidhya/
├── app.py                  # FastAPI factory + /health
├── config.py               # typed settings (pydantic-settings)
├── routers/
│   ├── router.py           # mounts the API routes
│   └── qa.py               # POST /ask
├── services/
│   ├── retriever.py        # pre-filter → hybrid search → rerank
│   ├── qa.py               # orchestration: cache → retrieve → ground → cache
│   └── schemas.py          # request/response models
├── shared/
│   ├── llm/                # OpenAI client, embeddings, grounded-answer generation
│   ├── storage/            # qdrant.py (vector store) + redis.py (cache)
│   └── logging/            # structured logging
├── scripts/ingest.py       # build the Qdrant index from the dataset
├── tests/                  # pytest suite
└── evals/run_evals.py      # live eval → RESULTS.md
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
cd vidhya

python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env        # then fill in your keys
```

### Environment variables
See [`.env.example`](.env.example). Required: `OPENAI_API_KEY`, `QDRANT_URL`, `QDRANT_API_KEY`.
Optional: `REDIS_URL` (cache) and `COHERE_API_KEY` (reranker) — both degrade gracefully if unset.
The Kaggle token (`KAGGLE_API_TOKEN`) is only needed for ingestion.

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

Request body: `question` (3–2000 chars, required), `top_k` (1–20, optional).

---

## Testing

**Unit / integration suite** (fast, mocked — no network or keys):
```bash
pytest          # or: make test
```

**Live eval report** (hits the real pipeline, writes `evals/RESULTS.md`):
```bash
python -m evals.run_evals
```
Runs 8+ diverse queries (basics, pandas, decorators, async, error handling, …) plus deliberate
edge cases (a vague query and an out-of-domain one), recording each answer, confidence, sources,
latency, and a quality observation.

---

## Deployment

Will be deployed soon.

---
