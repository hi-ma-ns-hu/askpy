"""
Measure NDCG@10 for the retriever.

Gold set: for each sampled SO question, the relevant chunk is any chunk
with payload.parent_id == question_id (chunks from that question's answer).

Run: python -m scripts.eval_ndcg --n 200
"""
import asyncio, math, random, time
from qdrant_client import QdrantClient
from shared import embed_text

async def get_embedding(text: str):
  return await embed_text(text)

def _retry(fn, retries=3, delay=2.0):
  for attempt in range(retries):
    try:
      return fn()
    except Exception as e:
      if attempt == retries - 1:
        raise
      print(f"    retrying after error: {e}")
      time.sleep(delay * (attempt + 1))

def ndcg_at_k(retrieved_ids: list[int], relevant_ids: set[int], k: int = 10) -> float:
  dcg = 0.0
  for rank, chunk_id in enumerate(retrieved_ids[:k], start=1):
    if chunk_id in relevant_ids:
      dcg += 1.0 / math.log2(rank + 1)
  # IDCG: best possible DCG given how many relevant docs exist
  n_relevant = min(len(relevant_ids), k)
  idcg = sum(1.0 / math.log2(i + 1) for i in range(1, n_relevant + 1))
  return dcg / idcg if idcg > 0 else 0.0

async def main(n: int = 200):
  from config import settings
  client = QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY)

  all_points, _ = client.scroll(collection_name=settings.QDRANT_COLLECTION, limit=10_000, with_payload=['parent_id', 'title'], with_vectors=False)

  # one entry per question
  seen = dict()
  for p in all_points:
    pid = p.payload['parent_id']
    if pid not in seen:
      seen[pid] = p.payload['title']
  
  sampled = random.sample(list(seen.items()), min(n, len(seen)))

  # for each question, find all chunks ids
  scores = list()
  for question_id, title in sampled:
    gold_chunks, _ = _retry(lambda: client.scroll(
        collection_name=settings.QDRANT_COLLECTION,
        scroll_filter={'must': [{'key': 'parent_id', 'match': {'value': question_id}}]},
        with_payload=False,
        with_vectors=False,
    ))
    relevant_ids = {p.id for p in gold_chunks}

    # embed the question title and search the dense vector index
    vector = await get_embedding(title)
    results = _retry(lambda: client.query_points(
        collection_name=settings.QDRANT_COLLECTION,
        query=vector,
        using="dense",
        limit=10,
        with_payload=False,
    ).points)
    retrieved_ids = [r.id for r in results]

    ndcg = ndcg_at_k(retrieved_ids, relevant_ids, k=10)
    scores.append(ndcg)
    print(f"  [{len(scores)}/{n}] {title[:60]!r} → {ndcg:.3f}")
    time.sleep(0.15)  # avoid rate-limiting on Qdrant Cloud free tier

  print(f"\nNDCG@10 over {len(scores)} queries: {sum(scores)/len(scores):.4f}")


if __name__ == '__main__':
  import argparse
  p = argparse.ArgumentParser()
  p.add_argument('--n', type=int, default=200)
  args = p.parse_args()
  asyncio.run(main(args.n))