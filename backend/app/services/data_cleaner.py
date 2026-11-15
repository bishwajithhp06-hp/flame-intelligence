import re
from typing import Dict, Any, Optional

class DataCleaner:
    @staticmethod
    def clean_text(text: Optional[str]) -> str:
        if not text:
            return ""
        # Remove extra whitespaces and control characters
        cleaned = re.sub(r'\s+', ' ', text).strip()
        return cleaned

    @staticmethod
    def clean_doi(doi: Optional[str]) -> Optional[str]:
        if not doi:
            return None
        doi = doi.strip()
        # Remove URL prefixes if present
        doi = re.sub(r'^https?://(dx\.)?doi\.org/', '', doi, flags=re.IGNORECASE)
        return doi

    @staticmethod
    def normalize_investigation(record: Dict[str, Any]) -> Dict[str, Any]:
        """Normalizes external or scraped data into standard database structure"""
        return {
            "investigation_id": record.get("investigation_id") or f"NASA-{record.get('acronym', 'EXP')}",
            "title": DataCleaner.clean_text(record.get("title", "Untitled NASA Investigation")),
            "acronym": DataCleaner.clean_text(record.get("acronym", "")).upper(),
            "principal_investigator": DataCleaner.clean_text(record.get("principal_investigator", "")),
            "institution": DataCleaner.clean_text(record.get("institution", "")),
            "category": DataCleaner.clean_text(record.get("category", "Microgravity Combustion")),
            "facility": DataCleaner.clean_text(record.get("facility", "ISS CIR / MSG")),
            "flight_mission": DataCleaner.clean_text(record.get("flight_mission", "")),
            "status": DataCleaner.clean_text(record.get("status", "Archived")),
            "time_period": DataCleaner.clean_text(record.get("time_period", "")),
            "description": DataCleaner.clean_text(record.get("description", "")),
            "objectives": DataCleaner.clean_text(record.get("objectives", "")),
            "fuel_types": DataCleaner.clean_text(record.get("fuel_types", "")),
            "oxidizer_environment": DataCleaner.clean_text(record.get("oxidizer_environment", "")),
            "gravity_environment": DataCleaner.clean_text(record.get("gravity_environment", "Microgravity (~10^-6 g)")),
            "measured_parameters": DataCleaner.clean_text(record.get("measured_parameters", "")),
            "key_findings": DataCleaner.clean_text(record.get("key_findings", "")),
            "fire_safety_relevance": DataCleaner.clean_text(record.get("fire_safety_relevance", "")),
            "source_url": record.get("source_url"),
            "psi_repo_url": record.get("psi_repo_url"),
            "ntrs_id": record.get("ntrs_id")
        }
