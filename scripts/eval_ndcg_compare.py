"""
Compare NDCG@10 for base vs fine-tuned sentence-transformer — no re-ingestion needed.

Approach:
  1. Load all chunk texts + parent_ids from Qdrant (payload only, no stored vectors)
  2. Encode every chunk with BOTH models in-memory
  3. For each sampled question title: encode → cosine similarity over all chunks → top-10 → NDCG@10
  4. Print before vs after

This is the standard production way to evaluate an embedding model change before
committing to a full re-ingestion.

Run:
  python -m scripts.eval_ndcg_compare --n 200
"""
import math
import random
import time

import numpy as np
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

BASE_MODEL = "all-MiniLM-L6-v2"
FINETUNED_MODEL = "./models/vidhya-embeddings"


def ndcg_at_k(ranked_ids: list, relevant_ids: set, k: int = 10) -> float:
    dcg = sum(
        1.0 / math.log2(rank + 1)
        for rank, cid in enumerate(ranked_ids[:k], start=1)
        if cid in relevant_ids
    )
    n_relevant = min(len(relevant_ids), k)
    idcg = sum(1.0 / math.log2(i + 1) for i in range(1, n_relevant + 1))
    return dcg / idcg if idcg > 0 else 0.0


def encode_all(model: SentenceTransformer, texts: list[str]) -> np.ndarray:
    """Batch-encode and L2-normalise so dot product == cosine similarity."""
    vecs = model.encode(texts, batch_size=64, show_progress_bar=True, convert_to_numpy=True)
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    return vecs / np.maximum(norms, 1e-9)


def eval_model(
    model: SentenceTransformer,
    chunk_ids: list,
    chunk_matrix: np.ndarray,
    id_to_parent: dict,
    sampled: list[tuple],
    k: int = 10,
) -> float:
    scores = []
    for i, (question_id, title) in enumerate(sampled):
        relevant_ids = {cid for cid, pid in id_to_parent.items() if pid == question_id}

        q_vec = model.encode(title, convert_to_numpy=True)
        q_vec = q_vec / max(np.linalg.norm(q_vec), 1e-9)

        sims = chunk_matrix @ q_vec          # (N,) cosine similarities
        top_k_idx = np.argpartition(sims, -k)[-k:]
        top_k_idx = top_k_idx[np.argsort(sims[top_k_idx])[::-1]]
        retrieved = [chunk_ids[i] for i in top_k_idx]

        ndcg = ndcg_at_k(retrieved, relevant_ids, k=k)
        scores.append(ndcg)
        print(f"  [{i+1}/{len(sampled)}] {title[:55]!r} → {ndcg:.3f}")

    return sum(scores) / len(scores)


def main(n: int = 200) -> None:
    from config import settings
    client = QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY)

    print("loading chunks from Qdrant ...")
    all_points, _ = client.scroll(
        collection_name=settings.QDRANT_COLLECTION,
        limit=10_000,
        with_payload=["parent_id", "title", "text"],
        with_vectors=False,
    )
    print(f"  loaded {len(all_points)} chunks")

    chunk_ids = [p.id for p in all_points]
    chunk_texts = [p.payload["text"] for p in all_points]
    id_to_parent = {p.id: p.payload["parent_id"] for p in all_points}

    # one entry per unique question
    seen = {}
    for p in all_points:
        pid = p.payload["parent_id"]
        if pid not in seen:
            seen[pid] = p.payload["title"]
    sampled = random.sample(list(seen.items()), min(n, len(seen)))

    results = {}
    for label, model_path in [("base", BASE_MODEL), ("fine-tuned", FINETUNED_MODEL)]:
        print(f"\n{'='*60}")
        print(f"model: {label}  ({model_path})")
        print(f"{'='*60}")

        model = SentenceTransformer(model_path)

        print("encoding all chunks ...")
        t0 = time.perf_counter()
        chunk_matrix = encode_all(model, chunk_texts)
        print(f"  done in {time.perf_counter()-t0:.1f}s  shape={chunk_matrix.shape}")

        print(f"evaluating {len(sampled)} queries ...")
        score = eval_model(model, chunk_ids, chunk_matrix, id_to_parent, sampled)
        results[label] = score
        print(f"\n  NDCG@10 ({label}): {score:.4f}")

    print(f"\n{'='*60}")
    print(f"RESULTS")
    print(f"{'='*60}")
    print(f"  base model ({BASE_MODEL}):   {results['base']:.4f}")
    print(f"  fine-tuned model:              {results['fine-tuned']:.4f}")
    delta = results["fine-tuned"] - results["base"]
    print(f"  delta:                         {delta:+.4f}")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--n", type=int, default=200)
    args = p.parse_args()
    main(args.n)
