from types import SimpleNamespace

import pytest

from agents.base import AgentOutput
from agents.intake_agent import IntakeResult
from agents.risk_agent import RiskAgent
from schemas.evidence import EvidenceChunk
from schemas.risk import RemediationAction, RiskAssessment, RiskLevel
from schemas.scenario import ParsedFields, ScenarioInput
from schemas.state import SharedState

class StubMessagesAPI:
    def __init__(self, response: object | None = None) -> None:
        self.response = response
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.response is None:
            raise AssertionError("Stub LLM response was not configured.")
        return self.response


class StubAnthropicClient:
    def __init__(self, response: object | None = None) -> None:
        self.messages = StubMessagesAPI(response=response)


@pytest.fixture
def mock_llm_client(monkeypatch):
    client = StubAnthropicClient()

    def _set_response(payload: dict) -> StubAnthropicClient:
        client.messages.response = SimpleNamespace(
            content=[
                SimpleNamespace(
                    type="tool_use",
                    name="parse_scenario",
                    input=payload,
                )
            ]
        )
        return client

    monkeypatch.setattr("agents.intake_agent.get_client", lambda: client)
    return _set_response


class _StubIntakeAgent:
    def __init__(self, *, should_raise: bool = False) -> None:
        self.should_raise = should_raise

    def run(self, context):
        if self.should_raise:
            raise RuntimeError("mock llm failed")

        if isinstance(context, SharedState):
            scenario = context.raw_input or ScenarioInput(raw_text="")
        elif isinstance(context, ScenarioInput):
            scenario = context
        else:
            scenario = ScenarioInput(raw_text=str(context))

        text = scenario.raw_text
        if "模糊" in text or "vague" in text.lower():
            parsed = ParsedFields(
                region=None,
                data_types=None,
                cross_border=None,
                missing_fields=["region", "data_types", "cross_border"],
            )
            followup = "1. 请补充法域\n2. 请补充数据类型\n3. 请说明是否跨境"
            shared_state = SharedState(
                session_id=scenario.session_id,
                raw_input=scenario,
                parsed_fields=parsed,
                followup_rounds=1,
                followup_prompt=followup,
                missing_fields=["region", "data_types", "cross_border"],
            )
            output = IntakeResult(
                parsed_fields=parsed,
                invalid_fields=[],
                missing_fields=shared_state.missing_fields,
                requires_followup=True,
                followup_prompt=followup,
                shared_state=shared_state,
                raw_tool_input={},
            )
            return AgentOutput(final_output=output, steps=1)

        if "EU+CN" in text or "人脸" in text or "biometric" in text.lower():
            parsed = ParsedFields(
                region="EU+CN",
                data_types=["Biometric", "Personal"],
                cross_border=True,
                third_party_model=True,
                aigc_output=True,
                missing_fields=["region", "data_types"],
            )
        else:
            parsed = ParsedFields(
                region="EU",
                data_types=["Personal"],
                cross_border=True,
                third_party_model=True,
                aigc_output=False,
                missing_fields=[],
            )

        shared_state = SharedState(
            session_id=scenario.session_id,
            raw_input=scenario,
            parsed_fields=parsed,
            followup_rounds=0,
            followup_prompt=None,
            missing_fields=parsed.missing_fields or [],
        )
        output = IntakeResult(
            parsed_fields=parsed,
            invalid_fields=[],
            missing_fields=shared_state.missing_fields,
            requires_followup=False,
            followup_prompt=None,
            shared_state=shared_state,
            raw_tool_input={},
        )
        return AgentOutput(final_output=output, steps=1)


def _build_risk_agent(
    retriever_fn,
):
    return RiskAgent(retriever=retriever_fn)


def _chunk(
    *,
    regulation: str,
    article: str,
    jurisdiction: str,
    text: str,
    summary: str,
    score: float,
) -> EvidenceChunk:
    return EvidenceChunk(
        regulation=regulation,
        article=article,
        jurisdiction=jurisdiction,
        text=text,
        summary=summary,
        rerank_score=score,
        tags=["cross_border_transfer"],
    )


