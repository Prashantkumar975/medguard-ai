"""Claims search — contract: GET /claims?q= returns claims enriched with site/page/incident."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models import Claim, Incident, Page, Snapshot, User
from app.schemas import ClaimOut

router = APIRouter()


@router.get("", response_model=list[ClaimOut])
def list_claims(
    q: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = (
        select(Claim, Snapshot.url, Incident.public_id)
        .join(Snapshot, Claim.snapshot_id == Snapshot.id)
        .outerjoin(Incident, Incident.claim_id == Claim.id)
        .where(Claim.organization_id == user.organization_id)
        .order_by(Claim.extracted_at.desc())
        .limit(500)
    )
    if q:
        stmt = stmt.where(Claim.statement.ilike(f"%{q}%"))
    rows = db.execute(stmt).all()
    out: list[ClaimOut] = []
    seen: set[str] = set()
    for claim, url, incident_public_id in rows:
        if incident_public_id and incident_public_id in seen:
            continue
        if incident_public_id:
            seen.add(incident_public_id)
        snap = db.get(Snapshot, claim.snapshot_id)
        site_domain = None
        if snap is not None:
            from urllib.parse import urlparse

            site_domain = urlparse(snap.url).netloc
        out.append(
            ClaimOut(
                id=claim.id,
                statement=claim.statement,
                context=claim.context_label,
                offsets=[claim.offsets_start, claim.offsets_end],
                snapshot_id=claim.snapshot_id,
                snapshot_fetched_at=snap.fetched_at if snap else None,
                content_hash=f"sha256:{snap.content_hash}" if snap else None,
                site=site_domain,
                page_url=url,
                incident_id=incident_public_id,
            )
        )
    return out
