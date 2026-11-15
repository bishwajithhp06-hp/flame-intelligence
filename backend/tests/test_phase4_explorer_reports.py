import json
import unittest
import asyncio

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models.investigation import SourceReference
from app.models.nasa_data import ProcessedResearchRecord, RawSourceRecord
from app.routes import experiments, reports
from app.schemas.mission import (
    MissionCitation,
    MissionAnalysisResponse,
    MissionParameters,
    MissionSynthesisDetails,
    SPECIALIST_ROLES,
    SpecialistAnalysis,
)
from app.services.experiment_explorer_service import ExperimentExplorerService


class PhaseFourExplorerTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.session_factory = sessionmaker(bind=self.engine, autoflush=False)
        self.db = self.session_factory()
        self.psi = SourceReference(
            source_name="NASA PSI",
            resource_id="NASA-PSI-REPO",
            resource_type="Research repository",
            title="NASA PSI",
            url="https://psi.nasa.gov/physci/repo",
            retrieval_status="dataset_file_retrieved",
            provenance_status="nasa_origin_source_link_verified",
        )
        self.ntrs = SourceReference(
            source_name="NASA NTRS",
            resource_id="NASA-NTRS-API",
            resource_type="Publication API",
            title="NASA NTRS",
            url="https://ntrs.nasa.gov",
            retrieval_status="retrieved",
            provenance_status="publication_metadata_only",
        )
        self.db.add_all([self.psi, self.ntrs])
        self.db.flush()

        psi_raw = RawSourceRecord(
            source_reference_id=self.psi.id,
            record_kind="psi_investigation",
            source_record_id="PSI-TEST",
            source_url="https://psi.nasa.gov/physci/repo/data/investigations/PSI-TEST",
            content_type="application/json",
            payload_json="{}",
            payload_sha256="a" * 64,
            payload_size_bytes=2,
        )
        ntrs_raw = RawSourceRecord(
            source_reference_id=self.ntrs.id,
            record_kind="ntrs_publication",
            source_record_id="12345678901",
            source_url="https://ntrs.nasa.gov/citations/12345678901",
            content_type="application/json",
            payload_json="{}",
            payload_sha256="b" * 64,
            payload_size_bytes=2,
        )
        file_raw = RawSourceRecord(
            source_reference_id=self.psi.id,
            record_kind="psi_dataset_file",
            source_record_id="PSI-TEST/file.csv/v1",
            source_url="https://psi.nasa.gov/physci/repo/data/investigations/PSI-TEST/file.csv",
            content_type="text/csv",
            payload_bytes=b"raw,csv\n",
            payload_sha256="c" * 64,
            payload_size_bytes=8,
        )
        self.db.add_all([psi_raw, ntrs_raw, file_raw])
        self.db.flush()
        self.psi_record = ProcessedResearchRecord(
            source_reference_id=self.psi.id,
            raw_record_id=psi_raw.id,
            record_kind="psi_investigation",
            source_record_id="PSI-TEST",
            title="Test Flame Extinguishment Experiment",
            description="Metadata description with FLEX identifier.",
            experiment_type="Microgravity Investigation",
            experiment_context_type="flight_experiment",
            material_classification=None,
            units_json="{}",
            normalized_metadata_json=json.dumps({
                "accession": "PSI-TEST",
                "experimental_conditions": None,
                "dataset_links": [{"file_name": "file.csv", "source_url": "https://psi.nasa.gov/file.csv"}],
                "measurement_values_imported": False,
            }),
            publication_references_json=json.dumps([{"title": "PSI source paper", "doi": "10.5555/psi.1"}]),
            dataset_links_json="[]",
            provenance_category="nasa_origin_source_link_verified",
        )
        self.ntrs_record = ProcessedResearchRecord(
            source_reference_id=self.ntrs.id,
            raw_record_id=ntrs_raw.id,
            record_kind="ntrs_publication",
            source_record_id="12345678901",
            title="Microgravity Combustion Publication",
            description="Publication abstract about microgravity combustion.",
            experiment_type="publication",
            experiment_context_type="unknown",
            material_classification=None,
            units_json="{}",
            normalized_metadata_json=json.dumps({
                "title": "Microgravity Combustion Publication",
                "abstract": "Publication abstract about microgravity combustion.",
                "ntrs_id": "12345678901",
                "url": "https://ntrs.nasa.gov/citations/12345678901",
                "year": 2024,
                "doi": "10.5555/ntrs.1",
                "authors": "A Researcher",
                "experimental_conditions": None,
            }),
            publication_references_json="[]",
            dataset_links_json="[]",
            provenance_category="publication_metadata_only",
        )
        file_record = ProcessedResearchRecord(
            source_reference_id=self.psi.id,
            raw_record_id=file_raw.id,
            record_kind="psi_dataset_file",
            source_record_id="PSI-TEST/file.csv/v1",
            title="file.csv",
            description=None,
            experiment_type=None,
            experiment_context_type="unknown",
            material_classification=None,
            units_json="{}",
            normalized_metadata_json=json.dumps({"file_name": "file.csv", "measurement_values_parsed": False}),
            publication_references_json="[]",
            dataset_links_json="[]",
            provenance_category="nasa_origin_source_link_verified",
        )
        self.db.add_all([self.psi_record, self.ntrs_record, file_record])
        self.db.commit()

        test_app = FastAPI()
        test_app.include_router(experiments.router)
        test_app.include_router(reports.router)

        def override_db():
            yield self.db

        test_app.dependency_overrides[get_db] = override_db
        self.api_app = test_app

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def request(self, method, path, *, params=None, json_body=None):
        async def send_request():
            async with AsyncClient(
                transport=ASGITransport(app=self.api_app),
                base_url="http://test",
            ) as client:
                return await client.request(method, path, params=params, json=json_body)

        return asyncio.run(send_request())

    def test_search_and_source_filter_return_only_stored_nasa_records(self):
        before = self.db.query(ProcessedResearchRecord).count()
        search = self.request("GET", "/api/experiments", params={"search": "FLEX"})
        source = self.request("GET", "/api/experiments", params={"source": "NASA NTRS"})
        self.assertEqual(search.status_code, 200)
        self.assertEqual([r["source_record_id"] for r in search.json()["records"]], ["PSI-TEST"])
        self.assertEqual(source.status_code, 200)
        self.assertEqual([r["record_kind"] for r in source.json()["records"]], ["ntrs_publication"])
        self.assertEqual(self.db.query(ProcessedResearchRecord).count(), before)

    def test_detail_distinguishes_raw_download_from_parsed_measurements_and_publication_metadata(self):
        response = self.request("GET", f"/api/experiments/{self.psi_record.id}")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["source_url"], "https://psi.nasa.gov/physci/repo/data/investigations/PSI-TEST")
        dataset = next(item for item in body["dataset_files"] if item["file_name"] == "file.csv")
        self.assertEqual(dataset["retrieval_status"], "retrieved")
        self.assertEqual(dataset["raw_size_bytes"], 8)
        self.assertFalse(dataset["measurements_parsed"])
        self.assertIn("not been parsed", dataset["note"])
        self.assertEqual(body["citations"][1]["doi"], "10.5555/psi.1")

        ntrs = self.request("GET", f"/api/experiments/{self.ntrs_record.id}").json()
        self.assertEqual(ntrs["evidence_status"], "NASA NTRS publication metadata; this record alone does not verify experimental measurements.")
        self.assertEqual(ntrs["citations"][0]["identifier"], "12345678901")
        self.assertEqual(ntrs["dataset_files"], [])

    def test_absent_structured_filters_are_not_inferred_from_narrative(self):
        response = self.request("GET", "/api/experiments").json()
        self.assertEqual(response["available_filters"]["material"], [])
        self.assertEqual(response["available_filters"]["gravity"], [])
        self.assertEqual(response["available_filters"]["environment"], [])
        self.assertIn("not converted into experimental conditions", response["conditions_notice"])
        filtered = self.request("GET", "/api/experiments", params={"gravity": "lunar"}).json()
        self.assertEqual(filtered["records"], [])

    def test_explicit_material_gravity_and_environment_filters_use_only_structured_fields(self):
        self.psi_record.material_classification = "PMMA"
        self.psi_record.normalized_metadata_json = json.dumps({
            "gravity_environment": "microgravity",
            "environment": "ISS",
        })
        self.db.commit()
        service = ExperimentExplorerService()
        result = service.list_records(
            self.db,
            material="PMMA",
            gravity="microgravity",
            environment="ISS",
        )
        self.assertEqual([item.source_record_id for item in result["records"]], ["PSI-TEST"])
        self.assertEqual(result["available_filters"]["material"], ["PMMA"])
        self.assertEqual(result["available_filters"]["gravity"], ["microgravity"])
        self.assertEqual(result["available_filters"]["environment"], ["ISS"])

    def test_comparison_does_not_treat_absent_or_incompatible_conditions_as_matches(self):
        response = self.request("POST", "/api/experiments/compare", json_body={
            "record_ids": [self.psi_record.id, self.ntrs_record.id],
        })
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["categorical_comparisons"], [{
            "field": "Experiment type",
            "left_value": "Microgravity Investigation",
            "right_value": "publication",
            "relationship": "different",
        }])
        self.assertEqual(body["quantitative_comparisons"], [])
        self.assertTrue(any("compatible, source-recorded units" in item for item in body["limitations"]))

    def test_comparison_only_accepts_explicit_conditions_with_valid_units(self):
        self.psi_record.normalized_metadata_json = json.dumps({
            "experimental_conditions": {"oxygen_percent": {"value": 34, "unit": "%"}},
        })
        self.ntrs_record.normalized_metadata_json = json.dumps({
            "experimental_conditions": {"oxygen_percent": {"value": 34, "unit": "percent"}},
        })
        self.db.commit()
        service = ExperimentExplorerService()
        result = service.compare(self.db, self.psi_record.id, self.ntrs_record.id)
        self.assertEqual(result.quantitative_comparisons, [{
            "field": "Oxygen concentration",
            "left_value": 34,
            "right_value": 34,
            "unit": "%",
            "relationship": "same",
        }])

        self.ntrs_record.normalized_metadata_json = json.dumps({
            "experimental_conditions": {"oxygen_percent": {"value": 34, "unit": "fraction"}},
        })
        self.db.commit()
        result = service.compare(self.db, self.psi_record.id, self.ntrs_record.id)
        self.assertEqual(result.quantitative_comparisons, [])

    def test_mission_report_is_a_pdf_with_parameters_provenance_and_sources(self):
        analysis = MissionAnalysisResponse(
            environment="Lunar Habitat",
            scenario_parameters=MissionParameters(
                environment="Lunar Habitat", oxygen_percent=34, pressure_atm=0.56,
                airflow_cm_s=15, gravity="lunar", material="pmma",
            ),
            specialist_analyses=[SpecialistAnalysis(
                role=role,
                analysis=f"{role} reports that the combined scenario is not documented.",
                evidence_status="Insufficient evidence",
                assumptions=["Values are hypothetical."],
                uncertainties=["No matching source condition is available."],
            ) for role in SPECIALIST_ROLES],
            mission_synthesis="The retrieved records do not document this combined scenario.",
            synthesis_details=MissionSynthesisDetails(
                combined_assessment="Insufficient direct evidence.",
                conflict_assessment="No conflicts identified among the four specialist outputs.",
                research_gaps=["Oxygen, pressure, and gravity combination is not documented."],
            ),
            citations=[MissionCitation(
                citation_id="TEST-PSI:1",
                title="Test NASA source reference",
                source="Test fixture",
                url="https://example.test/nasa-record",
                evidence_status="Test fixture citation; provenance unverified",
                evidence_class="local_provenance_unverified",
                relevance_explanation="A test-only source link.",
            )],
            evidence_matches=[],
            research_gaps={
                "supported_parameters": [],
                "partially_supported_parameters": [],
                "unsupported_parameters": [],
            },
            evidence_status="Insufficient evidence",
            evidence_limitations=["NASA source linkage does not validate measurements."],
        )
        response = self.request(
            "POST",
            "/api/reports/mission",
            params={"report_name": "Lunar Habitat PMMA case"},
            json_body=analysis.model_dump(mode="json"),
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith(b"%PDF-1.4"))
        self.assertEqual(response.headers["content-type"], "application/pdf")
        self.assertIn(b"Mission name: Lunar Habitat PMMA case", response.content)
        self.assertIn(b"Generated:", response.content)
        self.assertIn(b"Pressure: 0.56 atm", response.content)
        self.assertIn(b"PROVENANCE LIMITATIONS", response.content)
        self.assertIn(b"Mission Safety Synthesizer", response.content)
        self.assertIn(b"Test NASA source reference", response.content)
        self.assertIn(b"https://example.test/nasa-record", response.content)
        expected_xref = int(response.content.rsplit(b"startxref\n", 1)[1].splitlines()[0])
        self.assertEqual(expected_xref, response.content.index(b"xref\n"))
        self.assertIn(b"/Type /Pages /Kids", response.content)

    def test_experiment_comparison_report_uses_current_stored_records_and_citations(self):
        psi_metadata = json.loads(self.psi_record.normalized_metadata_json)
        psi_metadata["experimental_conditions"] = {"oxygen_percent": {"value": 34, "unit": "%"}}
        self.psi_record.normalized_metadata_json = json.dumps(psi_metadata)
        ntrs_metadata = json.loads(self.ntrs_record.normalized_metadata_json)
        ntrs_metadata["experimental_conditions"] = {"oxygen_percent": {"value": 34, "unit": "percent"}}
        self.ntrs_record.normalized_metadata_json = json.dumps(ntrs_metadata)
        self.db.commit()
        before = self.db.query(ProcessedResearchRecord).count()
        response = self.request(
            "POST",
            "/api/reports/experiments/compare",
            json_body={"record_ids": [self.psi_record.id, self.ntrs_record.id]},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF-1.4"))
        self.assertIn(b"Test Flame Extinguishment Experiment", response.content)
        self.assertIn(b"Microgravity Combustion Publication", response.content)
        self.assertIn(b"https://psi.nasa.gov/physci/repo/data/investigations/PSI-TEST", response.content)
        self.assertIn(b"https://ntrs.nasa.gov/citations/12345678901", response.content)
        self.assertIn(b"10.5555/ntrs.1", response.content)
        self.assertIn(b"Oxygen concentration: 34 / 34 %", response.content)
        self.assertIn(b"same", response.content)
        self.assertIn(b"No Mission Intelligence specialist analyses are attached", response.content)
        self.assertIn(b"Publication metadata is not measurement data", response.content)
        self.assertEqual(self.db.query(ProcessedResearchRecord).count(), before)

    def test_report_routes_reject_missing_mission_results_and_missing_comparison_records(self):
        missing_mission = self.request("POST", "/api/reports/mission", json_body={})
        missing_comparison = self.request(
            "POST",
            "/api/reports/experiments/compare",
            json_body={"record_ids": [99998, 99999]},
        )

        self.assertEqual(missing_mission.status_code, 422)
        self.assertEqual(missing_comparison.status_code, 404)


if __name__ == "__main__":
    unittest.main()
