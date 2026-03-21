"""RAG retrieval evaluator: measures Top-5 hit rate and bilingual search quality."""

from __future__ import annotations

import csv
import json
import statistics
from datetime import datetime
from pathlib import Path
from typing import Any

import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.schemas import ParsedFields
from app.rag.retriever.hybrid import hybrid_search
from app.config.settings import get_settings

TARGET_HIT_RATE = 0.70
TARGET_CROSS_LINGUAL_HIT_RATE = 0.60

EU_REGULATIONS = {"GDPR", "EU AI ACT", "EU AI ACT"}


def _jurisdiction_to_region(jurisdiction: str) -> str:
    j = jurisdiction.upper()
    if j == "EU":
        return "EU"
    if j == "CN":
        return "CN"
    return "Global"


def _contains_cjk(text: str) -> bool:
    return any("\u4e00" <= ch <= "\u9fff" for ch in text)


def _fuzzy_regulation_match(expected: str, actual: str) -> bool:
    """expected in actual (case-insensitive)."""
    return expected.lower() in actual.lower()


def _fuzzy_article_match(expected: str, actual: str | None) -> bool:
    """Fuzzy article ID match: normalize separators then check containment."""
    if actual is None:
        return False
    import re
    # Normalize: underscores/hyphens → spaces, collapse whitespace, strip trailing part numbers
    def _norm(s: str) -> str:
        s = s.lower().replace("_", " ").replace("-", " ")
        s = re.sub(r"\s+", " ", s).strip()
        return s
    exp_norm = _norm(expected)
    act_norm = _norm(actual)
    # Also try stripping trailing sub-chunk numbers (e.g. "article 28 1" → "article 28")
    act_base = re.sub(r"\s+\d+$", "", act_norm)
    return (
        exp_norm in act_norm
        or act_norm in exp_norm
        or exp_norm == act_base
    )


def _build_parsed_fields(query: str, jurisdiction: str) -> ParsedFields:
    region = _jurisdiction_to_region(jurisdiction)
    query_lower = query.lower()

    data_types: list[str] = []
    if any(t in query_lower for t in ("biometric", "face", "facial")) or any(
        t in query for t in ("生物特征", "人脸", "指纹")
    ):
        data_types.append("Biometric")
    elif any(t in query_lower for t in ("personal", "consent", "privacy")) or any(
        t in query for t in ("个人信息", "同意", "隐私")
    ):
        data_types.append("Personal")

    cross_border = any(t in query_lower for t in ("cross-border", "transfer", "third country")) or any(
        t in query for t in ("跨境", "出境", "境外", "传输到")
    )
    third_party = any(t in query_lower for t in ("third party", "processor", "vendor")) or any(
        t in query for t in ("第三方", "委托", "处理机构")
    )
    aigc = any(t in query_lower for t in ("generate", "synthetic", "ai-generated", "deepfake", "labeling")) or any(
        t in query for t in ("生成", "合成", "标识", "AIGC")
    )

    return ParsedFields(
        region=region,
        data_types=data_types or None,
        cross_border=cross_border or None,
        third_party_model=third_party or None,
        aigc_output=aigc or None,
    )


