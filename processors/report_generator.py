"""Audit report generation orchestrator."""

from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError

from guards import legal_disclaimer
from schemas.report import AuditReport
from schemas.risk import EscalationResult, RiskAssessment
from schemas.state import SharedState
from tools import output_filter

PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "templates" / "report.txt"


async def generate_report(
    state: SharedState,
    risk_assessment: RiskAssessment,
    escalation_result: EscalationResult,
) -> AuditReport:
    # The prompt text is loaded to keep runtime behavior aligned with prompt-driven design.
    _ = PROMPT_PATH.read_text(encoding="utf-8")

    parsed_fields = state.parsed_fields
    uncertainties = list(risk_assessment.low_confidence_items)
    if state.missing_fields:
        uncertainties.append(
            "以下内容因信息不足，结论存在不确定性：缺失字段 " + ", ".join(state.missing_fields)
        )
    if parsed_fields.region is None:
        uncertainties.append(
            "用户所在法域未明确，当前报告按中欧双法域保守评估，实际适用法域请结合业务确认"
        )

    report_payload = {
        "session_id": state.session_id or "unknown",
        "summary": _build_summary(state),
        "risk_level": risk_assessment.risk_level,
        "risk_overview": risk_assessment.risk_summary,
        "evidence_citations": risk_assessment.evidence,
        "uncertainties": uncertainties,
        "remediation_actions": risk_assessment.remediation,
        "parsed_fields": parsed_fields,
        "jurisdictions_covered": risk_assessment.jurisdictions_covered,
        "requires_escalation": escalation_result.requires_escalation,
        "escalation_result": escalation_result,
        "disclaimer": "",
        "reasoning": risk_assessment.reasoning,
    }

    try:
        report = AuditReport.model_validate(report_payload)
    except ValidationError as exc:
        report_payload["requires_escalation"] = True
        report_payload["uncertainties"] = uncertainties + [
            f"报告结构校验失败：{exc.errors()[0]['msg']}"
        ]
        report = AuditReport.model_validate(report_payload)

    report = output_filter.filter_report_fields(report)
    report = legal_disclaimer.inject_disclaimer(report)
    return report


def _build_summary(state: SharedState) -> str:
    raw = (state.raw_input.raw_text if state.raw_input else "").strip()
    if _contains_chinese(raw):
        return (
            f"该场景描述为：{raw}。"
            "系统已完成字段化解析并关联法规证据。"
            "以下报告用于上线前的前置风控讨论。"
        )
    return (
        f"The scenario is: {raw}. "
        "The system parsed key fields and aligned evidence citations. "
        "This report is a pre-launch risk reference."
    )


def _contains_chinese(text: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in text)
