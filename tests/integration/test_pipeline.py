import asyncio

from app.agents.base import AgentOutput
from app.agents.intake_agent import IntakeResult
from app.orchestrator.pipeline import run_pipeline
from app.orchestrator import pipeline as pipeline_module
from app.schemas.report import AuditReport
from app.schemas.risk import RiskLevel
from app.schemas.scenario import ParsedFields, ScenarioInput
from app.schemas.state import SharedState
from app.schemas.state import PipelineStatus

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
    assert state.followup_questions[0].field == "region"
    assert state.followup_questions[0].options[0].startswith("A.")


def test_report_schema_contract(mock_llm, mock_rag):
    state = asyncio.run(run_pipeline(SCENARIO_B_INPUT))
    assert state.report is not None
    report_json = state.report.to_json()
    AuditReport.model_validate(report_json)


def test_pipeline_emits_completed_events_for_risk_and_report(mock_llm, mock_rag):
    events: list[dict[str, str]] = []

    async def _capture(event: dict[str, str]) -> None:
        events.append(event)

    state = asyncio.run(run_pipeline(SCENARIO_B_INPUT, progress_callback=_capture))

    assert state.status == PipelineStatus.COMPLETED
    assert any(e.get("step") == "risk_analysis" and e.get("status") == "completed" for e in events)
    assert any(e.get("step") == "report_generation" and e.get("status") == "completed" for e in events)


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


def test_uncertainties_auto_filled_for_null_fields_and_hedging(monkeypatch, mock_rag):
    class _StubIntakeAgent:
        def run(self, context):
            if isinstance(context, SharedState):
                scenario = context.raw_input or ScenarioInput(raw_text="")
            else:
                scenario = context

            parsed = ParsedFields(
                region="EU+CN",
                data_types=["Personal", "Biometric"],
                cross_border=True,
                third_party_model=False,
                aigc_output=None,
                data_volume_level=None,
            )
            shared_state = SharedState(
                session_id=scenario.session_id,
                raw_input=scenario,
                parsed_fields=parsed,
                followup_rounds=0,
                followup_prompt=None,
                missing_fields=[],
            )
            output = IntakeResult(
                parsed_fields=parsed,
                invalid_fields=[],
                missing_fields=[],
                requires_followup=False,
                followup_prompt=None,
                shared_state=shared_state,
                raw_tool_input={},
            )
            return AgentOutput(final_output=output, steps=1)

    stub = _StubIntakeAgent()
    monkeypatch.setattr(pipeline_module, "_intake_agent_instance", stub)
    monkeypatch.setattr(pipeline_module, "_get_intake_agent", lambda: stub)

    scenario = ScenarioInput(
        raw_text=(
            "我们计划把欧洲用户视频传回国内训练模型，视频中可能包含用户人脸。"
            "AIGC 是否对外展示暂时不确定。"
        ),
        session_id="scenario-uncertainty",
    )
    state = asyncio.run(run_pipeline(scenario))

    assert state.report is not None
    uncertainty_text = " ".join(state.report.uncertainties)
    assert "[aigc_output]" in uncertainty_text
    assert "[data_volume_level]" in uncertainty_text
    assert "可能" in uncertainty_text


def test_pipeline_failure_handling(mock_llm_raises):
    state = asyncio.run(run_pipeline(SCENARIO_A_INPUT))
    assert state.status == PipelineStatus.FAILED
    assert state.error is not None
    assert state.report is None
