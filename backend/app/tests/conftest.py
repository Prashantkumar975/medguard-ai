"""Test fixtures: an isolated test database, a FastAPI client, and a seeded org/admin.

The suite runs against a real PostgreSQL database (medguard_test) with the vector
extension. Unit tests cover the deterministic services directly (SSRF guard, risk
engine, extraction schema, numeric conflicts); API tests cover auth, RBAC, tenant
isolation, CRUD and the incident lifecycle. Tests that need the live model are
marked and skipped when Ollama is unreachable — they are never silently mocked.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

os.environ.setdefault("ENVIRONMENT", "test")

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.core.config import settings  # noqa: E402

# The suite authenticates many times per minute; the per-email login limiter is a
# production guard (tested separately in test_login_rate_limit) and would otherwise
# throttle the test client. Disable it here only.
settings.login_rate_limit_enabled = False
from app.core.database import Base, get_db  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.models import Organization, User  # noqa: E402
import app.models.entities  # noqa: F401, E402


@pytest.fixture(scope="session")
def engine():
    eng = create_engine(settings.test_database_url, future=True)
    with eng.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.execute(text("CREATE SEQUENCE IF NOT EXISTS incident_number_seq START 1001"))
    Base.metadata.drop_all(eng)
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture(autouse=True)
def _clean_tables(engine):
    """Truncate all tables before every test so tests are hermetic."""
    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
    yield


@pytest.fixture()
def db(engine):
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    session = TestingSession()
    yield session
    session.rollback()
    session.close()


@pytest.fixture()
def org(db):
    org = Organization(name="Test Org", subscription_plan="trial")
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


@pytest.fixture()
def admin(db, org):
    user = User(
        organization_id=org.id,
        name="Test Admin",
        email="admin@test.local",
        password_hash=hash_password("Password123!"),
        role="admin",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture()
def client(db, engine):
    from fastapi.testclient import TestClient
    from app.main import app

    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

    def _override():
        session = TestingSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def auth_headers(client, admin):
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.local", "password": "Password123!"},
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
