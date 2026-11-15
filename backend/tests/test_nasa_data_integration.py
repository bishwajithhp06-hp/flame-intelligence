import asyncio
import json
import unittest
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.investigation import CombustionDataPoint, SourceReference
from app.models.nasa_data import ProcessedResearchRecord, RawSourceRecord
from app.schemas.mission import MissionParameters
from app.services.mission_evidence_service import MissionEvidenceService
from app.services.nasa_data_ingestion_service import NasaDataIngestionService, _experiment_context
from app.services.nasa_ntrs_service import NasaNtrsService
from app.services.nasa_psi_service import NasaPsiError, NasaPsiService


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=None, headers=None, content=None):
        self.status_code = status_code
        self._payload = payload
        self.text = text if text is not None else (json.dumps(payload) if payload is not None else "")
        self.headers = headers or {}
        self.content = content if content is not None else self.text.encode("utf-8")

    def json(self):
        if self._payload is None:
            raise ValueError("No JSON payload")
        return self._payload


class FakeStreamingResponse(FakeResponse):
    async def aiter_bytes(self):
        yield self.content


class FakeHttpClient:
    get_handler = None
    post_handler = None
    stream_handler = None
    requested = []

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def get(self, url, **kwargs):
        self.requested.append(("GET", url, kwargs))
        return type(self).get_handler(url, **kwargs)

    async def post(self, url, **kwargs):
        self.requested.append(("POST", url, kwargs))
        return type(self).post_handler(url, **kwargs)

    @asynccontextmanager
    async def stream(self, method, url, **kwargs):
        self.requested.append((method, url, kwargs))
        yield type(self).stream_handler(method, url, **kwargs)


class FakePsiIngestion:
    def __init__(self):
        self.last_http_status = 200

    async def search_investigations(self, query, limit, offset):
        if offset:
            return {"records": [], "total": 1, "failed_shards": 0}
        return {
            "records": [{"accession": "PSI-69", "raw_metadata": {"Title": "FLEX"}}],
            "total": 1,
            "failed_shards": 0,
        }

    async def get_investigation_metadata(self, accession):
        return {
            "accession": accession,
            "title": "Flame Extinguishment Experiment",
            "acronym": "FLEX",
            "projectType": "Microgravity Investigation",
            "experimentPlatform": "International Space Station (ISS)",
            "flightProgram": "ISS",
            "materials": "PMMA samples",
            "experimentalConditions": "Oxygen concentration range as reported in source metadata",
            "contacts": [{"name": "Source investigator"}],
            "publications": [{"title": "PSI-linked citation", "doi": "10.1234/example"}],
            "experimentalTable": [{
                "file_name": "PSI-69-table.csv",
                "file_size": 24,
                "s3_path": "psi-data/PSI-69/table.csv",
                "version": 3,
                "restricted": False,
            }],
        }

    @staticmethod
    def investigation_page_url(accession):
        return f"https://psi.nasa.gov/physci/repo/data/investigations/{accession}"

    @staticmethod
    def list_dataset_files(accession, metadata):
        item = metadata["experimentalTable"][0]
        return [{
            "file_name": item["file_name"],
            "remote_path": item["s3_path"],
            "file_size": item["file_size"],
            "version": item["version"],
            "restricted": item["restricted"],
            "source_url": FakePsiIngestion.investigation_page_url(accession),
        }]

    async def download_dataset_file(self, accession, file_reference, max_bytes):
        content = b"Condition,Unit\r\nTemperature,C\r\n"
        return {
            "content": content,
            "content_type": "text/csv",
            "size_bytes": len(content),
            "sha256": __import__("hashlib").sha256(content).hexdigest(),
            "source_url": file_reference["source_url"],
            "accession": accession,
            "file_name": file_reference["file_name"],
            "version": str(file_reference["version"]),
        }

    async def list_public_s3_objects(self, prefix, limit, continuation_token=None):
        self.last_http_status = 200
        return {
            "objects": [{
                "key": "DSI/fixture.csv", "size_bytes": 32, "last_modified": "2026-01-01T00:00:00Z",
                "etag": "fixture", "url": "https://nasa-psi.s3.us-west-2.amazonaws.com/DSI/fixture.csv",
            }],
            "prefixes": [], "is_truncated": True, "next_continuation_token": "page-2",
        }

    async def download_public_s3_object(self, key, max_bytes):
        self.last_http_status = 200
        content = b"Raw object fixture; no parsed values."
        return {
            "content": content, "content_type": "text/csv", "size_bytes": len(content),
            "sha256": __import__("hashlib").sha256(content).hexdigest(),
            "source_url": f"https://nasa-psi.s3.us-west-2.amazonaws.com/{key}", "key": key,
        }


