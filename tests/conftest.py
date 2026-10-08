"""Test setup: isolated temp database + temp certificate folder for every test run."""
import os
import tempfile

_TMP = tempfile.mkdtemp(prefix="certtests_")
# Must be set BEFORE importing the app so config picks them up.
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP}/test.db"
os.environ["CERTIFICATE_DIR"] = f"{_TMP}/certs"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import database  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture()
def client():
    database.Base.metadata.drop_all(bind=database.engine)
    database.Base.metadata.create_all(bind=database.engine)
    # TestClient runs background tasks before returning, so jobs are finished
    # by the time we read the response.
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def valid_payload():
    return {
        "event_name": "Python Workshop",
        "event_date": "2026-10-08",
        "recipients": [
            {"name": "Kumudhavalli V", "email": "kumudha@example.com"},
            {"name": "Arun Kumar", "email": "arun@example.com"},
            {"name": "Priya S", "email": "priya@example.com"},
        ],
    }
