'''
shared/storage/qdrant.py — Qdrant vector store: client + collection schema.

One collection holds both a dense vector (OpenAI 768-d, cosine) and a sparse
vector (BM25) per point, so the retriever can run hybrid search server-side.
Payload indexes on tags/score/year make metadata pre-filtering fast.

Connection mode is chosen from settings:
  QDRANT_URL set   → remote cluster (Qdrant Cloud free tier)
  QDRANT_URL empty → embedded local mode at ./index/qdrant (no server needed)

The sync client is used by the ingestion script; the async client by the API.
'''
from __future__ import annotations

from functools import lru_cache

from qdrant_client import QdrantClient, AsyncQdrantClient, models

from config import settings

# Named vectors inside the collection
DENSE = "dense"
SPARSE = "sparse"

LOCAL_PATH = "./index/qdrant"


@lru_cache
def get_qdrant_client() -> QdrantClient:
  '''Sync client — used by scripts/ingest.py.'''
  if settings.QDRANT_URL:
    return QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY or None)
  return QdrantClient(path=LOCAL_PATH)


@lru_cache
def get_async_qdrant_client() -> AsyncQdrantClient:
  '''Async client — used by the retriever in the request path.'''
  if settings.QDRANT_URL:
    return AsyncQdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY or None)
  return AsyncQdrantClient(path=LOCAL_PATH)


def ensure_collection(client: QdrantClient, dim: int = None) -> None:
  '''
  Create the collection (idempotent) with dense + sparse vectors and the
  payload indexes used for filtering. Safe to call on every ingest run.
  '''
  dim = dim or settings.EMBEDDING_DIM
  name = settings.QDRANT_COLLECTION

  if not client.collection_exists(name):
    client.create_collection(
      collection_name=name,
      vectors_config={DENSE: models.VectorParams(size=dim, distance=models.Distance.COSINE)},
      # IDF modifier lets Qdrant compute BM25 IDF weighting server-side
      sparse_vectors_config={SPARSE: models.SparseVectorParams(modifier=models.Modifier.IDF)},
    )

  # Payload indexes for metadata pre-filtering (idempotent).
  # Local embedded Qdrant ignores indexes (filtering still works), so only
  # create them against a real server.
  if settings.QDRANT_URL:
    for field, schema in (
      ("tags", models.PayloadSchemaType.KEYWORD),
      ("score", models.PayloadSchemaType.INTEGER),
      ("year", models.PayloadSchemaType.INTEGER),
    ):
      try:
        client.create_payload_index(name, field_name=field, field_schema=schema)
      except Exception:
        pass  # already exists
