from __future__ import annotations

import asyncio
import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path

from risk_knowledge.knowledge import retrieve_knowledge
from risk_knowledge.models import Level
from risk_knowledge.risk import assess_risk
from risk_knowledge.routing import analyze_routes
from risk_knowledge.service import RiskKnowledgeService


NOW = datetime(2026, 9, 19, 6, 0, tzinfo=UTC)


def query() -> dict:
    return {
        "run_id": "run-06-test",
        "origin": [100.0, 13.0],
        "destination": [100.2, 13.0],
        "departure_time": "2026-09-20T01:00:00Z",
        "travel_modes": ["CAR"],
        "language": "th-TH",
        "geography": "TH-10",
    }


def evidence(record_id: str, kind: str, *, severity: str = "LOW", value=None) -> dict:
    return {
        "schema_version": "canonical-record-v0.1-proposed",
        "record_id": record_id,
        "record_kind": kind,
        "status": "available",
        "source": {"name": "Synthetic test source", "authority": "Test authority"},
        "source_lineage": "https://example.org/source",
        "spatial_footprint": {"type": "Point", "coordinates": [100.05, 13.0]},
        "observed_at": "2026-09-19T05:00:00Z",
        "fetched_at": "2026-09-19T05:30:00Z",
        "expires_at": "2026-09-19T07:00:00Z",
        "freshness": "fresh",
        "severity": severity,
        "quality_flags": [],
        "value": value or {},
    }


def context() -> dict:
    coverage = {
        "current_weather": "covered",
        "weather_forecast": "covered",
        "transport_status": "covered",
        "closure": "covered",
        "disaster_event": "covered",
        "official_alert": "covered",
    }
    return {
        "feature_schema_version": "integrated-travel-v0.1-proposed",
        "run_id": "run-06-test",
        "created_at": "2026-09-19T06:00:00Z",
        "routes": [
            {
                "route_id": "primary-route",
                "label": "Primary",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[100.0, 13.0], [100.1, 13.0]],
                },
                "segments": [{
                    "start_index": 0,
                    "end_index": 1,
                    "enter_at": "2026-09-20T01:00:00Z",
                    "exit_at": "2026-09-20T01:30:00Z",
                    "matched_record_ids": {"closure": ["closure-1"]},
                    "coverage": coverage,
                }],
            },
            {
                "route_id": "alternative-route",
                "label": "Alternative",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[100.0, 13.0], [100.2, 13.0]],
                },
                "segments": [{
                    "start_index": 0,
                    "end_index": 1,
                    "enter_at": "2026-09-20T01:00:00Z",
                    "exit_at": "2026-09-20T01:50:00Z",
                    "matched_record_ids": {"weather_forecast": ["weather-1"]},
                    "coverage": coverage,
                }],
            },
        ],
        "evidence": [
            evidence("closure-1", "closure", severity="HIGH", value={"active": True}),
            evidence("weather-1", "weather_forecast", value={"rain_probability": 0.2}),
        ],
        "quality_flags": [],
        "degraded": False,
        "risk_score": None,
    }


def passage(**changes) -> dict:
    item = {
        "document_id": "ddpm-flood-1",
        "authority": "Synthetic approved authority",
        "title": "Flood safety guide",
        "url": "https://example.org/flood-guide",
        "language": "th-TH",
        "geography": ["TH-10"],
        "hazard_types": ["FLOOD"],
        "effective_at": "2026-01-01T00:00:00Z",
        "expires_at": "2027-01-01T00:00:00Z",
        "page": 4,
        "section": "Evacuation",
        "text": "FLOOD evacuation procedure from an approved synthetic test document.",
        "approved": True,
    }
    item.update(changes)
    return item


def alert() -> dict:
    return {
        "hazard_id": "flood-1",
        "hazard_type": "FLOOD",
        "severity": "HIGH",
        "title": "Flood warning",
        "level": "AVOID",
        "active": True,
    }


