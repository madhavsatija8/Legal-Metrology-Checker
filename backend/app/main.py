import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import models
from .database import Base, engine, SessionLocal
from .routers import auth, products, reports, rule_versions, scans, users, violations
from .seed_products import get_seed_data

# For local/dev use (no Postgres, just `uvicorn app.main:app --reload`),
# create tables directly from the models so the API works immediately.
# Anywhere real data matters, use Alembic instead: `alembic upgrade head`
# (see backend/migrations/). Running both is safe — create_all no-ops on
# tables Alembic already created.
Base.metadata.create_all(bind=engine)


def _auto_seed_products() -> None:
    """Insert the curated Indian product catalogue on first run (no-ops if already populated)."""
    db = SessionLocal()
    try:
        count = db.query(models.Product).count()
        if count > 0:
            return  # Already seeded — don't duplicate
        for entry in get_seed_data():
            db.add(models.Product(
                name=entry["name"],
                brand=entry.get("brand"),
                category=entry.get("category"),
                manufacturer_name=entry.get("manufacturer_name"),
                is_imported=entry.get("is_imported", False),
                barcode=entry.get("barcode"),
            ))
        db.commit()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    _auto_seed_products()
    yield


app = FastAPI(
    lifespan=lifespan,
    title="Legal Metrology Compliance Checker API",
    description=(
        "API for scanning packaged commodity labels and checking compliance "
        "with the Legal Metrology (Packaged Commodities) Rules, 2011."
    ),
    version="0.1.0",
)

# The Step 6 frontend runs on a different origin (Vite dev server on
# :5173, or whatever static host serves the built app in production) and
# needs to call this API with a Bearer token from the browser. Restrict
# ALLOWED_ORIGINS via env var in real deployments instead of "*".
_allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(products.router)
app.include_router(scans.router)
app.include_router(reports.router)
app.include_router(violations.router)
app.include_router(rule_versions.router)

# Uploaded label images are stored on local disk (see routers/scans.py's
# STORAGE_DIR) — serve them so the frontend can render the actual photo
# next to its extracted fields, not just a filename. Swap this mount for
# a real object-storage URL scheme (S3/MinIO) when deploying for real.
_storage_dir = os.path.join(os.path.dirname(__file__), "storage")
os.makedirs(_storage_dir, exist_ok=True)
app.mount("/storage", StaticFiles(directory=_storage_dir), name="storage")


@app.get("/health", tags=["health"])
def health_check():
    return {"status": "ok"}
