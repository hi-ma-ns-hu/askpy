"""
scripts/generate_finetune_data.py — Build contrastive training pairs for
fine-tuning a sentence-transformer embedding model.

Output: data/finetune_pairs.jsonl — one JSON line per training example:

  {"query": "how do I sort a dict by value?",
   "positive": "You can use sorted() with key=lambda: ...",
   "negative": "To reverse a list in Python, use list.reverse()..."}

What "contrastive" means:
  The model learns by seeing (query, positive, negative) triples.
  It's trained to make embed(query) ↔ embed(positive) close in vector space,
  and embed(query) ↔ embed(negative) far apart.

What makes a "hard" negative vs an "easy" negative:
  Easy negative: "What is the capital of France?" — trivially unrelated.
                 The model already knows this is far from a Python question.
                 Training on easy negatives teaches the model nothing new.

  Hard negative: "How do I sort a list by the second element of a tuple?"
                 — same domain, same intent, but answers a different sub-question.
                 Forcing the model to distinguish these is where learning happens.

  This script uses TF-IDF similarity to find hard negatives: questions that
  share many tokens with the query (same topic) but have a different top answer.
  That's the hardest thing to tell apart — exactly what you want.

Run:
  python -m scripts.generate_finetune_data --max-docs 5000
  head -n 2 data/finetune_pairs.jsonl | python -m json.tool
"""
from __future__ import annotations

import argparse
import csv
import gc
import html
import json
import math
import os
import re
from collections import Counter
from pathlib import Path


CSV_ENCODING = "latin-1"
MIN_QUESTION_SCORE = 5
MIN_ANSWER_SCORE   = 3
MIN_ANSWER_CHARS   = 150
MAX_PAIRS          = 10_000   # cap output — more isn't always better


# ── text cleaning ─────────────────────────────────────────────────────────────

def _clean(raw: str) -> str:
    if not isinstance(raw, str) or not raw:
        return ""
    text = re.sub(r"<[^>]+>", " ", html.unescape(raw))
    lines = [ln.rstrip() for ln in text.splitlines()]
    return "\n".join(ln for ln in lines if ln.strip())


# ── CSV loaders ───────────────────────────────────────────────────────────────

def _open(path: str):
    return open(path, encoding=CSV_ENCODING, errors="replace", newline="")


def _load_qa(qpath: str, apath: str, max_docs: int) -> list[dict]:
    """Load questions + their best answer into a single list of dicts."""
    # load questions
    questions: list[dict] = []
    with _open(qpath) as f:
        for row in csv.DictReader(f):
            try:
                score = int(row["Score"])
            except (ValueError, KeyError):
                continue
            if score >= MIN_QUESTION_SCORE:
                questions.append({
                    "id":    int(row["Id"]),
                    "score": score,
                    "title": _clean(row.get("Title", "")),
                    "body":  _clean(row.get("Body", "")),
                })
    questions.sort(key=lambda r: r["score"], reverse=True)
    questions = questions[:max_docs]
    print(f"  questions loaded: {len(questions)}")

    qids = {q["id"] for q in questions}

    # load best answer per question
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
                    best[parent] = {"score": score, "body": _clean(row.get("Body", ""))}

    docs = []
    for q in questions:
        ans = best.get(q["id"])
        if not ans:
            continue
        if ans["score"] < MIN_ANSWER_SCORE:
            continue
        if len(ans["body"]) < MIN_ANSWER_CHARS:
            continue
        docs.append({
            "query":    q["title"],
            "positive": ans["body"],
            "q_score":  q["score"],
            "a_score":  ans["score"],
        })

    print(f"  QA pairs after filter: {len(docs)}")
    return docs


# ── TF-IDF hard-negative mining ───────────────────────────────────────────────
#
# Why TF-IDF for negatives:
#   We want negatives that LOOK similar to the query (same vocabulary, same topic)
#   but answer a different question. TF-IDF overlap is a cheap proxy for this —
#   high term overlap = same domain, but different answer = good hard negative.
#
# Alternative: embed everything with a pretrained model and find nearest neighbours
# that aren't the true positive. More accurate, but requires ~1GB model + GPU.
# TF-IDF is good enough to start — if source_fit doesn't improve after training,
# switch to embedding-based negative mining.

def _tokenize(text: str) -> list[str]:
    return re.findall(r"\b[a-z0-9]+\b", text.lower())


def _build_idf(docs: list[dict]) -> dict[str, float]:
    n = len(docs)
    df: Counter = Counter()
    for d in docs:
        for tok in set(_tokenize(d["query"])):
            df[tok] += 1
    return {tok: math.log(n / (count + 1)) for tok, count in df.items()}


def _tfidf(tokens: list[str], idf: dict[str, float]) -> dict[str, float]:
    tf = Counter(tokens)
    total = len(tokens) or 1
    return {t: (tf[t] / total) * idf.get(t, 0) for t in tf}


def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
    keys = set(a) & set(b)
    dot = sum(a[k] * b[k] for k in keys)
    norm_a = math.sqrt(sum(v * v for v in a.values()))
    norm_b = math.sqrt(sum(v * v for v in b.values()))
    return dot / (norm_a * norm_b + 1e-9)


def mine_hard_negatives(docs: list[dict], pairs_per_doc: int = 2) -> list[dict]:
    """For each doc, find the most similar query whose answer is different."""
    print("  building TF-IDF index for hard-negative mining ...")
    idf = _build_idf(docs)
    vecs = [_tfidf(_tokenize(d["query"]), idf) for d in docs]

    pairs = []
    sample_step = max(1, len(docs) // MAX_PAIRS)   # subsample if corpus is large

    for i, (doc, qvec) in enumerate(zip(docs, vecs)):
        if i % sample_step != 0:
            continue

        # Score all other docs by TF-IDF similarity to this query
        scored = []
        for j, (other, ovec) in enumerate(zip(docs, vecs)):
            if i == j:
                continue
            sim = _cosine(qvec, ovec)
            scored.append((sim, j))
        scored.sort(reverse=True)

        # Take the top-K as hard negatives (high similarity = hard)
        added = 0
        for _, j in scored:
            if added >= pairs_per_doc:
                break
            neg = docs[j]["positive"]
            # Skip if the negative answer is very similar to the positive
            # (same thread, different phrasing — not a useful negative)
            if neg[:100] == doc["positive"][:100]:
                continue
            pairs.append({
                "query":    doc["query"],
                "positive": doc["positive"],
                "negative": neg,
            })
            added += 1

        if len(pairs) >= MAX_PAIRS:
            break

    print(f"  mined {len(pairs)} hard-negative pairs")
    return pairs


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Generate contrastive embedding fine-tuning pairs")
    parser.add_argument("--max-docs", type=int, default=5_000)
    parser.add_argument("--out", default="data/finetune_pairs.jsonl")
    args = parser.parse_args()

    from config import settings
    import kagglehub
    from kagglehub.config import set_kaggle_api_token
    set_kaggle_api_token(settings.KAGGLE_API_TOKEN)

    print("locating dataset ...")
    path = kagglehub.dataset_download("stackoverflow/pythonquestions")
    qpath = os.path.join(path, "Questions.csv")
    apath = os.path.join(path, "Answers.csv")

    print("loading Q&A pairs ...")
    docs = _load_qa(qpath, apath, args.max_docs)
    gc.collect()

    pairs = mine_hard_negatives(docs)

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w") as f:
        for p in pairs:
            f.write(json.dumps(p) + "\n")

    print(f"\nwrote {len(pairs)} pairs → {args.out}")
    print(f"next: python -m scripts.finetune_embeddings")


if __name__ == "__main__":
    main()
