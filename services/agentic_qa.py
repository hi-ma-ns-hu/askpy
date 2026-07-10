"""
services/agentic_qa.py — Tool-use variant of the Q&A pipeline.

Contrast with services/qa.py:
  qa.py        — Linear: retrieve(question) → LLM generates answer (one shot, 1 LLM call)
  agentic_qa   — Iterative: LLM may call search_more() → retrieve again → continue

When tool use helps:
  - Vague questions: "how do I make my code faster?" benefits from the LLM
    issuing targeted sub-queries like "cProfile Python profiling" and
    "numpy vectorization speed" rather than searching the vague question verbatim.
  - Multi-hop: "what's the difference between X and Y?" may need two retrievals.
  - Low initial context: LLM detects that retrieved chunks don't answer the question
    and proactively searches for a better angle.

When tool use hurts:
  - Adds one full LLM round trip when the tool is called (~1–2s extra latency).
  - Non-deterministic: model may or may not call the tool on the same question.
  - Harder to test: evals need to handle variable numbers of retrieve() calls.
  - Can loop if not guarded (always cap iterations).

This implementation caps at one tool call (max 2 LLM calls total).
A full agentic loop runs until finish_reason == "stop" with a max-steps guard.
"""
from __future__ import annotations

import json

from openai import AsyncOpenAI
from config import settings
from services.retriever import retrieve
from shared.llm.get_llm_answer import Vidhya_SYSTEM_PROMPT, _parse_response

# ── Tool schema (OpenAI function-calling format) ────────────────────────────

_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_more",
            "description": (
                "Search the Stack Overflow corpus for additional context. "
                "Call this when the current context does not fully answer the question. "
                "Use a focused, specific query rather than the original user question."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "A focused search query targeting the missing information.",
                    }
                },
                "required": ["query"],
            },
        },
    }
]


# ── Agentic ask ─────────────────────────────────────────────────────────────

async def agentic_ask(question: str, top_k: int = 5) -> dict:
    """
    Ask a question with tool use enabled. Returns a dict with:
      answer, confidence, tool_called (bool), tool_query (str | None), total_chunks (int)

    The LLM can call search_more() once if it decides the initial context
    is insufficient. After the tool call, it receives the additional chunks
    and generates its final answer.
    """
    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    # Step 1: initial retrieval — same as the linear pipeline
    initial_chunks = await retrieve(question, top_k=top_k)
    context = _format_context(initial_chunks)

    messages = [
        {"role": "system", "content": Vidhya_SYSTEM_PROMPT},
        {"role": "system", "content": f"Knowledge base context:\n{context}"},
        {"role": "user",   "content": question},
    ]

    # Step 2: first LLM call with tools available
    response = await client.chat.completions.create(
        model=settings.LLM_MODEL,
        messages=messages,
        tools=_TOOLS,
        # "auto" lets the model decide whether to call a tool.
        # "none" disables tools. "required" forces a tool call.
        tool_choice="auto",
        temperature=0.1,
    )

    tool_called = False
    tool_query: str | None = None
    all_chunks = list(initial_chunks)

    # Step 3: if the model called a tool, execute it and feed the result back
    if response.choices[0].finish_reason == "tool_calls":
        tool_called = True
        tool_call = response.choices[0].message.tool_calls[0]
        args = json.loads(tool_call.function.arguments)
        tool_query = args["query"]

        # Execute the tool — this is just another retrieve() call
        extra_chunks = await retrieve(tool_query, top_k=top_k)
        all_chunks.extend(extra_chunks)
        extra_context = _format_context(extra_chunks, offset=len(initial_chunks))

        # Feed the tool result back as a "tool" role message.
        # The messages list must include the assistant's tool_calls message
        # followed immediately by the tool result — OpenAI requires this ordering.
        messages.append(response.choices[0].message)
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": f"Additional context from search '{tool_query}':\n{extra_context}",
        })

        # Step 4: second LLM call — now with combined context, no more tools
        response = await client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=messages,
            tool_choice="none",   # prevent infinite tool loops
            temperature=0.1,
        )

    # Step 5: parse the final response the same way the linear pipeline does
    weights = [1 / (i + 1) for i in range(len(all_chunks))]
    retrieval_confidence = (
        sum(c["similarity"] * w for c, w in zip(all_chunks, weights)) / sum(weights)
        if all_chunks else 0.0
    )
    answer, confidence, _ = _parse_response(
        response.choices[0].message.content, retrieval_confidence, all_chunks
    )

    return {
        "answer": answer,
        "confidence": confidence,
        "tool_called": tool_called,
        "tool_query": tool_query,
        "total_chunks": len(all_chunks),
    }


# ── Helpers ──────────────────────────────────────────────────────────────────

def _format_context(chunks: list[dict], offset: int = 0) -> str:
    return "\n\n".join(
        f"[{offset + i + 1}] From '{c['title']}':\n{c['text']}"
        for i, c in enumerate(chunks)
    )
