"""
services/retriever.py — the retrieval stage of the RAG pipeline.

Flow:  metadata pre-filter → hybrid search (dense ⊕ sparse, RRF fusion)
       → Cohere rerank → top-k chunks.

Optional enhancements (off by default):
  use_hyde=True   — generate a hypothetical answer, embed that instead of the
                    question. Helps on vague queries where the question text has
                    few retrieval-friendly terms ("make code faster" → embeds
                    "profiling", "cProfile", "time complexity").
  expand_query()  — synonym expansion applied to the sparse vector only. Dense
                    already handles synonyms semantically; BM25 does not.

Returns chunks shaped {title, text, similarity, url, score, tags} — the
`title`/`text`/`similarity` keys are what shared.llm.get_llm_answer expects;
the rest are carried through for source attribution in the API response.

If COHERE_API_KEY is unset (or the rerank call fails), it degrades gracefully
to hybrid-only ranking so the endpoint never hard-fails on the reranker.
"""
from __future__ import annotations

import asyncio
import re
import zlib
from collections import Counter

from qdrant_client import models

from config import settings
from shared import get_logger
import numpy as np

from shared.llm.embedding import embed_text, embed_twostage, MATRYOSHKA_DIM
from shared.storage.qdrant import get_async_qdrant_client, DENSE, SPARSE

logger = get_logger(__name__)

_sparse_model = None  # fastembed BM25 — loaded once, lazily
_cohere_client = None

# ── query expansion (synonym map for sparse/BM25 only) ──────────────────────
# Dense already handles synonyms via the embedding space — no need there.
# BM25 is term-based so "sort" never matches "order" without this.

_SYNONYMS: dict[str, list[str]] = {
    "sort":   ["order", "rank", "arrange"],
    "filter": ["select", "subset", "query"],
    "merge":  ["join", "combine", "concat"],
    "error":  ["exception", "traceback", "failure"],
    "speed":  ["performance", "optimize", "fast"],
}


def expand_query(q: str) -> str:
    tokens = q.lower().split()
    extra = [syn for t in tokens for syn in _SYNONYMS.get(t, [])]
    return q + " " + " ".join(extra) if extra else q


# ── sparse encoding (lightweight BM25 TF; IDF handled server-side by Qdrant) ───

def _sparse_vector(text: str) -> models.SparseVector:
  # fastembed alternative: SparseTextEmbedding("Qdrant/bm25").embed([text])
  tokens = re.findall(r"\b[a-z0-9]+\b", text.lower())
  tf = Counter(tokens)
  indices = [zlib.crc32(t.encode()) & 0x7FFF_FFFF for t in tf]
  values = [float(v) for v in tf.values()]
  return models.SparseVector(indices=indices, values=values)


# ── lazy singletons ─────────────────────────────────────────────────────────────

def _get_sparse_model():
  global _sparse_model
  if _sparse_model is None:
    from fastembed import SparseTextEmbedding
    _sparse_model = SparseTextEmbedding("Qdrant/bm25")
  return _sparse_model


def _get_cohere():
  global _cohere_client
  if _cohere_client is None and settings.COHERE_API_KEY:
    import cohere
    _cohere_client = cohere.AsyncClientV2(api_key=settings.COHERE_API_KEY)
  return _cohere_client


# ── query encoding ──────────────────────────────────────────────────────────────

async def _sparse_encode(text: str) -> models.SparseVector:
  emb = await asyncio.to_thread(lambda: next(iter(_get_sparse_model().embed([text]))))
  return models.SparseVector(indices=emb.indices.tolist(), values=emb.values.tolist())
  # CRC32 fallback (no fastembed): return _sparse_vector(text)


def _build_filter(tags: list[str] | None, min_score: int | None, min_year: int | None) -> models.Filter | None:
  must = []
  if tags:
    must.append(models.FieldCondition(key="tags", match=models.MatchAny(any=tags)))
  if min_score is not None:
    must.append(models.FieldCondition(key="score", range=models.Range(gte=min_score)))
  if min_year is not None:
    must.append(models.FieldCondition(key="year", range=models.Range(gte=min_year)))
  return models.Filter(must=must) if must else None


def _to_chunk(payload: dict, similarity: float) -> dict:
  return {
    "title": payload["title"],
    "text": payload["text"],
    "similarity": round(float(similarity), 4),
    "url": payload["url"],
    "score": payload["score"],
    "tags": payload["tags"],
  }


# ── reranking ───────────────────────────────────────────────────────────────────

async def _rerank(question: str, candidates: list, top_k: int, skip: bool = False) -> list[dict]:
  payloads = [c.payload for c in candidates]
  co = None if skip else _get_cohere()

  if co is not None:
    try:
      resp = await co.rerank(
        model=settings.RERANK_MODEL,
        query=question,
        documents=[p["text"] for p in payloads],
        top_n=top_k,
      )
      return [_to_chunk(payloads[r.index], r.relevance_score) for r in resp.results]
    except Exception as e:
      logger.warning("rerank failed, falling back to hybrid order", error=str(e))

  # Fallback: keep hybrid (RRF) order; normalise fusion scores to ~[0,1].
  scores = [c.score for c in candidates]
  lo, hi = min(scores), max(scores)
  rng = (hi - lo) or 1.0
  return [_to_chunk(c.payload, (c.score - lo) / rng) for c in candidates[:top_k]]


# ── public API ──────────────────────────────────────────────────────────────────

