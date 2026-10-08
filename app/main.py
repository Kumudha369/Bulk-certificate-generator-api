"""FastAPI application entry point."""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import database, models  # noqa: F401  (models must be imported to register tables)
from app.config import CERTIFICATE_DIR
from app.routes import certificates


@asynccontextmanager
async def lifespan(_: FastAPI):
    CERTIFICATE_DIR.mkdir(parents=True, exist_ok=True)
    database.Base.metadata.create_all(bind=database.engine)
    yield


app = FastAPI(
    title="Bulk Certificate Generator API",
    description="Submit a list of recipients, get PDF certificates generated in bulk.",
    version="1.0.0",
    lifespan=lifespan,
)
app.include_router(certificates.router)


@app.get("/", tags=["health"])
def health():
    return {"status": "ok", "docs": "/docs"}
