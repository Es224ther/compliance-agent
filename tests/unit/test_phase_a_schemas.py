from pydantic import ValidationError

from schemas.evidence import EvidenceChunk
from schemas.report import AuditReport
from schemas.risk import EscalationResult, RemediationAction, RiskAssessment, RiskLevel
from schemas.scenario import ParsedFields


def _sample_evidence() -> list[EvidenceChunk]:
    return [
        EvidenceChunk(
            regulation="GDPR",
            article="Art.46",
            jurisdiction="EU",
            text="SCC safeguards for transfer.",
            summary="SCC safeguards",
            rerank_score=0.9,
            tags=["cross_border_transfer"],
        )
    ]


def test_schema_models_can_be_instantiated() -> None:
    evidence = _sample_evidence()
    remediation = [
        RemediationAction(
            role="PM",
            action="Document transfer pathway.",
            priority="Immediate",
            regulation_ref="GDPR Art.46",
        )
    ]
    assessment = RiskAssessment(
        risk_level=RiskLevel.HIGH,
        risk_summary="Cross-border transfer has elevated risk.",
        reasoning="Evidence indicates cross-border obligations.",
        jurisdictions_covered=["EU"],
        evidence=evidence,
        remediation=remediation,
        low_confidence_items=[],
        requires_escalation=False,
        scoring_factors=[{"rule": "x", "description": "x", "impact": "+1"}],
    )

    report = AuditReport(
        session_id="s-1",
        summary="场景摘要。",
        risk_level=assessment.risk_level,
        risk_overview=assessment.risk_summary,
        evidence_citations=evidence,
        uncertainties=[],
        remediation_actions=remediation,
        parsed_fields=ParsedFields(region="EU", data_types=["Personal"], cross_border=True),
        jurisdictions_covered=["EU"],
        requires_escalation=False,
        escalation_result=EscalationResult(requires_escalation=False, reasons=[]),
        disclaimer="免责声明文本",
    )

    assert report.session_id == "s-1"
    assert assessment.risk_level == RiskLevel.HIGH


def test_disclaimer_rendered_top_and_bottom() -> None:
    disclaimer = "免责声明文本"
    report = AuditReport(
        session_id="s-2",
        summary="摘要",
        risk_level=RiskLevel.LOW,
        risk_overview="概述",
        evidence_citations=_sample_evidence(),
        uncertainties=[],
        remediation_actions=[],
        parsed_fields=ParsedFields(region="EU", data_types=["Personal"], cross_border=False),
        jurisdictions_covered=["EU"],
        requires_escalation=False,
        escalation_result=None,
        disclaimer=disclaimer,
    )

    markdown = report.to_markdown()
    assert markdown.count(disclaimer) == 2
    assert markdown.strip().startswith(disclaimer)
    assert markdown.strip().endswith(disclaimer)


def test_model_validate_no_validation_error() -> None:
    payload = {
        "session_id": "s-3",
        "summary": "摘要",
        "risk_level": "Medium",
        "risk_overview": "概述",
        "evidence_citations": _sample_evidence(),
        "uncertainties": [],
        "remediation_actions": [],
        "parsed_fields": {"region": "EU", "data_types": ["Personal"], "cross_border": False},
        "jurisdictions_covered": ["EU"],
        "requires_escalation": False,
        "escalation_result": None,
        "disclaimer": "免责声明文本",
    }

    try:
        report = AuditReport.model_validate(payload)
    except ValidationError as exc:  # pragma: no cover
        raise AssertionError(f"Unexpected validation error: {exc}") from exc
    assert report.session_id == "s-3"
