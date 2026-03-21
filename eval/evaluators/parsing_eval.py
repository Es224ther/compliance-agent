"""Structural parsing evaluator: measures IntakeAgent ParsedFields accuracy."""

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
from app.config.settings import get_settings


FIELD_NAMES = [
    "region",
    "data_types",
    "cross_border",
    "third_party_model",
    "aigc_output",
    "data_volume_level",
]

TARGET_SUCCESS_RATE = 0.90


def _parse_expected(row: dict[str, str]) -> dict[str, Any]:
    """Convert CSV row strings to Python typed expected values."""
    expected: dict[str, Any] = {}

    raw_region = row.get("expected_region", "").strip()
    expected["region"] = None if raw_region in ("null", "", "None") else raw_region

    raw_dt = row.get("expected_data_types", "").strip()
    if raw_dt in ("null", "", "None"):
        expected["data_types"] = None
    else:
        try:
            expected["data_types"] = json.loads(raw_dt)
        except json.JSONDecodeError:
            expected["data_types"] = None

    for bool_field in ("expected_cross_border", "expected_third_party_model", "expected_aigc_output"):
        raw = row.get(bool_field, "").strip().lower()
        key = bool_field.replace("expected_", "")
        if raw in ("null", "", "none"):
            expected[key] = None
        elif raw == "true":
            expected[key] = True
        elif raw == "false":
            expected[key] = False
        else:
            expected[key] = None

    raw_vol = row.get("expected_data_volume_level", "").strip()
    expected["data_volume_level"] = None if raw_vol in ("null", "", "None") else raw_vol

    return expected


def _field_matches(field: str, expected_val: Any, actual_val: Any) -> bool:
    """Compare a single field value according to evaluation rules."""
    if expected_val is None:
        # null expected → always counts as correct (system can optionally infer)
        return True
    if field == "data_types":
        if actual_val is None:
            return False
        return set(expected_val) == set(actual_val)
    return expected_val == actual_val


def _get_actual_value(parsed_fields: ParsedFields, field: str) -> Any:
    return getattr(parsed_fields, field, None)


def _analyze_case(
    row: dict[str, str],
    expected: dict[str, Any],
    parsed_fields: ParsedFields,
    error: str | None = None,
) -> dict[str, Any]:
    mismatched = []
    field_results: dict[str, Any] = {}

    for field in FIELD_NAMES:
        exp_val = expected.get(field)
        if exp_val is None:
            continue  # skip null-expected fields in mismatch tracking
        act_val = _get_actual_value(parsed_fields, field)
        ok = _field_matches(field, exp_val, act_val)
        field_results[field] = {"expected": exp_val, "actual": act_val, "match": ok}
        if not ok:
            mismatched.append(field)

    passed = (len(mismatched) == 0) and (error is None)

    result: dict[str, Any] = {
        "test_id": row["test_id"],
        "category": row.get("category", ""),
        "difficulty": row.get("difficulty", ""),
        "passed": passed,
        "mismatched_fields": mismatched,
        "field_results": field_results,
    }
    if not passed:
        result["input_text"] = row["input_text"][:200]
        result["expected"] = {k: v for k, v in expected.items() if v is not None}
        actual_dict = {f: _get_actual_value(parsed_fields, f) for f in FIELD_NAMES}
        result["actual"] = actual_dict
        if error:
            result["error"] = error
        if mismatched:
            result["analysis"] = f"字段不匹配: {', '.join(mismatched)}"
    return result


