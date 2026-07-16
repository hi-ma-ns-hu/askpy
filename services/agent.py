"""
services/agent.py — Multi-tool agent for Q&A.

Contrast with agentic_qa.py:
  agentic_qa.py — one tool, one call allowed, hard-coded stop after 1 round
  agent.py      — three tools, real ReAct loop, max-steps guard

Agent design principles implemented here:

  1. Narrow tools — each tool has a distinct retrieval strategy so the LLM
     can route to the right one. Broad tools ("do_stuff") force the LLM to
     guess what they do; narrow tools ("search_by_tags") tell it exactly.

  2. Real loop — run until finish_reason == "stop", not until a hard-coded
     step count. The LLM decides when it has enough context.

  3. Max-steps guard — without a cap the loop can run forever. MAX_STEPS
     is the circuit breaker. When hit, we force tool_choice="none" and take
     whatever answer the LLM has so far.

  4. Context accumulation — every tool call's results extend all_chunks.
     The LLM's second call sees everything retrieved so far, not just the
     latest batch.

  5. Tool call logging — every tool dispatch is logged with the query and
     result count. This is the minimum observability you need to debug agent
     behavior in production.

Tool routing examples:
  "how do I sort a dataframe by column?"
    → LLM calls search_by_tags(query=..., tags=["pandas"])
    → returns pandas-specific chunks, not generic Python sorting

  "what is the modern way to open a file?"
    → LLM calls search_recent(query=...)
    → year filter excludes Python 2 open() answers from 2009

  "what's the difference between deepcopy and copy?"
    → LLM calls search_general twice with different sub-queries
    → two focused retrievals > one vague retrieval
"""
from __future__ import annotations

import json

from openai import AsyncOpenAI

from config import settings
from services.retriever import retrieve
from services.tag_extractor import extract_tags
from shared import get_logger
from shared.tracing import new_trace
from shared.llm.get_llm_answer import AskPy_SYSTEM_PROMPT, _parse_response

logger = get_logger(__name__)

MAX_STEPS = 4  # hard cap on tool calls before forcing a final answer

# ── Tool schemas (OpenAI function-calling format) ────────────────────────────

_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_general",
            "description": (
                "Search the Stack Overflow corpus for context on any Python topic. "
                "Use a focused sub-query, not the full user question. "
                "Call this first when context is missing or vague."
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
    },
    {
        "type": "function",
        "function": {
            "name": "search_by_tags",
            "description": (
                "Search the corpus filtered to specific Python library tags. "
                "Use when the question is clearly about a named library (pandas, numpy, "
                "matplotlib, sklearn, flask, django, sqlalchemy, etc.). "
                "More precise than search_general for library-specific questions."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "A focused search query.",
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Stack Overflow tags to filter on, e.g. ['pandas', 'dataframe'].",
                    },
                },
                "required": ["query", "tags"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_recent",
            "description": (
                "Search the corpus restricted to answers from 2015 onwards. "
                "Use when the question is about modern Python 3 idioms, f-strings, "
                "type hints, walrus operator, or anything where old Python 2 answers "
                "would be misleading. Avoids pre-Python-3.5 content."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "A focused search query.",
                    }
                },
                "required": ["query"],
            },
        },
    },
]


# ── Tool dispatch ─────────────────────────────────────────────────────────────

async def _dispatch(tool_name: str, args: dict, top_k: int) -> list[dict]:
    """Execute a tool call and return retrieved chunks."""
    if tool_name == "search_general":
        chunks = await retrieve(args["query"], top_k=top_k)
    elif tool_name == "search_by_tags":
        chunks = await retrieve(args["query"], top_k=top_k, tags=args.get("tags"))
    elif tool_name == "search_recent":
        chunks = await retrieve(args["query"], top_k=top_k, min_year=2015)
    else:
        logger.warning("agent called unknown tool", tool=tool_name)
        chunks = []

    logger.info("agent tool call", tool=tool_name, args=args, chunks_returned=len(chunks))
    return chunks


# ── Agent ─────────────────────────────────────────────────────────────────────

async def agent_ask(question: str, top_k: int = 5) -> dict:
    """
    Ask a question using a multi-tool ReAct agent.

    Returns:
      answer, confidence, steps (list of tool calls made), total_chunks
    """
    trace = new_trace("agent_ask", input={"question": question})
    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    # Step 1: initial retrieval — prime the agent with some context
    span_init = trace.span("initial_retrieval")
    initial_chunks = await retrieve(question, top_k=top_k)
    span_init.end(output={
        "chunks": len(initial_chunks),
        "top_score": initial_chunks[0]["similarity"] if initial_chunks else 0,
    })

    all_chunks: list[dict] = list(initial_chunks)
    steps: list[dict] = []

    detected_tags = extract_tags(question)
    tag_hint = f"\nDetected libraries in question: {detected_tags}. Use search_by_tags with these when relevant." if detected_tags else ""

    messages = [
        {"role": "system", "content": AskPy_SYSTEM_PROMPT + tag_hint},
        {"role": "system", "content": f"Initial context:\n{_format_context(initial_chunks)}"},
        {"role": "user", "content": question},
    ]

    # Step 2: ReAct loop — run until the LLM stops calling tools or we hit MAX_STEPS
    response = None
    for step in range(MAX_STEPS):
        force_stop = step == MAX_STEPS - 1
        response = await client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=messages,
            tools=_TOOLS,
            # On the last allowed step, prevent further tool calls so the model
            # must generate a final answer with whatever context it has.
            tool_choice="none" if force_stop else "auto",
            temperature=0.1,
        )
        choice = response.choices[0]

        if choice.finish_reason != "tool_calls":
            # LLM decided it has enough context — exit the loop
            break

        # Process all tool calls in this step (model may call multiple at once)
        messages.append(choice.message)
        for tool_call in choice.message.tool_calls:
            args = json.loads(tool_call.function.arguments)
            span_tool = trace.span(f"tool:{tool_call.function.name}", input=args)
            new_chunks = await _dispatch(tool_call.function.name, args, top_k)
            all_chunks.extend(new_chunks)
            steps.append({"tool": tool_call.function.name, "args": args, "chunks": len(new_chunks)})
            span_tool.end(output={"chunks": len(new_chunks)})

            # Append the tool result — must immediately follow the assistant's tool_calls message
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": f"Results for {tool_call.function.name}:\n{_format_context(new_chunks, offset=len(all_chunks) - len(new_chunks))}",
            })

    # Step 3: parse the final response
    weights = [1 / (i + 1) for i in range(len(all_chunks))]
    retrieval_confidence = (
        sum(c["similarity"] * w for c, w in zip(all_chunks, weights)) / sum(weights)
        if all_chunks else 0.0
    )
    answer, confidence, _ = _parse_response(
        response.choices[0].message.content, retrieval_confidence, all_chunks
    )

    logger.info("agent finished", steps=len(steps), total_chunks=len(all_chunks), confidence=confidence)
    trace.update(output={"answer": (answer or "")[:200], "confidence": confidence, "steps": len(steps)})
    return {
        "answer": answer,
        "confidence": confidence,
        "steps": steps,
        "total_chunks": len(all_chunks),
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _format_context(chunks: list[dict], offset: int = 0) -> str:
    if not chunks:
        return "(no results)"
    return "\n\n".join(
        f"[{offset + i + 1}] From '{c['title']}':\n{c['text']}"
        for i, c in enumerate(chunks)
    )