class RiskTests(unittest.TestCase):
    def test_official_closure_is_high_risk_override(self):
        result = assess_risk(context(), now=NOW)
        self.assertEqual(result.level, Level.HIGH)
        self.assertGreaterEqual(result.score, 0.95)
        self.assertIn("OFFICIAL_RESTRICTION", {factor.type for factor in result.factors})

    def test_missing_context_uses_conservative_degraded_result(self):
        result = assess_risk(None, now=NOW)
        self.assertEqual(result.level, Level.HIGH)
        self.assertEqual(result.confidence, Level.LOW)
        self.assertIsNone(result.score)

    def test_unknown_feature_schema_is_rejected(self):
        payload = context()
        payload["feature_schema_version"] = "unknown-v9"
        with self.assertRaisesRegex(ValueError, "unsupported feature_schema_version"):
            assess_risk(payload, now=NOW)

    def test_summary_only_context_cannot_establish_low_risk(self):
        summary = {
            "primary_route_id": "primary-route",
            "confidence": "HIGH",
            "flags": [],
            "active_restriction": False,
        }
        result = assess_risk(summary, now=NOW)
        self.assertEqual(result.level, Level.MEDIUM)
        self.assertEqual(result.confidence, Level.LOW)
        self.assertIsNone(result.score)
        self.assertIn("DATA_INCOMPLETE", {factor.type for factor in result.factors})

    def test_module_05_weather_aliases_are_scored_with_degraded_confidence(self):
        payload = context()
        payload["evidence"] = [evidence(
            "weather-05",
            "weather_forecast",
            value={
                "wind_speed_kmh": 72.0,
                "wind_speed_kph": 72.0,
                "visibility_m": 800.0,
                "visibility_km": 0.8,
                "rain_probability_percent": 80.0,
                "rain_probability": 0.8,
            },
        )]
        payload["quality_flags"] = ["partial"]
        payload["degraded"] = True
        result = assess_risk(payload, now=NOW)
        self.assertEqual(result.level, Level.HIGH)
        self.assertEqual(result.confidence, Level.MEDIUM)
        self.assertIn("WEATHER", {factor.type for factor in result.factors})

    def test_unknown_freshness_is_not_counted_as_usable_evidence(self):
        payload = context()
        payload["evidence"][1]["freshness"] = "unknown"
        payload["evidence"][1]["quality_flags"] = ["freshness_unknown"]
        payload["evidence"] = [payload["evidence"][1]]
        result = assess_risk(payload, now=NOW)
        self.assertEqual(result.confidence, Level.LOW)


class KnowledgeTests(unittest.TestCase):
    def test_retrieval_filters_expired_and_unapproved_documents(self):
        result = retrieve_knowledge(
            query(),
            [alert()],
            [
                passage(),
                passage(document_id="expired", expires_at="2026-09-18T00:00:00Z"),
                passage(document_id="unapproved", approved=False),
            ],
            now=NOW,
        )
        self.assertEqual(len(result.records), 1)
        self.assertIn("document_id=ddpm-flood-1", result.records[0].excerpt)
        self.assertIn("page=4", result.records[0].excerpt)

    def test_no_active_alert_returns_no_ungrounded_advice(self):
        inactive = alert() | {"active": False}
        result = retrieve_knowledge(query(), [inactive], [passage()], now=NOW)
        self.assertEqual(result.records, [])


class RouteTests(unittest.TestCase):
    def test_closure_blocks_primary_and_marks_alternative_safer(self):
        risk = assess_risk(context(), now=NOW)
        result = analyze_routes(query(), context(), risk, now=NOW)
        self.assertFalse(result.primary.usable)
        self.assertEqual(result.primary.risk_level, Level.HIGH)
        self.assertTrue(result.alternatives[0].usable)
        self.assertTrue(result.alternatives[0].clearly_safer)
        self.assertFalse(result.no_safe_route)

    def test_missing_context_does_not_claim_a_safe_route(self):
        result = analyze_routes(query(), None, None, now=NOW)
        self.assertFalse(result.primary.usable)
        self.assertTrue(result.no_safe_route)

    def test_partial_coverage_is_not_claimed_as_clearly_safer(self):
        payload = context()
        for status in payload["routes"][1]["segments"][0]["coverage"]:
            payload["routes"][1]["segments"][0]["coverage"][status] = "partial"
        risk = assess_risk(payload, now=NOW)
        result = analyze_routes(query(), payload, risk, now=NOW)
        self.assertTrue(result.alternatives[0].usable)
        self.assertEqual(result.alternatives[0].risk_level, Level.MEDIUM)
        self.assertFalse(result.alternatives[0].clearly_safer)


class ServiceAndContractTests(unittest.TestCase):
    def test_async_facade_runs_all_capabilities(self):
        service = RiskKnowledgeService(passages=[passage()], clock=lambda: NOW)

        async def run():
            risk_result = await service.risk(query(), context())
            knowledge_result = await service.knowledge(query(), [alert()])
            route_result = await service.routes(query(), context(), risk_result)
            return risk_result, knowledge_result, route_result

        risk_result, knowledge_result, route_result = asyncio.run(run())
        self.assertEqual(risk_result.level, Level.HIGH)
        self.assertEqual(len(knowledge_result.records), 1)
        self.assertEqual(route_result.primary.route_id, "primary-route")

    def test_outputs_validate_against_module_03_draft_contract(self):
        module_root = Path(__file__).resolve().parents[2]
        agent_root = module_root / "03_travel_ai_agent"
        sys.path.insert(0, str(agent_root))
        try:
            from travel_agent.tools.schemas import (
                KnowledgeResult as AgentKnowledgeResult,
                RiskResult as AgentRiskResult,
                RouteResult as AgentRouteResult,
            )

            risk_result = assess_risk(context(), now=NOW)
            knowledge_result = retrieve_knowledge(query(), [alert()], [passage()], now=NOW)
            route_result = analyze_routes(query(), context(), risk_result, now=NOW)
            AgentRiskResult.model_validate(risk_result.model_dump())
            AgentKnowledgeResult.model_validate(knowledge_result.model_dump())
            AgentRouteResult.model_validate(route_result.model_dump())
        finally:
            sys.path.remove(str(agent_root))


if __name__ == "__main__":
    unittest.main()
