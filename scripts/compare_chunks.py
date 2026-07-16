"""
scripts/compare_chunks.py — compare retrieval quality across chunk sizes.

Run AFTER ingesting the same corpus into three collections with different chunk sizes:

  python -m scripts.ingest --chunk-size 500  --min-score 50 --max-docs 50000 --collection AskPy_500
  python -m scripts.ingest --chunk-size 2000 --min-score 50 --max-docs 50000 --collection AskPy_2000
  python -m scripts.ingest --chunk-size 4000 --min-score 50 --max-docs 50000 --collection AskPy_4000

Then run:
  python -m scripts.compare_chunks

What to observe:
  AskPy_500  — precise retrieval, thin context → faithfulness drops (LLM lacks detail)
  AskPy_2000 — balanced: embedding is focused AND context is rich
  AskPy_4000 — rich context, diluted embedding → source_fit drops (retrieval misses)
"""
from __future__ import annotations

import asyncio

from evals.judge import judge_answer, JudgeResult
from services.retriever import retrieve
from shared import get_llm_answer

COLLECTIONS = ["AskPy_500", "AskPy_2000", "AskPy_4000"]

QUERIES = [
    "How do I reverse a list in Python?",
    "How do I merge two dictionaries in Python?",
    "What is the difference between @staticmethod and @classmethod?",
    "How do I filter rows in a pandas DataFrame by a column value?",
    "How does async and await work in Python?",
]


async def _score_one(question: str, collection: str) -> JudgeResult | None:
    chunks = await retrieve(question, collection_name=collection)
    if not chunks:
        return None
    answer, _, _, _ = await get_llm_answer(question, chunks)
    source_texts = [c["text"] for c in chunks]
    return await judge_answer(question, source_texts, answer or "I don't have enough information to answer this.")


async def main() -> None:
    col_w = max(len(c) for c in COLLECTIONS)
    q_w = 44

    print(f"\n{'Question':<{q_w}}  {'collection':<{col_w}}  {'rel':>5}  {'faith':>6}  {'src':>5}  {'verdict'}")
    print("-" * (q_w + col_w + 32))

    totals: dict[str, dict] = {c: {"relevance": 0.0, "faithfulness": 0.0, "source_fit": 0.0, "n": 0} for c in COLLECTIONS}

    for question in QUERIES:
        for collection in COLLECTIONS:
            result = await _score_one(question, collection)
            if result is None:
                print(f"{question[:q_w]:<{q_w}}  {collection:<{col_w}}  {'(no results)':>20}")
                continue
            t = totals[collection]
            t["relevance"] += result.relevance
            t["faithfulness"] += result.faithfulness
            t["source_fit"] += result.source_fit
            t["n"] += 1
            print(
                f"{question[:q_w]:<{q_w}}  {collection:<{col_w}}"
                f"  {result.relevance:>5.2f}  {result.faithfulness:>6.2f}  {result.source_fit:>5.2f}"
                f"  {result.verdict}"
            )
        print()

    print("-" * (q_w + col_w + 32))
    print(f"{'AVERAGES':<{q_w}}  {'collection':<{col_w}}  {'rel':>5}  {'faith':>6}  {'src':>5}")
    for collection in COLLECTIONS:
        t = totals[collection]
        n = t["n"] or 1
        print(
            f"{'':>{q_w}}  {collection:<{col_w}}"
            f"  {t['relevance']/n:>5.2f}  {t['faithfulness']/n:>6.2f}  {t['source_fit']/n:>5.2f}"
        )


if __name__ == "__main__":
    asyncio.run(main())
