from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.experiments import ExperimentCompareRequest
from app.schemas.mission import MissionAnalysisResponse
from app.services.experiment_explorer_service import ExperimentExplorerService
from app.services.mission_report import build_experiment_comparison_report, build_mission_report


router = APIRouter(prefix="/api/reports", tags=["Mission Reports"])
experiment_service = ExperimentExplorerService()


@router.post("/mission", response_class=Response)
def download_mission_report(
    analysis: MissionAnalysisResponse,
    report_name: str | None = Query(default=None, max_length=160),
):
    pdf = build_mission_report(analysis, report_name=report_name)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="flame-mission-report.pdf"'},
    )


@router.post("/experiments/compare", response_class=Response)
def download_experiment_comparison_report(
    request: ExperimentCompareRequest,
    db: Session = Depends(get_db),
):
    comparison = experiment_service.compare(db, *request.record_ids)
    if comparison is None:
        raise HTTPException(status_code=404, detail="Select two different stored NASA records to report.")
    pdf = build_experiment_comparison_report(comparison)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="flame-experiment-comparison-report.pdf"'},
    )
