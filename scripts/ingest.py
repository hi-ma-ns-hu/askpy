"""
scripts/ingest.py — Build the Qdrant vector index from the Stack Overflow
Python Q&A dataset (Kaggle: stackoverflow/pythonquestions).

Pipeline:
  download (kagglehub) → curate a high-signal subset → clean HTML
  → split into ~500-token chunks (with overlap) → embed dense (OpenAI 768-d)
  + sparse (BM25) → upsert to Qdrant.

Each Q&A thread is split into multiple chunks (~2000 chars each, 200-char
overlap). One Qdrant point per chunk. Point ID = question_id * 10_000 +
chunk_index, so chunks from the same thread share a recoverable parent ID.
The thread title is prepended to every chunk to anchor the embedding.

Run:
  python -m scripts.ingest --min-score 10 --max-docs 20000 --collection AskPy_qa_v2

Requires:
  OPENAI_API_KEY                              (.env)
  Kaggle auth: ~/.kaggle/kaggle.json  OR  KAGGLE_USERNAME / KAGGLE_KEY
  Qdrant: QDRANT_URL/QDRANT_API_KEY in .env, else embedded local ./index/qdrant
"""
from __future__ import annotations

import argparse
import gc
import html
import os
import re
import resource
import time

import csv
import zlib
from collections import Counter

# import pandas as pd  # ~150MB just to import; replaced with stdlib csv below
from openai import OpenAI
from fastembed import SparseTextEmbedding
from qdrant_client import models

from config import settings
from shared.storage.qdrant import get_qdrant_client, ensure_collection, DENSE, SPARSE

DATASET = "stackoverflow/pythonquestions"
CSV_ENCODING = "latin-1"          # the SO dump is latin-1, not utf-8
EMBED_BATCH = 256                 # OpenAI inputs per request
UPSERT_BATCH = 32                 # points per Qdrant upsert (small: avoids write timeout on slow connections)
CHUNK_SIZE    = 2000              # chars per chunk ≈ 500 tokens
CHUNK_OVERLAP = 200               # overlap between consecutive chunks ≈ 50 tokens


# ── text cleaning ──────────────────────────────────────────────────────────────

def clean_html(raw: str) -> str:
  if not isinstance(raw, str) or not raw:
    return ""
  text = re.sub(r"<[^>]+>", " ", html.unescape(raw))
  lines = [ln.rstrip() for ln in text.splitlines()]
  return "\n".join(ln for ln in lines if ln.strip())


# ── chunking ───────────────────────────────────────────────────────────────────

