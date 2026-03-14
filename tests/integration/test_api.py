import asyncio
import time

import pytest
from fastapi.testclient import TestClient

from app.api.middleware import reset_rate_limit_buckets
from app.api import routes
from app.api.store import store
from app.main import app
from schemas.evidence import EvidenceChunk
from schemas.report import AuditReport
from schemas.risk import EscalationResult, RemediationAction, RiskLevel
from schemas.scenario import ParsedFields, ScenarioInput
from schemas.state import PipelineStatus, SharedState


@pytest.fixture(autouse=True)
def clear_api_store():
    asyncio.run(store.clear())
    reset_rate_limit_buckets()
    yield
    asyncio.run(store.clear())
    reset_rate_limit_buckets()


def _build_report(session_id: str, report_id: str, risk_level: RiskLevel = RiskLevel.HIGH) -> AuditReport:
    return AuditReport(
        report_id=report_id,
        session_id=session_id,
        summary="场景摘要",
        risk_level=risk_level,
        risk_overview=f"{risk_level.value} 风险概述",
        evidence_citations=[
            EvidenceChunk(
                regulation="GDPR",
                article="Art.46",
                jurisdiction="EU",
                text="SCC safeguard",
                summary="EU safeguard",
                rerank_score=0.9,
                tags=["cross_border_transfer"],
            )
        ],
        uncertainties=[],
        remediation_actions=[
            RemediationAction(
                role="PM",
                action="补充合规说明",
                priority="Immediate",
                regulation_ref="GDPR Art.46",
            )
        ],
        parsed_fields=ParsedFields(region="EU", data_types=["Personal"], cross_border=True),
        jurisdictions_covered=["EU"],
        requires_escalation=risk_level == RiskLevel.CRITICAL,
        escalation_result=EscalationResult(requires_escalation=False, reasons=[]),
        disclaimer="免责声明",
    )


def _completed_state(session_id: str, report_id: str, risk_level: RiskLevel = RiskLevel.HIGH) -> SharedState:
    report = _build_report(session_id, report_id, risk_level=risk_level)
    return SharedState(
        session_id=session_id,
        report_id=report_id,
        raw_input=ScenarioInput(raw_text="测试场景", session_id=session_id),
        status=PipelineStatus.COMPLETED,
        parsed_fields=report.parsed_fields,
        report=report,
    )


def test_analyze_and_get_report(monkeypatch):
    async def stub_run_pipeline(scenario_input, on_progress=None, progress_callback=None, report_id=None):
        if progress_callback is not None:
            await progress_callback(
                {"step": "completed", "status": "completed", "message": "报告生成完成", "data": {"report_id": report_id}}
            )
        return _completed_state(scenario_input.session_id, report_id)

    monkeypatch.setattr(routes, "run_pipeline", stub_run_pipeline)

    with TestClient(app) as client:
        response = client.post("/api/v1/analyze", json={"scenario_text": "我们计划把欧洲用户素材传回国内训练模型。"})
        assert response.status_code == 202
        payload = response.json()
        assert payload["status"] == "processing"

        time.sleep(0.05)
        markdown_response = client.get(f"/api/v1/reports/{payload['report_id']}")
        assert markdown_response.status_code == 200
        assert "## 场景摘要" in markdown_response.text

        json_response = client.get(f"/api/v1/reports/{payload['report_id']}?format=json")
        assert json_response.status_code == 200
        assert json_response.json()["report_id"] == payload["report_id"]


def test_report_feedback_and_listing(monkeypatch):
    async def stub_run_pipeline(scenario_input, on_progress=None, progress_callback=None, report_id=None):
        return _completed_state(scenario_input.session_id, report_id, risk_level=RiskLevel.CRITICAL)

    monkeypatch.setattr(routes, "run_pipeline", stub_run_pipeline)

    with TestClient(app) as client:
        first = client.post("/api/v1/analyze", json={"scenario_text": "场景一"}).json()
        second = client.post("/api/v1/analyze", json={"scenario_text": "场景二"}).json()
        time.sleep(0.05)

        feedback_response = client.patch(
            f"/api/v1/reports/{first['report_id']}/feedback",
            json={"section": "整改建议", "rating": "helpful", "comment": "可执行"},
        )
        assert feedback_response.status_code == 204

        list_response = client.get("/api/v1/reports?risk_level=Critical")
        assert list_response.status_code == 200
        report_ids = [item["report_id"] for item in list_response.json()]
        assert first["report_id"] in report_ids
        assert second["report_id"] in report_ids


def test_rate_limit(monkeypatch):
    async def stub_run_pipeline(scenario_input, on_progress=None, progress_callback=None, report_id=None):
        return _completed_state(scenario_input.session_id, report_id)

    monkeypatch.setattr(routes, "run_pipeline", stub_run_pipeline)

    with TestClient(app) as client:
        for _ in range(10):
            response = client.post("/api/v1/analyze", json={"scenario_text": "限流测试文本，长度超过二十字。"})
            assert response.status_code == 202
        blocked = client.post("/api/v1/analyze", json={"scenario_text": "限流测试文本，长度超过二十字。"})
        assert blocked.status_code == 429


def test_websocket_progress_replay(monkeypatch):
    async def stub_run_pipeline(scenario_input, on_progress=None, progress_callback=None, report_id=None):
        assert progress_callback is not None
        await progress_callback({"step": "pii_sanitization", "status": "running", "message": "正在进行数据脱敏..."})
        await progress_callback({"step": "completed", "status": "completed", "message": "报告生成完成", "data": {"report_id": report_id}})
        return _completed_state(scenario_input.session_id, report_id)

    monkeypatch.setattr(routes, "run_pipeline", stub_run_pipeline)

    with TestClient(app) as client:
        analyze = client.post("/api/v1/analyze", json={"scenario_text": "WebSocket 测试文本，长度超过二十字。"}).json()
        time.sleep(0.05)
        with client.websocket_connect(f"/ws/{analyze['session_id']}") as websocket:
            first = websocket.receive_json()
            second = websocket.receive_json()

        assert first["step"] == "pii_sanitization"
        assert second["step"] == "completed"
