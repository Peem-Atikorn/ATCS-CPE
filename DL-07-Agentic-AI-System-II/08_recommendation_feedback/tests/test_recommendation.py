"""
Unit tests that do NOT require a running Postgres/Redis — safe to run with
plain `pytest` on a laptop, in CI, or inside the app container.

For tests against the real database (via docker compose), see
tests/test_db_integration.py, which is skipped automatically if
DATABASE_URL is unreachable.
"""

import asyncio

import pytest

from app.live_update import AlertEvent, FakeRedis, LiveUpdateBroker
from app.mock_data import ALL_SCENARIOS
from app.schema import RecommendationResponse, RiskLevel
from app.feedback import classify_free_text, FeedbackCategory


# ---------------------------------------------------------------------------
# Schema / fixture snapshot tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("scenario_name", list(ALL_SCENARIOS.keys()))
def test_mock_scenario_matches_schema(scenario_name):
    scenario = ALL_SCENARIOS[scenario_name]
    assert isinstance(scenario, RecommendationResponse)
    dumped = scenario.model_dump_json()
    restored = RecommendationResponse.model_validate_json(dumped)
    assert restored == scenario


def test_expires_at_after_fetched_at_is_enforced():
    with pytest.raises(Exception):
        ALL_SCENARIOS["travel_normally"].model_copy(
            update={"expires_at": ALL_SCENARIOS["travel_normally"].fetched_at}
        )


def test_emergency_scenario_has_contacts_and_instructions():
    e = ALL_SCENARIOS["emergency_instructions"]
    assert e.action_code.value == "EMERGENCY_INSTRUCTIONS"
    assert len(e.emergency_instructions) > 0
    assert len(e.official_contacts) > 0


def test_change_route_scenario_has_waypoints_for_map_rendering():
    r = ALL_SCENARIOS["change_route"]
    assert len(r.primary_route.waypoints) > 0
    assert len(r.alternative_routes[0].waypoints) > 0


def test_confidence_may_be_null_when_only_categorical_level_is_known():
    """
    Mirrors what 03_travel_ai_agent forwards today: 07 only emits a
    categorical confidence (LOW/MEDIUM/HIGH), so the numeric field is
    null until the team agrees on a 0-1 scale. The schema must accept
    this instead of rejecting the payload.
    """
    r = ALL_SCENARIOS["delay_travel"]
    assert r.confidence is None
    assert r.confidence_level is not None

    # Round-trips through JSON the same as every other fixture.
    restored = RecommendationResponse.model_validate_json(r.model_dump_json())
    assert restored.confidence is None
    assert restored.confidence_level == r.confidence_level


# ---------------------------------------------------------------------------
# Feedback classification (pure function, no DB)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "comment,expected",
    [
        ("This felt unsafe and dangerous", FeedbackCategory.UNSAFE),
        ("The info was outdated", FeedbackCategory.STALE),
        ("The route suggestion was wrong", FeedbackCategory.ROUTE_ISSUE),
        ("Thanks, worked great", FeedbackCategory.HELPFUL),
    ],
)
def test_classify_free_text(comment, expected):
    assert classify_free_text(comment) == expected


# ---------------------------------------------------------------------------
# Live update: consent, dedup, cooldown, severity override (FakeRedis only)
# ---------------------------------------------------------------------------

def test_no_consent_blocks_send():
    broker = LiveUpdateBroker(cooldown_seconds=60, redis_client=FakeRedis())
    event = AlertEvent("user-1", "req-1", RiskLevel.HIGH, "Alert")
    sent = asyncio.run(broker.publish(event))
    assert sent is False


def test_cooldown_suppresses_same_severity_repeat():
    broker = LiveUpdateBroker(cooldown_seconds=300, redis_client=FakeRedis())
    broker.grant_consent("user-1")
    e1 = AlertEvent("user-1", "req-1", RiskLevel.MODERATE, "Rain")
    e2 = AlertEvent("user-1", "req-1", RiskLevel.MODERATE, "Still rain", timestamp=e1.timestamp + 5)

    assert asyncio.run(broker.publish(e1)) is True
    assert asyncio.run(broker.publish(e2)) is False


def test_severity_increase_overrides_cooldown():
    broker = LiveUpdateBroker(cooldown_seconds=300, redis_client=FakeRedis())
    broker.grant_consent("user-1")
    e1 = AlertEvent("user-1", "req-1", RiskLevel.MODERATE, "Rain")
    e2 = AlertEvent("user-1", "req-1", RiskLevel.CRITICAL, "Flash flood", timestamp=e1.timestamp + 5)

    assert asyncio.run(broker.publish(e1)) is True
    assert asyncio.run(broker.publish(e2)) is True
