"""
scripts/ingest.py — Build the Qdrant vector index from the Stack Overflow
Python Q&A dataset (Kaggle: stackoverflow/pythonquestions).

Pipeline:
  download (kagglehub) → curate a high-signal subset → clean HTML
  → embed dense (OpenAI 768-d) + sparse (BM25) → upsert to Qdrant.

Each point is one self-contained Q&A (question + its top-voted answer), with
metadata (tags, score, year, url) stored as payload for pre-filtering.

Run:
  python -m scripts.ingest --min-score 10 --max-docs 20000

Requires:
  OPENAI_API_KEY                              (.env)
  Kaggle auth: ~/.kaggle/kaggle.json  OR  KAGGLE_USERNAME / KAGGLE_KEY
  Qdrant: QDRANT_URL/QDRANT_API_KEY in .env, else embedded local ./index/qdrant
"""
from __future__ import annotations

import argparse
import html
import os
import time

import pandas as pd
from bs4 import BeautifulSoup
from openai import OpenAI
from fastembed import SparseTextEmbedding
from qdrant_client import models

from config import settings
from shared.storage.qdrant import get_qdrant_client, ensure_collection, DENSE, SPARSE

DATASET = "stackoverflow/pythonquestions"
CSV_ENCODING = "latin-1"          # the SO dump is latin-1, not utf-8
EMBED_BATCH = 256                 # OpenAI inputs per request
UPSERT_BATCH = 256                # points per Qdrant upsert
MAX_CHARS = 6000                  # truncate very long Q&A before embedding


# ── text cleaning ──────────────────────────────────────────────────────────────

def clean_html(raw: str) -> str:
  """Strip HTML tags but keep code/text content and basic structure."""
  if not isinstance(raw, str) or not raw:
    return ""
  text = BeautifulSoup(html.unescape(raw), "lxml").get_text("\n")
  lines = [ln.rstrip() for ln in text.splitlines()]
  return "\n".join(ln for ln in lines if ln.strip())


# ── dataset loading (chunked, memory-bounded) ───────────────────────────────────

def load_questions(qpath: str, min_score: int, max_docs: int) -> pd.DataFrame:
  """Top `max_docs` questions with Score >= min_score, read in chunks."""
  keep = []
  for chunk in pd.read_csv(qpath, encoding=CSV_ENCODING, usecols=["Id", "Score", "Title", "Body", "CreationDate"], chunksize=200_000):
    keep.append(chunk[chunk["Score"] >= min_score])
  questions = pd.concat(keep, ignore_index=True)
  questions = questions.nlargest(max_docs, "Score").reset_index(drop=True)
  print(f"  questions: kept {len(questions)} (min_score={min_score}, cap={max_docs})")
  return questions


def load_top_answers(apath: str, question_ids: set[int]) -> dict[int, tuple[str, int]]:
  """For each selected question, the single highest-scored answer body."""
  best: dict[int, tuple[str, int]] = {}
  for chunk in pd.read_csv(apath, encoding=CSV_ENCODING, usecols=["ParentId", "Score", "Body"], chunksize=200_000):
    chunk = chunk[chunk["ParentId"].isin(question_ids)]
    for parent, score, body in zip(chunk["ParentId"], chunk["Score"], chunk["Body"]):
      cur = best.get(parent)
      if cur is None or score > cur[1]:
        best[parent] = (body, int(score))
  print(f"  answers: matched {len(best)} questions with an answer")
  return best


def load_tags(tpath: str, question_ids: set[int]) -> dict[int, list[str]]:
  """tag list per selected question."""
  tags: dict[int, list[str]] = {}
  for chunk in pd.read_csv(tpath, encoding=CSV_ENCODING, usecols=["Id", "Tag"], chunksize=500_000):
    chunk = chunk[chunk["Id"].isin(question_ids)]
    for qid, tag in zip(chunk["Id"], chunk["Tag"]):
      tags.setdefault(qid, []).append(str(tag))
  return tags


