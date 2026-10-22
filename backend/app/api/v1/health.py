"""Liveness and readiness probes."""
from fastapi import APIRouter, Depends, Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db

router = APIRouter()


@router.get("/health")
def health():
    return {"status": "ok", "service": settings.app_name}


@router.get("/health/ready")
def ready(response: Response, db: Session = Depends(get_db)):
    checks: dict[str, str] = {}
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:  # pragma: no cover - failure path
        checks["database"] = f"error: {exc.__class__.__name__}"
    try:
        import redis as redis_lib

        r = redis_lib.Redis.from_url(settings.redis_url, socket_timeout=1)
        r.ping()
        checks["redis"] = "ok"
    except Exception as exc:  # pragma: no cover
        checks["redis"] = f"error: {exc.__class__.__name__}"
    try:
        import httpx

        resp = httpx.get(f"{settings.ollama_base_url}/api/version", timeout=3)
        checks["llm"] = "ok" if resp.status_code == 200 else f"error: HTTP {resp.status_code}"
    except Exception as exc:  # pragma: no cover
        checks["llm"] = f"error: {exc.__class__.__name__}"
    ok = all(v == "ok" for v in checks.values())
    if not ok:
        response.status_code = 503
    return {"status": "ready" if ok else "degraded", "checks": checks}
