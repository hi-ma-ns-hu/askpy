"""
scripts/finetune_embeddings.py — Fine-tune a sentence-transformer on the
(query, positive, negative) pairs produced by generate_finetune_data.py.

What happens here:
  1. Load a pretrained sentence-transformer (all-MiniLM-L6-v2, 22M params, ~90MB)
  2. Wrap the JSONL pairs as a TripletDataset
  3. Train with TripletLoss — pulls (query, positive) together,
     pushes (query, negative) apart in 384-dim embedding space
  4. Save the model to ./models/AskPy-embeddings
  5. Set LOCAL_EMBEDDING_MODEL=./models/AskPy-embeddings in .env to use it

Training takes ~5–15 min on CPU for 5k pairs. NDCG@10 is logged per epoch —
watch it go up. If it plateaus after epoch 1, your negatives weren't hard enough.

Run:
  python -m scripts.finetune_embeddings
  python -m scripts.finetune_embeddings --epochs 5 --batch-size 32

Requires: pip install sentence-transformers
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


BASE_MODEL = "all-MiniLM-L6-v2"    # 22M params, 384-dim, fast on CPU
OUTPUT_DIR = "models/AskPy-embeddings"


def _load_pairs(path: str) -> tuple[list[str], list[str], list[str]]:
    queries, positives, negatives = [], [], []
    with open(path) as f:
        for line in f:
            row = json.loads(line)
            queries.append(row["query"])
            positives.append(row["positive"])
            negatives.append(row["negative"])
    return queries, positives, negatives


def main() -> None:
    parser = argparse.ArgumentParser(description="Fine-tune sentence-transformer on Q&A triplets")
    parser.add_argument("--data",       default="data/finetune_pairs.jsonl")
    parser.add_argument("--base-model", default=BASE_MODEL)
    parser.add_argument("--output",     default=OUTPUT_DIR)
    parser.add_argument("--epochs",     type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--warmup",     type=float, default=0.1,
                        help="fraction of steps used for LR warmup")
    args = parser.parse_args()

    # ── imports deferred — sentence-transformers is heavy ─────────────────────
    from sentence_transformers import SentenceTransformer, InputExample, losses
    from sentence_transformers.evaluation import TripletEvaluator
    from torch.utils.data import DataLoader

    print(f"loading base model: {args.base_model} ...")
    model = SentenceTransformer(args.base_model)

    print(f"loading pairs from {args.data} ...")
    queries, positives, negatives = _load_pairs(args.data)
    print(f"  loaded {len(queries)} triplets")

    # 90/10 train/eval split — evaluator tracks NDCG@10 per epoch
    split = int(len(queries) * 0.9)
    train_examples = [
        InputExample(texts=[q, p, n])
        for q, p, n in zip(queries[:split], positives[:split], negatives[:split])
    ]
    eval_queries    = queries[split:]
    eval_positives  = positives[split:]
    eval_negatives  = negatives[split:]

    train_dataloader = DataLoader(train_examples, shuffle=True, batch_size=args.batch_size)

    # TripletLoss: loss = max(0, margin + d(q,pos) - d(q,neg))
    # margin=0.5 means the negative must be at least 0.5 further than the positive.
    # Too small → model gets lazy. Too large → gradients vanish on easy pairs.
    loss = losses.TripletLoss(model=model, triplet_margin=0.5)

    evaluator = TripletEvaluator(
        anchors=eval_queries,
        positives=eval_positives,
        negatives=eval_negatives,
        name="AskPy-eval",
    )

    warmup_steps = int(len(train_dataloader) * args.epochs * args.warmup)
    print(f"\ntraining {args.epochs} epochs, batch={args.batch_size}, warmup={warmup_steps} steps")
    print("watch NDCG@10 — if it stops improving after epoch 1, negatives weren't hard enough\n")

    Path(args.output).mkdir(parents=True, exist_ok=True)
    model.fit(
        train_objectives=[(train_dataloader, loss)],
        evaluator=evaluator,
        epochs=args.epochs,
        warmup_steps=warmup_steps,
        output_path=args.output,
        save_best_model=True,
        show_progress_bar=True,
    )

    print(f"\nmodel saved → {args.output}")
    print(f"next steps:")
    print(f"  1. Add to .env:  LOCAL_EMBEDDING_MODEL={args.output}")
    print(f"  2. Re-ingest:    python -m scripts.ingest --max-docs 20000")
    print(f"  3. Run eval:     python -m evals.run_evals --no-cache")
    print(f"  4. Compare source_fit before vs after")


if __name__ == "__main__":
    main()
