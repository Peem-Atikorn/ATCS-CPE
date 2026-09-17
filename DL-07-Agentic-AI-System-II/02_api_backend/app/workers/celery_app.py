"""Celery application (docs/04_project_structure.md section 6).

Start a worker with:
    celery -A app.workers.celery_app:celery_app worker -Q recommendations

The app is created on first access, so importing this module needs no configuration.
Messages carry only ids; results live in PostgreSQL and Redis, not in Celery.
"""

from __future__ import annotations

from functools import lru_cache

from celery import Celery

from app.core.config import Settings, get_settings

RECOMMENDATION_QUEUE = "recommendations"
RUN_RECOMMENDATION = "app.workers.tasks.recommendation.run_recommendation"


def create_celery(settings: Settings) -> Celery:
    app = Celery("tsa", broker=settings.redis.broker_url(), set_as_current=False)
    app.conf.update(
        include=["app.workers.tasks.recommendation"],
        task_ignore_result=True,
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        worker_prefetch_multiplier=1,
        task_serializer="json",
        accept_content=["json"],
        task_default_queue=RECOMMENDATION_QUEUE,
        task_routes={RUN_RECOMMENDATION: {"queue": RECOMMENDATION_QUEUE}},
        broker_connection_retry_on_startup=True,
        worker_hijack_root_logger=False,
        # structlog writes JSON to stdout; Celery's stdout proxy would loop it back into logging.
        worker_redirect_stdouts=False,
        worker_send_task_events=False,
    )
    return app


@lru_cache
def get_celery() -> Celery:
    celery = create_celery(get_settings())
    # Registers the tasks on this app (they are declared with shared_task).
    from app.workers.tasks import recommendation  # noqa: F401

    return celery


def __getattr__(name: str) -> Celery:
    if name == "celery_app":
        return get_celery()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
