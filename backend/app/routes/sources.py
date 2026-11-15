from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from app.database import get_db
from app.models.investigation import SourceReference
from app.services.nasa_psi_service import NasaPsiService
from app.services.nasa_ntrs_service import NasaNtrsService

router = APIRouter(prefix="/api/sources", tags=["NASA Sources"])
psi_service = NasaPsiService()
ntrs_service = NasaNtrsService()

@router.get("")
def list_sources(db: Session = Depends(get_db)):
    sources = db.query(SourceReference).all()
    return [
        {
            "id": s.id,
            "source_name": s.source_name,
            "resource_id": s.resource_id,
            "resource_type": s.resource_type,
            "title": s.title,
            "url": s.url,
            "last_verified": s.last_verified,
            "status": s.status,
            "notes": s.notes,
            "retrieval_status": s.retrieval_status,
            "last_retrieved_at": s.last_retrieved_at,
            "last_http_status": s.last_http_status,
            "data_type": s.data_type,
            "provenance_status": s.provenance_status,
            "access_limitations": s.access_limitations,
        }
        for s in sources
    ]

@router.post("/check")
async def verify_external_sources(db: Session = Depends(get_db)):
    """Live connectivity verification of NASA PSI and NASA NTRS without downloading large datasets"""
    psi_status = await psi_service.check_psi_status()
    ntrs_status = await ntrs_service.check_ntrs_status()
    return {
        "status_checks": [psi_status, ntrs_status],
        "message": "Connectivity and metadata endpoint checks only; no PSI dataset or NTRS citation records were ingested."
    }
