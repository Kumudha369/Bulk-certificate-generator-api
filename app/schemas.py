"""Pydantic schemas for request validation and responses."""
from datetime import date, datetime
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.config import MAX_RECIPIENTS_PER_JOB


class JobCreate(BaseModel):
    """Request body for POST /api/jobs.

    `recipients` is deliberately a list of free-form objects. Each recipient is
    validated individually in the service layer, so ONE bad row is recorded as a
    failed certificate instead of rejecting the whole bulk request.
    """

    event_name: str = Field(..., min_length=1, max_length=200, examples=["Python Workshop"])
    event_date: date = Field(default_factory=date.today, examples=["2026-10-08"])
    recipients: List[Any] = Field(..., min_length=1, max_length=MAX_RECIPIENTS_PER_JOB)

    @field_validator("event_name")
    @classmethod
    def _strip_event_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("event_name must not be blank")
        return v


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    event_name: str
    event_date: date
    status: str
    total: int
    completed: int
    failed: int
    processing: int = 0
    created_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class CertificateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    job_id: str
    recipient_name: Optional[str] = None
    recipient_email: Optional[str] = None
    status: str
    error_message: Optional[str] = None
    download_url: Optional[str] = None
