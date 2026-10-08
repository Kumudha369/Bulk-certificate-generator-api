from datetime import date

from app.services import certificate_generator


def _create(client, payload):
    resp = client.post("/api/jobs", json=payload)
    assert resp.status_code == 202, resp.text
    return resp.json()


# ---------- 1. Job creation ----------
def test_create_job_returns_job_with_counts(client, valid_payload):
    job = _create(client, valid_payload)
    assert job["id"]
    assert job["total"] == 3
    assert job["event_name"] == "Python Workshop"


def test_job_completes_and_all_certificates_generated(client, valid_payload):
    job = _create(client, valid_payload)
    status = client.get(f"/api/jobs/{job['id']}").json()
    assert status["status"] == "COMPLETED"
    assert (status["total"], status["completed"], status["failed"], status["processing"]) == (3, 3, 0, 0)
    assert status["finished_at"] is not None


# ---------- 2. Validation ----------
def test_empty_recipient_list_rejected(client):
    resp = client.post("/api/jobs", json={"event_name": "X", "recipients": []})
    assert resp.status_code == 422


def test_missing_or_blank_event_name_rejected(client):
    assert client.post("/api/jobs", json={"recipients": [{"name": "A", "email": "a@b.com"}]}).status_code == 422
    assert client.post("/api/jobs", json={"event_name": "  ", "recipients": [{"name": "A", "email": "a@b.com"}]}).status_code == 422


def test_invalid_recipients_are_recorded_as_failed_not_whole_job(client):
    payload = {
        "event_name": "Workshop",
        "recipients": [
            {"name": "Good Person", "email": "good@example.com"},
            {"name": "", "email": "noname@example.com"},
            {"name": "Bad Email", "email": "not-an-email"},
            {"name": "No Email"},
            "just a string",
            {"name": "Good Person Again", "email": "GOOD@example.com"},  # duplicate (case-insensitive)
        ],
    }
    job = _create(client, payload)
    status = client.get(f"/api/jobs/{job['id']}").json()
    assert status["status"] == "COMPLETED_WITH_ERRORS"
    assert (status["total"], status["completed"], status["failed"]) == (6, 1, 5)

    failed = client.get(f"/api/jobs/{job['id']}/certificates?status_filter=FAILED").json()
    assert len(failed) == 5
    messages = " | ".join(c["error_message"] for c in failed)
    assert "Name is required" in messages
    assert "Invalid email" in messages
    assert "Email is required" in messages
    assert "Duplicate email" in messages


def test_all_invalid_job_is_failed(client):
    job = _create(client, {"event_name": "W", "recipients": [{"name": "", "email": "x"}]})
    status = client.get(f"/api/jobs/{job['id']}").json()
    assert status["status"] == "FAILED"
    assert status["failed"] == 1 and status["completed"] == 0


# ---------- 3. Certificate generation ----------
def test_generator_creates_valid_pdf(tmp_path):
    out = certificate_generator.generate_certificate_pdf(
        tmp_path / "c.pdf", "Test Person", "Event", date(2026, 10, 8)
    )
    data = out.read_bytes()
    assert data.startswith(b"%PDF") and len(data) > 500


def test_generator_handles_very_long_name(tmp_path):
    out = certificate_generator.generate_certificate_pdf(
        tmp_path / "long.pdf", "A" * 150, "E" * 100, date(2026, 1, 1)
    )
    assert out.exists()


# ---------- 4. Progress / status ----------
def test_unknown_job_returns_404(client):
    assert client.get("/api/jobs/doesnotexist").status_code == 404
    assert client.get("/api/jobs/doesnotexist/certificates").status_code == 404


def test_job_progress_counters_add_up(client):
    recipients = [{"name": f"User {i}", "email": f"user{i}@example.com"} for i in range(25)]
    job = _create(client, {"event_name": "Bulk", "recipients": recipients})
    s = client.get(f"/api/jobs/{job['id']}").json()
    assert s["completed"] + s["failed"] + s["processing"] == s["total"] == 25
    assert s["completed"] == 25


# ---------- 5. One certificate failing must not stop the rest ----------
def test_single_generation_failure_is_isolated(client, valid_payload, monkeypatch):
    real = certificate_generator.generate_certificate_pdf

    def flaky(path, name, event, d):
        if name == "Arun Kumar":
            raise RuntimeError("simulated PDF failure")
        return real(path, name, event, d)

    monkeypatch.setattr(certificate_generator, "generate_certificate_pdf", flaky)

    job = _create(client, valid_payload)
    s = client.get(f"/api/jobs/{job['id']}").json()
    assert s["status"] == "COMPLETED_WITH_ERRORS"
    assert (s["completed"], s["failed"]) == (2, 1)

    failed = client.get(f"/api/jobs/{job['id']}/certificates?status_filter=FAILED").json()
    assert failed[0]["recipient_name"] == "Arun Kumar"
    assert "simulated PDF failure" in failed[0]["error_message"]
    assert failed[0]["download_url"] is None


# ---------- 6. Retrieval ----------
def test_list_and_download_certificate(client, valid_payload):
    job = _create(client, valid_payload)
    certs = client.get(f"/api/jobs/{job['id']}/certificates").json()
    assert len(certs) == 3 and all(c["status"] == "COMPLETED" for c in certs)

    resp = client.get(f"/api/certificates/{certs[0]['id']}")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content.startswith(b"%PDF")


def test_download_failed_certificate_returns_409(client):
    job = _create(client, {"event_name": "W", "recipients": [{"name": "Bad", "email": "bad"}, {"name": "Ok", "email": "ok@example.com"}]})
    failed = client.get(f"/api/jobs/{job['id']}/certificates?status_filter=FAILED").json()[0]
    assert client.get(f"/api/certificates/{failed['id']}").status_code == 409


def test_download_unknown_certificate_returns_404(client):
    assert client.get("/api/certificates/nope").status_code == 404


def test_download_job_as_zip(client, valid_payload):
    job = _create(client, valid_payload)
    resp = client.get(f"/api/jobs/{job['id']}/download")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/zip"
    import io, zipfile
    assert len(zipfile.ZipFile(io.BytesIO(resp.content)).namelist()) == 3


def test_invalid_status_filter_rejected(client, valid_payload):
    job = _create(client, valid_payload)
    assert client.get(f"/api/jobs/{job['id']}/certificates?status_filter=BOGUS").status_code == 422
