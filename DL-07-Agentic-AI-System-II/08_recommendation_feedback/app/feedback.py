"""
Feedback handling — classification and safety escalation, backed by
PostgreSQL (app/db.py) instead of in-memory lists.

Rules encoded here (from 02_step.txt / 03_process.txt):
- Explicit user feedback is stored separately from automatic telemetry.
- UNSAFE / INCORRECT reports go to a human safety-review queue.
- Reviewed + approved feedback may be used for evaluation/retraining.
  Unreviewed feedback must NEVER be used for that.
"""

from __future__ import annotations

import structlog

from app import db
from app.schema import FeedbackCategory, FeedbackSubmission

logger = structlog.get_logger("feedback")

ESCALATE_TO_SAFETY_REVIEW = {FeedbackCategory.UNSAFE, FeedbackCategory.INCORRECT}


async def submit_feedback(feedback: FeedbackSubmission) -> bool:
    """Persists the feedback; returns True if it was escalated to safety review."""
    escalated = feedback.category in ESCALATE_TO_SAFETY_REVIEW
    await db.save_feedback(feedback, escalated=escalated)
    if escalated:
        logger.warning(
            "safety_review_enqueued",
            request_id=feedback.request_id,
            category=feedback.category.value,
        )
    return escalated


async def mark_reviewed(request_id: str, reviewer: str, approve_for_training: bool = True) -> None:
    """Called by the human safety-review process once a report is cleared."""
    await db.mark_reviewed(request_id, reviewer, approve_for_training)


async def pending_safety_review() -> list[dict]:
    return await db.fetch_pending_safety_review()


async def reviewed_for_training() -> list[dict]:
    """The ONLY feedback set that may be used for evaluation/retraining."""
    return await db.fetch_reviewed_for_training()


def classify_free_text(comment: str) -> FeedbackCategory:
    """
    Lightweight keyword-based fallback classifier for when the caller (UI)
    does not already supply a category. Prefer the UI's explicit category
    when available — this is only a safety net.
    """
    text_lower = comment.lower()
    if any(w in text_lower for w in ["danger", "unsafe", "injur", "accident"]):
        return FeedbackCategory.UNSAFE
    if any(w in text_lower for w in ["wrong", "incorrect", "not accurate"]):
        return FeedbackCategory.INCORRECT
    if any(w in text_lower for w in ["old", "outdated", "stale", "expired"]):
        return FeedbackCategory.STALE
    if any(w in text_lower for w in ["route", "path", "detour"]):
        return FeedbackCategory.ROUTE_ISSUE
    if any(w in text_lower for w in ["source", "citation", "reference"]):
        return FeedbackCategory.SOURCE_ISSUE
    return FeedbackCategory.HELPFUL
