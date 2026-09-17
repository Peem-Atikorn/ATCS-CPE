"""What the application services need from the outside world.

Services depend on these Protocols and records only; infrastructure implements them
(docs/04_project_structure.md section 2).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from app.domain.enums import (
    AgentRunStatus,
    JobStage,
    JobStatus,
    JobType,
    MessageRole,
    RecommendationStatus,
    RecommendationType,
    RequestMode,
    RequestSource,
    RiskLevel,
)
from app.domain.normalization import NormalizedTravelRequest
from app.infrastructure.agent.client import AgentCallResult
from app.infrastructure.agent.contracts import AgentRunRequest, AgentVersions, ProgressLine
from app.infrastructure.redis.job_state import JobEvent, JobSnapshot
from app.services.pagination import Cursor
from app.services.recommendation_payload import Assessment, fallback_reply

# ------------------------------------------------------------------ records


@dataclass(frozen=True, slots=True)
class UserRef:
    id: UUID
    pseudonymous_id: str
    language: str
    home_region: str | None


@dataclass(frozen=True, slots=True)
class NewRecommendation:
    user_id: UUID
    request: NormalizedTravelRequest
    mode: RequestMode
    source: RequestSource
    conversation_id: UUID | None
    trip_id: UUID | None
    cache_key: str | None
    correlation_id: str
    now: datetime
    retention_days: int
    conversation_days: int
    # Chosen by the caller so the active-job slot can be taken before the rows exist.
    job_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class CreatedRecommendation:
    request_id: UUID
    recommendation_id: UUID
    conversation_id: UUID
    job_id: UUID | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class StoredResult:
    status: RecommendationStatus
    risk_level: RiskLevel | None
    risk_score: float | None
    risk_confidence: float | None
    recommendation_type: RecommendationType | None
    payload: dict[str, Any]
    warning_codes: tuple[str, ...]
    applied_rules: tuple[str, ...]
    overall_is_stale: bool
    valid_until: datetime | None
    api_version: str
    agent_version: str | None
    risk_model_version: str | None
    prompt_version: str | None
    # Stored as the assistant message of the conversation.
    message: str | None

    @classmethod
    def from_assessment(
        cls, assessment: Assessment, *, versions: AgentVersions, api_version: str
    ) -> StoredResult:
        clarification = assessment.payload.get("clarification") or {}
        return cls(
            status=assessment.status,
            risk_level=assessment.risk_level,
            risk_score=assessment.risk_score,
            risk_confidence=assessment.risk_confidence,
            recommendation_type=assessment.recommendation_type,
            payload=assessment.payload,
            warning_codes=assessment.warning_codes,
            applied_rules=assessment.applied_rules,
            overall_is_stale=assessment.overall_is_stale,
            valid_until=assessment.valid_until,
            api_version=api_version,
            agent_version=versions.agent,
            risk_model_version=versions.risk_model,
            prompt_version=versions.prompt,
            message=(
                assessment.summary
                or clarification.get("question")
                or fallback_reply(str(assessment.payload.get("language", "")))
            ),
        )


@dataclass(frozen=True, slots=True)
class RecommendationRecord:
    id: UUID
    user_id: UUID
    request_id: UUID
    conversation_id: UUID | None
    status: RecommendationStatus
    payload: dict[str, Any] | None
    error_code: str | None
    created_at: datetime
    job_id: UUID | None


@dataclass(frozen=True, slots=True)
class JobRecord:
    id: UUID
    user_id: UUID
    type: JobType
    status: JobStatus
    stage: JobStage
    progress: int
    recommendation_id: UUID | None
    error_code: str | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_snapshot(cls, snapshot: JobSnapshot) -> JobRecord:
        return cls(
            id=snapshot.job_id,
            user_id=snapshot.user_id,
            type=snapshot.type,
            status=snapshot.status,
            stage=snapshot.stage,
            progress=snapshot.progress,
            recommendation_id=snapshot.recommendation_id,
            error_code=snapshot.error_code,
            created_at=snapshot.created_at,
            updated_at=snapshot.updated_at,
        )


@dataclass(frozen=True, slots=True)
class RecommendationSummaryRecord:
    id: UUID
    created_at: datetime
    status: RecommendationStatus
    risk_level: RiskLevel | None
    recommendation_type: RecommendationType | None
    origin_name: str | None
    destination_name: str | None
    departure_time: datetime


@dataclass(frozen=True, slots=True)
class ConversationRecord:
    id: UUID
    user_id: UUID
    title: str | None
    language: str
    created_at: datetime
    updated_at: datetime
    last_recommendation_id: UUID | None
    message_count: int


@dataclass(frozen=True, slots=True)
class MessageRecord:
    id: UUID
    conversation_id: UUID
    role: MessageRole
    content: str
    recommendation_id: UUID | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class WorkItem:
    job_id: UUID
    attempt: int
    user: UserRef
    recommendation_id: UUID
    request_id: UUID
    conversation_id: UUID | None
    previous_recommendation_id: UUID | None
    request: NormalizedTravelRequest
    # Earlier (role, content) pairs of the conversation, oldest first.
    context: tuple[tuple[str, str], ...]
    cache_key: str | None


@dataclass(frozen=True, slots=True)
class AgentRunRecord:
    run_id: UUID
    attempt: int
    status: AgentRunStatus
    http_status: int | None
    error_code: str | None
    started_at: datetime
    finished_at: datetime
    tool_calls: int | None
    agent_version: str | None
    trace_id: str | None


@dataclass(frozen=True, slots=True)
class JobOutcome:
    status: JobStatus
    finished_at: datetime
    result: StoredResult | None
    error_code: str | None
    agent_run: AgentRunRecord | None
    conversation_days: int


# ------------------------------------------------------------------ ports


class RecommendationRepository(Protocol):
    async def get_or_create_user(
        self, issuer: str, subject: str, *, pseudonym: Callable[[UUID], str]
    ) -> UserRef: ...

    async def conversation_exists(self, user_id: UUID, conversation_id: UUID) -> bool: ...

    async def trip_exists(self, user_id: UUID, trip_id: UUID) -> bool: ...

    async def region_for(self, lat: float, lon: float) -> str | None: ...

    async def create_pending(self, new: NewRecommendation) -> CreatedRecommendation: ...

    async def create_completed(
        self, new: NewRecommendation, result: StoredResult
    ) -> CreatedRecommendation: ...

    async def set_task_id(self, job_id: UUID, task_id: str) -> None: ...

    async def fail_job(self, job_id: UUID, error_code: str, now: datetime) -> None: ...

    async def get_recommendation(
        self, user_id: UUID, recommendation_id: UUID
    ) -> RecommendationRecord | None: ...

    async def get_job(self, user_id: UUID, job_id: UUID) -> JobRecord | None: ...

    async def list_recommendations(
        self,
        user_id: UUID,
        *,
        limit: int,
        cursor: Cursor | None,
        created_from: datetime | None,
        created_to: datetime | None,
        risk_level: RiskLevel | None,
    ) -> list[RecommendationSummaryRecord]: ...

    async def start_job(
        self, job_id: UUID, now: datetime, *, context_messages: int
    ) -> WorkItem | None: ...

    async def emergency_default(self, region_code: str, language: str) -> dict[str, Any] | None: ...

    async def finish_job(self, job_id: UUID, outcome: JobOutcome) -> None: ...


class ConversationRepository(Protocol):
    """List methods return up to `limit + 1` rows (see pagination.build_page)."""

    async def create(
        self,
        user_id: UUID,
        *,
        title: str | None,
        language: str,
        now: datetime,
        retention_days: int,
    ) -> ConversationRecord: ...

    async def get(self, user_id: UUID, conversation_id: UUID) -> ConversationRecord | None: ...

    async def list_conversations(
        self, user_id: UUID, *, limit: int, cursor: Cursor | None
    ) -> list[ConversationRecord]: ...

    async def delete(self, user_id: UUID, conversation_id: UUID) -> bool: ...

    async def messages(
        self, user_id: UUID, conversation_id: UUID, *, limit: int, cursor: Cursor | None
    ) -> list[MessageRecord] | None: ...

    async def last_request(
        self, user_id: UUID, conversation_id: UUID
    ) -> NormalizedTravelRequest | None: ...

    async def reply_for(self, user_id: UUID, recommendation_id: UUID) -> MessageRecord | None: ...


ProgressCallback = Callable[[ProgressLine], Awaitable[None]]


class AgentPort(Protocol):
    async def run(
        self,
        request: AgentRunRequest,
        *,
        deadline: datetime,
        on_progress: ProgressCallback | None = None,
    ) -> AgentCallResult: ...


class JobStatePort(Protocol):
    async def create(self, snapshot: JobSnapshot) -> None: ...

    async def update(
        self,
        job_id: UUID,
        *,
        updated_at: datetime,
        status: JobStatus | None = None,
        stage: JobStage | None = None,
        progress: int | None = None,
        error_code: str | None = None,
    ) -> None: ...

    async def publish(self, job_id: UUID, event: str, data: dict[str, Any]) -> str: ...

    async def get(self, job_id: UUID) -> JobSnapshot | None: ...

    async def read(self, job_id: UUID, *, after: str, block_ms: int | None) -> list[JobEvent]: ...


class TicketPort(Protocol):
    async def issue(self, user_id: UUID, job_id: UUID, *, ttl_seconds: int) -> str: ...

    async def redeem(self, ticket: str) -> tuple[UUID, UUID] | None: ...


class CachePort(Protocol):
    async def get(self, cache_key: str) -> dict[str, Any] | None: ...

    async def put(self, cache_key: str, payload: dict[str, Any], *, ttl_seconds: int) -> None: ...


class JobQueue(Protocol):
    async def enqueue_recommendation(self, job_id: UUID, *, correlation_id: str) -> str: ...
