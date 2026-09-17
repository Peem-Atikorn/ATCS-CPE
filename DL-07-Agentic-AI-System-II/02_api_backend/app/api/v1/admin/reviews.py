"""Safety review queue for reported feedback (docs/02_api_spec.md section 8.2, D-69)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request

from app.api.audit import client_ip_hash, correlation_id
from app.api.auth import require_scopes
from app.api.deps import get_feedback_service
from app.core.security import Principal, Scope
from app.domain.enums import ReviewStatus
from app.schemas.v1.feedback import ReviewPage, ReviewQueueItem, ReviewResponse, ReviewUpdate
from app.services.feedback_service import FeedbackService

router = APIRouter(prefix="/admin/feedback/reviews", tags=["admin"])

_reviewer = require_scopes(Scope.SAFETY_REVIEW)


@router.get("", summary="Feedback waiting for review, oldest first", response_model=ReviewPage)
async def list_reviews(
    request: Request,
    status: ReviewStatus = Query(default=ReviewStatus.PENDING),
    limit: int | None = Query(default=None),
    cursor: str | None = Query(default=None, max_length=200),
    principal: Principal = Depends(_reviewer),
    service: FeedbackService = Depends(get_feedback_service),
) -> ReviewPage:
    page = await service.reviews(
        principal.subject,
        status=status,
        limit=limit,
        cursor=cursor,
        correlation_id=correlation_id(),
        ip_hash=client_ip_hash(request),
    )
    return ReviewPage(
        items=[ReviewQueueItem.from_item(item) for item in page.items],
        next_cursor=page.next_cursor,
    )


@router.patch(
    "/{feedback_id}", summary="Approve or reject reported feedback", response_model=ReviewResponse
)
async def review_feedback(
    feedback_id: UUID,
    body: ReviewUpdate,
    request: Request,
    principal: Principal = Depends(_reviewer),
    service: FeedbackService = Depends(get_feedback_service),
) -> ReviewResponse:
    record = await service.review(
        principal.subject,
        feedback_id,
        decision=body.status,
        note=body.note,
        correlation_id=correlation_id(),
        ip_hash=client_ip_hash(request),
    )
    return ReviewResponse.from_record(record)
