"""
services/guardrails.py — input-side guardrails for the Q&A endpoint.

Two checks run before the pipeline:

  1. Prompt injection — detect attempts to override system instructions.
     Uses a regex pattern set. Fast, zero cost, zero latency.
     Limitation: pattern-based, so novel phrasing can slip through.
     A production-grade alternative is a dedicated classifier model.

  2. Question quality — reject inputs with control characters that pass
     Pydantic's min_length check but aren't real questions.

What we deliberately do NOT guard here:
  - Domain filtering (is this actually a Python question?)
    The retriever returning empty + qa.py refusing is already correct
    behavior for off-domain queries. A keyword heuristic here would have
    too many false positives ("how do I sort?" has no Python keywords).
    The right domain guard is an LLM classifier, which adds latency on
    every request — only worth it if off-domain abuse is a real cost issue.

  - Indirect prompt injection (malicious text in the corpus)
    This is an architectural threat, not an input filter problem.
    Mitigation: the system prompt's grounding constraint ("answer ONLY
    from context") limits what the LLM will act on, but doesn't fully
    eliminate the risk. Full mitigation requires corpus sanitation at
    ingest time and sandboxed LLM execution.
"""
from __future__ import annotations

import re

from fastapi import HTTPException

# Patterns that indicate an attempt to override system instructions.
# Deliberately conservative — err toward false negatives over false positives
# so legitimate edge-case questions aren't blocked.
_INJECTION_RE = re.compile(
    r"ignore\s+(?:(?:all|previous|prior|above|the|any|your)\s+)*(?:instructions|guidelines|rules|constraints)"
    r"|you\s+are\s+now\b"
    r"|disregard\s+(?:all\s+|previous\s+)?(?:instructions|guidelines)"
    r"|forget\s+(?:everything|all|your\s+instructions)"
    r"|(?:new|updated|actual|real|true)\s+system\s+(?:prompt|instructions?|message)"
    r"|act\s+as\s+(?:a\s+|an\s+)?(?:different|new|another|unrestricted|jailbroken)"
    r"|###\s*(?:system|instruction)"
    r"|<\s*(?:system|instruction)\s*>"
    r"|override\s+(?:the\s+|your\s+|all\s+|previous\s+)?(?:instructions|guidelines|rules)"
    r"|your\s+(?:new|actual|real|true)\s+instructions\s+are",
    re.IGNORECASE,
)

# Characters that have no place in a natural-language question.
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

def check_input(question: str) -> None:
    """
    Raise HTTPException(422) if the input fails any guardrail.
    Call this before the retrieval pipeline.
    """
    if _CONTROL_RE.search(question):
        raise HTTPException(status_code=422, detail="Input contains invalid characters.")

    if _INJECTION_RE.search(question):
        raise HTTPException(status_code=422, detail="Input contains disallowed patterns.")