def run_parsing_eval(
    cases_path: Path,
    output_path: Path,
    *,
    delay: float = 1.0,
    verbose: bool = False,
) -> dict[str, Any]:
    """Run parsing evaluation and return result dict."""

    if not cases_path.exists():
        raise FileNotFoundError(f"Test case file not found: {cases_path}")

    rows = list(csv.DictReader(cases_path.open(encoding="utf-8")))
    if not rows:
        raise ValueError(f"No parsing test cases in {cases_path}")

    agent = IntakeAgent()
    settings = get_settings()

    # Per-category, per-difficulty, per-field tracking
    by_category: dict[str, dict[str, int]] = {}
    by_difficulty: dict[str, dict[str, int]] = {}
    by_field: dict[str, dict[str, int]] = {}
    for f in FIELD_NAMES:
        by_field[f] = {"total_expected": 0, "correct": 0}

    passed_count = 0
    failures: list[dict[str, Any]] = []

    total = len(rows)
    for idx, row in enumerate(rows):
        test_id = row["test_id"]
        category = row.get("category", "unknown")
        difficulty = row.get("difficulty", "unknown")
        input_text = row["input_text"].strip()

        if verbose:
            print(f"[{idx+1}/{total}] {test_id} ...", end="", flush=True)

        expected = _parse_expected(row)
        parsed_fields = ParsedFields()
        error: str | None = None

        try:
            scenario = ScenarioInput(raw_text=input_text)
            agent_output = agent.run(scenario)
            if agent_output.tool_results:
                intake_result: IntakeResult = agent_output.tool_results[0].output
                parsed_fields = intake_result.parsed_fields
            else:
                error = "No tool results returned from IntakeAgent"
        except Exception as exc:
            error = f"LLM call failed: {exc}"

        case_result = _analyze_case(row, expected, parsed_fields, error)
        passed = case_result["passed"]

        if passed:
            passed_count += 1
        if verbose:
            status = "✓" if passed else "✗"
            print(f" {status}")

        # Aggregate category
        if category not in by_category:
            by_category[category] = {"total": 0, "passed": 0}
        by_category[category]["total"] += 1
        if passed:
            by_category[category]["passed"] += 1

        # Aggregate difficulty
        if difficulty not in by_difficulty:
            by_difficulty[difficulty] = {"total": 0, "passed": 0}
        by_difficulty[difficulty]["total"] += 1
        if passed:
            by_difficulty[difficulty]["passed"] += 1

        # Aggregate per-field
        for field, fd in case_result["field_results"].items():
            if field in by_field:
                by_field[field]["total_expected"] += 1
                if fd["match"]:
                    by_field[field]["correct"] += 1

        if not passed:
            failures.append({
                "test_id": case_result["test_id"],
                "category": case_result["category"],
                "difficulty": case_result["difficulty"],
                "input_text": case_result.get("input_text", ""),
                "expected": case_result.get("expected", {}),
                "actual": case_result.get("actual", {}),
                "mismatched_fields": case_result["mismatched_fields"],
                "analysis": case_result.get("analysis", ""),
                **({"error": case_result["error"]} if "error" in case_result else {}),
            })

        if delay > 0 and idx < total - 1:
            time.sleep(delay)

    success_rate = passed_count / total if total else 0.0

    # Compute category rates
    by_cat_result = {
        cat: {
            "total": d["total"],
            "passed": d["passed"],
            "rate": round(d["passed"] / d["total"], 3) if d["total"] else 0.0,
        }
        for cat, d in by_category.items()
    }

    by_diff_result = {
        diff: {
            "total": d["total"],
            "passed": d["passed"],
            "rate": round(d["passed"] / d["total"], 3) if d["total"] else 0.0,
        }
        for diff, d in by_difficulty.items()
    }

    by_field_result = {
        field: {
            "total_expected": d["total_expected"],
            "correct": d["correct"],
            "rate": round(d["correct"] / d["total_expected"], 3) if d["total_expected"] else 0.0,
        }
        for field, d in by_field.items()
        if d["total_expected"] > 0
    }

    result: dict[str, Any] = {
        "eval_mode": "parsing",
        "timestamp": datetime.utcnow().isoformat(timespec="seconds"),
        "model": settings.model_name,
        "total_cases": total,
        "passed": passed_count,
        "failed": total - passed_count,
        "success_rate": round(success_rate, 3),
        "target": TARGET_SUCCESS_RATE,
        "target_met": success_rate >= TARGET_SUCCESS_RATE,
        "by_category": by_cat_result,
        "by_difficulty": by_diff_result,
        "by_field": by_field_result,
        "failures": failures,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    return result
