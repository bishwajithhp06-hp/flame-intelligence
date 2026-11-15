from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class StatOverview(BaseModel):
    total_investigations: int
    total_publications: int
    total_findings: int
    total_datapoints: int
    categories_count: int
    data_authenticity_notice: str = "All records reflect documented NASA PSI, NTRS, and peer-reviewed flight investigation records. Demonstration samples are explicitly indicated."

class CategoryDistribution(BaseModel):
    category: str
    count: int
    percentage: float

class TimelineEvent(BaseModel):
    year_or_period: str
    acronym: str
    title: str
    facility: str
    milestone: str

class FlameComparisonItem(BaseModel):
    acronym: str
    title: str
    facility: str
    fuel_types: str
    oxidizer_conditions: str
    key_findings: str
    extinguishment_mechanisms: str
    safety_implication: str
    primary_doi: Optional[str] = None
    psi_link: Optional[str] = None

class CombustionDataPointItem(BaseModel):
    id: int
    investigation: str
    fuel: str
    state: str
    o2_pct: Optional[float]
    pressure_atm: Optional[float]
    flow_velocity: Optional[float]
    burn_rate: Optional[float]
    unit: Optional[str]
    phenomenon: str
    legacy_measured_flag: bool
    evidence_status: str
    source: str
