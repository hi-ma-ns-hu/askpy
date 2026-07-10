"""
services/query_classifier.py — zero-shot query classification before retrieval.

Production context: classifying the query before retrieval lets you route to
the best strategy per query type. "debugging" queries are keyword-heavy (error
messages, exact function names) → sparse/BM25 wins. "conceptual" queries are
intent-based → dense wins. "out-of-domain" → skip retrieval entirely and refuse.

Zero-shot means no training data from you — the model (BART-MNLI) was trained
on Natural Language Inference and repurposes that to score each candidate label
as "does this question entail being about <label>?". You can add or change labels
without retraining anything.

Model: facebook/bart-large-mnli (~1.6GB, downloads on first use).
Lazy-loaded — the model is not loaded at import time, only on the first call.
This keeps startup fast and avoids loading it in processes that don't use it
(e.g. the ingestion script).
"""
from __future__ import annotations

_classifier = None
_transformers_available: bool | None = None  # None = not yet checked


def _check_transformers() -> bool:
    global _transformers_available
    if _transformers_available is None:
        try:
            import transformers  # noqa: F401
            _transformers_available = True
        except ImportError:
            _transformers_available = False
    return _transformers_available

QUERY_TYPES = [
    "debugging",       # fix an error, traceback, unexpected behaviour
    "how-to",          # step-by-step: how do I do X
    "conceptual",      # explain or compare: what is X, difference between X and Y
    "library-specific",# question scoped to a named library (pandas, numpy, etc.)
    "out-of-domain",   # nothing to do with Python programming
]


def _get_classifier():
    global _classifier
    if not _check_transformers():
        raise RuntimeError("transformers not installed — pip install transformers torch")
    if _classifier is None:
        from transformers import pipeline as hf_pipeline
        _classifier = hf_pipeline(
            "zero-shot-classification",
            model="facebook/bart-large-mnli",
        )
    return _classifier


def classify_query(question: str) -> str:
    """
    Return the most likely query type for this question.

    Runs synchronously — call from a thread or executor if you need async.
    First call is slow (~2s, model load). Subsequent calls ~100-300ms on CPU.
    """
    result = _get_classifier()(question, candidate_labels=QUERY_TYPES)
    return result["labels"][0]


def classify_query_with_scores(question: str) -> dict[str, float]:
    """Return all labels with their scores — useful for logging and analysis."""
    result = _get_classifier()(question, candidate_labels=QUERY_TYPES)
    return dict(zip(result["labels"], result["scores"]))
