import json
import logging
import os
from sqlalchemy.orm import Session
from app.models.investigation import (
    Investigation,
    Publication,
    ResearchFinding,
    CombustionDataPoint,
    SourceReference
)
from app.services.data_cleaner import DataCleaner

logger = logging.getLogger("flame_intelligence.collector")

class DataCollector:
    """Manages local research metadata seeding and source registry records."""

    @staticmethod
    def seed_initial_verified_records(db: Session, force: bool = False):
        """Populate an empty database with the project's local seed records."""
        count = db.query(Investigation).count()
        if count > 0 and not force:
            logger.info(f"Database already populated with {count} investigations. Skipping seed.")
            return

        seed_file = os.path.join(os.path.dirname(__file__), "..", "seed_data", "verified_nasa_records.json")
        if not os.path.exists(seed_file):
            logger.error(f"Seed file not found at {seed_file}")
            return

        with open(seed_file, "r", encoding="utf-8") as f:
            records = json.load(f)

        logger.info(f"Seeding {len(records)} local research investigation records...")

        for item in records:
            # Check existing
            existing = db.query(Investigation).filter(Investigation.investigation_id == item["investigation_id"]).first()
            if existing:
                continue

            cleaned_inv = DataCleaner.normalize_investigation(item)
            inv = Investigation(**cleaned_inv)
            db.add(inv)
            db.flush() # get inv.id

            # Publications
            for pub in item.get("publications", []):
                p = Publication(
                    investigation_id=inv.id,
                    title=DataCleaner.clean_text(pub.get("title")),
                    authors=DataCleaner.clean_text(pub.get("authors")),
                    year=pub.get("year"),
                    journal_or_conference=DataCleaner.clean_text(pub.get("journal_or_conference")),
                    doi=DataCleaner.clean_doi(pub.get("doi")),
                    ntrs_id=pub.get("ntrs_id"),
                    abstract=pub.get("abstract"),
                    url=pub.get("url")
                )
                db.add(p)

            # Findings
            for finding in item.get("findings", []):
                f_obj = ResearchFinding(
                    investigation_id=inv.id,
                    finding_text=DataCleaner.clean_text(finding.get("finding_text")),
                    category=DataCleaner.clean_text(finding.get("category")),
                    spacecraft_fire_safety_implication=DataCleaner.clean_text(finding.get("spacecraft_fire_safety_implication")),
                    evidence_strength=finding.get("evidence_strength", "High (Flight Verified)"),
                    source_citation=DataCleaner.clean_text(finding.get("source_citation")),
                    doi=DataCleaner.clean_doi(finding.get("doi"))
                )
                db.add(f_obj)

            # Datapoints
            for dp in item.get("datapoints", []):
                dp_obj = CombustionDataPoint(
                    investigation_id=inv.id,
                    fuel_name=DataCleaner.clean_text(dp.get("fuel_name")),
                    fuel_state=dp.get("fuel_state"),
                    ambient_o2_percent=dp.get("ambient_o2_percent"),
                    pressure_atm=dp.get("pressure_atm"),
                    ambient_velocity_cm_s=dp.get("ambient_velocity_cm_s"),
                    burn_rate_or_flame_speed=dp.get("burn_rate_or_flame_speed"),
                    unit=dp.get("unit"),
                    phenomenon=DataCleaner.clean_text(dp.get("phenomenon")),
                    is_measured_flight_data=dp.get("is_measured_flight_data", False),
                    source_reference=DataCleaner.clean_text(dp.get("source_reference"))
                )
                db.add(dp_obj)

        # Seed Source References
        official_sources = [
            {
                "source_name": "NASA Physical Sciences Informatics (PSI)",
                "resource_id": "NASA-PSI-REPO",
                "resource_type": "Primary Flight Research Data Repository",
                "title": "NASA Physical Sciences Research Informatics System",
                "url": "https://psi.nasa.gov/physci/repo",
                "last_verified": "2026-11-14",
                "status": "Operational",
                "notes": "Houses raw & processed microgravity experiment telemetry, videos, and experiment summaries for Combustion Science."
            },
            {
                "source_name": "NASA Technical Reports Server (NTRS)",
                "resource_id": "NASA-NTRS-API",
                "resource_type": "Scientific & Technical Information (STI) Repository",
                "title": "NASA Technical Reports Server Publications & Citations",
                "url": "https://ntrs.nasa.gov/",
                "last_verified": "2026-11-14",
                "status": "Operational",
                "notes": "Direct access to peer-reviewed NASA conference papers, contractor reports, journal articles, and technical memorandums."
            },
            {
                "source_name": "ISS Combustion Integrated Rack (CIR)",
                "resource_id": "NASA-ISS-CIR",
                "resource_type": "Space Station Payload Facility",
                "title": "Combustion Integrated Rack (CIR) Flight Facility",
                "url": "https://www.nasa.gov/mission_pages/station/research/experiments/explorer/Facility.html?#id=317",
                "last_verified": "2026-11-14",
                "status": "Archived Flight Data",
                "notes": "Host facility in US Destiny Laboratory for FLEX, FLEX-2, and ACME investigations."
            },
            {
                "source_name": "NASA Microgravity Science Glovebox (MSG)",
                "resource_id": "NASA-ISS-MSG",
                "resource_type": "Space Station Glovebox Facility",
                "title": "Microgravity Science Glovebox (MSG) Flight Facility",
                "url": "https://www.nasa.gov/mission_pages/station/research/experiments/explorer/Facility.html?#id=340",
                "last_verified": "2026-11-14",
                "status": "Operational",
                "notes": "Host sealed glovebox facility for SPICE and BASS combustion experiments."
            }
        ]

        for s in official_sources:
            if not db.query(SourceReference).filter(SourceReference.resource_id == s["resource_id"]).first():
                db.add(SourceReference(**s))

        db.commit()
        logger.info("Database seeding successfully committed.")
