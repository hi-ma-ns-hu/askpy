"""Pydantic request/response schemas for the Q&A API (shared by services + routers)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
  question: str = Field(min_length=3, max_length=2000, description="A Python programming question")
  top_k: int | None = Field(default=None, ge=1, le=20, description="Override number of sources to ground on")


class Source(BaseModel):
  title: str
  url: str
  excerpt: str
  similarity: float


class AnswerResponse(BaseModel):
  answer: str
  confidence: float
  sources: list[Source]
  cached: bool = False
