"""Evaluation harness for retrieval mode."""

from __future__ import annotations

import argparse
import csv
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.schemas import ParsedFields
from app.rag.retriever.hybrid import hybrid_search


DEFAULT_RETRIEVAL_CASES = ROOT / "eval" / "test_cases" / "retrieval_tests.csv"
DEFAULT_RESULTS_PATH = ROOT / "eval" / "results.csv"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run evaluation harness.")
    parser.add_argument(
        "--mode",
        required=True,
        choices=["retrieval"],
        help="Evaluation mode.",
    )
    parser.add_argument(
        "--cases",
        default=str(DEFAULT_RETRIEVAL_CASES),
        help="CSV file containing evaluation cases.",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_RESULTS_PATH),
        help="CSV file where per-case results are written.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.mode != "retrieval":
        raise ValueError(f"Unsupported mode: {args.mode}")
    run_retrieval_eval(Path(args.cases), Path(args.output))


def run_retrieval_eval(cases_path: Path, output_path: Path) -> None:
    if not cases_path.exists():
        raise FileNotFoundError(f"Test case file not found: {cases_path}")

    rows = list(csv.DictReader(cases_path.open(encoding="utf-8")))
    if not rows:
        raise ValueError(f"No retrieval test cases found in {cases_path}")

    results: list[dict[str, object]] = []
    top5_hits = 0
    bilingual_hits = 0
    bilingual_total = 0
    rerank_scores: list[float] = []

    for row in rows:
        query = row["query"].strip()
        expected_regulation = row["expected_regulation"].strip()
        expected_article_id = row["expected_article_id"].strip()
        jurisdiction = row["jurisdiction"].strip()
        parsed_fields = _build_parsed_fields(query=query, jurisdiction=jurisdiction)

        try:
            retrieved = hybrid_search(query=query, parsed_fields=parsed_fields, top_k=5)
            actual_ids = [item.article_id for item in retrieved]
            hit_top5 = any(_article_id_matches(expected_article_id, aid) for aid in actual_ids)
            top1 = retrieved[0] if retrieved else None
            top1_regulation = top1.regulation if top1 else ""
            top1_article_id = top1.article_id if top1 else ""
            top1_rerank_score = top1.rerank_score if top1 and top1.rerank_score is not None else 0.0
            rerank_scores.append(float(top1_rerank_score))
            error = ""
        except Exception as exc:
            retrieved = []
            actual_ids = []
            hit_top5 = False
            top1_regulation = ""
            top1_article_id = ""
            top1_rerank_score = 0.0
            error = f"{type(exc).__name__}: {exc}"

        if hit_top5:
            top5_hits += 1

        is_bilingual_case = _contains_cjk(query) and jurisdiction == "EU"
        if is_bilingual_case:
            bilingual_total += 1
            if hit_top5:
                bilingual_hits += 1

        results.append(
            {
                "query": query,
                "expected_regulation": expected_regulation,
                "expected_article_id": expected_article_id,
                "jurisdiction": jurisdiction,
                "top_hit_regulation": top1_regulation,
                "top_hit_article_id": top1_article_id,
                "hit_top5": int(hit_top5),
                "top1_rerank_score": round(float(top1_rerank_score), 4),
                "returned_count": len(retrieved),
                "error": error,
            }
        )

    _write_results(output_path, results)

    total_cases = len(rows)
    hit_rate = top5_hits / total_cases if total_cases else 0.0
    avg_rerank = statistics.mean(rerank_scores) if rerank_scores else 0.0
    bilingual_hit_rate = bilingual_hits / bilingual_total if bilingual_total else 0.0

    print(f"cases={total_cases}")
    print(f"top5_hit_rate={hit_rate:.2%}")
    print(f"avg_rerank_score={avg_rerank:.4f}")
    print(f"bilingual_hit_rate={bilingual_hit_rate:.2%}")
    print(f"results_csv={output_path}")


def _build_parsed_fields(*, query: str, jurisdiction: str) -> ParsedFields:
    region = _jurisdiction_to_region(jurisdiction)
    query_lower = query.lower()

    data_types: list[str] = []
    if any(term in query_lower for term in ("biometric", "face", "facial")) or any(
        term in query for term in ("生物特征", "人脸")
    ):
        data_types.append("Biometric")
    elif any(term in query_lower for term in ("personal", "consent", "privacy")) or any(
        term in query for term in ("个人信息", "同意")
    ):
        data_types.append("Personal")

    return ParsedFields(
        region=region,
        data_types=data_types or None,
        cross_border=_matches_any(query_lower, query, ("cross-border", "transfer", "third country"), ("跨境", "出境", "境外", "第三国")),
        third_party_model=_matches_any(query_lower, query, ("third party", "external", "vendor", "processor"), ("第三方", "外部", "处理者", "供应商")),
        aigc_output=_matches_any(query_lower, query, ("generate", "synthetic", "chatbot", "deepfake"), ("生成", "合成", "标识", "聊天机器人")),
    )


def _jurisdiction_to_region(jurisdiction: str) -> str:
    if jurisdiction == "EU":
        return "EU"
    if jurisdiction == "CN":
        return "CN"
    return "Global"


def _matches_any(query_lower: str, query_original: str, en_terms: tuple[str, ...], zh_terms: tuple[str, ...]) -> bool:
    if any(term in query_lower for term in en_terms):
        return True
    if any(term in query_original for term in zh_terms):
        return True
    return False


def _contains_cjk(text: str) -> bool:
    return any("\u4e00" <= ch <= "\u9fff" for ch in text)


def _article_id_matches(expected: str, actual: str) -> bool:
    """Match article IDs, treating split chunks (Article_28_1) as equivalent to base (Article 28)."""
    if expected == actual:
        return True
    # Normalize: replace underscores with spaces, strip trailing part number
    import re
    normalized = re.sub(r"\s*_?\d+$", "", actual.replace("_", " ")).strip()
    return expected == normalized


def _write_results(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "query",
        "expected_regulation",
        "expected_article_id",
        "jurisdiction",
        "top_hit_regulation",
        "top_hit_article_id",
        "hit_top5",
        "top1_rerank_score",
        "returned_count",
        "error",
    ]
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()

