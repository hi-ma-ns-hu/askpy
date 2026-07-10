"""
scripts/generate_dpo_data.py — Build a DPO (Direct Preference Optimization)
training dataset from Stack Overflow Q&A pairs.

Output: data/dpo_train.jsonl — one JSON line per preference pair:

  {
    "prompt":   [{"role": "user", "content": "<question>"}],
    "chosen":   [{"role": "assistant", "content": "<high-score answer>"}],
    "rejected": [{"role": "assistant", "content": "<lower-score answer>"}],
    "score_gap": 12
  }

How this differs from SFT data:
  SFT: (question, good_answer) — teaches the model WHAT to say
  DPO: (question, good_answer, bad_answer) — teaches the model STYLE PREFERENCE
       The model already knows facts from SFT. DPO teaches it to prefer direct,
       code-first, non-hedging answers over vague, verbose, hedge-y ones.

Quality filters:
  - Both answers must have score >= MIN_ANSWER_SCORE
  - Score gap must be >= MIN_SCORE_GAP (forces real preference signal)
  - chosen answer must have code (code-first is what we're teaching)
  - rejected answer must NOT have code, OR have much lower score

Run:
  python -m scripts.generate_dpo_data --max-docs 5000
  head -n 2 data/dpo_train.jsonl | python -m json.tool
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

CSV_ENCODING = "latin-1"

MIN_QUESTION_SCORE = 5
MIN_ANSWER_SCORE   = 2     # lower than SFT — rejected answers are supposed to be meh
MIN_SCORE_GAP      = 5     # chosen must beat rejected by at least this many upvotes
MIN_ANSWER_CHARS   = 100
MAX_ANSWER_CHARS   = 2000
MAX_PAIRS          = 5_000


def _clean(raw: str) -> str:
    if not isinstance(raw, str) or not raw:
        return ""
    text = re.sub(r"<[^>]+>", " ", html.unescape(raw))
    lines = [ln.rstrip() for ln in text.splitlines()]
    return "\n".join(ln for ln in lines if ln.strip())


def _has_code(text: str) -> bool:
    return "    " in text or "```" in text or "()" in text or "import " in text


def _open(path: str):
    return open(path, encoding=CSV_ENCODING, errors="replace", newline="")


def _load_questions(path: str, max_docs: int) -> dict[int, dict]:
    questions = {}
    with _open(path) as f:
        for row in csv.DictReader(f):
            try:
                score = int(row["Score"])
            except (ValueError, KeyError):
                continue
            if score >= MIN_QUESTION_SCORE:
                questions[int(row["Id"])] = {
                    "title": _clean(row.get("Title", "")),
                    "score": score,
                }
    # Keep top-scored questions (more likely to have multiple good answers)
    sorted_ids = sorted(questions, key=lambda i: questions[i]["score"], reverse=True)
    return {i: questions[i] for i in sorted_ids[:max_docs]}


def _load_answers(path: str, qids: set[int]) -> dict[int, list[dict]]:
    """Load all answers for each question, so we can pick chosen vs rejected."""
    answers: dict[int, list[dict]] = {}
    with _open(path) as f:
        for row in csv.DictReader(f):
            try:
                parent = int(row["ParentId"])
                score  = int(row["Score"])
            except (ValueError, KeyError):
                continue
            if parent not in qids:
                continue
            if score < MIN_ANSWER_SCORE:
                continue
            body = _clean(row.get("Body", ""))
            if len(body) < MIN_ANSWER_CHARS or len(body) > MAX_ANSWER_CHARS:
                continue
            answers.setdefault(parent, []).append({"score": score, "body": body})
    return answers


def _build_pairs(questions: dict[int, dict], answers: dict[int, list[dict]]) -> list[dict]:
    pairs = []
    for qid, q in questions.items():
        ans_list = answers.get(qid)
        if not ans_list or len(ans_list) < 2:
            continue

        ans_list.sort(key=lambda a: a["score"], reverse=True)
        chosen   = ans_list[0]
        rejected = ans_list[-1]   # lowest-scored answer for this question

        gap = chosen["score"] - rejected["score"]
        if gap < MIN_SCORE_GAP:
            continue
        if not _has_code(chosen["body"]):
            continue   # chosen must demonstrate code — that's the style we're teaching

        pairs.append({
            "prompt":    [{"role": "user", "content": q["title"]}],
            "chosen":    [{"role": "assistant", "content": chosen["body"]}],
            "rejected":  [{"role": "assistant", "content": rejected["body"]}],
            "score_gap": gap,
        })

        if len(pairs) >= MAX_PAIRS:
            break

    return pairs


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate DPO preference pairs from Stack Overflow")
    parser.add_argument("--max-docs", type=int, default=5_000)
    parser.add_argument("--out", default="data/dpo_train.jsonl")
    args = parser.parse_args()

    from config import settings
    import kagglehub
    from kagglehub.config import set_kaggle_api_token
    set_kaggle_api_token(settings.KAGGLE_API_TOKEN)

    print("locating dataset ...")
    path = kagglehub.dataset_download("stackoverflow/pythonquestions")
    qpath = os.path.join(path, "Questions.csv")
    apath = os.path.join(path, "Answers.csv")

    print("loading questions ...")
    questions = _load_questions(qpath, args.max_docs)
    print(f"  loaded {len(questions)} questions")

    print("loading answers ...")
    answers = _load_answers(apath, set(questions.keys()))
    questions_with_multiple = sum(1 for qid in questions if len(answers.get(qid, [])) >= 2)
    print(f"  {questions_with_multiple} questions have ≥2 answers (needed for preference pairs)")
    gc.collect()

    print("building preference pairs ...")
    pairs = _build_pairs(questions, answers)

    if not pairs:
        print("no pairs found — try lowering --min-score-gap or --max-docs")
        return

    gaps = [p["score_gap"] for p in pairs]
    print(f"\nstats:")
    print(f"  pairs: {len(pairs)}")
    print(f"  avg score gap: {sum(gaps)/len(gaps):.1f}")
    print(f"  min gap: {min(gaps)}, max gap: {max(gaps)}")

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w") as f:
        for p in pairs:
            f.write(json.dumps(p) + "\n")

    print(f"\nwrote {len(pairs)} pairs → {args.out}")
    print(f"next: python -m scripts.finetune_dpo")


if __name__ == "__main__":
    main()
