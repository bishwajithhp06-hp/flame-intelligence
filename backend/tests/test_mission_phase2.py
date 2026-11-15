import asyncio
import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.investigation import (
    CombustionDataPoint,
    Investigation,
    Publication,
    ResearchFinding,
)
from app.schemas.mission import MissionCitation, MissionParameters, SPECIALIST_ROLES
from app.services.mission_evidence_service import MissionEvidenceService
from app.services.mission_service import MissionIntelligenceService, SpecialistStageResult, SynthesisDraft


class MissionPhaseTwoTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.session_factory = sessionmaker(bind=self.engine, autoflush=False)
        self.db = self.session_factory()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    @staticmethod
    def parameters(**overrides):
        values = {
            "environment": "Lunar Habitat",
            "oxygen_percent": 34.0,
            "pressure_atm": 0.56,
            "airflow_cm_s": 15.0,
            "gravity": "lunar",
            "material": "pmma",
        }
        values.update(overrides)
        return MissionParameters.model_validate(values)

    def add_local_record(self):
        investigation = Investigation(
            investigation_id="LOCAL-SAFFIRE-FIXTURE",
            title="Local PMMA flame spread fixture",
            acronym="SAFFIRE",
            category="Large-scale material flammability",
            description="Local fixture about PMMA combustion and airflow; not a verified NASA source.",
            facility="Cygnus spacecraft",
            flight_mission="ISS Expeditions",
            fuel_types="PMMA (polymethyl methacrylate) sheets",
            oxidizer_environment="O2 enriched up to 34%; pressure 0.55 to 1.0 atm",
            gravity_environment="Microgravity (~10^-5 g)",
            measured_parameters="Flame spread; recorded flow condition around 10 to 20 cm/s.",
            key_findings="The local record describes PMMA flame spread at low airflow.",
            source_url="https://example.test/local-investigation-record",
        )
        investigation.publications.append(Publication(
            title="Fixture publication metadata",
            authors="Test Author",
            year=2020,
            doi="10.5555/fixture.1",
            ntrs_id="TEST-NTRS-001",
            abstract="A local fixture publication record for contract tests.",
            url="https://example.test/publication",
        ))
        investigation.findings.append(ResearchFinding(
            finding_text="The local record describes PMMA flame behavior.",
            category="Material flammability",
            spacecraft_fire_safety_implication="Fixture-only text.",
            evidence_strength="High (Flight Verified)",
            source_citation="Fixture citation",
            doi="10.5555/fixture.1",
        ))
        investigation.datapoints.append(CombustionDataPoint(
            fuel_name="PMMA",
            fuel_state="Solid Sheet",
            ambient_o2_percent=34.0,
            pressure_atm=0.56,
            ambient_velocity_cm_s=15.0,
            burn_rate_or_flame_speed=9876.543,
            unit="fixture units",
            is_measured_flight_data=True,
            source_reference="Unverified fixture row",
        ))
        self.db.add(investigation)
        self.db.commit()
        return investigation

    @staticmethod
    def evidence_summary_claim(evidence_id, citation_id):
        excerpt = "PMMA (polymethyl methacrylate) sheets"
        return {
            "claim_text": (
                'The local provenance-unverified SAFFIRE record lists '
                f'"{excerpt}" in its stored fuel/material field.'
            ),
            "claim_type": "evidence_summary",
            "sources": [{
                "evidence_id": evidence_id,
                "citation_ids": [citation_id],
                "source_excerpt": excerpt,
                "provenance_status": "Local record — provenance unverified",
            }],
            "uncertainty": "This stored description does not verify experimental measurements.",
        }

    @staticmethod
    def hypothetical_claim(text="As a hypothetical inference, lunar gravity may affect scenario transfer."):
        return {
            "claim_text": text,
            "claim_type": "hypothetical_inference",
            "sources": [],
            "uncertainty": "The combined scenario is not established by the retrieved conditions.",
        }

    @staticmethod
    def first_stage_response(evidence_id=None, citation_id=None):
        claims = [MissionPhaseTwoTests.hypothetical_claim()]
        if evidence_id and citation_id:
            claims.insert(0, MissionPhaseTwoTests.evidence_summary_claim(evidence_id, citation_id))
        return {
            "specialist_analyses": [
                {
                    "role": role,
                    "scenario_parameters": MissionPhaseTwoTests.parameters().model_dump(mode="json"),
                    "claims": claims,
                }
                for role in SPECIALIST_ROLES[:4]
            ]
        }

    @staticmethod
    def synthesis_response(evidence_id=None, citation_id=None):
        analysis_claims = [{
            "claim_text": "The four specialist perspectives leave this hypothetical outcome uncertain.",
            "claim_type": "hypothetical_inference",
            "sources": [],
            "uncertainty": "No retrieved source establishes the combined scenario.",
        }]
        combined_claims = [MissionPhaseTwoTests.hypothetical_claim(
            "The combined hypothetical mission outcome remains uncertain."
        )]
        if evidence_id and citation_id:
            combined_claims.append(
                MissionPhaseTwoTests.evidence_summary_claim(evidence_id, citation_id)
            )
        return {
            "scenario_parameters": MissionPhaseTwoTests.parameters().model_dump(mode="json"),
            "analysis_claims": analysis_claims,
            "combined_assessment_claims": combined_claims,
            "conflict_assessment": "No conflicts identified among the validated specialist claims.",
            "main_documented_findings": ([
                {"finding": "The local record describes PMMA flame behavior.", "citation_ids": [citation_id]}
            ] if citation_id else []),
            "conflicting_claims": [],
            "important_uncertainties": ["Local record provenance is unverified."],
            "research_gaps": ["No lunar-gravity habitat experiment is present in the retrieved records."],
            "supporting_citation_ids": [citation_id] if citation_id else [],
        }

    def test_evidence_matching_citations_gaps_and_datapoint_exclusion(self):
        self.add_local_record()
        bundle = MissionEvidenceService().retrieve(
            self.db,
            self.parameters(),
            "PMMA in a lunar habitat",
        )

        self.assertEqual(len(bundle.records), 1)
        record = bundle.records[0]
        self.assertEqual(record.investigation_title, "Local PMMA flame spread fixture")
        self.assertEqual(record.investigation_acronym, "SAFFIRE")
        self.assertEqual(record.original_source_url, "https://example.test/local-investigation-record")
        self.assertEqual(record.evidence_status, "Local record — provenance unverified")
        self.assertEqual(record.evidence_class, "local_provenance_unverified")
        self.assertIn("PMMA", record.relevance_explanation)
        self.assertIn("Retrieved citation IDs for this investigation", bundle.context)
        self.assertIn("INV:LOCAL-SAFFIRE-FIXTURE", bundle.context)
        self.assertIn("SAFFIRE:TEST-NTRS-001", bundle.context)

        matches = {item.parameter: item for item in record.parameter_matches}
        self.assertEqual(matches["material"].status, "match")
        self.assertEqual(matches["oxygen_percent"].status, "match")
        self.assertEqual(matches["pressure_atm"].status, "match")
        self.assertEqual(matches["airflow_cm_s"].status, "match")
        self.assertEqual(matches["gravity"].status, "different")
        self.assertEqual(matches["environment"].status, "different")
        self.assertEqual(matches["experiment_type"].status, "unavailable")

        publication = record.publications[0]
        self.assertEqual(publication.title, "Fixture publication metadata")
        self.assertEqual(publication.doi, "10.5555/fixture.1")
        self.assertEqual(publication.identifier, "TEST-NTRS-001")
        self.assertEqual(publication.url, "https://example.test/publication")
        self.assertEqual(publication.evidence_status, "Local record — provenance unverified")
        self.assertEqual(record.findings[0].evidence_status, "Local record — provenance unverified")

        self.assertNotIn("9876.543", bundle.context)
        self.assertNotIn("9876.543", json.dumps([item.model_dump() for item in bundle.records]))
        self.assertIn("Numerical datapoint rows were excluded", " ".join(bundle.limitations))

        self.assertEqual(bundle.research_gaps.supported_parameters, [])
        self.assertEqual(bundle.research_gaps.combined_scenario_status, "not_documented")
        self.assertIn("cannot be combined into evidence", bundle.research_gaps.combined_scenario_explanation)
        self.assertIn('"pressure_atm": 0.56', bundle.context)
        self.assertIn("Microgravity results must not be inferred to represent lunar gravity", bundle.context)
        partial = {item.parameter for item in bundle.research_gaps.partially_supported_parameters}
        unsupported = {item.parameter for item in bundle.research_gaps.unsupported_parameters}
        self.assertTrue({"material", "oxygen_percent", "pressure_atm", "airflow_cm_s"}.issubset(partial))
        self.assertTrue({"environment", "gravity", "experiment_type"}.issubset(unsupported))

    def test_empty_evidence_reports_gaps_without_inventing_records(self):
        bundle = MissionEvidenceService().retrieve(self.db, self.parameters())
        self.assertEqual(bundle.records, [])
        self.assertEqual(bundle.citations, [])
        self.assertEqual(bundle.research_gaps.supported_parameters, [])
        self.assertEqual(bundle.research_gaps.partially_supported_parameters, [])
        self.assertGreaterEqual(len(bundle.research_gaps.unsupported_parameters), 7)
        self.assertIn("No relevant local combustion investigation records were retrieved.", bundle.limitations)

    def test_mocked_gemini_runs_four_specialists_then_synthesizes_with_safe_citations(self):
        investigation = self.add_local_record()
        evidence_id = investigation.investigation_id
        citation_id = "SAFFIRE:TEST-NTRS-001"
        gemini_client = Mock()
        gemini_client.models.generate_content.side_effect = [
            SimpleNamespace(text=json.dumps(self.first_stage_response(evidence_id, citation_id))),
            SimpleNamespace(text=json.dumps(self.synthesis_response(evidence_id, citation_id))),
        ]
        ntrs_service = Mock()
        ntrs_service.search_citations = AsyncMock(return_value=[])
        service = MissionIntelligenceService(
            client=gemini_client,
            model="test-model",
            ntrs_service=ntrs_service,
        )

        result = asyncio.run(service.analyze(
            self.db,
            self.parameters(),
            "How does 34% oxygen affect PMMA combustion in a lunar habitat?",
        ))

        self.assertEqual(gemini_client.models.generate_content.call_count, 2)
        self.assertEqual(
            [item.role for item in result.specialist_analyses],
            list(SPECIALIST_ROLES),
        )
        self.assertEqual(result.scenario_parameters.pressure_atm, 0.56)
        self.assertEqual(result.scenario_parameters.oxygen_percent, 34.0)
        self.assertEqual(result.scenario_parameters.airflow_cm_s, 15.0)
        self.assertEqual(result.research_gaps.combined_scenario_status, "not_documented")
        self.assertEqual(result.synthesis_details.conflicting_claims, [])
        self.assertIn("No conflicts identified", result.synthesis_details.conflict_assessment)
        self.assertTrue(all(item.relevant_evidence for item in result.specialist_analyses))
        self.assertTrue(all(item.citations for item in result.specialist_analyses))
        self.assertEqual(result.synthesis_details.main_documented_findings[0].finding,
                         "The local record describes PMMA flame behavior.")
        self.assertEqual(
            result.synthesis_details.main_documented_findings[0].citations[0].doi,
            "10.5555/fixture.1",
        )
        self.assertIn("lunar-gravity", " ".join(result.synthesis_details.research_gaps))
        self.assertEqual(result.evidence_matches[0].evidence_status, "Local record — provenance unverified")

        first_prompt = gemini_client.models.generate_content.call_args_list[0].kwargs["contents"]
        synthesis_prompt = gemini_client.models.generate_content.call_args_list[1].kwargs["contents"]
        self.assertIn('"oxygen_percent": 34.0', first_prompt)
        self.assertIn('"pressure_atm": 0.56', first_prompt)
        self.assertIn('"airflow_cm_s": 15.0', first_prompt)
        self.assertEqual(first_prompt.count('"scenario_parameters"'), 4)
        self.assertIn("AUTHORITATIVE VALIDATED SCENARIO INPUTS", first_prompt)
        self.assertIn("Retrieved citation IDs for this investigation", first_prompt)
        self.assertIn("SAFFIRE:TEST-NTRS-001", first_prompt)
        self.assertIn("hypothetical_inference", first_prompt)
        self.assertIn('"source_excerpt": "PMMA (polymethyl methacrylate) sheets"', first_prompt)
        self.assertIn('"citation_ids": ["SAFFIRE:TEST-NTRS-001"]', first_prompt)
        self.assertIn("Atmosphere Analyst: oxygen, diluents, pressure", first_prompt)
        self.assertIn('"pressure_atm": 0.56', synthesis_prompt)
        self.assertIn("VALIDATED SPECIALIST HANDOFF", synthesis_prompt)
        self.assertIn("conflicting_claims", synthesis_prompt)
        self.assertIn("Never imply that separate conditions were tested together", synthesis_prompt)
        self.assertIn('"selected_evidence_records"', synthesis_prompt)
        self.assertIn('"investigation_title": "Local PMMA flame spread fixture"', synthesis_prompt)
        self.assertIn('"evidence_class": "local_provenance_unverified"', synthesis_prompt)
        self.assertIn('"selected_citation_records"', synthesis_prompt)

    def test_scenario_echo_and_generated_prose_consistency_are_enforced(self):
        parameters = self.parameters()
        rounded = parameters.model_copy(update={"pressure_atm": 0.55})
        with self.assertRaisesRegex(RuntimeError, "changed the validated scenario inputs"):
            MissionIntelligenceService._validate_scenario_echo(
                rounded,
                parameters,
                "Atmosphere Analyst",
            )

        MissionIntelligenceService._validate_generated_text(
            "The hypothetical scenario input is 0.56 atm.",
            parameters,
            "Atmosphere Analyst",
        )
        with self.assertRaisesRegex(RuntimeError, "pressure value that conflicts"):
            MissionIntelligenceService._validate_generated_text(
                "The scenario pressure is 0.55 atm.",
                parameters,
                "Atmosphere Analyst",
            )
        with self.assertRaisesRegex(RuntimeError, "unsupported numeric risk or threshold"):
            MissionIntelligenceService._validate_generated_text(
                "The risk score is 15%.",
                parameters,
                "Mission Safety Synthesizer",
            )
        MissionIntelligenceService._validate_generated_text(
            "The combined scenario has not been tested.",
            parameters,
            "Mission Safety Synthesizer",
        )
        with self.assertRaisesRegex(RuntimeError, "combined scenario was tested"):
            MissionIntelligenceService._validate_generated_text(
                "The combined scenario has been experimentally tested.",
                parameters,
                "Mission Safety Synthesizer",
            )

    @staticmethod
    def _claim_fixture():
        citation = MissionCitation(
            citation_id="SAFFIRE:TEST-1", title="SAFFIRE fixture publication",
            source="Local publication record", identifier="TEST-1",
            evidence_status="Local record — provenance unverified",
            evidence_class="local_provenance_unverified", investigation_acronym="SAFFIRE",
            relevance_explanation="Test citation fixture.", relevance_snippet="PMMA flame behavior was documented.",
        )
        record = SimpleNamespace(
            evidence_id="LOCAL-SAFFIRE", investigation_title="SAFFIRE fixture record",
            investigation_acronym="SAFFIRE", evidence_class="local_provenance_unverified",
            evidence_status="Local record — provenance unverified", experiment_type="Flammability metadata",
            fuel_types="PMMA sheets", oxidizer_environment="Oxygen enriched conditions",
            gravity_environment="Microgravity", facility="Fixture facility", flight_mission="Not verified",
            measured_parameters="Flame spread",
            findings=[SimpleNamespace(finding_text="PMMA flame behavior was documented.")],
            publications=[citation],
        )
        return citation, record, {citation.citation_id: citation}, {record.evidence_id: record}

    @staticmethod
    def claim(claim_text, claim_type, sources=None, uncertainty=""):
        from app.services.mission_service import MissionClaim
        return MissionClaim(claim_text=claim_text, claim_type=claim_type, sources=sources or [], uncertainty=uncertainty)

    @staticmethod
    def source_ref(evidence_id, citation_ids, source_excerpt, provenance_status):
        from app.services.mission_service import ClaimSourceReference
        return ClaimSourceReference(
            evidence_id=evidence_id, citation_ids=citation_ids,
            source_excerpt=source_excerpt, provenance_status=provenance_status,
        )

    def test_claim_diagnostics_identify_each_rejection_for_all_four_specialists(self):
        citation, record, citations, records = self._claim_fixture()
        service = MissionIntelligenceService(client=Mock())
        other_citation = MissionCitation(
            citation_id="FLEX:OTHER-1", title="Unrelated FLEX citation", source="Local publication",
            evidence_status="Local record — provenance unverified",
            evidence_class="local_provenance_unverified", investigation_acronym="FLEX",
            relevance_explanation="Unrelated fixture.",
        )
        citations[other_citation.citation_id] = other_citation
        cases = [
            (
                self.claim('The local provenance-unverified SAFFIRE record lists "PMMA sheets".', "evidence_summary"),
                "missing_source_reference",
            ),
            (
                self.claim(
                    'The local provenance-unverified SAFFIRE record lists "PMMA sheets".',
                    "evidence_summary",
                    [self.source_ref("UNKNOWN", [citation.citation_id], "PMMA sheets", record.evidence_status)],
                ),
                "unknown_evidence_id",
            ),
            (
                self.claim(
                    'The local provenance-unverified SAFFIRE record lists "PMMA sheets".',
                    "evidence_summary",
                    [self.source_ref(record.evidence_id, ["UNKNOWN:CITATION"], "PMMA sheets", record.evidence_status)],
                ),
                "unknown_citation_id",
            ),
            (
                self.claim(
                    'The local provenance-unverified SAFFIRE record lists "PMMA sheets".',
                    "evidence_summary",
                    [self.source_ref(record.evidence_id, [], "PMMA sheets", record.evidence_status)],
                ),
                "missing_citation_id",
            ),
            (
                self.claim(
                    'The local provenance-unverified SAFFIRE record lists "PMMA sheets".',
                    "evidence_summary",
                    [self.source_ref(record.evidence_id, [other_citation.citation_id], "PMMA sheets", record.evidence_status)],
                ),
                "mismatched_investigation",
            ),
            (
                self.claim(
                    'The local provenance-unverified SAFFIRE record lists "PMMA sheets".',
                    "evidence_summary",
                    [self.source_ref(record.evidence_id, [citation.citation_id], "PMMA sheets", "Verified NASA flight data")],
                ),
                "provenance_status_mismatch",
            ),
            (
                self.claim(
                    'The local provenance-unverified SAFFIRE record proved an unsupported experimental result.',
                    "historical_experimental",
                    [self.source_ref(record.evidence_id, [citation.citation_id], "unsupported experimental result", record.evidence_status)],
                    "This local record is provenance-unverified.",
                ),
                "unsupported_historical_claim",
            ),
            (
                self.claim("An unknown classification should be rejected.", "made_up_classification"),
                "invalid_claim_classification",
            ),
        ]

        for role in ("Combustion Analyst", "Atmosphere Analyst", "Material Safety Analyst", "Fire Suppression Analyst"):
            for claim, expected_reason in cases:
                with self.subTest(role=role, reason=expected_reason):
                    accepted, issues, diagnostics = service._filter_claims(
                        [claim], self.parameters(), role, citations, records
                    )
                    self.assertEqual(accepted, [])
                    self.assertEqual(diagnostics[0].role, role)
                    self.assertEqual(diagnostics[0].reason_code, expected_reason)
                    self.assertIn(expected_reason, issues[0])
                    self.assertNotIn(claim.claim_text, json.dumps(diagnostics[0].model_dump(mode="json")))
                    if expected_reason == "unknown_evidence_id":
                        self.assertFalse(diagnostics[0].evidence_ids_valid)
                    if expected_reason == "unknown_citation_id":
                        self.assertTrue(diagnostics[0].evidence_ids_valid)
                        self.assertFalse(diagnostics[0].citation_ids_valid)
                    if expected_reason == "mismatched_investigation":
                        self.assertTrue(diagnostics[0].citation_ids_valid)
                        self.assertFalse(diagnostics[0].citation_investigation_match)
                    if expected_reason == "provenance_status_mismatch":
                        self.assertTrue(diagnostics[0].provenance_restriction_rejected)
                    if expected_reason == "unsupported_historical_claim":
                        self.assertFalse(diagnostics[0].historical_source_text_match)

        valid_summary = self.claim(
            'The local provenance-unverified SAFFIRE record lists "PMMA sheets" as its stored material.',
            "evidence_summary",
            [self.source_ref(record.evidence_id, [citation.citation_id], "PMMA sheets", record.evidence_status)],
        )
        valid_inference = self.claim(**self.hypothetical_claim())
        for role in ("Combustion Analyst", "Atmosphere Analyst", "Material Safety Analyst", "Fire Suppression Analyst"):
            with self.subTest(role=role, reason="valid claims"):
                accepted, issues, diagnostics = service._filter_claims(
                    [valid_summary, valid_inference], self.parameters(), role, citations, records
                )
                self.assertEqual(len(accepted), 2)
                self.assertEqual(issues, [])
                self.assertEqual(diagnostics, [])

    def test_parser_schema_mismatch_is_logged_without_generated_claim_text(self):
        sentinel = "PRIVATE_GENERATED_CLAIM_TEXT_91AF"
        malformed = {"specialist_analyses": [], "claim_text": sentinel}
        client = Mock()
        client.models.generate_content.return_value = SimpleNamespace(text=json.dumps(malformed))
        service = MissionIntelligenceService(client=client)

        with self.assertLogs("flame_intelligence.mission", level="WARNING") as captured:
            with self.assertRaisesRegex(RuntimeError, "parser_schema_mismatch"):
                asyncio.run(service._generate_json("safe prompt", SpecialistStageResult, "specialist analysis"))

        logged = "\n".join(captured.output)
        self.assertIn("parser_schema_mismatch", logged)
        self.assertNotIn(sentinel, logged)

    def test_synthesis_parser_schema_mismatch_is_controlled_without_response_text(self):
        sentinel = "PRIVATE_SYNTHESIS_OUTPUT_4A20"
        malformed = {"claim_text": sentinel, "scenario_parameters": {}}
        client = Mock()
        client.models.generate_content.return_value = SimpleNamespace(text=json.dumps(malformed))
        service = MissionIntelligenceService(client=client)

        with self.assertLogs("flame_intelligence.mission", level="WARNING") as captured:
            with self.assertRaisesRegex(RuntimeError, "invalid mission synthesis response \\(parser_schema_mismatch\\)"):
                asyncio.run(service._generate_json("safe synthesis prompt", SynthesisDraft, "mission synthesis"))

        logged = "\n".join(captured.output)
        self.assertIn("stage=mission synthesis", logged)
        self.assertIn("reason_code=parser_schema_mismatch", logged)
        self.assertNotIn(sentinel, logged)

    def test_valid_evidence_summary_uses_matching_record_citation_and_excerpt(self):
        citation, record, citations, records = self._claim_fixture()
        excerpt = "PMMA sheets"
        text = 'The local provenance-unverified SAFFIRE record lists "PMMA sheets" as its stored material.'
        claim = self.claim(text, "evidence_summary", [
            self.source_ref(record.evidence_id, [citation.citation_id], excerpt, record.evidence_status)
        ], "This stored description does not verify underlying measurements.")
        MissionIntelligenceService(client=Mock())._validate_claim(claim, "Combustion Analyst", citations, records)

    def test_evidence_summary_without_citation_is_rejected(self):
        citation, record, citations, records = self._claim_fixture()
        claim = self.claim(
            'The local provenance-unverified SAFFIRE record lists "PMMA sheets".',
            "evidence_summary",
            [self.source_ref(record.evidence_id, [], "PMMA sheets", record.evidence_status)],
        )
        with self.assertRaisesRegex(RuntimeError, "no citation IDs"):
            MissionIntelligenceService(client=Mock())._validate_claim(claim, "Combustion Analyst", citations, records)

    def test_invalid_evidence_id_is_rejected(self):
        citation, record, citations, records = self._claim_fixture()
        claim = self.claim(
            'The local provenance-unverified SAFFIRE record lists "PMMA sheets".',
            "evidence_summary",
            [self.source_ref("NOT-RETRIEVED", [citation.citation_id], "PMMA sheets", record.evidence_status)],
        )
        with self.assertRaisesRegex(RuntimeError, "unavailable evidence record"):
            MissionIntelligenceService(client=Mock())._validate_claim(claim, "Combustion Analyst", citations, records)

    def test_mismatched_citation_is_rejected(self):
        citation, record, citations, records = self._claim_fixture()
        unrelated = MissionCitation(
            citation_id="FLEX:OTHER-1", title="Unrelated FLEX citation", source="Local publication",
            evidence_status="Local record — provenance unverified",
            evidence_class="local_provenance_unverified", investigation_acronym="FLEX",
            relevance_explanation="Unrelated fixture.",
        )
        citations[unrelated.citation_id] = unrelated
        claim = self.claim(
            'The local provenance-unverified SAFFIRE record lists "PMMA sheets".',
            "evidence_summary",
            [self.source_ref(record.evidence_id, [unrelated.citation_id], "PMMA sheets", record.evidence_status)],
        )
        with self.assertRaisesRegex(RuntimeError, "belongs to another investigation"):
            MissionIntelligenceService(client=Mock())._validate_claim(claim, "Combustion Analyst", citations, records)

    def test_unsupported_historical_claim_is_rejected(self):
        claim = self.claim("The submitted atmosphere was tested in the lunar scenario.", "historical_experimental")
        with self.assertRaisesRegex(RuntimeError, "no record citations"):
            MissionIntelligenceService(client=Mock())._validate_claim(claim, "Atmosphere Analyst", {}, {})

    def test_supported_historical_claim_quotes_retrieved_finding_and_preserves_provenance(self):
        citation, record, citations, records = self._claim_fixture()
        excerpt = "PMMA flame behavior was documented."
        text = f'The local provenance-unverified SAFFIRE finding states "{excerpt}"'
        claim = self.claim(
            text, "historical_experimental",
            [self.source_ref(record.evidence_id, [citation.citation_id], excerpt, record.evidence_status)],
            "The finding remains provenance-unverified.",
        )
        MissionIntelligenceService(client=Mock())._validate_claim(claim, "Combustion Analyst", citations, records)

    def test_hypothetical_inference_requires_explicit_uncertainty(self):
        valid = self.claim(
            "As a hypothetical inference, lunar gravity may affect scenario transfer.",
            "hypothetical_inference", uncertainty="No retrieved evidence establishes the combined conditions.",
        )
        MissionIntelligenceService(client=Mock())._validate_claim(valid, "Atmosphere Analyst", {}, {})
        invalid = self.claim("Lunar gravity affects scenario transfer.", "hypothetical_inference", uncertainty="Uncertain.")
        with self.assertRaisesRegex(RuntimeError, "not explicitly uncertain"):
            MissionIntelligenceService(client=Mock())._validate_claim(invalid, "Atmosphere Analyst", {}, {})

    def test_general_scientific_context_does_not_claim_source_support(self):
        valid = self.claim("Oxygen availability can affect combustion chemistry.", "general_scientific_context")
        MissionIntelligenceService(client=Mock())._validate_claim(valid, "Atmosphere Analyst", {}, {})
        invalid = self.claim(
            "A NASA experiment established that oxygen changes combustion.", "general_scientific_context"
        )
        with self.assertRaisesRegex(RuntimeError, "attributed to a source"):
            MissionIntelligenceService(client=Mock())._validate_claim(invalid, "Atmosphere Analyst", {}, {})

    def test_synthesizer_can_combine_multiple_claim_sources_without_cross_attribution(self):
        first_citation, first_record, citations, records = self._claim_fixture()
        second_citation = MissionCitation(
            citation_id="FLEX:TEST-2", title="FLEX metadata", source="Local publication",
            evidence_status="Local record — provenance unverified",
            evidence_class="local_provenance_unverified", investigation_acronym="FLEX",
            relevance_explanation="Second source fixture.",
        )
        second_record = SimpleNamespace(
            evidence_id="LOCAL-FLEX", investigation_title="FLEX record", investigation_acronym="FLEX",
            evidence_class="local_provenance_unverified", evidence_status="Local record — provenance unverified",
            experiment_type="Flame spread metadata", fuel_types="Cotton fabric", oxidizer_environment="Air",
            gravity_environment="Microgravity", facility="Fixture", flight_mission="Not verified",
            measured_parameters="Flame spread", findings=[], publications=[second_citation],
        )
        records[second_record.evidence_id] = second_record
        citations[second_citation.citation_id] = second_citation
        text = (
            'The local provenance-unverified SAFFIRE record lists "PMMA sheets" and '
            'the local provenance-unverified FLEX record lists "Cotton fabric".'
        )
        claim = self.claim(text, "evidence_summary", [
            self.source_ref(first_record.evidence_id, [first_citation.citation_id], "PMMA sheets", first_record.evidence_status),
            self.source_ref(second_record.evidence_id, [second_citation.citation_id], "Cotton fabric", second_record.evidence_status),
        ])
        MissionIntelligenceService(client=Mock())._validate_claim(claim, "Mission Safety Synthesizer", citations, records)

    def test_partial_specialist_failure_keeps_valid_roles_and_marks_response_partial(self):
        scenario = self.parameters().model_dump(mode="json")
        invalid_claim = {
            "claim_text": "The local SAFFIRE record states an unsupported result.",
            "claim_type": "evidence_summary",
            "sources": [{"evidence_id": "MISSING-RECORD", "citation_ids": ["MISSING-CITATION"],
                         "source_excerpt": "not retrieved", "provenance_status": "unknown"}],
            "uncertainty": "",
        }
        valid_claim = {
            "claim_text": "Combustion depends on fuel, heat, and an oxidizer.",
            "claim_type": "general_scientific_context", "sources": [], "uncertainty": "",
        }
        first_response = {"specialist_analyses": [
            {"role": role, "scenario_parameters": scenario,
             "claims": [invalid_claim, valid_claim] if role == "Combustion Analyst" else [valid_claim]}
            for role in SPECIALIST_ROLES[:4]
        ]}
        synthesis_claim = {
            "claim_text": "This hypothetical mission outcome remains uncertain.",
            "claim_type": "hypothetical_inference", "sources": [],
            "uncertainty": "The retrieved packet does not establish the combined scenario.",
        }
        synthesis_response = {
            "scenario_parameters": scenario,
            "analysis_claims": [synthesis_claim],
            "combined_assessment_claims": [synthesis_claim],
            "conflict_assessment": "No conflicts identified among the validated specialist claims.",
            "main_documented_findings": [], "conflicting_claims": [],
            "important_uncertainties": [],
            "research_gaps": ["Combustion Analyst had one rejected evidence claim."],
            "supporting_citation_ids": [],
        }
        gemini = Mock()
        gemini.models.generate_content.side_effect = [
            SimpleNamespace(text=json.dumps(first_response)),
            SimpleNamespace(text=json.dumps(synthesis_response)),
        ]
        ntrs = Mock()
        ntrs.search_citations = AsyncMock(return_value=[])
        result = asyncio.run(MissionIntelligenceService(client=gemini, ntrs_service=ntrs).analyze(
            self.db, self.parameters(), "Test partial claim handling"
        ))
        combustion = next(item for item in result.specialist_analyses if item.role == "Combustion Analyst")
        self.assertEqual(result.evidence_validation_status, "partial")
        self.assertEqual(combustion.evidence_validation_status, "partial")
        self.assertIn("Combustion depends on fuel", combustion.analysis)
        self.assertNotIn("unsupported result", combustion.analysis)
        self.assertTrue(result.evidence_validation_issues)
        self.assertEqual(gemini.models.generate_content.call_count, 2)
        synthesis_prompt = gemini.models.generate_content.call_args_list[1].kwargs["contents"]
        self.assertIn('"validation_status": "partial"', synthesis_prompt)
        self.assertNotIn("unsupported result", synthesis_prompt)

    def test_missing_combustion_evidence_reference_is_omitted_and_synthesis_continues(self):
        """Reproduce the live failure shape without calling Gemini or inventing NASA evidence."""
        investigation = self.add_local_record()
        citation_id = "SAFFIRE:TEST-NTRS-001"
        scenario = self.parameters().model_dump(mode="json")
        missing_reference_claim = {
            "claim_text": (
                'The local provenance-unverified SAFFIRE record lists '
                '"PMMA (polymethyl methacrylate) sheets" in its stored fuel/material field.'
            ),
            "claim_type": "evidence_summary",
            "sources": [],
            "uncertainty": "The stored description does not verify experimental measurements.",
        }
        first_stage = self.first_stage_response()
        combustion = first_stage["specialist_analyses"][0]
        self.assertEqual(combustion["role"], "Combustion Analyst")
        combustion["claims"] = [missing_reference_claim, *combustion["claims"]]

        gemini_client = Mock()
        gemini_client.models.generate_content.side_effect = [
            SimpleNamespace(text=json.dumps(first_stage)),
            SimpleNamespace(text=json.dumps(self.synthesis_response())),
        ]
        ntrs_service = Mock()
        ntrs_service.search_citations = AsyncMock(return_value=[])
        service = MissionIntelligenceService(client=gemini_client, ntrs_service=ntrs_service)

        result = asyncio.run(service.analyze(
            self.db,
            self.parameters(),
            "How does this hypothetical PMMA scenario compare with retrieved combustion research?",
        ))

        self.assertEqual(gemini_client.models.generate_content.call_count, 2)
        self.assertEqual(result.evidence_validation_status, "partial")
        self.assertEqual(
            [item.role for item in result.specialist_analyses],
            list(SPECIALIST_ROLES),
        )
        combustion_output = result.specialist_analyses[0]
        self.assertEqual(combustion_output.evidence_validation_status, "partial")
        self.assertNotIn("lists", combustion_output.analysis)
        self.assertIn("As a hypothetical inference", combustion_output.analysis)
        self.assertEqual(combustion_output.relevant_evidence, [])
        self.assertEqual(combustion_output.citations, [])

        first_prompt = gemini_client.models.generate_content.call_args_list[0].kwargs["contents"]
        synthesis_prompt = gemini_client.models.generate_content.call_args_list[1].kwargs["contents"]
        self.assertIn(f"Evidence ID: {investigation.investigation_id}", first_prompt)
        self.assertIn(citation_id, first_prompt)
        self.assertIn("Local record — provenance unverified", first_prompt)
        self.assertIn('"validation_status": "partial"', synthesis_prompt)
        self.assertNotIn(missing_reference_claim["claim_text"], synthesis_prompt)

    def test_evidence_summary_without_any_source_object_is_rejected(self):
        citation, record, citations, records = self._claim_fixture()
        claim = self.claim(
            'The local provenance-unverified SAFFIRE record lists "PMMA sheets".',
            "evidence_summary",
            [],
        )
        with self.assertRaisesRegex(RuntimeError, "no record citations"):
            MissionIntelligenceService(client=Mock())._validate_claim(
                claim, "Combustion Analyst", citations, records
            )

    def test_valid_claims_from_all_four_roles_reach_synthesis_and_bad_claim_is_omitted(self):
        investigation = self.add_local_record()
        evidence_id = investigation.investigation_id
        citation_id = "SAFFIRE:TEST-NTRS-001"
        scenario = self.parameters().model_dump(mode="json")
        first_stage = self.first_stage_response(evidence_id, citation_id)
        bad_claim = {
            "claim_text": "The local SAFFIRE record proves a lunar habitat outcome.",
            "claim_type": "historical_experimental",
            "sources": [],
            "uncertainty": "",
        }
        first_stage["specialist_analyses"][0]["claims"] = [
            *first_stage["specialist_analyses"][0]["claims"], bad_claim
        ]

        gemini = Mock()
        gemini.models.generate_content.side_effect = [
            SimpleNamespace(text=json.dumps(first_stage)),
            SimpleNamespace(text=json.dumps(self.synthesis_response(evidence_id, citation_id))),
        ]
        ntrs = Mock()
        ntrs.search_citations = AsyncMock(return_value=[])
        result = asyncio.run(MissionIntelligenceService(client=gemini, ntrs_service=ntrs).analyze(
            self.db, self.parameters(), "Compare the hypothetical scenario with local fixture records."
        ))

        self.assertEqual(result.scenario_parameters.model_dump(mode="json"), scenario)
        self.assertEqual(len(result.specialist_analyses), 5)
        for specialist in result.specialist_analyses[:4]:
            self.assertIn("local provenance-unverified SAFFIRE record lists", specialist.analysis)
            self.assertIn("hypothetical inference", specialist.analysis)
            self.assertEqual(len(specialist.relevant_evidence), 1)
            self.assertEqual(len(specialist.citations), 1)
        combustion = result.specialist_analyses[0]
        self.assertEqual(combustion.evidence_validation_status, "partial")
        self.assertEqual(combustion.evidence_validation_diagnostics[0].reason_code, "missing_source_reference")
        self.assertNotIn("proves a lunar habitat outcome", combustion.analysis)
        self.assertTrue(result.specialist_analyses[4].analysis)
        self.assertEqual(result.evidence_validation_status, "partial")
        synthesis_prompt = gemini.models.generate_content.call_args_list[1].kwargs["contents"]
        self.assertGreaterEqual(synthesis_prompt.count("local provenance-unverified SAFFIRE record lists"), 4)
        self.assertNotIn("proves a lunar habitat outcome", synthesis_prompt)

    def test_four_unvalidated_specialists_are_disclosed_and_synthesis_continues(self):
        """Match the live partial-result shape when all first-stage claims lack source refs."""
        investigation = self.add_local_record()
        evidence_id = investigation.investigation_id
        citation_id = "SAFFIRE:TEST-NTRS-001"
        first_stage = self.first_stage_response()
        unsupported_summary = {
            "claim_text": (
                'The local provenance-unverified SAFFIRE record lists '
                '"PMMA (polymethyl methacrylate) sheets" in its stored record.'
            ),
            "claim_type": "evidence_summary",
            "sources": [],
            "uncertainty": "This test fixture does not independently verify measurements.",
        }
        for specialist in first_stage["specialist_analyses"]:
            specialist["claims"] = [unsupported_summary]

        gemini_client = Mock()
        gemini_client.models.generate_content.side_effect = [
            SimpleNamespace(text=json.dumps(first_stage)),
            SimpleNamespace(text=json.dumps(self.synthesis_response(evidence_id, citation_id))),
        ]
        ntrs_service = Mock()
        ntrs_service.search_citations = AsyncMock(return_value=[])
        service = MissionIntelligenceService(client=gemini_client, ntrs_service=ntrs_service)

        result = asyncio.run(service.analyze(
            self.db,
            self.parameters(),
            "Compare the hypothetical scenario with the retrieved local research record.",
        ))

        self.assertEqual(gemini_client.models.generate_content.call_count, 2)
        self.assertEqual(result.evidence_validation_status, "partial")
        self.assertEqual(
            [item.role for item in result.specialist_analyses],
            list(SPECIALIST_ROLES),
        )
        for specialist in result.specialist_analyses[:4]:
            self.assertEqual(specialist.evidence_validation_status, "no_valid_claims")
            self.assertEqual(len(specialist.evidence_validation_diagnostics), 1)
            self.assertEqual(specialist.evidence_validation_diagnostics[0].reason_code, "missing_source_reference")
            self.assertEqual(specialist.analysis, "No claim passed evidence validation for this specialist.")
            self.assertEqual(specialist.relevant_evidence, [])
            self.assertEqual(specialist.citations, [])
        self.assertEqual(result.specialist_analyses[4].role, "Mission Safety Synthesizer")
        self.assertEqual(result.specialist_analyses[4].evidence_validation_status, "validated")
        self.assertTrue(result.specialist_analyses[4].analysis)
        self.assertEqual(len(result.evidence_validation_issues), 4)
        self.assertEqual(len(result.evidence_validation_diagnostics), 4)

        synthesis_prompt = gemini_client.models.generate_content.call_args_list[1].kwargs["contents"]
        self.assertEqual(synthesis_prompt.count('"validation_status": "no_valid_claims"'), 4)
        self.assertNotIn(unsupported_summary["claim_text"], synthesis_prompt)

    def test_conflicting_claims_name_multiple_specialist_roles(self):
        with self.assertRaisesRegex(RuntimeError, "at least two specialist roles"):
            MissionIntelligenceService._validate_conflicting_claims([
                "Combustion Analyst reported a different conclusion."
            ])
        MissionIntelligenceService._validate_conflict_assessment([], "No conflicts identified.")
        with self.assertRaisesRegex(RuntimeError, "explicitly report"):
            MissionIntelligenceService._validate_conflict_assessment([], "The specialists analyzed the evidence.")

    def test_ntrs_metadata_is_preserved_without_claiming_measurement_verification(self):
        evidence = MissionEvidenceService().retrieve(self.db, self.parameters())
        ntrs_service = Mock()
        ntrs_service.search_citations = AsyncMock(return_value=[{
            "ntrs_id": "20260001234",
            "title": "NTRS metadata fixture",
            "source": "NASA Technical Reports Server (NTRS)",
            "authors": "Fixture Author",
            "year": 2026,
            "doi": "10.5555/ntrs.fixture",
            "url": "https://ntrs.nasa.gov/citations/20260001234",
            "abstract": "Publication metadata fixture; not a verified measurement.",
        }])
        service = MissionIntelligenceService(client=Mock(), ntrs_service=ntrs_service)

        asyncio.run(service._add_ntrs_metadata(evidence, self.parameters()))

        citation = evidence.citations[0]
        self.assertEqual(citation.citation_id, "NTRS:20260001234")
        self.assertEqual(citation.title, "NTRS metadata fixture")
        self.assertEqual(citation.doi, "10.5555/ntrs.fixture")
        self.assertEqual(citation.identifier, "20260001234")
        self.assertEqual(citation.evidence_status, "Publication metadata retrieved; measurements not verified")
        self.assertEqual(citation.evidence_class, "publication_metadata_only")
        self.assertIn("not a retrieved NASA PSI dataset", citation.relevance_explanation)
        self.assertEqual(
            MissionIntelligenceService._overall_evidence_status(evidence),
            "Publication metadata retrieved; measurements not verified",
        )

    def test_documented_findings_must_match_a_record_and_its_citation(self):
        investigation = self.add_local_record()
        evidence = MissionEvidenceService().retrieve(self.db, self.parameters())
        citations = {item.citation_id: item for item in evidence.citations}
        citation_id = "SAFFIRE:TEST-NTRS-001"

        documented = MissionIntelligenceService._validate_generated_finding(
            {
                "finding": "The local record describes PMMA flame behavior.",
                "citation_ids": [citation_id],
            },
            citations,
            evidence.records,
        )
        self.assertEqual(documented.citations[0].investigation_acronym, investigation.acronym)

        with self.assertRaisesRegex(RuntimeError, "does not exactly match"):
            MissionIntelligenceService._validate_generated_finding(
                {
                    "finding": "PMMA has a documented safe oxygen threshold.",
                    "citation_ids": [citation_id],
                },
                citations,
                evidence.records,
            )

        ntrs_only = {
            "NTRS:20260001234": MissionCitation(
                citation_id="NTRS:20260001234",
                title="Unrelated NTRS metadata",
                source="NTRS",
                evidence_status="Publication metadata retrieved; measurements not verified",
                relevance_explanation="Metadata only",
            )
        }
        with self.assertRaisesRegex(RuntimeError, "without a citation associated"):
            MissionIntelligenceService._validate_generated_finding(
                {
                    "finding": "The local record describes PMMA flame behavior.",
                    "citation_ids": ["NTRS:20260001234"],
                },
                ntrs_only,
                evidence.records,
            )

    def test_gemini_provider_failure_and_invalid_ai_json_are_controlled(self):
        provider_failure = Mock()
        provider_failure.models.generate_content.side_effect = OSError("mock provider outage with private details")
        unavailable_service = MissionIntelligenceService(
            client=provider_failure,
            ntrs_service=Mock(search_citations=AsyncMock(return_value=[])),
        )
        with self.assertRaisesRegex(RuntimeError, "temporarily unavailable.*network_or_timeout") as raised:
            asyncio.run(unavailable_service.analyze(self.db, self.parameters()))
        self.assertNotIn("private details", str(raised.exception))

        quota_error = SimpleNamespace(code=429, status="RESOURCE_EXHAUSTED")
        details = MissionIntelligenceService._provider_failure_details(quota_error)
        self.assertEqual(details, ("quota_or_rate_limit", 429, "RESOURCE_EXHAUSTED"))

        auth_error = SimpleNamespace(code=401, status="UNAUTHENTICATED")
        details = MissionIntelligenceService._provider_failure_details(auth_error)
        self.assertEqual(details, ("authentication", 401, "UNAUTHENTICATED"))

        model_error = SimpleNamespace(code=404, status="NOT_FOUND")
        details = MissionIntelligenceService._provider_failure_details(model_error)
        self.assertEqual(details, ("model_or_endpoint_unavailable", 404, "NOT_FOUND"))

        invalid_response_client = Mock()
        invalid_response_client.models.generate_content.return_value = SimpleNamespace(text="not-json")
        invalid_service = MissionIntelligenceService(
            client=invalid_response_client,
            ntrs_service=Mock(search_citations=AsyncMock(return_value=[])),
        )
        with self.assertRaisesRegex(RuntimeError, "invalid specialist analysis response"):
            asyncio.run(invalid_service.analyze(self.db, self.parameters()))


if __name__ == "__main__":
    unittest.main()
