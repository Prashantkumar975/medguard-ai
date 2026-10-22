"""Admin: users, settings (contract shapes), plus the org-wide audit trail."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.core.database import get_db
from app.models import AuditLog, Organization, OrgSetting, User
from app.schemas import AuditEventOut, SettingsOut, UserOut, UserPatch

router = APIRouter()
router_audit = APIRouter()

DEFAULT_NOTIFICATIONS = {
    "email_enabled": True,
    "recipients": "",
    "webhook_url": "",
    "min_priority": "high",
    "daily_digest": True,
}
DEFAULT_ORG_PROFILE = {
    "name": "",
    "default_scan_interval_hours": 24,
    "jurisdictions": ["US"],
    "retention_days": 365,
}


def _ensure_settings(db: Session, org_id: str, org_name: str) -> OrgSetting:
    row = db.get(OrgSetting, org_id)
    if row is None:
        profile = {**DEFAULT_ORG_PROFILE, "name": org_name}
        row = OrgSetting(organization_id=org_id, notifications=dict(DEFAULT_NOTIFICATIONS), organization_profile=profile)
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


@router.get("/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    users = db.scalars(select(User).where(User.organization_id == admin.organization_id)).all()
    return [
        UserOut(id=u.id, name=u.name, email=u.email, role=u.role, last_active=u.last_active) for u in users
    ]


@router.patch("/users/{user_id}", response_model=UserOut)
def patch_user(
    user_id: str,
    body: UserPatch,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    target = db.scalar(select(User).where(User.id == user_id, User.organization_id == admin.organization_id))
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")
    target.role = body.role
    db.add(
        AuditLog(
            organization_id=admin.organization_id,
            actor=admin.name,
            action="role",
            object=target.name,
            detail=f"Role changed to {body.role}",
        )
    )
    db.commit()
    db.refresh(target)
    return UserOut(id=target.id, name=target.name, email=target.email, role=target.role, last_active=target.last_active)


@router.get("/settings", response_model=SettingsOut)
def get_settings_(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    org = db.get(Organization, admin.organization_id)
    row = _ensure_settings(db, admin.organization_id, org.name if org else "")
    return SettingsOut(notifications=row.notifications, organization=row.organization_profile)


@router.put("/settings", response_model=SettingsOut)
def put_settings(
    body: SettingsOut,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    org = db.get(Organization, admin.organization_id)
    row = _ensure_settings(db, admin.organization_id, org.name if org else "")
    row.notifications = body.notifications.model_dump()
    row.organization_profile = body.organization.model_dump()
    db.add(
        AuditLog(
            organization_id=admin.organization_id,
            actor=admin.name,
            action="settings",
            object="Organization settings",
            detail=f"Settings updated (alert threshold: {body.notifications.min_priority})",
        )
    )
    db.commit()
    db.refresh(row)
    return SettingsOut(notifications=row.notifications, organization=row.organization_profile)


@router_audit.get("", response_model=list[AuditEventOut])
def audit_trail(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    rows = db.scalars(
        select(AuditLog)
        .where(AuditLog.organization_id == admin.organization_id)
        .order_by(AuditLog.at.desc())
        .limit(200)
    ).all()
    return [
        AuditEventOut(
            id=r.id,
            at=r.at,
            actor=r.actor,
            action=r.action,
            object=r.object,
            incident_id=r.incident_id,
            site=r.site,
            detail=r.detail,
        )
        for r in rows
    ]
