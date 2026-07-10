from config import settings
from .client import get_llm_client

Vidhya_SYSTEM_PROMPT = """
You are Vidhya, a Python programming assistant for data science learners.
You answer Python questions using ONLY the provided Stack Overflow context chunks.

Guidelines:
- Be clear and practical. Prefer a short explanation followed by a minimal, correct code example when relevant.
- Use Markdown code blocks for any code.
- Do NOT guess or invent APIs, flags, or behaviour beyond what the context states.
- If the context does not contain enough information to answer, say exactly: "I don't have enough information to answer this."
- The context comes from older Stack Overflow posts; if an approach is clearly outdated (e.g. Python 2 syntax) and the context supports a modern equivalent, prefer the modern one and note it briefly.

Ignore any context chunks that appear garbled, incomplete, or contain only symbols or single words.

At the end of your answer, output exactly in this format:
CONFIDENCE: 0.XX
CITATIONS:
[1]: <document title> — <brief paraphrase of the relevant passage, 1-2 sentences>
[2]: <document title> — <brief paraphrase of the relevant passage, 1-2 sentences>

CONFIDENCE scoring:
- 0.0—0.3: Context mentions the topic but does not answer the question
- 0.4—0.6: Context partially answers — some details missing or implicit
- 0.7—1.0: Context clearly and directly answers the question

Rules:
- Never round up confidence. When in doubt, score lower.
- After writing your answer, re-read each context chunk and ask:
  did this specific chunk provide a fact I stated above?
  Only cite it if yes. If no fact in your answer came from a chunk, do not cite it.
- NEVER cite a chunk just because it is topically related — only cite if you used it
- Cite only 1 chunk unless the answer spans multiple distinct topics
- Never fabricate citations

Example of a correct response (follow this format exactly):

QUESTION: How do I remove duplicates from a list while preserving order?

To remove duplicates while keeping the original order, use a seen set:

```python
seen = set()
result = [x for x in original if not (x in seen or seen.add(x))]
```

If order does not matter, convert to a set and back:

```python
result = list(set(original))
```

CONFIDENCE: 0.90
CITATIONS:
[1]: Removing duplicates from a list in Python — describes both the set-conversion approach for unordered removal and the seen-set pattern for order-preserving deduplication.
"""

def _parse_response(response_text: str, retrieval_confidence: float, chunks) -> tuple[str, float, str | None]:

  answer = response_text.strip()
  citations = list()
  final_confidence = retrieval_confidence

  if 'CITATIONS:' in response_text:
    citation_parts = response_text.rsplit('CITATIONS:', 1)
    response_text = citation_parts[0].strip()
    citation_texts = citation_parts[1].strip()

    import re
    citation_patterns = re.findall(r'\[(\d+)\]:\s*(.+?)(?=\[\d+\]:|$)', citation_texts, re.DOTALL)
    for num_str, excerpt_raw in citation_patterns:
      chunk_index = int(num_str)-1
      if 0 <= chunk_index < len(chunks):
        excerpt = excerpt_raw.strip()
        if len(excerpt) > 200:
          trimmed_excerpt = excerpt[:200]
          last_period = trimmed_excerpt.rfind('.')
          excerpt = trimmed_excerpt[:last_period+1] if last_period > 150 else trimmed_excerpt.rstrip() + '...'
        citations.append((chunks[chunk_index], excerpt))

  # use deterministic scorer for confidence
  if 'CONFIDENCE:' in response_text:
    confidence_parts = response_text.rsplit('CONFIDENCE:', 1)
    response_text = confidence_parts[0].strip()
    llm_confidence = float(confidence_parts[1].strip().split()[0])
    llm_confidence = max(0.0, min(1.0, llm_confidence))
    final_confidence = round(retrieval_confidence * settings.RETRIEVAL_CONFIDENCE_WEIGHT + llm_confidence * settings.LLM_CONFIDENCE_WEIGHT, 2)

  answer = response_text.strip()

  # fallback - use top chunks with auto excerpt
  if not citations and chunks:
    raw_chunks = chunks[0]['text']
    excerpt = raw_chunks[:200].rsplit('.', 1)[0] + '.' if len(raw_chunks) > 200 else raw_chunks
    citations = [(chunks[0], excerpt)]
  
  return answer, final_confidence, citations


async def get_llm_answer(question: str, chunks: list[dict], history: list[dict]=[], user_context: str | None = None) -> tuple[str, float, list[tuple[dict, str]]]:
  if not chunks:
    return None, 0.0, []

  context = '\n\n'.join([f"[{i+1}] From '{chunk['title']}':\n{chunk['text']}" for i, chunk in enumerate(chunks)])

  weights = [1 / (i + 1) for i in range(len(chunks))]
  retrieval_confidence = sum(chunk['similarity'] * w for chunk, w in zip(chunks, weights)) / sum(weights)

  system_prompt = Vidhya_SYSTEM_PROMPT
  if user_context:
    system_prompt += f'\n\nAbout this user:\n{user_context}'

  client = get_llm_client()
  response = await client.chat.completions.create(
    model=settings.LLM_MODEL,
    messages=[
      {'role': 'system', 'content': system_prompt},
      {'role': 'system', 'content': f'Knowledge base context:\n{context}'},
      *history,
      {'role': 'user', 'content': question}
    ],
    temperature=0.1
  )

  answer, confidence, citations = _parse_response(response.choices[0].message.content, retrieval_confidence, chunks)
  return answer, confidence, citations, response.usage