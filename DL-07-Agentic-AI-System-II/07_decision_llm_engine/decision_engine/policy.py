import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .models import Action, DecisionRequest, Level

LEVEL_RANK = {Level.LOW: 0, Level.MEDIUM: 1, Level.HIGH: 2}


@dataclass(frozen=True)
class Policy:
    version: str
    digest: str
    rules: tuple[tuple[str, Action], ...]

    @classmethod
    def load(cls, version: str) -> "Policy":
        if version != "prototype-v1":
            raise ValueError("Unsupported policy version")
        raw = (Path(__file__).parent / "policies" / f"{version}.json").read_bytes()
        manifest = json.loads(raw)
        if manifest["version"] != version or manifest["status"] != "prototype":
            raise ValueError("Policy manifest does not match its declared version/status")
        return cls(
            version=version,
            digest=hashlib.sha256(raw).hexdigest(),
            rules=tuple((rule["id"], Action(rule["action"])) for rule in manifest["rules"]),
        )


@dataclass(frozen=True)
class Decision:
    action: Action
    rule_id: str
    confidence: Level
    issues: tuple[str, ...]
    escalation_required: bool
    selected_route_id: str | None = None
    suggested_departure_time: datetime | None = None


def evaluate(request: DecisionRequest, now: datetime, policy: Policy) -> Decision:
    issues = set(request.quality.flags)
    required = (request.risk, request.weather, request.transport, request.routes)
    if any(part is None for part in required) or not request.evidence:
        issues.add("missing")
    if request.quality.active_restriction is None:
        issues.add("restriction_unknown")
    if request.quality.confidence == Level.LOW or (
        request.risk and request.risk.confidence == Level.LOW
    ):
        issues.add("low_confidence")
    if any(item.expires_at <= now for item in request.evidence):
        issues.add("stale")
    if any(item.fetched_at > now for item in request.evidence):
        issues.add("future_data")
    if request.context.departure_time < now:
        issues.add("departure_in_past")

    by_id = {item.evidence_id: item for item in request.evidence}
    active_alerts = [alert for alert in request.alerts if alert.active]
    if request.quality.active_restriction and not any(
        alert.level in {"AVOID", "CLOSURE"} for alert in active_alerts
    ):
        issues.add("restriction_requires_review")
    if active_alerts and request.quality.active_restriction is False:
        issues.add("conflicting")
    if (
        request.routes
        and request.routes.no_safe_route
        and any(
            route.usable and route.risk_level == Level.LOW for route in request.routes.alternatives
        )
    ):
        issues.add("conflicting")
    for alert in active_alerts:
        if any(
            by_id[eid].kind != "official" or not by_id[eid].official_source
            for eid in alert.evidence_ids
        ):
            issues.add("unverified_warning")
        if alert.level == "CAUTION":
            # The guide does not define warning-level mapping: request review.
            issues.add("caution_requires_review")

    # An assertion must refer to the matching evidence category, not arbitrary IDs.
    typed_parts = (
        (request.risk, "risk"),
        (request.weather, "weather"),
        (request.transport, "transport"),
        (request.routes, "route"),
        (request.time_assessment, "time"),
    )
    for part, kind in typed_parts:
        if part and any(by_id[eid].kind != kind for eid in part.evidence_ids):
            issues.add("evidence_kind_mismatch")
    if request.routes:
        for route in request.routes.alternatives:
            if any(by_id[eid].kind != "route" for eid in route.evidence_ids):
                issues.add("evidence_kind_mismatch")

    # Deterministic tie-breaking; HIGH never yields a weaker action via an alternative.
    alternatives = sorted(
        (
            option
            for option in (request.routes.alternatives if request.routes else [])
            if option.usable
            and option.clearly_safer
            and request.risk
            and LEVEL_RANK[option.risk_level] < LEVEL_RANK[request.risk.level]
        ),
        key=lambda option: (LEVEL_RANK[option.risk_level], option.route_id),
    )
    later = request.time_assessment
    conditions = {
        "OFFICIAL_RESTRICTION": any(a.level in {"AVOID", "CLOSURE"} for a in active_alerts),
        "HIGH_RISK": request.risk is not None and request.risk.level == Level.HIGH,
        "NO_SAFE_ROUTE": request.routes is not None and request.routes.no_safe_route,
        "INSUFFICIENT_EVIDENCE": bool(issues),
        "SAFER_ROUTE": bool(alternatives),
        "SAFER_TIME": later is not None and later.safer_later,
        "LOW_RISK_CLEAR": request.risk is not None
        and request.risk.level == Level.LOW
        and request.quality.active_restriction is False
        and not active_alerts,
        "UNRESOLVED": True,
    }
    for rule_id, action in policy.rules:
        if not conditions[rule_id]:
            continue
        if rule_id == "UNRESOLVED":
            issues.add("unresolved_policy")
        confidence = min(
            (request.quality.confidence, request.risk.confidence if request.risk else Level.LOW),
            key=LEVEL_RANK.__getitem__,
        )
        if issues:
            confidence = Level.LOW
        return Decision(
            action=action,
            rule_id=rule_id,
            confidence=confidence,
            issues=tuple(sorted(issues)),
            escalation_required=bool(issues),
            selected_route_id=alternatives[0].route_id if action == Action.CHANGE_ROUTE else None,
            suggested_departure_time=(
                later.suggested_departure_time if action == Action.DELAY and later else None
            ),
        )
    raise RuntimeError("Policy must contain a terminal rule")
