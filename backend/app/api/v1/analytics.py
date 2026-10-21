"""Analytics — every number computed from real stored records via SQL."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models import Claim, Incident, Scan, Site, Snapshot, User
from app.schemas import AnalyticsSummary, Kpi, RecentRun, ScanActivityDay, VerdictCount

router = APIRouter()

ACTIVE = ("open", "in_review", "awaiting_correction")


def _series_7d(db: Session, org: str) -> list[int]:
    """Daily active-incident totals for the last 7 days (ending today)."""
    out: list[int] = []
    now = datetime.now(timezone.utc)
    for i in range(6, -1, -1):
        day_start = (now - timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        n = db.scalar(
            select(func.count(Incident.id)).where(
                Incident.organization_id == org,
                Incident.created_at < day_end,
            )
        )
        out.append(n or 0)
    return out


@router.get("/summary", response_model=AnalyticsSummary)
def analytics_summary(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    org = user.organization_id
    now = datetime.now(timezone.utc)

    # --- KPI: open findings + critical count ---
    active_rows = db.scalars(
        select(Incident).where(Incident.organization_id == org, Incident.status.in_(ACTIVE))
    ).all()
    active_count = len(active_rows)
    critical_count = sum(1 for i in active_rows if i.priority == "critical")

    # --- KPI: pages scanned in the last 24h ---
    day_ago = now - timedelta(hours=24)
    pages_24h = db.scalar(
        select(func.coalesce(func.sum(Scan.pages_done), 0)).where(
            Scan.organization_id == org, Scan.started_at >= day_ago
        )
    ) or 0
    prev_pages = db.scalar(
        select(func.coalesce(func.sum(Scan.pages_done), 0)).where(
            Scan.organization_id == org,
            Scan.started_at >= day_ago - timedelta(hours=24),
            Scan.started_at < day_ago,
        )
    ) or 0
    pages_delta = f"{(pages_24h - prev_pages) / prev_pages * 100:+.1f}% vs yesterday" if prev_pages else "no prior data"

    # --- KPI: claims extracted in the last 7 days ---
    week_ago = now - timedelta(days=7)
    claims_week = db.scalar(
        select(func.count(Claim.id)).where(Claim.organization_id == org, Claim.extracted_at >= week_ago)
    ) or 0
    prev_week = db.scalar(
        select(func.count(Claim.id)).where(
            Claim.organization_id == org, Claim.extracted_at >= week_ago - timedelta(days=7), Claim.extracted_at < week_ago
        )
    ) or 0

    # --- KPI: median review turnaround (created -> first review) ---
    from app.models import Review

    review_rows = db.execute(
        select(Review.created_at, Incident.created_at)
        .join(Incident, Review.incident_id == Incident.id)
        .where(Incident.organization_id == org)
    ).all()
    deltas = sorted((r_created - i_created).total_seconds() / 3600 for r_created, i_created in review_rows)
    if deltas:
        median_h = deltas[len(deltas) // 2]
        review_value = f"{median_h:.1f}h"
    else:
        review_value = "—"

    kpis = [
        Kpi(key="open", label="Open findings", value=active_count, delta=f"{critical_count} critical", series=_series_7d(db, org)),
        Kpi(key="pages", label="Pages scanned (24h)", value=int(pages_24h), delta=pages_delta),
        Kpi(key="claims", label="Claims extracted (7d)", value=claims_week, delta=f"{claims_week - prev_week:+d} vs prior week"),
        Kpi(key="review", label="Median time to review", value=review_value, delta=f"{len(deltas)} reviews recorded"),
    ]

    # --- scan activity: last 14 days ---
    scan_activity: list[ScanActivityDay] = []
    for i in range(13, -1, -1):
        day_start = (now - timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        changed = db.scalar(
            select(func.count(Snapshot.id)).where(
                Snapshot.site_id.in_(select(Site.id).where(Site.organization_id == org)),
                Snapshot.changed.is_(True),
                Snapshot.fetched_at >= day_start,
                Snapshot.fetched_at < day_end,
            )
        ) or 0
        flagged = db.scalar(
            select(func.count(Incident.id)).where(
                Incident.organization_id == org,
                Incident.created_at >= day_start,
                Incident.created_at < day_end,
                Incident.verdict != "SUPPORTED",
            )
        ) or 0
        scan_activity.append(
            ScanActivityDay(day=f"{day_start.strftime('%b')} {day_start.day}", changed=changed, flagged=flagged)
        )

    # --- verdict distribution over all incidents ---
    verdict_rows = db.execute(
        select(Incident.verdict, func.count(Incident.id))
        .where(Incident.organization_id == org)
        .group_by(Incident.verdict)
    ).all()
    counts = {v: c for v, c in verdict_rows}
    by_verdict = [
        VerdictCount(verdict=v, count=counts.get(v, 0))
        for v in ("SUPPORTED", "POTENTIAL_CONTRADICTION", "POSSIBLY_OUTDATED", "INCOMPLETE_INFORMATION", "INSUFFICIENT_EVIDENCE")
    ]

    # --- priority distribution of active incidents ---
    by_priority = {k: 0 for k in ("critical", "high", "medium", "low")}
    for inc in active_rows:
        by_priority[inc.priority] = by_priority.get(inc.priority, 0) + 1

    # --- recent runs ---
    recent = db.scalars(
        select(Scan).where(Scan.organization_id == org).order_by(Scan.started_at.desc()).limit(8)
    ).all()
    site_domains = {s.id: s.domain for s in db.scalars(select(Site).where(Site.organization_id == org))}
    recent_runs = [
        RecentRun(
            id=scan.id,
            site=site_domains.get(scan.site_id, ""),
            status=scan.status,
            pages=scan.pages_done,
            changed=scan.changed,
            at=scan.started_at,
            duration_s=scan.duration_s,
            error=scan.error,
        )
        for scan in recent
    ]

    return AnalyticsSummary(
        kpis=kpis,
        scan_activity=scan_activity,
        by_verdict=by_verdict,
        by_priority=by_priority,
        recent_runs=recent_runs,
    )
