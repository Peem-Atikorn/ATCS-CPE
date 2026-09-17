"""Per-process resources for Celery tasks (D-20, D-50).

Tasks are synchronous; each worker process keeps one event loop (asyncio.Runner) so the
database pool, Redis clients and HTTP client created on first use can be reused.
"""

from __future__ import annotations

import asyncio
import contextvars
from dataclasses import dataclass
from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.clock import SystemClock
from app.core.config import Settings, get_settings
from app.infrastructure.agent.factory import build_agent_client
from app.infrastructure.db.repositories.recommendations import SqlRecommendationRepository
from app.infrastructure.db.session import create_engine, create_session_factory
from app.infrastructure.redis.cache import RedisRecommendationCache
from app.infrastructure.redis.clients import RedisClients, create_redis_clients
from app.infrastructure.redis.job_state import RedisJobStateStore
from app.infrastructure.redis.keys import RedisKeys
from app.infrastructure.redis.slots import RedisSlotLimiter
from app.services.agent_run_service import AgentRunService


@dataclass
class WorkerResources:
    engine: AsyncEngine
    redis: RedisClients
    http: httpx.AsyncClient
    service: AgentRunService

    async def aclose(self) -> None:
        await self.http.aclose()
        await self.redis.aclose()
        await self.engine.dispose()


def build_worker_resources(settings: Settings) -> WorkerResources:
    engine = create_engine(settings.db)
    redis = create_redis_clients(settings.redis)
    keys = RedisKeys(settings.app.app_env.value)
    http = httpx.AsyncClient(timeout=httpx.Timeout(5.0, connect=2.0))
    service = AgentRunService(
        repository=SqlRecommendationRepository(create_session_factory(engine)),
        agent=build_agent_client(settings, http, redis.core, keys),
        job_state=RedisJobStateStore(
            redis.core, keys, ttl_seconds=settings.jobs.job_result_ttl_seconds
        ),
        slots=RedisSlotLimiter(redis.core),
        cache=RedisRecommendationCache(redis.cache, keys),
        keys=keys,
        settings=settings,
        clock=SystemClock(),
    )
    return WorkerResources(engine, redis, http, service)


class WorkerRuntime:
    def __init__(self) -> None:
        self._runner: asyncio.Runner | None = None
        self._resources: WorkerResources | None = None

    def run_recommendation(self, job_id: UUID) -> str | None:
        if self._runner is None:
            self._runner = asyncio.Runner()
        # Runner.run() would otherwise reuse the context of its first call, so the
        # correlation id and log context of an earlier task would leak into this one.
        return self._runner.run(self._run(job_id), context=contextvars.copy_context())

    async def _run(self, job_id: UUID) -> str | None:
        if self._resources is None:
            self._resources = build_worker_resources(get_settings())
        status = await self._resources.service.run(job_id)
        return status.value if status is not None else None

    def close(self) -> None:
        if self._runner is None:
            return
        if self._resources is not None:
            self._runner.run(self._resources.aclose())
            self._resources = None
        self._runner.close()
        self._runner = None


runtime = WorkerRuntime()
