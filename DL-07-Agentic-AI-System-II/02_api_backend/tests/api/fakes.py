"""Fake application services for HTTP-layer tests."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.core.errors import AppError, ErrorCode
from app.core.ids import new_id
from app.domain.enums import JobStage, JobStatus, JobType, RecommendationStatus
from app.domain.errors import DomainError
from app.infrastructure.redis.job_state import JobEvent
from app.services.ports import JobRecord, RecommendationRecord, UserRef
from app.services.recommendation_service import CreateOutcome, CreateRecommendation

T0 = datetime(2026, 9, 17, 8, 0, tzinfo=UTC)
USER = UserRef(new_id(), "pseudo", "th", None)


def payload(**changes: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "status": "completed",
        "valid_until": "2026-09-17T08:08:00Z",
        "language": "en",
        "risk": {"level": "LOW", "score": 0.12, "confidence": 0.9, "factors": []},
        "recommendation": {
            "type": "TRAVEL_NORMALLY",
            "summary": "Conditions are safe for your trip.",
            "reasons": ["No active warnings on the route."],
            "suggested_departure_time": None,
        },
        "routes": {
            "primary": {
                "route_id": "r-primary",
                "label": "Train",
                "travel_modes": ["TRAIN"],
                "distance_km": 661.0,
                "duration_minutes": 690.0,
                "risk_level": "LOW",
                "geometry": {"type": "LineString", "coordinates": [[100.5, 13.7], [98.9, 18.7]]},
                "legs": [
                    {
                        "mode": "TRAIN",
                        "from": "Krung Thep Aphiwat",
                        "to": "Chiang Mai",
                        "departure_at": None,
                        "arrival_at": None,
                        "operator": "SRT",
                        "service_status": "on_time",
                    }
                ],
                "restrictions": [],
                "tips": [],
            },
            "alternatives": [],
        },
        "hazards": [],
        "emergency_instructions": None,
        "sources": [
            {
                "source_id": "src-weather",
                "name": "TMD",
                "category": "WEATHER",
                "url": "https://www.tmd.go.th",
                "retrieved_at": "2026-09-17T07:59:00Z",
            }
        ],
        "data_freshness": {
            "overall_is_stale": False,
            "items": [
                {
                    "category": "WEATHER",
                    "updated_at": "2026-09-17T07:40:00Z",
                    "age_seconds": 1200,
                    "is_stale": False,
                }
            ],
        },
        "service_status": {"weather": "ok", "disaster": "ok"},
        "clarification": None,
        "warnings": [],
        "versions": {"api": "1.0.0", "agent": "a", "risk_model": "r", "prompt": "p"},
        "disclaimer": "Follow official announcements.",
    }
    body.update(changes)
    return body


def record(
    status: RecommendationStatus = RecommendationStatus.COMPLETED, **changes: Any
) -> RecommendationRecord:
    values: dict[str, Any] = {
        "id": new_id(),
        "user_id": USER.id,
        "request_id": new_id(),
        "conversation_id": new_id(),
        "status": status,
        "payload": payload() if status is not RecommendationStatus.PROCESSING else None,
        "error_code": None,
        "created_at": T0,
        "job_id": None,
    }
    values.update(changes)
    return RecommendationRecord(**values)


def job(**changes: Any) -> JobRecord:
    values: dict[str, Any] = {
        "id": new_id(),
        "user_id": USER.id,
        "type": JobType.RECOMMENDATION,
        "status": JobStatus.RUNNING,
        "stage": JobStage.ASSESSING_RISK,
        "progress": 60,
        "recommendation_id": new_id(),
        "error_code": None,
        "created_at": T0,
        "updated_at": T0,
    }
    values.update(changes)
    return JobRecord(**values)


@dataclass
class FakeRecommendations:
    outcome: CreateOutcome | Exception | None = None
    records: dict[UUID, RecommendationRecord] = field(default_factory=dict)
    commands: list[CreateRecommendation] = field(default_factory=list)

    async def create(self, user: UserRef, command: CreateRecommendation) -> CreateOutcome:
        self.commands.append(command)
        if isinstance(self.outcome, AppError | DomainError):
            raise self.outcome
        assert self.outcome is not None
        assert not isinstance(self.outcome, Exception)
        return self.outcome

    async def get(self, user: UserRef, recommendation_id: UUID) -> RecommendationRecord:
        found = self.records.get(recommendation_id)
        if found is None or found.user_id != user.id:
            raise AppError(ErrorCode.NOT_FOUND)
        return found


@dataclass
class FakeJobs:
    jobs: dict[UUID, JobRecord] = field(default_factory=dict)
    events: list[JobEvent | None] = field(default_factory=list)
    tickets: dict[str, tuple[UUID, UUID]] = field(default_factory=dict)
    closed: list[str] = field(default_factory=list)
    last_event_ids: list[str | None] = field(default_factory=list)
    hang: bool = False

    async def get(self, user_id: UUID, job_id: UUID) -> JobRecord:
        found = self.jobs.get(job_id)
        if found is None or found.user_id != user_id:
            raise AppError(ErrorCode.NOT_FOUND)
        return found

    async def issue_ticket(self, user_id: UUID, job_id: UUID) -> tuple[str, int]:
        await self.get(user_id, job_id)
        ticket = f"ticket-{len(self.tickets)}"
        self.tickets[ticket] = (user_id, job_id)
        return ticket, 60

    async def redeem_ticket(self, ticket: str, job_id: UUID) -> UUID:
        found = self.tickets.pop(ticket, None)
        if found is None or found[1] != job_id:
            raise AppError(ErrorCode.UNAUTHENTICATED)
        return found[0]

    async def open_stream(self, user_id: UUID, job_id: UUID) -> tuple[JobRecord, str]:
        return await self.get(user_id, job_id), "conn-1"

    async def close_stream(self, user_id: UUID, connection_id: str) -> None:
        await asyncio.sleep(0)  # a real await point, like the Redis call
        self.closed.append(connection_id)

    async def stream(
        self,
        user_id: UUID,
        job: JobRecord,
        connection_id: str,
        *,
        last_event_id: str | None,
        disconnected: Callable[[], Awaitable[bool]] | None = None,
    ) -> AsyncIterator[JobEvent | None]:
        self.last_event_ids.append(last_event_id)
        for event in self.events:
            yield event
        if self.hang:
            await asyncio.Event().wait()


class FakeUsers:
    async def resolve(self, principal: object) -> UserRef:
        return USER
