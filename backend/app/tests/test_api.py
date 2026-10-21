"""API integration tests: auth, RBAC, tenant isolation, CRUD, incident lifecycle.

Runs against a real PostgreSQL test database through the FastAPI app.
"""
from __future__ import annotations

import pytest


# ---------------- auth ----------------
def test_login_wrong_password_401(client):
    resp = client.post("/api/v1/auth/login", json={"email": "admin@test.local", "password": "nope"})
    assert resp.status_code == 401


def test_me_requires_token(client):
    assert client.get("/api/v1/auth/me").status_code == 401


def test_me_returns_role(client, auth_headers):
    me = client.get("/api/v1/auth/me", headers=auth_headers)
    assert me.status_code == 200
    body = me.json()
    assert body["role"] == "admin"
    assert "password" not in body


def test_refresh_rotation_revokes_old(client, auth_headers):
    pair = client.post("/api/v1/auth/login", json={"email": "admin@test.local", "password": "Password123!"}).json()
    r1 = client.post("/api/v1/auth/refresh", json={"refresh_token": pair["refresh_token"]})
    assert r1.status_code == 200
    # reusing the old (rotated) refresh token must fail
    r2 = client.post("/api/v1/auth/refresh", json={"refresh_token": pair["refresh_token"]})
    assert r2.status_code == 401


# ---------------- RBAC ----------------
@pytest.fixture()
def viewer_headers(client, db, org):
    from app.core.security import hash_password
    from app.models import User

    u = User(organization_id=org.id, name="Viewer", email="viewer@test.local",
             password_hash=hash_password("Password123!"), role="viewer")
    db.add(u)
    db.commit()
    resp = client.post("/api/v1/auth/login", json={"email": "viewer@test.local", "password": "Password123!"})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_viewer_cannot_create_site(client, viewer_headers):
    resp = client.post("/api/v1/sites", headers=viewer_headers, json={"domain": "nope.example"})
    assert resp.status_code == 403


def test_viewer_can_read_sites(client, viewer_headers):
    assert client.get("/api/v1/sites", headers=viewer_headers).status_code == 200


def test_viewer_cannot_start_scan(client, viewer_headers):
    resp = client.post("/api/v1/scans", headers=viewer_headers, json={"site_id": "x"})
    assert resp.status_code == 403


def test_unauthenticated_reads_blocked(client):
    assert client.get("/api/v1/sites").status_code == 401
    assert client.get("/api/v1/incidents").status_code == 401


# ---------------- sites CRUD ----------------
def test_site_create_and_duplicate(client, auth_headers):
    r1 = client.post("/api/v1/sites", headers=auth_headers, json={"domain": "alpha.example"})
    assert r1.status_code == 201
    body = r1.json()
    assert body["domain"] == "alpha.example"
    assert body["enabled"] is True
    # duplicate rejected with the contract message
    r2 = client.post("/api/v1/sites", headers=auth_headers, json={"domain": "alpha.example"})
    assert r2.status_code == 409
    assert r2.json()["detail"] == "That domain is already registered"


def test_site_patch_toggle(client, auth_headers):
    site = client.post("/api/v1/sites", headers=auth_headers, json={"domain": "beta.example"}).json()
    resp = client.patch(f"/api/v1/sites/{site['id']}", headers=auth_headers, json={"enabled": False})
    assert resp.status_code == 200
    assert resp.json()["enabled"] is False


def test_site_not_found(client, auth_headers):
    resp = client.get("/api/v1/sites/does-not-exist", headers=auth_headers)
    assert resp.status_code == 404


# ---------------- tenant isolation ----------------
def test_second_org_cannot_see_first_org_sites(client, auth_headers, db, org):
    from app.core.security import hash_password
    from app.models import Organization, User

    other = Organization(name="Other Org")
    db.add(other)
    db.commit()
    db.refresh(other)
    db.add(User(organization_id=other.id, name="Other", email="other@test.local",
                password_hash=hash_password("Password123!"), role="admin"))
    db.commit()

    site = client.post("/api/v1/sites", headers=auth_headers, json={"domain": "isolation.example"}).json()
    login = client.post("/api/v1/auth/login", json={"email": "other@test.local", "password": "Password123!"})
    other_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    # other org cannot list or fetch this org's site
    listed = client.get("/api/v1/sites", headers=other_headers).json()
    assert all(s["id"] != site["id"] for s in listed)
    assert client.get(f"/api/v1/sites/{site['id']}", headers=other_headers).status_code == 404


