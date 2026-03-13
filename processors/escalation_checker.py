"""Rule-based escalation decision engine."""

from __future__ import annotations

from guards.confidence_gate import ConfidenceResult
from schemas.risk import EscalationResult, RiskAssessment, RiskLevel
from schemas.scenario import ParsedFields


def check_escalation(
    risk_assessment: RiskAssessment,
    parsed_fields: ParsedFields,
    confidence_result: ConfidenceResult,
) -> EscalationResult:
    reasons: list[str] = []

    if risk_assessment.risk_level == RiskLevel.CRITICAL:
        reasons.append("高风险场景（Critical），需人工法务复核")

    if confidence_result.low_confidence:
        reasons.append(confidence_result.reason or "证据置信度偏低，建议人工复核")

    key_missing = [name for name in (parsed_fields.missing_fields or []) if name in {"region", "data_types"}]
    if key_missing:
        reasons.append(
            f"关键字段缺失（{', '.join(key_missing)}），评估结论存在重大不确定性"
        )

    return EscalationResult(
        requires_escalation=bool(reasons),
        reasons=reasons,
        primary_reason=reasons[0] if reasons else "",
    )
