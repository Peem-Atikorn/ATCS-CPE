"""Synthetic stand-ins for Modules 04, 05 and 06 until their services exist.

Nothing here is real weather, transport or disaster data. Pick a scenario with
`request.preferences.mock_scenario`; unknown or missing values use `low_risk`.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from travel_agent.contracts import RiskLevel
from travel_agent.tools.base import ToolError
from travel_agent.tools.schemas import (
    Alert,
    DisasterResult,
    IntegratedContext,
    KnowledgeResult,
    Record,
    RecordKind,
    RiskFactorResult,
    RiskResult,
    RouteInfo,
    RouteResult,
    TransportResult,
    TravelQuery,
    WeatherResult,
)

SCENARIOS = frozenset(
    {"low_risk", "high_risk", "closure", "safer_route", "safer_time", "weather_down"}
)


def _scenario(query: TravelQuery) -> str:
    return query.mock_scenario if query.mock_scenario in SCENARIOS else "low_risk"


class MockToolSet:
    def __init__(self, clock: Callable[[], datetime] = lambda: datetime.now(UTC)) -> None:
        self._clock = clock

    def _record(self, kind: RecordKind, *, official: bool = False) -> Record:
        now = self._clock()
        return Record(
            kind=kind,
            source_name=f"SYNTHETIC {kind} mock (Module 03)",
            url=f"https://example.org/mock/{kind}",
            official_source=official,
            observed_at=now - timedelta(minutes=10),
            fetched_at=now - timedelta(minutes=1),
            expires_at=now + timedelta(hours=1),
            excerpt="MOCK DATA ONLY. Not an actual alert or travel assessment.",
        )

    async def weather(self, query: TravelQuery) -> WeatherResult:
        if _scenario(query) == "weather_down":
            raise ToolError("weather", "mock provider unavailable")
        return WeatherResult(
            summary="Synthetic weather: light rain", records=[self._record("weather")]
        )

    async def transport(self, query: TravelQuery) -> TransportResult:
        return TransportResult(
            summary="Synthetic transport: services running", records=[self._record("transport")]
        )

    async def disasters(self, query: TravelQuery) -> DisasterResult:
        record = self._record("official", official=True)
        alerts = []
        if _scenario(query) == "closure":
            alerts.append(
                Alert(
                    hazard_id="mock-flood-1",
                    hazard_type="FLOOD",
                    severity=RiskLevel.HIGH,
                    title="Synthetic road closure due to flooding",
                    level="CLOSURE",
                    active=True,
                    record=record,
                )
            )
        return DisasterResult(alerts=alerts, records=[record])

    async def integrate(self, query, weather, transport, disasters) -> IntegratedContext:
        closure = bool(
            disasters and any(a.active and a.level == "CLOSURE" for a in disasters.alerts)
        )
        return IntegratedContext(
            data_version="mock-data-v1",
            primary_route_id="mock-primary",
            confidence=RiskLevel.HIGH,
            active_restriction=closure if disasters else None,
        )

    async def risk(self, query: TravelQuery, context: IntegratedContext | None) -> RiskResult:
        level, score = {
            "high_risk": (RiskLevel.HIGH, 0.86),
            "closure": (RiskLevel.HIGH, 0.9),
            "safer_route": (RiskLevel.MEDIUM, 0.54),
            "safer_time": (RiskLevel.MEDIUM, 0.5),
        }.get(_scenario(query), (RiskLevel.LOW, 0.12))
        return RiskResult(
            level=level,
            score=score,
            confidence=RiskLevel.HIGH,
            model_version="mock-risk-v1",
            factors=[
                RiskFactorResult(type="RAIN", level=level, description="Synthetic rainfall factor")
            ],
            records=[self._record("risk")],
        )

    async def knowledge(self, query: TravelQuery, alerts: list[Alert]) -> KnowledgeResult:
        return KnowledgeResult(records=[self._record("knowledge")])

    async def routes(self, query, context, risk) -> RouteResult:
        scenario = _scenario(query)
        primary_level = risk.level if risk else RiskLevel.MEDIUM
        alternatives = []
        if scenario == "safer_route":
            alternatives.append(
                RouteInfo(
                    route_id="mock-alternative",
                    label="Synthetic inland road",
                    travel_modes=["CAR"],
                    distance_km=162,
                    duration_minutes=150,
                    risk_level=RiskLevel.LOW,
                    clearly_safer=True,
                )
            )
        safer_later = scenario == "safer_time"
        return RouteResult(
            primary=RouteInfo(
                route_id=context.primary_route_id if context else "mock-primary",
                label="Synthetic coastal road",
                travel_modes=["CAR"],
                distance_km=148,
                duration_minutes=130,
                risk_level=primary_level,
                usable=scenario != "closure",
            ),
            alternatives=alternatives,
            safer_later=safer_later,
            suggested_departure_time=query.departure_time + timedelta(hours=3)
            if safer_later
            else None,
            records=[self._record("route"), self._record("time")],
        )
