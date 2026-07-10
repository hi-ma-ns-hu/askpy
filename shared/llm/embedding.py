from __future__ import annotations

import asyncio

from config import settings
from .client import get_llm_client

BATCH_SIZE = 2048
EMBEDDING_MODEL = settings.EMBEDDING_MODEL

# Matryoshka first-pass dimension. Must be ≤ EMBEDDING_DIM.
# OpenAI text-embedding-3-small: first N dims are a valid sub-space,
# so 256-dim vectors rank almost as well as 768-dim at 1/3 the cost.
MATRYOSHKA_DIM = 256

_local_model = None   # lazy singleton — sentence-transformer is ~90MB to load


def _get_local_model():
    global _local_model
    if _local_model is None:
        from sentence_transformers import SentenceTransformer
        _local_model = SentenceTransformer(settings.LOCAL_EMBEDDING_MODEL)
    return _local_model


async def embed_text(text: str, dimensions: int | None = None) -> list[float]:
  """Embed a single text. dimensions defaults to settings.EMBEDDING_DIM (768).

  When LOCAL_EMBEDDING_MODEL is set, uses the fine-tuned sentence-transformer
  instead of the OpenAI API. Note: local model output is 384-dim (all-MiniLM),
  not 768-dim — re-ingest required when switching between the two.
  """
  if settings.LOCAL_EMBEDDING_MODEL:
      model = _get_local_model()
      vec = await asyncio.to_thread(model.encode, text)
      return vec.tolist()

  client = get_llm_client()
  response = await client.embeddings.create(
    model=EMBEDDING_MODEL,
    input=text,
    dimensions=dimensions or settings.EMBEDDING_DIM,
  )
  return response.data[0].embedding


async def embed_twostage(text: str) -> tuple[list[float], list[float]]:
  """Return (small, full) embeddings in one parallel round-trip.

  small — MATRYOSHKA_DIM (256) dims: cheap first pass for broad ANN recall.
  full  — settings.EMBEDDING_DIM (768) dims: precise re-scoring of top-N.

  Two API calls fire concurrently so latency ≈ max(t_small, t_full) not their sum.
  """
  small, full = await asyncio.gather(
    embed_text(text, dimensions=MATRYOSHKA_DIM),
    embed_text(text, dimensions=settings.EMBEDDING_DIM),
  )
  return small, full


async def embed_batch_text(texts: list[str]) -> list[list[float]]:
  client = get_llm_client()
  all_embeddings = []

  for batch_start in range(0, len(texts), BATCH_SIZE):
    batch = texts[batch_start:batch_start + BATCH_SIZE]
    response = await client.embeddings.create(model=EMBEDDING_MODEL, input=batch, dimensions=settings.EMBEDDING_DIM)
    all_embeddings.extend([e.embedding for e in response.data])

  return all_embeddings