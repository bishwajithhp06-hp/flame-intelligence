import json
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy.orm import Session

from app.models.investigation import SourceReference
from app.models.nasa_data import ProcessedResearchRecord
from app.schemas.experiments import (
    ExperimentCitation,
    ExperimentComparison,
    ExperimentRecord,
    ExperimentRecordDetail,
    RetrievedDatasetFile,
)


CONDITION_FIELDS = {
    "oxygen_percent": {"%", "percent", "percent oxygen"},
    "pressure_atm": {"atm", "atmosphere", "atmospheres"},
    "airflow_cm_s": {"cm/s", "cm s-1", "cm s^-1"},
}
CONDITION_LABELS = {
    "oxygen_percent": "Oxygen concentration",
    "pressure_atm": "Pressure",
    "airflow_cm_s": "Airflow",
}
CONDITION_CANONICAL_UNITS = {
    "oxygen_percent": "%",
    "pressure_atm": "atm",
    "airflow_cm_s": "cm/s",
}


class ExperimentExplorerService:
    """Read-only explorer over records actually persisted from PSI and NTRS."""

    conditions_notice = (
        "Filters and comparisons use structured values in stored NASA records only. "
        "Narrative text and publication abstracts are not converted into experimental conditions. "
        "A downloaded raw file is not treated as parsed measurement data."
    )

    def list_records(
        self,
        db: Session,
        *,
        search: Optional[str] = None,
        source: Optional[str] = None,
        material: Optional[str] = None,
        gravity: Optional[str] = None,
        environment: Optional[str] = None,
    ) -> Dict[str, Any]:
        rows = self._base_query(db)
        entries = [self._summary(row) for row in rows]
        available_filters = {
            "source": self._unique(item.source_name for item in entries),
            "material": self._unique(item.material for item in entries),
            "gravity": self._unique(item.gravity_environment for item in entries),
            "environment": self._unique(item.environment for item in entries),
        }

        query = (search or "").strip().casefold()
        if query:
            entries = [item for item in entries if self._matches_search(item, query)]
        if source:
            entries = [item for item in entries if source.casefold() in {
                item.source_name.casefold(), item.source_resource_id.casefold()
            }]
        if material:
            entries = [item for item in entries if self._same(item.material, material)]
        if gravity:
            entries = [item for item in entries if self._same(item.gravity_environment, gravity)]
        if environment:
            entries = [item for item in entries if self._same(item.environment, environment)]

        return {
            "records": entries,
            "available_filters": available_filters,
            "conditions_notice": self.conditions_notice,
        }

    def get_detail(self, db: Session, record_id: int) -> Optional[ExperimentRecordDetail]:
        row = db.query(ProcessedResearchRecord).filter(
            ProcessedResearchRecord.id == record_id,
            ProcessedResearchRecord.record_kind.in_(["psi_investigation", "ntrs_publication"]),
        ).first()
        if row is None:
            return None

        summary = self._summary(row)
        source = row.source_reference
        metadata = self._json_dict(row.normalized_metadata_json)
        dataset_files = self._dataset_files(db, row, metadata)
        return ExperimentRecordDetail(
            **summary.model_dump(),
            dataset_files=dataset_files,
            retrieval_status=source.retrieval_status if source else "unknown",
            retrieval_http_status=source.last_http_status if source else None,
            source_last_retrieved_at=(
                source.last_retrieved_at.isoformat() if source and source.last_retrieved_at else None
            ),
        )

    def compare(self, db: Session, left_id: int, right_id: int) -> Optional[ExperimentComparison]:
        left = self.get_detail(db, left_id)
        right = self.get_detail(db, right_id)
        if left is None or right is None or left_id == right_id:
            return None

        categories = []
        for key, label in (
            ("experiment_type", "Experiment type"),
            ("experiment_context_type", "Experiment context"),
            ("material", "Material classification"),
            ("gravity_environment", "Gravity environment"),
            ("environment", "Environment"),
        ):
            first = getattr(left, key)
            second = getattr(right, key)
            if first is not None and second is not None:
                categories.append({
                    "field": label,
                    "left_value": first,
                    "right_value": second,
                    "relationship": "same" if self._same(first, second) else "different",
                })

        quantitative = self._quantitative_comparisons(left, right)
        limitations = []
        if not categories:
            limitations.append("No shared structured categorical experiment fields are available for comparison.")
        if not quantitative:
            limitations.append(
                "No shared structured numeric conditions with compatible, source-recorded units are available."
            )
        limitations.append(
            "This comparison does not establish scientific equivalence or show that the combined conditions were tested."
        )
        return ExperimentComparison(
            left=left,
            right=right,
            categorical_comparisons=categories,
            quantitative_comparisons=quantitative,
            limitations=limitations,
        )

    def _base_query(self, db: Session) -> List[ProcessedResearchRecord]:
        return (
            db.query(ProcessedResearchRecord)
            .filter(ProcessedResearchRecord.record_kind.in_(["psi_investigation", "ntrs_publication"]))
            .order_by(ProcessedResearchRecord.id.asc())
            .all()
        )

    def _summary(self, row: ProcessedResearchRecord) -> ExperimentRecord:
        metadata = self._json_dict(row.normalized_metadata_json)
        source = row.source_reference
        raw = row.raw_record
        source_name = source.source_name if source else "NASA source"
        resource_id = source.resource_id if source else "unknown"
        source_url = (raw.source_url if raw else None) or metadata.get("url")

        citations = []
        if row.record_kind == "ntrs_publication":
            citations.append(ExperimentCitation(
                title=str(metadata.get("title") or row.title or row.source_record_id),
                url=metadata.get("url") or source_url,
                doi=metadata.get("doi") or None,
                identifier=str(metadata.get("ntrs_id") or row.source_record_id),
                authors=metadata.get("authors"),
                year=metadata.get("year") if isinstance(metadata.get("year"), int) else None,
                evidence_type="NASA NTRS publication metadata",
            ))
            status = "NASA NTRS publication metadata; this record alone does not verify experimental measurements."
        else:
            citations.append(ExperimentCitation(
                title=str(row.title or row.source_record_id),
                url=source_url,
                evidence_type="NASA PSI source metadata",
            ))
            status = (
                "NASA PSI source record retrieved; source linkage is recorded, but experimental condition and "
                "measurement provenance are not independently validated here."
            )

        for publication in self._json_list(row.publication_references_json):
            title = publication.get("title") if isinstance(publication, dict) else None
            if not title:
                continue
            doi = publication.get("doi") or None
            citations.append(ExperimentCitation(
                title=str(title),
                url=f"https://doi.org/{doi}" if doi else None,
                doi=doi,
                authors=publication.get("authorList") if isinstance(publication, dict) else None,
                evidence_type="NASA PSI source metadata",
            ))

        material = self._explicit_text(row.material_classification) or self._explicit_text(metadata.get("material"))
        gravity = self._explicit_text(metadata.get("gravity_environment")) or self._explicit_text(metadata.get("gravity"))
        environment = self._explicit_text(metadata.get("environment"))
        condition_values = self._condition_values(metadata)
        missing = []
        for key, label, value in (
            ("material", "material", material),
            ("gravity_environment", "gravity environment", gravity),
            ("environment", "mission environment", environment),
        ):
            if not value:
                missing.append(label)
        for key, label in (
            ("oxygen_percent", "oxygen concentration"),
            ("pressure_atm", "pressure"),
            ("airflow_cm_s", "airflow"),
        ):
            if key not in condition_values:
                missing.append(label)

        return ExperimentRecord(
            record_id=row.id,
            source_record_id=row.source_record_id,
            record_kind=row.record_kind,
            title=row.title or metadata.get("title") or row.source_record_id,
            description=row.description or metadata.get("abstract"),
            source_name=source_name,
            source_resource_id=resource_id,
            source_url=source_url,
            retrieved_at=row.retrieved_at.isoformat() if row.retrieved_at else None,
            provenance_category=row.provenance_category,
            evidence_status=status,
            experiment_type=row.experiment_type,
            experiment_context_type=(
                row.experiment_context_type
                if row.experiment_context_type and row.experiment_context_type.casefold() != "unknown"
                else None
            ),
            material=material,
            gravity_environment=gravity,
            environment=environment,
            condition_values=condition_values,
            missing_data=missing,
            citations=citations,
        )

    def _dataset_files(self, db, row, metadata) -> List[RetrievedDatasetFile]:
        files = {}
        for link in metadata.get("dataset_links") or []:
            if not isinstance(link, dict):
                continue
            name = str(link.get("file_name") or link.get("remote_path") or "NASA PSI dataset file")
            files[name] = RetrievedDatasetFile(
                file_name=name,
                source_url=link.get("source_url") or link.get("download_endpoint"),
                retrieval_status="metadata_only",
                raw_size_bytes=None,
                measurements_parsed=False,
                note="A source link is listed in PSI metadata; no local downloaded payload is linked to this file entry.",
            )

        prefix = f"{row.source_record_id}/"
        child_rows = (
            db.query(ProcessedResearchRecord)
            .filter(
                ProcessedResearchRecord.source_reference_id == row.source_reference_id,
                ProcessedResearchRecord.record_kind == "psi_dataset_file",
                ProcessedResearchRecord.source_record_id.like(f"{prefix}%"),
            )
            .all()
        )
        for child in child_rows:
            child_metadata = self._json_dict(child.normalized_metadata_json)
            child_raw = child.raw_record
            name = str(child_metadata.get("file_name") or child.source_record_id)
            has_payload = bool(child_raw and child_raw.payload_size_bytes > 0)
            parsed = bool(
                child_metadata.get("measurement_values_parsed")
                or child_metadata.get("measurement_values_imported")
            )
            files[name] = RetrievedDatasetFile(
                file_name=name,
                source_url=(child_raw.source_url if child_raw else None),
                retrieval_status="retrieved" if has_payload else "metadata_only",
                raw_size_bytes=child_raw.payload_size_bytes if has_payload else None,
                measurements_parsed=parsed,
                note=(
                    "Raw source file is stored; measurement values have not been parsed into normalized records."
                    if has_payload and not parsed
                    else "Stored measurement parsing status comes from the normalized source metadata."
                ),
            )
        return list(files.values())

    @classmethod
    def _condition_values(cls, metadata: Dict[str, Any]) -> Dict[str, Any]:
        source_conditions = metadata.get("experimental_conditions")
        if not isinstance(source_conditions, dict):
            source_conditions = metadata.get("condition_values")
        if not isinstance(source_conditions, dict):
            return {}
        result = {}
        for field, accepted_units in CONDITION_FIELDS.items():
            condition = source_conditions.get(field)
            if not isinstance(condition, dict) or "value" not in condition:
                continue
            value = condition.get("value")
            unit = str(condition.get("unit") or "").strip().casefold()
            if isinstance(value, (int, float)) and unit in accepted_units:
                result[field] = {"value": value, "unit": CONDITION_CANONICAL_UNITS[field]}
        return result

    @classmethod
    def _quantitative_comparisons(cls, left, right):
        result = []
        for field in CONDITION_FIELDS:
            first = left.condition_values.get(field)
            second = right.condition_values.get(field)
            if not isinstance(first, dict) or not isinstance(second, dict):
                continue
            if first.get("unit") != second.get("unit"):
                continue
            result.append({
                "field": CONDITION_LABELS[field],
                "left_value": first["value"],
                "right_value": second["value"],
                "unit": first["unit"],
                "relationship": "same" if first["value"] == second["value"] else "different",
            })
        return result

    @staticmethod
    def _json_dict(value):
        try:
            parsed = json.loads(value or "{}")
        except (TypeError, json.JSONDecodeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}

    @staticmethod
    def _json_list(value):
        try:
            parsed = json.loads(value or "[]")
        except (TypeError, json.JSONDecodeError):
            return []
        return parsed if isinstance(parsed, list) else []

    @staticmethod
    def _explicit_text(value):
        return value.strip() if isinstance(value, str) and value.strip() else None

    @staticmethod
    def _unique(values: Iterable[Optional[str]]) -> List[str]:
        return sorted({item.strip() for item in values if isinstance(item, str) and item.strip()})

    @staticmethod
    def _same(left, right):
        return bool(left is not None and right is not None and str(left).casefold() == str(right).casefold())

    @staticmethod
    def _matches_search(record, query):
        return any(
            query in value.casefold()
            for value in (
                record.title,
                record.description or "",
                record.source_record_id,
                record.source_name,
                record.source_url or "",
                *(citation.title for citation in record.citations),
                *(citation.identifier or "" for citation in record.citations),
            )
        )
