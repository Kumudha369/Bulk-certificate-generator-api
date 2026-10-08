"""Business logic: validate recipients, create jobs, generate certificates."""
import logging
from datetime import datetime, timezone
from typing import Any, List, Optional, Tuple

from email_validator import EmailNotValidError, validate_email
from sqlalchemy.orm import Session

from app import database
from app.config import CERTIFICATE_DIR
from app.models import Certificate, CertificateStatus, GenerationJob, JobStatus
from app.schemas import JobCreate
from app.services import certificate_generator

logger = logging.getLogger(__name__)

MAX_NAME_LENGTH = 200


def validate_recipient(raw: Any, seen_emails: set) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Validate ONE recipient. Returns (name, email, error_message).

    error_message is None when the recipient is valid.
    """
    if not isinstance(raw, dict):
        return None, None, "Recipient must be an object with 'name' and 'email'"

    name = raw.get("name")
    email = raw.get("email")
    name = name.strip() if isinstance(name, str) else None
    email = email.strip() if isinstance(email, str) else None

    if not name:
        return name, email, "Name is required"
    if len(name) > MAX_NAME_LENGTH:
        return name[:50] + "...", email, f"Name must be at most {MAX_NAME_LENGTH} characters"
    if not email:
        return name, email, "Email is required"
    try:
        email = validate_email(email, check_deliverability=False).normalized
    except EmailNotValidError as exc:
        return name, email, f"Invalid email: {exc}"
    if email.lower() in seen_emails:
        return name, email, "Duplicate email in this job"

    seen_emails.add(email.lower())
    return name, email, None


def create_job(db: Session, payload: JobCreate) -> GenerationJob:
    """Validate recipients and store the job + one Certificate row per recipient.

    Invalid recipients are stored as FAILED immediately (with a reason);
    valid ones are PENDING and picked up by process_job().
    """
    job = GenerationJob(
        event_name=payload.event_name,
        event_date=payload.event_date,
        total=len(payload.recipients),
        status=JobStatus.PENDING,
    )
    db.add(job)
    db.flush()  # assigns job.id

    seen: set = set()
    failed = 0
    for raw in payload.recipients:
        name, email, error = validate_recipient(raw, seen)
        cert = Certificate(
            job_id=job.id,
            recipient_name=name,
            recipient_email=email,
            status=CertificateStatus.FAILED if error else CertificateStatus.PENDING,
            error_message=error,
        )
        failed += 1 if error else 0
        db.add(cert)

    job.failed = failed
    if failed == job.total:  # nothing to generate
        job.status = JobStatus.FAILED
        job.finished_at = datetime.now(timezone.utc)
    else:
        job.status = JobStatus.PROCESSING
    db.commit()
    db.refresh(job)
    return job


def process_job(job_id: str) -> None:
    """Generate PDFs for every PENDING certificate of a job.

    Runs as a background task with its OWN database session. Each certificate is
    wrapped in try/except, so one failure never stops the rest of the batch.
    Progress is committed after every certificate so clients can poll it.
    """
    db = database.SessionLocal()
    try:
        job = db.get(GenerationJob, job_id)
        if job is None:
            return

        pending: List[Certificate] = (
            db.query(Certificate)
            .filter(Certificate.job_id == job_id, Certificate.status == CertificateStatus.PENDING)
            .order_by(Certificate.created_at, Certificate.id)
            .all()
        )

        for cert in pending:
            try:
                path = CERTIFICATE_DIR / job_id / f"{cert.id}.pdf"
                certificate_generator.generate_certificate_pdf(
                    path, cert.recipient_name, job.event_name, job.event_date
                )
                cert.status = CertificateStatus.COMPLETED
                cert.file_path = str(path)
                job.completed += 1
            except Exception as exc:  # noqa: BLE001 - isolate each failure
                logger.exception("Certificate %s failed", cert.id)
                cert.status = CertificateStatus.FAILED
                cert.error_message = f"Generation error: {exc}"
                job.failed += 1
            db.commit()

        job.status = (
            JobStatus.COMPLETED if job.failed == 0
            else JobStatus.FAILED if job.completed == 0
            else JobStatus.COMPLETED_WITH_ERRORS
        )
        job.finished_at = datetime.now(timezone.utc)
        db.commit()
    except Exception:  # noqa: BLE001
        logger.exception("Job %s crashed", job_id)
        db.rollback()
        job = db.get(GenerationJob, job_id)
        if job:
            job.status = JobStatus.FAILED
            job.finished_at = datetime.now(timezone.utc)
            db.commit()
    finally:
        db.close()
