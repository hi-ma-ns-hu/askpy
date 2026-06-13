"""
config.py — Application settings, loaded from environment variables.

Loading priority (highest first):
  1. Real environment variables  — injected by the platform (Render/HF/systemd)
  2. .env file                   — local dev only, never committed
  3. Default value below         — only for settings safe to assume

Fields with NO default are REQUIRED — the app crashes loudly at startup if missing.
A loud crash beats silently running misconfigured.

Required to boot:  OPENAI_API_KEY, QDRANT_URL, QDRANT_API_KEY, KAGGLE_API_TOKEN
Optional:  REDIS_URL (answer cache), COHERE_API_KEY (reranker) — both degrade gracefully
"""
from functools import lru_cache
from typing import Literal

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
  model_config = SettingsConfigDict(
    env_file=".env",
    env_file_encoding="utf-8",
    case_sensitive=True,
    extra="ignore",          # ignore leftover env keys (old Slack/Celery/etc.)
  )

  # ── ENVIRONMENT ─────────────────────────────────────────────────────────────
  APP_ENV: Literal["DEVELOPMENT", "STAGING", "PRODUCTION"] = "DEVELOPMENT"
  LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

  # ── CACHE (Redis) ───────────────────────────────────────────────────────────
  # Optional — the /ask answer cache. If unset, the app runs cache-less.
  REDIS_URL: str = ""
  QA_CACHE_TTL_SECONDS: int = 86400          # 24h — how long answers are cached

  # ── LLM (OpenAI) ────────────────────────────────────────────────────────────
  OPENAI_API_KEY: str
  LLM_MODEL: str = "gpt-4o-mini"
  EMBEDDING_MODEL: str = "text-embedding-3-small"
  EMBEDDING_DIM: int = 768                   # Matryoshka truncation (1536 → 768)

  # ── VECTOR STORE (Qdrant) ───────────────────────────────────────────────────
  # Optional at boot so /health works before ingestion is configured.
  QDRANT_URL: str;
  QDRANT_API_KEY: str;
  QDRANT_COLLECTION: str = "vidhya_qa"

  # ── RERANKER (Cohere) ───────────────────────────────────────────────────────
  COHERE_API_KEY: str = ''
  RERANK_MODEL: str = "rerank-english-v3.0"

  # ── DATASET (Kaggle) ────────────────────────────────────────────────────────
  # Used only by scripts/ingest.py to authenticate the dataset download.
  KAGGLE_API_TOKEN: str

  # ── RETRIEVAL PIPELINE ──────────────────────────────────────────────────────
  RETRIEVE_CANDIDATES: int = 50              # hybrid search → candidates for rerank
  RETRIEVE_TOP_K: int = 5                    # final chunks passed to the LLM
  RETRIEVAL_THRESHOLD: float = 0.2           # drop candidates below this similarity

  # ── CONFIDENCE SCORING (see shared/llm/get_llm_answer.py) ───────────────────
  RETRIEVAL_CONFIDENCE_WEIGHT: float = 0.3
  LLM_CONFIDENCE_WEIGHT: float = 0.7
  ANSWER_CONFIDENCE_THRESHOLD: float = 0.4

  # ── COMPUTED ────────────────────────────────────────────────────────────────
  @computed_field
  @property
  def IS_DEVELOPMENT(self) -> bool:
    return self.APP_ENV == "DEVELOPMENT"


@lru_cache
def get_settings() -> Settings:
  return Settings()


settings = get_settings()
