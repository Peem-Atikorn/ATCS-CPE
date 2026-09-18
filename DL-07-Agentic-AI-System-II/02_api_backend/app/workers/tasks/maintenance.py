"""Queue `maintenance`: stuck-job reaper (D-74) and account deletion (D-79)."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from uuid import UUID

import structlog
from celery import shared_task

from app.core.ids import accept_client_id, correlation_id_var, new_id
from app.core.logging import get_logger
from app.workers.celery_app import DELETE_ACCOUNT, REAP_STUCK_JOBS
from app.workers.runtime import runtime

log = get_logger(__name__)


@contextmanager
def _correlation(value: str) -> Iterator[None]:
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(correlation_id=value)
    token = correlation_id_var.set(value)
    try:
        yield
    finally:
        correlation_id_var.reset(token)
        structlog.contextvars.clear_contextvars()


@shared_task(name=REAP_STUCK_JOBS, ignore_result=True)
def reap_stuck_jobs() -> dict[str, int]:
    with _correlation(str(new_id())):
        return runtime.reap_stuck_jobs()


@shared_task(name=DELETE_ACCOUNT, ignore_result=True)
def delete_account(user_id: str, correlation_id: str | None = None) -> bool:
    with _correlation(accept_client_id(correlation_id) or str(new_id())):
        try:
            parsed = UUID(user_id)
        except ValueError:
            log.warning("invalid_user_id")
            return False
        return runtime.delete_account(parsed)
