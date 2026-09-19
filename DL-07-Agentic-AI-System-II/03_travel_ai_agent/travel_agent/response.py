"""Turn the run state and Module 07's decision into Module 02's AgentRunResponse."""

from __future__ import annotations

from typing import TYPE_CHECKING

from travel_agent.config import Settings
from travel_agent.contracts import (
    AgentDiagnostics,
    AgentRecommendation,
    AgentRisk,
    AgentRoutes,
    AgentRunResponse,
    AgentRunStatus,
    AgentVersions,
    Clarification,
    DataCategory,
    DataFreshness,
    FreshnessItem,
    Hazard,
    RiskFactor,
    RouteOption,
    ServiceState,
    Source,
)
from travel_agent.tools.schemas import RouteInfo

if TYPE_CHECKING:
    from travel_agent.pipeline import AgentState

# Evidence kinds from 07's vocabulary -> the backend's data categories.
# "time" has no backend category and is left out of sources/freshness.
CATEGORY = {
    "weather": DataCategory.WEATHER,
    "transport": DataCategory.TRANSPORT,
    "route": DataCategory.TRANSPORT,
    "official": DataCategory.DISASTER,
    "risk": DataCategory.DISASTER,
    "knowledge": DataCategory.KNOWLEDGE_BASE,
}


def build_response(
    state: AgentState,
    *,
    settings: Settings,
    clarification: Clarification | None,
    duration_ms: int,
) -> AgentRunResponse:
    decision = state.decision
    records = {r.id: r for r in state.records()}
    common = {
        "run_id": state.run.run_id,
        "service_status": state.service_status,
        "versions": AgentVersions(
            agent=settings.agent_version,
            risk_model=state.risk.model_version if state.risk else None,
            prompt=settings.prompt_version,
        ),
        "diagnostics": AgentDiagnostics(
            tool_calls=state.budget.tool_calls,
            duration_ms=duration_ms,
            trace_id=str(state.run.run_id),
        ),
    }
    if clarification:
        return AgentRunResponse(
            status=AgentRunStatus.NEEDS_CLARIFICATION, clarification=clarification, **common
        )
    assert decision is not None, "the pipeline ends the run when Module 07 fails"

    risk_level = decision.risk_level or (state.risk.level if state.risk else None)
    risk = None
    if risk_level:
        risk = AgentRisk(
            level=risk_level,
            score=state.risk.score if state.risk else None,
            # 06 and 07 give confidence as LOW/MEDIUM/HIGH, not a probability;
            # we do not invent a number for the backend's 0-1 field.
            confidence=None,
            factors=[
                RiskFactor(type=f.type, level=f.level, description=f.description)
                for f in (state.risk.factors if state.risk else [])
            ],
        )

    sources = []
    for citation in decision.citations:
        record = records.get(citation.evidence_id)
        category = CATEGORY.get(record.kind) if record else None
        if category:
            sources.append(
                Source(
                    source_id=citation.evidence_id,
                    name=citation.source_name,
                    category=category,
                    url=citation.url,
                    retrieved_at=citation.fetched_at,
                )
            )

    # Report the oldest observation per category, so freshness is never overstated.
    oldest: dict[DataCategory, object] = {}
    for record in records.values():
        category = CATEGORY.get(record.kind)
        if category and (category not in oldest or record.observed_at < oldest[category]):
            oldest[category] = record.observed_at

    routes = None
    if state.routes:
        routes = AgentRoutes(
            primary=_route(state.routes.primary),
            alternatives=[_route(r) for r in state.routes.alternatives],
        )

    return AgentRunResponse(
        status=response_status(state),
        risk=risk,
        recommendation=AgentRecommendation(
            type=decision.backend_action_code,
            summary=decision.explanation.summary[:4000],
            reasons=decision.explanation.reasons,
            suggested_departure_time=decision.suggested_departure_time,
        ),
        routes=routes,
        hazards=[
            Hazard(
                hazard_id=a.hazard_id,
                type=a.hazard_type,
                severity=a.severity,
                title=a.title,
                starts_at=a.starts_at,
                ends_at=a.ends_at,
                source_id=a.record.id,
            )
            for a in (state.disasters.alerts if state.disasters else [])
            if a.active
        ],
        # Pending team agreement on who owns emergency instructions (07 or 08).
        emergency_instructions=None,
        sources=sources,
        data_freshness=DataFreshness(
            items=[FreshnessItem(category=c, updated_at=t) for c, t in oldest.items()]
        ),
        valid_until=decision.valid_until,
        **common,
    )


def response_status(state: AgentState) -> AgentRunStatus:
    if any(s is ServiceState.UNAVAILABLE for s in state.service_status.values()):
        return AgentRunStatus.PARTIAL_RESULT
    return AgentRunStatus.COMPLETED


def _route(info: RouteInfo) -> RouteOption:
    return RouteOption(
        route_id=info.route_id,
        label=info.label,
        travel_modes=info.travel_modes,
        distance_km=info.distance_km,
        duration_minutes=info.duration_minutes,
        risk_level=info.risk_level,
        restrictions=[] if info.usable else ["NOT_USABLE"],
    )
