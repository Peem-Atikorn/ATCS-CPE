"""Operational endpoints. /ready and /metrics are added in step 5.10."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["ops"])


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


@router.get("/health", response_model=HealthResponse, summary="Liveness probe")
async def health() -> HealthResponse:
    # Liveness only: never check dependencies here, or a DB outage restarts every pod.
    return HealthResponse()
