"""Celery beat schedule (docs/04_project_structure.md section 6).

Start the scheduler with:
    celery -A app.workers.celery_app:celery_app beat --schedule /tmp/celerybeat-schedule
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from app.core.config import Settings


def beat_schedule(settings: Settings) -> dict[str, dict[str, Any]]:
    from app.workers.celery_app import ALERT_QUEUE, SCAN_TRIP_ALERTS

    interval = timedelta(minutes=settings.trips.trip_alert_scan_minutes)  # P-56
    return {
        "scan-trip-alerts": {
            "task": SCAN_TRIP_ALERTS,
            "schedule": interval,
            # A run that waited longer than one interval is dropped; the next one covers it.
            "options": {"queue": ALERT_QUEUE, "expires": int(interval.total_seconds())},
        }
    }
