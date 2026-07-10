"""Pydantic request/response schemas for the Q&A API (shared by services + routers)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
  question: str = Field(min_length=3, max_length=2000, description="A Python programming question")
  top_k: int | None = Field(default=None, ge=1, le=20, description="Override number of sources to ground on")
  min_year: int | None = Field(default=None, ge=2008, le=2030, description="Only retrieve answers posted on or after this year")
  thread_id: str | None = Field(default=None, max_length=128, description="Session ID for multi-turn conversation. Omit for single-turn.")


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


class AgentStep(BaseModel):
  tool: str
  args: dict
  chunks: int


class AgentResponse(BaseModel):
  answer: str
  confidence: float
  steps: list[AgentStep]
  total_chunks: int
