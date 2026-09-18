from datetime import datetime

from .audit import AuditStore
from .config import Settings
from .evidence import references
from .explanation import ExplanationProvider, explain
from .models import BACKEND_ACTIONS, DecisionRequest, DecisionResponse, Versions
from .policy import Policy, evaluate


async def decide(
    request: DecisionRequest,
    *,
    now: datetime,
    settings: Settings,
    policy: Policy,
    audit: AuditStore,
    provider: ExplanationProvider | None = None,
) -> DecisionResponse:
    decision = evaluate(request, now, policy)
    citations, evidence_status = references(request, decision, now)
    explanation, checks = await explain(
        decision, request, settings, provider, [item.evidence_id for item in citations]
    )
    result = DecisionResponse(
        request_id=request.context.request_id,
        action_code=decision.action,
        backend_action_code=BACKEND_ACTIONS[decision.action],
        risk_level=request.risk.level if request.risk else None,
        confidence=decision.confidence,
        escalation_required=decision.escalation_required,
        escalation_reasons=list(decision.issues),
        selected_route_id=decision.selected_route_id,
        suggested_departure_time=decision.suggested_departure_time,
        explanation=explanation,
        citations=citations,
        evidence_status=evidence_status,
        rules_fired=[decision.rule_id],
        degraded_services=["llm"] if explanation.mode == "template" else [],
        validation_results=["INPUT_SCHEMA_VALID", "CONTEXT_MATCHED", "ACTION_LOCKED", *checks],
        versions=Versions(
            policy=policy.version,
            policy_sha256=policy.digest,
            prompt=settings.prompt_version,
            model=settings.llm_model_explainer if explanation.mode == "provider" else "template-v1",
            risk_model=request.risk.model_version if request.risk else None,
            data=request.quality.data_version,
        ),
        evaluated_at=now,
        valid_until=min((e.expires_at for e in request.evidence), default=None),
    )
    audit.append(result)
    return result
