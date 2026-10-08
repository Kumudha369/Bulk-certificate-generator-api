# Bulk Certificate Generator API

A backend service that accepts a **list of recipients in one request**, validates them,
generates a PDF certificate for each from a **single predefined template**, tracks job
progress, and lets clients retrieve the results.

Built with **Python, FastAPI, SQLAlchemy (SQLite), Pydantic, ReportLab, Pytest**.

## Features
- Bulk submission: one `POST` creates one job for many recipients
- Per-recipient validation (name required, valid email, duplicate email detection)
- One bad recipient does **not** reject the whole job – it is recorded as `FAILED` with a reason
- PDF generation in a background task (API returns `202` immediately)
- Failure isolation: if one certificate fails to generate, the rest still complete
- Progress tracking: `total / completed / failed / processing` + job status
- Retrieve a single certificate PDF or the whole job as a ZIP
- Automated tests (16) and auto-generated Swagger docs

## Project structure
```
app/
  main.py                      FastAPI app + startup (creates tables)
  config.py                    Settings (env-overridable)
  database.py                  Engine / session
  models.py                    GenerationJob, Certificate tables
  schemas.py                   Request / response models
  routes/certificates.py       HTTP endpoints
  services/job_service.py      Validation, job creation, bulk processing
  services/certificate_generator.py   The one PDF template (ReportLab)
tests/                         Pytest suite
run.py                         Starts the dev server
```

## Setup
Requires Python 3.10+.

```bash
python -m venv venv
venv\Scripts\activate          # Windows   (Mac/Linux: source venv/bin/activate)
pip install -r requirements.txt
```

## Run
```bash
python run.py
```
Open **http://127.0.0.1:8000/docs** for the interactive Swagger UI.
The SQLite DB (`certificates.db`) and PDFs (`generated_certificates/`) are created automatically.

## Test
```bash
python -m pytest -v
```
Tests use a temporary database and folder, so they never touch real data.

## API
| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/jobs` | Submit a bulk generation job (returns `202`) |
| GET | `/api/jobs/{job_id}` | Job status and progress |
| GET | `/api/jobs/{job_id}/certificates` | List certificates (`?status_filter=COMPLETED\|FAILED\|PENDING`) |
| GET | `/api/jobs/{job_id}/download` | All completed certificates as a ZIP |
| GET | `/api/certificates/{certificate_id}` | Download one PDF |

### Submit a job
```bash
curl -X POST http://127.0.0.1:8000/api/jobs -H "Content-Type: application/json" -d '{
  "event_name": "Python Workshop",
  "event_date": "2026-10-08",
  "recipients": [
    {"name": "Kumudhavalli V", "email": "kumudha@example.com"},
    {"name": "Bad Email",      "email": "not-an-email"}
  ]
}'
```
Response (`202 Accepted`):
```json
{ "id": "c2d6a74a...", "event_name": "Python Workshop", "event_date": "2026-10-08",
  "status": "PROCESSING", "total": 2, "completed": 0, "failed": 1, "processing": 1 }
```

### Check progress
`GET /api/jobs/{id}` →
```json
{ "status": "COMPLETED_WITH_ERRORS", "total": 2, "completed": 1, "failed": 1, "processing": 0 }
```

### List certificates
```json
[
  { "id": "d836...", "recipient_name": "Kumudhavalli V", "status": "COMPLETED",
    "download_url": "http://127.0.0.1:8000/api/certificates/d836...", "error_message": null },
  { "id": "19c3...", "recipient_name": "Bad Email", "status": "FAILED",
    "error_message": "Invalid email: An email address must have an @-sign.", "download_url": null }
]
```

### Job statuses
`PENDING` → `PROCESSING` → `COMPLETED` (all ok) / `COMPLETED_WITH_ERRORS` (some failed) / `FAILED` (none succeeded)

### Error responses
`422` invalid request body (no recipients, missing event name) · `404` unknown job/certificate ·
`409` certificate exists but failed / not ready

## Design decisions
- **Async job model.** Generating PDFs can be slow, so `POST /jobs` stores the job and returns
  `202`; FastAPI `BackgroundTasks` does the work and the client polls the status endpoint.
- **Row-level validation.** `recipients` is accepted as a list; each entry is validated individually
  so a single typo does not block 999 valid certificates. Only structural problems (empty list,
  missing event name, > 1000 recipients) reject the entire request.
- **Failure isolation.** Each certificate is generated inside its own `try/except` and committed
  immediately, so progress is visible live and one crash never stops the batch.
- **Two tables** (`generation_jobs` 1—N `certificates`) make it easy to see exactly which
  recipients succeeded or failed, and why.
- **One template in code.** ReportLab draws the template, so no binary assets are needed; long
  names auto-shrink to fit.
- **UUID ids** avoid guessable sequential ids.
- Certificate files are stored as `generated_certificates/<job_id>/<certificate_id>.pdf`.

## Limitations & future scope
- `BackgroundTasks` runs in-process; for production use a queue (Celery / RQ + Redis) so jobs survive restarts and scale across workers.
- SQLite is used for easy setup; switch to PostgreSQL by changing `DATABASE_URL`.
- Add authentication, email delivery of certificates, CSV upload, and multiple templates.
