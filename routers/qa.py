"""POST /ask — answer a Python question, grounded in the Stack Overflow corpus."""
from fastapi import APIRouter

from services.guardrails import check_input
from services.schemas import AskRequest, AnswerResponse, AgentResponse
from services.qa import ask
from services.agent import agent_ask
from services.semantic_cache import get_stats

qa_router = APIRouter(tags=["qa"])


@qa_router.post("/ask", response_model=AnswerResponse)
async def ask_endpoint(req: AskRequest) -> AnswerResponse:
  check_input(req.question)
  return await ask(req.question, req.top_k, req.min_year, req.thread_id)


@qa_router.post("/ask/agent", response_model=AgentResponse)
async def ask_agent_endpoint(req: AskRequest) -> AgentResponse:
  check_input(req.question)
  result = await agent_ask(req.question, top_k=req.top_k or 5)
  return AgentResponse(**result)


@qa_router.get("/cache/stats", tags=["ops"])
async def cache_stats() -> dict:
  """Live cache diagnostics since last restart.

  semantic_hits — served from semantic cache (paraphrase match)
  misses        — fell through to full pipeline
  For historical trends, query structured logs: event='semantic_hit' or 'miss'.
  """
  return get_stats()