def build_documents(questions, answers, tags) -> list[dict]:
  """Join into self-contained Q&A documents ready for embedding."""
  docs = []
  for row in questions.itertuples(index=False):
    ans = answers.get(row.Id)
    if not ans:
      continue  # skip questions with no answer — nothing to ground on
    answer_body, answer_score = ans
    title = clean_html(row.Title)
    body = clean_html(row.Body)
    answer = clean_html(answer_body)
    text = f"Question: {title}\n\n{body}\n\nTop answer:\n{answer}"[:MAX_CHARS]
    year = int(str(row.CreationDate)[:4]) if pd.notna(row.CreationDate) else 0
    docs.append({
      "id": int(row.Id),
      "title": title,
      "text": text,
      "score": int(row.Score),
      "answer_score": answer_score,
      "tags": tags.get(row.Id, []),
      "year": year,
      "url": f"https://stackoverflow.com/questions/{int(row.Id)}",
    })
  print(f"  documents: built {len(docs)} Q&A docs (with answers)")
  return docs


# ── embedding + upsert ──────────────────────────────────────────────────────────

def embed_dense(client: OpenAI, texts: list[str]) -> list[list[float]]:
  out = []
  for start in range(0, len(texts), EMBED_BATCH):
    batch = texts[start:start + EMBED_BATCH]
    for attempt in range(5):
      try:
        resp = client.embeddings.create(model=settings.EMBEDDING_MODEL, input=batch, dimensions=settings.EMBEDDING_DIM)
        out.extend([d.embedding for d in resp.data])
        break
      except Exception as e:
        wait = 2 ** attempt
        print(f"    embed retry {attempt + 1} after error ({e}); sleeping {wait}s")
        time.sleep(wait)
    else:
      raise RuntimeError("dense embedding failed after retries")
  return out


def ingest(docs: list[dict]) -> None:
  oai = OpenAI(api_key=settings.OPENAI_API_KEY)
  sparse_model = SparseTextEmbedding("Qdrant/bm25")
  qdrant = get_qdrant_client()
  ensure_collection(qdrant)

  total = len(docs)
  for start in range(0, total, UPSERT_BATCH):
    batch = docs[start:start + UPSERT_BATCH]
    texts = [d["text"] for d in batch]

    dense = embed_dense(oai, texts)
    sparse = list(sparse_model.embed(texts))

    points = [
      models.PointStruct(
        id=d["id"],
        vector={
          DENSE: dense_vec,
          SPARSE: models.SparseVector(indices=sp.indices.tolist(), values=sp.values.tolist()),
        },
        payload={k: d[k] for k in ("title", "text", "score", "answer_score", "tags", "year", "url")},
      )
      for d, dense_vec, sp in zip(batch, dense, sparse)
    ]
    qdrant.upsert(collection_name=settings.QDRANT_COLLECTION, points=points)
    print(f"  upserted {min(start + UPSERT_BATCH, total)}/{total}")

  print(f"done — {total} points in collection '{settings.QDRANT_COLLECTION}'")


# ── entrypoint ──────────────────────────────────────────────────────────────────

def main() -> None:
  parser = argparse.ArgumentParser(description="Ingest Stack Overflow Python Q&A into Qdrant")
  parser.add_argument("--min-score", type=int, default=10, help="minimum question score to keep")
  parser.add_argument("--max-docs", type=int, default=20_000, help="cap on number of Q&A docs")
  args = parser.parse_args()

  import kagglehub
  from kagglehub.config import set_kaggle_api_token
  set_kaggle_api_token(settings.KAGGLE_API_TOKEN)

  print(f"downloading {DATASET} via kagglehub ...")
  path = kagglehub.dataset_download(DATASET)
  qpath, apath, tpath = (os.path.join(path, f) for f in ("Questions.csv", "Answers.csv", "Tags.csv"))

  print("curating subset ...")
  questions = load_questions(qpath, args.min_score, args.max_docs)
  qids = set(questions["Id"].tolist())
  answers = load_top_answers(apath, qids)
  tags = load_tags(tpath, qids)
  docs = build_documents(questions, answers, tags)

  if not docs:
    raise SystemExit("no documents to ingest — try a lower --min-score")

  print(f"embedding + upserting {len(docs)} docs ...")
  ingest(docs)


if __name__ == "__main__":
  main()
