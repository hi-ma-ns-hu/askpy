"""
scripts/generate_sft_data.py — Build a supervised fine-tuning (SFT) dataset
from the Stack Overflow Python Q&A Kaggle dump.

Output: data/sft_train.jsonl — one JSON line per training example in OpenAI
chat format:

  {"messages": [
    {"role": "system",  "content": "<Vidhya system prompt>"},
    {"role": "user",    "content": "<question title + body>"},
    {"role": "assistant","content": "<cleaned top answer>"}
  ]}

Quality filters (applied before writing — this is where 80% of fine-tuning
work happens):

  1. answer_score >= MIN_ANSWER_SCORE      — absolute floor; negatively-scored
                                             answers are wrong or unhelpful
  2. answer_score / question_score >= RATIO_THRESHOLD
                                           — relative signal; a great question
                                             with a mediocre answer means the
                                             best answer is still not great
  3. answer length >= MIN_ANSWER_CHARS     — one-liners ("just do X") don't
                                             teach the model to explain reasoning
  4. answer length <= MAX_ANSWER_CHARS     — very long answers are often
                                             overlong or contain unrelated tangents
  5. question score >= MIN_QUESTION_SCORE  — low-scored questions are often
                                             unclear, duplicates, or off-topic

Run:
  python -m scripts.generate_sft_data --max-docs 5000
  python -m scripts.generate_sft_data --max-docs 5000 --no-filter  # see raw vs filtered
  head -n 3 data/sft_train.jsonl | python -m json.tool

Requires: same Kaggle dataset as scripts/ingest.py
"""
from __future__ import annotations

import argparse
import csv
import gc
import html
import json
import os
import re
from pathlib import Path

CSV_ENCODING = "latin-1"   # SO dataset is latin-1, not utf-8

# ── quality filter thresholds ────────────────────────────────────────────────
# Read 20 examples before changing these — the defaults are intentionally strict.
# Looser filters = more data but noisier training signal. Strict = less data
# but the model learns from examples that are demonstrably correct and clear.

MIN_QUESTION_SCORE = 5     # ignore poorly-received questions
MIN_ANSWER_SCORE   = 3     # floor: at least 3 upvotes on the answer
RATIO_THRESHOLD    = 0.25  # answer_score / question_score
MIN_ANSWER_CHARS   = 200   # too short = "see docs" or wrong approach
MAX_ANSWER_CHARS   = 3000  # too long = rambling or covers multiple topics


# ── system prompt (same as the live service) ────────────────────────────────

_SYSTEM_PROMPT = (
    "You are Vidhya, a Python programming assistant for data science learners. "
    "Answer the question clearly and practically. "
    "Prefer a short explanation followed by a minimal, correct code example when relevant. "
    "Use Markdown code blocks for any code. "
    "If you are unsure, say so — never invent APIs or behaviour."
)


# ── text cleaning (same logic as ingest.py) ─────────────────────────────────

def _clean(raw: str) -> str:
    if not isinstance(raw, str) or not raw:
        return ""
    text = re.sub(r"<[^>]+>", " ", html.unescape(raw))
    lines = [ln.rstrip() for ln in text.splitlines()]
    return "\n".join(ln for ln in lines if ln.strip())


# ── CSV loaders ──────────────────────────────────────────────────────────────

def _open(path: str):
    return open(path, encoding=CSV_ENCODING, errors="replace", newline="")


def _load_questions(qpath: str, max_docs: int, min_score: int) -> list[dict]:
    rows = []
    with _open(qpath) as f:
        for row in csv.DictReader(f):
            try:
                score = int(row["Score"])
            except (ValueError, KeyError):
                continue
            if score >= min_score:
                rows.append({
                    "id":    int(row["Id"]),
                    "score": score,
                    "title": row.get("Title", ""),
                    "body":  row.get("Body", ""),
                })
    rows.sort(key=lambda r: r["score"], reverse=True)
    rows = rows[:max_docs]
    print(f"  questions: kept {len(rows)} with score >= {min_score}")
    return rows


