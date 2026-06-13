'''
shared/storage/redis.py — Shared async Redis pool.

Initialized once at module load, closed on app shutdown.
Never call Redis.from_url() elsewhere — import from here instead.

Usage in FastAPI route handlers (via Depends):
  from shared.storage import RedisClient
  @router.get("/example")
  async def example(r: RedisClient):
    await r.set("key", "value")

Usage in Celery tasks / agents (direct pool):
  from shared.storage import redis
  await redis.get("key")
'''
from __future__ import annotations

from typing import Annotated, AsyncGenerator

from fastapi import Depends
from redis.asyncio import Redis

from config import settings


# None when REDIS_URL is unset — the app then runs cache-less.
redis: Redis | None = Redis.from_url(settings.REDIS_URL, decode_responses=True) if settings.REDIS_URL else None


async def get_redis() -> AsyncGenerator[Redis | None, None]:
  yield redis


RedisClient = Annotated[Redis | None, Depends(get_redis)]