# ---------------- analytics (contract endpoint) ----------------
def test_analytics_summary_contract(client, auth_headers, seeded_incident):
    """Regression: /analytics/summary must 200 with the full chart shape.

    This endpoint once 500'd on a glibc-only strftime flag; the test exercises
    every SQL aggregation branch against real rows.
    """
    resp = client.get("/api/v1/analytics/summary", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # all four KPI keys the dashboard resolves by name
    kpi_keys = [k["key"] for k in body["kpis"]]
    assert all(key in kpi_keys for key in ("open", "pages", "claims", "review"))
    # 14 days of scan activity with portable "Mon D" labels
    assert len(body["scan_activity"]) == 14
    for day in body["scan_activity"]:
        assert day["changed"] >= 0 and day["flagged"] >= 0
    # verdict distribution covers all five verdicts
    assert {v["verdict"] for v in body["by_verdict"]} == {
        "SUPPORTED", "POTENTIAL_CONTRADICTION", "POSSIBLY_OUTDATED",
        "INCOMPLETE_INFORMATION", "INSUFFICIENT_EVIDENCE",
    }
    assert set(body["by_priority"]) == {"critical", "high", "medium", "low"}
    # seeded incident is active + critical -> reflected in KPI and priority
    open_kpi = next(k for k in body["kpis"] if k["key"] == "open")
    assert open_kpi["value"] >= 1
    assert body["by_priority"]["critical"] >= 1


def test_analytics_summary_empty_org(client, db, org):
    """Empty state: a fresh org gets zeros, not a crash (brief section 14)."""
    from app.core.security import hash_password
    from app.models import User

    u = User(organization_id=org.id, name="Fresh", email="fresh@test.local",
             password_hash=hash_password("Password123!"), role="admin")
    db.add(u)
    db.commit()
    login = client.post("/api/v1/auth/login", json={"email": "fresh@test.local", "password": "Password123!"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    body = client.get("/api/v1/analytics/summary", headers=headers).json()
    open_kpi = next(k for k in body["kpis"] if k["key"] == "open")
    assert open_kpi["value"] == 0
    assert body["recent_runs"] == []


# ---------------- incident lifecycle ----------------
@pytest.fixture()
def seeded_incident(db, org, admin):
    """Create a minimal claim+snapshot+incident directly in the DB for lifecycle tests."""
    from app.models import Claim, Incident, Page, Site, Snapshot, new_id

    site = Site(id=new_id(), organization_id=org.id, domain="cycle.example")
    db.add(site)
    db.flush()
    page = Page(id=new_id(), site_id=site.id, url="https://cycle.example/x")
    db.add(page)
    db.flush()
    snap = Snapshot(id=new_id(), page_id=page.id, site_id=site.id, url="https://cycle.example/x",
                    http_status=200, content_hash="abc123", text_content="body")
    db.add(snap)
    db.flush()
    claim = Claim(id=new_id(), organization_id=org.id, snapshot_id=snap.id, site_id=site.id,
                  statement="Zorvaxin is safe in pregnancy.", offsets_start=0, offsets_end=28,
                  extraction_model="test", extraction_confidence=0.9)
    db.add(claim)
    db.flush()
    inc = Incident(public_id="INC-9001", number=9001, organization_id=org.id, site_id=site.id,
                   snapshot_id=snap.id, claim_id=claim.id, title="Test finding",
                   verdict="POTENTIAL_CONTRADICTION", priority="critical", status="open",
                   rationale="r", harm=0.9, exposure=0.5, evidence_strength=0.8, uncertainty=0.1,
                   dedupe_key="dedupe-test-1")
    db.add(inc)
    db.commit()
    db.refresh(inc)
    return inc


def test_review_requires_rationale(client, auth_headers, seeded_incident):
    resp = client.post(
        f"/api/v1/incidents/{seeded_incident.public_id}/review",
        headers=auth_headers, json={"decision": "confirm", "rationale": "too short"},
    )
    assert resp.status_code == 422
    assert "at least 10 characters" in resp.json()["detail"]


def test_review_confirm_transitions_to_awaiting_correction(client, auth_headers, seeded_incident):
    resp = client.post(
        f"/api/v1/incidents/{seeded_incident.public_id}/review",
        headers=auth_headers, json={"decision": "confirm", "rationale": "Confirmed against the label."},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "awaiting_correction"
    assert body["decision"]["decision"] == "confirm"


def test_recheck_blocked_unless_awaiting_correction(client, auth_headers, seeded_incident):
    resp = client.post(f"/api/v1/incidents/{seeded_incident.public_id}/recheck", headers=auth_headers)
    assert resp.status_code == 409
    assert "only available after a confirmed issue" in resp.json()["detail"]


def test_incident_list_filter_by_priority(client, auth_headers, seeded_incident):
    resp = client.get("/api/v1/incidents", headers=auth_headers, params={"priority": "critical"})
    assert resp.status_code == 200
    assert any(i["id"] == "INC-9001" for i in resp.json())


# ---------------- login rate limiter (feature proof) ----------------
def test_login_rate_limit_engages(client, monkeypatch):
    """With the limiter re-enabled, repeated bad logins for one email are throttled."""
    import redis as redis_lib
    from app.core.config import settings

    monkeypatch.setattr(settings, "login_rate_limit_enabled", True)
    # start from a clean counter for this email
    r = redis_lib.Redis.from_url(settings.redis_url, socket_timeout=1)
    for k in r.keys("login:rl:*:limited@test.local"):
        r.delete(k)

    codes = []
    for _ in range(settings.login_rate_limit_attempts + 2):
        resp = client.post(
            "/api/v1/auth/login",
            json={"email": "limited@test.local", "password": "wrong"},
        )
        codes.append(resp.status_code)
    # once the window budget is spent, the limiter returns 429 regardless of credentials
    assert 429 in codes


def test_login_rate_limit_keyed_on_body_email(client, monkeypatch):
    """The email lives in the JSON body: two emails from one IP get independent budgets."""
    import redis as redis_lib
    from app.core.config import settings

    monkeypatch.setattr(settings, "login_rate_limit_enabled", True)
    r = redis_lib.Redis.from_url(settings.redis_url, socket_timeout=1)
    for pat in ("login:rl:*:rl-a@test.local", "login:rl:*:rl-b@test.local"):
        for k in r.keys(pat):
            r.delete(k)

    # exhaust one email's budget…
    codes_a = [
        client.post("/api/v1/auth/login", json={"email": "rl-a@test.local", "password": "wrong"}).status_code
        for _ in range(settings.login_rate_limit_attempts + 1)
    ]
    assert 429 in codes_a
    # …and prove a DIFFERENT email from the same IP still has budget (per-email keying)
    resp_b = client.post("/api/v1/auth/login", json={"email": "rl-b@test.local", "password": "wrong"})
    assert resp_b.status_code == 401, resp_b.text


# ---------------- recheck enqueue race (regression) ----------------
def _confirm_for_recheck(client, auth_headers, seeded_incident):
    resp = client.post(
        f"/api/v1/incidents/{seeded_incident.public_id}/review",
        headers=auth_headers,
        json={"decision": "confirm", "rationale": "Confirmed against the label."},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "awaiting_correction"


def test_recheck_reverts_status_when_broker_unavailable(client, auth_headers, seeded_incident, monkeypatch):
    """Regression: status is committed BEFORE .delay(); a broker outage must revert
    the incident instead of stranding it in_review with no task behind it."""
    from app.workers.tasks import run_recheck_task

    _confirm_for_recheck(client, auth_headers, seeded_incident)

    def _boom(*_args, **_kwargs):
        raise ConnectionError("broker down")

    monkeypatch.setattr(run_recheck_task, "delay", _boom)
    resp = client.post(f"/api/v1/incidents/{seeded_incident.public_id}/recheck", headers=auth_headers)
    assert resp.status_code == 503
    assert "Could not queue the recheck" in resp.json()["detail"]

    got = client.get(f"/api/v1/incidents/{seeded_incident.public_id}", headers=auth_headers).json()
    assert got["status"] == "awaiting_correction"


def test_recheck_success_enqueues_with_status_committed(client, auth_headers, seeded_incident, monkeypatch):
    """Happy path: 200 with the pending state persisted and exactly one task enqueued."""
    from app.workers.tasks import run_recheck_task

    _confirm_for_recheck(client, auth_headers, seeded_incident)

    calls = []
    monkeypatch.setattr(run_recheck_task, "delay", lambda *a, **k: calls.append(a))
    resp = client.post(f"/api/v1/incidents/{seeded_incident.public_id}/recheck", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "in_review"
    assert len(calls) == 1
    assert calls[0][0] == seeded_incident.id


def test_incident_list_filters_and_ordering(client, auth_headers, seeded_incident, db, org):
    """Parity for the SQL-side rewrite: priority-first ordering, q across title/
    claim statement/public_id/domain, status incl. active/all, site by domain."""
    from app.models import Incident

    db.add(Incident(
        public_id="INC-9002", organization_id=org.id, site_id=seeded_incident.site_id,
        snapshot_id=seeded_incident.snapshot_id, claim_id=seeded_incident.claim_id,
        title="Low priority resolved", verdict="SUPPORTED", priority="low", status="resolved",
        rationale="r", dedupe_key="dedupe-test-2",
    ))
    db.commit()

    def _ids(**params):
        return [i["id"] for i in client.get("/api/v1/incidents", headers=auth_headers, params=params).json()]

    # default ordering: critical (INC-9001) before low (INC-9002)
    assert _ids() == ["INC-9001", "INC-9002"]
    # free-text search reaches the claim statement (case-insensitive substring)
    assert set(_ids(q="zorvaxin")) == {"INC-9001", "INC-9002"}
    assert _ids(q="no-such-term") == []
    # status filters, incl. the synthetic active/all values
    assert _ids(status="active") == ["INC-9001"]
    assert len(_ids(status="all")) == 2
    assert _ids(status="resolved") == ["INC-9002"]
    # site filter matches the domain exactly
    assert len(_ids(site="cycle.example")) == 2
    assert _ids(site="other.example") == []
