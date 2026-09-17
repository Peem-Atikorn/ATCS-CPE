"""All /v1 routers."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import conversations, jobs, recommendations

router = APIRouter(prefix="/v1")
router.include_router(recommendations.router)
router.include_router(jobs.router)
router.include_router(conversations.router)
