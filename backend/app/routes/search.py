from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.research_service import ResearchService

router = APIRouter(prefix="/api/search", tags=["Search"])

@router.get("")
def search(
    q: str = Query(..., min_length=2, description="Search term for investigations, publications, or findings"),
    limit: int = Query(15, ge=1, le=50),
    db: Session = Depends(get_db)
):
    return ResearchService.search_all(db, q=q, limit=limit)
