"""E-01 POST and E-03 GET /v1/travel/recommendations (docs/02_api_spec.md section 5)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from fastapi.responses import JSONResponse

from app.api.auth import recommend_rate_limit, require_scopes
from app.api.deps import get_current_user, get_recommendation_service
from app.api.idempotency import IdempotentRoute
from app.core.ids import current_correlation_id, current_request_id, new_id
from app.core.security import Scope
from app.domain.enums import RequestMode
from app.schemas.v1.travel import JobAccepted, RecommendationResponse, TravelRequest
from app.services.ports import UserRef
from app.services.recommendation_service import (
    Accepted,
    CreateRecommendation,
    RecommendationService,
)

router = APIRouter(
    prefix="/travel/recommendations", tags=["recommendations"], route_class=IdempotentRoute
)


def _json(
    model: RecommendationResponse | JobAccepted, status: int, response: Response
) -> JSONResponse:
    result = JSONResponse(model.model_dump(mode="json", by_alias=True), status_code=status)
    # Headers set by dependencies (rate limit) are not merged into a returned response.
    for name, value in response.headers.items():
        if name.lower().startswith("ratelimit-"):
            result.headers[name] = value
    return result


@router.post(
    "",
    summary="Ask for a travel safety recommendation",
    status_code=200,
    response_model=RecommendationResponse,
    responses={202: {"model": JobAccepted, "description": "Still running; follow the job"}},
    dependencies=[Depends(require_scopes(Scope.TRAVEL_WRITE)), Depends(recommend_rate_limit)],
)
async def create_recommendation(
    body: TravelRequest,
    request: Request,
    response: Response,
    mode: RequestMode = Query(default=RequestMode.AUTO),
    accept_language: str | None = Header(default=None),
    user: UserRef = Depends(get_current_user),
    service: RecommendationService = Depends(get_recommendation_service),
) -> JSONResponse:
    command = CreateRecommendation(
        input=body.to_domain(accept_language),
        mode=mode,
        conversation_id=body.conversation_id,
        trip_id=body.trip_id,
        correlation_id=current_correlation_id() or current_request_id() or str(new_id()),
    )
    outcome = await service.create(user, command)
    if isinstance(outcome, Accepted):
        accepted = JobAccepted.build(
            outcome.job_id, outcome.recommendation_id, outcome.conversation_id
        )
        result = _json(accepted, 202, response)
        result.headers["Location"] = accepted.status_url
        return result
    return _json(RecommendationResponse.from_record(outcome.record), 200, response)


@router.get(
    "/{recommendation_id}",
    summary="Get a recommendation",
    response_model=RecommendationResponse,
    dependencies=[Depends(require_scopes(Scope.TRAVEL_READ))],
)
async def get_recommendation(
    recommendation_id: UUID,
    user: UserRef = Depends(get_current_user),
    service: RecommendationService = Depends(get_recommendation_service),
) -> RecommendationResponse:
    return RecommendationResponse.from_record(await service.get(user, recommendation_id))
