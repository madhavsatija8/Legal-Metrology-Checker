"""
Shared fixtures for the Step 8 API-level test suite (test_api_e2e_pipeline.py,
test_auth_rbac.py). These hit the real FastAPI app through TestClient/httpx —
unlike test_compliance_engine.py / test_ocr_pipeline.py / test_report_generation.py,
which call the pipeline functions directly and don't need a DB or HTTP layer at all.

Each test gets its own in-memory SQLite database (StaticPool keeps a single
connection alive so it survives TestClient's threadpool-executed requests),
created fresh from the ORM models and thrown away afterwards. That means
these tests can run in any order, in parallel, and without touching the
`legal_metrology.db` file a developer might have from running the app locally.
"""
import os

# Must be set before `app.auth` is imported anywhere, since it reads these at
# module load time. RULES_CONFIG_PATH mirrors what docker-compose.yml sets in
# the container so the compliance engine reads the real, versioned rule file
# rather than guessing a relative path.
os.environ.setdefault("JWT_SECRET_KEY", "test-only-secret-do-not-use-in-prod")
os.environ.setdefault(
    "RULES_CONFIG_PATH",
    os.path.join(os.path.dirname(__file__), "..", "..", "rules", "legal_metrology_rules.json"),
)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app import models  # noqa: E402
from app.auth import hash_password  # noqa: E402
from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402

SAMPLES_DIR = os.path.join(os.path.dirname(__file__), "sample_labels")


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def client(db_session):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def make_user(db_session):
    """Insert a user directly (bypassing /auth/register) so tests can set up
    fixtures for all three roles without depending on the registration
    endpoint's own behavior — that endpoint gets its own coverage in
    test_auth_rbac.py."""

    def _make(email: str, role: models.UserRole, password: str = "testpass123", full_name: str = "Test User"):
        user = models.User(
            email=email,
            full_name=full_name,
            hashed_password=hash_password(password),
            role=role,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user

    return _make


@pytest.fixture()
def login(client):
    """Returns Authorization headers for a given email/password, via the real
    POST /auth/login endpoint (so token creation is exercised, not stubbed)."""

    def _login(email: str, password: str = "testpass123") -> dict:
        resp = client.post("/auth/login", data={"username": email, "password": password})
        assert resp.status_code == 200, resp.text
        token = resp.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    return _login
