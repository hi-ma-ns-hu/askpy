"""POST /ask — answer a Python question, grounded in the Stack Overflow corpus."""
from fastapi import APIRouter

from services.schemas import AskRequest, AnswerResponse
from services.qa import ask

qa_router = APIRouter(tags=["qa"])


@qa_router.post("/ask", response_model=AnswerResponse)
async def ask_endpoint(req: AskRequest) -> AnswerResponse:
  return await ask(req.question, req.top_k)
