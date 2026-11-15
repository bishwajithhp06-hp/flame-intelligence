from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.services.research_service import ResearchService
from app.schemas.investigation import InvestigationSummary, InvestigationDetail

router = APIRouter(prefix="/api/investigations", tags=["Investigations"])

@router.get("", response_model=List[InvestigationSummary])
def get_investigations(
    category: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    return ResearchService.list_investigations(db, category=category, search=search, limit=limit, skip=skip)

@router.get("/{investigation_id}", response_model=InvestigationDetail)
def get_investigation_detail(investigation_id: int, db: Session = Depends(get_db)):
    inv = ResearchService.get_investigation_by_id(db, investigation_id)
    if not inv:
        raise HTTPException(status_code=404, detail="NASA Investigation not found.")
    return inv

@router.get("/acronym/{acronym}", response_model=InvestigationDetail)
def get_investigation_by_acronym(acronym: str, db: Session = Depends(get_db)):
    inv = ResearchService.get_investigation_by_acronym(db, acronym)
    if not inv:
        raise HTTPException(status_code=404, detail=f"NASA Investigation with acronym '{acronym}' not found.")
    return inv