@pytest.fixture
def mock_llm(monkeypatch):
    from orchestrator import pipeline as pipeline_module

    stub = _StubIntakeAgent()
    monkeypatch.setattr(pipeline_module, "_intake_agent_instance", stub)
    monkeypatch.setattr(pipeline_module, "_get_intake_agent", lambda: stub)
    return stub


@pytest.fixture
def mock_llm_raises(monkeypatch):
    from orchestrator import pipeline as pipeline_module

    stub = _StubIntakeAgent(should_raise=True)
    monkeypatch.setattr(pipeline_module, "_intake_agent_instance", stub)
    monkeypatch.setattr(pipeline_module, "_get_intake_agent", lambda: stub)
    return stub


@pytest.fixture
def mock_rag(monkeypatch):
    from orchestrator import pipeline as pipeline_module

    def retriever(query: str, parsed_fields: ParsedFields) -> list[EvidenceChunk]:
        return [
            _chunk(
                regulation="GDPR",
                article="Art.46",
                jurisdiction="EU",
                text="Standard Contractual Clauses required.",
                summary="EU safeguards",
                score=0.91,
            ),
            _chunk(
                regulation="PIPL",
                article="第38条",
                jurisdiction="CN",
                text="数据出境安全评估要求。",
                summary="CN safeguards",
                score=0.87,
            ),
            _chunk(
                regulation="GDPR",
                article="Art.44",
                jurisdiction="EU",
                text="cross-border transfer to third country.",
                summary="EU transfer rule",
                score=0.85,
            ),
        ]

    risk_agent = _build_risk_agent(retriever)
    monkeypatch.setattr(pipeline_module, "_risk_agent_instance", risk_agent)
    monkeypatch.setattr(pipeline_module, "_get_risk_agent", lambda: risk_agent)
    return retriever


@pytest.fixture
def mock_rag_critical(monkeypatch):
    from orchestrator import pipeline as pipeline_module

    def retriever(query: str, parsed_fields: ParsedFields) -> list[EvidenceChunk]:
        return [
            _chunk(
                regulation="GDPR",
                article="Art.46",
                jurisdiction="EU",
                text="Standard Contractual Clauses for biometric transfers.",
                summary="EU safeguard",
                score=0.45,
            ),
            _chunk(
                regulation="PIPL",
                article="第38条",
                jurisdiction="CN",
                text="数据出境安全评估覆盖生物特征。",
                summary="CN safeguard",
                score=0.4,
            ),
            _chunk(
                regulation="AI Act",
                article="Art.9",
                jurisdiction="EU",
                text="risk management requirements.",
                summary="EU AI obligations",
                score=0.35,
            ),
        ]

    risk_agent = _build_risk_agent(retriever)
    monkeypatch.setattr(pipeline_module, "_risk_agent_instance", risk_agent)
    monkeypatch.setattr(pipeline_module, "_get_risk_agent", lambda: risk_agent)
    return retriever


@pytest.fixture
def mock_rag_eu_only(monkeypatch):
    from orchestrator import pipeline as pipeline_module

    def retriever(query: str, parsed_fields: ParsedFields) -> list[EvidenceChunk]:
        return [
            _chunk(
                regulation="GDPR",
                article="Art.46",
                jurisdiction="EU",
                text="SCC safeguard for transfers.",
                summary="EU safeguard",
                score=0.92,
            ),
            _chunk(
                regulation="GDPR",
                article="Art.13",
                jurisdiction="EU",
                text="transparency obligation.",
                summary="EU transparency",
                score=0.81,
            ),
            _chunk(
                regulation="GDPR",
                article="Art.44",
                jurisdiction="EU",
                text="third country transfer condition.",
                summary="EU transfer condition",
                score=0.8,
            ),
        ]

    risk_agent = _build_risk_agent(retriever)
    monkeypatch.setattr(pipeline_module, "_risk_agent_instance", risk_agent)
    monkeypatch.setattr(pipeline_module, "_get_risk_agent", lambda: risk_agent)
    return retriever
