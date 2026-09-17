"""Assemble application services for a request (the only api module that sees infrastructure)."""

from __future__ import annotations

from fastapi import Depends, Request

from app.api.auth import get_principal
from app.api.resources import AppResources, get_resources
from app.core.clock import SystemClock
from app.core.errors import AppError, ErrorCode
from app.core.logging import get_logger
from app.core.security import Principal
from app.infrastructure.db.repositories.conversations import SqlConversationRepository
from app.infrastructure.db.repositories.recommendations import SqlRecommendationRepository
from app.services.conversation_service import ConversationService
from app.services.job_service import JobService
from app.services.ports import UserRef
from app.services.recommendation_service import RecommendationService
from app.services.user_service import UserService

log = get_logger(__name__)

_CLOCK = SystemClock()


def _require[T](value: T | None, name: str) -> T:
    if value is None:
        # Wiring error: the resource was not created at startup.
        log.error("resource_missing", resource=name)
        raise AppError(ErrorCode.DEPENDENCY_UNAVAILABLE, retry_after=5)
    return value


def _repository(resources: AppResources) -> SqlRecommendationRepository:
    return SqlRecommendationRepository(_require(resources.sessions, "sessions"))


def get_user_service(request: Request) -> UserService:
    resources = get_resources(request)
    return UserService(_repository(resources), resources.settings.secrets.pseudonym_secret)


async def get_current_user(
    request: Request,
    principal: Principal = Depends(get_principal),
    users: UserService = Depends(get_user_service),
) -> UserRef:
    cached: UserRef | None = getattr(request.state, "user", None)
    if cached is None:
        cached = await users.resolve(principal)
        request.state.user = cached
    return cached


def get_recommendation_service(request: Request) -> RecommendationService:
    resources = get_resources(request)
    return RecommendationService(
        repository=_repository(resources),
        job_state=_require(resources.job_state, "job_state"),
        slots=_require(resources.slots, "slots"),
        cache=_require(resources.cache, "cache"),
        queue=_require(resources.queue, "queue"),
        keys=resources.keys,
        settings=resources.settings,
        clock=_CLOCK,
    )


def get_job_service(request: Request) -> JobService:
    resources = get_resources(request)
    return JobService(
        repository=_repository(resources),
        job_state=_require(resources.job_state, "job_state"),
        slots=_require(resources.slots, "slots"),
        tickets=_require(resources.tickets, "tickets"),
        keys=resources.keys,
        settings=resources.settings,
        clock=_CLOCK,
    )


def get_conversation_service(request: Request) -> ConversationService:
    resources = get_resources(request)
    return ConversationService(
        conversations=SqlConversationRepository(_require(resources.sessions, "sessions")),
        recommendations=get_recommendation_service(request),
        settings=resources.settings,
        clock=_CLOCK,
    )
