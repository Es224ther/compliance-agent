from app.schemas.evidence import EvidenceChunk
from app.schemas.risk import RiskLevel
from app.schemas.scenario import ParsedFields
from app.tools.risk_scorer import calculate_risk_level


def _chunk(
    *,
    regulation: str,
    article: str,
    jurisdiction: str,
    text: str,
    summary: str,
    rerank_score: float = 0.8,
    tags: list[str] | None = None,
) -> EvidenceChunk:
    return EvidenceChunk(
        regulation=regulation,
        article=article,
        jurisdiction=jurisdiction,
        text=text,
        summary=summary,
        rerank_score=rerank_score,
        tags=tags or [],
    )


def test_scenario_a() -> None:
    evidence = [
        _chunk(
            regulation="GDPR",
            article="Art.46",
            jurisdiction="EU",
            text="Standard Contractual Clauses required for transfer.",
            summary="EU transfer safeguard",
        ),
        _chunk(
            regulation="PIPL",
            article="Art.38",
            jurisdiction="CN",
            text="数据出境安全评估和生物特征处理要求。",
            summary="CN cross-border requirement",
        ),
    ]
    parsed = ParsedFields(
        region="EU+CN",
        data_types=["Biometric", "Personal"],
        cross_border=True,
        third_party_model=True,
        aigc_output=False,
    )

    risk_level, _, _ = calculate_risk_level(evidence, parsed)
    assert risk_level == RiskLevel.CRITICAL


def test_scenario_b() -> None:
    evidence = [
        _chunk(
            regulation="GDPR",
            article="Art.44",
            jurisdiction="EU",
            text="cross-border transfer to third country needs safeguards.",
            summary="transfer restriction",
        ),
    ]
    parsed = ParsedFields(
        region="EU",
        data_types=["Personal"],
        cross_border=False,
        third_party_model=True,
        aigc_output=False,
    )

    risk_level, _, _ = calculate_risk_level(evidence, parsed)
    assert risk_level == RiskLevel.HIGH


def test_scenario_c() -> None:
    evidence = [
        _chunk(
            regulation="GDPR",
            article="Art.13",
            jurisdiction="EU",
            text="transparency and consent requirements apply.",
            summary="EU transparency",
        ),
        _chunk(
            regulation="AIGC 标识办法",
            article="第4条",
            jurisdiction="CN",
            text="生成式内容应进行标识管理。",
            summary="CN AIGC requirement",
        ),
    ]
    parsed = ParsedFields(
        region="EU+CN",
        data_types=["Personal"],
        cross_border=False,
        third_party_model=False,
        aigc_output=True,
    )

    risk_level, _, _ = calculate_risk_level(evidence, parsed)
    assert risk_level in {RiskLevel.HIGH, RiskLevel.CRITICAL}


def test_deterministic() -> None:
    evidence = [
        _chunk(
            regulation="GDPR",
            article="Art.13",
            jurisdiction="EU",
            text="consent and transparency obligations.",
            summary="medium controls",
        ),
    ]
    parsed = ParsedFields(
        region="EU",
        data_types=["Personal"],
        cross_border=False,
        third_party_model=False,
        aigc_output=False,
    )

    first = calculate_risk_level(evidence, parsed)
    for _ in range(5):
        assert calculate_risk_level(evidence, parsed) == first


def test_biometric_force_critical() -> None:
    evidence = [
        _chunk(
            regulation="GDPR",
            article="Art.13",
            jurisdiction="EU",
            text="consent and transparency obligations.",
            summary="medium controls",
        ),
    ]
    parsed = ParsedFields(
        region="EU",
        data_types=["Biometric"],
        cross_border=False,
        third_party_model=False,
        aigc_output=False,
    )

    risk_level, _, factors = calculate_risk_level(evidence, parsed)
    assert risk_level == RiskLevel.CRITICAL
    assert any(item["rule"] == "biometric_force_critical" for item in factors)
