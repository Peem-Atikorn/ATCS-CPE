"""Celery wiring: configuration, the task entry point and the enqueue adapter."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import pytest

from app.core.config import Settings
from app.core.ids import correlation_id_var, new_id
from app.infrastructure.queue import CeleryJobQueue
from app.workers import celery_app as celery_module
from app.workers.celery_app import RECOMMENDATION_QUEUE, RUN_RECOMMENDATION, create_celery
from app.workers.runtime import WorkerRuntime
from app.workers.tasks import recommendation as task_module


def test_celery_configuration(settings: Settings) -> None:
    app = create_celery(settings)

    conf = app.conf
    assert conf.broker_url == "redis://localhost:6379/2"
    assert conf.task_acks_late is True
    assert conf.task_reject_on_worker_lost is True
    assert conf.worker_prefetch_multiplier == 1
    assert conf.task_ignore_result is True
    assert conf.accept_content == ["json"]
    assert conf.task_default_queue == RECOMMENDATION_QUEUE
    assert conf.task_routes[RUN_RECOMMENDATION] == {"queue": RECOMMENDATION_QUEUE}
    # Our JSON logs go to the real stdout; the redirect proxy would swallow them.
    assert conf.worker_redirect_stdouts is False


def test_module_exposes_a_configured_app_with_the_task() -> None:
    celery_module.get_celery.cache_clear()

    app = celery_module.celery_app

    assert RUN_RECOMMENDATION in app.tasks
    with pytest.raises(AttributeError):
        _ = celery_module.not_there


class FakeRuntime:
    def __init__(self) -> None:
        self.calls: list[tuple[UUID, str | None]] = []

    def run_recommendation(self, job_id: UUID) -> str | None:
        self.calls.append((job_id, correlation_id_var.get()))
        return "succeeded"


def test_task_runs_the_job_with_its_correlation_id(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime = FakeRuntime()
    monkeypatch.setattr(task_module, "runtime", runtime)
    job_id = new_id()

    result = task_module.run_recommendation(str(job_id), correlation_id="corr-42")

    assert result == "succeeded"
    assert runtime.calls == [(job_id, "corr-42")]
    assert correlation_id_var.get() is None


@pytest.mark.parametrize("correlation_id", [None, "bad id with spaces"])
def test_unsafe_correlation_id_is_replaced(
    monkeypatch: pytest.MonkeyPatch, correlation_id: str | None
) -> None:
    runtime = FakeRuntime()
    monkeypatch.setattr(task_module, "runtime", runtime)
    job_id = new_id()

    task_module.run_recommendation(str(job_id), correlation_id=correlation_id)

    assert runtime.calls[0][1] == str(job_id)


def test_invalid_job_id_is_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime = FakeRuntime()
    monkeypatch.setattr(task_module, "runtime", runtime)

    assert task_module.run_recommendation("not-a-uuid") is None
    assert runtime.calls == []


class FakeCelery:
    def __init__(self) -> None:
        self.sent: list[tuple[str, dict[str, Any]]] = []

    def send_task(self, name: str, **options: Any) -> Any:
        self.sent.append((name, options))
        return type("Result", (), {"id": "task-123"})()


async def test_queue_sends_only_ids() -> None:
    celery = FakeCelery()
    job_id = new_id()

    task_id = await CeleryJobQueue(celery).enqueue_recommendation(  # type: ignore[arg-type]
        job_id, correlation_id="corr-1"
    )

    assert task_id == "task-123"
    name, options = celery.sent[0]
    assert name == RUN_RECOMMENDATION
    assert options["kwargs"] == {"job_id": str(job_id), "correlation_id": "corr-1"}
    assert options["queue"] == RECOMMENDATION_QUEUE
    assert options["retry_policy"]["max_retries"] <= 3


def test_runtime_runs_each_job_in_the_callers_context(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime = WorkerRuntime()
    seen: list[str | None] = []

    async def fake_run(job_id: UUID) -> str | None:
        seen.append(correlation_id_var.get())
        return None

    monkeypatch.setattr(runtime, "_run", fake_run)
    try:
        for value in ("first", "second"):
            token = correlation_id_var.set(value)
            try:
                runtime.run_recommendation(new_id())
            finally:
                correlation_id_var.reset(token)
    finally:
        runtime.close()

    assert seen == ["first", "second"]
