import asyncio
import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models.investigation import CombustionDataPoint, Investigation
from app.routes import mission as mission_route
from app.services.mission_service import MissionIntelligenceService
from app.schemas.investigation import CombustionDataPointResponse
from app.schemas.mission import (
    MissionAnalysisRequest,
    MissionAnalysisResponse,
    MissionSynthesisDetails,
    MissionParameters,
    ResearchGapReport,
    SpecialistAnalysis,
    SPECIALIST_ROLES,
)
from app.services.analytics_service import AnalyticsService


class PhaseOneAuditTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.session_factory = sessionmaker(bind=self.engine, autoflush=False)
        self.db = self.session_factory()

        self.api_app = FastAPI()
        self.api_app.include_router(mission_route.router)

        def override_get_db():
            yield self.db

        self.api_app.dependency_overrides[get_db] = override_get_db

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def post_json(self, path, payload):
        async def send_request():
            async with AsyncClient(
                transport=ASGITransport(app=self.api_app),
                base_url="http://test",
            ) as client:
                return await client.post(path, json=payload)

        return asyncio.run(send_request())

    @staticmethod
    def valid_mission_payload():
        return {
            "parameters": {
                "environment": "ISS Cabin",
                "oxygen_percent": 21,
                "pressure_atm": 1.0,
                "airflow_cm_s": 10,
                "gravity": "microgravity",
                "material": "pmma",
            }
        }

    @staticmethod
    def lunar_mission_payload():
        return {
            "parameters": {
                "environment": "Lunar Habitat",
                "oxygen_percent": 34.0,
                "pressure_atm": 0.56,
                "airflow_cm_s": 15.0,
                "gravity": "lunar",
                "material": "pmma",
            },
            "question": "How does 34% oxygen affect PMMA combustion in a lunar habitat?",
        }

    @staticmethod
    def mock_mission_response(parameters=None, environment="Lunar Habitat"):
        parameters = parameters or MissionParameters(
            environment=environment,
            oxygen_percent=21,
            pressure_atm=1.0,
            airflow_cm_s=10,
            gravity="microgravity",
            material="pmma",
        )
        return MissionAnalysisResponse(
            environment=parameters.environment,
            scenario_parameters=parameters,
            specialist_analyses=[
                SpecialistAnalysis(
                    role=role,
                    analysis="The available evidence is insufficient for a scientific conclusion.",
                    evidence_status="Insufficient evidence",
                )
                for role in SPECIALIST_ROLES
            ],
            mission_synthesis="The available evidence is insufficient for a scientific conclusion.",
            synthesis_details=MissionSynthesisDetails(
                combined_assessment="The available evidence is insufficient for a scientific conclusion.",
                conflict_assessment="No conflicts identified among the four specialist outputs.",
            ),
            citations=[],
            evidence_matches=[],
            research_gaps=ResearchGapReport(),
            evidence_status="Insufficient evidence",
            evidence_limitations=["No verified experimental measurements were provided."],
        )

    def add_local_investigation_with_flagged_datapoint(self):
        investigation = Investigation(
            investigation_id="LOCAL-AUDIT-RECORD",
            title="Local audit fixture",
            acronym="AUDIT",
            category="Test record",
            description="Local fixture; not a NASA source.",
        )
        investigation.datapoints.append(
            CombustionDataPoint(
                fuel_name="fixture fuel",
                fuel_state="Solid Sheet",
                burn_rate_or_flame_speed=987.65,
                unit="fixture units",
                is_measured_flight_data=True,
                source_reference="unverified fixture source",
            )
        )
        self.db.add(investigation)
        self.db.commit()
        return investigation

    def test_mission_request_schema_rejects_out_of_range_input(self):
        payload = self.valid_mission_payload()
        payload["parameters"]["oxygen_percent"] = 41
        with self.assertRaises(ValidationError):
            MissionAnalysisRequest.model_validate(payload)

    def test_valid_nested_request_and_route_preserve_exact_parameters(self):
        payload = self.lunar_mission_payload()
        validated = MissionAnalysisRequest.model_validate(payload)
        self.assertEqual(validated.parameters.environment, "Lunar Habitat")
        self.assertEqual(validated.parameters.oxygen_percent, 34.0)
        self.assertEqual(validated.parameters.pressure_atm, 0.56)
        self.assertEqual(validated.parameters.airflow_cm_s, 15.0)

        fake_service = Mock()
        fake_service.analyze = AsyncMock(
            side_effect=lambda db, parameters, question: self.mock_mission_response(parameters)
        )
        with patch.object(mission_route, "mission_service", fake_service):
            response = self.post_json("/api/mission/analyze", payload)

        self.assertEqual(response.status_code, 200)
        call = fake_service.analyze.await_args
        received = call.kwargs["parameters"]
        self.assertEqual(received.environment, "Lunar Habitat")
        self.assertEqual(received.oxygen_percent, 34.0)
        self.assertEqual(received.pressure_atm, 0.56)
        self.assertEqual(received.airflow_cm_s, 15.0)
        self.assertEqual(call.kwargs["question"], payload["question"])

        body = response.json()
        self.assertEqual(body["environment"], "Lunar Habitat")
        self.assertEqual(body["scenario_parameters"]["pressure_atm"], 0.56)
        self.assertEqual(
            {item["role"] for item in body["specialist_analyses"]},
            set(SPECIALIST_ROLES),
        )
        self.assertIn("mission_synthesis", body)
        self.assertIn("citations", body)
        self.assertIn("evidence_status", body)
        self.assertIn("disclaimer", body)

        forty_percent_payload = self.lunar_mission_payload()
        forty_percent_payload["parameters"]["oxygen_percent"] = 40.0
        with patch.object(mission_route, "mission_service", fake_service):
            forty_response = self.post_json("/api/mission/analyze", forty_percent_payload)
        self.assertEqual(forty_response.status_code, 200)
        forty_call = fake_service.analyze.await_args
        self.assertEqual(forty_call.kwargs["parameters"].oxygen_percent, 40.0)

    def test_invalid_oxygen_pressure_and_missing_parameters_return_422(self):
        invalid_oxygen = self.lunar_mission_payload()
        invalid_oxygen["parameters"]["oxygen_percent"] = 41
        self.assertEqual(
            self.post_json("/api/mission/analyze", invalid_oxygen).status_code,
            422,
        )

        invalid_pressure = self.lunar_mission_payload()
        invalid_pressure["parameters"]["pressure_atm"] = 1.6
        self.assertEqual(
            self.post_json("/api/mission/analyze", invalid_pressure).status_code,
            422,
        )

        missing_pressure = self.lunar_mission_payload()
        del missing_pressure["parameters"]["pressure_atm"]
        self.assertEqual(
            self.post_json("/api/mission/analyze", missing_pressure).status_code,
            422,
        )

    def test_missing_gemini_configuration_returns_controlled_503(self):
        unavailable_service = MissionIntelligenceService(
            client=None,
            ntrs_service=Mock(),
        )
        with patch.object(mission_route, "mission_service", unavailable_service):
            response = self.post_json("/api/mission/analyze", self.lunar_mission_payload())

        self.assertEqual(response.status_code, 503)
        self.assertIn("Gemini is not configured", response.json()["detail"])

    def test_mocked_gemini_success_returns_all_five_roles_and_uses_exact_values(self):
        scenario_parameters = MissionParameters.model_validate(
            self.lunar_mission_payload()["parameters"]
        )
        mocked_specialists = {
            "specialist_analyses": [
                {
                    "role": role,
                    "scenario_parameters": scenario_parameters.model_dump(mode="json"),
                    "claims": [{
                        "claim_text": "This hypothetical scenario remains uncertain.",
                        "claim_type": "hypothetical_inference",
                        "sources": [],
                        "uncertainty": "No matching records were retrieved.",
                    }],
                }
                for role in SPECIALIST_ROLES[:4]
            ],
        }
        mocked_synthesis = {
            "scenario_parameters": scenario_parameters.model_dump(mode="json"),
            "analysis_claims": [{
                "claim_text": "The submitted scenario remains hypothetical and uncertain.",
                "claim_type": "hypothetical_inference",
                "sources": [],
                "uncertainty": "No matching records were retrieved.",
            }],
            "combined_assessment_claims": [{
                "claim_text": "The hypothetical scenario's effects remain uncertain.",
                "claim_type": "hypothetical_inference",
                "sources": [],
                "uncertainty": "No evidence establishes the combined conditions.",
            }],
            "conflict_assessment": "No conflicts identified among the four specialist outputs.",
            "main_documented_findings": [],
            "conflicting_claims": [],
            "important_uncertainties": ["No matching records were retrieved."],
            "research_gaps": ["No evidence is available for this scenario."],
            "supporting_citation_ids": [],
        }
        gemini_client = Mock()
        gemini_client.models.generate_content.side_effect = [
            SimpleNamespace(text=json.dumps(mocked_specialists)),
            SimpleNamespace(text=json.dumps(mocked_synthesis)),
        ]
        ntrs_service = Mock()
        ntrs_service.search_citations = AsyncMock(return_value=[])
        service = MissionIntelligenceService(
            client=gemini_client,
            ntrs_service=ntrs_service,
        )
        request = MissionAnalysisRequest.model_validate(self.lunar_mission_payload())

        result = asyncio.run(
            service.analyze(
                db=self.db,
                parameters=request.parameters,
                question=request.question,
            )
        )

        self.assertEqual(
            {item.role for item in result.specialist_analyses},
            set(SPECIALIST_ROLES),
        )
        self.assertEqual(result.environment, "Lunar Habitat")
        self.assertEqual(result.evidence_status, "Insufficient evidence")
        self.assertEqual(result.citations, [])
        self.assertEqual(gemini_client.models.generate_content.call_count, 2)
        first_prompt = gemini_client.models.generate_content.call_args_list[0].kwargs["contents"]
        synthesis_prompt = gemini_client.models.generate_content.call_args_list[1].kwargs["contents"]
        self.assertIn('"oxygen_percent": 34.0', first_prompt)
        self.assertIn('"pressure_atm": 0.56', first_prompt)
        self.assertIn('"airflow_cm_s": 15.0', first_prompt)
        self.assertIn(request.question, first_prompt)
        self.assertIn("VALIDATED SPECIALIST HANDOFF", synthesis_prompt)

    def test_legacy_flag_does_not_prove_flight_provenance(self):
        investigation = self.add_local_investigation_with_flagged_datapoint()
        evidence = MissionIntelligenceService(client=None)._retrieve_evidence(self.db)
        self.assertIn("Local record — provenance unverified", evidence["context"])
        self.assertNotIn("987.65", evidence["context"])

        self.assertEqual(AnalyticsService.get_datapoints(self.db, flight_only=True), [])
        records = AnalyticsService.get_datapoints(self.db, flight_only=False)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["evidence_status"], "Local record — provenance unverified")
        self.assertTrue(records[0]["legacy_measured_flag"])

        datapoint = investigation.datapoints[0]
        response = CombustionDataPointResponse.model_validate(datapoint, from_attributes=True)
        self.assertEqual(response.evidence_status, "Local record — provenance unverified")
        self.assertTrue(response.legacy_measured_flag)
        self.assertNotIn("is_measured_flight_data", response.model_dump())

if __name__ == "__main__":
    unittest.main()
