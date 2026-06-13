"""Endpoint tests for POST /ask (externals stubbed via conftest fixtures)."""


def test_ask_happy_path(client, fake_redis, stub_pipeline):
  r = client.post("/api/ask", json={"question": "How do I reverse a list in Python?"})
  assert r.status_code == 200
  body = r.json()
  assert "L[::-1]" in body["answer"]
  assert 0.0 <= body["confidence"] <= 1.0
  assert body["cached"] is False
  # source attribution
  assert len(body["sources"]) == 1
  src = body["sources"][0]
  assert src["url"].startswith("https://stackoverflow.com/")
  assert set(src) == {"title", "url", "excerpt", "similarity"}


def test_ask_is_cached_on_repeat(client, fake_redis, stub_pipeline):
  q = {"question": "How do I reverse a list in Python?"}
  first = client.post("/api/ask", json=q).json()
  second = client.post("/api/ask", json=q).json()
  assert first["cached"] is False
  assert second["cached"] is True
  # the expensive path ran only once
  assert stub_pipeline["retrieve"] == 1
  assert stub_pipeline["llm"] == 1


def test_ask_out_of_domain(client, fake_redis, stub_empty_retrieval):
  r = client.post("/api/ask", json={"question": "What is the capital of France?"})
  assert r.status_code == 200
  body = r.json()
  assert body["confidence"] == 0.0
  assert body["sources"] == []
  assert "don't have enough information" in body["answer"].lower()


def test_ask_rejects_too_short(client):
  r = client.post("/api/ask", json={"question": "hi"})
  assert r.status_code == 422


def test_ask_rejects_missing_question(client):
  r = client.post("/api/ask", json={})
  assert r.status_code == 422


def test_ask_rejects_bad_top_k(client):
  r = client.post("/api/ask", json={"question": "valid question here", "top_k": 99})
  assert r.status_code == 422
