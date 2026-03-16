from app.guards.legal_disclaimer import inject_disclaimer
from app.schemas.evidence import EvidenceChunk
from app.schemas.report import AuditReport
from app.schemas.risk import RemediationAction, RiskLevel
from app.schemas.scenario import ParsedFields
from app.tools.output_filter import filter_report_fields


def _report_with_hard_tone() -> AuditReport:
    evidence = [
        EvidenceChunk(
            regulation="GDPR",
            article="Art.46",
            jurisdiction="EU",
            text="法规原文：贵司必须立即完成整改，否则违法。",
            summary="法规摘要：贵司必须遵守跨境传输要求。",
            rerank_score=0.9,
            tags=["cross_border_transfer"],
        )
    ]
    remediation = [
        RemediationAction(
            role="PM",
            action="贵司必须立即修订产品说明。",
            priority="Immediate",
            regulation_ref="GDPR Art.46",
        )
    ]
    return AuditReport(
        session_id="s-filter",
        summary="贵司必须立即修复，否则违法。",
        risk_level=RiskLevel.HIGH,
        risk_overview="该路径可能违规。",
        evidence_citations=evidence,
        uncertainties=["该判断必须遵守额外信息补充。"],
        remediation_actions=remediation,
        parsed_fields=ParsedFields(region="EU", data_types=["Personal"], cross_border=True),
        jurisdictions_covered=["EU"],
        requires_escalation=False,
        escalation_result=None,
        disclaimer="免责声明",
        reasoning="This path must immediately be fixed.",
    )


def test_output_filter_respects_protected_evidence_fields() -> None:
    report = _report_with_hard_tone()
    filtered = filter_report_fields(report)

    assert "建议贵司" in filtered.summary
    assert "可能不符合相关法规要求" in filtered.summary
    assert "存在合规风险" in filtered.risk_overview
    assert "should prioritize" in filtered.reasoning
    assert "法规原文：贵司必须立即完成整改，否则违法。" == filtered.evidence_citations[0].text
    assert "法规摘要：贵司必须遵守跨境传输要求。" == filtered.evidence_citations[0].summary
    assert filtered.remediation_actions[0].action.startswith("建议贵司")


def test_disclaimer_rendered_once_top_and_bottom() -> None:
    report = _report_with_hard_tone()
    report.requires_escalation = True
    report = inject_disclaimer(report)

    markdown = report.to_markdown()
    assert markdown.count(report.disclaimer) == 2
    assert markdown.strip().startswith(report.disclaimer)
    assert markdown.strip().endswith(report.disclaimer)


def test_report_json_contract_round_trip() -> None:
    report = inject_disclaimer(filter_report_fields(_report_with_hard_tone()))
    payload = report.to_json()
    validated = AuditReport.model_validate(payload)
    assert validated.session_id == "s-filter"
