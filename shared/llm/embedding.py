from config import settings

from .client import get_llm_client

BATCH_SIZE = 2048

EMBEDDING_MODEL = settings.EMBEDDING_MODEL

async def embed_text(text: str) -> list[float]:
  client = get_llm_client()
  response = await client.embeddings.create(model=EMBEDDING_MODEL, input=text, dimensions=settings.EMBEDDING_DIM)
  return response.data[0].embedding


async def embed_batch_text(texts: list[str]) -> list[list[float]]:
  client = get_llm_client()
  all_embeddings = []

  for batch_start in range(0, len(texts), BATCH_SIZE):
    batch = texts[batch_start:batch_start + BATCH_SIZE]
    response = await client.embeddings.create(model=EMBEDDING_MODEL, input=batch, dimensions=settings.EMBEDDING_DIM)
    all_embeddings.extend([e.embedding for e in response.data])

  return all_embeddings