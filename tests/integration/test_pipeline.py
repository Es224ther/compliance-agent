import asyncio

from orchestrator.pipeline import run_pipeline
from schemas.report import AuditReport
from schemas.risk import RiskLevel
from schemas.scenario import ScenarioInput
from schemas.state import PipelineStatus

SCENARIO_A_INPUT = ScenarioInput(
    raw_text="我们在 EU+CN 处理人脸数据并跨境训练第三方模型，输出 AIGC 内容。",
    session_id="scenario-a",
)
SCENARIO_B_INPUT = ScenarioInput(
    raw_text="EU 团队调用第三方模型处理用户个人数据，并进行跨境访问。",
    session_id="scenario-b",
)
VAGUE_INPUT = ScenarioInput(
    raw_text="这是一个模糊描述，没有法域和数据类型。",
    session_id="scenario-vague",
)


def test_pipeline_scenario_a(mock_llm, mock_rag):
    state = asyncio.run(run_pipeline(SCENARIO_A_INPUT))
    assert state.status == PipelineStatus.COMPLETED
    assert state.report is not None
    assert state.report.risk_level == RiskLevel.CRITICAL
    assert state.report.requires_escalation is True
    assert "高风险提示" in state.report.disclaimer
    assert len(state.report.evidence_citations) >= 2
    assert len(state.report.remediation_actions) >= 3
    assert {"EU", "CN"}.issubset(set(state.report.jurisdictions_covered))


def test_pipeline_awaiting_followup(mock_llm):
    state = asyncio.run(run_pipeline(VAGUE_INPUT))
    assert state.status == PipelineStatus.AWAITING_FOLLOWUP
    assert state.followup_questions is not None


def test_report_schema_contract(mock_llm, mock_rag):
    state = asyncio.run(run_pipeline(SCENARIO_B_INPUT))
    assert state.report is not None
    report_json = state.report.to_json()
    AuditReport.model_validate(report_json)


def test_escalation_priority(mock_llm, mock_rag_critical):
    state = asyncio.run(run_pipeline(SCENARIO_A_INPUT))
    escalation = state.escalation_result
    assert escalation is not None
    assert escalation.requires_escalation is True
    assert "Critical" in escalation.primary_reason
    assert len(escalation.reasons) >= 2


def test_cross_jurisdiction_eu_cn(mock_llm, mock_rag_eu_only):
    state = asyncio.run(run_pipeline(SCENARIO_A_INPUT))
    assert state.report is not None
    assert state.report.requires_escalation is True
    uncertainty_text = " ".join(state.report.uncertainties)
    assert "单一法域" in uncertainty_text or "EU" in uncertainty_text


def test_pipeline_failure_handling(mock_llm_raises):
    state = asyncio.run(run_pipeline(SCENARIO_A_INPUT))
    assert state.status == PipelineStatus.FAILED
    assert state.error is not None
    assert state.report is None
