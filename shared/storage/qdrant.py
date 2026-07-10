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
    return QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY or None, timeout=60)
  return QdrantClient(path=LOCAL_PATH)


@lru_cache
def get_async_qdrant_client() -> AsyncQdrantClient:
  '''Async client — used by the retriever in the request path.'''
  if settings.QDRANT_URL:
    return AsyncQdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY or None)
  return AsyncQdrantClient(path=LOCAL_PATH)


def ensure_collection(client: QdrantClient, dim: int = None, collection_name: str = None) -> None:
  '''
  Create the collection (idempotent) with dense + sparse vectors and the
  payload indexes used for filtering. Safe to call on every ingest run.

  ── Scaling to distributed Qdrant ────────────────────────────────────────────
  When a single node approaches ~5M vectors at 768-dim (~15GB RAM), switch to
  a distributed cluster. shard_number and replication_factor are set at
  collection creation — they cannot be changed after the fact without migrating.

  Current single-node config (no sharding args → Qdrant defaults to 1 shard, 1 replica):
    client.create_collection(
        collection_name=name,
        vectors_config={...},
    )

  Distributed config for ~20M vectors across 4 nodes:
    client.create_collection(
        collection_name=name,
        vectors_config={...},
        shard_number=4,        # data split across 4 shards (one shard per node is typical)
        replication_factor=2,  # each shard has 2 copies — survives 1 node failure
    )

  Rule of thumb:
    shard_number  = number of nodes (each node owns one shard)
    replication_factor = 2 for production (1 failure tolerance), 1 for dev/staging

  A Qdrant node holds ~5M dense 768-dim vectors comfortably in 16GB RAM.
  At 20M vectors: 4 shards × 5M each. Each shard replicated twice = 8 shard
  instances total across your cluster, so you need ≥4 nodes (2 replicas × 4 shards
  can pack onto 4 nodes with 2 shard replicas per node).
  ─────────────────────────────────────────────────────────────────────────────
  '''
  dim = dim or settings.EMBEDDING_DIM
  name = collection_name or settings.QDRANT_COLLECTION

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
