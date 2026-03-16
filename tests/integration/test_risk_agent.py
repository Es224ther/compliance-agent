import asyncio

from app.agents.risk_agent import MAX_REACT_STEPS, MAX_RETRIEVAL_ACTIONS, RiskAgent
from app.schemas.evidence import EvidenceChunk
from app.schemas.risk import RiskLevel
from app.schemas.scenario import ParsedFields


def _chunk(
    *,
    regulation: str,
    article: str,
    jurisdiction: str,
    text: str,
    summary: str,
    score: float = 0.9,
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


def test_risk_agent_scenario_a() -> None:
    class StubRetriever:
        def __init__(self) -> None:
            self.calls = 0

        def __call__(self, query: str, parsed_fields: ParsedFields) -> list[EvidenceChunk]:
            self.calls += 1
            if self.calls == 1:
                return [
                    _chunk(
                        regulation="GDPR",
                        article="Art.46",
                        jurisdiction="EU",
                        text="Standard Contractual Clauses are a transfer safeguard.",
                        summary="EU transfer safeguard",
                    ),
                    _chunk(
                        regulation="GDPR",
                        article="Art.44",
                        jurisdiction="EU",
                        text="cross-border transfer to third country needs safeguards.",
                        summary="EU transfer conditions",
                    ),
                ]
            return [
                _chunk(
                    regulation="PIPL",
                    article="第38条",
                    jurisdiction="CN",
                    text="数据出境安全评估与个人信息保护要求。",
                    summary="CN outflow requirements",
                ),
                _chunk(
                    regulation="GDPR",
                    article="Art.46",
                    jurisdiction="EU",
                    text="Standard Contractual Clauses are a transfer safeguard.",
                    summary="EU transfer safeguard",
                ),
            ]

    parsed = ParsedFields(
        region="EU+CN",
        data_types=["Biometric", "Personal"],
        cross_border=True,
        third_party_model=True,
        aigc_output=False,
    )

    agent = RiskAgent(retriever=StubRetriever())
    result = asyncio.run(agent.run(parsed))

    assert result.risk_level == RiskLevel.CRITICAL
    assert any(chunk.regulation == "GDPR" for chunk in result.evidence)
    assert any(chunk.regulation == "PIPL" for chunk in result.evidence)
    assert "【EU 合规要求】" in result.reasoning
    assert "【CN 合规要求】" in result.reasoning
    assert any(factor["rule"] == "biometric_force_critical" for factor in result.scoring_factors)
    assert agent.last_react_steps <= MAX_REACT_STEPS
    assert agent.last_retrieval_actions <= MAX_RETRIEVAL_ACTIONS
