"""
evals/run_evals.py — run a set of diverse Python queries against the LIVE
pipeline and write a results report (evals/RESULTS.md).

Includes an LLM-as-judge layer (evals/judge.py) that scores each answer on
relevance, faithfulness, and source fit — three dimensions the original
heuristic observe() function cannot catch.

We call retrieve() directly alongside ask() so the judge gets the full chunk
text (up to 6000 chars), not the 200-char excerpts in AnswerResponse.sources.
This avoids false faithfulness failures from truncated source excerpts.

Run:
  python -m evals.run_evals              # full eval with judge
  python -m evals.run_evals --skip-judge # heuristic only, no extra API calls
  python -m evals.run_evals --no-cache   # bypass Redis so every answer is computed fresh
"""
from __future__ import annotations

import asyncio
import time
from pathlib import Path

import services.qa as _qa_module          # imported by name so we can patch its redis
from services.qa import ask
from services.retriever import retrieve, retrieve_twostage
from services.schemas import AnswerResponse, Source
from evals.judge import judge_answer, JudgeResult
from shared import get_llm_answer

# Two queries that cleanly isolate sparse vs dense strengths.
# Run with --mode all to see them compared side-by-side across all three modes.
COMPARISON_QUERIES = [
    "pandas merge left join",                           # keyword-heavy — sparse should win
    "how do I avoid modifying a list while iterating",  # intent-based — dense should win
]

QUERIES: list[tuple[str, str]] = [
    ("Paraphrase",       "make python code not slow"),
    ("Exact error",      "AttributeError NoneType has no attribute strip"),
    ("Version",          "dict merge operator python 3.9"),
    ("Long-tail",        "how to profile memory usage in python asyncio tasks"),
    ("Functions",        "How do I create a decorator that accepts arguments?"),
    ("OOP",              "What is the difference between @staticmethod and @classmethod?"),
    ("Concurrency",      "How does async and await work in Python?"),
    ("Idioms",           "What is the difference between a list comprehension and a generator expression?"),
    ("Error handling",   "How do I catch multiple exceptions in one except clause?"),
    ("Edge: OOD",        "What is the capital of France?"),
]


def observe(confidence: float, n_sources: int, answer: str) -> str:
    """Original heuristic — kept alongside the judge to surface disagreements."""
    refused = "don't have enough information" in answer.lower()
    if refused:
        return "heuristic: correctly refused"
    if confidence >= 0.7:
        return f"heuristic: strong ({n_sources} sources)"
    if confidence >= 0.4:
        return f"heuristic: partial ({n_sources} sources)"
    return f"heuristic: low confidence ({n_sources} sources)"


async def _run_mode_comparison() -> None:
    """Run COMPARISON_QUERIES in all three modes and print a side-by-side table."""
    print("\n" + "=" * 82)
    print("MODE COMPARISON — same query, three retrieval strategies")
    print("  sparse wins on library names / version numbers")
    print("  dense  wins on intent / paraphrase queries")
    print("  hybrid beats both consistently (RRF fusion)")
    print("=" * 82)

    for question in COMPARISON_QUERIES:
        print(f"\nQuery: {question!r}")
        print(f"  {'mode':<8}  {'rel':>5}  {'faith':>6}  {'src':>5}  {'verdict':<8}  top-1 title")
        print("  " + "-" * 76)
        for mode in ("dense", "sparse", "hybrid"):
            try:
                chunks = await retrieve(question, mode=mode)
                if not chunks:
                    print(f"  {mode:<8}  (no results)")
                    continue
                answer, _, _, _ = await get_llm_answer(question, chunks)
                source_texts = [c["text"] for c in chunks]
                result = await judge_answer(
                    question, source_texts,
                    answer or "I don't have enough information to answer this.",
                )
                top_title = chunks[0]["title"][:42]
                print(
                    f"  {mode:<8}  {result.relevance:>5.2f}  {result.faithfulness:>6.2f}"
                    f"  {result.source_fit:>5.2f}  {result.verdict:<8}  {top_title}"
                )
            except Exception as e:
                print(f"  {mode:<8}  [error: {e}]")


