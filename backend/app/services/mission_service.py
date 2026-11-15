import asyncio
import json
import logging
import math
import re
from typing import List, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from sqlalchemy.orm import Session

from app.schemas.mission import (
    EvidenceValidationDiagnostic,
    FIRST_FOUR_SPECIALIST_ROLES,
    DocumentedFinding,
    EvidenceReference,
    MissionAnalysisResponse,
    MissionCitation,
    MissionParameters,
    MissionSynthesisDetails,
    SpecialistAnalysis,
)
from app.services.mission_evidence_service import (
    MissionEvidenceBundle,
    MissionEvidenceService,
)
from app.services.nasa_ntrs_service import NasaNtrsService

logger = logging.getLogger("flame_intelligence.mission")


def _unique(values):
    return list(dict.fromkeys(value for value in values if value))

FirstFourRole = Literal[
    "Combustion Analyst",
    "Atmosphere Analyst",
    "Material Safety Analyst",
    "Fire Suppression Analyst",
]
class ClaimValidationFailure(RuntimeError):
    """A safe, classified claim rejection that can be reported without claim text."""

    def __init__(self, reason_code, message):
        super().__init__(message)
        self.reason_code = reason_code


class ClaimSourceReference(BaseModel):
    """One record and one or more citations that support a claim."""

    model_config = ConfigDict(extra="forbid")

    evidence_id: str = ""
    citation_ids: List[str] = Field(default_factory=list)
    source_excerpt: str = ""
    provenance_status: str = ""


class MissionClaim(BaseModel):
    """A single user-facing claim with its own classification and sources."""

    model_config = ConfigDict(extra="forbid")

    claim_text: str = Field(min_length=1)
    # Keep the raw label so one invalid claim can be diagnosed and omitted without
    # turning every other claim in the same stage into a parser failure.
    claim_type: str
    sources: List[ClaimSourceReference] = Field(default_factory=list)
    uncertainty: str = ""


class SpecialistDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: FirstFourRole
    scenario_parameters: MissionParameters
    claims: List[MissionClaim] = Field(default_factory=list)

    @property
    def analysis(self):
        return "\n".join(claim.claim_text for claim in self.claims)

    @property
    def relevant_evidence_ids(self):
        return _unique(source.evidence_id for claim in self.claims for source in claim.sources)

    @property
    def citation_ids(self):
        return _unique(citation_id for claim in self.claims for source in claim.sources for citation_id in source.citation_ids)

    @property
    def assumptions(self):
        return []

    @property
    def uncertainties(self):
        return _unique(claim.uncertainty for claim in self.claims if claim.uncertainty)


class SpecialistStageResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    specialist_analyses: List[SpecialistDraft]

    @model_validator(mode="after")
    def require_four_distinct_roles(self):
        roles = [item.role for item in self.specialist_analyses]
        if len(roles) != len(FIRST_FOUR_SPECIALIST_ROLES) or set(roles) != set(FIRST_FOUR_SPECIALIST_ROLES):
            raise ValueError("The first analysis stage must return the four specialist roles exactly once")
        return self


class SynthesisDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_parameters: MissionParameters
    analysis_claims: List[MissionClaim] = Field(default_factory=list)
    combined_assessment_claims: List[MissionClaim] = Field(default_factory=list)
    conflict_assessment: str = "No conflicts identified among the available validated claims."
    main_documented_findings: List[dict] = Field(default_factory=list)
    conflicting_claims: List[str] = Field(default_factory=list)
    important_uncertainties: List[str] = Field(default_factory=list)
    research_gaps: List[str] = Field(default_factory=list)
    supporting_citation_ids: List[str] = Field(default_factory=list)

    @property
    def analysis(self):
        return "\n".join(claim.claim_text for claim in self.analysis_claims)

    @property
    def combined_assessment(self):
        return "\n".join(claim.claim_text for claim in self.combined_assessment_claims)

    @property
    def claims(self):
        return self.analysis_claims + self.combined_assessment_claims

    @property
    def relevant_evidence_ids(self):
        return _unique(source.evidence_id for claim in self.claims for source in claim.sources)

    @property
    def citation_ids(self):
        return _unique(citation_id for claim in self.claims for source in claim.sources for citation_id in source.citation_ids)

    @property
    def uncertainties(self):
        return _unique(claim.uncertainty for claim in self.claims if claim.uncertainty)

    @property
    def assumptions(self):
        return []


