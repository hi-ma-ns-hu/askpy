"""
services/tag_extractor.py — extract Python library names from a question.

Production context: agent.py's search_by_tags tool is only useful when the
agent knows which tags to filter on. Regex intersection against a known library
set is O(n tokens), zero latency, zero false positives for known names — no
model needed for a closed vocabulary like this.

The agent still decides whether to call search_by_tags — this just surfaces
the library names so the LLM can use them if relevant.
"""
from __future__ import annotations

import re

KNOWN_LIBRARIES: set[str] = {
    "pandas", "numpy", "matplotlib", "sklearn", "scikit-learn",
    "flask", "django", "fastapi", "sqlalchemy", "asyncio",
    "requests", "httpx", "pydantic", "celery", "redis",
    "pytest", "unittest", "mock", "pathlib", "collections",
    "itertools", "functools", "threading", "multiprocessing",
    "subprocess", "logging", "argparse", "json", "csv",
    "re", "os", "sys", "io", "datetime", "typing",
}

# Aliases where the question uses a common name but the SO tag differs
_ALIASES: dict[str, str] = {
    "scikit-learn": "sklearn",
    "sci-kit":      "sklearn",
    "scikit":       "sklearn",
}


def extract_tags(question: str) -> list[str]:
    """
    Return library names found in the question, ordered by position of first
    occurrence. Empty list when no known libraries are mentioned.

    Examples:
        "how do I merge dataframes in pandas?"  → ["pandas"]
        "flask vs django for a REST API"         → ["flask", "django"]
        "how do I reverse a list?"               → []
    """
    tokens = re.findall(r"\b[a-z0-9_\-]+\b", question.lower())
    seen: dict[str, int] = {}
    for i, tok in enumerate(tokens):
        canonical = _ALIASES.get(tok, tok)
        if canonical in KNOWN_LIBRARIES and canonical not in seen:
            seen[canonical] = i
    return sorted(seen, key=seen.__getitem__)
