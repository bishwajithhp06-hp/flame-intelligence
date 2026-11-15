from sqlalchemy import Column, Integer, String, Text, DateTime, Float, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

class Investigation(Base):
    __tablename__ = "investigations"

    id = Column(Integer, primary_key=True, index=True)
    investigation_id = Column(String(100), unique=True, index=True, nullable=False)
    title = Column(String(255), nullable=False)
    acronym = Column(String(50), index=True, nullable=False)
    principal_investigator = Column(String(255), nullable=True)
    institution = Column(String(255), nullable=True)
    category = Column(String(100), index=True, nullable=False)
    facility = Column(String(150), nullable=True)
    flight_mission = Column(String(150), nullable=True)
    status = Column(String(50), default="Completed")
    time_period = Column(String(100), nullable=True)
    description = Column(Text, nullable=False)
    objectives = Column(Text, nullable=True)
    fuel_types = Column(String(255), nullable=True)
    oxidizer_environment = Column(String(255), nullable=True)
    gravity_environment = Column(String(100), default="Microgravity (~10^-6 g)")
    measured_parameters = Column(Text, nullable=True)
    key_findings = Column(Text, nullable=True)
    fire_safety_relevance = Column(Text, nullable=True)
    source_url = Column(String(500), nullable=True)
    psi_repo_url = Column(String(500), nullable=True)
    ntrs_id = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    publications = relationship("Publication", back_populates="investigation", cascade="all, delete-orphan")
    findings = relationship("ResearchFinding", back_populates="investigation", cascade="all, delete-orphan")
    datapoints = relationship("CombustionDataPoint", back_populates="investigation", cascade="all, delete-orphan")

class Publication(Base):
    __tablename__ = "publications"

    id = Column(Integer, primary_key=True, index=True)
    investigation_id = Column(Integer, ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(500), nullable=False)
    authors = Column(String(500), nullable=True)
    year = Column(Integer, nullable=True)
    journal_or_conference = Column(String(255), nullable=True)
    doi = Column(String(150), nullable=True)
    ntrs_id = Column(String(100), nullable=True)
    abstract = Column(Text, nullable=True)
    url = Column(String(500), nullable=True)

    investigation = relationship("Investigation", back_populates="publications")

class ResearchFinding(Base):
    __tablename__ = "research_findings"

    id = Column(Integer, primary_key=True, index=True)
    investigation_id = Column(Integer, ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False)
    finding_text = Column(Text, nullable=False)
    category = Column(String(100), nullable=True)
    spacecraft_fire_safety_implication = Column(Text, nullable=False)
    evidence_strength = Column(String(50), default="High (Flight Verified)")
    source_citation = Column(String(500), nullable=True)
    doi = Column(String(150), nullable=True)

    investigation = relationship("Investigation", back_populates="findings")

class CombustionDataPoint(Base):
    __tablename__ = "combustion_datapoints"

    id = Column(Integer, primary_key=True, index=True)
    investigation_id = Column(Integer, ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False)
    fuel_name = Column(String(100), nullable=False)
    fuel_state = Column(String(50), nullable=False) # "Droplet", "Solid Sheet", "Gas Jet"
    ambient_o2_percent = Column(Float, nullable=True)
    pressure_atm = Column(Float, nullable=True)
    ambient_velocity_cm_s = Column(Float, nullable=True)
    burn_rate_or_flame_speed = Column(Float, nullable=True)
    unit = Column(String(50), nullable=True)
    phenomenon = Column(String(255), nullable=True)
    is_measured_flight_data = Column(Boolean, default=False)
    source_reference = Column(String(255), nullable=True)

    investigation = relationship("Investigation", back_populates="datapoints")

class SourceReference(Base):
    __tablename__ = "source_references"

    id = Column(Integer, primary_key=True, index=True)
    source_name = Column(String(255), nullable=False)
    resource_id = Column(String(100), nullable=False)
    resource_type = Column(String(100), nullable=False)
    title = Column(String(500), nullable=False)
    url = Column(String(500), nullable=False)
    last_verified = Column(String(50), nullable=True)
    status = Column(String(50), default="Accessible")
    notes = Column(Text, nullable=True)
    # Additive Phase 3 source-register fields. ``last_verified`` remains for
    # compatibility with existing records and is not used as a retrieval time.
    retrieval_status = Column(String(50), nullable=False, default="not_attempted")
    last_retrieved_at = Column(DateTime, nullable=True)
    last_http_status = Column(Integer, nullable=True)
    data_type = Column(String(150), nullable=True)
    provenance_status = Column(String(100), nullable=False, default="unclassified")
    access_limitations = Column(Text, nullable=True)
