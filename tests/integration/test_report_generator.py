import asyncio

from processors.report_generator import generate_report
from schemas.evidence import EvidenceChunk
from schemas.report import AuditReport
from schemas.risk import EscalationResult, RemediationAction, RiskAssessment, RiskLevel
from schemas.scenario import ParsedFields, ScenarioInput
from schemas.state import SharedState


def _scenario_a_state() -> tuple[SharedState, RiskAssessment, EscalationResult]:
    evidence = [
        EvidenceChunk(
            regulation="GDPR",
            article="Art.46",
            jurisdiction="EU",
            text="SCC obligations for transfer.",
            summary="EU transfer safeguard",
            rerank_score=0.9,
            tags=["cross_border_transfer"],
        ),
        EvidenceChunk(
            regulation="PIPL",
            article="第38条",
            jurisdiction="CN",
            text="数据出境安全评估要求。",
            summary="CN security assessment requirement",
            rerank_score=0.88,
            tags=["cross_border_transfer"],
        ),
    ]
    risk = RiskAssessment(
        risk_level=RiskLevel.CRITICAL,
        risk_summary="贵司必须立即处理跨境生物特征数据流程。",
        reasoning=(
            "【EU 合规要求】\n基于 GDPR Art.46 ...\n\n"
            "【CN 合规要求】\n基于 PIPL 第38条 ...\n\n"
            "【跨法域注意事项】\n两套义务并行。"
        ),
        jurisdictions_covered=["EU", "CN"],
        evidence=evidence,
        remediation=[
            RemediationAction(
                role="PM",
                action="贵司必须立即建立跨境流程台账。",
                priority="Immediate",
                regulation_ref="GDPR Art.46",
            ),
            RemediationAction(
                role="Dev",
                action="必须立即增加传输审计日志。",
                priority="Immediate",
                regulation_ref="PIPL 第38条",
            ),
            RemediationAction(
                role="Security",
                action="must immediately trigger legal review workflow.",
                priority="Immediate",
                regulation_ref="PIPL 第38条",
            ),
        ],
        low_confidence_items=[],
        requires_escalation=True,
        scoring_factors=[
            {
                "rule": "biometric_force_critical",
                "description": "Biometric data present → force Critical",
                "impact": "force Critical",
            }
        ],
    )
    escalation = EscalationResult(
        requires_escalation=True,
        reasons=["高风险场景（Critical），需人工法务复核"],
    )
    state = SharedState(
        session_id="scenario-a",
        raw_input=ScenarioInput(
            raw_text="我们在 EU+CN 处理人脸数据并跨境训练模型。",
            session_id="scenario-a",
        ),
        parsed_fields=ParsedFields(
            region="EU+CN",
            data_types=["Biometric"],
            cross_border=True,
            third_party_model=True,
        ),
    )
    return state, risk, escalation


def test_report_generator_scenario_a_contract() -> None:
    state, risk, escalation = _scenario_a_state()
    report = asyncio.run(generate_report(state, risk, escalation))

    markdown = report.to_markdown()
    assert markdown.count(report.disclaimer) == 2
    assert report.evidence_citations[0].text == "SCC obligations for transfer."
    assert report.evidence_citations[1].text == "数据出境安全评估要求。"
    assert "建议贵司" in report.risk_overview
    assert "系统已完成" not in report.summary
    assert "已关联法规证据" not in report.summary
    assert "。。" not in report.summary
    assert len(report.summary) <= 100

    payload = report.to_json()
    validated = AuditReport.model_validate(payload)
    assert validated.session_id == "scenario-a"
