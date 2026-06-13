"""
evals/run_evals.py — run a set of diverse Python queries against the LIVE
pipeline and write a results report (evals/RESULTS.md).

This is the "Test Results" deliverable: real questions, real grounded answers,
confidence, sources, latency, and an auto-generated quality observation that
you can refine by hand.

Run (server NOT required — calls the pipeline in-process):
  python -m evals.run_evals

Needs a populated Qdrant + OPENAI_API_KEY (and COHERE_API_KEY for reranking).
"""
from __future__ import annotations

import asyncio
import time
from pathlib import Path

from services.qa import ask

# (category, question) — includes vague + out-of-domain edge cases on purpose.
QUERIES: list[tuple[str, str]] = [
  ("Basics",        "How do I reverse a list in Python?"),
  ("Data structures", "How do I merge two dictionaries in Python?"),
  ("Functions",     "How do I create a decorator that accepts arguments?"),
  ("OOP",           "What is the difference between @staticmethod and @classmethod?"),
  ("Libraries",     "How do I filter rows in a pandas DataFrame by a column value?"),
  ("Concurrency",   "How does async and await work in Python?"),
  ("Error handling","How do I catch multiple exceptions in one except clause?"),
  ("Idioms",        "What is the difference between a list comprehension and a generator expression?"),
  ("Edge: vague",   "How do I make my Python code faster?"),
  ("Edge: out-of-domain", "What is the capital of France?"),
]


def observe(confidence: float, n_sources: int, answer: str) -> str:
  """Heuristic quality note — a starting point to refine by hand."""
  refused = "don't have enough information" in answer.lower()
  if refused:
    return "Correctly refused — no grounded answer in the corpus (good failure mode)."
  if confidence >= 0.7:
    return f"Strong, grounded answer ({n_sources} source(s))."
  if confidence >= 0.4:
    return f"Reasonable but partial — context only partly covers it ({n_sources} source(s))."
  return f"Low confidence — weak grounding; answer should be treated with caution ({n_sources} source(s))."


async def main(delay: float) -> None:
  rows = []
  details = []
  print(f"running {len(QUERIES)} eval queries against the live pipeline (delay={delay}s) ...\n")

  for i, (category, question) in enumerate(QUERIES):
    t0 = time.perf_counter()
    resp = await ask(question)
    latency = time.perf_counter() - t0

    note = observe(resp.confidence, len(resp.sources), resp.answer)
    rows.append((category, question, resp.confidence, len(resp.sources), note))
    details.append((category, question, resp, note))
    print(f"  [{category}] conf={resp.confidence:.2f} {latency:.2f}s — {question}")

    # Space out calls to stay under Cohere's free-trial rerank rate limit (~10/min).
    if delay and i < len(QUERIES) - 1:
      await asyncio.sleep(delay)

  # ── write report ──
  out = ["# Eval Results — Python Q&A Assistant", ""]
  out.append("Each query was run against the live RAG pipeline (hybrid retrieval → rerank → grounded answer).")
  out.append("")
  out.append("| # | Category | Question | Confidence | Sources | Observation |")
  out.append("|---|---|---|---|---|---|")
  for i, (cat, q, conf, n, note) in enumerate(rows, 1):
    out.append(f"| {i} | {cat} | {q} | {conf:.2f} | {n} | {note} |")
  out.append("")
  out.append("---")
  out.append("")

  for i, (cat, q, resp, note) in enumerate(details, 1):
    out.append(f"## {i}. [{cat}] {q}")
    out.append("")
    out.append(f"**Confidence:** {resp.confidence:.2f}  ·  **Cached:** {resp.cached}")
    out.append("")
    out.append("**Answer:**")
    out.append("")
    out.append("> " + resp.answer.replace("\n", "\n> "))
    out.append("")
    if resp.sources:
      out.append("**Sources:**")
      for s in resp.sources:
        out.append(f"- [{s.title}]({s.url}) — similarity {s.similarity:.3f}")
      out.append("")
    out.append(f"**Observation:** {note}")
    out.append("")

  report = Path(__file__).parent / "RESULTS.md"
  report.write_text("\n".join(out))
  print(f"\nwrote {report}")


if __name__ == "__main__":
  import argparse
  parser = argparse.ArgumentParser(description="Run live eval queries and write evals/RESULTS.md")
  parser.add_argument("--delay", type=float, default=7.0,
                      help="seconds between queries to stay under Cohere's free-trial rerank rate limit")
  args = parser.parse_args()
  asyncio.run(main(args.delay))
