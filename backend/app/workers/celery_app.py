"""Celery application: Redis broker, real background jobs."""
from __future__ import annotations

import sys
from pathlib import Path

from celery import Celery

# Make the backend package importable when the worker starts from backend/
_backend_root = str(Path(__file__).resolve().parents[2])
if _backend_root not in sys.path:
    sys.path.insert(0, _backend_root)

from app.core.config import settings  # noqa: E402

celery_app = Celery(
    "medguard",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_soft_time_limit=60 * 30,
    task_time_limit=60 * 40,
    task_default_retry_delay=10,
    broker_connection_retry_on_startup=True,
    # Windows Redis 5.x (RESP2-only) compatibility
    broker_transport_options={"confirm_publish": True},
    redis_max_connections=10,
)

celery_app.autodiscover_tasks(["app.workers"])

# Register the beat schedule (declared in app.workers.schedules). Nothing else
# imports that module, so without this beat starts with an empty schedule and
# the hourly scheduled-scan task never fires.
from app.workers import schedules  # noqa: E402,F401
