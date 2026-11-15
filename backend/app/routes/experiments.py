from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.experiments import (
    ExperimentCompareRequest,
    ExperimentComparison,
    ExperimentExplorerResponse,
    ExperimentRecordDetail,
)
from app.services.experiment_explorer_service import ExperimentExplorerService


router = APIRouter(prefix="/api/experiments", tags=["NASA Experiment Explorer"])
experiment_service = ExperimentExplorerService()


@router.get("", response_model=ExperimentExplorerResponse)
def list_stored_experiments(
    search: str | None = Query(default=None, max_length=200),
    source: str | None = Query(default=None, max_length=100),
    material: str | None = Query(default=None, max_length=200),
    gravity: str | None = Query(default=None, max_length=100),
    environment: str | None = Query(default=None, max_length=150),
    db: Session = Depends(get_db),
):
    return experiment_service.list_records(
        db,
        search=search,
        source=source,
        material=material,
        gravity=gravity,
        environment=environment,
    )


@router.post("/compare", response_model=ExperimentComparison)
def compare_stored_experiments(
    request: ExperimentCompareRequest,
    db: Session = Depends(get_db),
):
    result = experiment_service.compare(db, *request.record_ids)
    if result is None:
        raise HTTPException(status_code=404, detail="Select two different stored NASA records to compare.")
    return result


@router.get("/{record_id}", response_model=ExperimentRecordDetail)
def get_stored_experiment_detail(record_id: int, db: Session = Depends(get_db)):
    result = experiment_service.get_detail(db, record_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Stored NASA experiment or publication record not found.")
    return result
