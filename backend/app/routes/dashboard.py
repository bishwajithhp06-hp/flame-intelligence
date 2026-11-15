from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from app.database import get_db
from app.services.analytics_service import AnalyticsService
from app.services.research_service import ResearchService

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])

@router.get("/stats")
def get_dashboard_stats(db: Session = Depends(get_db)):
    return AnalyticsService.get_overview_stats(db)

@router.get("/categories")
def get_categories(db: Session = Depends(get_db)):
    return AnalyticsService.get_category_distribution(db)

@router.get("/timeline")
def get_timeline(db: Session = Depends(get_db)):
    return AnalyticsService.get_mission_timeline(db)

@router.get("/recent")
def get_recent_investigations(db: Session = Depends(get_db)):
    return ResearchService.list_investigations(db, limit=5)
