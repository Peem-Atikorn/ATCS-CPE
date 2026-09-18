from datetime import datetime

from .models import Citation, DecisionRequest, EvidenceStatus
from .policy import Decision


def references(
    request: DecisionRequest,
    decision: Decision,
    now: datetime,
) -> tuple[list[Citation], list[EvidenceStatus]]:
    parts = [request.risk, request.weather, request.transport, request.routes]
    if decision.rule_id == "OFFICIAL_RESTRICTION":
        parts = [a for a in request.alerts if a.active and a.level in {"AVOID", "CLOSURE"}]
    elif decision.rule_id == "HIGH_RISK":
        parts = [request.risk]
    elif decision.rule_id == "NO_SAFE_ROUTE":
        parts = [request.routes]
    elif decision.rule_id == "SAFER_ROUTE":
        parts = [
            request.risk,
            request.routes,
            *(r for r in request.routes.alternatives if r.route_id == decision.selected_route_id),
        ]
    elif decision.rule_id == "SAFER_TIME":
        parts = [request.risk, request.time_assessment]
    used_ids = {eid for part in parts if part for eid in part.evidence_ids}
    expected_kinds: dict[str, set[str]] = {}
    typed_parts = [
        (request.risk, "risk"),
        (request.weather, "weather"),
        (request.transport, "transport"),
        (request.routes, "route"),
        (request.time_assessment, "time"),
    ]
    typed_parts.extend((alert, "official") for alert in request.alerts)
    if request.routes:
        typed_parts.extend((route, "route") for route in request.routes.alternatives)
    for part, kind in typed_parts:
        if part:
            for eid in part.evidence_ids:
                expected_kinds.setdefault(eid, set()).add(kind)
    citations = []
    statuses = []
    for item in sorted(request.evidence, key=lambda e: e.evidence_id):
        issues = []
        if item.expires_at <= now:
            issues.append("stale")
        if item.fetched_at > now:
            issues.append("future_data")
        if item.kind == "official" and not item.official_source:
            issues.append("unverified_warning")
        if any(kind != item.kind for kind in expected_kinds.get(item.evidence_id, ())):
            issues.append("evidence_kind_mismatch")
        used = item.evidence_id in used_ids
        cited = used and not issues
        statuses.append(
            EvidenceStatus(
                evidence_id=item.evidence_id,
                used_by_decision=used,
                cited=cited,
                validation_issues=issues,
            )
        )
        if cited:
            citations.append(
                Citation(
                    **item.model_dump(
                        include={
                            "evidence_id",
                            "source_name",
                            "url",
                            "observed_at",
                            "fetched_at",
                            "expires_at",
                        }
                    )
                )
            )
    return citations, statuses
