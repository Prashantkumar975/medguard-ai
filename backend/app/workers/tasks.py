"""Celery tasks: scan runs, rechecks, scheduled monitoring, usage metering."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from app.workers.celery_app import celery_app

log = logging.getLogger(__name__)


def _same_claim(old_claim, new_claim) -> bool:
    """Require matching drug context and meaningful text overlap before recheck."""
    import re

    if old_claim is None:
        return False
    if old_claim.medication and (new_claim.medication or "").casefold() != old_claim.medication.casefold():
        return False
    if old_claim.category and new_claim.category and old_claim.category != new_claim.category:
        return False
    old_terms = set(re.findall(r"[a-z0-9]+", old_claim.statement.casefold()))
    new_terms = set(re.findall(r"[a-z0-9]+", new_claim.claim_text.casefold()))
    ignored = {"the", "and", "for", "with", "that", "this", "from", "can", "may", "not", "should", "is", "are"}
    old_terms -= ignored
    new_terms -= ignored
    if not old_terms or not new_terms:
        return False
    return len(old_terms & new_terms) / len(old_terms | new_terms) >= 0.3


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
            inc.status = "awaiting_correction"
            db.add(IncidentTrace(incident_id=inc.id, step="Rescan", detail="Recheck could not run because the original snapshot or site is unavailable; incident remains open for review"))
            db.commit()
            return {"status": "awaiting_correction", "note": "recheck unavailable"}

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
            inc.status = "awaiting_correction"
            db.add(IncidentTrace(incident_id=inc.id, step="Rescan", detail="Page could not be rescanned; no resolution was inferred"))
            scan.status = "failed"
            scan.error = "; ".join(result.errors)[:500]
            scan.finished_at = datetime.now(timezone.utc)
            scan.duration_s = max(0, int((scan.finished_at - scan.started_at).total_seconds())) if scan.started_at else 0
            site.last_scan_status = "failed"
            db.commit()
            return {"status": "awaiting_correction", "error": "page could not be rescanned"}

        claims, failures = extract_claims(page.text, page.url)
        extraction_failures = [f for f in failures if f.reason in {"model_unavailable", "invalid_output"}]
        if extraction_failures or not claims:
            inc.status = "awaiting_correction"
            db.add(IncidentTrace(incident_id=inc.id, step="Rescan", detail="Claim extraction did not produce a verifiable result; incident remains open"))
            scan.status = "failed"
            scan.error = "; ".join(f.detail for f in extraction_failures)[:500] or "No claim could be extracted for recheck"
            scan.finished_at = datetime.now(timezone.utc)
            scan.duration_s = max(0, int((scan.finished_at - scan.started_at).total_seconds())) if scan.started_at else 0
            site.last_scan_status = "failed"
            db.commit()
            return {"status": "awaiting_correction", "error": "claim extraction could not be verified"}

        old = inc.claim
        matching_outcome = None
        for c in claims:
            if not old or not _same_claim(old, c):
                continue
            hits = hybrid_search(db, inc.organization_id, c.claim_text, jurisdiction=site.jurisdiction)
            ev_texts = [h.text for h in hits]
            matching_outcome = verify_mod.verify(c, ev_texts, [None] * len(ev_texts))
            break

        inc.attempt_no += 1
        if matching_outcome is None:
            inc.status = "awaiting_correction"
            db.add(IncidentTrace(incident_id=inc.id, step="Rescan", detail=f"Attempt {inc.attempt_no}: the original claim could not be matched confidently; incident remains open"))
            scan.status = "failed"
            scan.error = "Could not match the extracted claim to the incident under review"
        elif matching_outcome.verdict == "POTENTIAL_CONTRADICTION":
            inc.status = "open"
            db.add(IncidentTrace(incident_id=inc.id, step="Rescan", detail=f"Attempt {inc.attempt_no}: claim still conflicts after rescan; reopened"))
        elif matching_outcome.verdict == "SUPPORTED":
            inc.status = "resolved"
            db.add(IncidentTrace(incident_id=inc.id, step="Rescan", detail=f"Attempt {inc.attempt_no}: page rescanned; claim no longer conflicts with the evidence"))
        else:
            inc.status = "awaiting_correction"
            db.add(IncidentTrace(incident_id=inc.id, step="Rescan", detail=f"Attempt {inc.attempt_no}: recheck was inconclusive ({matching_outcome.verdict}); incident remains open"))

        from app.models import Notification

        # A reopened incident is NOT a resolution — only notify when the rescan
        # actually cleared the conflict.
        if inc.status == "resolved":
            db.add(Notification(
                organization_id=inc.organization_id,
                kind="resolved",
                title=f"Finding resolved on {site.domain}",
                detail=inc.title,
                href=f"/incidents/{inc.public_id}",
            ))
        if scan.status != "failed":
            scan.status = "completed"
        scan.finished_at = datetime.now(timezone.utc)
        scan.duration_s = max(0, int((scan.finished_at - scan.started_at).total_seconds())) if scan.started_at else 0
        site.last_scan_status = scan.status
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
    from app.models import Scan, Site, new_id
    from sqlalchemy import select

    db = SessionLocal()
    try:
        sites = db.scalars(select(Site).where(Site.enabled.is_(True)).with_for_update(skip_locked=True)).all()
        now = datetime.now(timezone.utc)
        enqueued = 0
        for site in sites:
            active = db.scalar(
                select(Scan.id).where(Scan.site_id == site.id, Scan.status.in_(("queued", "running"))).limit(1)
            )
            if active:
                continue
            due = site.last_scan_at is None or site.last_scan_at + timedelta(hours=site.scan_interval_hours) <= now
            if not due:
                continue
            scan = Scan(
                id=new_id(),
                organization_id=site.organization_id,
                site_id=site.id,
                status="queued",
                trigger="scheduled",
                max_pages=25,
            )
            db.add(scan)
            # Set this at enqueue time so simultaneous beat workers cannot
            # schedule another run before the crawler starts.
            site.last_scan_at = now
            db.commit()
            try:
                run_scan_task.delay(scan.id)
            except Exception as exc:
                scan.status = "failed"
                scan.finished_at = now
                scan.error = f"Could not queue scheduled scan: {exc.__class__.__name__}"
                site.last_scan_status = "failed"
                db.commit()
                continue
            enqueued += 1
        return {"enqueued": enqueued}
    finally:
        db.close()


@celery_app.task(name="medguard.snapshot_retention")
def snapshot_retention_task() -> dict:
    """Remove expired, unreferenced page snapshots and expired refresh tokens.

    Current page versions and snapshots used by claims/findings are preserved.
    Reviewer decisions and audit logs are intentionally retained indefinitely.
    """
    from sqlalchemy import delete, exists, select

    from app.core.database import SessionLocal
    from app.models import Claim, Organization, OrgSetting, Page, RefreshToken, Site, Snapshot

    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        profiles = dict(db.execute(
            select(Organization.id, OrgSetting.organization_profile)
            .outerjoin(OrgSetting, OrgSetting.organization_id == Organization.id)
        ).all())
        deleted_snapshots = 0
        for org_id, profile in profiles.items():
            days = max(30, min(3650, int((profile or {}).get("retention_days", 365))))
            cutoff = now - timedelta(days=days)
            current_snapshot = exists(select(Page.id).where(Page.last_snapshot_id == Snapshot.id))
            claimed_snapshot = exists(select(Claim.id).where(Claim.snapshot_id == Snapshot.id))
            result = db.execute(
                delete(Snapshot)
                .where(
                    Snapshot.site_id.in_(select(Site.id).where(Site.organization_id == org_id)),
                    Snapshot.fetched_at < cutoff,
                    ~current_snapshot,
                    ~claimed_snapshot,
                )
                .execution_options(synchronize_session=False)
            )
            deleted_snapshots += result.rowcount or 0
        expired_tokens = db.execute(
            delete(RefreshToken)
            .where(RefreshToken.expires_at < now)
            .execution_options(synchronize_session=False)
        ).rowcount or 0
        db.commit()
        return {"deleted_snapshots": deleted_snapshots, "deleted_expired_refresh_tokens": expired_tokens}
    finally:
        db.close()