async def main(delay: float, skip_judge: bool = False, no_cache: bool = False, mode: str = "hybrid", skip_rerank: bool = False, use_hyde: bool = False) -> None:
    if no_cache:
        _qa_module.redis = None
        print("cache: disabled (--no-cache)\n")

    rows = []
    print(f"running {len(QUERIES)} queries (judge={'off' if skip_judge else 'on'}, delay={delay}s, hyde={use_hyde})\n")

    for i, (category, question) in enumerate(QUERIES):
        t0 = time.perf_counter()

        if mode == "hybrid":
            # Production path: cache + hybrid retrieval inside ask().
            # Retrieve again separately so the judge gets full chunk text.
            resp = await ask(question)
            latency = time.perf_counter() - t0
            judge_chunks = await retrieve(question, mode="hybrid", skip_rerank=skip_rerank, use_hyde=use_hyde) if not skip_judge else []
        elif mode == "twostage":
            chunks = await retrieve_twostage(question)
            if chunks:
                answer, confidence, _, _ = await get_llm_answer(question, chunks)
            else:
                answer, confidence, chunks = None, 0.0, []
            latency = time.perf_counter() - t0
            resp = AnswerResponse(
                answer=answer or "I don't have enough information to answer this.",
                confidence=confidence or 0.0,
                sources=[
                    Source(title=c["title"], url=c["url"], excerpt=c["text"][:200], similarity=c["similarity"])
                    for c in chunks
                ],
                cached=False,
            )
            judge_chunks = chunks
        else:
            # Non-hybrid: bypass ask() so the answer actually comes from
            # this mode's chunks, not a cached hybrid answer.
            chunks = await retrieve(question, mode=mode, skip_rerank=skip_rerank, use_hyde=use_hyde)
            if chunks:
                answer, confidence, _, _ = await get_llm_answer(question, chunks)
            else:
                answer, confidence, chunks = None, 0.0, []
            latency = time.perf_counter() - t0
            resp = AnswerResponse(
                answer=answer or "I don't have enough information to answer this.",
                confidence=confidence or 0.0,
                sources=[
                    Source(title=c["title"], url=c["url"], excerpt=c["text"][:200], similarity=c["similarity"])
                    for c in chunks
                ],
                cached=False,
            )
            judge_chunks = chunks  # same chunks, no second retrieve needed

        heuristic = observe(resp.confidence, len(resp.sources), resp.answer)

        judge: JudgeResult | None = None
        if not skip_judge:
            try:
                source_texts = [c["text"] for c in judge_chunks]
                judge = await judge_answer(question, source_texts, resp.answer)
            except Exception as e:
                print(f"  [judge error] {e}")

        rows.append((category, question, resp, latency, heuristic, judge))
        verdict = judge.verdict if judge else "—"
        print(f"  [{category:20s}] conf={resp.confidence:.2f}  verdict={verdict:7s}  {latency:.1f}s")

        if delay and i < len(QUERIES) - 1:
            await asyncio.sleep(delay)

    # "all" runs a hybrid main eval + the comparison block; report goes to results_hybrid.md
    # twostage has no reranker step so _norerank suffix is not applicable
    suffix = ("hybrid" if mode == "all" else mode) + ("_hyde" if use_hyde else "") + ("_norerank" if skip_rerank and mode != "twostage" else "")
    _write_report(rows, report_mode=suffix)
    _write_json_metrics(rows)

    if mode == "all":
        await _run_mode_comparison()


def _write_json_metrics(rows: list) -> None:
    """Write aggregated metrics to results_current.json for check_regression.py."""
    judged = [judge for _, _, _, _, _, judge in rows if judge is not None]
    if not judged:
        return
    metrics = {
        "relevance":   round(sum(j.relevance    for j in judged) / len(judged), 4),
        "faithfulness": round(sum(j.faithfulness for j in judged) / len(judged), 4),
        "source_fit":  round(sum(j.source_fit   for j in judged) / len(judged), 4),
        "n":           len(judged),
    }
    path = Path(__file__).parent / "results_current.json"
    path.write_text(__import__("json").dumps(metrics, indent=2))
    print(f"wrote {path}")


