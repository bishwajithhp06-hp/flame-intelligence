from sqlalchemy.orm import Session
from sqlalchemy import or_, desc
from typing import List, Optional, Dict, Any
from app.models.investigation import (
    Investigation,
    Publication,
    ResearchFinding,
    CombustionDataPoint,
    SourceReference
)

class ResearchService:
    @staticmethod
    def list_investigations(
        db: Session,
        category: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 50,
        skip: int = 0
    ) -> List[Dict[str, Any]]:
        query = db.query(Investigation)
        if category:
            query = query.filter(Investigation.category.ilike(f"%{category}%"))
        if search:
            search_fmt = f"%{search}%"
            query = query.filter(
                or_(
                    Investigation.title.ilike(search_fmt),
                    Investigation.acronym.ilike(search_fmt),
                    Investigation.description.ilike(search_fmt),
                    Investigation.fuel_types.ilike(search_fmt),
                    Investigation.principal_investigator.ilike(search_fmt)
                )
            )

        items = query.offset(skip).limit(limit).all()
        result = []
        for inv in items:
            result.append({
                "id": inv.id,
                "investigation_id": inv.investigation_id,
                "title": inv.title,
                "acronym": inv.acronym,
                "principal_investigator": inv.principal_investigator,
                "category": inv.category,
                "facility": inv.facility,
                "status": inv.status,
                "time_period": inv.time_period,
                "fuel_types": inv.fuel_types,
                "source_url": inv.source_url,
                "publications_count": len(inv.publications),
                "findings_count": len(inv.findings),
                "datapoints_count": len(inv.datapoints)
            })
        return result

    @staticmethod
    def get_investigation_by_id(db: Session, investigation_id: int) -> Optional[Investigation]:
        return db.query(Investigation).filter(Investigation.id == investigation_id).first()

    @staticmethod
    def get_investigation_by_acronym(db: Session, acronym: str) -> Optional[Investigation]:
        return db.query(Investigation).filter(Investigation.acronym.ilike(acronym.strip())).first()

    @staticmethod
    def search_all(db: Session, q: str, limit: int = 20) -> Dict[str, Any]:
        """Unified scientific search across investigations, publications, and findings"""
        search_fmt = f"%{q}%"
        invs = db.query(Investigation).filter(
            or_(
                Investigation.title.ilike(search_fmt),
                Investigation.acronym.ilike(search_fmt),
                Investigation.description.ilike(search_fmt),
                Investigation.key_findings.ilike(search_fmt)
            )
        ).limit(limit).all()

        pubs = db.query(Publication).filter(
            or_(
                Publication.title.ilike(search_fmt),
                Publication.abstract.ilike(search_fmt),
                Publication.authors.ilike(search_fmt)
            )
        ).limit(limit).all()

        findings = db.query(ResearchFinding).filter(
            or_(
                ResearchFinding.finding_text.ilike(search_fmt),
                ResearchFinding.spacecraft_fire_safety_implication.ilike(search_fmt)
            )
        ).limit(limit).all()

        return {
            "query": q,
            "investigations": [
                {
                    "id": i.id,
                    "acronym": i.acronym,
                    "title": i.title,
                    "category": i.category,
                    "facility": i.facility
                } for i in invs
            ],
            "publications": [
                {
                    "id": p.id,
                    "title": p.title,
                    "authors": p.authors,
                    "year": p.year,
                    "doi": p.doi,
                    "url": p.url,
                    "investigation_id": p.investigation_id
                } for p in pubs
            ],
            "findings": [
                {
                    "id": f.id,
                    "finding_text": f.finding_text,
                    "implication": f.spacecraft_fire_safety_implication,
                    "evidence_strength": f.evidence_strength,
                    "doi": f.doi,
                    "investigation_id": f.investigation_id
                } for f in findings
            ]
        }

    @staticmethod
    def get_fire_safety_insights(db: Session) -> List[Dict[str, Any]]:
        """Extract research-supported fire safety insights ranked by evidence strength"""
        findings = db.query(ResearchFinding).all()
        results = []
        for f in findings:
            inv = f.investigation
            results.append({
                "id": f.id,
                "investigation_acronym": inv.acronym if inv else "NASA Research",
                "investigation_title": inv.title if inv else "",
                "facility": inv.facility if inv else "ISS Flight Module",
                "finding_text": f.finding_text,
                "category": f.category,
                "spacecraft_fire_safety_implication": f.spacecraft_fire_safety_implication,
                "evidence_strength": f.evidence_strength,
                "source_citation": f.source_citation,
                "doi": f.doi,
                "disclaimer": "Scientific research insight based on microgravity flight tests. Not a certified spacecraft design clearance."
            })
        # Rank by evidence strength: High first
        results.sort(key=lambda x: 0 if "High" in x["evidence_strength"] else 1)
        return results
