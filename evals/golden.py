"""
evals/golden.py — 30 labeled golden examples for regression testing.

Production context: golden sets are the standard way teams catch regressions
before shipping. Every deploy runs check_regression.py against these examples.
If any metric drops >5%, the deploy fails. Netflix, Notion, and most ML teams
call this "offline eval" — a fixed labeled set that never changes, so you're
always comparing against the same ground truth.

How these were built:
  - Questions: top-voted Stack Overflow Python questions in the Qdrant corpus
  - must_contain: key tokens from the accepted answer (not the full answer)
  - must_refuse: True for out-of-domain questions the corpus cannot answer

must_contain notes:
  - Tokens must appear literally in the answer (case-insensitive check)
  - Keep them minimal — test for key concepts, not full sentences
  - Two alternatives in a list mean "at least one must appear"
"""
from __future__ import annotations

GOLDEN: list[dict] = [
    # ── basics ──────────────────────────────────────────────────────────────
    {
        "question": "How do I reverse a list in Python?",
        "must_contain": ["[::-1]", "reverse()"],
        "must_refuse": False,
        "category": "basics",
    },
    {
        "question": "How do I check if a key exists in a Python dictionary?",
        "must_contain": ["in"],
        "must_refuse": False,
        "category": "basics",
    },
    {
        "question": "How do I concatenate two lists in Python?",
        "must_contain": ["+", "extend"],
        "must_refuse": False,
        "category": "basics",
    },
    {
        "question": "How do I remove duplicates from a list in Python?",
        "must_contain": ["set"],
        "must_refuse": False,
        "category": "basics",
    },
    {
        "question": "How do I get the length of a list in Python?",
        "must_contain": ["len("],
        "must_refuse": False,
        "category": "basics",
    },

    # ── data structures ──────────────────────────────────────────────────────
    {
        "question": "How do I sort a dictionary by value in Python?",
        "must_contain": ["sorted"],
        "must_refuse": False,
        "category": "data-structures",
    },
    {
        "question": "How do I merge two dictionaries in Python?",
        "must_contain": ["update", "|", "**"],
        "must_refuse": False,
        "category": "data-structures",
    },
    {
        "question": "What is the difference between a list and a tuple in Python?",
        "must_contain": ["mutable", "immutable"],
        "must_refuse": False,
        "category": "data-structures",
    },
    {
        "question": "How do I iterate over a dictionary in Python?",
        "must_contain": ["items()", "keys()", "values()"],
        "must_refuse": False,
        "category": "data-structures",
    },
    {
        "question": "How do I count occurrences of an element in a list?",
        "must_contain": ["count(", "Counter"],
        "must_refuse": False,
        "category": "data-structures",
    },

    # ── functions and OOP ────────────────────────────────────────────────────
    {
        "question": "How do I create a decorator in Python?",
        "must_contain": ["@", "wrapper", "functools"],
        "must_refuse": False,
        "category": "functions",
    },
    {
        "question": "What is the difference between @staticmethod and @classmethod in Python?",
        "must_contain": ["cls", "self"],
        "must_refuse": False,
        "category": "oop",
    },
    {
        "question": "How do I use *args and **kwargs in Python?",
        "must_contain": ["*args", "**kwargs"],
        "must_refuse": False,
        "category": "functions",
    },
    {
        "question": "What is __init__ in Python?",
        "must_contain": ["__init__", "constructor", "self"],
        "must_refuse": False,
        "category": "oop",
    },
    {
        "question": "How do I implement inheritance in Python?",
        "must_contain": ["class", "super()"],
        "must_refuse": False,
        "category": "oop",
    },

    # ── error handling ───────────────────────────────────────────────────────
    {
        "question": "How do I catch multiple exceptions in Python?",
        "must_contain": ["except", "tuple"],
        "must_refuse": False,
        "category": "error-handling",
    },
    {
        "question": "How do I raise a custom exception in Python?",
        "must_contain": ["raise", "Exception"],
        "must_refuse": False,
        "category": "error-handling",
    },
    {
        "question": "What does the finally block do in Python?",
        "must_contain": ["finally"],
        "must_refuse": False,
        "category": "error-handling",
    },

    # ── concurrency ──────────────────────────────────────────────────────────
    {
        "question": "How does async and await work in Python?",
        "must_contain": ["async", "await", "coroutine", "event loop"],
        "must_refuse": False,
        "category": "concurrency",
    },
    {
        "question": "What is the difference between threading and multiprocessing in Python?",
        "must_contain": ["GIL", "thread", "process"],
        "must_refuse": False,
        "category": "concurrency",
    },

    # ── file I/O ─────────────────────────────────────────────────────────────
    {
        "question": "How do I read a file line by line in Python?",
        "must_contain": ["open(", "readline", "for line in"],
        "must_refuse": False,
        "category": "file-io",
    },
    {
        "question": "How do I write to a file in Python?",
        "must_contain": ["open(", "write(", "'w'"],
        "must_refuse": False,
        "category": "file-io",
    },

    # ── comprehensions and idioms ────────────────────────────────────────────
    {
        "question": "What is a list comprehension in Python?",
        "must_contain": ["[", "for", "in"],
        "must_refuse": False,
        "category": "idioms",
    },
    {
        "question": "What is the difference between a list comprehension and a generator expression?",
        "must_contain": ["generator", "yield", "memory", "lazy"],
        "must_refuse": False,
        "category": "idioms",
    },
    {
        "question": "How do I use the walrus operator in Python?",
        "must_contain": [":="],
        "must_refuse": False,
        "category": "idioms",
    },

    # ── libraries ────────────────────────────────────────────────────────────
    {
        "question": "How do I merge two dataframes in pandas?",
        "must_contain": ["merge", "join", "concat"],
        "must_refuse": False,
        "category": "libraries",
    },
    {
        "question": "How do I filter rows in a pandas DataFrame?",
        "must_contain": ["loc", "iloc", "boolean"],
        "must_refuse": False,
        "category": "libraries",
    },
    {
        "question": "How do I install a package in Python?",
        "must_contain": ["pip install"],
        "must_refuse": False,
        "category": "basics",
    },

    # ── out-of-domain — system MUST refuse ──────────────────────────────────
    {
        "question": "What is the capital of France?",
        "must_contain": [],
        "must_refuse": True,
        "category": "out-of-domain",
    },
    {
        "question": "Who won the FIFA World Cup in 2022?",
        "must_contain": [],
        "must_refuse": True,
        "category": "out-of-domain",
    },
]