class FakeNtrsIngestion:
    MAX_RESULTS = 500

    def __init__(self):
        self.last_http_status = 200
        self.last_error = None
        self.last_total = 1
        self.last_pages = 1

    async def search_citations(self, query, limit):
        return [{
            "ntrs_id": "20260001234",
            "title": "NASA citation fixture",
            "abstract": "Citation metadata only.",
            "authors": "A. Researcher",
            "year": 2026,
            "publication_date": "2026-05-01",
            "doi": "10.1234/ntrs.fixture",
            "publication": "NASA Technical Report",
            "url": "https://ntrs.nasa.gov/citations/20260001234",
            "download_links": [],
            "raw_metadata": {"id": "20260001234", "title": "NASA citation fixture"},
        }]


class NasaDataIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.db = sessionmaker(bind=self.engine, autoflush=False)()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_psi_search_and_details_parse_official_shape(self):
        def get_handler(url, **kwargs):
            if url.endswith("/repo/search"):
                return FakeResponse(payload={
                    "hits": {
                        "total": {"value": 1},
                        "hits": [{"_index": "investigation", "_source": {
                            "Accession": "PSI-69", "Title": "Flame Extinguishment Experiment", "Acronym": "FLEX"
                        }}],
                    },
                    "_shards": {"failed": 0},
                })
            return FakeResponse(payload={
                "accession": "PSI-69", "title": "Flame Extinguishment Experiment", "doi": "10.60555/example",
                "experimentalTable": [{"file_name": "table.csv", "s3_path": "psi-data/PSI-69/table.csv", "version": 5}],
            })

        FakeHttpClient.get_handler = get_handler
        FakeHttpClient.requested = []
        with patch("app.services.nasa_psi_service.httpx.AsyncClient", FakeHttpClient):
            async def exercise():
                service = NasaPsiService()
                result = await service.search_investigations("FLEX", limit=1, offset=0)
                details = await service.get_investigation_metadata("PSI-69")
                files = service.list_dataset_files("PSI-69", details)
                return result, details, files

            result, details, files = asyncio.run(exercise())

        self.assertEqual(result["records"][0]["accession"], "PSI-69")
        self.assertEqual(details["doi"], "10.60555/example")
        self.assertEqual(files[0]["file_name"], "table.csv")
        self.assertEqual(files[0]["version"], "5")
        self.assertEqual(len(FakeHttpClient.requested), 2)

    def test_psi_dataset_download_is_bounded_and_rejects_restricted_files(self):
        content = b"headers,only\r\n"

        def get_handler(url, **kwargs):
            return FakeResponse(text="https://psi-repo-prod.s3.amazonaws.com/signed?temporary=secret")

        def stream_handler(method, url, **kwargs):
            return FakeStreamingResponse(
                content=content,
                headers={"content-type": "text/csv", "content-length": str(len(content))},
            )

        FakeHttpClient.get_handler = get_handler
        FakeHttpClient.stream_handler = stream_handler
        FakeHttpClient.requested = []
        with patch("app.services.nasa_psi_service.httpx.AsyncClient", FakeHttpClient):
            async def exercise():
                service = NasaPsiService()
                return await service.download_dataset_file("PSI-69", {
                    "file_name": "table.csv", "file_size": len(content), "version": "5",
                    "restricted": False, "source_url": service.investigation_page_url("PSI-69"),
                })

            downloaded = asyncio.run(exercise())
            with self.assertRaises(NasaPsiError):
                asyncio.run(NasaPsiService().download_dataset_file("PSI-69", {
                    "file_name": "restricted.csv", "file_size": 1, "restricted": True,
                }))

        self.assertEqual(downloaded["content"], content)
        self.assertEqual(downloaded["size_bytes"], len(content))
        self.assertNotIn("temporary=secret", downloaded["source_url"])
        self.assertTrue(FakeHttpClient.requested[0][2]["params"]["redirect"] == "false")

    def test_ntrs_paginates_normalizes_fields_and_deduplicates(self):
        def post_handler(url, **kwargs):
            payload = kwargs["json"]
            offset = payload["page"]["from"]
            if offset == 0:
                items = [
                    {"id": f"NTRS-{i}", "title": f"Report {i}", "authorAffiliations": []}
                    for i in range(10)
                ]
            else:
                items = [
                    {"id": "NTRS-9", "title": "Duplicate report"},
                    {
                        "id": "NTRS-10", "title": "Last report", "abstract": "A complete abstract.",
                        "authorAffiliations": [{"meta": {"author": {"name": "Test Author"}}}],
                        "publications": [{"publicationDate": "2024-03-01", "doi": "10.1234/report", "publicationName": "NASA STI"}],
                    },
                    {"id": "NTRS-11", "title": "Another report"},
                ]
            return FakeResponse(payload={"stats": {"total": 12}, "results": items})

        FakeHttpClient.post_handler = post_handler
        FakeHttpClient.requested = []
        with patch("app.services.nasa_ntrs_service.httpx.AsyncClient", FakeHttpClient):
            async def exercise():
                service = NasaNtrsService()
                records = await service.search_citations("PMMA", limit=12)
                return service, records

            service, records = asyncio.run(exercise())

        self.assertEqual(len(records), 12)
        self.assertEqual(len({item["ntrs_id"] for item in records}), 12)
        self.assertEqual(service.last_pages, 2)
        self.assertEqual(records[10]["year"], 2024)
        self.assertEqual(records[10]["doi"], "10.1234/report")
        self.assertEqual(records[10]["abstract"], "A complete abstract.")
        self.assertEqual(records[10]["authors"], "Test Author")
        self.assertEqual(FakeHttpClient.requested[1][2]["json"]["page"]["from"], 10)

    def test_source_register_raw_dedup_and_processed_metadata(self):
        service = NasaDataIngestionService(FakePsiIngestion(), FakeNtrsIngestion())
        service.ensure_source_register(self.db)
        service.ensure_source_register(self.db)
        self.db.commit()
        self.assertEqual(self.db.query(SourceReference).count(), 3)

        async def ingest_twice():
            first = await service.ingest_psi_investigations(self.db, "FLEX", limit=1)
            second = await service.ingest_psi_investigations(self.db, "FLEX", limit=1)
            ntrs_first = await service.ingest_ntrs(self.db, "combustion", limit=1)
            ntrs_second = await service.ingest_ntrs(self.db, "combustion", limit=1)
            return first, second, ntrs_first, ntrs_second

        psi_first, psi_second, ntrs_first, ntrs_second = asyncio.run(ingest_twice())
        self.assertEqual(psi_first["raw_snapshots_inserted"], 1)
        self.assertEqual(psi_second["raw_snapshots_inserted"], 0)
        self.assertEqual(ntrs_first["raw_snapshots_inserted"], 1)
        self.assertEqual(ntrs_second["raw_snapshots_inserted"], 0)
        self.assertEqual(self.db.query(RawSourceRecord).count(), 2)
        processed = self.db.query(ProcessedResearchRecord).all()
        self.assertEqual(len(processed), 2)
        psi_record = next(row for row in processed if row.record_kind == "psi_investigation")
        self.assertEqual(psi_record.provenance_category, "nasa_origin_source_link_verified")
        self.assertEqual(json.loads(psi_record.investigators_json)[0]["name"], "Source investigator")
        self.assertEqual(len(json.loads(psi_record.dataset_links_json)), 1)
        source = self.db.query(SourceReference).filter_by(resource_id="NASA-PSI-REPO").one()
        self.assertEqual(source.retrieval_status, "retrieved")
        self.assertIsNotNone(source.last_retrieved_at)
        self.assertEqual(source.last_http_status, 200)
        self.assertIsNone(source.last_verified)
        self.assertEqual(source.status, "Not yet retrieved")
        self.assertIsNone(source.notes)
        self.assertEqual(self.db.query(CombustionDataPoint).count(), 0)

    def test_dataset_file_keeps_raw_bytes_headers_and_never_imports_measurements(self):
        service = NasaDataIngestionService(FakePsiIngestion(), FakeNtrsIngestion())

        async def ingest():
            return await service.ingest_psi_dataset(
                self.db, "PSI-69", "PSI-69-table.csv", max_bytes=1024
            )

        result = asyncio.run(ingest())
        raw = self.db.query(RawSourceRecord).one()
        processed = self.db.query(ProcessedResearchRecord).one()
        metadata = json.loads(processed.normalized_metadata_json)
        self.assertEqual(result["numeric_measurements_imported"], 0)
        self.assertEqual(raw.payload_bytes, b"Condition,Unit\r\nTemperature,C\r\n")
        self.assertEqual(metadata["csv_headers"], ["Condition", "Unit"])
        self.assertFalse(metadata["measurement_values_parsed"])
        self.assertEqual(self.db.query(CombustionDataPoint).count(), 0)

    def test_s3_listing_is_not_content_and_explicit_object_is_stored_raw(self):
        service = NasaDataIngestionService(FakePsiIngestion(), FakeNtrsIngestion())

        async def ingest():
            listing = await service.ingest_psi_s3_listing(self.db, prefix="DSI/", limit=10)
            object_result = await service.ingest_psi_s3_object(self.db, "DSI/fixture.csv", max_bytes=1024)
            return listing, object_result

        listing, object_result = asyncio.run(ingest())
        self.assertFalse(listing["content_retrieved"])
        self.assertEqual(listing["next_continuation_token"], "page-2")
        self.assertEqual(object_result["numeric_measurements_imported"], 0)
        self.assertEqual(self.db.query(RawSourceRecord).count(), 2)
        binary = self.db.query(RawSourceRecord).filter_by(record_kind="psi_s3_dataset_file").one()
        self.assertEqual(binary.payload_bytes, b"Raw object fixture; no parsed values.")
        self.assertEqual(self.db.query(CombustionDataPoint).count(), 0)

    def test_additive_migration_preserves_existing_source_register_row(self):
        from app.migrations import apply_additive_migrations

        old_engine = create_engine("sqlite://")
        try:
            with old_engine.begin() as connection:
                connection.exec_driver_sql(
                    "CREATE TABLE source_references (id INTEGER PRIMARY KEY, source_name VARCHAR(255), "
                    "resource_id VARCHAR(100), resource_type VARCHAR(100), title VARCHAR(500), url VARCHAR(500), "
                    "last_verified VARCHAR(50), status VARCHAR(50), notes TEXT)"
                )
                connection.exec_driver_sql(
                    "INSERT INTO source_references (id, source_name, resource_id, title, url, status) "
                    "VALUES (7, 'Legacy NASA source', 'NASA-OLD', 'Preserved row', 'https://example.test/source', 'Accessible')"
                )
            apply_additive_migrations(old_engine)
            with old_engine.connect() as connection:
                row = connection.exec_driver_sql(
                    "SELECT id, source_name, resource_id, title, url, status, retrieval_status, provenance_status "
                    "FROM source_references WHERE id=7"
                ).one()
                columns = {item["name"] for item in __import__("sqlalchemy").inspect(old_engine).get_columns("source_references")}
            self.assertEqual(row[:6], (7, "Legacy NASA source", "NASA-OLD", "Preserved row", "https://example.test/source", "Accessible"))
            self.assertEqual(row[6], "not_attempted")
            self.assertEqual(row[7], "unclassified")
            self.assertIn("access_limitations", columns)
        finally:
            old_engine.dispose()

    def test_experiment_context_does_not_infer_flight_from_microgravity_alone(self):
        self.assertEqual(_experiment_context({"projectType": "Microgravity Investigation"}), "unknown")
        self.assertEqual(_experiment_context({"projectType": "Microgravity Investigation", "experimentPlatform": "International Space Station (ISS)"}), "flight_experiment")
        self.assertEqual(_experiment_context({"projectType": "Numerical simulation of microgravity"}), "simulation")

    def test_register_upsert_preserves_legacy_source_fields_and_notes(self):
        source = SourceReference(
            source_name="NASA Physical Sciences Informatics (PSI)",
            resource_id="NASA-PSI-REPO",
            resource_type="Original type",
            title="Original title",
            url="https://psi.nasa.gov/physci/repo",
            last_verified="2026-11-14",
            status="Operational",
            notes="Legacy notes stay intact.",
        )
        self.db.add(source)
        self.db.commit()
        NasaDataIngestionService.ensure_source_register(self.db)
        self.db.commit()
        self.db.refresh(source)
        self.assertEqual(source.resource_type, "Original type")
        self.assertEqual(source.title, "Original title")
        self.assertEqual(source.last_verified, "2026-11-14")
        self.assertEqual(source.status, "Operational")
        self.assertEqual(source.notes, "Legacy notes stay intact.")
        self.assertEqual(source.retrieval_status, "not_attempted")

    def test_mission_evidence_uses_psi_and_ntrs_with_provenance_classes(self):
        service = NasaDataIngestionService(FakePsiIngestion(), FakeNtrsIngestion())

        async def ingest():
            await service.ingest_psi_investigations(self.db, "FLEX", limit=1)
            await service.ingest_ntrs(self.db, "combustion", limit=1)

        asyncio.run(ingest())
        params = MissionParameters.model_validate({
            "environment": "Lunar Habitat", "oxygen_percent": 34, "pressure_atm": 0.56,
            "airflow_cm_s": 15, "gravity": "lunar", "material": "pmma",
        })
        bundle = MissionEvidenceService().retrieve(self.db, params, "PMMA combustion")
        psi = next(record for record in bundle.records if record.evidence_id == "NASA-PSI:PSI-69")
        ntrs = next(citation for citation in bundle.citations if citation.citation_id == "NTRS:20260001234")
        self.assertEqual(psi.evidence_class, "verified_nasa_source")
        self.assertIn("measurement provenance not independently validated", psi.evidence_status)
        self.assertEqual(ntrs.evidence_class, "publication_metadata_only")
        self.assertNotIn("verified experimental", bundle.context.lower())
        self.assertIn("Microgravity results must not be inferred", bundle.context)
        self.assertEqual(bundle.research_gaps.combined_scenario_status, "not_documented")

    def test_psi_ntrs_failure_and_missing_data_are_controlled(self):
        def get_handler(url, **kwargs):
            return FakeResponse(status_code=503, payload={"error": "unavailable"})

        FakeHttpClient.get_handler = get_handler
        with patch("app.services.nasa_psi_service.httpx.AsyncClient", FakeHttpClient):
            async def search():
                await NasaPsiService().search_investigations("not-found", limit=1)

            with self.assertRaises(NasaPsiError):
                asyncio.run(search())

        async def empty_page(query, limit):
            return []

        ntrs = FakeNtrsIngestion()
        ntrs.search_citations = empty_page
        service = NasaDataIngestionService(FakePsiIngestion(), ntrs)
        result = asyncio.run(service.ingest_ntrs(self.db, "empty query", limit=1))
        self.assertEqual(result["records_retrieved"], 0)
        self.assertEqual(result["retrieval_status"], "retrieved_empty")

    def test_failed_ingestion_updates_source_register_without_claiming_success(self):
        class UnavailablePsi(FakePsiIngestion):
            async def search_investigations(self, query, limit, offset):
                self.last_http_status = 503
                raise NasaPsiError("PSI unavailable", 503)

        service = NasaDataIngestionService(UnavailablePsi(), FakeNtrsIngestion())
        with self.assertRaises(NasaPsiError):
            asyncio.run(service.ingest_psi_investigations(self.db, "FLEX", limit=1))
        source = self.db.query(SourceReference).filter_by(resource_id="NASA-PSI-REPO").one()
        self.assertEqual(source.retrieval_status, "failed")
        self.assertEqual(source.status, "Not yet retrieved")
        self.assertEqual(source.last_http_status, 503)
        self.assertEqual(self.db.query(RawSourceRecord).count(), 0)

    def test_ntrs_http_failure_is_recorded_without_fabricated_results(self):
        FakeHttpClient.post_handler = lambda url, **kwargs: FakeResponse(status_code=503, payload={"error": "unavailable"})
        FakeHttpClient.requested = []
        with patch("app.services.nasa_ntrs_service.httpx.AsyncClient", FakeHttpClient):
            async def search():
                service = NasaNtrsService()
                records = await service.search_citations("combustion", limit=2)
                return service, records

            service, records = asyncio.run(search())
        self.assertEqual(records, [])
        self.assertEqual(service.last_http_status, 503)
        self.assertEqual(service.last_error, "http_503")


if __name__ == "__main__":
    unittest.main()
