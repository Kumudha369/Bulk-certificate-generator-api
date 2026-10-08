"""HTTP endpoints."""
import io
import zipfile
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Certificate, CertificateStatus, GenerationJob
from app.schemas import CertificateOut, JobCreate, JobOut
from app.services import job_service

router = APIRouter(prefix="/api", tags=["certificates"])


def _job_out(job: GenerationJob) -> JobOut:
    out = JobOut.model_validate(job)
    out.status = job.status.value
    out.processing = max(job.total - job.completed - job.failed, 0)
    return out


def _cert_out(cert: Certificate, request: Request) -> CertificateOut:
    out = CertificateOut.model_validate(cert)
    out.status = cert.status.value
    if cert.status == CertificateStatus.COMPLETED:
        out.download_url = str(request.url_for("download_certificate", certificate_id=cert.id))
    return out


def _get_job_or_404(db: Session, job_id: str) -> GenerationJob:
    job = db.get(GenerationJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/jobs", response_model=JobOut, status_code=status.HTTP_202_ACCEPTED)
def create_job(payload: JobCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Submit a bulk generation job. Returns immediately (202); poll GET /jobs/{id}."""
    job = job_service.create_job(db, payload)
    if job.status.value == "PROCESSING":
        background_tasks.add_task(job_service.process_job, job.id)
    return _job_out(job)


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: str, db: Session = Depends(get_db)):
    """Job status and progress counters."""
    return _job_out(_get_job_or_404(db, job_id))


@router.get("/jobs/{job_id}/certificates", response_model=list[CertificateOut])
def list_certificates(
    job_id: str, request: Request, status_filter: str | None = None, db: Session = Depends(get_db)
):
    """List every certificate in a job. Optional ?status_filter=COMPLETED|FAILED|PENDING."""
    _get_job_or_404(db, job_id)
    query = db.query(Certificate).filter(Certificate.job_id == job_id)
    if status_filter:
        try:
            query = query.filter(Certificate.status == CertificateStatus(status_filter.upper()))
        except ValueError:
            raise HTTPException(status_code=422, detail="status_filter must be PENDING, COMPLETED or FAILED")
    certs = query.order_by(Certificate.created_at, Certificate.id).all()
    return [_cert_out(c, request) for c in certs]


@router.get("/jobs/{job_id}/download")
def download_job_zip(job_id: str, db: Session = Depends(get_db)):
    """Download all successfully generated certificates of a job as one ZIP."""
    _get_job_or_404(db, job_id)
    certs = (
        db.query(Certificate)
        .filter(Certificate.job_id == job_id, Certificate.status == CertificateStatus.COMPLETED)
        .all()
    )
    if not certs:
        raise HTTPException(status_code=404, detail="No completed certificates for this job yet")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for cert in certs:
            safe = "".join(ch if ch.isalnum() else "_" for ch in (cert.recipient_name or "certificate"))
            zf.write(cert.file_path, arcname=f"{safe}_{cert.id[:8]}.pdf")
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="job_{job_id}.zip"'},
    )


@router.get("/certificates/{certificate_id}", name="download_certificate")
def download_certificate(certificate_id: str, db: Session = Depends(get_db)):
    """Download one certificate PDF."""
    cert = db.get(Certificate, certificate_id)
    if cert is None:
        raise HTTPException(status_code=404, detail="Certificate not found")
    if cert.status != CertificateStatus.COMPLETED or not cert.file_path:
        raise HTTPException(
            status_code=409,
            detail=f"Certificate is {cert.status.value}" + (f": {cert.error_message}" if cert.error_message else ""),
        )
    path = Path(cert.file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Certificate file is missing on disk")
    return FileResponse(path, media_type="application/pdf", filename=f"certificate_{cert.id[:8]}.pdf")
