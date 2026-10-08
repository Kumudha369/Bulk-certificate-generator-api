"""Central configuration. Values can be overridden with environment variables."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'certificates.db'}")
CERTIFICATE_DIR = Path(os.getenv("CERTIFICATE_DIR", BASE_DIR / "generated_certificates"))
MAX_RECIPIENTS_PER_JOB = int(os.getenv("MAX_RECIPIENTS_PER_JOB", "1000"))
