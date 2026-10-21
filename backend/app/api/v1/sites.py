"""Sites CRUD — contract: GET/POST /sites, GET/PATCH /sites/{id}."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_perm
from app.core.database import get_db
from app.models import AuditLog, Site, User, new_id
from app.schemas import SiteCreate, SiteOut, SitePatch

router = APIRouter()


def _normalize_domain(raw: str) -> str:
    domain = raw.strip().lower()
    for prefix in ("https://", "http://"):
        if domain.startswith(prefix):
            domain = domain[len(prefix):]
    domain = domain.split("/")[0]
    if not domain or " " in domain:
        raise HTTPException(status_code=422, detail="A valid domain is required")
    # keep :port only for local dev targets (demo site); strip otherwise
    from app.core.config import settings

    host, _, port = domain.partition(":")
    if port:
        is_local = host in ("localhost", "127.0.0.1", "0.0.0.0")
        if not (settings.allow_local_targets and is_local and port.isdigit()):
            domain = host
    return domain


@router.get("", response_model=list[SiteOut])
def list_sites(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    sites = db.scalars(select(Site).where(Site.organization_id == user.organization_id).order_by(Site.domain)).all()
    return [SiteOut.model_validate(s, from_attributes=True) for s in sites]


@router.post("", response_model=SiteOut, status_code=201)
def create_site(
    body: SiteCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_perm("manageSites")),
):
    domain = _normalize_domain(body.domain)
    existing = db.scalar(
        select(Site).where(Site.organization_id == user.organization_id, Site.domain == domain)
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="That domain is already registered")
    site = Site(
        id=new_id(),
        organization_id=user.organization_id,
        domain=domain,
        jurisdiction=body.jurisdiction or "US",
        language=body.language or "en",
        scan_interval_hours=body.scan_interval_hours or 24,
        enabled=True,
        pages=0,
    )
    db.add(site)
    db.add(
        AuditLog(
            organization_id=user.organization_id,
            actor=user.name,
            action="site",
            object=domain,
            site=domain,
            detail="Website added to monitoring",
        )
    )
    db.commit()
    db.refresh(site)
    return SiteOut.model_validate(site, from_attributes=True)


@router.get("/{site_id}", response_model=SiteOut)
def get_site(site_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    site = db.scalar(select(Site).where(Site.id == site_id, Site.organization_id == user.organization_id))
    if site is None:
        raise HTTPException(status_code=404, detail="Site not found")
    return SiteOut.model_validate(site, from_attributes=True)


@router.patch("/{site_id}", response_model=SiteOut)
def patch_site(
    site_id: str,
    body: SitePatch,
    db: Session = Depends(get_db),
    user: User = Depends(require_perm("manageSites")),
):
    site = db.scalar(select(Site).where(Site.id == site_id, Site.organization_id == user.organization_id))
    if site is None:
        raise HTTPException(status_code=404, detail="Site not found")
    data = body.model_dump(exclude_unset=True)
    was_enabled = site.enabled
    for k, v in data.items():
        setattr(site, k, v)
    if "enabled" in data and data["enabled"] != was_enabled:
        db.add(
            AuditLog(
                organization_id=user.organization_id,
                actor=user.name,
                action="site",
                object=site.domain,
                site=site.domain,
                detail="Monitoring enabled" if data["enabled"] else "Monitoring paused (site disabled)",
            )
        )
    db.commit()
    db.refresh(site)
    return SiteOut.model_validate(site, from_attributes=True)
