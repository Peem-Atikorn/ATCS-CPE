"""FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import ops
from app.api.error_handlers import register_error_handlers
from app.api.middleware.request_context import (
    CORRELATION_ID_HEADER,
    REQUEST_ID_HEADER,
    RequestContextMiddleware,
)
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging, get_logger

API_TITLE = "Travel Safety & Advisory API"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(
        level=settings.observability.log_level,
        json_output=settings.observability.log_json,
    )
    log = get_logger(__name__)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        log.info("startup", env=settings.app.app_env.value, version=settings.app.api_version)
        yield
        log.info("shutdown")

    docs = settings.app.enable_docs
    app = FastAPI(
        title=API_TITLE,
        version=settings.app.api_version,
        lifespan=lifespan,
        docs_url="/docs" if docs else None,
        redoc_url=None,
        openapi_url="/openapi.json" if docs else None,
    )
    app.state.settings = settings

    register_error_handlers(app, type_base_url=settings.app.error_type_base_url)

    # Starlette runs the last added middleware first.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.app.cors_allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "Accept-Language",
            "Idempotency-Key",
            "Last-Event-ID",
            REQUEST_ID_HEADER,
            CORRELATION_ID_HEADER,
        ],
        expose_headers=[
            REQUEST_ID_HEADER,
            CORRELATION_ID_HEADER,
            "Retry-After",
            "RateLimit-Limit",
            "RateLimit-Remaining",
            "RateLimit-Reset",
            "Idempotent-Replayed",
            "Location",
        ],
        max_age=600,
    )
    app.add_middleware(RequestContextMiddleware, type_base_url=settings.app.error_type_base_url)

    app.include_router(ops.router)
    return app
