"""Shared FastAPI dependencies: current user, RBAC, org scoping."""
from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWTError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_token
from app.models import User

bearer_scheme = HTTPBearer(auto_error=False)

ROLE_PERMS: dict[str, list[str]] = {
    "review": ["admin", "reviewer"],
    "scan": ["admin", "reviewer"],
    "manageSites": ["admin"],
    "administer": ["admin"],
}


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if creds is None or not creds.credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = decode_token(creds.credentials)
    except PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token type")
    user = db.get(User, payload.get("sub"))
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    return user


def require_perm(perm: str):
    allowed = ROLE_PERMS[perm]

    def _dep(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(status_code=403, detail="You do not have permission to perform this action")
        return user

    return _dep


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="You do not have permission to perform this action")
    return user


async def login_rate_limit(request: Request) -> None:
    """Per-IP fixed-window limiter backed by Redis.

    Limiting by IP prevents attempts from bypassing the throttle by rotating
    email addresses. The test suite can disable this guard explicitly.
    """
    from app.core.config import settings
    if not settings.login_rate_limit_enabled:
        return
    import redis as redis_lib

    key = f"login:rl:{request.client.host if request.client else 'unknown'}"
    try:
        r = redis_lib.Redis.from_url(settings.redis_url, socket_timeout=1)
        n = r.incr(key)
        if n == 1:
            r.expire(key, settings.login_rate_limit_window_s)
        if n > settings.login_rate_limit_attempts:
            raise HTTPException(status_code=429, detail="Too many login attempts. Try again shortly.")
    except HTTPException:
        raise
    except Exception:  # Redis unavailable — do not lock everyone out
        pass
