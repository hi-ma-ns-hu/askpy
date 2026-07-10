"""
services/semantic_cache.py — semantic similarity cache backed by Qdrant.

Production context: exact SHA-256 caches (Redis) catch copy-paste repeats.
Semantic cache catches paraphrases — same intent, different words — which
exact caches miss entirely. At scale (Notion, Glean, Perplexity), 30-60% of
traffic is paraphrase repeats; serving them from cache cuts LLM cost linearly.

Collection is separate from the main QA collection so cache entries never
pollute retrieval results and can be wiped independently.

Threshold guidance (calibrate with run_threshold_sweep.py):
  0.88 — too loose: "sort ascending" hits "sort descending" (wrong answer)
  0.94 — sweet spot: catches paraphrases, rejects different-intent questions
  0.97 — too tight: barely beats exact cache
"""
from __future__ import annotations

import json

from qdrant_client import models

from config import settings
from shared import get_logger
from shared.llm.embedding import embed_text
from shared.storage.qdrant import get_async_qdrant_client, DENSE
from services.schemas import AnswerResponse

logger = get_logger(__name__)

CACHE_COLLECTION = "qa_semantic_cache"

# In-memory counters — reset on restart, good for live diagnostics.
# Historical analysis: query structured logs for event="semantic_hit"/"miss".
# Production teams use Prometheus counters for this; same pattern, durable.
_stats: dict[str, int] = {"semantic_hits": 0, "misses": 0}


def get_stats() -> dict[str, int]:
    return dict(_stats)


async def _ensure_cache_collection() -> None:
    """Create cache collection if it doesn't exist. Dense-only — no sparse needed for cache lookup."""
    client = get_async_qdrant_client()
    exists = await client.collection_exists(CACHE_COLLECTION)
    if not exists:
        await client.create_collection(
            collection_name=CACHE_COLLECTION,
            vectors_config=models.VectorParams(
                size=settings.EMBEDDING_DIM,
                distance=models.Distance.COSINE,
            ),
        )
        logger.info("semantic cache collection created", collection=CACHE_COLLECTION)


async def semantic_cache_get(question: str, threshold: float | None = None) -> AnswerResponse | None:
    """Return a cached AnswerResponse if a similar question was answered before.

    Production note: threshold 0.94 is a starting point. Run the threshold
    sweep script after collecting 50+ real queries to find your actual sweet spot.
    False positives (wrong cached answer served) are worse than misses — err high.
    """
    try:
        t = threshold if threshold is not None else settings.SEMANTIC_CACHE_THRESHOLD
        vec = await embed_text(question)
        client = get_async_qdrant_client()
        hits = await client.query_points(
            collection_name=CACHE_COLLECTION,
            query=vec,
            limit=1,
            score_threshold=t,
            with_payload=True,
        )
        if hits.points:
            hit = hits.points[0]
            _stats["semantic_hits"] += 1
            logger.info(
                "cache",
                event="semantic_hit",
                similarity=round(hit.score, 4),
                matched_question=hit.payload.get("question", ""),
                question=question,
            )
            return AnswerResponse(**json.loads(hit.payload["response"]), cached=True)
        _stats["misses"] += 1
        logger.info("cache", event="miss", question=question)
    except Exception as e:
        # Cache failures must never break the request path.
        logger.warning("semantic cache get failed", error=str(e))
    return None


async def semantic_cache_set(question: str, response: AnswerResponse) -> None:
    """Store a question+answer in the semantic cache."""
    try:
        await _ensure_cache_collection()
        vec = await embed_text(question)
        client = get_async_qdrant_client()
        await client.upsert(
            collection_name=CACHE_COLLECTION,
            points=[
                models.PointStruct(
                    id=abs(hash(question)) % (2**63),
                    vector=vec,
                    payload={
                        "question": question,
                        "response": response.model_dump_json(exclude={"cached"}),
                    },
                )
            ],
        )
        logger.info("cache", event="semantic_set", question=question)
    except Exception as e:
        logger.warning("semantic cache set failed", error=str(e))