def _load_answers(apath: str, qids: set[int]) -> dict[int, dict]:
    """Best answer (highest score) per question."""
    best: dict[int, dict] = {}
    with _open(apath) as f:
        for row in csv.DictReader(f):
            try:
                parent = int(row["ParentId"])
                score  = int(row["Score"])
            except (ValueError, KeyError):
                continue
            if parent in qids:
                cur = best.get(parent)
                if cur is None or score > cur["score"]:
                    best[parent] = {"score": score, "body": row.get("Body", "")}
    print(f"  answers: matched {len(best)} questions")
    return best


# ── quality filter ────────────────────────────────────────────────────────────

def _passes_filter(q_score: int, a_score: int, a_text: str) -> tuple[bool, str]:
    """Return (passes, reason_if_rejected)."""
    if a_score < MIN_ANSWER_SCORE:
        return False, f"answer_score {a_score} < {MIN_ANSWER_SCORE}"
    if q_score > 0 and (a_score / q_score) < RATIO_THRESHOLD:
        return False, f"ratio {a_score}/{q_score}={a_score/q_score:.2f} < {RATIO_THRESHOLD}"
    if len(a_text) < MIN_ANSWER_CHARS:
        return False, f"answer too short ({len(a_text)} chars)"
    if len(a_text) > MAX_ANSWER_CHARS:
        return False, f"answer too long ({len(a_text)} chars)"
    return True, ""


# ── format ───────────────────────────────────────────────────────────────────

def _to_example(title: str, q_body: str, a_text: str) -> dict:
    user_content = f"{title}\n\n{q_body}".strip()
    return {
        "messages": [
            {"role": "system",    "content": _SYSTEM_PROMPT},
            {"role": "user",      "content": user_content},
            {"role": "assistant", "content": a_text},
        ]
    }


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Generate SFT training data from Stack Overflow dump")
    parser.add_argument("--max-docs",   type=int, default=5_000, help="max Q&A pairs to process")
    parser.add_argument("--min-score",  type=int, default=MIN_QUESTION_SCORE, help="min question score")
    parser.add_argument("--no-filter",  action="store_true", help="skip quality filters — write all pairs (shows how many the filter removes)")
    parser.add_argument("--out",        default="data/sft_train.jsonl", help="output path")
    args = parser.parse_args()

    # ── locate Kaggle dataset ───────────────────────────────────────────────
    from config import settings
    import kagglehub
    from kagglehub.config import set_kaggle_api_token
    set_kaggle_api_token(settings.KAGGLE_API_TOKEN)

    print("locating dataset ...")
    path = kagglehub.dataset_download("stackoverflow/pythonquestions")
    qpath = os.path.join(path, "Questions.csv")
    apath = os.path.join(path, "Answers.csv")

    # ── load ────────────────────────────────────────────────────────────────
    print("loading questions ...")
    questions = _load_questions(qpath, args.max_docs, args.min_score)
    gc.collect()

    qids = {q["id"] for q in questions}
    print("loading answers ...")
    answers = _load_answers(apath, qids)
    gc.collect()

    # ── build + filter ──────────────────────────────────────────────────────
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)

    written = 0
    rejected: dict[str, int] = {}

    with open(args.out, "w") as out_f:
        for q in questions:
            ans = answers.get(q["id"])
            if not ans:
                rejected["no_answer"] = rejected.get("no_answer", 0) + 1
                continue

            title  = _clean(q["title"])
            q_body = _clean(q["body"])
            a_text = _clean(ans["body"])

            if not args.no_filter:
                ok, reason = _passes_filter(q["score"], ans["score"], a_text)
                if not ok:
                    rejected[reason.split(" ")[0]] = rejected.get(reason.split(" ")[0], 0) + 1
                    continue

            example = _to_example(title, q_body, a_text)
            out_f.write(json.dumps(example) + "\n")
            written += 1

    # ── report ──────────────────────────────────────────────────────────────
    total = len(questions)
    print(f"\n{'─' * 50}")
    print(f"wrote {written} examples → {args.out}")
    print(f"rejected {total - written} / {total} ({(total - written) / total * 100:.0f}%)")
    if rejected:
        print("\nrejection breakdown:")
        for reason, count in sorted(rejected.items(), key=lambda x: -x[1]):
            print(f"  {count:>5}  {reason}")
    print(f"{'─' * 50}")
    print(f"\nnext: head -n 3 {args.out} | python -m json.tool")


if __name__ == "__main__":
    main()
