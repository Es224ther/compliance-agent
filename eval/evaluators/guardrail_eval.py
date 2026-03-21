"""Guardrail evaluator: measures follow-up trigger accuracy."""

from __future__ import annotations

import csv
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.agents.intake_agent import IntakeAgent, IntakeResult
from app.schemas import ParsedFields, ScenarioInput
from app.guards.field_rules import check_completeness
from app.config.settings import get_settings

TARGET_ACCURACY = 0.80


def _parse_bool(raw: str) -> bool:
    return raw.strip().lower() == "true"


def _parse_missing_fields(raw: str) -> list[str]:
    raw = raw.strip()
    if not raw or raw.lower() in ("null", "none", "[]"):
        return []
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return [f.strip().strip('"') for f in raw.strip("[]").split(",") if f.strip()]


def run_guardrail_eval(
    cases_path: Path,
    output_path: Path,
    *,
    delay: float = 1.0,
    verbose: bool = False,
) -> dict[str, Any]:
    """Run guardrail evaluation and return result dict."""

    if not cases_path.exists():
        raise FileNotFoundError(f"Test case file not found: {cases_path}")

    rows = list(csv.DictReader(cases_path.open(encoding="utf-8")))
    if not rows:
        raise ValueError(f"No guardrail test cases in {cases_path}")

    agent = IntakeAgent()
    settings = get_settings()

    true_positive = 0
    true_negative = 0
    false_positive = 0
    false_negative = 0

    # Field detection accuracy (for TP cases)
    total_expected_missing = 0
    total_correctly_identified = 0

    by_difficulty: dict[str, dict[str, int]] = {}
    failures: list[dict[str, Any]] = []
    total = len(rows)

    for idx, row in enumerate(rows):
        test_id = row["test_id"].strip()
        input_text = row["input_text"].strip()
        expected_missing = _parse_missing_fields(row.get("missing_fields", ""))
        should_trigger = _parse_bool(row.get("should_trigger_followup", "false"))
        difficulty = row.get("difficulty", "unknown").strip()

        if verbose:
            print(f"[{idx+1}/{total}] {test_id} ...", end="", flush=True)

        parsed_fields = ParsedFields()
        error: str | None = None
        actual_missing: list[str] = []

        try:
            scenario = ScenarioInput(raw_text=input_text)
            agent_output = agent.run(scenario)
            if agent_output.tool_results:
                intake_result: IntakeResult = agent_output.tool_results[0].output
                parsed_fields = intake_result.parsed_fields
            else:
                error = "No tool results returned"
        except Exception as exc:
            error = f"LLM call failed: {exc}"

        actual_missing = check_completeness(parsed_fields)
        actual_trigger = len(actual_missing) > 0

        correct = actual_trigger == should_trigger

        # Confusion matrix
        if should_trigger and actual_trigger:
            true_positive += 1
        elif not should_trigger and not actual_trigger:
            true_negative += 1
        elif not should_trigger and actual_trigger:
            false_positive += 1
        else:
            false_negative += 1

        # Difficulty aggregation
        if difficulty not in by_difficulty:
            by_difficulty[difficulty] = {"total": 0, "correct": 0}
        by_difficulty[difficulty]["total"] += 1
        if correct:
            by_difficulty[difficulty]["correct"] += 1

        # Field detection soft metric (only for TP cases where should_trigger=true)
        if should_trigger and expected_missing:
            for expected_field in expected_missing:
                total_expected_missing += 1
                if expected_field in actual_missing:
                    total_correctly_identified += 1

        if verbose:
            status = "✓" if correct else "✗"
            print(f" {status}")

        if not correct or error:
            failures.append({
                "test_id": test_id,
                "input_text": input_text[:200],
                "expected_trigger": should_trigger,
                "actual_trigger": actual_trigger,
                "expected_missing": expected_missing,
                "actual_missing": actual_missing,
                "analysis": _analyze_failure(should_trigger, actual_trigger, error),
                **({"error": error} if error else {}),
            })

        if delay > 0 and idx < total - 1:
            time.sleep(delay)

    correct_total = true_positive + true_negative
    accuracy = correct_total / total if total else 0.0
    precision = true_positive / (true_positive + false_positive) if (true_positive + false_positive) > 0 else 0.0
    recall = true_positive / (true_positive + false_negative) if (true_positive + false_negative) > 0 else 0.0
    field_detection_accuracy = (
        total_correctly_identified / total_expected_missing if total_expected_missing > 0 else 0.0
    )

    by_diff_result = {
        diff: {
            "total": d["total"],
            "correct": d["correct"],
            "rate": round(d["correct"] / d["total"], 3) if d["total"] else 0.0,
        }
        for diff, d in by_difficulty.items()
    }

    result: dict[str, Any] = {
        "eval_mode": "guardrail",
        "timestamp": datetime.utcnow().isoformat(timespec="seconds"),
        "model": settings.model_name,
        "total_cases": total,
        "correct": correct_total,
        "incorrect": total - correct_total,
        "accuracy": round(accuracy, 3),
        "target": TARGET_ACCURACY,
        "target_met": accuracy >= TARGET_ACCURACY,
        "true_positive": true_positive,
        "true_negative": true_negative,
        "false_positive": false_positive,
        "false_negative": false_negative,
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "field_detection_accuracy": round(field_detection_accuracy, 3),
        "by_difficulty": by_diff_result,
        "failures": failures,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    return result


def _analyze_failure(should_trigger: bool, actual_trigger: bool, error: str | None) -> str:
    if error:
        return f"执行错误: {error}"
    if should_trigger and not actual_trigger:
        return "漏报：对残缺输入没追问，LLM 可能猜测了缺失字段"
    if not should_trigger and actual_trigger:
        return "误报：对完整输入仍触发追问"
    return ""
