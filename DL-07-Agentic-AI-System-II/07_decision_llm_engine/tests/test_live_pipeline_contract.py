"""Read-only contract tests across the current 05 -> 06 -> 03 -> 07 boundary.

The sibling modules are imported as dependencies but never modified. Provider calls
are not made: synthetic canonical records exercise their real integration/adapters.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from decision_engine.api import create_app
from decision_engine.config import Settings

MODULES = Path(__file__).resolve().parents[2]
MODULE_03 = MODULES / "03_travel_ai_agent"
MODULE_05 = MODULES / "05_data_integration" / "integration.py"
MODULE_06 = MODULES / "06_risk_knowledge_services"

if not all(path.exists() for path in (MODULE_03, MODULE_05, MODULE_06)):
    pytest.skip("Sibling modules are absent in this standalone checkout", allow_module_level=True)

for path in (MODULE_03, MODULE_06):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from risk_knowledge.risk import assess_risk  # noqa: E402
from risk_knowledge.routing import analyze_routes  # noqa: E402
from travel_agent.evidence import build_decision_request  # noqa: E402
from travel_agent.tools.schemas import (  # noqa: E402
    DisasterResult,
    IntegratedContext,
    Record,
    RiskResult,
    RouteResult,
    TransportResult,
    WeatherResult,
)

NOW = datetime(2026, 9, 21, 1, 0, tzinfo=UTC)
DEPARTURE = NOW + timedelta(hours=1)


@pytest.fixture
def pipeline_client(tmp_path):
    app = create_app(Settings(_env_file=None, audit_log_path=tmp_path / "pipeline-audit.jsonl"))
    app.state.clock = lambda: NOW
    with TestClient(app) as client:
        yield client


def load_module_05():
    spec = importlib.util.spec_from_file_location("module_05_for_07_contract", MODULE_05)
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load Module 05 integration")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def route_query():
    return {
        "run_id": "00000000-0000-4000-8000-000000000705",
        "routes": [
            {
                "route_id": "contract-primary",
                "label": "Synthetic contract route",
                "travel_modes": ["CAR"],
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[100.0, 13.0], [100.2, 13.0]],
                },
                "segments": [
                    {
                        "start_index": 0,
                        "end_index": 1,
                        "enter_at": DEPARTURE.isoformat(),
                        "exit_at": (DEPARTURE + timedelta(minutes=40)).isoformat(),
                    }
                ],
            }
        ],
    }


def canonical_records(*, high_transport=False, omit_kind=None):
    records = []
    for kind in (
        "current_weather",
        "weather_forecast",
        "transport_status",
        "closure",
        "disaster_event",
        "official_alert",
    ):
        if kind == omit_kind:
            continue
        high = high_transport and kind == "transport_status"
        records.append(
            {
                "schema_version": "canonical-record-v0.1-proposed",
                "record_id": f"contract-{kind}",
                "record_kind": kind,
                "status": "available",
                "source": {"name": "Synthetic contract provider", "authority": None},
                "source_lineage": f"https://example.org/contract/{kind}",
                "spatial_footprint": {"type": "Point", "coordinates": [100.1, 13.0]},
                "observed_at": (NOW - timedelta(minutes=10)).isoformat(),
                "valid_at": (DEPARTURE + timedelta(minutes=10)).isoformat(),
                "fetched_at": (NOW - timedelta(minutes=5)).isoformat(),
                "expires_at": (NOW + timedelta(hours=3)).isoformat(),
                "severity": "HIGH" if high else "LOW",
                "quality_flags": [],
                "value": {
                    "active": False,
                    "status": "CLOSED" if high else "NORMAL",
                    "severity": "HIGH" if high else "LOW",
                },
            }
        )
    return records


def evidence_record(kind, evidence_id):
    return Record(
        id=evidence_id,
        kind=kind,
        source_name="Synthetic cross-module fixture",
        url=f"https://example.org/contract/{kind}",
        observed_at=NOW - timedelta(minutes=10),
        fetched_at=NOW - timedelta(minutes=5),
        expires_at=NOW + timedelta(hours=3),
        excerpt="Synthetic contract evidence; not travel advice.",
    )


class PipelineState(SimpleNamespace):
    def records(self):
        found = []
        for result in (
            self.weather,
            self.transport,
            self.disasters,
            self.candidates,
            self.risk,
            self.knowledge,
            self.routes,
        ):
            if result:
                found.extend(result.records)
        return found


def pipeline_payload(*, upstream_ready, high_transport=False, omit_kind=None):
    integrated = load_module_05().build_context(
        route_query(),
        canonical_records(high_transport=high_transport, omit_kind=omit_kind),
        now=NOW,
    )
    if omit_kind is None:
        assert all(
            status == "covered"
            for segment in integrated["routes"][0]["segments"]
            for status in segment["coverage"].values()
        )
        assert integrated["quality_flags"] == []

    if upstream_ready:
        integrated.update(confidence="HIGH", active_restriction=False)
    risk_06 = assess_risk(integrated, now=NOW)
    routes_06 = analyze_routes(
        {
            "run_id": integrated["run_id"],
            "origin": [13.0, 100.0],
            "destination": [13.0, 100.2],
            "departure_time": DEPARTURE,
            "travel_modes": ["CAR"],
        },
        integrated,
        risk_06,
        now=NOW,
    )
    risk = RiskResult.model_validate(risk_06.model_dump(mode="python")).model_copy(
        update={"records": [evidence_record("risk", "contract-risk")]}
    )
    routes = RouteResult.model_validate(routes_06.model_dump(mode="python")).model_copy(
        update={"records": [evidence_record("route", "contract-route")]}
    )
    context = IntegratedContext.model_validate(integrated)
    state = PipelineState(
        run=SimpleNamespace(
            run_id=UUID(integrated["run_id"]),
            request=SimpleNamespace(departure_time=DEPARTURE, language="th"),
        ),
        context=context,
        weather=WeatherResult(
            summary="Synthetic complete weather check",
            records=[evidence_record("weather", "contract-weather")],
        ),
        transport=TransportResult(
            summary="Synthetic complete transport check",
            records=[evidence_record("transport", "contract-transport")],
        ),
        disasters=DisasterResult(
            alerts=[], records=[evidence_record("official", "contract-official")]
        ),
        candidates=SimpleNamespace(records=[]),
        risk=risk,
        knowledge=None,
        routes=routes,
    )
    return integrated, risk_06, build_decision_request(state)


def test_current_complete_coverage_stays_conservative_until_quality_is_confirmed(
    pipeline_client,
):
    integrated, risk, payload = pipeline_payload(upstream_ready=False)
    assert risk.level.value == "LOW"
    assert risk.confidence.value == "HIGH"
    assert integrated.get("confidence") is None
    assert integrated.get("active_restriction") is None
    assert payload["quality"]["confidence"] == "LOW"
    assert payload["quality"]["active_restriction"] is None

    result = pipeline_client.post("/v1/decisions", json=payload)
    assert result.status_code == 200, result.text
    body = result.json()
    assert body["risk_level"] == "LOW"
    assert body["action_code"] == "AVOID"
    assert {"low_confidence", "restriction_unknown"} <= set(body["escalation_reasons"])


def test_confirmed_complete_low_risk_reaches_normal_through_current_contract(
    pipeline_client,
):
    _, risk, payload = pipeline_payload(upstream_ready=True)
    assert risk.level.value == "LOW"
    assert payload["quality"]["confidence"] == "HIGH"
    assert payload["quality"]["active_restriction"] is False

    result = pipeline_client.post("/v1/decisions", json=payload)
    assert result.status_code == 200, result.text
    body = result.json()
    assert body["risk_level"] == "LOW"
    assert body["action_code"] == "NORMAL"
    assert body["confidence"] == 0.9
    assert not body["escalation_required"]


def test_high_risk_from_module_06_cannot_be_weakened_by_module_07(pipeline_client):
    _, risk, payload = pipeline_payload(upstream_ready=True, high_transport=True)
    assert risk.level.value == "HIGH"

    result = pipeline_client.post("/v1/decisions", json=payload)
    assert result.status_code == 200, result.text
    body = result.json()
    assert body["risk_level"] == "HIGH"
    assert body["action_code"] == "AVOID"
    assert body["rules_fired"] == ["HIGH_RISK"]
    assert body["emergency_assessment"]["status"] == "fallback"


def test_partial_coverage_from_module_05_cannot_select_a_safe_action(pipeline_client):
    integrated, risk, payload = pipeline_payload(upstream_ready=True, omit_kind="official_alert")
    coverage = integrated["routes"][0]["segments"][0]["coverage"]
    assert coverage["official_alert"] == "missing"
    assert {"missing", "partial"} <= set(integrated["quality_flags"])
    assert risk.level.value == "LOW"

    result = pipeline_client.post("/v1/decisions", json=payload)
    assert result.status_code == 200, result.text
    body = result.json()
    assert body["risk_level"] == "LOW"
    assert body["action_code"] == "AVOID"
    assert body["selected_route_id"] is None
    assert {"missing", "partial", "incomplete"} <= set(body["escalation_reasons"])
