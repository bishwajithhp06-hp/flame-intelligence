import json
import re
from dataclasses import dataclass
from types import SimpleNamespace
from typing import List, Optional

from sqlalchemy.orm import Session, joinedload

from app.models.investigation import Investigation
from app.models.nasa_data import ProcessedResearchRecord
from app.schemas.mission import (
    EvidenceFinding,
    EvidenceParameterMatch,
    MissionCitation,
    MissionEvidenceRecord,
    MissionParameters,
    ResearchGapAssessment,
    ResearchGapReport,
)


LOCAL_EVIDENCE_STATUS = "Local record — provenance unverified"
DOMAIN_TERMS = (
    "combustion", "flame", "fire", "flammability", "extinguish", "soot", "burning"
)


@dataclass
class MissionEvidenceBundle:
    records: List[MissionEvidenceRecord]
    citations: List[MissionCitation]
    research_gaps: ResearchGapReport
    limitations: List[str]
    context: str


class MissionEvidenceService:
    """Retrieves local research metadata and explains condition-level matches.

    Matching examines investigation metadata and narrative conditions only. It
    intentionally never reads CombustionDataPoint rows because their legacy
    measured-flight flag does not establish measurement provenance.
    """

    MATERIAL_TERMS = {
        "n-heptane": ("n-heptane", "heptane"),
        "pmma": ("pmma", "polymethyl methacrylate"),
        "cotton-fabric": ("cotton", "fabric", "sibal"),
        "gas-jet": ("gas-jet", "gas jet", "gaseous hydrocarbon", "methane", "ethylene", "propane"),
        "nomex": ("nomex",),
    }
    MATERIAL_LABELS = {
        "n-heptane": "n-Heptane",
        "pmma": "PMMA",
        "cotton-fabric": "Cotton/fabric",
        "gas-jet": "Gaseous fuel jet",
        "nomex": "Nomex",
    }
    PRESSURE_UNITS_TO_ATM = {"atm": 1.0, "psi": 1 / 14.6959, "bar": 0.986923}
    NUMBER = r"\d+(?:\.\d+)?"
    RANGE_SEPARATOR = r"(?:to|[-–])"

    def retrieve(
        self,
        db: Session,
        parameters: Optional[MissionParameters] = None,
        question: Optional[str] = None,
    ) -> MissionEvidenceBundle:
        investigations = (
            db.query(Investigation)
            .options(
                joinedload(Investigation.publications),
                joinedload(Investigation.findings),
            )
            .order_by(Investigation.updated_at.desc())
            .limit(50)
            .all()
        )

        records = []
        citations: List[MissionCitation] = []
        seen_citations = set()
        for investigation in investigations:
            matches = self._parameter_matches(investigation, parameters)
            if parameters is not None and not self._is_combustion_relevant(investigation, matches):
                continue

            relevance = self._relevance_explanation(investigation, matches, parameters)
            publication_citations = []
            for publication in investigation.publications:
                citation_id = (
                    f"{investigation.acronym}:"
                    f"{publication.ntrs_id or publication.doi or publication.id}"
                )
                citation = MissionCitation(
                    citation_id=citation_id,
                    title=publication.title,
                    source="Local publication record — provenance unverified",
                    authors=publication.authors,
                    year=publication.year,
                    identifier=publication.ntrs_id or investigation.ntrs_id,
                    doi=publication.doi,
                    url=publication.url or investigation.source_url,
                    evidence_status=LOCAL_EVIDENCE_STATUS,
                    evidence_class="local_provenance_unverified",
                    relevance_explanation=(
                        f"Publication is associated with {investigation.acronym}; {relevance}"
                    ),
                    relevance_snippet=(publication.abstract or "")[:400] or None,
                    investigation_acronym=investigation.acronym,
                )
                publication_citations.append(citation)
                if citation_id not in seen_citations:
                    citations.append(citation)
                    seen_citations.add(citation_id)

            source_citation_id = f"INV:{investigation.investigation_id}"
            if investigation.source_url:
                source_citation = MissionCitation(
                    citation_id=source_citation_id,
                    title=investigation.title,
                    source="Local investigation record — provenance unverified",
                    identifier=investigation.ntrs_id or investigation.investigation_id,
                    url=investigation.source_url,
                    evidence_status=LOCAL_EVIDENCE_STATUS,
                    evidence_class="local_provenance_unverified",
                    relevance_explanation=relevance,
                    relevance_snippet=(investigation.description or "")[:400] or None,
                    investigation_acronym=investigation.acronym,
                )
                if source_citation_id not in seen_citations:
                    citations.append(source_citation)
                    seen_citations.add(source_citation_id)

            record = MissionEvidenceRecord(
                evidence_id=investigation.investigation_id,
                investigation_title=investigation.title,
                investigation_acronym=investigation.acronym,
                original_source_url=investigation.source_url,
                experiment_type=investigation.category,
                facility=investigation.facility,
                flight_mission=investigation.flight_mission,
                fuel_types=investigation.fuel_types,
                oxidizer_environment=investigation.oxidizer_environment,
                gravity_environment=investigation.gravity_environment,
                measured_parameters=investigation.measured_parameters,
                evidence_status=LOCAL_EVIDENCE_STATUS,
                evidence_class="local_provenance_unverified",
                relevance_explanation=relevance,
                parameter_matches=matches,
                publications=publication_citations,
                findings=[
                    EvidenceFinding(
                        finding_text=finding.finding_text,
                        source_citation=finding.source_citation,
                        doi=finding.doi,
                        evidence_status=LOCAL_EVIDENCE_STATUS,
                    )
                    for finding in investigation.findings
                ],
            )
            records.append(record)

        # PSI investigation metadata fetched through the official repository
        # path has established source linkage, but that does not independently
        # validate experimental conditions or any measurement values.
        psi_records = (
            db.query(ProcessedResearchRecord)
            .filter(ProcessedResearchRecord.record_kind == "psi_investigation")
            .order_by(ProcessedResearchRecord.retrieved_at.desc())
            .limit(100)
            .all()
        )
        for stored in psi_records:
            metadata = _json_dict(stored.normalized_metadata_json)
            accession = str(metadata.get("accession") or stored.source_record_id)
            acronym = str(metadata.get("acronym") or accession)
            title = str(metadata.get("title") or stored.title or accession)
            source_url = stored.raw_record.source_url if stored.raw_record else None
            investigation_view = SimpleNamespace(
                title=title,
                acronym=acronym,
                category=stored.experiment_type or "NASA PSI investigation metadata",
                description=stored.description or "",
                objectives=metadata.get("objectives") or "",
                fuel_types=metadata.get("materials") or "",
                oxidizer_environment=metadata.get("experimental_conditions") or "",
                gravity_environment=(metadata.get("gravity_environment") or metadata.get("gravityEnvironment") or ""),
                facility=metadata.get("experiment_platform") or "",
                flight_mission=metadata.get("flight_program") or "",
                measured_parameters=metadata.get("measured_parameters") or "",
                key_findings="",
                source_url=source_url,
                ntrs_id=None,
            )
            matches = self._parameter_matches(investigation_view, parameters)
            if parameters is not None and not self._is_combustion_relevant(investigation_view, matches):
                continue
            relevance = (
                "Retrieved from NASA PSI's first-party investigation metadata endpoint. "
                "The source linkage is verified; investigation condition descriptions and measurements are not independently validated."
            )
            record_citations = []
            citation_id = f"NASA-PSI:{accession}"
            source_citation = MissionCitation(
                citation_id=citation_id,
                title=title,
                source="NASA Physical Sciences Informatics (PSI) repository metadata",
                identifier=accession,
                url=source_url,
                evidence_status=(
                    "NASA PSI investigation metadata retrieved; source linkage verified; "
                    "measurement and condition validation not established"
                ),
                evidence_class="verified_nasa_source",
                relevance_explanation=relevance,
                investigation_acronym=acronym,
            )
            record_citations.append(source_citation)
            if citation_id not in seen_citations:
                citations.append(source_citation)
                seen_citations.add(citation_id)

            for publication in _json_list(stored.publication_references_json):
                if not isinstance(publication, dict):
                    continue
                pub_title = publication.get("title") or publication.get("publicationTitle")
                if not pub_title:
                    continue
                doi = publication.get("doi") or publication.get("DOI")
                ntrs_id = publication.get("ntrsId") or publication.get("ntrs_id") or publication.get("identifier")
                pub_id = f"NASA-PSI-PUB:{ntrs_id or doi or accession + ':' + str(len(record_citations))}"
                pub_citation = MissionCitation(
                    citation_id=pub_id,
                    title=str(pub_title),
                    source="NASA PSI linked publication reference",
                    identifier=str(ntrs_id) if ntrs_id else None,
                    doi=str(doi) if doi else None,
                    url=publication.get("url"),
                    evidence_status="Publication reference metadata only; no experimental measurements verified",
                    evidence_class="publication_metadata_only",
                    relevance_explanation=f"Listed as a publication reference by PSI investigation {accession}; not a measurement provenance link.",
                    investigation_acronym=acronym,
                )
                record_citations.append(pub_citation)
                if pub_id not in seen_citations:
                    citations.append(pub_citation)
                    seen_citations.add(pub_id)

            file_names = [
                str(item.get("file_name"))
                for item in _json_list(stored.dataset_links_json)
                if isinstance(item, dict) and item.get("file_name")
            ]
            if file_names:
                relevance += " Listed dataset files: " + ", ".join(file_names[:8]) + ". File listing does not mean file content was retrieved."
            records.append(MissionEvidenceRecord(
                evidence_id=f"NASA-PSI:{accession}",
                investigation_title=title,
                investigation_acronym=acronym,
                original_source_url=source_url,
                experiment_type=stored.experiment_type,
                facility=investigation_view.facility or None,
                flight_mission=investigation_view.flight_mission or None,
                fuel_types=investigation_view.fuel_types or None,
                oxidizer_environment=investigation_view.oxidizer_environment or None,
                gravity_environment=investigation_view.gravity_environment or None,
                measured_parameters=investigation_view.measured_parameters or None,
                evidence_status=(
                    "NASA PSI investigation source linkage verified; experimental condition and measurement provenance not independently validated"
                ),
                evidence_class="verified_nasa_source",
                relevance_explanation=relevance,
                parameter_matches=matches,
                publications=record_citations,
                findings=[],
            ))

        # Stored NTRS items are retained as publication metadata citations only.
        ntrs_records = (
            db.query(ProcessedResearchRecord)
            .filter(ProcessedResearchRecord.record_kind == "ntrs_publication")
            .order_by(ProcessedResearchRecord.retrieved_at.desc())
            .limit(100)
            .all()
        )
        for stored in ntrs_records:
            metadata = _json_dict(stored.normalized_metadata_json)
            identifier = str(metadata.get("ntrs_id") or stored.source_record_id)
            citation_id = f"NTRS:{identifier}"
            if citation_id in seen_citations:
                continue
            citations.append(MissionCitation(
                citation_id=citation_id,
                title=str(metadata.get("title") or stored.title or identifier),
                source="NASA Technical Reports Server (NTRS)",
                authors=_join_authors(metadata.get("authors")),
                year=metadata.get("year"),
                identifier=identifier,
                doi=metadata.get("doi"),
                url=metadata.get("url") or (stored.raw_record.source_url if stored.raw_record else None),
                evidence_status="NTRS publication metadata retrieved; source-linked publication citation only",
                evidence_class="publication_metadata_only",
                relevance_explanation=(
                    "Retrieved NTRS record is publication metadata. It does not establish that a cited numerical measurement "
                    "originates from a particular flight experiment."
                ),
                relevance_snippet=(metadata.get("abstract") or "")[:400] or None,
            ))
            seen_citations.add(citation_id)

        # Categorical ordering: exact material references first, then by stable ID.
        records.sort(key=lambda item: (self._material_rank(item), item.investigation_acronym))
        gaps = self._detect_research_gaps(records, parameters)
        limitations = [
            "Local investigation summaries and findings are not independently provenance-verified.",
            "Numerical datapoint rows were excluded from retrieval and matching.",
            "Condition matches compare stored text/ranges only; they do not establish experimental equivalence or safety.",
            "No retrieved source explicitly documents the full combined scenario as tested.",
            "Microgravity results cannot be inferred to apply to lunar gravity.",
            "NASA PSI dataset retrieval is not performed by this service.",
        ]
        if not records:
            limitations.append("No relevant local combustion investigation records were retrieved.")
            limitations.append("No source-linked PSI combustion investigation records were retrieved.")
        if any(record.evidence_class == "verified_nasa_source" for record in records):
            limitations = [item for item in limitations if item != "NASA PSI dataset retrieval is not performed by this service."]
            limitations.append("Stored PSI investigation metadata is source-linked; the evidence service does not parse dataset measurements or verify test conditions.")
        context = self._format_context(records, gaps, question, parameters, citations)
        stored_ntrs = [citation for citation in citations if citation.citation_id.startswith("NTRS:")]
        if stored_ntrs:
            context += "\n\nStored NTRS publication metadata (citation context only; not experimental measurement evidence):\n"
            context += "\n".join(
                f"- {citation.citation_id}: {citation.title}; DOI={citation.doi or 'not stated'}; "
                f"URL={citation.url or 'not stated'}; abstract={citation.relevance_snippet or 'not supplied'}"
                for citation in stored_ntrs
            )
            context += "\nTreat these as publication references only; they do not establish numerical measurement provenance."
        return MissionEvidenceBundle(
            records=records,
            citations=citations,
            research_gaps=gaps,
            limitations=limitations,
            context=context,
        )

    def _is_combustion_relevant(self, investigation, matches) -> bool:
        searchable = " ".join((
            investigation.title or "",
            investigation.category or "",
            investigation.description or "",
            investigation.fuel_types or "",
            investigation.key_findings or "",
        )).lower()
        return any(term in searchable for term in DOMAIN_TERMS) or any(
            item.status in ("match", "partial") for item in matches
        )

    def _parameter_matches(self, investigation, parameters):
        if parameters is None:
            return []
        return [
            self._material_match(investigation, parameters.material),
            self._text_range_match(
                parameter="oxygen_percent",
                scenario_value=f"{parameters.oxygen_percent:g}% O2",
                recorded_text=investigation.oxidizer_environment or "",
                target=parameters.oxygen_percent,
                kind="oxygen",
            ),
            self._text_range_match(
                parameter="pressure_atm",
                scenario_value=f"{parameters.pressure_atm:g} atm",
                recorded_text=investigation.oxidizer_environment or "",
                target=parameters.pressure_atm,
                kind="pressure",
            ),
            self._text_range_match(
                parameter="airflow_cm_s",
                scenario_value=f"{parameters.airflow_cm_s:g} cm/s",
                recorded_text=" ".join((
                    investigation.oxidizer_environment or "",
                    investigation.measured_parameters or "",
                    investigation.description or "",
                    investigation.objectives or "",
                    investigation.key_findings or "",
                )),
                target=parameters.airflow_cm_s,
                kind="airflow",
            ),
            self._gravity_match(investigation.gravity_environment, parameters.gravity),
            self._environment_match(investigation, parameters.environment),
            EvidenceParameterMatch(
                parameter="experiment_type",
                scenario_value="Not specified in the mission request",
                recorded_value=investigation.category,
                status="unavailable",
                explanation=(
                    "The investigation category is available, but the mission request "
                    "does not specify an experiment type for a direct comparison."
                ),
            ),
        ]

    def _material_match(self, investigation, material):
        aliases = self.MATERIAL_TERMS[material]
        display_material = self.MATERIAL_LABELS[material]
        fuel_text = (investigation.fuel_types or "").lower()
        broader_text = " ".join((
            investigation.title or "",
            investigation.description or "",
            investigation.objectives or "",
            investigation.key_findings or "",
        )).lower()
        if any(alias in fuel_text for alias in aliases):
            status = "match"
            explanation = (
                f"The stored fuel/material description explicitly mentions {display_material}; "
                "the record remains provenance-unverified."
            )
        elif any(alias in broader_text for alias in aliases):
            status = "partial"
            explanation = (
                f"{display_material} is mentioned in narrative investigation text, but not in "
                "the structured fuel/material field; provenance is unverified."
            )
        elif fuel_text:
            status = "different"
            explanation = (
                f"The investigation lists different fuel/materials from {display_material}; "
                "it is retained only as related combustion context."
            )
        else:
            status = "unavailable"
            explanation = "The investigation record does not specify fuel/material conditions."
        return EvidenceParameterMatch(
            parameter="material",
            scenario_value=display_material,
            recorded_value=investigation.fuel_types,
            status=status,
            explanation=explanation,
        )

    def _text_range_match(self, parameter, scenario_value, recorded_text, target, kind):
        if kind == "oxygen":
            values = self._oxygen_values(recorded_text)
            unit = "% O2"
        elif kind == "pressure":
            values = self._pressure_values(recorded_text)
            unit = "atm"
        else:
            values = self._airflow_values(recorded_text)
            unit = "cm/s"

        if not values:
            return EvidenceParameterMatch(
                parameter=parameter,
                scenario_value=scenario_value,
                recorded_value=None,
                status="unavailable",
                explanation=f"No {parameter.replace('_', ' ')} condition is stated in the stored investigation metadata.",
            )

        lower, upper = min(values), max(values)
        if lower <= target <= upper:
            status = "match"
            if lower == upper:
                condition = f"The stored record states {lower:g} {unit}, matching the scenario value."
            else:
                condition = f"The scenario value falls within the stored {lower:g}–{upper:g} {unit} range."
        else:
            status = "different"
            condition = f"The scenario value is outside the stored {lower:g}–{upper:g} {unit} range."
        return EvidenceParameterMatch(
            parameter=parameter,
            scenario_value=scenario_value,
            recorded_value=recorded_text,
            status=status,
            explanation=(
                f"{condition} This is a text-based comparison against a local record "
                "whose provenance is unverified, not a validated test-condition match."
            ),
        )

    def _oxygen_values(self, text):
        values = [float(value) for value in re.findall(rf"({self.NUMBER})\s*%", text)]
        if "mole fraction" in text.lower():
            for low, high in re.findall(
                rf"mole fraction[^\d]*({self.NUMBER})\s*{self.RANGE_SEPARATOR}\s*({self.NUMBER})",
                text,
                flags=re.IGNORECASE,
            ):
                low_value, high_value = float(low), float(high)
                if 0 <= low_value <= 1 and 0 <= high_value <= 1:
                    values.extend((low_value * 100, high_value * 100))
        return values

    def _pressure_values(self, text):
        values = []
        for segment in re.split(r"[;\n]", text):
            if "pressure" not in segment.lower():
                continue
            for low, low_unit, high, high_unit in re.findall(
                rf"({self.NUMBER})\s*(atm|psi|bar)?\s*{self.RANGE_SEPARATOR}\s*({self.NUMBER})\s*(atm|psi|bar)",
                segment,
                flags=re.IGNORECASE,
            ):
                unit = (low_unit or high_unit).lower()
                values.extend((
                    float(low) * self.PRESSURE_UNITS_TO_ATM[unit],
                    float(high) * self.PRESSURE_UNITS_TO_ATM[high_unit.lower()],
                ))
            for value, unit in re.findall(
                rf"({self.NUMBER})\s*(atm|psi|bar)\b",
                segment,
                flags=re.IGNORECASE,
            ):
                values.append(float(value) * self.PRESSURE_UNITS_TO_ATM[unit.lower()])
        return values

    def _airflow_values(self, text):
        unit = r"(?:cm\s*/\s*s|cm\s*s(?:\^?-?1|⁻¹))"
        values = []
        range_pattern = rf"({self.NUMBER})\s*{self.RANGE_SEPARATOR}\s*({self.NUMBER})\s*{unit}"
        for low, high in re.findall(range_pattern, text, flags=re.IGNORECASE):
            values.extend((float(low), float(high)))
        values.extend(
            float(value)
            for value in re.findall(rf"({self.NUMBER})\s*{unit}", text, flags=re.IGNORECASE)
        )
        return values

    def _gravity_match(self, recorded, scenario_gravity):
        recorded_text = recorded or ""
        normalized = recorded_text.lower()
        if not recorded_text:
            status = "unavailable"
            explanation = "The investigation does not state a gravity environment."
        elif scenario_gravity in normalized:
            status = "match"
            explanation = (
                f"The stored gravity description mentions {scenario_gravity}; "
                "the record's provenance is unverified."
            )
        else:
            status = "different"
            explanation = (
                f"The stored gravity description is '{recorded_text}', which differs "
                f"from the hypothetical {scenario_gravity} scenario."
            )
        return EvidenceParameterMatch(
            parameter="gravity",
            scenario_value=scenario_gravity,
            recorded_value=recorded_text or None,
            status=status,
            explanation=explanation,
        )

    def _environment_match(self, investigation, scenario_environment):
        platform = " ".join((investigation.facility or "", investigation.flight_mission or ""))
        normalized = platform.lower()
        direct_terms = {
            "ISS Cabin": ("international space station", "iss"),
            "Lunar Habitat": ("lunar habitat", "lunar surface habitat"),
            "Mars Habitat": ("mars habitat", "martian habitat"),
            "Pressurized Rover": ("pressurized rover", "rover cabin"),
            "Spacecraft Cabin": ("spacecraft", "cygnus"),
            "Spacesuit": ("spacesuit", "space suit"),
        }[scenario_environment]
        hits = [
            term for term in direct_terms
            if re.search(
                rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])",
                normalized,
            )
        ]
        if hits:
            status = "partial" if scenario_environment == "Spacecraft Cabin" and "cygnus" in hits else "match"
            explanation = (
                f"Stored facility/mission metadata mentions {', '.join(hits)}. This is "
                "a platform-context match only; it does not establish equivalence to the hypothetical environment."
            )
        elif platform:
            status = "different"
            explanation = (
                f"Stored facility/mission metadata describes '{platform}', not the "
                f"hypothetical {scenario_environment} environment."
            )
        else:
            status = "unavailable"
            explanation = "No facility or mission-platform information is recorded."
        return EvidenceParameterMatch(
            parameter="environment",
            scenario_value=scenario_environment,
            recorded_value=platform or None,
            status=status,
            explanation=explanation,
        )

    def _relevance_explanation(self, investigation, matches, parameters):
        reasons = []
        for item in matches:
            if item.parameter == "material" and item.status == "match":
                reasons.append(f"its stored fuel/material field includes {item.scenario_value}")
            elif item.parameter in ("oxygen_percent", "pressure_atm", "airflow_cm_s") and item.status == "match":
                reasons.append(f"its stored conditions include the scenario's {item.parameter.replace('_', ' ')} value/range")
        if not reasons:
            reasons.append("it covers combustion or spacecraft fire-safety research relevant as general context")
        suffix = " The investigation record is not independently provenance-verified."
        return f"Retrieved as related combustion research context because {', and '.join(reasons)}.{suffix}"

    def _material_rank(self, record):
        for item in record.parameter_matches:
            if item.parameter == "material":
                return 0 if item.status == "match" else 1
        return 2

    def _detect_research_gaps(self, records, parameters):
        if parameters is None:
            return ResearchGapReport(
                unsupported_parameters=[
                    ResearchGapAssessment(
                        parameter="scenario_parameters",
                        scenario_value="Not supplied",
                        status="unsupported",
                        explanation="No scenario was supplied for condition matching.",
                    )
                ],
                important_assumptions=["Local record provenance is unverified."],
            )

        scenario_values = {
            "environment": parameters.environment,
            "material": self.MATERIAL_LABELS[parameters.material],
            "oxygen_percent": f"{parameters.oxygen_percent:g}% O2",
            "pressure_atm": f"{parameters.pressure_atm:g} atm",
            "airflow_cm_s": f"{parameters.airflow_cm_s:g} cm/s",
            "gravity": parameters.gravity,
            "experiment_type": "Not specified in the mission request",
        }
        supported = []
        partial = []
        unsupported = []
        for parameter, scenario_value in scenario_values.items():
            matches = [
                (record, item)
                for record in records
                for item in record.parameter_matches
                if item.parameter == parameter
            ]
            aligned = [
                (record, item) for record, item in matches
                if item.status in ("match", "partial")
            ]
            verified_aligned = [
                pair for pair in aligned
                if pair[0].evidence_status.startswith(
                    "NASA PSI experimental-condition field explicitly documents"
                )
            ]
            evidence_names = list(dict.fromkeys(
                f"{record.investigation_acronym}: {item.recorded_value or item.explanation}"
                for record, item in aligned
            ))
            if verified_aligned:
                status = "supported"
            elif aligned:
                status = "partial"
            else:
                status = "unsupported"

            if status == "supported":
                explanation = "A provenance-established record documents this scenario condition."
            elif status == "partial":
                explanation = (
                    "Related source metadata contains a textual condition match, but the match does not independently validate an experimental condition or confirm that the scenario was tested."
                )
            else:
                explanation = (
                    "No retrieved record documents this scenario condition. Retrieved "
                    "experiments may provide context, but they differ or do not report it."
                )
            assessment = ResearchGapAssessment(
                parameter=parameter,
                scenario_value=scenario_value,
                status=status,
                available_evidence=evidence_names,
                explanation=explanation,
            )
            {"supported": supported, "partial": partial, "unsupported": unsupported}[status].append(assessment)

        assumptions = [
            "Mission parameters are hypothetical user inputs, not NASA test conditions.",
            "Condition matching uses investigation metadata and narrative fields only; no datapoint rows or legacy measured-flight flags are used.",
            "All current local investigation records remain provenance-unverified; therefore no parameter is classified as fully supported by verified evidence.",
            "A text/range match describes metadata overlap only and does not establish experimental equivalence or a safety conclusion.",
            "No retrieved source explicitly documents the full combined scenario as tested; condition overlaps across separate records are not a joint experiment.",
            "Microgravity findings do not establish lunar-gravity findings.",
            "The mission evidence matcher does not parse PSI dataset measurements; source-linked file metadata and raw bytes are retained separately.",
        ]
        return ResearchGapReport(
            supported_parameters=supported,
            partially_supported_parameters=partial,
            unsupported_parameters=unsupported,
            important_assumptions=assumptions,
        )

    def _format_context(self, records, research_gaps, question, parameters=None, citations=None):
        sections = [
            "No retrieved record currently establishes verified NASA experimental measurements. Local seed records are provenance-unverified; PSI records are source-linked metadata only; NTRS items are publication metadata only.",
            "Parameter overlaps are related research context, not evidence that the full combined scenario was tested. Never combine conditions from different records into one experiment.",
            "Microgravity results must not be inferred to represent lunar gravity.",
            "Numerical datapoint rows are excluded. Do not repeat numerical experimental condition values in specialist prose. Use the deterministic match explanations below for condition comparisons.",
            f"Research question: {question or 'General mission fire-safety research analysis.'}",
        ]
        if parameters is not None:
            sections.append(
                "AUTHORITATIVE VALIDATED SCENARIO INPUTS (exact; do not round or substitute):\n"
                + json.dumps(parameters.model_dump(mode="json"), indent=2)
            )
        for record in records:
            record_citations = [
                citation for citation in (citations or [])
                if citation.investigation_acronym == record.investigation_acronym
            ]
            sections.append(
                f"Evidence ID: {record.evidence_id}\n"
                f"Investigation: {record.investigation_title} ({record.investigation_acronym})\n"
                f"Experiment type: {record.experiment_type or 'Not stated'}\n"
                f"Stored fuel/materials: {record.fuel_types or 'Not stated'}\n"
                f"Stored oxidizer conditions: {record.oxidizer_environment or 'Not stated'}\n"
                f"Stored gravity: {record.gravity_environment or 'Not stated'}\n"
                f"Stored facility/mission: {record.facility or 'Not stated'} / {record.flight_mission or 'Not stated'}\n"
                f"Stored measured-parameter description: {record.measured_parameters or 'Not stated'}\n"
                f"Original source URL: {record.original_source_url or 'Not stated'}\n"
                f"Evidence status: {record.evidence_status}\n"
                f"Evidence class: {record.evidence_class}\n"
                f"Relevance: {record.relevance_explanation}\n"
                "Retrieved citation IDs for this investigation (cite only these IDs when attributing claims):\n"
                + ("\n".join(
                    f"- {citation.citation_id}: {citation.title}; status={citation.evidence_status}"
                    for citation in record_citations
                ) or "- None retrieved")
                + "\n"
                "Condition matches:\n"
                + "\n".join(
                    f"- {item.parameter}: scenario={item.scenario_value}; recorded={item.recorded_value or 'unavailable'}; status={item.status}; {item.explanation}"
                    for item in record.parameter_matches
                )
                + f"\nResearch findings ({record.evidence_status}):\n"
                + ("\n".join(f"- {finding.finding_text}" for finding in record.findings) or "- None recorded")
                + "\nPublication citation IDs:\n"
                + ("\n".join(
                    f"- {citation.citation_id}: {citation.title}; DOI={citation.doi or 'not stated'}; NTRS={citation.identifier or 'not stated'}; URL={citation.url or 'not stated'}"
                    for citation in record.publications
                ) or "- None recorded")
            )
        sections.append(
            "Research gap categories:\n"
            f"- Partially supported by related metadata: {', '.join(item.parameter for item in research_gaps.partially_supported_parameters) or 'none'}\n"
            f"- Unsupported by available conditions: {', '.join(item.parameter for item in research_gaps.unsupported_parameters) or 'none'}\n"
            "No fully provenance-verified parameters are currently available.\n"
            f"Combined scenario status: {research_gaps.combined_scenario_status}. {research_gaps.combined_scenario_explanation}"
        )
        return "\n\n".join(sections)


def _json_dict(value):
    try:
        parsed = json.loads(value or "{}")
        return parsed if isinstance(parsed, dict) else {}
    except (TypeError, ValueError):
        return {}


def _json_list(value):
    try:
        parsed = json.loads(value or "[]")
        return parsed if isinstance(parsed, list) else []
    except (TypeError, ValueError):
        return []


def _join_authors(value):
    if isinstance(value, list):
        return "; ".join(str(item) for item in value if item) or None
    return str(value) if value else None
