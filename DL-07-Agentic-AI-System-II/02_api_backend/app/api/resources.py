"""Long-lived clients shared by every request (created in the app lifespan)."""

from __future__ import annotations

from dataclasses import dataclass

import httpx
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from starlette.requests import HTTPConnection

from app.core.config import Settings
from app.core.security import TokenVerifier, build_token_verifier
from app.infrastructure.agent.client import AgentClient
from app.infrastructure.agent.factory import build_agent_client
from app.infrastructure.db.session import create_engine, create_session_factory
from app.infrastructure.queue import CeleryJobQueue
from app.infrastructure.redis.cache import RedisRecommendationCache
from app.infrastructure.redis.clients import RedisClients, create_redis_clients
from app.infrastructure.redis.idempotency_store import IdempotencyStore, RedisIdempotencyStore
from app.infrastructure.redis.job_state import RedisJobStateStore
from app.infrastructure.redis.keys import RedisKeys
from app.infrastructure.redis.rate_limiter import RateLimiter, RedisRateLimiter
from app.infrastructure.redis.slots import RedisSlotLimiter, SlotLimiter
from app.infrastructure.redis.tickets import RedisTicketStore
from app.infrastructure.redis.user_data import RedisUserData
from app.services.ports import CachePort, JobQueue, JobStatePort, TicketPort, UserDataPort
from app.workers.celery_app import create_celery


@dataclass
class AppResources:
    settings: Settings
    keys: RedisKeys
    token_verifier: TokenVerifier
    rate_limiter: RateLimiter
    idempotency: IdempotencyStore
    agent: AgentClient | None = None
    redis: RedisClients | None = None
    http: httpx.AsyncClient | None = None
    engine: AsyncEngine | None = None
    sessions: async_sessionmaker[AsyncSession] | None = None
    job_state: JobStatePort | None = None
    slots: SlotLimiter | None = None
    tickets: TicketPort | None = None
    cache: CachePort | None = None
    queue: JobQueue | None = None
    user_data: UserDataPort | None = None

    async def aclose(self) -> None:
        if self.http is not None:
            await self.http.aclose()
        if self.redis is not None:
            await self.redis.aclose()
        if self.engine is not None:
            await self.engine.dispose()


def build_resources(settings: Settings) -> AppResources:
    http = httpx.AsyncClient(timeout=httpx.Timeout(5.0, connect=2.0))
    redis = create_redis_clients(settings.redis)
    keys = RedisKeys(settings.app.app_env.value)
    engine = create_engine(settings.db)
    return AppResources(
        settings=settings,
        keys=keys,
        token_verifier=build_token_verifier(settings.auth, http),
        rate_limiter=RedisRateLimiter(redis.core),
        idempotency=RedisIdempotencyStore(redis.core),
        agent=build_agent_client(settings, http, redis.core, keys),
        redis=redis,
        http=http,
        engine=engine,
        sessions=create_session_factory(engine),
        job_state=RedisJobStateStore(
            redis.core, keys, ttl_seconds=settings.jobs.job_result_ttl_seconds
        ),
        slots=RedisSlotLimiter(redis.core),
        tickets=RedisTicketStore(redis.core, keys),
        cache=RedisRecommendationCache(redis.cache, keys),
        queue=CeleryJobQueue(create_celery(settings)),
        user_data=RedisUserData(redis.core, keys),
    )


def get_resources(conn: HTTPConnection) -> AppResources:
    resources: AppResources = conn.app.state.resources
    return resources
