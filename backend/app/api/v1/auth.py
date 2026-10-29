"""Auth endpoints: login, refresh (rotating), logout, me."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, login_rate_limit
from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token, decode_token, hash_password, verify_password
from app.models import AuditLog, Organization, OrgSetting, RefreshToken, User, new_id
from app.schemas import LoginRequest, MeOut, RefreshRequest, RegisterRequest, TokenPair
import hashlib
import secrets

router = APIRouter()


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def _issue_tokens(db: Session, user: User) -> TokenPair:
    access = create_access_token(user_id=user.id, organization_id=user.organization_id, role=user.role)
    raw_refresh = secrets.token_urlsafe(48)
    db.add(
        RefreshToken(
            id=new_id(),
            user_id=user.id,
            token_hash=_hash(raw_refresh),
            expires_at=datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_ttl_days),
        )
    )
    user.last_active = datetime.now(timezone.utc)
    db.commit()
    return TokenPair(access_token=access, refresh_token=raw_refresh)


@router.post("/login", response_model=TokenPair)
def login(body: LoginRequest, db: Session = Depends(get_db), _rl=Depends(login_rate_limit)):
    query = select(User).where(User.email == body.email.lower().strip())
    if body.organization_id:
        query = query.where(User.organization_id == body.organization_id)
    matches = db.scalars(query.limit(2)).all()
    if len(matches) > 1:
        raise HTTPException(status_code=400, detail="Organization is required for this email address")
    user = matches[0] if matches else None
    if user is None or not user.is_active or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return _issue_tokens(db, user)


@router.post("/register", response_model=TokenPair, status_code=201)
def register(body: RegisterRequest, db: Session = Depends(get_db), _rl=Depends(login_rate_limit)):
    """Create a workspace and its first administrator, then start a session."""
    # Public self-service registration creates a new tenant/workspace; the first
    # registrant is its administrator. No existing tenant data is exposed.
    organization = Organization(name=body.organization_name.strip(), subscription_plan="trial")
    db.add(organization)
    db.flush()

    email = body.email.lower().strip()
    user = User(
        organization_id=organization.id,
        name=body.name.strip(),
        email=email,
        password_hash=hash_password(body.password),
        role="admin",
        is_active=True,
    )
    db.add(user)
    db.add(OrgSetting(
        organization_id=organization.id,
        notifications={"min_priority": "high"},
        organization_profile={
            "name": organization.name,
            "default_scan_interval_hours": 24,
            "jurisdictions": ["US"],
            "retention_days": 365,
        },
    ))
    db.add(AuditLog(
        organization_id=organization.id,
        actor=user.name,
        action="organization_created",
        object=organization.name,
        detail="Workspace and first administrator created through registration",
    ))
    db.flush()
    return _issue_tokens(db, user)


@router.post("/refresh", response_model=TokenPair)
def refresh(body: RefreshRequest, db: Session = Depends(get_db)):
    token = db.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == _hash(body.refresh_token)).with_for_update()
    )
    now = datetime.now(timezone.utc)
    if token is None:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    if token.revoked_at is not None:
        # Reuse of a rotated token indicates theft or a replay. Revoke the whole
        # user's refresh-token family so the stolen session cannot continue.
        db.query(RefreshToken).filter(
            RefreshToken.user_id == token.user_id,
            RefreshToken.revoked_at.is_(None),
        ).update({RefreshToken.revoked_at: now}, synchronize_session=False)
        db.commit()
        raise HTTPException(status_code=401, detail="Refresh token reuse detected; sign in again")
    if token.expires_at < now:
        token.revoked_at = now
        db.commit()
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    user = db.get(User, token.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    # rotate: revoke old, issue new
    token.revoked_at = now
    pair = _issue_tokens(db, user)
    return pair


@router.post("/logout")
def logout(body: RefreshRequest, db: Session = Depends(get_db)):
    token = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == _hash(body.refresh_token)))
    if token is not None and token.revoked_at is None:
        token.revoked_at = datetime.now(timezone.utc)
        db.commit()
    return {"ok": True}


@router.get("/me", response_model=MeOut)
def me(user: User = Depends(get_current_user)):
    return MeOut(
        id=user.id,
        name=user.name,
        email=user.email,
        role=user.role,  # type: ignore[arg-type]
        organization_id=user.organization_id,
        is_active=user.is_active,
    )
