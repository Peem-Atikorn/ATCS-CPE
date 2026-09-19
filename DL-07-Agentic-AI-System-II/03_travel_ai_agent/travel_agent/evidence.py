"""Build Module 07's DecisionRequest (decision_engine/models.py) from tool results.

07 rejects the whole package if any part disagrees on request/route/time or cites an
evidence ID that is not in the package, so everything here shares one `context` and
only references records that were collected in this run.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from travel_agent.contracts import RiskLevel
from travel_agent.tools.schemas import Record

if TYPE_CHECKING:
    from travel_agent.pipeline import AgentState

MAX_EVIDENCE_IDS = 32  # per item, 07's EvidenceIds limit


def _ids(records: list[Record]) -> list[str]:
    return [r.id for r in records if r.id][:MAX_EVIDENCE_IDS]


def locale_for(language: str) -> str:
    return "th-TH" if language.lower().startswith("th") else "en-US"


def primary_route_id(state: AgentState) -> str:
    if state.routes:
        return state.routes.primary.route_id
    if state.context:
        return state.context.primary_route_id
    return "primary"


def build_decision_request(state: AgentState) -> dict[str, Any]:
    departure = state.run.request.departure_time
    context = {
        "request_id": str(state.run.run_id),
        "route_id": primary_route_id(state),
        "departure_time": departure.isoformat(),
    }
    payload: dict[str, Any] = {
        "context": context,
        "locale": locale_for(state.run.request.language),
        "quality": _quality(state, context),
        "alerts": [],
        "evidence": [
            {"context": context, "evidence_id": r.id, **r.model_dump(mode="json", exclude={"id"})}
            for r in state.records()
        ],
    }

    if state.risk:
        payload["risk"] = {
            "context": context,
            "level": state.risk.level,
            "confidence": state.risk.confidence,
            "model_version": state.risk.model_version,
            "evidence_ids": _ids(state.risk.records),
        }
    for name, result in (("weather", state.weather), ("transport", state.transport)):
        if result:
            payload[name] = {
                "context": context,
                "text": result.summary,
                "evidence_ids": _ids(result.records),
            }
    if state.disasters:
        payload["alerts"] = [
            {
                "context": context,
                "level": alert.level,
                "active": alert.active,
                "evidence_ids": _ids([alert.record]),
            }
            for alert in state.disasters.alerts
        ]
    if routes := state.routes:
        # 07 checks that each claim cites evidence of its own kind (route vs time).
        route_ids = _ids([r for r in routes.records if r.kind == "route"])
        time_ids = _ids([r for r in routes.records if r.kind == "time"])
        seen = {routes.primary.route_id}
        alternatives = []
        for option in routes.alternatives:
            if option.route_id in seen:
                continue  # 07 requires unique alternatives that differ from the primary
            seen.add(option.route_id)
            alternatives.append(
                {
                    "route_id": option.route_id,
                    "risk_level": option.risk_level,
                    "usable": option.usable,
                    "clearly_safer": option.clearly_safer,
                    "evidence_ids": route_ids,
                }
            )
        if route_ids:
            payload["routes"] = {
                "context": context,
                "no_safe_route": routes.no_safe_route,
                "alternatives": alternatives,
                "evidence_ids": route_ids,
            }
        later = routes.suggested_departure_time
        # A "safer later" claim without a later time is not usable evidence.
        safer_later = routes.safer_later and later is not None and later > departure
        if time_ids:
            payload["time_assessment"] = {
                "context": context,
                "safer_later": safer_later,
                "suggested_departure_time": later.isoformat() if safer_later else None,
                "evidence_ids": time_ids,
            }
    return payload


def _quality(state: AgentState, context: dict[str, Any]) -> dict[str, Any]:
    integrated = state.context
    flags = set(integrated.flags) if integrated else {"incomplete"}
    required = (state.weather, state.transport, state.disasters, state.risk, state.routes)
    if any(result is None for result in required):
        flags.add("missing")
    return {
        "context": context,
        "confidence": integrated.confidence if integrated else RiskLevel.LOW,
        "flags": sorted(flags),
        # Unknown restriction status stays None; it must never read as "no restriction".
        "active_restriction": integrated.active_restriction if integrated else None,
        "data_version": integrated.data_version if integrated else "unintegrated",
    }
