"""Scans: POST /scans enqueues a real background job; GETs expose progress."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_perm
from app.core.config import settings
from app.core.database import get_db
from app.models import Scan, Site, User, new_id
from app.schemas import ScanCreate, ScanOut

router = APIRouter()


@router.post("", response_model=ScanOut, status_code=201)
def start_scan(
    body: ScanCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_perm("scan")),
):
    site = db.scalar(select(Site).where(Site.id == body.site_id, Site.organization_id == user.organization_id))
    if site is None:
        raise HTTPException(status_code=404, detail="Unknown site")
    if not site.enabled:
        raise HTTPException(status_code=409, detail="Enable this site before scanning")

    scan = Scan(
        id=new_id(),
        organization_id=user.organization_id,
        site_id=site.id,
        status="queued",
        pages_total=0,
        max_pages=settings.scan_default_max_pages,
        trigger="manual",
    )
    db.add(scan)
    db.commit()
    db.refresh(scan)

    from app.workers.tasks import run_scan_task

    async_result = run_scan_task.delay(scan.id)
    scan.task_id = async_result.id
    db.commit()
    db.refresh(scan)
    return ScanOut.model_validate(scan, from_attributes=True)


@router.get("", response_model=list[ScanOut])
def list_scans(
    site_id: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = select(Scan).where(Scan.organization_id == user.organization_id)
    if site_id:
        q = q.where(Scan.site_id == site_id)
    q = q.order_by(Scan.started_at.desc()).limit(100)
    return [ScanOut.model_validate(s, from_attributes=True) for s in db.scalars(q).all()]


@router.get("/{scan_id}", response_model=ScanOut)
def get_scan(scan_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    scan = db.scalar(select(Scan).where(Scan.id == scan_id, Scan.organization_id == user.organization_id))
    if scan is None:
        raise HTTPException(status_code=404, detail="Scan not found")
    return ScanOut.model_validate(scan, from_attributes=True)
