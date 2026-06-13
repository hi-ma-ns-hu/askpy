"""
services/retriever.py — the retrieval stage of the RAG pipeline.

Flow:  metadata pre-filter → hybrid search (dense ⊕ sparse, RRF fusion)
       → Cohere rerank → top-k chunks.

Returns chunks shaped {title, text, similarity, url, score, tags} — the
`title`/`text`/`similarity` keys are what shared.llm.get_llm_answer expects;
the rest are carried through for source attribution in the API response.

If COHERE_API_KEY is unset (or the rerank call fails), it degrades gracefully
to hybrid-only ranking so the endpoint never hard-fails on the reranker.
"""
from __future__ import annotations

import asyncio

from qdrant_client import models

from config import settings
from shared import get_logger
from shared.llm.embedding import embed_text
from shared.storage.qdrant import get_async_qdrant_client, DENSE, SPARSE

logger = get_logger(__name__)

_sparse_model = None      # fastembed BM25 — loaded once, lazily
_cohere_client = None


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
  # fastembed is sync/CPU-bound — run off the event loop
  emb = await asyncio.to_thread(lambda: next(iter(_get_sparse_model().embed([text]))))
  return models.SparseVector(indices=emb.indices.tolist(), values=emb.values.tolist())


def _build_filter(tags: list[str] | None, min_score: int | None) -> models.Filter | None:
  must = []
  if tags:
    must.append(models.FieldCondition(key="tags", match=models.MatchAny(any=tags)))
  if min_score is not None:
    must.append(models.FieldCondition(key="score", range=models.Range(gte=min_score)))
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

async def _rerank(question: str, candidates: list, top_k: int) -> list[dict]:
  payloads = [c.payload for c in candidates]
  co = _get_cohere()

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

async def retrieve(
  question: str,
  top_k: int | None = None,
  tags: list[str] | None = None,
  min_score: int | None = None,
) -> list[dict]:
  """Retrieve the most relevant Q&A chunks for a question."""
  top_k = top_k or settings.RETRIEVE_TOP_K
  client = get_async_qdrant_client()
  qfilter = _build_filter(tags, min_score)

  dense_vec = await embed_text(question)
  sparse_vec = await _sparse_encode(question)

  # Hybrid: prefetch dense + sparse candidate sets, fuse with RRF.
  res = await client.query_points(
    collection_name=settings.QDRANT_COLLECTION,
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

  reranked = await _rerank(question, res.points, top_k)
  return [c for c in reranked if c["similarity"] >= settings.RETRIEVAL_THRESHOLD][:top_k]
