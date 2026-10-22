"""API v1 router aggregation."""
from fastapi import APIRouter

from app.api.v1 import (
    admin,
    analytics,
    auth,
    claims,
    health,
    incidents,
    notifications,
    references,
    reports,
    scans,
    sites,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(sites.router, prefix="/sites", tags=["sites"])
api_router.include_router(scans.router, prefix="/scans", tags=["scans"])
api_router.include_router(claims.router, prefix="/claims", tags=["claims"])
api_router.include_router(incidents.router, prefix="/incidents", tags=["incidents"])
api_router.include_router(references.router, prefix="/references", tags=["references"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(admin.router_audit, prefix="/audit", tags=["audit"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])
