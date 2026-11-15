from sqlalchemy.orm import Session
from typing import List, Dict, Any
from app.models.investigation import (
    Investigation,
    Publication,
    ResearchFinding,
    CombustionDataPoint,
    SourceReference
)

class AnalyticsService:
    @staticmethod
    def get_overview_stats(db: Session) -> Dict[str, Any]:
        total_inv = db.query(Investigation).count()
        total_pubs = db.query(Publication).count()
        total_findings = db.query(ResearchFinding).count()
        total_dps = db.query(CombustionDataPoint).count()
        categories = db.query(Investigation.category).distinct().count()

        return {
            "total_investigations": total_inv,
            "total_publications": total_pubs,
            "total_findings": total_findings,
            "total_datapoints": total_dps,
            "categories_count": categories,
            "data_authenticity_notice": "Local datapoints are retained for exploration. Their legacy flight-data flags do not independently verify NASA provenance."
        }

    @staticmethod
    def get_category_distribution(db: Session) -> List[Dict[str, Any]]:
        categories = db.query(Investigation.category).all()
        counts: Dict[str, int] = {}
        for (cat,) in categories:
            counts[cat] = counts.get(cat, 0) + 1

        total = sum(counts.values()) or 1
        return [
            {
                "category": cat,
                "count": count,
                "percentage": round((count / total) * 100, 1)
            }
            for cat, count in counts.items()
        ]

    @staticmethod
    def get_mission_timeline(db: Session) -> List[Dict[str, Any]]:
        return [
            {
                "year_or_period": "2008 - 2011",
                "acronym": "SPICE",
                "title": "Smoke Point In Co-flow Experiment",
                "facility": "ISS Microgravity Science Glovebox (MSG)",
                "milestone": "First quantitative mapping of reduced smoke points in microgravity laminar gas diffusion flames."
            },
            {
                "year_or_period": "2009 - 2014",
                "acronym": "FLEX",
                "title": "Flame Extinguishment Experiment",
                "facility": "ISS Combustion Integrated Rack (CIR)",
                "milestone": "Historic discovery of sustained low-temperature quasi-steady 'cool flames' in droplet combustion."
            },
            {
                "year_or_period": "2012 - 2016",
                "acronym": "BASS",
                "title": "Burning and Suppression of Solids",
                "facility": "ISS Microgravity Science Glovebox (MSG)",
                "milestone": "Identification of critical low-velocity flow regime (1-5 cm/s) as the hardest condition for solid fire extinction."
            },
            {
                "year_or_period": "2016 - 2024",
                "acronym": "SAFFIRE",
                "title": "Spacecraft Fire Safety Demonstration (I-VI)",
                "facility": "Cygnus Spacecraft (Uncrewed Flight)",
                "milestone": "First large-scale (1m fabric) spacecraft fire tests validating NASA-STD-6001 exploration atmosphere flammability."
            },
            {
                "year_or_period": "2017 - 2022",
                "acronym": "ACME",
                "title": "Advanced Combustion via Microgravity Experiments",
                "facility": "ISS Combustion Integrated Rack (CIR)",
                "milestone": "Proof of concept for active electric-field flame deflection and non-chemical blowout in microgravity."
            }
        ]

    @staticmethod
    def get_experiment_comparison_matrix(db: Session) -> List[Dict[str, Any]]:
        invs = db.query(Investigation).all()
        matrix = []
        for inv in invs:
            doi = inv.publications[0].doi if inv.publications else None
            matrix.append({
                "acronym": inv.acronym,
                "title": inv.title,
                "facility": inv.facility or "ISS Module",
                "category": inv.category,
                "fuel_types": inv.fuel_types or "Documented in flight report",
                "oxidizer_conditions": inv.oxidizer_environment or "Standard Spacecraft Atmosphere",
                "gravity_level": inv.gravity_environment,
                "key_findings": inv.key_findings or "Detailed in publications",
                "safety_implication": inv.fire_safety_relevance or "Extinguishment protocol guidance",
                "primary_doi": doi,
                "psi_link": inv.psi_repo_url,
                "measured_parameters": inv.measured_parameters
            })
        return matrix

    @staticmethod
    def get_datapoints(db: Session, flight_only: bool = True) -> List[Dict[str, Any]]:
        # The legacy boolean is not provenance documentation, so it cannot
        # qualify a record as verified flight data.
        if flight_only:
            return []
        query = db.query(CombustionDataPoint)
        dps = query.all()
        return [
            {
                "id": dp.id,
                "investigation": dp.investigation.acronym if dp.investigation else "Local record",
                "fuel": dp.fuel_name,
                "state": dp.fuel_state,
                "o2_pct": dp.ambient_o2_percent,
                "pressure_atm": dp.pressure_atm,
                "flow_velocity": dp.ambient_velocity_cm_s,
                "burn_rate": dp.burn_rate_or_flame_speed,
                "unit": dp.unit,
                "phenomenon": dp.phenomenon,
                "legacy_measured_flag": dp.is_measured_flight_data,
                "evidence_status": "Local record — provenance unverified",
                "source": dp.source_reference
            }
            for dp in dps
        ]
