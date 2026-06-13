"""
services/qa.py — the Q&A orchestration: cache → retrieve → ground → cache.

This is the brain behind POST /ask. It ties the retriever to the LLM answer
layer and wraps the whole thing in a Redis answer cache so repeated questions
are served instantly (and cheaply).
"""
from __future__ import annotations

import hashlib
import json

from config import settings
from shared import get_logger, redis, get_llm_answer
from services.schemas import AnswerResponse, Source
from services.retriever import retrieve

logger = get_logger(__name__)

NO_ANSWER = "I don't have enough information to answer this."


# Bump when the response schema changes — invalidates stale cached answers.
_CACHE_VERSION = "v2"


def _cache_key(question: str, top_k: int | None) -> str:
  raw = f"{question.strip().lower()}::{top_k or settings.RETRIEVE_TOP_K}"
  return f"qa:{_CACHE_VERSION}:{hashlib.sha256(raw.encode()).hexdigest()}"


def _preview(text: str, limit: int = 200) -> str:
  """A short single-line snippet of a source — prefers the answer portion."""
  snippet = text.split("Top answer:", 1)[-1] if "Top answer:" in text else text
  snippet = " ".join(snippet.split())
  return snippet[:limit].rstrip() + ("…" if len(snippet) > limit else "")


async def _cache_get(key: str) -> AnswerResponse | None:
  if redis is None:
    return None
  try:
    raw = await redis.get(key)
    if raw:
      return AnswerResponse(**json.loads(raw), cached=True)
  except Exception as e:
    logger.warning("cache read failed", error=str(e))
  return None


async def _cache_set(key: str, resp: AnswerResponse) -> None:
  if redis is None:
    return
  try:
    payload = resp.model_dump(exclude={"cached"})
    await redis.set(key, json.dumps(payload), ex=settings.QA_CACHE_TTL_SECONDS)
  except Exception as e:
    logger.warning("cache write failed", error=str(e))


async def ask(question: str, top_k: int | None = None) -> AnswerResponse:
  key = _cache_key(question, top_k)

  cached = await _cache_get(key)
  if cached:
    logger.info("answer served from cache")
    return cached

  chunks = await retrieve(question, top_k=top_k)
  if not chunks:
    # Nothing relevant retrieved — don't hallucinate, return a grounded refusal.
    return AnswerResponse(answer=NO_ANSWER, confidence=0.0, sources=[])

  answer, confidence, _ = await get_llm_answer(question, chunks)
  # Sources = the full retrieved evidence set (what the answer was grounded in),
  # ordered by rerank relevance.
  sources = [
    Source(title=chunk["title"], url=chunk["url"], excerpt=_preview(chunk["text"]), similarity=chunk["similarity"])
    for chunk in chunks
  ]
  resp = AnswerResponse(answer=answer or NO_ANSWER, confidence=confidence, sources=sources)

  await _cache_set(key, resp)
  logger.info("answer generated", confidence=confidence, sources=len(sources))
  return resp
