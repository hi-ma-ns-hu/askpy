"""
evals/judge.py — LLM-as-judge quality evaluation.

Evaluates each pipeline answer on three dimensions using GPT-4o:

  relevance     Does the answer address what was actually asked?
  faithfulness  Is every factual claim traceable to the provided sources?
  source_fit    Are the retrieved sources relevant to the question?

Why three dimensions and not one score?
  A RAG pipeline can fail in orthogonal ways:
    retrieval-bad / LLM-good  → low source_fit, high faithfulness (correctly refused)
    retrieval-good / LLM-bad  → high source_fit, low faithfulness (hallucinated)
    both-good / wrong-question → source_fit + faithfulness fine, low relevance

  A single quality score hides which stage broke.

Note on faithfulness accuracy:
  When called from run_evals.py, the judge receives full chunk text (retrieved
  fresh via retrieve()). If called with only source excerpts from AnswerResponse,
  faithfulness scores may be under-reported — the supporting detail may exist in
  the full chunk but not in the 200-char excerpt.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from openai import AsyncOpenAI
from config import settings


@dataclass
class JudgeResult:
    relevance: float      # 0–1: answer addresses the question
    faithfulness: float   # 0–1: no claims beyond what the sources contain
    source_fit: float     # 0–1: retrieved sources are relevant to the question
    verdict: str          # "pass" | "partial" | "fail"
    reasoning: str        # one-sentence explanation


_JUDGE_SYSTEM = """\
You are a strict, impartial judge evaluating the output of a Q&A retrieval system.

Important constraint: this system is corpus-constrained. It is designed to answer ONLY
from its retrieved sources and must refuse if its sources cannot answer the question.
Refusing an out-of-domain or unsupported question is CORRECT behavior, not a failure.
Do NOT penalize the system for lacking knowledge that isn't in its sources.

You will receive:
  QUESTION  — what the user asked
  SOURCES   — text from each retrieved document (may be empty for out-of-domain queries)
  ANSWER    — the system's final answer

Score 0.0–1.0 on three dimensions:

RELEVANCE: Does the answer address the question?
  1.0 → directly and completely answers it
  0.5 → partially answers or addresses a near-miss question
  0.0 → ignores the question entirely
  Refusal ("I don't have enough information"):
    1.0 if sources are empty OR sources genuinely cannot answer the question
    0.2 if the sources DO contain the answer (the model should have answered)

FAITHFULNESS: Are all factual claims in the answer supported by the sources?
  1.0 → every claim can be traced to the provided sources
  0.5 → most claims supported, minor additions present
  0.0 → answer contains facts not found in the sources (hallucination)
  Note: refusals always score 1.0 on faithfulness.

SOURCE_FIT: Are the retrieved sources relevant to the question asked?
  1.0 → all sources directly relate to the question
  0.5 → most relevant, one or two tangential
  0.0 → sources are off-topic relative to the question

Verdict:
  "pass"    → relevance >= 0.7 AND faithfulness >= 0.8 AND source_fit >= 0.6
  "partial" → any dimension >= 0.4 but not all thresholds met
  "fail"    → any dimension < 0.4

Return ONLY valid JSON — no prose, no markdown fences:
{"relevance": 0.XX, "faithfulness": 0.XX, "source_fit": 0.XX, "verdict": "...", "reasoning": "one sentence"}\
"""


async def judge_answer(
    question: str,
    sources: list[str],
    answer: str,
) -> JudgeResult:
    """Evaluate a single pipeline result using GPT-4o as an independent judge."""
    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    sources_block = "\n".join(f"[{i + 1}] {s}" for i, s in enumerate(sources))
    user_msg = f"QUESTION: {question}\n\nSOURCES:\n{sources_block}\n\nANSWER: {answer}"

    resp = await client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": _JUDGE_SYSTEM},
            {"role": "user", "content": user_msg},
        ],
        temperature=0.0,
        response_format={"type": "json_object"},
    )

    data = json.loads(resp.choices[0].message.content)
    return JudgeResult(
        relevance=float(data["relevance"]),
        faithfulness=float(data["faithfulness"]),
        source_fit=float(data["source_fit"]),
        verdict=data["verdict"],
        reasoning=data["reasoning"],
    )
