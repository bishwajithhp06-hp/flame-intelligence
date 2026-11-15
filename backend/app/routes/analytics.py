from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from app.database import get_db
from app.services.analytics_service import AnalyticsService
from app.services.research_service import ResearchService

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])

@router.get("/datapoints")
def get_datapoints(
    flight_only: bool = Query(True, description="Return only independently provenance-verified flight data; legacy flags are not verification"),
    db: Session = Depends(get_db)
):
    return AnalyticsService.get_datapoints(db, flight_only=flight_only)

@router.get("/comparison")
def get_comparison_matrix(db: Session = Depends(get_db)):
    return AnalyticsService.get_experiment_comparison_matrix(db)

@router.get("/insights")
def get_fire_safety_insights(db: Session = Depends(get_db)):
    return ResearchService.get_fire_safety_insights(db)
