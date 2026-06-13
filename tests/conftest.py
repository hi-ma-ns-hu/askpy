"""
Shared pytest fixtures.

The endpoint tests stub the two external calls (retrieve + LLM) and swap Redis
for an in-memory fake, so the suite is fast, deterministic, and needs no
network, API keys, or running services.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import services.qa as qa
from app import app


class FakeRedis:
  """Minimal async Redis stand-in backed by a dict."""
  def __init__(self) -> None:
    self.store: dict[str, str] = {}

  async def get(self, key):
    return self.store.get(key)

  async def set(self, key, value, ex=None):
    self.store[key] = value

  async def ping(self):
    return True


@pytest.fixture
def client() -> TestClient:
  return TestClient(app)


@pytest.fixture
def fake_redis(monkeypatch) -> FakeRedis:
  fr = FakeRedis()
  monkeypatch.setattr(qa, "redis", fr)
  return fr


@pytest.fixture
def stub_pipeline(monkeypatch):
  """
  Stub retrieve() + get_llm_answer() with canned, deterministic output.
  Returns a dict of call counters so tests can assert e.g. cache behaviour.
  """
  calls = {"retrieve": 0, "llm": 0}

  chunk = {
    "title": "How can I reverse a list in python?",
    "text": "Use slicing: L[::-1] returns a reversed copy.",
    "similarity": 0.88,
    "url": "https://stackoverflow.com/questions/3940128",
    "score": 100,
    "tags": ["python", "list"],
  }

  async def fake_retrieve(question, top_k=None, **kwargs):
    calls["retrieve"] += 1
    return [chunk]

  async def fake_llm(question, chunks, history=None, user_context=None):
    calls["llm"] += 1
    return ("Use L[::-1] to reverse a list.", 0.82, [(chunks[0], "slice with [::-1]")])

  monkeypatch.setattr(qa, "retrieve", fake_retrieve)
  monkeypatch.setattr(qa, "get_llm_answer", fake_llm)
  return calls


@pytest.fixture
def stub_empty_retrieval(monkeypatch):
  """Retrieval returns nothing — the out-of-domain path."""
  async def fake_retrieve(question, top_k=None, **kwargs):
    return []
  monkeypatch.setattr(qa, "retrieve", fake_retrieve)
