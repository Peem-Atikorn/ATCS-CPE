from datetime import UTC, datetime, timedelta

import pytest

from travel_agent.tools.base import ToolError
from travel_agent.tools.live import LiveToolSet
from travel_agent.tools.schemas import IntegratedContext, TravelQuery

NOW = datetime(2026, 9, 21, 3, 0, tzinfo=UTC)


def query() -> TravelQuery:
    return TravelQuery(
        run_id="run-live-1",
        origin=(13.7563, 100.5018),
        destination=(12.5684, 99.9577),
        departure_time=NOW + timedelta(minutes=10),
        travel_modes=["CAR"],
    )


def canonical(kind: str, record_id: str, *, severity: str = "MEDIUM") -> dict:
    return {
        "schema_version": "canonical-record-v0.1-proposed",
        "record_id": record_id,
        "record_kind": kind,
        "status": "available",
        "source": {"name": "Real provider", "authority": None},
        "source_lineage": "https://provider.example/events?id=1",
        "spatial_footprint": {"type": "Point", "coordinates": [100.25, 13.2]},
        "observed_at": NOW.isoformat(),
        "valid_at": None,
        "issued_at": None,
        "event_time": NOW.isoformat(),
        "fetched_at": NOW.isoformat(),
        "expires_at": (NOW + timedelta(hours=1)).isoformat(),
        "severity": severity,
        "quality_flags": [],
        "value": {
            "event_type": "FL",
            "name": "Flood event",
            "description": "Provider-reported event",
            "starts_at": (NOW - timedelta(minutes=5)).isoformat(),
            "ends_at": (NOW + timedelta(minutes=30)).isoformat(),
        },
    }


def context_builder_spy(calls: list):
    def build(payload, records, *, now):
        calls.append((payload, records, now))
        return {
            "feature_schema_version": "integrated-travel-v0.1-proposed",
            "run_id": payload["run_id"],
            "created_at": now.isoformat(),
            "routes": payload["routes"],
            "evidence": records,
            "quality_flags": ["partial"],
            "degraded": True,
            "risk_score": None,
        }

    return build


@pytest.mark.asyncio
async def test_live_transport_and_disasters_feed_canonical_records_to_module_05():
    calls = []
    transport_record = canonical("transport_status", "tomtom:incident-1")
    disaster_record = canonical("disaster_event", "gdacs:FL:1:1", severity="HIGH")
    captured_transport = {}

    def fetch_transport(bbox, *, now, api_key):
        captured_transport.update(bbox=bbox, now=now, api_key=api_key)
        return [transport_record]

    tools = LiveToolSet(
        tomtom_api_key="test-key",
        clock=lambda: NOW,
        transport_fetcher=fetch_transport,
        disaster_fetcher=lambda *, now: [disaster_record],
        context_builder=context_builder_spy(calls),
    )

    transport = await tools.transport(query())
    disasters = await tools.disasters(query())
    routes = [
        {
            "route_id": "route-1",
            "label": "Route 1",
            "travel_modes": ["CAR"],
            "geometry": {
                "type": "LineString",
                "coordinates": [[100.5018, 13.7563], [99.9577, 12.5684]],
            },
            "segments": [
                {
                    "start_index": 0,
                    "end_index": 1,
                    "enter_at": (NOW + timedelta(minutes=10)).isoformat(),
                    "exit_at": (NOW + timedelta(hours=2)).isoformat(),
                }
            ],
        }
    ]
    context = await tools.integrate(query(), routes, None, transport, disasters)

    assert captured_transport == {
        "bbox": (99.9577, 12.5684, 100.5018, 13.7563),
        "now": NOW,
        "api_key": "test-key",
    }
    assert transport.records[0].source_name == "Real provider"
    assert disasters.alerts[0].severity.value == "HIGH"
    assert disasters.alerts[0].level == "CAUTION"
    assert disasters.alerts[0].active is True
    assert context.run_id == "run-live-1"
    assert calls[0][1] == [transport_record, disaster_record]


@pytest.mark.asyncio
async def test_successful_empty_provider_checks_have_non_synthetic_proof_records():
    tools = LiveToolSet(
        clock=lambda: NOW,
        transport_fetcher=lambda bbox, *, now, api_key: [],
        disaster_fetcher=lambda *, now: [],
        context_builder=context_builder_spy([]),
    )

    transport = await tools.transport(query())
    disasters = await tools.disasters(query())

    assert transport.canonical_records == []
    assert transport.records[0].source_name == "TomTom Orbis Traffic"
    assert "no matching active records" in transport.records[0].excerpt
    assert disasters.alerts == []
    assert "SYNTHETIC" not in disasters.records[0].source_name


@pytest.mark.asyncio
async def test_unavailable_provider_marks_tool_unavailable_instead_of_claiming_success():
    unavailable = {
        "status": "unavailable",
        "error_code": "PROVIDER_UNAVAILABLE",
    }
    tools = LiveToolSet(
        clock=lambda: NOW,
        transport_fetcher=lambda bbox, *, now, api_key: [unavailable],
        disaster_fetcher=lambda *, now: [],
        context_builder=context_builder_spy([]),
    )

    with pytest.raises(ToolError, match="PROVIDER_UNAVAILABLE"):
        await tools.transport(query())


@pytest.mark.asyncio
async def test_live_module_06_accepts_module_05_context_and_returns_agent_contracts():
    tools = LiveToolSet(
        clock=lambda: NOW,
        transport_fetcher=lambda bbox, *, now, api_key: [],
        disaster_fetcher=lambda *, now: [],
        context_builder=context_builder_spy([]),
    )
    integrated = IntegratedContext.model_validate({
        "feature_schema_version": "integrated-travel-v0.1-proposed",
        "run_id": "run-live-1",
        "created_at": NOW.isoformat(),
        "routes": [{
            "route_id": "route-1",
            "label": "Route 1",
            "travel_modes": ["CAR"],
            "geometry": {
                "type": "LineString",
                "coordinates": [[100.5018, 13.7563], [99.9577, 12.5684]],
            },
            "segments": [{
                "start_index": 0,
                "end_index": 1,
                "enter_at": (NOW + timedelta(minutes=10)).isoformat(),
                "exit_at": (NOW + timedelta(hours=2)).isoformat(),
                "matched_record_ids": {},
                "coverage": {"weather_observation": "missing"},
            }],
        }],
        "evidence": [],
        "quality_flags": ["missing"],
        "degraded": True,
        "risk_score": None,
    })

    risk = await tools.risk(query(), integrated)
    knowledge = await tools.knowledge(query(), [])
    routes = await tools.routes(query(), integrated, risk)

    assert risk.model_version == "rule-baseline-v0.1.2"
    assert risk.confidence.value == "LOW"
    assert knowledge.records == []
    assert routes.primary.route_id == "route-1"
    assert routes.primary.clearly_safer is False
