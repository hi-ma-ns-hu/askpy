from fastapi import APIRouter

from .qa import qa_router

router = APIRouter()
router.include_router(qa_router)
