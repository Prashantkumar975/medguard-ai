"""Incidents: list/filter, detail, review (immutable audit), recheck (new attempt)."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import case, exists, or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, require_perm
from app.core.database import get_db
from app.models import (
    AuditLog,
    Claim,
    Evidence,
    Incident,
    IncidentTrace,
    Notification,
    Review,
    Site,
    Snapshot,
    User,
)
from app.schemas import (
    ClaimDetail,
    DecisionOut,
    EvidenceOut,
    IncidentDetail,
    IncidentSummary,
    ReviewRequest,
    RiskOut,
    TraceEntry,
)

router = APIRouter()

PRIORITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}
ACTIVE = ("open", "in_review", "awaiting_correction")
DECISION_TRANSITIONS = {"confirm": "awaiting_correction", "dismiss": "dismissed", "needs_info": "in_review"}
REVIEW_LABEL = {"confirm": "Issue confirmed", "needs_info": "More information requested", "dismiss": "Dismissed as false alarm"}


def _summary(inc: Incident, site_domain: str | None) -> IncidentSummary:
    ev = inc.evidence[0] if inc.evidence else None
    return IncidentSummary(
        id=inc.public_id,
        title=inc.title,
        priority=inc.priority,
        verdict=inc.verdict,
        status=inc.status,
        site=site_domain or "",
        page_url=inc.snapshot.url if inc.snapshot else None,
        claim_statement=inc.claim.statement if inc.claim else "",
        evidence_authority=ev.document.authority if ev and ev.document else None,
        evidence_date=ev.document.effective_date if ev and ev.document else None,
        created_at=inc.created_at,
    )


def _detail(inc: Incident, site_domain: str | None) -> IncidentDetail:
    claim = inc.claim
    snap = inc.snapshot
    return IncidentDetail(
        id=inc.public_id,
        title=inc.title,
        priority=inc.priority,
        verdict=inc.verdict,
        status=inc.status,
        site=site_domain or "",
        page_url=snap.url if snap else None,
        created_at=inc.created_at,
        agent_run_id=inc.agent_run_id,
        claim=ClaimDetail(
            id=claim.id,
            statement=claim.statement,
            context=claim.context_label,
            offsets=[claim.offsets_start, claim.offsets_end],
            snapshot_id=claim.snapshot_id,
            snapshot_fetched_at=snap.fetched_at if snap else None,
            content_hash=f"sha256:{snap.content_hash}" if snap else None,
        ),
        evidence=[
            EvidenceOut(
                id=e.id,
                document_id=e.document_id,
                authority=e.document.authority if e.document else "",
                doc_type=e.document.doc_type if e.document else "",
                title=e.document.title if e.document else "",
                version=e.document.version if e.document else "",
                effective_date=e.document.effective_date if e.document else None,
                url=e.document.source_url if e.document else "",
                section=e.section,
                quote=e.quote,
                offsets=[e.offsets_start, e.offsets_end],
            )
            for e in inc.evidence
        ],
        rationale=inc.rationale,
        risk=RiskOut(
            harm=inc.harm,
            exposure=inc.exposure,
            evidence_strength=inc.evidence_strength,
            uncertainty=inc.uncertainty,
        ),
        decision=(
            DecisionOut(
                decision=inc.reviews[-1].decision,
                rationale=inc.reviews[-1].rationale,
                reviewer=inc.reviews[-1].reviewer.name,
                at=inc.reviews[-1].created_at,
            )
            if inc.reviews
            else None
        ),
        trace=[TraceEntry(step=t.step, detail=t.detail, at=t.at) for t in inc.trace],
    )


def _load(db: Session, user: User, public_id: str) -> Incident:
    inc = db.scalar(
        select(Incident)
        .join(Site, Incident.site_id == Site.id)
        .where(Incident.public_id == public_id, Incident.organization_id == user.organization_id)
    )
    if inc is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return inc


@router.get("", response_model=list[IncidentSummary])
def list_incidents(
    q: str | None = None,
    priority: str | None = None,
    verdict: str | None = None,
    site: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # Filtering, ordering and eager-loading all happen in SQL: priority-first
    # ordering via a CASE rank, org scoping, and claim/snapshot/evidence.document
    # selectinloaded so building the response never lazy-loads per row (N+1).
    stmt = (
        select(Incident, Site.domain)
        .join(Site, Incident.site_id == Site.id)
        .where(Incident.organization_id == user.organization_id)
        .options(
            selectinload(Incident.claim),
            selectinload(Incident.snapshot),
            selectinload(Incident.evidence).selectinload(Evidence.document),
        )
    )
    if priority:
        stmt = stmt.where(Incident.priority == priority)
    if verdict:
        stmt = stmt.where(Incident.verdict == verdict)
    if site:
        stmt = stmt.where(Site.domain == site)
    if status and status != "all":
        if status == "active":
            stmt = stmt.where(Incident.status.in_(ACTIVE))
        else:
            stmt = stmt.where(Incident.status == status)
    if q:
        like = f"%{(q or '').lower()}%"
        stmt = stmt.where(
            or_(
                Incident.title.ilike(like),
                Incident.public_id.ilike(like),
                Site.domain.ilike(like),
                exists().where(Claim.id == Incident.claim_id, Claim.statement.ilike(like)),
            )
        )
    rank = case(*[(Incident.priority == k, v) for k, v in PRIORITY_RANK.items()], else_=9)
    stmt = stmt.order_by(rank, Incident.created_at.desc())
    return [_summary(inc, domain) for inc, domain in db.execute(stmt).all()]


@router.get("/{incident_id}", response_model=IncidentDetail)
def get_incident(incident_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    inc = _load(db, user, incident_id)
    from urllib.parse import urlparse

    domain = urlparse(inc.snapshot.url).netloc if inc.snapshot else ""
    return _detail(inc, domain)


@router.post("/{incident_id}/review", response_model=IncidentDetail)
def review_incident(
    incident_id: str,
    body: ReviewRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_perm("review")),
):
    inc = _load(db, user, incident_id)
    if not body.decision or len(body.rationale.strip()) < 10:
        raise HTTPException(
            status_code=422,
            detail="Choose a decision and write a rationale of at least 10 characters",
        )
    previous = inc.status
    inc.status = DECISION_TRANSITIONS[body.decision]
    review = Review(
        incident_id=inc.id,
        reviewer_id=user.id,
        decision=body.decision,
        rationale=body.rationale.strip(),
        previous_status=previous,
        new_status=inc.status,
    )
    db.add(review)
    db.add(
        IncidentTrace(
            incident_id=inc.id,
            step="Human review",
            detail=f"Reviewer decision recorded: {body.decision}",
        )
    )
    db.add(
        AuditLog(
            organization_id=user.organization_id,
            actor=user.name,
            action="review",
            object=inc.public_id,
            incident_id=inc.public_id,
            detail=f"{REVIEW_LABEL[body.decision]}: {body.rationale.strip()}",
        )
    )
    if inc.status == "resolved":
        db.add(
            Notification(
                organization_id=user.organization_id,
                kind="resolved",
                title=f"Finding resolved on {(inc.snapshot.url.split('/')[2] if inc.snapshot else '')}",
                detail=inc.title,
                href=f"/incidents/{inc.public_id}",
            )
        )
    db.commit()
    db.refresh(inc)
    from urllib.parse import urlparse

    domain = urlparse(inc.snapshot.url).netloc if inc.snapshot else ""
    return _detail(inc, domain)


@router.post("/{incident_id}/recheck", response_model=IncidentDetail)
def recheck_incident(
    incident_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_perm("review")),
):
    inc = _load(db, user, incident_id)
    if inc.status != "awaiting_correction":
        raise HTTPException(
            status_code=409,
            detail="Recheck is only available after a confirmed issue has been corrected",
        )
    # Persist the pending state BEFORE enqueuing: the worker may finish (and
    # write a terminal status) at any moment after .delay(), and a commit issued
    # here afterwards would overwrite it and strand the incident in_review.
    # If the broker is unreachable the status is reverted rather than left
    # pending with no task behind it (the beat reaper is the backstop).
    from app.workers.tasks import run_recheck_task

    previous = inc.status
    inc.status = "in_review"
    db.add(
        IncidentTrace(
            incident_id=inc.id,
            step="Rescan",
            detail="Recheck requested — page queued for rescan and re-verification",
        )
    )
    db.add(
        AuditLog(
            organization_id=user.organization_id,
            actor=user.name,
            action="recheck",
            object=inc.public_id,
            incident_id=inc.public_id,
            detail="Recheck requested — page queued for rescan",
        )
    )
    db.commit()
    try:
        run_recheck_task.delay(inc.id, user.id)
    except Exception:
        inc.status = previous
        db.add(
            IncidentTrace(
                incident_id=inc.id,
                step="Rescan",
                detail="Recheck could not be queued (broker unavailable); status restored",
            )
        )
        db.commit()
        raise HTTPException(
            status_code=503,
            detail="Could not queue the recheck. Please try again shortly.",
        )
    db.refresh(inc)
    from urllib.parse import urlparse

    domain = urlparse(inc.snapshot.url).netloc if inc.snapshot else ""
    return _detail(inc, domain)
