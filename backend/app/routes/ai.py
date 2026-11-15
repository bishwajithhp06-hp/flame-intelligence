import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.config import settings
from app.database import get_db
from app.services.gemini_service import GeminiResearchService
from app.schemas.ai import QueryRequest, QueryResponse

router = APIRouter(prefix="/api/ai", tags=["AI Research Assistant"])
logger = logging.getLogger("flame_intelligence.ai_route")
ai_service = GeminiResearchService()

@router.post("/query", response_model=QueryResponse)
async def ask_research_assistant(request: QueryRequest, db: Session = Depends(get_db)):
    try:
        return await ai_service.answer_question(
            db=db,
            question=request.question,
            investigation_filter=request.investigation_filter
        )
    except RuntimeError as exc:
        development_mode = settings.ENVIRONMENT.strip().lower() in {"development", "dev", "local"}
        if development_mode:
            detail = str(exc)
        else:
            logger.warning(
                "AI research analysis unavailable: error_type=%s",
                type(exc).__name__,
            )
            detail = "AI research analysis is temporarily unavailable."
        raise HTTPException(status_code=503, detail=detail) from exc