def _write_report(rows: list, report_mode: str = "hybrid") -> None:
    out = ["# Eval Results — Python Q&A Assistant", ""]
    out.append("Pipeline: hybrid retrieval → Cohere rerank → grounded LLM answer.")
    out.append("Judge: GPT-4o scores relevance, faithfulness, and source fit independently.")
    out.append("")

    # Summary table
    out.append("| # | Category | Question | Conf | Latency | Verdict | Rel | Faith | Src |")
    out.append("|---|---|---|---|---|---|---|---|---|")
    for i, (cat, q, resp, latency, heuristic, judge) in enumerate(rows, 1):
        verdict = judge.verdict if judge else "—"
        rel    = f"{judge.relevance:.2f}"    if judge else "—"
        faith  = f"{judge.faithfulness:.2f}" if judge else "—"
        src    = f"{judge.source_fit:.2f}"   if judge else "—"
        out.append(f"| {i} | {cat} | {q} | {resp.confidence:.2f} | {latency:.1f}s | {verdict} | {rel} | {faith} | {src} |")

    out.append("")

    # Disagreements — where heuristic and judge diverge is where bugs hide
    disagreements = [
        (i + 1, cat, q, resp, heuristic, judge)
        for i, (cat, q, resp, _, heuristic, judge) in enumerate(rows)
        if judge and (
            ("correctly refused" in heuristic and judge.verdict == "fail")
            or ("strong" in heuristic and judge.verdict != "pass")
            or (judge.source_fit < 0.5 and "don't have enough" not in resp.answer.lower())
        )
    ]

    if disagreements:
        out.append("## Notable disagreements: heuristic vs. judge")
        out.append("")
        out.append("Where the two measures diverge is where bugs hide.")
        out.append("")
        for num, cat, q, resp, heuristic, judge in disagreements:
            out.append(f"### #{num} [{cat}] — {q}")
            out.append(f"- **Heuristic:** {heuristic}")
            out.append(f"- **Judge:** rel={judge.relevance:.2f}, faith={judge.faithfulness:.2f}, src={judge.source_fit:.2f}, verdict=**{judge.verdict}**")
            out.append(f"- **Reasoning:** {judge.reasoning}")
            out.append("")

    out.append("---")
    out.append("")

    # Detailed per-query results
    for i, (cat, q, resp, latency, heuristic, judge) in enumerate(rows, 1):
        out.append(f"## {i}. [{cat}] {q}")
        out.append("")
        out.append(f"**Confidence:** {resp.confidence:.2f}  ·  **Latency:** {latency:.1f}s  ·  **Cached:** {resp.cached}")
        if judge:
            out.append(f"**Judge:** {judge.verdict} — rel={judge.relevance:.2f}  faith={judge.faithfulness:.2f}  src={judge.source_fit:.2f}")
            out.append(f"**Reasoning:** {judge.reasoning}")
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
        out.append(f"*{heuristic}*")
        out.append("")

    report = Path(__file__).parent / f"results_{report_mode}.md"
    report.write_text("\n".join(out))
    print(f"\nwrote {report}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run live eval queries and write evals/results.md")
    parser.add_argument("--delay", type=float, default=7.0,
                        help="seconds between queries (stay under Cohere free-tier rate limit)")
    parser.add_argument("--skip-judge", action="store_true",
                        help="skip LLM judge — fast heuristic-only run")
    parser.add_argument("--no-cache", action="store_true",
                        help="bypass Redis cache so every answer is computed fresh from Qdrant")
    parser.add_argument("--mode", choices=["hybrid", "dense", "sparse", "twostage", "all"], default="hybrid",
                        help="retrieval mode; 'twostage' uses Matryoshka 256-dim ANN + 768-dim client re-score; 'all' also runs the mode-comparison block")
    parser.add_argument("--skip-rerank", action="store_true",
                        help="disable Cohere reranker — compare source_fit with and without it")
    parser.add_argument("--hyde", action="store_true",
                        help="use HyDE — embed a hypothetical answer instead of the question (helps on vague queries)")
    args = parser.parse_args()
    asyncio.run(main(args.delay, args.skip_judge, args.no_cache, args.mode, args.skip_rerank, args.hyde))