class MissionIntelligenceService:
    """Coordinates four shared-evidence specialists and one synthesis stage."""

    def __init__(
        self,
        client=None,
        model: str = "gemini-2.5-flash",
        ntrs_service=None,
        evidence_service=None,
    ):
        self.client = client
        self.model = model
        self.ntrs_service = ntrs_service or NasaNtrsService()
        self.evidence_service = evidence_service or MissionEvidenceService()

    def _retrieve_evidence(self, db: Session, parameters=None, question=None):
        """Compatibility wrapper retaining Phase 1 provenance-audit behavior."""
        bundle = self.evidence_service.retrieve(db, parameters, question)
        return {
            "context": bundle.context,
            "citations": bundle.citations,
            "investigations": [record.investigation_acronym for record in bundle.records],
            "records": bundle.records,
            "research_gaps": bundle.research_gaps,
            "limitations": bundle.limitations,
        }

    async def analyze(
        self,
        db: Session,
        parameters: MissionParameters,
        question: str | None = None,
    ) -> MissionAnalysisResponse:
        if not self.client:
            raise RuntimeError(
                "Gemini is not configured. Check GEMINI_API_KEY in backend/.env."
            )

        evidence = self.evidence_service.retrieve(db, parameters, question)
        await self._add_ntrs_metadata(evidence, parameters)
        available_records = {record.evidence_id: record for record in evidence.records}
        available_citations = {citation.citation_id: citation for citation in evidence.citations}

        first_stage = await self._generate_specialists(
            parameters=parameters,
            question=question,
            evidence=evidence,
        )
        validation_issues = []
        validation_diagnostics = []
        validated_specialists = []
        for specialist in first_stage.specialist_analyses:
            self._validate_scenario_echo(
                specialist.scenario_parameters,
                parameters,
                specialist.role,
            )
            accepted_claims, claim_issues, claim_diagnostics = self._filter_claims(
                specialist.claims,
                parameters,
                specialist.role,
                available_citations,
                available_records,
            )
            validated_specialists.append((
                specialist.model_copy(update={"claims": accepted_claims}),
                self._validation_state(specialist.claims, accepted_claims),
                claim_issues,
                claim_diagnostics,
            ))
            validation_issues.extend(claim_issues)
            validation_diagnostics.extend(claim_diagnostics)

        synthesis = await self._generate_synthesis(
            parameters=parameters,
            question=question,
            evidence=evidence,
            specialists=validated_specialists,
        )
        self._validate_scenario_echo(
            synthesis.scenario_parameters,
            parameters,
            "Mission Safety Synthesizer",
        )
        self._validate_conflicting_claims(synthesis.conflicting_claims)
        self._validate_conflict_assessment(
            synthesis.conflicting_claims,
            synthesis.conflict_assessment,
        )
        valid_analysis_claims, analysis_issues, analysis_diagnostics = self._filter_claims(
            synthesis.analysis_claims,
            parameters,
            "Mission Safety Synthesizer",
            available_citations,
            available_records,
        )
        submitted_synthesis_claims = (
            synthesis.analysis_claims + synthesis.combined_assessment_claims
        )
        valid_combined_claims, combined_issues, combined_diagnostics = self._filter_claims(
            synthesis.combined_assessment_claims,
            parameters,
            "Mission Safety Synthesizer",
            available_citations,
            available_records,
        )
        synthesis.analysis_claims = valid_analysis_claims
        synthesis.combined_assessment_claims = valid_combined_claims
        synthesis_issues = analysis_issues + combined_issues
        synthesis_diagnostics = analysis_diagnostics + combined_diagnostics
        validation_issues.extend(synthesis_issues)
        validation_diagnostics.extend(synthesis_diagnostics)
        synthesis_validation_status = self._validation_state(
            submitted_synthesis_claims,
            valid_analysis_claims + valid_combined_claims,
        )
        self._validate_references(
            synthesis.relevant_evidence_ids,
            synthesis.citation_ids + synthesis.supporting_citation_ids,
            available_records,
            available_citations,
        )

        specialist_outputs = []
        for draft, validation_status, specialist_issues, specialist_diagnostics in validated_specialists:
            record_refs = self._record_references(draft.relevant_evidence_ids, available_records)
            specialist_citations = self._citations(draft.citation_ids, available_citations)
            specialist_outputs.append(SpecialistAnalysis(
                role=draft.role,
                analysis=draft.analysis or "No claim passed evidence validation for this specialist.",
                relevant_evidence=record_refs,
                evidence_status=self._evidence_status(record_refs, specialist_citations),
                evidence_validation_status=validation_status,
                evidence_validation_issues=specialist_issues,
                evidence_validation_diagnostics=specialist_diagnostics,
                assumptions=self._unique(evidence.research_gaps.important_assumptions + draft.assumptions),
                uncertainties=draft.uncertainties,
                citations=specialist_citations,
            ))

        synthesis_refs = self._record_references(synthesis.relevant_evidence_ids, available_records)
        synthesis_citations = self._citations(synthesis.citation_ids, available_citations)
        supporting_citations = self._citations(
            synthesis.supporting_citation_ids,
            available_citations,
        )
        synthesis_assumptions = self._unique(
            evidence.research_gaps.important_assumptions + synthesis.assumptions
        )
        synthesis_uncertainties = self._unique(
            synthesis.important_uncertainties + synthesis.uncertainties
        )

        generated_findings = []
        for item in synthesis.main_documented_findings:
            finding = self._validate_generated_finding(
                item,
                available_citations,
                evidence.records,
            )
            generated_findings.append(finding)

        detected_gaps = [
            f"{item.parameter} ({item.scenario_value}): {item.explanation}"
            for item in (
                evidence.research_gaps.partially_supported_parameters
                + evidence.research_gaps.unsupported_parameters
            )
        ]
        synthesis_gap_text = self._unique(synthesis.research_gaps + detected_gaps)
        synthesis_detail = MissionSynthesisDetails(
            combined_assessment=synthesis.combined_assessment or "No synthesis claim passed evidence validation.",
            conflict_assessment=synthesis.conflict_assessment,
            main_documented_findings=generated_findings,
            important_uncertainties=synthesis_uncertainties,
            research_gaps=synthesis_gap_text,
            conflicting_claims=synthesis.conflicting_claims,
            supporting_citations=supporting_citations,
        )
        synthesizer = SpecialistAnalysis(
            role="Mission Safety Synthesizer",
            analysis=synthesis.analysis or "No synthesis claim passed evidence validation.",
            relevant_evidence=synthesis_refs,
            evidence_status=self._evidence_status(synthesis_refs, synthesis_citations),
            evidence_validation_status=synthesis_validation_status,
            evidence_validation_issues=synthesis_issues,
            evidence_validation_diagnostics=synthesis_diagnostics,
            assumptions=synthesis_assumptions,
            uncertainties=synthesis_uncertainties,
            citations=synthesis_citations,
        )
        specialist_outputs.append(synthesizer)

        overall_status = self._overall_evidence_status(evidence)
        limitations = self._unique(
            evidence.limitations
            + [
                item.explanation
                for item in evidence.research_gaps.unsupported_parameters
            ]
        )
        return MissionAnalysisResponse(
            environment=parameters.environment,
            scenario_parameters=parameters,
            specialist_analyses=specialist_outputs,
            mission_synthesis=synthesis.combined_assessment or "No synthesis claim passed evidence validation.",
            synthesis_details=synthesis_detail,
            citations=evidence.citations,
            evidence_matches=evidence.records,
            research_gaps=evidence.research_gaps,
            evidence_status=overall_status,
            evidence_validation_status="partial" if validation_issues else "complete",
            evidence_validation_issues=self._unique(validation_issues),
            evidence_validation_diagnostics=validation_diagnostics,
            evidence_limitations=limitations,
            disclaimer=(
                "Research support for a hypothetical scenario only. Local evidence "
                "may be provenance-unverified; this is not a safety certification, "
                "operational instruction, or flight clearance."
            ),
        )

    async def _add_ntrs_metadata(self, evidence: MissionEvidenceBundle, parameters):
        query = " ".join((
            parameters.material,
            parameters.environment,
            parameters.gravity,
            "spacecraft combustion",
        ))
        live_records = await self.ntrs_service.search_citations(query, limit=5)
        existing_citation_ids = {citation.citation_id for citation in evidence.citations}
        for record in live_records:
            citation_id = f"NTRS:{record['ntrs_id']}"
            if citation_id in existing_citation_ids:
                continue
            evidence.citations.append(MissionCitation(
                citation_id=citation_id,
                title=record["title"],
                source=record.get("source") or "NASA Technical Reports Server (NTRS)",
                authors=record.get("authors"),
                year=record.get("year"),
                identifier=record.get("ntrs_id"),
                doi=record.get("doi"),
                url=record.get("url"),
                evidence_status="Publication metadata retrieved; measurements not verified",
                evidence_class="publication_metadata_only",
                relevance_explanation=(
                    f"Retrieved by an NTRS metadata search for {query}. This result is "
                    "publication metadata, not a retrieved NASA PSI dataset or verified measurement."
                ),
                relevance_snippet=record.get("abstract"),
            ))
            evidence.context += (
                f"\nNTRS publication metadata ID {citation_id}: {record['title']}; "
                f"abstract={record.get('abstract') or 'not supplied'}; "
                "publication metadata only, measurements not verified.\n"
            )
            existing_citation_ids.add(citation_id)

    @staticmethod
    def _claim_reference_example(evidence):
        for record in evidence.records:
            citations = record.publications or [
                citation for citation in evidence.citations
                if citation.investigation_acronym == record.investigation_acronym
            ]
            if not citations:
                continue
            excerpt = next((
                value for value in (
                    record.fuel_types,
                    record.experiment_type,
                    record.investigation_title,
                    record.measured_parameters,
                ) if value
            ), None)
            if not excerpt:
                continue
            if record.evidence_class == "local_provenance_unverified":
                prefix = f"The local provenance-unverified {record.investigation_acronym} record"
            elif record.evidence_class == "verified_nasa_source":
                prefix = f"NASA PSI metadata for {record.investigation_acronym}"
            else:
                prefix = f"The retrieved publication metadata for {record.investigation_acronym}"
            claim_text = f'{prefix} lists "{excerpt}" in its stored record.'
            return {
                "claim_text": claim_text,
                "claim_type": "evidence_summary",
                "sources": [{
                    "evidence_id": record.evidence_id,
                    "citation_ids": [citations[0].citation_id],
                    "source_excerpt": excerpt,
                    "provenance_status": record.evidence_status,
                }],
                "uncertainty": "This record description is not independent verification of the underlying experiment.",
            }
        return {
            "claim_text": "This hypothetical scenario's outcome remains uncertain.",
            "claim_type": "hypothetical_inference",
            "sources": [],
            "uncertainty": "No retrieved record establishes this combined scenario.",
        }

    async def _generate_specialists(self, parameters, question, evidence):
        scenario_payload = parameters.model_dump(mode="json")
        claim_example = self._claim_reference_example(evidence)
        role_examples = ",\n".join(
            json.dumps({
                "role": role,
                "scenario_parameters": scenario_payload,
                "claims": [claim_example],
            })
            for role in FIRST_FOUR_SPECIALIST_ROLES
        )
        prompt = f"""
You coordinate four independent research specialists. Each receives the same validated hypothetical scenario and the same retrieved evidence packet. Return only structured claims; the backend constructs the displayed analysis from claims that pass evidence validation.

SCENARIO (user inputs, not measurements):
{json.dumps(parameters.model_dump(mode="json"), indent=2)}

RESEARCH QUESTION:
{question or "Analyze the scenario using available research evidence."}

RETRIEVED EVIDENCE PACKET:
{evidence.context}

RESPONSIBILITIES:
- Combustion Analyst: combustion modes, flame behavior, extinction, and soot only where supplied records support discussion.
- Atmosphere Analyst: oxygen, diluents, pressure, and atmosphere-condition evidence.
- Material Safety Analyst: fuel/material relevance and material-test evidence.
- Fire Suppression Analyst: documented extinction/suppression evidence and limits.

CLAIM OUTPUT RULES:
- Return claims as the only analysis content. Each claim is exactly one user-facing sentence; do not return a second free-text analysis or duplicate global source-ID arrays.
- Each claim object has claim_text, claim_type, sources, and uncertainty. claim_type must be one of evidence_summary, historical_experimental, hypothetical_inference, general_scientific_context, unsupported.
- Each sources item has evidence_id, citation_ids, source_excerpt, provenance_status. Copy evidence_id and citation IDs exactly from the same record section in the packet. Use a source excerpt that appears verbatim in that retrieved record, finding, citation title, or source snippet. Copy its evidence status exactly.
- An evidence_summary must identify its record in claim_text and quote its source_excerpt verbatim. It may summarize record contents only. Do not claim the quoted metadata is a verified experimental finding.
- A historical_experimental claim must quote exact result wording from a retrieved finding/source excerpt, include the matching evidence and citation IDs, and preserve provenance status. Metadata-only sources cannot support an experimental result.
- A hypothetical_inference must explicitly use conditional or inference language in claim_text and fill uncertainty. Never present it as observed or tested. Related evidence may be listed as context, but IDs must map to the same cited record.
- general_scientific_context must be general explanation with sources empty; do not attribute it to a NASA experiment. Unsupported claims must be omitted or classified unsupported; unsupported claims are rejected.
- The 12 legacy local datapoints are not verified NASA flight measurements. NASA PSI source linkage does not independently validate conditions or measurements. NTRS is publication metadata only.
- Never combine separate condition matches as one experiment. Do not infer lunar gravity from microgravity. Do not invent values, risk scores, suppression thresholds, citations, safety advice, or certifications.
- Echo the exact scenario object for each role. Do not round or replace any value.

EXAMPLE CLAIM WITH IDS FROM THIS EVIDENCE PACKET (use only if the quoted field is relevant):
{json.dumps(claim_example, indent=2)}

Return JSON with exactly four roles and this structure:
{{"specialist_analyses":[
{role_examples}
]}}
"""
        return await self._generate_json(prompt, SpecialistStageResult, "specialist analysis")

    async def _generate_synthesis(self, parameters, question, evidence, specialists):
        specialist_handoff = self._format_specialist_evidence_handoff(specialists, evidence)
        scenario_json = json.dumps(parameters.model_dump(mode="json"), indent=2)
        claim_example = self._claim_reference_example(evidence)
        prompt = f"""
You are the Mission Safety Synthesizer, the fifth logical specialist. Synthesize only the four specialists' validated structured claims and the retrieved packet.

SCENARIO (authoritative exact user inputs):
{scenario_json}

RESEARCH QUESTION:
{question or "Analyze the scenario using available research evidence."}

SHARED RETRIEVED EVIDENCE PACKET:
{evidence.context}

VALIDATED SPECIALIST HANDOFF:
{json.dumps(specialist_handoff, indent=2)}

SYNTHESIS RULES:
- The handoff contains only claims that passed specialist-level validation. Some roles may be partial or have no valid claims; explicitly disclose this in research_gaps and uncertainties. Do not treat missing specialist output as agreement.
- Return analysis_claims and combined_assessment_claims as structured claim arrays. Displayed prose is constructed from those claims; do not provide parallel free text.
- Every claim has claim_text, claim_type, sources, and uncertainty. Each source reference has evidence_id, citation_ids, source_excerpt, provenance_status. Copy valid IDs only from the same retrieved record. Do not transfer a citation from one specialist/record to an unrelated claim.
- evidence_summary claims identify the source in claim_text and quote source_excerpt verbatim. Historical experimental claims quote exact retrieved result wording; source metadata alone cannot support experimental results.
- hypothetical_inference claims explicitly label the inference or condition in claim_text and state uncertainty. General scientific context is uncited and cannot imply a particular experiment established it. Unsupported claims must be omitted or classified unsupported; unsupported claims will be omitted from the final response.
- Preserve evidence classes: local records are provenance-unverified; NASA PSI metadata establishes source linkage only; NTRS records are publication metadata. Do not present the 12 local datapoints as verified NASA flight measurements.
- Do not infer lunar-gravity outcomes from microgravity. Never imply that separate conditions were tested together. Do not invent values, findings, citations, risk scores, thresholds, recommendations, or certifications.
- List conflicts between the validated specialists and name both roles. If none among available validated claims, state so while still disclosing any missing/partial role.
- Copy main_documented_findings exactly from a supplied local finding and cite a publication belonging to that investigation. Return an empty array if no exact finding applies.
- Preserve the scenario values exactly.

Reference shape for a source-backed claim:
{json.dumps(claim_example, indent=2)}

Return only JSON:
{{
  "scenario_parameters": {scenario_json},
  "analysis_claims": [{json.dumps(claim_example)}],
  "combined_assessment_claims": [{json.dumps(claim_example)}],
  "conflict_assessment": "No conflicts identified among the validated specialist claims.",
  "main_documented_findings": [],
  "conflicting_claims": [],
  "important_uncertainties": [],
  "research_gaps": [],
  "supporting_citation_ids": []
}}
"""
        return await self._generate_json(prompt, SynthesisDraft, "mission synthesis")

    @staticmethod
    def _format_specialist_evidence_handoff(specialists, evidence):
        records = {record.evidence_id: record for record in evidence.records}
        citations = {citation.citation_id: citation for citation in evidence.citations}
        handoff = []
        for draft, validation_status, validation_issues, validation_diagnostics in specialists:
            selected_evidence_ids = _unique(
                source.evidence_id for claim in draft.claims for source in claim.sources
            )
            selected_citation_ids = _unique(
                citation_id
                for claim in draft.claims
                for source in claim.sources
                for citation_id in source.citation_ids
            )
            handoff.append({
                "role": draft.role,
                "scenario_parameters": draft.scenario_parameters.model_dump(mode="json"),
                "validated_claims": [claim.model_dump(mode="json") for claim in draft.claims],
                "validation_status": validation_status,
                "validation_issues": validation_issues,
                "validation_diagnostics": [item.model_dump(mode="json") for item in validation_diagnostics],
                "selected_evidence_records": [
                    records[item].model_dump(mode="json") for item in selected_evidence_ids if item in records
                ],
                "selected_citation_records": [
                    citations[item].model_dump(mode="json") for item in selected_citation_ids if item in citations
                ],
            })
        return {
            "specialists": handoff,
            "evidence_limitations": evidence.limitations,
            "research_gaps": evidence.research_gaps.model_dump(mode="json"),
        }

    async def _generate_json(self, prompt, result_model, stage_name):
        try:
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=self.model,
                contents=prompt,
            )
        except Exception as exc:
            category, http_status, provider_status = self._provider_failure_details(exc)
            logger.error(
                "Gemini provider call failed: stage=%s model=%s category=%s "
                "provider_http_status=%s provider_status=%s error_type=%s",
                stage_name,
                self.model,
                category,
                http_status or "unavailable",
                provider_status or "unavailable",
                type(exc).__name__,
            )
            status_detail = f" (HTTP {http_status})" if http_status else ""
            raise RuntimeError(
                "Gemini mission analysis is temporarily unavailable: "
                f"provider error category={category}{status_detail}."
            ) from None

        sdk_http_response = getattr(response, "sdk_http_response", None)
        provider_http_status = getattr(sdk_http_response, "status_code", None)
        logger.info(
            "Gemini provider call completed: stage=%s model=%s provider_status=%s",
            stage_name,
            self.model,
            provider_http_status if provider_http_status is not None else "success",
        )

        response_text = getattr(response, "text", None)
        if not isinstance(response_text, str) or not response_text.strip():
            raise RuntimeError(f"Gemini returned an empty {stage_name} response.")
        response_text = response_text.strip()
        if response_text.startswith("```"):
            response_text = response_text.split("\n", 1)[-1]
            response_text = response_text.rsplit("```", 1)[0].strip()
        try:
            parsed = json.loads(response_text)
            return result_model.model_validate(parsed)
        except (json.JSONDecodeError, ValidationError, TypeError, ValueError) as exc:
            error_count = 1
            if isinstance(exc, ValidationError):
                error_count = len(exc.errors(include_input=False, include_context=False, include_url=False))
            logger.warning(
                "Gemini response parser/schema mismatch: stage=%s reason_code=parser_schema_mismatch "
                "error_type=%s error_count=%d",
                stage_name,
                type(exc).__name__,
                error_count,
            )
            raise RuntimeError(
                f"Gemini returned an invalid {stage_name} response (parser_schema_mismatch). Please retry."
            ) from exc

    @staticmethod
    def _provider_failure_details(exc):
        """Return safe provider failure metadata without logging response bodies."""
        http_status = getattr(exc, "code", None)
        if not isinstance(http_status, int):
            http_status = getattr(exc, "status_code", None)
        if not isinstance(http_status, int):
            http_status = None

        provider_status = getattr(exc, "status", None)
        if not isinstance(provider_status, str) or not re.fullmatch(r"[A-Z_]{2,64}", provider_status):
            provider_status = None

        class_name = type(exc).__name__.lower()
        if http_status == 401 or provider_status == "UNAUTHENTICATED":
            category = "authentication"
        elif http_status == 403 or provider_status == "PERMISSION_DENIED":
            category = "permission_denied"
        elif http_status == 404 or provider_status == "NOT_FOUND":
            category = "model_or_endpoint_unavailable"
        elif http_status == 429 or provider_status in {"RESOURCE_EXHAUSTED", "RATE_LIMIT_EXCEEDED"}:
            category = "quota_or_rate_limit"
        elif http_status == 400 or provider_status == "INVALID_ARGUMENT":
            category = "invalid_provider_request"
        elif isinstance(exc, (TimeoutError, asyncio.TimeoutError)) or any(
            marker in class_name for marker in ("timeout", "connect", "network")
        ):
            category = "network_or_timeout"
        elif http_status is not None and http_status >= 500:
            category = "provider_server_error"
        elif isinstance(exc, OSError):
            category = "network_or_timeout"
        else:
            category = "provider_request_error"
        return category, http_status, provider_status

    def _validate_references(self, record_ids, citation_ids, records, citations):
        unknown_records = sorted(set(record_ids) - set(records))
        unknown_citations = sorted(set(citation_ids) - set(citations))
        if unknown_records or unknown_citations:
            raise RuntimeError(
                "Gemini referenced evidence or citations that were not retrieved; "
                "the response was rejected to prevent fabricated sources."
            )

    @staticmethod
    def _validate_scenario_echo(echo, parameters, role):
        if echo.model_dump(mode="json") != parameters.model_dump(mode="json"):
            raise RuntimeError(
                f"Gemini {role} output changed the validated scenario inputs; the response was rejected."
            )

    @staticmethod
    def _specialist_text(specialist):
        return "\n".join([
            specialist.analysis,
            *specialist.assumptions,
            *specialist.uncertainties,
        ])

    @staticmethod
    def _synthesis_text(synthesis):
        return "\n".join([
            synthesis.analysis,
            synthesis.combined_assessment,
            *synthesis.conflicting_claims,
            *synthesis.important_uncertainties,
            *synthesis.research_gaps,
            *synthesis.assumptions,
            *synthesis.uncertainties,
        ])

    @staticmethod
    def _validate_generated_text(text, parameters, role):
        ungrounded_joint_test = re.compile(
            r"\b(?:(?:the|this)\s+)?(?:full|combined|entire|exact)\s+"
            r"(?:scenario|parameter combination|condition set)\b"
            r".{0,80}\b(?:was|were|has been|have been|is)\s+"
            r"(?:experimentally\s+)?(?:tested|measured|demonstrated|validated|verified)\b",
            re.IGNORECASE,
        )
        if ungrounded_joint_test.search(text):
            raise ClaimValidationFailure(
                "unsupported_combined_scenario_claim",
                f"Gemini {role} output claims the combined scenario was tested without joint source evidence; the response was rejected."
            )

        unsupported_numeric_claim = re.compile(
            r"\b(?:risk(?:\s+(?:score|percentage|probability))?|threshold|suppression\s+limit)\b"
            r"[^.\n]{0,50}\b\d+(?:\.\d+)?\s*(?:%|/\s*100)?",
            re.IGNORECASE,
        )
        if unsupported_numeric_claim.search(text):
            raise ClaimValidationFailure(
                "unsupported_numeric_risk_or_threshold",
                f"Gemini {role} output contains an unsupported numeric risk or threshold claim; the response was rejected."
            )

        checks = (
            (re.compile(r"(?P<value>\d+(?:\.\d+)?)\s*%\s*(?:O2|oxygen)?", re.IGNORECASE), parameters.oxygen_percent, "oxygen"),
            (re.compile(r"(?P<value>\d+(?:\.\d+)?)\s*(?:atm|atmospheres?)\b", re.IGNORECASE), parameters.pressure_atm, "pressure"),
            (re.compile(r"(?P<value>\d+(?:\.\d+)?)\s*(?:cm\s*/\s*s|cm\s*s(?:\^?-?1|⁻¹))\b", re.IGNORECASE), parameters.airflow_cm_s, "airflow"),
        )
        for pattern, expected, name in checks:
            for match in pattern.finditer(text):
                if not math.isclose(float(match.group("value")), expected, rel_tol=0.0, abs_tol=1e-12):
                    raise ClaimValidationFailure(
                        "scenario_value_mismatch",
                        f"Gemini {role} output contains a {name} value that conflicts with the exact scenario; the response was rejected."
                    )

    @staticmethod
    def _validate_conflicting_claims(conflicts):
        role_names = set(FIRST_FOUR_SPECIALIST_ROLES)
        for conflict in conflicts:
            named_roles = [role for role in role_names if role in conflict]
            if len(named_roles) < 2:
                raise RuntimeError(
                    "Gemini synthesis listed a conflict without identifying at least two specialist roles."
                )

    def _filter_claims(self, claims, parameters, role, available_citations, available_records):
        accepted = []
        issues = []
        diagnostics = []
        if not claims:
            return [], [f"{role}: no structured claims were returned by the specialist."], diagnostics

        for claim_index, claim in enumerate(claims):
            try:
                self._validate_generated_text(claim.claim_text, parameters, role)
                self._validate_claim(claim, role, available_citations, available_records)
            except ClaimValidationFailure as exc:
                diagnostic = self._build_validation_diagnostic(
                    claim,
                    role,
                    claim_index,
                    exc.reason_code,
                    str(exc),
                    available_citations,
                    available_records,
                )
                diagnostics.append(diagnostic)
                logger.warning(
                    "Mission claim omitted: role=%s claim_index=%d classification=%s reason_code=%s "
                    "evidence_references_supplied=%s evidence_ids_valid=%s citation_ids_supplied=%s "
                    "citation_ids_valid=%s citation_investigation_match=%s provenance_restriction_rejected=%s "
                    "historical_source_text_match=%s",
                    diagnostic.role,
                    diagnostic.claim_index,
                    diagnostic.claim_classification,
                    diagnostic.reason_code,
                    diagnostic.evidence_references_supplied,
                    diagnostic.evidence_ids_valid,
                    diagnostic.citation_ids_supplied,
                    diagnostic.citation_ids_valid,
                    diagnostic.citation_investigation_match,
                    diagnostic.provenance_restriction_rejected,
                    diagnostic.historical_source_text_match,
                )
                issues.append(
                    f"{role} claim {claim_index} omitted: {diagnostic.reason_code} — {diagnostic.reason}"
                )
            else:
                accepted.append(claim)
        return accepted, self._unique(issues), diagnostics

    @staticmethod
    def _build_validation_diagnostic(
        claim,
        role,
        claim_index,
        reason_code,
        reason,
        available_citations,
        available_records,
    ):
        source_refs = claim.sources
        evidence_ids = [source.evidence_id for source in source_refs]
        citation_ids = [citation_id for source in source_refs for citation_id in source.citation_ids]
        evidence_ids_valid = (
            all(evidence_id and evidence_id in available_records for evidence_id in evidence_ids)
            if source_refs else None
        )
        citation_ids_valid = (
            all(citation_id in available_citations for citation_id in citation_ids)
            if citation_ids else None
        )

        citation_investigation_match = None
        if evidence_ids_valid and citation_ids_valid:
            matches = []
            for source in source_refs:
                record = available_records[source.evidence_id]
                associated_ids = {
                    item.citation_id for item in getattr(record, "publications", [])
                    if getattr(item, "citation_id", None)
                }
                for citation_id in source.citation_ids:
                    citation = available_citations[citation_id]
                    matches.append(
                        citation_id in associated_ids
                        or bool(record.investigation_acronym)
                        and citation.investigation_acronym == record.investigation_acronym
                    )
            citation_investigation_match = bool(matches) and all(matches)

        historical_source_text_match = None
        if claim.claim_type == "historical_experimental":
            if evidence_ids_valid and citation_ids_valid and citation_investigation_match:
                source_matches = []
                for source in source_refs:
                    record = available_records[source.evidence_id]
                    citations = [available_citations[item] for item in source.citation_ids]
                    result_text = [
                        item.finding_text for item in record.findings if item.finding_text
                    ] + [
                        citation.relevance_snippet
                        for citation in citations
                        if citation.relevance_snippet
                        and citation.evidence_class != "publication_metadata_only"
                    ]
                    excerpt = MissionIntelligenceService._normalized_source_text(source.source_excerpt)
                    source_matches.append(bool(excerpt) and any(
                        excerpt in MissionIntelligenceService._normalized_source_text(item)
                        for item in result_text
                    ) and excerpt in MissionIntelligenceService._normalized_source_text(claim.claim_text))
                historical_source_text_match = bool(source_matches) and all(source_matches)

        provenance_codes = {
            "provenance_status_mismatch",
            "historical_provenance_uncertainty_missing",
            "local_provenance_not_disclosed",
            "publication_metadata_only",
            "nasa_source_linkage_overstated",
        }
        allowed_classifications = {
            "evidence_summary",
            "historical_experimental",
            "hypothetical_inference",
            "general_scientific_context",
            "unsupported",
        }
        return EvidenceValidationDiagnostic(
            role=role,
            claim_index=claim_index,
            claim_classification=(
                claim.claim_type if claim.claim_type in allowed_classifications else "invalid"
            ),
            reason_code=reason_code,
            reason=reason,
            evidence_references_supplied=bool(source_refs),
            evidence_ids_valid=evidence_ids_valid,
            citation_ids_supplied=bool(citation_ids),
            citation_ids_valid=citation_ids_valid,
            citation_investigation_match=citation_investigation_match,
            provenance_restriction_rejected=reason_code in provenance_codes,
            historical_source_text_match=historical_source_text_match,
        )

    @staticmethod
    def _validation_state(submitted_claims, accepted_claims):
        if not accepted_claims:
            return "no_valid_claims"
        if len(accepted_claims) < len(submitted_claims):
            return "partial"
        return "validated"

    @staticmethod
    def _normalized_source_text(text):
        return re.sub(r"[^a-z0-9]+", " ", str(text or "").casefold()).strip()

    def _validate_claim(self, claim, role, available_citations, available_records):
        claim_type = claim.claim_type
        claim_text = claim.claim_text
        if claim_type == "unsupported":
            raise ClaimValidationFailure("unsupported_claim", "Claim was explicitly classified as unsupported.")
        if claim_type not in {
            "evidence_summary",
            "historical_experimental",
            "hypothetical_inference",
            "general_scientific_context",
        }:
            raise ClaimValidationFailure("invalid_claim_classification", "Claim classification is not supported.")

        source_context = re.compile(
            r"\b(?:evidence|record|investigation|experiment|study|publication|paper|"
            r"NASA|PSI|NTRS|flight data|research finding)\b",
            re.IGNORECASE,
        )
        uncertainty_language = re.compile(
            r"\b(?:may|might|could|possibly|potentially|uncertain|unknown|not established|"
            r"not supported|insufficient evidence|cannot conclude|inference|hypothetical)\b",
            re.IGNORECASE,
        )
        if claim_type == "general_scientific_context":
            if claim.sources or source_context.search(claim_text):
                raise ClaimValidationFailure("general_context_attributed_to_source", "general context was attributed to a source")
            return
        if claim_type == "hypothetical_inference":
            if not claim.uncertainty.strip() or not uncertainty_language.search(claim_text):
                raise ClaimValidationFailure("hypothetical_missing_uncertainty", "hypothetical inference is not explicitly uncertain")
            if re.search(
                r"\b(?:was|were|has been|have been|had been)\s+(?!(?:not|never)\b)[a-z][a-z-]*(?:ed|en)\b",
                claim_text,
                re.IGNORECASE,
            ):
                raise ClaimValidationFailure("historical_claim_mislabeled_as_hypothetical", "Historical wording was labelled as a hypothetical inference.")
            if source_context.search(claim_text) and not claim.sources and not re.search(
                r"\b(?:no|none|not|without|unavailable|insufficient|unknown|lack(?:s|ing)?)\b",
                claim_text,
                re.IGNORECASE,
            ):
                raise ClaimValidationFailure("hypothetical_missing_source_reference", "A source-based hypothetical claim has no source link.")

        if claim_type in {"evidence_summary", "historical_experimental"} and not claim.sources:
            raise ClaimValidationFailure("missing_source_reference", "source-backed claim has no record citations")
        if claim_type == "historical_experimental" and not claim.uncertainty.strip():
            # Historical source reports may be described, but provenance limitations must be stated.
            raise ClaimValidationFailure("historical_provenance_uncertainty_missing", "Historical claim omits provenance uncertainty.")

        for source in claim.sources:
            record = available_records.get(source.evidence_id)
            if record is None:
                raise ClaimValidationFailure("unknown_evidence_id", "claim references an unavailable evidence record")
            if not source.citation_ids:
                raise ClaimValidationFailure("missing_citation_id", "claim source has no citation IDs")
            citations = []
            for citation_id in source.citation_ids:
                citation = available_citations.get(citation_id)
                if citation is None:
                    raise ClaimValidationFailure("unknown_citation_id", "Claim references a citation that was not retrieved.")
                associated_ids = {
                    item.citation_id for item in getattr(record, "publications", [])
                    if getattr(item, "citation_id", None)
                }
                if citation_id not in associated_ids and (
                    not record.investigation_acronym
                    or citation.investigation_acronym != record.investigation_acronym
                ):
                    raise ClaimValidationFailure("mismatched_investigation", "claim citation belongs to another investigation")
                citations.append(citation)

            allowed_statuses = {
                record.evidence_status,
                record.evidence_class,
                *(citation.evidence_status for citation in citations),
                *(citation.evidence_class for citation in citations),
            }
            if source.provenance_status not in allowed_statuses:
                raise ClaimValidationFailure("provenance_status_mismatch", "Claim provenance label does not match the retrieved source.")

            metadata_text = [
                record.evidence_id,
                record.investigation_acronym,
                record.investigation_title,
                record.experiment_type,
                record.fuel_types,
                record.oxidizer_environment,
                record.gravity_environment,
                record.facility,
                record.flight_mission,
                record.measured_parameters,
            ]
            finding_text = [
                item.finding_text for item in record.findings if item.finding_text
            ]
            citation_text = [
                item.title for item in citations
            ] + [
                item.identifier for item in citations if item.identifier
            ] + [
                item.doi for item in citations if item.doi
            ] + [
                item.relevance_snippet for item in citations if item.relevance_snippet
            ]
            available_source_text = [item for item in metadata_text + finding_text + citation_text if item]
            excerpt = self._normalized_source_text(source.source_excerpt)
            if not excerpt or not any(
                excerpt in self._normalized_source_text(item) for item in available_source_text
            ):
                code = "unsupported_historical_claim" if claim_type == "historical_experimental" else "source_excerpt_not_retrieved"
                raise ClaimValidationFailure(code, "Claim excerpt is absent from the retrieved evidence packet.")

            source_anchor_values = [
                record.evidence_id,
                record.investigation_acronym,
                record.investigation_title,
                *(citation.identifier for citation in citations if citation.identifier),
            ]
            if not any(
                anchor and str(anchor).casefold() in claim_text.casefold()
                for anchor in source_anchor_values
            ):
                raise ClaimValidationFailure("source_anchor_missing", "Claim text does not identify its cited source.")

            if claim_type == "evidence_summary":
                if excerpt not in self._normalized_source_text(claim_text):
                    raise ClaimValidationFailure("evidence_summary_excerpt_mismatch", "Evidence summary does not quote its retrieved excerpt.")
            else:
                supported_result_text = finding_text + [
                    citation.relevance_snippet
                    for citation in citations
                    if citation.relevance_snippet
                    and citation.evidence_class != "publication_metadata_only"
                ]
                if not any(
                    excerpt in self._normalized_source_text(item)
                    for item in supported_result_text
                ) or excerpt not in self._normalized_source_text(claim_text):
                    raise ClaimValidationFailure("unsupported_historical_claim", "Historical result is not quoted from a retrieved finding/source excerpt.")

            if record.evidence_class == "local_provenance_unverified" and not re.search(
                r"\b(?:local|unverified|provenance)\b", claim_text, re.IGNORECASE
            ):
                raise ClaimValidationFailure("local_provenance_not_disclosed", "Local source provenance was omitted from claim wording.")
            for citation in citations:
                if citation.evidence_class == "publication_metadata_only":
                    if claim_type == "historical_experimental" or not re.search(
                        r"\b(?:publication|abstract|metadata)\b", claim_text, re.IGNORECASE
                    ):
                        raise ClaimValidationFailure("publication_metadata_only", "Publication metadata was used as experimental evidence.")
                if citation.evidence_class == "verified_nasa_source" and not re.search(
                    r"\b(?:metadata|source linkage)\b", claim_text, re.IGNORECASE
                ):
                    raise ClaimValidationFailure("nasa_source_linkage_overstated", "NASA source linkage was overstated as validated measurement evidence.")

    @staticmethod
    def _validate_conflict_assessment(conflicts, assessment):
        normalized = assessment.lower()
        if not conflicts and not re.search(
            r"\b(?:no conflicts?|no inconsistencies|no conflicting claims)\b",
            normalized,
        ):
            raise RuntimeError(
                "Gemini synthesis must explicitly report when no specialist conflicts were found."
            )
        if conflicts and not re.search(r"\bconflict|inconsisten", normalized):
            raise RuntimeError(
                "Gemini synthesis conflict assessment does not describe the listed conflicts."
            )

    def _record_references(self, record_ids, records):
        return [
            EvidenceReference(
                evidence_id=records[item].evidence_id,
                investigation_title=records[item].investigation_title,
                investigation_acronym=records[item].investigation_acronym,
                original_source_url=records[item].original_source_url,
                evidence_status=records[item].evidence_status,
            evidence_class=records[item].evidence_class,
                relevance_explanation=records[item].relevance_explanation,
            )
            for item in dict.fromkeys(record_ids)
        ]

    @staticmethod
    def _citations(citation_ids, citations):
        return [citations[item] for item in dict.fromkeys(citation_ids)]

    @staticmethod
    def _evidence_status(references, citations):
        statuses = {item.evidence_status for item in citations}
        statuses.update(item.evidence_status for item in references)
        if not statuses:
            return "Insufficient evidence"
        if statuses == {"Local record — provenance unverified"}:
            return "Local record — provenance unverified"
        if "Publication metadata retrieved; measurements not verified" in statuses:
            if "Local record — provenance unverified" in statuses:
                return "Local records unverified; publication metadata retrieved, measurements not verified"
            return "Publication metadata retrieved; measurements not verified"
        return "; ".join(sorted(statuses))

    @staticmethod
    def _overall_evidence_status(evidence):
        if not evidence.records:
            if evidence.citations:
                return "Publication metadata retrieved; measurements not verified"
            return "Insufficient evidence"
        has_psi = any(record.evidence_class == "verified_nasa_source" for record in evidence.records)
        has_local = any(record.evidence_class == "local_provenance_unverified" for record in evidence.records)
        descriptions = ["No NASA experimental measurement provenance was established"]
        if has_psi:
            descriptions.append("PSI investigation source links are verified, but test conditions and measurement provenance are not independently validated")
        if has_local:
            descriptions.append("local seed records remain provenance-unverified")
        if any(citation.evidence_class == "publication_metadata_only" for citation in evidence.citations):
            descriptions.append("publication metadata does not establish measurement provenance")
        return "; ".join(descriptions) + "."

    @staticmethod
    def _validate_generated_finding(item, citations, evidence_records):
        if not isinstance(item, dict) or set(item) != {"finding", "citation_ids"}:
            raise RuntimeError("Gemini returned an invalid documented-finding structure.")
        finding = item["finding"]
        citation_ids = item["citation_ids"]
        if not isinstance(finding, str) or not finding.strip() or not isinstance(citation_ids, list) or not citation_ids:
            raise RuntimeError("Gemini returned a finding without a supported citation reference.")
        unknown = sorted(set(citation_ids) - set(citations))
        if unknown:
            raise RuntimeError("Gemini returned an unsupported citation reference; the response was rejected.")
        matching_records = [
            record
            for record in evidence_records
            if any(
                finding.strip() == source_finding.finding_text.strip()
                for source_finding in record.findings
            )
        ]
        if not matching_records:
            raise RuntimeError(
                "Gemini returned a documented finding that does not exactly match a retrieved record."
            )
        allowed_citation_ids = {
            citation.citation_id
            for record in matching_records
            for citation in citations.values()
            if citation.investigation_acronym == record.investigation_acronym
        }
        if not allowed_citation_ids.intersection(citation_ids):
            raise RuntimeError(
                "Gemini returned a documented finding without a citation associated with its investigation."
            )
        return DocumentedFinding(
            finding=finding,
            citations=MissionIntelligenceService._citations(citation_ids, citations),
        )

    @staticmethod
    def _unique(items):
        return list(dict.fromkeys(item for item in items if item))
