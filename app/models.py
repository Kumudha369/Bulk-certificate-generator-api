"""SQLAlchemy models: one GenerationJob has many Certificates."""
import enum
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Column, Date, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


class JobStatus(str, enum.Enum):
    PENDING = "PENDING"                          # accepted, not started
    PROCESSING = "PROCESSING"                    # certificates being generated
    COMPLETED = "COMPLETED"                      # every certificate succeeded
    COMPLETED_WITH_ERRORS = "COMPLETED_WITH_ERRORS"  # some succeeded, some failed
    FAILED = "FAILED"                            # nothing succeeded


class CertificateStatus(str, enum.Enum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class GenerationJob(Base):
    __tablename__ = "generation_jobs"

    id = Column(String(32), primary_key=True, default=_uuid)
    event_name = Column(String(200), nullable=False)
    event_date = Column(Date, nullable=False, default=date.today)
    status = Column(Enum(JobStatus), nullable=False, default=JobStatus.PENDING)
    total = Column(Integer, nullable=False, default=0)
    completed = Column(Integer, nullable=False, default=0)
    failed = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), default=_now)
    finished_at = Column(DateTime(timezone=True), nullable=True)

    certificates = relationship(
        "Certificate", back_populates="job", cascade="all, delete-orphan"
    )


class Certificate(Base):
    __tablename__ = "certificates"

    id = Column(String(32), primary_key=True, default=_uuid)
    job_id = Column(String(32), ForeignKey("generation_jobs.id"), nullable=False, index=True)
    recipient_name = Column(String(200), nullable=True)
    recipient_email = Column(String(320), nullable=True)
    status = Column(Enum(CertificateStatus), nullable=False, default=CertificateStatus.PENDING)
    file_path = Column(String(500), nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now)

    job = relationship("GenerationJob", back_populates="certificates")
