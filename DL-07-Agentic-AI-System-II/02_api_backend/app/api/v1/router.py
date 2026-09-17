"""All /v1 routers."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import conversations, feedback, jobs, recommendations, trips
from app.api.v1.admin import reviews

router = APIRouter(prefix="/v1")
router.include_router(recommendations.router)
router.include_router(jobs.router)
router.include_router(conversations.router)
router.include_router(trips.router)
router.include_router(feedback.router)
router.include_router(reviews.router)
