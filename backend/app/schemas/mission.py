from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


SPECIALIST_ROLES = (
    "Combustion Analyst",
    "Atmosphere Analyst",
    "Material Safety Analyst",
    "Fire Suppression Analyst",
    "Mission Safety Synthesizer",
)
FIRST_FOUR_SPECIALIST_ROLES = SPECIALIST_ROLES[:4]
SpecialistRole = Literal[
    "Combustion Analyst",
    "Atmosphere Analyst",
    "Material Safety Analyst",
    "Fire Suppression Analyst",
    "Mission Safety Synthesizer",
]
MatchStatus = Literal["match", "partial", "different", "unavailable"]
GapStatus = Literal["supported", "partial", "unsupported"]
EvidenceClass = Literal[
    "verified_nasa_source",
    "local_provenance_unverified",
    "publication_metadata_only",
]


class MissionParameters(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    environment: Literal[
        "ISS Cabin",
        "Lunar Habitat",
        "Mars Habitat",
        "Pressurized Rover",
        "Spacecraft Cabin",
        "Spacesuit",
    ]
    oxygen_percent: float = Field(..., ge=10, le=40)
    pressure_atm: float = Field(..., ge=0.2, le=1.5)
    airflow_cm_s: float = Field(..., ge=0, le=50)
    gravity: Literal["microgravity", "lunar", "mars", "earth"]
    material: Literal["n-heptane", "pmma", "cotton-fabric", "gas-jet", "nomex"]


class MissionAnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    parameters: MissionParameters
    question: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Optional additional mission research question",
    )


class MissionCitation(BaseModel):
    citation_id: str
    title: str
    source: str
    authors: Optional[str] = None
    year: Optional[int] = None
    identifier: Optional[str] = None
    doi: Optional[str] = None
    url: Optional[str] = None
    evidence_status: str
    evidence_class: EvidenceClass = "local_provenance_unverified"
    relevance_explanation: str
    relevance_snippet: Optional[str] = None
    investigation_acronym: Optional[str] = None


class EvidenceFinding(BaseModel):
    finding_text: str
    source_citation: Optional[str] = None
    doi: Optional[str] = None
    evidence_status: str = "Local record — provenance unverified"


class EvidenceParameterMatch(BaseModel):
    parameter: str
    scenario_value: str
    recorded_value: Optional[str] = None
    status: MatchStatus
    explanation: str


class MissionEvidenceRecord(BaseModel):
    evidence_id: str
    investigation_title: str
    investigation_acronym: str
    original_source_url: Optional[str] = None
    experiment_type: Optional[str] = None
    facility: Optional[str] = None
    flight_mission: Optional[str] = None
    fuel_types: Optional[str] = None
    oxidizer_environment: Optional[str] = None
    gravity_environment: Optional[str] = None
    measured_parameters: Optional[str] = None
    evidence_status: str = "Local record — provenance unverified"
    evidence_class: EvidenceClass = "local_provenance_unverified"
    relevance_explanation: str
    parameter_matches: List[EvidenceParameterMatch] = Field(default_factory=list)
    publications: List[MissionCitation] = Field(default_factory=list)
    findings: List[EvidenceFinding] = Field(default_factory=list)


class EvidenceReference(BaseModel):
    evidence_id: str
    investigation_title: str
    investigation_acronym: str
    original_source_url: Optional[str] = None
    evidence_status: str
    evidence_class: EvidenceClass = "local_provenance_unverified"
    relevance_explanation: str


class EvidenceValidationDiagnostic(BaseModel):
    """Safe per-claim validation metadata. Generated claim text is intentionally omitted."""

    role: SpecialistRole
    claim_index: int = Field(ge=0)
    claim_classification: str
    reason_code: str
    reason: str
    evidence_references_supplied: bool
    evidence_ids_valid: Optional[bool] = None
    citation_ids_supplied: bool
    citation_ids_valid: Optional[bool] = None
    citation_investigation_match: Optional[bool] = None
    provenance_restriction_rejected: bool = False
    historical_source_text_match: Optional[bool] = None


class SpecialistAnalysis(BaseModel):
    role: SpecialistRole
    analysis: str
    relevant_evidence: List[EvidenceReference] = Field(default_factory=list)
    evidence_status: str = "Insufficient evidence"
    evidence_validation_status: Literal["validated", "partial", "no_valid_claims"] = "validated"
    evidence_validation_issues: List[str] = Field(default_factory=list)
    evidence_validation_diagnostics: List[EvidenceValidationDiagnostic] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
    uncertainties: List[str] = Field(default_factory=list)
    citations: List[MissionCitation] = Field(default_factory=list)


class ResearchGapAssessment(BaseModel):
    parameter: str
    scenario_value: str
    status: GapStatus
    available_evidence: List[str] = Field(default_factory=list)
    explanation: str


class ResearchGapReport(BaseModel):
    supported_parameters: List[ResearchGapAssessment] = Field(default_factory=list)
    partially_supported_parameters: List[ResearchGapAssessment] = Field(default_factory=list)
    unsupported_parameters: List[ResearchGapAssessment] = Field(default_factory=list)
    important_assumptions: List[str] = Field(default_factory=list)
    combined_scenario_status: Literal["not_documented"] = "not_documented"
    combined_scenario_explanation: str = (
        "No retrieved source explicitly documents this full parameter combination as tested. "
        "Separate condition overlaps from related records cannot be combined into evidence of a joint test."
    )


class DocumentedFinding(BaseModel):
    finding: str
    citations: List[MissionCitation] = Field(default_factory=list)


class MissionSynthesisDetails(BaseModel):
    combined_assessment: str
    conflict_assessment: str
    main_documented_findings: List[DocumentedFinding] = Field(default_factory=list)
    important_uncertainties: List[str] = Field(default_factory=list)
    research_gaps: List[str] = Field(default_factory=list)
    conflicting_claims: List[str] = Field(default_factory=list)
    supporting_citations: List[MissionCitation] = Field(default_factory=list)


class MissionAnalysisResponse(BaseModel):
    environment: str
    scenario_parameters: MissionParameters
    specialist_analyses: List[SpecialistAnalysis]
    mission_synthesis: str
    synthesis_details: MissionSynthesisDetails
    citations: List[MissionCitation] = Field(default_factory=list)
    evidence_matches: List[MissionEvidenceRecord] = Field(default_factory=list)
    research_gaps: ResearchGapReport
    evidence_status: str
    evidence_validation_status: Literal["complete", "partial"] = "complete"
    evidence_validation_issues: List[str] = Field(default_factory=list)
    evidence_validation_diagnostics: List[EvidenceValidationDiagnostic] = Field(default_factory=list)
    evidence_limitations: List[str] = Field(default_factory=list)
    disclaimer: str = (
        "Research guidance only. This output is not certified spacecraft "
        "engineering advice or flight clearance."
    )

    @model_validator(mode="after")
    def require_all_specialist_roles(self):
        roles = [item.role for item in self.specialist_analyses]
        if len(roles) != len(SPECIALIST_ROLES) or set(roles) != set(SPECIALIST_ROLES):
            raise ValueError("Mission response must contain all five specialist roles exactly once")
        if self.environment != self.scenario_parameters.environment:
            raise ValueError("Mission response environment must match the submitted scenario parameters")
        return self
