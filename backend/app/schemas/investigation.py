from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional
from datetime import datetime

class PublicationBase(BaseModel):
    title: str
    authors: Optional[str] = None
    year: Optional[int] = None
    journal_or_conference: Optional[str] = None
    doi: Optional[str] = None
    ntrs_id: Optional[str] = None
    abstract: Optional[str] = None
    url: Optional[str] = None

class PublicationResponse(PublicationBase):
    id: int
    investigation_id: int
    model_config = ConfigDict(from_attributes=True)

class ResearchFindingBase(BaseModel):
    finding_text: str
    category: Optional[str] = None
    spacecraft_fire_safety_implication: str
    evidence_strength: str = "High (Flight Verified)"
    source_citation: Optional[str] = None
    doi: Optional[str] = None

class ResearchFindingResponse(ResearchFindingBase):
    id: int
    investigation_id: int
    model_config = ConfigDict(from_attributes=True)

class CombustionDataPointBase(BaseModel):
    fuel_name: str
    fuel_state: str
    ambient_o2_percent: Optional[float] = None
    pressure_atm: Optional[float] = None
    ambient_velocity_cm_s: Optional[float] = None
    burn_rate_or_flame_speed: Optional[float] = None
    unit: Optional[str] = None
    phenomenon: Optional[str] = None
    is_measured_flight_data: bool = False
    source_reference: Optional[str] = None

class CombustionDataPointResponse(BaseModel):
    id: int
    investigation_id: int
    fuel_name: str
    fuel_state: str
    ambient_o2_percent: Optional[float] = None
    pressure_atm: Optional[float] = None
    ambient_velocity_cm_s: Optional[float] = None
    burn_rate_or_flame_speed: Optional[float] = None
    unit: Optional[str] = None
    phenomenon: Optional[str] = None
    legacy_measured_flag: bool = Field(default=False, validation_alias="is_measured_flight_data")
    evidence_status: str = "Local record — provenance unverified"
    source_reference: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

class InvestigationBase(BaseModel):
    investigation_id: str
    title: str
    acronym: str
    principal_investigator: Optional[str] = None
    institution: Optional[str] = None
    category: str
    facility: Optional[str] = None
    flight_mission: Optional[str] = None
    status: str = "Completed"
    time_period: Optional[str] = None
    description: str
    objectives: Optional[str] = None
    fuel_types: Optional[str] = None
    oxidizer_environment: Optional[str] = None
    gravity_environment: str = "Microgravity (~10^-6 g)"
    measured_parameters: Optional[str] = None
    key_findings: Optional[str] = None
    fire_safety_relevance: Optional[str] = None
    source_url: Optional[str] = None
    psi_repo_url: Optional[str] = None
    ntrs_id: Optional[str] = None

class InvestigationSummary(BaseModel):
    id: int
    investigation_id: str
    title: str
    acronym: str
    principal_investigator: Optional[str] = None
    category: str
    facility: Optional[str] = None
    status: str
    time_period: Optional[str] = None
    fuel_types: Optional[str] = None
    source_url: Optional[str] = None
    publications_count: int = 0
    findings_count: int = 0
    datapoints_count: int = 0
    model_config = ConfigDict(from_attributes=True)

class InvestigationDetail(InvestigationBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    publications: List[PublicationResponse] = []
    findings: List[ResearchFindingResponse] = []
    datapoints: List[CombustionDataPointResponse] = []
    model_config = ConfigDict(from_attributes=True)
