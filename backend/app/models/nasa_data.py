from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


class RawSourceRecord(Base):
    """Immutable source snapshots and bounded, explicitly retrieved files."""

    __tablename__ = "raw_source_records"
    __table_args__ = (
        UniqueConstraint(
            "source_reference_id",
            "record_kind",
            "source_record_id",
            "payload_sha256",
            name="uq_raw_source_snapshot",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    source_reference_id = Column(
        Integer, ForeignKey("source_references.id", ondelete="CASCADE"), nullable=False, index=True
    )
    record_kind = Column(String(80), nullable=False, index=True)
    source_record_id = Column(String(1000), nullable=False)
    source_url = Column(String(2000), nullable=False)
    retrieved_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    content_type = Column(String(255), nullable=True)
    payload_json = Column(Text, nullable=True)
    payload_bytes = Column(LargeBinary, nullable=True)
    payload_sha256 = Column(String(64), nullable=False, index=True)
    payload_size_bytes = Column(Integer, nullable=False, default=0)

    source_reference = relationship("SourceReference")


class ProcessedResearchRecord(Base):
    """Normalized source metadata, always linked to the raw snapshot it came from."""

    __tablename__ = "processed_research_records"
    __table_args__ = (
        UniqueConstraint(
            "source_reference_id",
            "record_kind",
            "source_record_id",
            name="uq_processed_source_record",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    source_reference_id = Column(
        Integer, ForeignKey("source_references.id", ondelete="CASCADE"), nullable=False, index=True
    )
    raw_record_id = Column(
        Integer, ForeignKey("raw_source_records.id", ondelete="RESTRICT"), nullable=False, unique=True
    )
    record_kind = Column(String(80), nullable=False, index=True)
    source_record_id = Column(String(1000), nullable=False)
    source_version = Column(String(100), nullable=True)
    title = Column(String(1000), nullable=True)
    description = Column(Text, nullable=True)
    investigators_json = Column(Text, nullable=True)
    publication_references_json = Column(Text, nullable=True)
    dataset_links_json = Column(Text, nullable=True)
    experiment_type = Column(String(150), nullable=True)
    experiment_context_type = Column(String(50), nullable=False, default="unknown")
    material_classification = Column(String(255), nullable=True)
    units_json = Column(Text, nullable=True)
    normalized_metadata_json = Column(Text, nullable=False)
    provenance_category = Column(String(80), nullable=False)
    retrieved_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    source_reference = relationship("SourceReference")
    raw_record = relationship("RawSourceRecord")
