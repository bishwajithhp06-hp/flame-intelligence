import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.routes.ai import ai_service
from app.schemas.mission import MissionAnalysisRequest, MissionAnalysisResponse
from app.services.mission_service import MissionIntelligenceService

logger = logging.getLogger("flame_intelligence.mission_route")

router = APIRouter(prefix="/api/mission", tags=["Mission Intelligence"])

# Reuse the Gemini client already initialized for /api/ai/query.
mission_service = MissionIntelligenceService(
    client=ai_service.client,
    model=ai_service.model,
)


@router.post("/analyze", response_model=MissionAnalysisResponse)
async def analyze_mission(
    request: MissionAnalysisRequest,
    db: Session = Depends(get_db),
) -> MissionAnalysisResponse:
    try:
        return await mission_service.analyze(
            db=db,
            parameters=request.parameters,
            question=request.question,
        )
    except RuntimeError as exc:
        development_mode = settings.ENVIRONMENT.strip().lower() in {"development", "dev", "local"}
        if development_mode:
            detail = str(exc)
        else:
            logger.warning(
                "Mission analysis unavailable: error_type=%s",
                type(exc).__name__,
            )
            detail = "Mission analysis is temporarily unavailable."
        raise HTTPException(status_code=503, detail=detail) from exc
    except Exception as exc:
        logger.exception("Mission analysis request failed")
        raise HTTPException(
            status_code=503,
            detail="Mission analysis is temporarily unavailable.",
        ) from exc
