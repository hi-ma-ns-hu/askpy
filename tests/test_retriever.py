"""Unit tests for retriever helpers (no network)."""
from types import SimpleNamespace

import services.retriever as rt


def test_build_filter_none():
  assert rt._build_filter(None, None) is None


def test_build_filter_tags_and_score():
  f = rt._build_filter(["python", "pandas"], 10)
  assert f is not None
  assert len(f.must) == 2


def test_to_chunk_shape_and_rounding():
  payload = {"title": "T", "text": "body", "url": "u", "score": 5, "tags": ["python"]}
  c = rt._to_chunk(payload, 0.776543)
  assert c["title"] == "T"
  assert c["similarity"] == 0.7765
  assert {"title", "text", "similarity", "url", "score", "tags"} <= set(c)


async def test_rerank_fallback_normalizes(monkeypatch):
  # force the no-Cohere fallback
  monkeypatch.setattr(rt, "_get_cohere", lambda: None)
  cands = [
    SimpleNamespace(payload={"title": f"t{i}", "text": "x", "url": "u", "score": i, "tags": []}, score=s)
    for i, s in enumerate([0.5, 0.3, 0.1])
  ]
  out = await rt._rerank("q", cands, top_k=2)
  assert len(out) == 2
  assert out[0]["similarity"] == 1.0            # top fusion score → 1.0
  assert all(0.0 <= c["similarity"] <= 1.0 for c in out)
