"""Persistence workflows for NASA PSI and NTRS source metadata.

Raw responses are retained as immutable, hash-addressed snapshots. Normalized
rows link back to those snapshots. Downloaded PSI files are kept as raw bytes;
this module deliberately does not promote their numerical rows into the legacy
combustion datapoint table.
"""

import csv
import hashlib
import io
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional

from sqlalchemy.orm import Session

from app.models.investigation import SourceReference
from app.models.nasa_data import ProcessedResearchRecord, RawSourceRecord
from app.services.nasa_ntrs_service import NasaNtrsService
from app.services.nasa_psi_service import NasaPsiError, NasaPsiService

logger = logging.getLogger("flame_intelligence.nasa_ingestion")


def _utcnow():
    # Keep the existing SQLite convention of naive UTC datetimes.
    return datetime.now(timezone.utc).replace(tzinfo=None)

PROVENANCE_SOURCE_LINK_VERIFIED = "nasa_origin_source_link_verified"
PROVENANCE_PUBLICATION_METADATA = "publication_metadata_only"
PROVENANCE_MEASUREMENT_UNVERIFIED = "measurement_provenance_unverified"


class NasaDataIngestionService:
    SOURCE_DEFINITIONS = (
        {
            "resource_id": "NASA-PSI-REPO",
            "source_name": "NASA Physical Sciences Informatics (PSI)",
            "resource_type": "Research investigation metadata and dataset repository",
            "title": "NASA Physical Sciences Informatics Repository",
            "url": "https://psi.nasa.gov/physci/repo",
            "data_type": "investigation_metadata,dataset_files",
            "provenance_status": PROVENANCE_SOURCE_LINK_VERIFIED,
            "access_limitations": (
                "PSI repository JSON endpoints are first-party web application endpoints, not a separately versioned API. "
                "Some files are restricted; large-file access may use separate request workflows. File downloads are explicit and capped."
            ),
        },
        {
            "resource_id": "NASA-PSI-S3",
            "source_name": "NASA PSI public S3 registry bucket",
            "resource_type": "Public object metadata and bounded file access",
            "title": "NASA PSI Public Data (Registry of Open Data on AWS)",
            "url": "https://registry.opendata.aws/nasa-psi/",
            "data_type": "public_object_listing,dataset_files",
            "provenance_status": PROVENANCE_SOURCE_LINK_VERIFIED,
            "access_limitations": "Only public objects are accessible. Listings are paginated; downloads require an explicit key and a configured byte cap.",
        },
        {
            "resource_id": "NASA-NTRS-API",
            "source_name": "NASA Technical Reports Server (NTRS)",
            "resource_type": "Scientific and technical publication metadata API",
            "title": "NASA Technical Reports Server Citation Search API",
            "url": "https://ntrs.nasa.gov/api/citations/search",
            "data_type": "publication_metadata",
            "provenance_status": PROVENANCE_PUBLICATION_METADATA,
            "access_limitations": "Citation metadata is not experimental measurement provenance. Full text is not downloaded by this workflow.",
        },
    )

    def __init__(self, psi_service=None, ntrs_service=None):
        self.psi = psi_service or NasaPsiService()
        self.ntrs = ntrs_service or NasaNtrsService()

    @classmethod
    def ensure_source_register(cls, db: Session) -> None:
        """Idempotently add/update NASA source register entries without deleting rows."""
        for definition in cls.SOURCE_DEFINITIONS:
            source = (
                db.query(SourceReference)
                .filter(SourceReference.resource_id == definition["resource_id"])
                .first()
            )
            if source is None:
                source = SourceReference(
                    source_name=definition["source_name"],
                    resource_id=definition["resource_id"],
                    resource_type=definition["resource_type"],
                    title=definition["title"],
                    url=definition["url"],
                    status="Not yet retrieved",
                    retrieval_status="not_attempted",
                    provenance_status=definition["provenance_status"],
                    data_type=definition["data_type"],
                    access_limitations=definition["access_limitations"],
                )
                db.add(source)
            else:
                # Preserve legacy source identity, verification date, status,
                # and notes. Only the Phase 3 fields are updated here.
                for field in ("data_type", "provenance_status", "access_limitations"):
                    setattr(source, field, definition[field])
        db.flush()

    async def ingest_psi_investigations(self, db: Session, query: str, limit: int = 20) -> Dict[str, Any]:
        if limit < 1 or limit > 100:
            raise ValueError("PSI ingestion limit must be between 1 and 100.")
        source = self._source(db, "NASA-PSI-REPO")
        started = _utcnow()
        stored = 0
        raw_inserted = 0
        offset = 0
        page_size = min(20, limit)
        failed_shards = 0
        try:
            while stored < limit:
                page = await self.psi.search_investigations(query=query, limit=min(page_size, limit - stored), offset=offset)
                failed_shards += page["failed_shards"]
                hits = page["records"]
                if not hits:
                    break
                for hit in hits:
                    accession = hit["accession"]
                    detail = await self.psi.get_investigation_metadata(accession)
                    if not detail:
                        continue
                    raw, inserted = self._save_raw(
                        db,
                        source,
                        record_kind="psi_investigation",
                        source_record_id=accession,
                        source_url=self.psi.investigation_page_url(accession),
                        payload_json=self._json(detail),
                        content_type="application/json",
                    )
                    raw_inserted += inserted
                    self._upsert_psi_investigation(db, source, raw, detail)
                    stored += 1
                    if stored >= limit:
                        break
                offset += len(hits)
                if len(hits) < page_size or offset >= page["total"]:
                    break

            retrieval_status = "partial" if failed_shards else ("retrieved" if stored else "retrieved_empty")
            self._mark_source(source, retrieval_status, self.psi.last_http_status, started)
            db.commit()
            return {
                "source": "NASA PSI",
                "query": query,
                "retrieval_status": retrieval_status,
                "records_retrieved": stored,
                "raw_snapshots_inserted": raw_inserted,
                "failed_shards": failed_shards,
                "last_http_status": source.last_http_status,
            }
        except Exception as exc:
            db.rollback()
            source = self._source(db, "NASA-PSI-REPO")
            self._mark_source(source, "failed", getattr(exc, "status_code", None) or self.psi.last_http_status, started)
            db.commit()
            raise

    async def ingest_psi_dataset(
        self,
        db: Session,
        accession: str,
        file_name: str,
        max_bytes: int = NasaPsiService.MAX_DATASET_BYTES,
    ) -> Dict[str, Any]:
        """Retrieve one specifically selected, public PSI dataset under the service cap."""
        source = self._source(db, "NASA-PSI-REPO")
        started = _utcnow()
        try:
            metadata = await self.psi.get_investigation_metadata(accession)
            if metadata is None:
                raise NasaPsiError(f"NASA PSI investigation {accession} was not found.", 404)
            file_reference = next(
                (item for item in self.psi.list_dataset_files(accession, metadata) if item["file_name"] == file_name),
                None,
            )
            if file_reference is None:
                raise ValueError(f"File {file_name!r} is not listed by NASA PSI for {accession}.")
            result = await self.psi.download_dataset_file(accession, file_reference, max_bytes=max_bytes)
        except Exception as exc:
            self._mark_failed(db, "NASA-PSI-REPO", self.psi.last_http_status, started, exc)
            raise
        raw, inserted = self._save_raw(
            db,
            source,
            record_kind="psi_dataset_file",
            source_record_id=f"{accession}/{file_name}/v{result['version']}",
            source_url=result["source_url"],
            payload_bytes=result["content"],
            content_type=result.get("content_type"),
        )
        headers = self._csv_headers(result["content"], file_name)
        normalized = {
            "accession": accession,
            "file_name": file_name,
            "file_version": result["version"],
            "file_size_bytes": result["size_bytes"],
            "sha256": result["sha256"],
            "csv_headers": headers,
            "measurement_values_parsed": False,
            "provenance_category": "nasa_origin_source_link_verified",
            "note": "Raw file bytes are stored. Numeric rows are not imported as verified measurements.",
        }
        self._upsert_processed(
            db,
            source,
            raw,
            record_kind="psi_dataset_file",
            source_record_id=raw.source_record_id,
            normalized=normalized,
            provenance=PROVENANCE_SOURCE_LINK_VERIFIED,
            title=file_name,
            experiment_type="dataset_file",
            context_type="unknown",
            units={"headers": headers, "measurement_units_not_normalized": True},
        )
        self._mark_source(source, "dataset_file_retrieved" if inserted else "dataset_file_retrieved_deduplicated", self.psi.last_http_status, _utcnow())
        db.commit()
        return {
            "source": "NASA PSI",
            "accession": accession,
            "file_name": file_name,
            "retrieval_status": "retrieved",
            "raw_snapshot_inserted": bool(inserted),
            "size_bytes": result["size_bytes"],
            "sha256": result["sha256"],
            "csv_headers": headers,
            "numeric_measurements_imported": 0,
        }

    async def ingest_ntrs(self, db: Session, query: str, limit: int = 20) -> Dict[str, Any]:
        if limit < 1 or limit > self.ntrs.MAX_RESULTS:
            raise ValueError(f"NTRS ingestion limit must be between 1 and {self.ntrs.MAX_RESULTS}.")
        source = self._source(db, "NASA-NTRS-API")
        started = _utcnow()
        citations = await self.ntrs.search_citations(query, limit=limit)
        raw_inserted = 0
        for citation in citations:
            citation_id = citation["ntrs_id"]
            raw, inserted = self._save_raw(
                db,
                source,
                record_kind="ntrs_publication",
                source_record_id=citation_id,
                source_url=citation["url"],
                payload_json=self._json(citation.get("raw_metadata") or citation),
                content_type="application/json",
            )
            raw_inserted += inserted
            normalized = {
                key: citation.get(key)
                for key in (
                    "ntrs_id", "title", "abstract", "authors", "year", "publication_date",
                    "doi", "publication", "url", "download_links",
                )
            }
            self._upsert_processed(
                db,
                source,
                raw,
                record_kind="ntrs_publication",
                source_record_id=citation_id,
                normalized=normalized,
                provenance=PROVENANCE_PUBLICATION_METADATA,
                title=citation.get("title"),
                description=citation.get("abstract"),
                investigators=[citation.get("authors")] if citation.get("authors") else [],
                publications=[normalized],
                experiment_type="publication",
                context_type="unknown",
            )
        status = (
            "partial" if self.ntrs.last_error and citations
            else "failed" if self.ntrs.last_error
            else "retrieved" if citations
            else "retrieved_empty"
        )
        self._mark_source(source, status, self.ntrs.last_http_status, started)
        db.commit()
        return {
            "source": "NASA NTRS",
            "query": query,
            "retrieval_status": status,
            "records_retrieved": len(citations),
            "raw_snapshots_inserted": raw_inserted,
            "pages_requested": self.ntrs.last_pages,
            "total_reported": self.ntrs.last_total,
            "last_http_status": self.ntrs.last_http_status,
            "error": self.ntrs.last_error,
        }

    async def ingest_psi_s3_listing(
        self,
        db: Session,
        prefix: str = "",
        limit: int = 100,
        continuation_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        source = self._source(db, "NASA-PSI-S3")
        started = _utcnow()
        try:
            page = await self.psi.list_public_s3_objects(
                prefix=prefix, limit=limit, continuation_token=continuation_token
            )
        except Exception as exc:
            self._mark_failed(db, "NASA-PSI-S3", self.psi.last_http_status, started, exc)
            raise
        inserted = 0
        for item in page["objects"]:
            key = item["key"]
            raw, was_inserted = self._save_raw(
                db,
                source,
                record_kind="psi_s3_object_metadata",
                source_record_id=key,
                source_url=item["url"],
                payload_json=self._json(item),
                content_type="application/xml",
            )
            inserted += was_inserted
            self._upsert_processed(
                db,
                source,
                raw,
                record_kind="psi_s3_object_metadata",
                source_record_id=key,
                normalized=item,
                provenance=PROVENANCE_SOURCE_LINK_VERIFIED,
                title=key.rsplit("/", 1)[-1],
                experiment_type="public_dataset_object_metadata",
                context_type="unknown",
            )
        self._mark_source(source, "listing_retrieved", self.psi.last_http_status, started)
        db.commit()
        return {
            "source": "NASA PSI public S3 registry bucket",
            "retrieval_status": "listing_retrieved",
            "objects_listed": len(page["objects"]),
            "raw_snapshots_inserted": inserted,
            "is_truncated": page["is_truncated"],
            "next_continuation_token_available": bool(page["next_continuation_token"]),
            "next_continuation_token": page["next_continuation_token"],
            "content_retrieved": False,
        }

    async def ingest_psi_s3_object(
        self, db: Session, key: str, max_bytes: int = NasaPsiService.MAX_DATASET_BYTES
    ) -> Dict[str, Any]:
        """Retrieve and persist one explicitly selected public S3 object."""
        source = self._source(db, "NASA-PSI-S3")
        started = _utcnow()
        try:
            result = await self.psi.download_public_s3_object(key, max_bytes=max_bytes)
        except Exception as exc:
            self._mark_failed(db, "NASA-PSI-S3", self.psi.last_http_status, started, exc)
            raise
        raw, inserted = self._save_raw(
            db,
            source,
            record_kind="psi_s3_dataset_file",
            source_record_id=key,
            source_url=result["source_url"],
            payload_bytes=result["content"],
            content_type=result.get("content_type"),
        )
        normalized = {
            "key": key,
            "size_bytes": result["size_bytes"],
            "sha256": result["sha256"],
            "measurement_values_parsed": False,
            "provenance_category": PROVENANCE_SOURCE_LINK_VERIFIED,
            "note": "The explicitly selected public S3 object is stored as raw bytes; no numerical rows are promoted.",
        }
        self._upsert_processed(
            db,
            source,
            raw,
            record_kind="psi_s3_dataset_file",
            source_record_id=key,
            normalized=normalized,
            provenance=PROVENANCE_SOURCE_LINK_VERIFIED,
            title=key.rsplit("/", 1)[-1],
            experiment_type="public_dataset_object",
            context_type="unknown",
            units={"measurement_values_parsed": False},
        )
        self._mark_source(source, "dataset_file_retrieved" if inserted else "dataset_file_retrieved_deduplicated", self.psi.last_http_status, _utcnow())
        db.commit()
        return {
            "source": "NASA PSI public S3 registry bucket",
            "key": key,
            "retrieval_status": "retrieved",
            "raw_snapshot_inserted": bool(inserted),
            "size_bytes": result["size_bytes"],
            "sha256": result["sha256"],
            "numeric_measurements_imported": 0,
        }

    def _source(self, db: Session, resource_id: str) -> SourceReference:
        self.ensure_source_register(db)
        source = db.query(SourceReference).filter(SourceReference.resource_id == resource_id).first()
        if source is None:
            raise RuntimeError(f"Source register entry is missing: {resource_id}")
        return source

    def _mark_failed(self, db: Session, resource_id: str, http_status, started, error: Exception) -> None:
        db.rollback()
        source = self._source(db, resource_id)
        self._mark_source(source, "failed", http_status, started)
        db.commit()

    @staticmethod
    def _mark_source(source, retrieval_status, http_status, started):
        source.retrieval_status = retrieval_status
        source.last_retrieved_at = _utcnow()
        source.last_http_status = http_status

    @staticmethod
    def _json(value):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)

    def _save_raw(
        self,
        db,
        source,
        record_kind,
        source_record_id,
        source_url,
        payload_json=None,
        payload_bytes=None,
        content_type=None,
    ):
        digest_input = payload_bytes if payload_bytes is not None else (payload_json or "").encode("utf-8")
        digest = hashlib.sha256(digest_input).hexdigest()
        existing = (
            db.query(RawSourceRecord)
            .filter_by(
                source_reference_id=source.id,
                record_kind=record_kind,
                source_record_id=source_record_id,
                payload_sha256=digest,
            )
            .first()
        )
        if existing:
            return existing, False
        raw = RawSourceRecord(
            source_reference_id=source.id,
            record_kind=record_kind,
            source_record_id=str(source_record_id),
            source_url=source_url,
            retrieved_at=_utcnow(),
            content_type=content_type,
            payload_json=payload_json,
            payload_bytes=payload_bytes,
            payload_sha256=digest,
            payload_size_bytes=len(digest_input),
        )
        db.add(raw)
        db.flush()
        return raw, True

    def _upsert_psi_investigation(self, db, source, raw, metadata):
        accession = str(metadata.get("accession"))
        publications = _as_list(metadata.get("publications") or metadata.get("publicationReferences"))
        contacts = (
            metadata.get("investigators") or metadata.get("contacts")
            or metadata.get("principalInvestigators") or metadata.get("researchers") or []
        )
        dataset_files = self.psi.list_dataset_files(accession, metadata)
        description = _first_text(
            metadata.get("description"), metadata.get("abstract"), metadata.get("objectives"),
            metadata.get("approach"), metadata.get("summary"),
        )
        material = _first_text(metadata.get("fuel"), metadata.get("materials"), metadata.get("fuelTypes"))
        conditions = _first_text(
            metadata.get("experimentalConditions"), metadata.get("testConditions"),
            metadata.get("environment"),
        )
        normalized = {
            "accession": accession,
            "acronym": metadata.get("acronym"),
            "title": metadata.get("title"),
            "description": description,
            "investigators": contacts,
            "publications": publications,
            "dataset_links": dataset_files,
            "project_type": metadata.get("projectType") or metadata.get("project_type"),
            "space_program": metadata.get("spaceProgram"),
            "flight_program": metadata.get("flightProgram"),
            "experiment_platform": metadata.get("experimentPlatform"),
            "materials": material,
            "experimental_conditions": conditions,
            "provenance_category": PROVENANCE_SOURCE_LINK_VERIFIED,
            "condition_values_normalized": False,
            "measurement_values_imported": False,
        }
        self._upsert_processed(
            db,
            source,
            raw,
            record_kind="psi_investigation",
            source_record_id=accession,
            normalized=normalized,
            provenance=PROVENANCE_SOURCE_LINK_VERIFIED,
            title=metadata.get("title"),
            description=description,
            investigators=contacts,
            publications=publications,
            dataset_links=dataset_files,
            experiment_type=metadata.get("projectType") or metadata.get("project_type"),
            context_type=_experiment_context(metadata),
            material=material,
            units={"source_values_preserved": True, "unit_conversion_performed": False},
        )

    def _upsert_processed(
        self,
        db,
        source,
        raw,
        record_kind,
        source_record_id,
        normalized,
        provenance,
        title=None,
        description=None,
        investigators=None,
        publications=None,
        dataset_links=None,
        experiment_type=None,
        context_type="unknown",
        material=None,
        units=None,
    ):
        processed = (
            db.query(ProcessedResearchRecord)
            .filter_by(
                source_reference_id=source.id,
                record_kind=record_kind,
                source_record_id=str(source_record_id),
            )
            .first()
        )
        payload = {
            "raw_record_id": raw.id,
            "source_version": normalized.get("version") or normalized.get("file_version"),
            "title": title or normalized.get("title"),
            "description": description,
            "investigators_json": self._json(investigators or []),
            "publication_references_json": self._json(publications or []),
            "dataset_links_json": self._json(dataset_links or []),
            "experiment_type": experiment_type,
            "experiment_context_type": context_type,
            "material_classification": material,
            "units_json": self._json(units or {}),
            "normalized_metadata_json": self._json(normalized),
            "provenance_category": provenance,
            "retrieved_at": _utcnow(),
        }
        if processed is None:
            db.add(ProcessedResearchRecord(
                source_reference_id=source.id,
                record_kind=record_kind,
                source_record_id=str(source_record_id),
                **payload,
            ))
        else:
            for field, value in payload.items():
                setattr(processed, field, value)
        db.flush()

    @staticmethod
    def _csv_headers(content: bytes, file_name: str):
        if not file_name.lower().endswith(".csv"):
            return []
        try:
            text = content[:64 * 1024].decode("utf-8-sig")
        except UnicodeDecodeError:
            text = content[:64 * 1024].decode("cp1252", errors="replace")
        try:
            return next(csv.reader(io.StringIO(text)))
        except (csv.Error, StopIteration):
            return []


def _as_list(value):
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _first_text(*values):
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, (dict, list)) and value:
            return json.dumps(value, ensure_ascii=False, default=str)
    return None


def _experiment_context(metadata):
    text = " ".join(str(metadata.get(key) or "") for key in (
        "projectType", "project_type", "flightProgram", "flightPlatform",
        "experimentPlatform", "title", "experimentType",
    )).lower()
    if "simulation" in text or "numerical model" in text:
        return "simulation"
    if any(term in text for term in (
        "international space station", "space shuttle", "spaceflight", "flight experiment", "flight platform",
    )) or re.search(r"\bISS\b", text, flags=re.IGNORECASE):
        return "flight_experiment"
    if "ground" in text or "1 g" in text or "earth gravity" in text:
        return "ground_experiment"
    return "unknown"
