"""Long-lived clients shared by every request (created in the app lifespan)."""

from __future__ import annotations

from dataclasses import dataclass

import httpx
from starlette.requests import HTTPConnection

from app.core.config import Settings
from app.core.security import TokenVerifier, build_token_verifier
from app.infrastructure.redis.clients import RedisClients, create_redis_clients
from app.infrastructure.redis.idempotency_store import IdempotencyStore, RedisIdempotencyStore
from app.infrastructure.redis.keys import RedisKeys
from app.infrastructure.redis.rate_limiter import RateLimiter, RedisRateLimiter


@dataclass
class AppResources:
    settings: Settings
    keys: RedisKeys
    token_verifier: TokenVerifier
    rate_limiter: RateLimiter
    idempotency: IdempotencyStore
    redis: RedisClients | None = None
    http: httpx.AsyncClient | None = None

    async def aclose(self) -> None:
        if self.http is not None:
            await self.http.aclose()
        if self.redis is not None:
            await self.redis.aclose()


def build_resources(settings: Settings) -> AppResources:
    http = httpx.AsyncClient(timeout=httpx.Timeout(5.0, connect=2.0))
    redis = create_redis_clients(settings.redis)
    return AppResources(
        settings=settings,
        keys=RedisKeys(settings.app.app_env.value),
        token_verifier=build_token_verifier(settings.auth, http),
        rate_limiter=RedisRateLimiter(redis.core),
        idempotency=RedisIdempotencyStore(redis.core),
        redis=redis,
        http=http,
    )


def get_resources(conn: HTTPConnection) -> AppResources:
    resources: AppResources = conn.app.state.resources
    return resources
