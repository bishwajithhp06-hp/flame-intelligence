from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class ExperimentCitation(BaseModel):
    title: str
    url: Optional[str] = None
    doi: Optional[str] = None
    identifier: Optional[str] = None
    authors: Optional[str] = None
    year: Optional[int] = None
    evidence_type: Literal["NASA PSI source metadata", "NASA NTRS publication metadata"]


class RetrievedDatasetFile(BaseModel):
    file_name: str
    source_url: Optional[str] = None
    retrieval_status: Literal["retrieved", "metadata_only"]
    raw_size_bytes: Optional[int] = None
    measurements_parsed: bool = False
    note: str


class ExperimentRecord(BaseModel):
    record_id: int
    source_record_id: str
    record_kind: str
    title: str
    description: Optional[str] = None
    source_name: str
    source_resource_id: str
    source_url: Optional[str] = None
    retrieved_at: Optional[str] = None
    provenance_category: str
    evidence_status: str
    experiment_type: Optional[str] = None
    experiment_context_type: Optional[str] = None
    material: Optional[str] = None
    gravity_environment: Optional[str] = None
    environment: Optional[str] = None
    condition_values: Dict[str, Any] = Field(default_factory=dict)
    missing_data: List[str] = Field(default_factory=list)
    citations: List[ExperimentCitation] = Field(default_factory=list)


class ExperimentExplorerResponse(BaseModel):
    records: List[ExperimentRecord]
    available_filters: Dict[str, List[str]]
    conditions_notice: str


class ExperimentRecordDetail(ExperimentRecord):
    dataset_files: List[RetrievedDatasetFile] = Field(default_factory=list)
    retrieval_status: str
    retrieval_http_status: Optional[int] = None
    source_last_retrieved_at: Optional[str] = None


class ExperimentCompareRequest(BaseModel):
    record_ids: List[int] = Field(min_length=2, max_length=2)


class ExperimentComparison(BaseModel):
    left: ExperimentRecord
    right: ExperimentRecord
    categorical_comparisons: List[Dict[str, Optional[str]]] = Field(default_factory=list)
    quantitative_comparisons: List[Dict[str, Any]] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
