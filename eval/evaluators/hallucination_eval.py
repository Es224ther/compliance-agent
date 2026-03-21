"""Hallucination evaluator: verifies report citations exist in the knowledge base."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.orchestrator.pipeline import run_pipeline
from app.schemas import ScenarioInput
from app.rag.kb.vector_store import get_default_store
from app.config.settings import get_settings

TARGET_HALLUCINATION_RATE = 0.10

DEMO_SCENARIOS = [
    "我们计划把欧洲用户上传的短视频素材传回国内服务器，用于训练一个 AI 视频剪辑模型。训练完成后模型部署在国内，服务全球用户。视频中可能包含用户人脸。",
    "开发团队希望接入 OpenAI GPT-4 API，对用户提交的文本与图片内容进行处理。用户来自中国大陆。",
    "向欧洲 B 端客户提供 AI 自动生成广告视频的 API，需要满足 EU AI Act 透明度要求和中国 AIGC 标识合规。",
]


def _load_demo_scenarios() -> list[str]:
    demo_path = ROOT / "data" / "scenarios_demo.json"
    if demo_path.exists():
        try:
            raw = json.loads(demo_path.read_text(encoding="utf-8"))
            if isinstance(raw, list) and raw:
                texts = [
                    item.get("text") or item.get("description") or item.get("raw_text")
                    for item in raw
                    if isinstance(item, dict)
                ]
                texts = [t for t in texts if t]
                if texts:
                    return texts[:3]
        except Exception:
            pass
    return DEMO_SCENARIOS


def _citation_exists_in_kb(regulation: str, article_id: str, kb_chunks: list[dict[str, Any]]) -> bool:
    """Check if a regulation + article_id pair exists in KB metadata."""
    reg_lower = regulation.lower()
    art_lower = article_id.lower()

    for chunk in kb_chunks:
        chunk_reg = str(chunk.get("regulation", "")).lower()
        chunk_art = str(chunk.get("article_id", "")).lower()
        chunk_id = str(chunk.get("chunk_id", "")).lower()

        # Fuzzy regulation match
        reg_match = reg_lower in chunk_reg or chunk_reg in reg_lower
        if not reg_match:
            continue

        # Article match: try article_id field and chunk_id
        if art_lower in chunk_art or chunk_art in art_lower:
            return True
        if art_lower in chunk_id or chunk_id in art_lower:
            return True
        # Also check without spaces/underscores
        art_norm = art_lower.replace(" ", "_").replace("-", "_")
        cid_norm = chunk_id.replace(" ", "_").replace("-", "_")
        if art_norm in cid_norm or cid_norm in art_norm:
            return True

    return False


async def _run_scenario(scenario_text: str) -> Any:
    scenario_input = ScenarioInput(raw_text=scenario_text)
    state = await run_pipeline(scenario_input)
    return state


def run_hallucination_eval(
    output_path: Path,
    *,
    verbose: bool = False,
) -> dict[str, Any]:
    """Run hallucination evaluation and return result dict."""

    settings = get_settings()
    scenarios = _load_demo_scenarios()

    # Load KB chunks once for citation checking
    if verbose:
        print("Loading knowledge base for citation verification...")
    try:
        store = get_default_store()
        kb_chunks = store.fetch_all()
        kb_chunk_count = len(kb_chunks)
    except Exception as exc:
        kb_chunks = []
        kb_chunk_count = 0
        if verbose:
            print(f"  Warning: Could not load KB chunks: {exc}")

    total_citations = 0
    hallucinated_citations = 0
    hallucination_cases: list[dict[str, Any]] = []
    by_scenario: list[dict[str, Any]] = []

    for scenario_idx, scenario_text in enumerate(scenarios):
        scenario_id = scenario_idx + 1
        if verbose:
            print(f"[{scenario_id}/{len(scenarios)}] Running pipeline for scenario {scenario_id}...")

        report = None
        risk_level = "Unknown"
        citations: list[dict[str, Any]] = []
        scenario_hallucinated = 0
        error: str | None = None

        try:
            state = asyncio.run(_run_scenario(scenario_text))
            risk_level = state.risk_level or "Unknown"

            # Extract report
            raw_report = state.report
            if raw_report is None:
                error = "Pipeline completed but report is None"
            else:
                # Handle both AuditReport model and dict
                if hasattr(raw_report, "evidence_citations"):
                    evidence_list = raw_report.evidence_citations
                elif isinstance(raw_report, dict):
                    evidence_list = raw_report.get("evidence_citations", [])
                else:
                    evidence_list = []

                for chunk in evidence_list:
                    if hasattr(chunk, "regulation"):
                        reg = chunk.regulation or ""
                        art_id = chunk.article_id or chunk.article or ""
                        cited_text = (chunk.summary or chunk.text or "")[:120]
                    elif isinstance(chunk, dict):
                        reg = chunk.get("regulation", "")
                        art_id = chunk.get("article_id") or chunk.get("article", "")
                        cited_text = (chunk.get("summary") or chunk.get("text", ""))[:120]
                    else:
                        continue

                    if not reg or not art_id:
                        continue

                    total_citations += 1
                    exists = _citation_exists_in_kb(reg, art_id, kb_chunks)

                    citation_entry: dict[str, Any] = {
                        "regulation": reg,
                        "article_id": art_id,
                        "exists_in_kb": exists,
                    }
                    citations.append(citation_entry)

                    if not exists:
                        scenario_hallucinated += 1
                        hallucinated_citations += 1
                        hallucination_cases.append({
                            "scenario_id": scenario_id,
                            "regulation": reg,
                            "article_id": art_id,
                            "cited_text": cited_text,
                            "exists_in_kb": False,
                            "likely_cause": "generation",
                        })

        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            if verbose:
                print(f"  Error: {error}")

        by_scenario.append({
            "scenario_id": scenario_id,
            "input_text": scenario_text[:100] + ("..." if len(scenario_text) > 100 else ""),
            "risk_level": risk_level,
            "total_citations": len(citations),
            "hallucinated": scenario_hallucinated,
            "citations": citations,
            **({"error": error} if error else {}),
        })

    valid_citations = total_citations - hallucinated_citations
    hallucination_rate = hallucinated_citations / total_citations if total_citations > 0 else 0.0

    result: dict[str, Any] = {
        "eval_mode": "hallucination",
        "timestamp": datetime.utcnow().isoformat(timespec="seconds"),
        "model": settings.model_name,
        "kb_chunk_count": kb_chunk_count,
        "total_scenarios": len(scenarios),
        "total_citations": total_citations,
        "valid_citations": valid_citations,
        "hallucinated_citations": hallucinated_citations,
        "hallucination_rate": round(hallucination_rate, 3),
        "target": TARGET_HALLUCINATION_RATE,
        "target_met": hallucination_rate <= TARGET_HALLUCINATION_RATE,
        "by_scenario": by_scenario,
        "hallucination_cases": hallucination_cases,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    return result