async def _hyde_embed(question: str) -> list[float]:
  """Generate a hypothetical answer and embed it instead of the question.

  HyDE (Hypothetical Document Embeddings): the gap between a short vague
  question and a detailed technical answer is large in embedding space. By
  asking the LLM to write a plausible answer first, we embed something that
  looks like a Stack Overflow answer — much closer to what we actually stored.
  """
  from openai import AsyncOpenAI
  client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
  resp = await client.chat.completions.create(
    model=settings.LLM_MODEL,
    messages=[
      {"role": "system", "content": "Write a short technical answer (3-4 sentences) to this Python question. Be specific."},
      {"role": "user", "content": question},
    ],
    temperature=0.3,
    max_tokens=150,
  )
  hypothetical = resp.choices[0].message.content
  logger.info("hyde", question=question[:80], hypothetical=hypothetical[:120])
  return await embed_text(hypothetical)


async def retrieve(
  question: str,
  top_k: int | None = None,
  tags: list[str] | None = None,
  min_score: int | None = None,
  min_year: int | None = None,
  collection_name: str | None = None,
  mode: str = "hybrid",        # "hybrid" | "dense" | "sparse"
  skip_rerank: bool = False,
  use_hyde: bool = False,
) -> list[dict]:
  """Retrieve the most relevant Q&A chunks for a question."""
  top_k = top_k or settings.RETRIEVE_TOP_K
  client = get_async_qdrant_client()
  qfilter = _build_filter(tags, min_score, min_year)
  collection = collection_name or settings.QDRANT_COLLECTION

  # HyDE: embed a hypothetical answer instead of the raw question.
  # Applied to the dense vector only — sparse still uses the original question
  # (with synonym expansion) because BM25 needs the actual query terms.
  sparse_question = expand_query(question)

  if mode == "dense":
    dense_vec = await _hyde_embed(question) if use_hyde else await embed_text(question)
    res = await client.query_points(
      collection_name=collection,
      query=dense_vec,
      using=DENSE,
      limit=settings.RETRIEVE_CANDIDATES,
      query_filter=qfilter,
      with_payload=True,
    )
  elif mode == "sparse":
    sparse_vec = await _sparse_encode(sparse_question)
    res = await client.query_points(
      collection_name=collection,
      query=sparse_vec,
      using=SPARSE,
      limit=settings.RETRIEVE_CANDIDATES,
      query_filter=qfilter,
      with_payload=True,
    )
  else:  # hybrid — dense + sparse prefetch, fused with RRF
    dense_vec = await _hyde_embed(question) if use_hyde else await embed_text(question)
    sparse_vec = await _sparse_encode(sparse_question)
    res = await client.query_points(
      collection_name=collection,
      prefetch=[
        models.Prefetch(query=dense_vec, using=DENSE, limit=settings.RETRIEVE_CANDIDATES, filter=qfilter),
        models.Prefetch(query=sparse_vec, using=SPARSE, limit=settings.RETRIEVE_CANDIDATES, filter=qfilter),
      ],
      query=models.FusionQuery(fusion=models.Fusion.RRF),
      limit=settings.RETRIEVE_CANDIDATES,
      with_payload=True,
    )

  if not res.points:
    return []

  reranked = await _rerank(question, res.points, top_k, skip=skip_rerank)
  return [c for c in reranked if c["similarity"] >= settings.RETRIEVAL_THRESHOLD][:top_k]


async def retrieve_twostage(
  question: str,
  top_k: int | None = None,
  collection_name: str | None = None,
) -> list[dict]:
  """Two-stage Matryoshka retrieval.

  Stage 1 — 256-dim query → Qdrant ANN: fast broad recall over all points.
  Stage 2 — 768-dim re-score: client-side cosine over the top-N candidates,
             using the first 768 dims of their stored vectors (already fetched
             with with_vectors=True) to pick the best top_k precisely.

  Why it's cheaper: stage-1 embedding is 3x smaller payload from OpenAI; in a
  dedicated 256-dim collection the ANN scan would also be 3x faster. Here we
  approximate that by truncating stored 768-dim vectors to 256 dims client-side
  to show the ranking quality is preserved before the full-dim re-score.
  """
  top_k = top_k or settings.RETRIEVE_TOP_K
  client = get_async_qdrant_client()
  collection = collection_name or settings.QDRANT_COLLECTION

  # Fire both embeddings concurrently — latency ≈ max(t256, t768), not their sum.
  small_vec, full_vec = await embed_twostage(question)

  # Stage 1: broad recall with 256-dim query truncated to match stored 768-dim.
  # We pad small_vec to 768 dims (zeros) so Qdrant accepts it, then rely on the
  # fact that Matryoshka makes the first 256 dims the most informative.
  padded = small_vec + [0.0] * (settings.EMBEDDING_DIM - MATRYOSHKA_DIM)
  res = await client.query_points(
    collection_name=collection,
    query=padded,
    using=DENSE,
    limit=settings.RETRIEVE_CANDIDATES,
    with_payload=True,
    with_vectors=True,
  )

  if not res.points:
    return []

  # Stage 2: re-score the candidates with the full 768-dim query embedding.
  q = np.array(full_vec)
  scored = []
  for p in res.points:
    stored = np.array(p.vector[DENSE])
    sim = float(np.dot(q, stored) / (np.linalg.norm(q) * np.linalg.norm(stored) + 1e-9))
    scored.append((sim, p.payload))

  scored.sort(reverse=True)
  return [
    _to_chunk(payload, sim)
    for sim, payload in scored[:top_k]
    if sim >= settings.RETRIEVAL_THRESHOLD
  ]
