"""Beat schedule for recurring monitoring."""
from app.workers.celery_app import celery_app

celery_app.conf.beat_schedule = {
    "scheduled-scans-every-hour": {
        "task": "medguard.scheduled_scans",
        "schedule": 3600.0,
    },
    # Fail scans stuck queued/running and rechecks that never finished after a
    # worker died mid-task (the orphaned broker delivery is not always restored).
    "reap-stuck-every-10-minutes": {
        "task": "medguard.reap_stuck",
        "schedule": 600.0,
    },
    "snapshot-retention-daily": {
        "task": "medguard.snapshot_retention",
        "schedule": 86400.0,
    },
}
