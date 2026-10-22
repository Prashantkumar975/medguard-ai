"""Celery tasks: scan runs, rechecks, scheduled monitoring, usage metering."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from app.workers.celery_app import celery_app

log = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="medguard.run_scan",
    max_retries=2,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=60,
)
def run_scan_task(self, scan_id: str) -> dict:
    """Run a full investigation pipeline for a scan. Idempotent per scan id:
    the workflow marks scan status, and re-entry re-runs from the crawl step."""
    from app.core.database import SessionLocal
    from app.models import Scan

    db = SessionLocal()
    try:
        scan = db.get(Scan, scan_id)
        if scan is None:
            log.error("scan %s not found", scan_id)
            return {"error": "scan not found"}
        if scan.status == "cancelled":
            return {"status": "cancelled"}
        db.commit()
    finally:
        db.close()

    from app.agents.workflow import run_investigation

    result = run_investigation(scan_id)
    return {"status": "failed" if result.get("error") else "completed", **{k: v for k, v in result.items() if k in ("incidents_created",)}}


@celery_app.task(name="medguard.run_recheck")
def run_recheck_task(incident_id: str, reviewer_id: str) -> dict:
    """Recheck: re-crawl the incident's page, re-extract, re-verify.

    Creates a NEW investigation attempt; the original incident history is retained.
    """
    from app.core.database import SessionLocal
    from app.models import Incident, Scan, Snapshot, IncidentTrace, Site

    db = SessionLocal()
    try:
        inc = db.query(Incident).filter(Incident.id == incident_id).first()
        if inc is None:
            return {"error": "incident not found"}
        snap = db.get(Snapshot, inc.snapshot_id) if inc.snapshot_id else None
        site = db.get(Site, inc.site_id)
        if snap is None or site is None:
            inc.status = "resolved"
            db.add(IncidentTrace(incident_id=inc.id, step="Rescan", detail="Original snapshot unavailable; incident closed"))
            db.commit()
            return {"status": "resolved", "note": "no snapshot"}

        scan = Scan(
            organization_id=inc.organization_id,
            site_id=site.id,
            status="queued",
            trigger="recheck",
            max_pages=1,
        )
        db.add(scan)
        db.commit()
        db.refresh(scan)

        from app.services.crawler.crawler import crawl_site
        from app.services.extraction.claims import extract_claims
        from app.services.retrieval.search import hybrid_search
        from app.services.risk import engine as risk_engine
        from app.services.verification import verify as verify_mod
        from app.services.extraction.claims import ExtractedClaim

        scan.status = "running"
        db.commit()
        result = crawl_site(db, scan, site, max_pages=1, only_urls=[snap.url])
        page = next((p for p in result.pages if p.url == snap.url), None)

        if page is None:
            inc.status = "resolved"
            db.add(IncidentTrace(incident_id=inc.id, step="Rescan", detail="Page could not be rescanned; marked resolved with history retained"))
            scan.status = "failed"
            scan.error = "; ".join(result.errors)[:500]
            db.commit()
            return {"status": "failed"}

        claims, _failures = extract_claims(page.text, page.url)
        old = inc.claim
        still_conflicting = False
        for c in claims:
            if old and old.medication and c.medication and c.medication.lower() == old.medication.lower():
                outcome = verify_mod.verify(c, [], [])
                # retrieve evidence again
                hits = hybrid_search(db, inc.organization_id, c.claim_text, jurisdiction=site.jurisdiction)
                ev_texts = [h.text for h in hits]
                outcome = verify_mod.verify(c, ev_texts, [None] * len(ev_texts))
                if outcome.verdict == "POTENTIAL_CONTRADICTION":
                    still_conflicting = True
                break

        inc.attempt_no += 1
        if still_conflicting:
            inc.status = "open"
            db.add(IncidentTrace(incident_id=inc.id, step="Rescan", detail=f"Attempt {inc.attempt_no}: claim still conflicts after rescan; reopened"))
        else:
            inc.status = "resolved"
            db.add(IncidentTrace(incident_id=inc.id, step="Rescan", detail=f"Attempt {inc.attempt_no}: page rescanned; claim no longer conflicts with the evidence"))

        from app.models import Notification

        # A reopened incident is NOT a resolution — only notify when the rescan
        # actually cleared the conflict.
        if not still_conflicting:
            db.add(Notification(
                organization_id=inc.organization_id,
                kind="resolved",
                title=f"Finding resolved on {site.domain}",
                detail=inc.title,
                href=f"/incidents/{inc.public_id}",
            ))
        scan.status = "completed"
        db.commit()
        return {"status": inc.status, "attempt": inc.attempt_no}
    finally:
        db.close()


@celery_app.task(name="medguard.reap_stuck")
def reap_stuck_task() -> dict:
    """Reap stale pending work (Celery Beat every 10 min).

    A worker killed mid-task leaves rows pending forever — the orphaned broker
    delivery is not always redelivered — so this sweep:
    - fails scans stuck in queued/running past the stale threshold, and
    - returns incidents stuck in_review on a dead recheck to awaiting_correction.
      (in_review with a latest "Rescan: Recheck requested…" trace = recheck queued
      but never finished; a needs_info review has a "Human review" trace instead
      and is never touched.)
    """
    from app.core.config import settings
    from app.core.database import SessionLocal
    from app.models import Incident, IncidentTrace, Notification, Scan
    from sqlalchemy import select

    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(minutes=settings.reaper_stale_minutes)

        failed_scans = 0
        stale_scans = db.scalars(
            select(Scan)
            .where(Scan.status.in_(("queued", "running")), Scan.started_at < cutoff)
            .order_by(Scan.started_at)
        ).all()
        for scan in stale_scans:
            scan.status = "failed"
            scan.error = f"Reaped: no worker progress within {settings.reaper_stale_minutes} minutes"
            scan.finished_at = now
            db.add(
                Notification(
                    organization_id=scan.organization_id,
                    kind="scan_failed",
                    title="Scan timed out",
                    detail=f"The {scan.trigger} scan stalled and was marked failed",
                    href=None,
                )
            )
            failed_scans += 1

        reverted_rechecks = 0
        pending = db.scalars(select(Incident).where(Incident.status == "in_review")).all()
        for inc in pending:
            rescan_traces = [t for t in inc.trace if t.step == "Rescan"]
            if not rescan_traces:
                continue
            latest = rescan_traces[-1]  # relationship is ordered by at
            if not latest.detail.startswith("Recheck requested") or latest.at >= cutoff:
                continue
            inc.status = "awaiting_correction"
            db.add(
                IncidentTrace(
                    incident_id=inc.id,
                    step="Reaper",
                    detail=(
                        f"Recheck did not finish within {settings.reaper_stale_minutes} minutes; "
                        "returned to awaiting_correction — request it again"
                    ),
                )
            )
            db.add(
                Notification(
                    organization_id=inc.organization_id,
                    kind="scan_failed",
                    title="Recheck timed out",
                    detail=inc.title,
                    href=f"/incidents/{inc.public_id}",
                )
            )
            reverted_rechecks += 1

        db.commit()
        return {"failed_scans": failed_scans, "reverted_rechecks": reverted_rechecks}
    finally:
        db.close()


@celery_app.task(name="medguard.scheduled_scans")
def scheduled_scans_task() -> dict:
    """Enqueue scans for enabled sites whose interval has elapsed (Celery Beat)."""
    from app.core.database import SessionLocal
    from app.models import Site
    from sqlalchemy import select

    db = SessionLocal()
    try:
        sites = db.scalars(select(Site).where(Site.enabled.is_(True))).all()
        now = datetime.now(timezone.utc)
        enqueued = 0
        for site in sites:
            due = site.last_scan_at is None or site.last_scan_at + timedelta(hours=site.scan_interval_hours) <= now
            if not due:
                continue
            from app.models import Scan, new_id

            scan = Scan(
                id=new_id(),
                organization_id=site.organization_id,
                site_id=site.id,
                status="queued",
                trigger="scheduled",
                max_pages=25,
            )
            db.add(scan)
            db.commit()
            run_scan_task.delay(scan.id)
            enqueued += 1
        return {"enqueued": enqueued}
    finally:
        db.close()