def run_retrieval_eval(
    cases_path: Path,
    output_path: Path,
    *,
    verbose: bool = False,
) -> dict[str, Any]:
    """Run retrieval evaluation and return result dict."""

    if not cases_path.exists():
        raise FileNotFoundError(f"Test case file not found: {cases_path}")

    rows = list(csv.DictReader(cases_path.open(encoding="utf-8")))
    if not rows:
        raise ValueError(f"No retrieval test cases in {cases_path}")

    settings = get_settings()

    hit_count = 0
    rerank_scores: list[float] = []
    by_topic: dict[str, dict[str, int]] = {}
    by_language: dict[str, dict[str, int]] = {}

    # Cross-lingual: zh query expecting EU regulation
    cross_lingual_hits = 0
    cross_lingual_total = 0

    details: list[dict[str, Any]] = []
    total = len(rows)

    for idx, row in enumerate(rows):
        test_id = row["test_id"].strip()
        topic = row["topic"].strip()
        jurisdiction = row["jurisdiction"].strip()
        query = row["query"].strip()
        expected_reg = row["expected_regulation"].strip()
        expected_art = row["expected_article_id"].strip()
        query_lang = row.get("query_language", "").strip()

        if verbose:
            print(f"[{idx+1}/{total}] {test_id} ...", end="", flush=True)

        parsed_fields = _build_parsed_fields(query, jurisdiction)

        try:
            retrieved = hybrid_search(query=query, parsed_fields=parsed_fields, top_k=5)
            error = ""
        except Exception as exc:
            retrieved = []
            error = f"{type(exc).__name__}: {exc}"

        # Determine hit
        hit = False
        hit_rank: int | None = None
        top5_serialized: list[dict[str, Any]] = []

        for rank, chunk in enumerate(retrieved):
            reg_match = _fuzzy_regulation_match(expected_reg, chunk.regulation)
            primary_art = chunk.article_id or chunk.article
            art_match = _fuzzy_article_match(expected_art, primary_art)
            # Also check merged (absorbed) article IDs from short-chunk merging.
            if not art_match:
                merged_ids = getattr(chunk, "_merged_article_ids", [])
                for mid in merged_ids:
                    if _fuzzy_article_match(expected_art, mid):
                        art_match = True
                        break
            top5_serialized.append({
                "chunk_id": chunk.chunk_id,
                "regulation": chunk.regulation,
                "article_id": primary_art,
                "rerank_score": round(chunk.rerank_score, 4) if chunk.rerank_score is not None else None,
            })
            if reg_match and art_match and not hit:
                hit = True
                hit_rank = rank + 1  # 1-indexed

        if hit:
            hit_count += 1
        if verbose:
            print(f" {'✓' if hit else '✗'}")

        # Top-1 rerank score
        if retrieved and retrieved[0].rerank_score is not None:
            rerank_scores.append(float(retrieved[0].rerank_score))

        # By topic
        if topic not in by_topic:
            by_topic[topic] = {"total": 0, "hit": 0}
        by_topic[topic]["total"] += 1
        if hit:
            by_topic[topic]["hit"] += 1

        # By language
        if query_lang not in by_language:
            by_language[query_lang] = {"total": 0, "hit": 0}
        by_language[query_lang]["total"] += 1
        if hit:
            by_language[query_lang]["hit"] += 1

        # Cross-lingual: zh query + EU regulation expected
        is_cross_lingual = query_lang == "zh" and expected_reg.upper() in (
            "GDPR", "EU AI ACT", "EU AI ACT"
        )
        if is_cross_lingual:
            cross_lingual_total += 1
            if hit:
                cross_lingual_hits += 1

        details.append({
            "test_id": test_id,
            "query": query,
            "expected": {"regulation": expected_reg, "article_id": expected_art},
            "top5_results": top5_serialized,
            "hit": hit,
            "hit_rank": hit_rank,
            **({"error": error} if error else {}),
        })

    hit_rate = hit_count / total if total else 0.0
    avg_top1 = statistics.mean(rerank_scores) if rerank_scores else 0.0
    cross_lingual_rate = cross_lingual_hits / cross_lingual_total if cross_lingual_total else 0.0

    by_topic_result = {
        t: {"total": d["total"], "hit": d["hit"], "rate": round(d["hit"] / d["total"], 3) if d["total"] else 0.0}
        for t, d in by_topic.items()
    }
    by_language_result = {
        lang: {"total": d["total"], "hit": d["hit"], "rate": round(d["hit"] / d["total"], 3) if d["total"] else 0.0}
        for lang, d in by_language.items()
    }

    result: dict[str, Any] = {
        "eval_mode": "retrieval",
        "timestamp": datetime.utcnow().isoformat(timespec="seconds"),
        "model": settings.model_name,
        "total_cases": total,
        "hit": hit_count,
        "missed": total - hit_count,
        "hit_rate": round(hit_rate, 3),
        "target": TARGET_HIT_RATE,
        "target_met": hit_rate >= TARGET_HIT_RATE,
        "avg_top1_rerank_score": round(avg_top1, 4),
        "by_topic": by_topic_result,
        "by_language": by_language_result,
        "cross_lingual_hit_rate": round(cross_lingual_rate, 3),
        "cross_lingual_target": TARGET_CROSS_LINGUAL_HIT_RATE,
        "cross_lingual_target_met": cross_lingual_rate >= TARGET_CROSS_LINGUAL_HIT_RATE,
        "details": details,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    return result