def split_text(text: str, max_chars: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
  """Split text into overlapping chunks, preferring sentence boundaries."""
  chunks, start = [], 0
  while start < len(text):
    end = min(start + max_chars, len(text))
    if end < len(text):
      # prefer to break at a sentence boundary in the second half of the window
      boundary = text.rfind(".", start + max_chars // 2, end)
      if boundary > start:
        end = boundary + 1
    chunk = text[start:end].strip()
    if chunk:
      chunks.append(chunk)
    if end >= len(text):
      break
    start = end - overlap
  return chunks


# ── dataset loading (stdlib csv — zero pandas/numpy overhead) ──────────────────

def _open_csv(path: str):
  return open(path, encoding=CSV_ENCODING, errors="replace", newline="")


def load_questions(qpath: str, min_score: int, max_docs: int, limit_csv: int | None = None) -> list[dict]:
  """Top `max_docs` questions with Score >= min_score."""
  # import pandas as pd  # old pandas version kept for reference
  keep = []
  with _open_csv(qpath) as f:
    reader = csv.DictReader(f)
    for i, row in enumerate(reader):
      if limit_csv and i >= limit_csv:
        break
      try:
        score = int(row["Score"])
      except (ValueError, KeyError):
        continue
      if score >= min_score:
        keep.append({"Id": int(row["Id"]), "Score": score, "Title": row["Title"],
                     "Body": row["Body"], "CreationDate": row.get("CreationDate", "")})
  keep.sort(key=lambda r: r["Score"], reverse=True)
  keep = keep[:max_docs]
  print(f"  questions: kept {len(keep)} (min_score={min_score}, cap={max_docs})")
  return keep


def load_top_answers(apath: str, question_ids: set[int], limit_csv: int | None = None) -> dict[int, tuple[str, int]]:
  """For each selected question, the single highest-scored answer body."""
  # import pandas as pd  # old pandas version kept for reference
  best: dict[int, tuple[str, int]] = {}
  with _open_csv(apath) as f:
    reader = csv.DictReader(f)
    for i, row in enumerate(reader):
      if limit_csv and i >= limit_csv:
        break
      try:
        parent = int(row["ParentId"])
        score = int(row["Score"])
      except (ValueError, KeyError):
        continue
      if parent in question_ids:
        cur = best.get(parent)
        if cur is None or score > cur[1]:
          best[parent] = (row["Body"], score)
  print(f"  answers: matched {len(best)} questions with an answer")
  return best


def load_tags(tpath: str, question_ids: set[int], limit_csv: int | None = None) -> dict[int, list[str]]:
  """Tag list per selected question."""
  # import pandas as pd  # old pandas version kept for reference
  tags: dict[int, list[str]] = {}
  with _open_csv(tpath) as f:
    reader = csv.DictReader(f)
    for i, row in enumerate(reader):
      if limit_csv and i >= limit_csv:
        break
      try:
        qid = int(row["Id"])
      except (ValueError, KeyError):
        continue
      if qid in question_ids:
        tags.setdefault(qid, []).append(row["Tag"])
  return tags


def build_documents(questions: list[dict], answers: dict, tags: dict, chunk_size: int = CHUNK_SIZE) -> list[dict]:
  """Split each Q&A into overlapping chunks, one dict per chunk."""
  docs = []
  for row in questions:
    ans = answers.get(row["Id"])
    if not ans:
      continue
    answer_body, answer_score = ans
    title = clean_html(row["Title"])
    body = clean_html(row["Body"])
    answer = clean_html(answer_body)
    full_text = f"Question: {title}\n\n{body}\n\nTop answer:\n{answer}"
    year = int(row["CreationDate"][:4]) if row.get("CreationDate", "")[:4].isdigit() else 0
    question_id = row["Id"]
    url = f"https://stackoverflow.com/questions/{question_id}"

    for chunk_index, chunk_text in enumerate(split_text(full_text, max_chars=chunk_size)):
      text = f"{title}\n\n{chunk_text}"
      docs.append({
        "id": question_id * 10_000 + chunk_index,
        "parent_id": question_id,
        "chunk_index": chunk_index,
        "title": title,
        "text": text,
        "score": row["Score"],
        "answer_score": answer_score,
        "tags": tags.get(question_id, []),
        "year": year,
        "url": url,
      })

  q_count = len({d["parent_id"] for d in docs})
  print(f"  documents: {q_count} Q&A threads → {len(docs)} chunks")
  return docs


# ── sparse encoding (lightweight BM25 TF; IDF handled server-side by Qdrant) ───

def sparse_vector(text: str) -> models.SparseVector:
  # from fastembed import SparseTextEmbedding; sparse_model = SparseTextEmbedding("Qdrant/bm25")
  tokens = re.findall(r"\b[a-z0-9]+\b", text.lower())
  tf = Counter(tokens)
  indices = [zlib.crc32(t.encode()) & 0x7FFF_FFFF for t in tf]
  values = [float(v) for v in tf.values()]
  return models.SparseVector(indices=indices, values=values)


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


def ingest(docs: list[dict], collection: str) -> None:
  oai = OpenAI(api_key=settings.OPENAI_API_KEY)
  sparse_model = SparseTextEmbedding("Qdrant/bm25")
  qdrant = get_qdrant_client()
  ensure_collection(qdrant, collection_name=collection)

  total = len(docs)
  for start in range(0, total, UPSERT_BATCH):
    batch = docs[start:start + UPSERT_BATCH]
    texts = [d["text"] for d in batch]

    dense = embed_dense(oai, texts)
    sparse = list(sparse_model.embed(texts))
    # sparse = [sparse_vector(t) for t in texts]  # lightweight CRC32 fallback (no fastembed)

    points = [
      models.PointStruct(
        id=d["id"],
        vector={
          DENSE: dense_vec,
          SPARSE: models.SparseVector(indices=sp.indices.tolist(), values=sp.values.tolist()),
          # SPARSE: sp,  # CRC32 fallback already returns models.SparseVector
        },
        payload={k: d[k] for k in ("title", "text", "score", "answer_score", "tags", "year", "url", "parent_id", "chunk_index")},
      )
      for d, dense_vec, sp in zip(batch, dense, sparse)
    ]
    qdrant.upsert(collection_name=collection, points=points)
    print(f"  upserted {min(start + UPSERT_BATCH, total)}/{total}")

  print(f"done — {total} chunks in collection '{collection}'")


# ── entrypoint ──────────────────────────────────────────────────────────────────

def _mb() -> float:
  return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024 / 1024


def main() -> None:
  parser = argparse.ArgumentParser(description="Ingest Stack Overflow Python Q&A into Qdrant")
  parser.add_argument("--min-score", type=int, default=10, help="minimum question score to keep")
  parser.add_argument("--max-docs", type=int, default=20_000, help="cap on number of Q&A docs")
  parser.add_argument("--collection", default=settings.QDRANT_COLLECTION, help="Qdrant collection name to write into")
  parser.add_argument("--limit-csv", type=int, default=None, help="stop reading each CSV after this many rows (dev/test only — top-scored docs may be missed)")
  parser.add_argument("--chunk-size", type=int, default=CHUNK_SIZE, help="max characters per chunk (default 2000 ≈ 500 tokens)")
  args = parser.parse_args()

  print(f"[mem] after imports: {_mb():.0f}MB", flush=True)

  import kagglehub
  from kagglehub.config import set_kaggle_api_token
  set_kaggle_api_token(settings.KAGGLE_API_TOKEN)

  print(f"downloading {DATASET} via kagglehub ...", flush=True)
  path = kagglehub.dataset_download(DATASET)
  print(f"[mem] after kagglehub: {_mb():.0f}MB", flush=True)
  qpath, apath, tpath = (os.path.join(path, f) for f in ("Questions.csv", "Answers.csv", "Tags.csv"))

  print("curating subset ...", flush=True)
  questions = load_questions(qpath, args.min_score, args.max_docs, args.limit_csv)
  print(f"[mem] after load_questions: {_mb():.0f}MB", flush=True)
  qids = {q["Id"] for q in questions}
  print(f"  selected {len(qids)} question IDs", flush=True)
  answers = load_top_answers(apath, qids, args.limit_csv)
  gc.collect()
  print(f"  answers loaded  [mem] {_mb():.0f}MB", flush=True)
  tags = load_tags(tpath, qids, args.limit_csv)
  gc.collect()
  print(f"  tags loaded  [mem] {_mb():.0f}MB", flush=True)
  print("  calling build_documents ...", flush=True)
  docs = build_documents(questions, answers, tags, chunk_size=args.chunk_size)
  del questions, answers, tags
  gc.collect()
  print(f"[mem] after build_documents: {_mb():.0f}MB", flush=True)

  if not docs:
    raise SystemExit("no documents to ingest — try a lower --min-score")

  print(f"embedding + upserting {len(docs)} chunks into '{args.collection}' ...")
  ingest(docs, collection=args.collection)


if __name__ == "__main__":
  main()
