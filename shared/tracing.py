"""
shared/tracing.py — Langfuse distributed tracing, optional.

If LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY are absent, every trace() call
returns a no-op object with the same interface. The request path is never
blocked or slowed by missing observability config.

Production context: this is the standard pattern — observability is a side
effect, not a dependency. The same code runs identically with and without it.
The only difference is whether traces appear in the Langfuse dashboard.

Usage:
    from shared.tracing import new_trace

    trace = new_trace("qa_request", input={"question": question})
    span  = trace.span("retrieval")
    span.end(output={"chunks": 5})
    trace.update(output={"answer": "..."})
"""
from __future__ import annotations

from config import settings


# ── No-op objects (used when Langfuse is not configured) ─────────────────────

class _NoopSpan:
    def end(self, output: dict | None = None, usage: dict | None = None) -> None:
        pass

    def span(self, name: str, **_) -> "_NoopSpan":
        return _NoopSpan()


class _NoopTrace:
    def span(self, name: str, **_) -> _NoopSpan:
        return _NoopSpan()

    def update(self, **_) -> None:
        pass


_NOOP = _NoopTrace()


# ── Client singleton ──────────────────────────────────────────────────────────

_client = None
_initialized = False


def _get_client():
    global _client, _initialized
    if _initialized:
        return _client
    _initialized = True
    if not (settings.LANGFUSE_PUBLIC_KEY and settings.LANGFUSE_SECRET_KEY):
        return None
    try:
        from langfuse import Langfuse
        _client = Langfuse(
            public_key=settings.LANGFUSE_PUBLIC_KEY,
            secret_key=settings.LANGFUSE_SECRET_KEY,
        )
    except Exception:
        pass
    return _client


# ── Public API ────────────────────────────────────────────────────────────────

def new_trace(name: str, **kwargs) -> _NoopTrace:
    """
    Create a Langfuse trace.

    Returns a real LangfuseTrace when keys are configured, or a no-op object
    that satisfies the same .span() / .update() interface when they're not.
    Exceptions from Langfuse itself are swallowed — tracing must never raise.
    """
    lf = _get_client()
    if lf is None:
        return _NOOP
    try:
        return lf.trace(name=name, **kwargs)
    except Exception:
        return _NOOP
