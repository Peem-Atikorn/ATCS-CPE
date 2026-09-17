"""Enqueue jobs on Celery from async code."""

from __future__ import annotations

import asyncio
from uuid import UUID

from celery import Celery

from app.workers.celery_app import RECOMMENDATION_QUEUE, RUN_RECOMMENDATION

# Publishing blocks while the broker is unreachable; keep that short.
_RETRY_POLICY = {"max_retries": 2, "interval_start": 0, "interval_step": 0.5, "interval_max": 1}


class CeleryJobQueue:
    def __init__(self, celery: Celery) -> None:
        self._celery = celery

    async def enqueue_recommendation(self, job_id: UUID, *, correlation_id: str) -> str:
        # Only ids go through the broker (docs/04_project_structure.md section 6).
        result = await asyncio.to_thread(
            self._celery.send_task,
            RUN_RECOMMENDATION,
            kwargs={"job_id": str(job_id), "correlation_id": correlation_id},
            queue=RECOMMENDATION_QUEUE,
            retry=True,
            retry_policy=_RETRY_POLICY,
        )
        return str(result.id)
