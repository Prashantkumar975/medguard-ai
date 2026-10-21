"""Beat reaper (medguard.reap_stuck): stale pending rows are failed or reverted,
while fresh scans and human-driven in_review states are never touched.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.models import (
    Claim,
    Incident,
    IncidentTrace,
    Notification,
    Page,
    Scan,
    Site,
    Snapshot,
    new_id,
)

RECHECK_PENDING = "Recheck requested — page queued for rescan and re-verification"


def _incident(db, org, *, public_id: str, status: str, trace_step: str, trace_at, medication=None):
    """Minimal site→page→snapshot→claim→incident chain with one trace entry."""
    site = Site(id=new_id(), organization_id=org.id, domain=f"{public_id.lower()}.example")
    db.add(site)
    db.flush()
    page = Page(id=new_id(), site_id=site.id, url=f"https://{site.domain}/x")
    db.add(page)
    db.flush()
    snap = Snapshot(
        id=new_id(), page_id=page.id, site_id=site.id, url=page.url,
        http_status=200, content_hash="abc123", text_content="body",
    )
    db.add(snap)
    db.flush()
    claim = Claim(
        id=new_id(), organization_id=org.id, snapshot_id=snap.id, site_id=site.id,
        statement="Zorvaxin is safe in pregnancy.", offsets_start=0, offsets_end=28,
        extraction_model="test", extraction_confidence=0.9, medication=medication,
    )
    db.add(claim)
    db.flush()
    inc = Incident(
        public_id=public_id, organization_id=org.id, site_id=site.id,
        snapshot_id=snap.id, claim_id=claim.id, title=f"{public_id} finding",
        verdict="POTENTIAL_CONTRADICTION", priority="high", status=status,
        rationale="r", dedupe_key=f"reap-{public_id}",
    )
    db.add(inc)
    db.flush()
    db.add(IncidentTrace(incident_id=inc.id, step=trace_step, detail=RECHECK_PENDING, at=trace_at))
    db.commit()
    return inc


def test_reaper_fails_stale_scans_and_reverts_stuck_recheck(db, org, engine, monkeypatch):
    six_hours_ago = datetime.now(timezone.utc) - timedelta(hours=6)

    site = Site(id=new_id(), organization_id=org.id, domain="reap.example")
    db.add(site)
    db.flush()
    stale_scan = Scan(
        id=new_id(), organization_id=org.id, site_id=site.id,
        status="running", trigger="manual", max_pages=25, started_at=six_hours_ago,
    )
    fresh_scan = Scan(  # started_at defaults to now — must NOT be reaped
        id=new_id(), organization_id=org.id, site_id=site.id,
        status="queued", trigger="manual", max_pages=25,
    )
    db.add_all([stale_scan, fresh_scan])
    db.commit()

    # dead recheck: in_review with a stale "Recheck requested" rescan trace
    stuck = _incident(
        db, org, public_id="INC-9101", status="in_review",
        trace_step="Rescan", trace_at=six_hours_ago,
    )
    # human-driven in_review (needs_info): a "Human review" trace, never touched
    needs_info = _incident(
        db, org, public_id="INC-9102", status="in_review",
        trace_step="Human review", trace_at=six_hours_ago,
    )

    # the task builds its own SessionLocal — point it at the test database
    from sqlalchemy.orm import sessionmaker

    import app.core.database as db_module

    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    monkeypatch.setattr(db_module, "SessionLocal", TestingSession)

    from app.workers.tasks import reap_stuck_task

    result = reap_stuck_task()
    assert result == {"failed_scans": 1, "reverted_rechecks": 1}

    db.expire_all()
    s = db.get(Scan, stale_scan.id)
    assert s.status == "failed"
    assert s.finished_at is not None
    assert "Reaped" in s.error

    assert db.get(Scan, fresh_scan.id).status == "queued"

    st = db.get(Incident, stuck.id)
    assert st.status == "awaiting_correction"
    assert any(t.step == "Reaper" for t in st.trace)

    assert db.get(Incident, needs_info.id).status == "in_review"

    notifs = db.scalars(
        select(Notification).where(Notification.organization_id == org.id)
    ).all()
    assert len(notifs) == 2  # one per reaped row; none for the healthy rows
    assert {n.kind for n in notifs} == {"scan_failed"}


def test_reaper_is_quiet_when_nothing_is_stale(db, org, engine, monkeypatch):
    from sqlalchemy.orm import sessionmaker

    import app.core.database as db_module

    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    monkeypatch.setattr(db_module, "SessionLocal", TestingSession)

    site = Site(id=new_id(), organization_id=org.id, domain="calm.example")
    db.add(site)
    db.flush()
    db.add(
        Scan(id=new_id(), organization_id=org.id, site_id=site.id,
             status="running", trigger="manual", max_pages=25)
    )
    db.commit()

    from app.workers.tasks import reap_stuck_task

    assert reap_stuck_task() == {"failed_scans": 0, "reverted_rechecks": 0}
    assert db.scalars(select(Notification)).all() == []


# ---------------- recheck task: resolution notification gating ----------------
def _run_recheck(db, org, engine, monkeypatch, *, verdict):
    """Drive run_recheck_task to completion with crawl/search/verify stubbed,
    so both status branches of the notification gating are exercised."""
    import types

    from sqlalchemy.orm import sessionmaker

    import app.core.database as db_module
    import app.services.crawler.crawler as crawler_mod
    from app.services.extraction import claims as claims_mod
    import app.services.retrieval.search as search_mod
    from app.services.verification import verify as verify_mod

    inc = _incident(
        db, org, public_id="INC-9201", status="awaiting_correction",
        trace_step="Rescan", trace_at=datetime.now(timezone.utc) - timedelta(hours=6),
        medication="Zorvaxin",
    )

    page = types.SimpleNamespace(url=inc.snapshot.url, text="Zorvaxin is safe in pregnancy.")
    monkeypatch.setattr(crawler_mod, "crawl_site", lambda *a, **k: types.SimpleNamespace(pages=[page], errors=[]))
    monkeypatch.setattr(search_mod, "hybrid_search", lambda *a, **k: [])
    monkeypatch.setattr(
        claims_mod, "extract_claims",
        lambda *a, **k: ([types.SimpleNamespace(medication="Zorvaxin", claim_text=page.text)], []),
    )
    monkeypatch.setattr(verify_mod, "verify", lambda *a, **k: types.SimpleNamespace(verdict=verdict))

    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    monkeypatch.setattr(db_module, "SessionLocal", TestingSession)

    from app.workers.tasks import run_recheck_task

    run_recheck_task(inc.id, None)
    return inc


def test_recheck_reopen_does_not_notify_resolution(db, org, engine, monkeypatch):
    inc = _run_recheck(db, org, engine, monkeypatch, verdict="POTENTIAL_CONTRADICTION")
    db.expire_all()
    got = db.get(Incident, inc.id)
    assert got.status == "open"          # reopened, not resolved
    assert got.attempt_no == 2
    assert db.scalars(select(Notification)).all() == []  # no false "Finding resolved"


def test_recheck_resolution_notifies(db, org, engine, monkeypatch):
    inc = _run_recheck(db, org, engine, monkeypatch, verdict="SUPPORTED")
    db.expire_all()
    got = db.get(Incident, inc.id)
    assert got.status == "resolved"
    notifs = db.scalars(select(Notification)).all()
    assert len(notifs) == 1
    assert notifs[0].kind == "resolved"
