"""
scripts/threshold_sweep.py — semantic cache threshold calibration.

Production context: before shipping a semantic cache, you need to know where
"similar enough to reuse" ends and "different intent, wrong answer" begins.
This script makes that boundary visible from data rather than intuition.

What it does:
  1. Seeds the semantic cache with answers to SEED_QUERIES
  2. Runs PROBE_QUERIES against the cache at each threshold
  3. Tracks hits (cache returned something) and false positives (hit on a
     known-different-intent pair)
  4. Prints a table — the sweet spot is the highest threshold with 0 FP

Run:
  python -m scripts.threshold_sweep

Interpret:
  hit_rate    — % of probe queries served from cache (higher = more efficient)
  false_pos   — queries where cache returned an answer with wrong intent (must be 0)
  fp_examples — which pairs triggered the false positive so you can inspect them
"""
from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.llm.embedding import embed_text
from shared.storage.qdrant import get_async_qdrant_client
from services.semantic_cache import CACHE_COLLECTION, _ensure_cache_collection
from services.schemas import AnswerResponse, Source
from qdrant_client import models

THRESHOLDS = [0.88, 0.91, 0.94, 0.97]

# Pairs: (seed_query, probe_query, same_intent)
# same_intent=True  → cache hit is CORRECT   (paraphrase)
# same_intent=False → cache hit is WRONG     (false positive)
PAIRS: list[tuple[str, str, bool]] = [
    # paraphrases — cache SHOULD hit
    ("how do I sort a list in python",          "sort a python list",                          True),
    ("how do I sort a list in python",          "what is the way to sort list elements",       True),
    ("how to read a file in python",            "open and read file python",                   True),
    ("what is a python decorator",              "explain decorators in python",                True),
    ("how to handle exceptions in python",      "try except block python",                     True),

    # different intent — cache MUST NOT hit
    ("how do I sort a list ascending in python","how do I sort a list descending in python",   False),
    ("how to read a file in python",            "how to write a file in python",               False),
    ("what is a list in python",                "what is a tuple in python",                   False),
    ("how to open a file",                      "how to delete a file",                        False),
    ("difference between == and is in python",  "difference between and and or in python",     False),
]

DUMMY_RESPONSE = AnswerResponse(
    answer="placeholder answer for calibration",
    confidence=0.8,
    sources=[Source(title="test", url="http://example.com", excerpt="test", similarity=0.8)],
    cached=False,
)


async def _seed_cache(seed_queries: list[str]) -> None:
    """Embed seed queries and upsert into the cache collection directly."""
    await _ensure_cache_collection()
    client = get_async_qdrant_client()

    for q in seed_queries:
        vec = await embed_text(q)
        await client.upsert(
            collection_name=CACHE_COLLECTION,
            points=[
                models.PointStruct(
                    id=abs(hash(q)) % (2**63),
                    vector=vec,
                    payload={
                        "question": q,
                        "response": DUMMY_RESPONSE.model_dump_json(exclude={"cached"}),
                    },
                )
            ],
        )
    print(f"seeded {len(seed_queries)} queries into cache\n")


async def _probe(probe_query: str, threshold: float) -> tuple[bool, float]:
    """Return (hit, similarity_score) for probe_query at this threshold."""
    vec = await embed_text(probe_query)
    client = get_async_qdrant_client()
    hits = await client.query_points(
        collection_name=CACHE_COLLECTION,
        query=vec,
        limit=1,
        score_threshold=threshold,
        with_payload=True,
    )
    if hits.points:
        return True, round(hits.points[0].score, 4)
    # fetch without threshold to get actual score
    raw = await client.query_points(
        collection_name=CACHE_COLLECTION,
        query=vec,
        limit=1,
        with_payload=True,
    )
    score = round(raw.points[0].score, 4) if raw.points else 0.0
    return False, score


async def main() -> None:
    seed_queries = list({seed for seed, _, _ in PAIRS})
    await _seed_cache(seed_queries)

    # collect results per threshold
    results: dict[float, dict] = {}
    for t in THRESHOLDS:
        results[t] = {"hits": 0, "fp": 0, "fp_examples": [], "total": len(PAIRS)}

    # print similarity scores for every pair so you can see the distribution
    print(f"{'intent':<6}  {'score':>6}  seed → probe")
    print("-" * 72)
    pair_scores: list[tuple[str, str, bool, float]] = []
    for seed, probe, same_intent in PAIRS:
        # probe at lowest threshold to get the score regardless
        _, score = await _probe(probe, 0.0)
        label = "same" if same_intent else "diff"
        flag = "  ←FP risk" if not same_intent and score > 0.88 else ""
        print(f"{label:<6}  {score:>6.4f}  {seed!r} → {probe!r}{flag}")
        pair_scores.append((seed, probe, same_intent, score))

    print()

    for seed, probe, same_intent, score in pair_scores:
        for t in THRESHOLDS:
            hit = score >= t
            if hit:
                results[t]["hits"] += 1
                if not same_intent:
                    results[t]["fp"] += 1
                    results[t]["fp_examples"].append((seed, probe, score))

    # print table
    print(f"{'threshold':>10}  {'hit_rate':>9}  {'false_pos':>10}  {'verdict'}")
    print("-" * 60)
    for t in THRESHOLDS:
        r = results[t]
        hit_rate = r["hits"] / r["total"] * 100
        fp = r["fp"]
        verdict = "OK" if fp == 0 else f"BAD ({fp} FP)"
        print(f"{t:>10.2f}  {hit_rate:>8.0f}%  {fp:>10}  {verdict}")

    print()

    # show false positive examples so you can inspect them
    for t in THRESHOLDS:
        if results[t]["fp_examples"]:
            print(f"threshold {t} false positives:")
            for seed, probe, score in results[t]["fp_examples"]:
                print(f"  score={score:.4f}  seed:  {seed!r}")
                print(f"         probe: {probe!r}")
            print()

    # recommend
    safe = [t for t in THRESHOLDS if results[t]["fp"] == 0]
    if safe:
        best = min(safe)  # lowest threshold with zero FP = most cache hits, still safe
        print(f"recommended threshold: {best}")
        print(f"set SEMANTIC_CACHE_THRESHOLD={best} in your config or .env")
    else:
        print("no safe threshold found in tested range — add higher thresholds or review pairs")


if __name__ == "__main__":
    asyncio.run(main())
