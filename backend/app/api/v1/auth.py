"""Auth endpoints: login, refresh (rotating), logout, me."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, login_rate_limit
from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token, decode_token, verify_password
from app.models import RefreshToken, User, new_id
from app.schemas import LoginRequest, MeOut, RefreshRequest, TokenPair
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
    user = db.scalar(select(User).where(User.email == body.email.lower().strip()))
    if user is None or not user.is_active or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return _issue_tokens(db, user)


@router.post("/refresh", response_model=TokenPair)
def refresh(body: RefreshRequest, db: Session = Depends(get_db)):
    token = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == _hash(body.refresh_token)))
    now = datetime.now(timezone.utc)
    if token is None or token.revoked_at is not None or token.expires_at < now:
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
