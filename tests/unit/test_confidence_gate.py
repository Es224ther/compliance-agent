from guards.confidence_gate import evaluate_confidence
from schemas.evidence import EvidenceChunk
from schemas.scenario import ParsedFields


def _chunk(
    *,
    regulation: str,
    article: str,
    jurisdiction: str,
    score: float,
    tags: list[str],
) -> EvidenceChunk:
    return EvidenceChunk(
        regulation=regulation,
        article=article,
        jurisdiction=jurisdiction,
        text=f"{regulation} text",
        summary=f"{regulation} summary",
        rerank_score=score,
        tags=tags,
    )


def test_low_confidence_empty_evidence() -> None:
    parsed = ParsedFields(region="EU", data_types=["Personal"], cross_border=True)
    result = evaluate_confidence([], parsed)

    assert result.low_confidence is True
    assert "all_scores_below_threshold" in result.triggered_conditions


def test_cross_jurisdiction_completeness() -> None:
    parsed = ParsedFields(
        region="EU+CN",
        data_types=["Personal"],
        cross_border=True,
    )
    evidence = [
        _chunk(
            regulation="GDPR",
            article="Art.46",
            jurisdiction="EU",
            score=0.8,
            tags=["cross_border_transfer"],
        )
    ]
    result = evaluate_confidence(evidence, parsed)

    assert result.low_confidence is True
    assert "eu_cn_single_jurisdiction" in result.triggered_conditions
    assert "单一法域" in (result.reason or "")


def test_confidence_gate_triggers_escalation() -> None:
    parsed = ParsedFields(
        region="EU",
        data_types=["Personal"],
        cross_border=True,
        missing_fields=["region", "data_types"],
    )
    evidence = [
        _chunk(regulation="GDPR", article="Art.13", jurisdiction="EU", score=0.4, tags=["a"]),
        _chunk(regulation="PIPL", article="第13条", jurisdiction="CN", score=0.5, tags=["b"]),
        _chunk(regulation="AI Act", article="Art.9", jurisdiction="EU", score=0.2, tags=["c"]),
    ]
    result = evaluate_confidence(evidence, parsed)

    assert result.low_confidence is True
    assert len(result.triggered_conditions) >= 2
    assert result.reason is not None
