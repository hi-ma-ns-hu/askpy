"""
services/qa.py — the Q&A orchestration: cache → retrieve → ground → cache.

This is the brain behind POST /ask. It ties the retriever to the LLM answer
layer and wraps the whole thing in a Redis answer cache so repeated questions
are served instantly (and cheaply).
"""
from __future__ import annotations

import hashlib
import json
import time

from config import settings
from shared import get_logger, redis, get_llm_answer
from shared.llm.context.conversation import get_conversation_context, save_conversation_context
from shared.tracing import new_trace
from services.schemas import AnswerResponse, Source
from services.retriever import retrieve
from services.semantic_cache import semantic_cache_get, semantic_cache_set
from services.query_classifier import classify_query

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


async def ask(question: str, top_k: int | None = None, min_year: int | None = None, thread_id: str | None = None) -> AnswerResponse:
  trace = new_trace("qa_request", input={"question": question})

  # 1. Semantic cache — catches paraphrases exact cache misses entirely.
  #    Checked first because embed cost (~150ms) is still cheaper than
  #    retrieve + LLM (~1-3s). On miss, falls through to exact cache.
  span_cache = trace.span("cache_lookup")
  semantic = await semantic_cache_get(question)
  if semantic:
    span_cache.end(output={"hit": True, "type": "semantic"})
    trace.update(output={"answer": semantic.answer[:200], "confidence": semantic.confidence, "cached": True})
    return semantic

  key = _cache_key(question, top_k)
  cached = await _cache_get(key)
  if cached:
    span_cache.end(output={"hit": True, "type": "exact"})
    trace.update(output={"answer": cached.answer[:200], "confidence": cached.confidence, "cached": True})
    logger.info("cache", event="exact_hit", question=question)
    return cached
  span_cache.end(output={"hit": False})

  # Classify query type so we can log it alongside the request trace.
  # Opt-in via ENABLE_QUERY_CLASSIFICATION — requires torch + transformers.
  query_type = "unknown"
  if settings.ENABLE_QUERY_CLASSIFICATION:
    try:
      query_type = classify_query(question)
    except Exception as e:
      logger.warning("query classification failed", error=str(e))

  # Load prior turns for this session. Empty list when thread_id is None
  # (single-turn mode) or Redis is unavailable.
  history = []
  if thread_id and redis is not None:
    try:
      history = await get_conversation_context(workspace_id="default", thread_id=thread_id)
    except Exception as e:
      logger.warning("history load failed", error=str(e))

  t0 = time.perf_counter()
  span_retrieve = trace.span("retrieval")
  chunks = await retrieve(question, top_k=top_k, min_year=min_year)
  retrieve_ms = round((time.perf_counter() - t0) * 1000)
  span_retrieve.end(output={
    "chunks": len(chunks),
    "top_score": chunks[0]["similarity"] if chunks else 0,
  })

  if not chunks:
    # Nothing relevant retrieved — don't hallucinate, return a grounded refusal.
    # Do NOT save this turn to history: a refusal poisons future context.
    logger.info("request trace", retrieve_ms=retrieve_ms, llm_ms=0, tokens_in=0, tokens_out=0, est_cost_usd=0.0, outcome="no_retrieval", query_type=query_type)
    trace.update(output={"answer": NO_ANSWER, "confidence": 0.0, "outcome": "no_retrieval", "query_type": query_type})
    return AnswerResponse(answer=NO_ANSWER, confidence=0.0, sources=[])

  t1 = time.perf_counter()
  span_llm = trace.span("llm_generation")
  answer, confidence, citations, usage = await get_llm_answer(question, chunks, history=history)
  llm_ms = round((time.perf_counter() - t1) * 1000)
  span_llm.end(
    output={"confidence": confidence},
    usage={"input": usage.prompt_tokens, "output": usage.completion_tokens},
  )

  # GPT-4o-mini pricing: $0.15/1M input tokens, $0.60/1M output tokens.
  est_cost_usd = round(
    (usage.prompt_tokens / 1_000_000) * 0.15 +
    (usage.completion_tokens / 1_000_000) * 0.60,
    6,
  )

  # Prefer LLM-generated citation excerpts — they describe what the model
  # actually used from each chunk, which is more precise than raw truncation.
  # Fall back to _preview() for any chunk the LLM didn't explicitly cite.
  cited = {c["title"]: excerpt for c, excerpt in citations} if citations else {}
  sources = [
    Source(
      title=chunk["title"],
      url=chunk["url"],
      excerpt=cited.get(chunk["title"], _preview(chunk["text"])),
      similarity=chunk["similarity"],
    )
    for chunk in chunks
  ]

  # Gate on confidence: if the LLM wasn't sure enough, refuse rather than surface a
  # weak answer. Do NOT save low-confidence turns to history for the same reason.
  if confidence < settings.ANSWER_CONFIDENCE_THRESHOLD:
    logger.info("request trace", retrieve_ms=retrieve_ms, llm_ms=llm_ms, tokens_in=usage.prompt_tokens, tokens_out=usage.completion_tokens, est_cost_usd=est_cost_usd, outcome="low_confidence", query_type=query_type)
    trace.update(output={"answer": NO_ANSWER, "confidence": confidence, "outcome": "low_confidence", "query_type": query_type})
    return AnswerResponse(answer=NO_ANSWER, confidence=confidence, sources=sources)

  resp = AnswerResponse(answer=answer or NO_ANSWER, confidence=confidence, sources=sources)
  await _cache_set(key, resp)
  await semantic_cache_set(question, resp)

  # Save this turn to conversation history so follow-up questions have context.
  # Only reached for successful (answered) responses — refusals are not saved.
  if thread_id and redis is not None:
    try:
      await save_conversation_context(
        workspace_id="default",
        thread_id=thread_id,
        question=question,
        answer=answer or NO_ANSWER,
      )
    except Exception as e:
      logger.warning("history save failed", error=str(e))

  logger.info("request trace", retrieve_ms=retrieve_ms, llm_ms=llm_ms, tokens_in=usage.prompt_tokens, tokens_out=usage.completion_tokens, est_cost_usd=est_cost_usd, outcome="answered", query_type=query_type)
  trace.update(output={"answer": (answer or NO_ANSWER)[:200], "confidence": confidence, "outcome": "answered", "query_type": query_type})
  return resp
