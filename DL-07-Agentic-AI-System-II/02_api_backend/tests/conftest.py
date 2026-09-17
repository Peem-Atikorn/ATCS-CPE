from __future__ import annotations

from collections.abc import AsyncIterator, Iterator

import httpx
import pytest
from fastapi import FastAPI

from app.core.config import Settings, get_settings
from app.main import create_app

REQUIRED_ENV = {
    "APP_ENV": "test",
    "DATABASE_URL": "postgresql+asyncpg://tsa:tsa@localhost:5432/tsa_test",
    "REDIS_URL": "redis://localhost:6379/0",
    "JWT_ISSUER": "http://testserver/dev-issuer",
    "JWT_AUDIENCE": "travel-safety-api",
    "AGENT_SERVICE_URL": "http://mock-agent:8010",
    "CORS_ALLOWED_ORIGINS": "http://localhost:3000",
    "LOG_JSON": "true",
}


@pytest.fixture(autouse=True)
def env(
    monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory
) -> Iterator[None]:
    # Run from an empty directory so a developer's local .env never leaks into tests.
    monkeypatch.chdir(tmp_path_factory.mktemp("cwd"))
    for key, value in REQUIRED_ENV.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def settings() -> Settings:
    return Settings()


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    return create_app(settings)


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c
