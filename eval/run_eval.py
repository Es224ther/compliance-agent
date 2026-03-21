"""Main evaluation entry point for Compliance Agent."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_OUTPUT_DIR = ROOT / "eval" / "results"
TEST_CASES_DIR = ROOT / "eval" / "test_cases"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compliance Agent Evaluation Harness",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--mode",
        required=True,
        choices=["all", "parsing", "retrieval", "guardrail", "hallucination"],
        help="Evaluation mode to run.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory for result JSON files (default: eval/results).",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Seconds to wait between LLM calls (default: 1.0).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print per-case progress.",
    )
    return parser


def run_parsing(output_dir: Path, delay: float, verbose: bool) -> dict:
    from eval.evaluators.parsing_eval import run_parsing_eval

    cases_path = TEST_CASES_DIR / "parsing_tests.csv"
    output_path = output_dir / "parsing_result.json"
    print(f"\n{'='*50}")
    print("Running PARSING evaluation...")
    result = run_parsing_eval(cases_path, output_path, delay=delay, verbose=verbose)
    rate = result["success_rate"]
    met = result["target_met"]
    print(f"  解析成功率: {rate:.1%}  目标: ≥{result['target']:.0%}  {'✅ PASS' if met else '❌ FAIL'}")
    print(f"  结果写入: {output_path}")
    return result


def run_retrieval(output_dir: Path, verbose: bool) -> dict:
    from eval.evaluators.retrieval_eval import run_retrieval_eval

    cases_path = TEST_CASES_DIR / "retrieval_tests.csv"
    output_path = output_dir / "retrieval_result.json"
    print(f"\n{'='*50}")
    print("Running RETRIEVAL evaluation...")
    result = run_retrieval_eval(cases_path, output_path, verbose=verbose)
    rate = result["hit_rate"]
    met = result["target_met"]
    cl_rate = result["cross_lingual_hit_rate"]
    cl_met = result["cross_lingual_target_met"]
    print(f"  Top-5 命中率: {rate:.1%}  目标: ≥{result['target']:.0%}  {'✅ PASS' if met else '❌ FAIL'}")
    print(f"  双语检索命中率: {cl_rate:.1%}  目标: ≥{result['cross_lingual_target']:.0%}  {'✅ PASS' if cl_met else '❌ FAIL'}")
    print(f"  结果写入: {output_path}")
    return result


def run_guardrail(output_dir: Path, delay: float, verbose: bool) -> dict:
    from eval.evaluators.guardrail_eval import run_guardrail_eval

    cases_path = TEST_CASES_DIR / "guardrail_tests.csv"
    output_path = output_dir / "guardrail_result.json"
    print(f"\n{'='*50}")
    print("Running GUARDRAIL evaluation...")
    result = run_guardrail_eval(cases_path, output_path, delay=delay, verbose=verbose)
    acc = result["accuracy"]
    met = result["target_met"]
    print(f"  追问触发准确率: {acc:.1%}  目标: ≥{result['target']:.0%}  {'✅ PASS' if met else '❌ FAIL'}")
    print(f"  结果写入: {output_path}")
    return result


def run_hallucination(output_dir: Path, verbose: bool) -> dict:
    from eval.evaluators.hallucination_eval import run_hallucination_eval

    output_path = output_dir / "hallucination_result.json"
    print(f"\n{'='*50}")
    print("Running HALLUCINATION evaluation...")
    result = run_hallucination_eval(output_path, verbose=verbose)
    rate = result["hallucination_rate"]
    met = result["target_met"]
    print(f"  幻觉率: {rate:.1%}  目标: ≤{result['target']:.0%}  {'✅ PASS' if met else '❌ FAIL'}")
    print(f"  结果写入: {output_path}")
    return result


def print_summary_report(results: dict[str, dict]) -> None:
    """Print human-readable summary table to terminal."""
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    parsing = results.get("parsing", {})
    retrieval = results.get("retrieval", {})
    guardrail = results.get("guardrail", {})
    hallucination = results.get("hallucination", {})

    lines = [
        "═" * 51,
        "  Compliance Agent — 评测报告",
        f"  {now}",
        "═" * 51,
        "",
        f"  {'指标':<22} {'实际值':>8}  {'目标值':>8}  {'状态'}",
        "  " + "─" * 47,
    ]

    def row(label: str, value: float | None, target: float, lower_is_better: bool = False) -> str:
        if value is None:
            return f"  {label:<22} {'N/A':>8}  {'':>8}  ⚠️  SKIP"
        if lower_is_better:
            met = value <= target
            target_str = f"≤ {target:.0%}"
        else:
            met = value >= target
            target_str = f"≥ {target:.0%}"
        status = "✅ PASS" if met else "❌ FAIL"
        return f"  {label:<22} {value:.1%}   {target_str:>8}  {status}"

    lines.append(row(
        "解析成功率",
        parsing.get("success_rate"),
        parsing.get("target", 0.90),
    ))
    lines.append(row(
        "RAG Top-5 命中率",
        retrieval.get("hit_rate"),
        retrieval.get("target", 0.70),
    ))
    lines.append(row(
        "双语检索命中率",
        retrieval.get("cross_lingual_hit_rate"),
        retrieval.get("cross_lingual_target", 0.60),
    ))
    lines.append(row(
        "追问触发准确率",
        guardrail.get("accuracy"),
        guardrail.get("target", 0.80),
    ))
    lines.append(row(
        "幻觉率",
        hallucination.get("hallucination_rate"),
        hallucination.get("target", 0.10),
        lower_is_better=True,
    ))

    lines.append("  " + "─" * 47)

    all_met = all(
        r.get("target_met", False)
        for r in results.values()
        if r
    )
    overall = "✅ ALL PASS" if all_met else "❌ SOME FAILED"
    lines.append(f"  总体结果：{overall}")
    lines.append("")
    lines.append("  失败用例详情见 eval/results/")
    lines.append("═" * 51)

    print("\n" + "\n".join(lines))


def save_summary(results: dict[str, dict], output_dir: Path) -> None:
    metrics: dict[str, dict] = {}

    if "parsing" in results:
        r = results["parsing"]
        metrics["parsing_success_rate"] = {
            "value": r.get("success_rate"),
            "target": r.get("target"),
            "met": r.get("target_met"),
        }

    if "retrieval" in results:
        r = results["retrieval"]
        metrics["retrieval_hit_rate"] = {
            "value": r.get("hit_rate"),
            "target": r.get("target"),
            "met": r.get("target_met"),
        }
        metrics["cross_lingual_hit_rate"] = {
            "value": r.get("cross_lingual_hit_rate"),
            "target": r.get("cross_lingual_target"),
            "met": r.get("cross_lingual_target_met"),
        }

    if "guardrail" in results:
        r = results["guardrail"]
        metrics["guardrail_accuracy"] = {
            "value": r.get("accuracy"),
            "target": r.get("target"),
            "met": r.get("target_met"),
        }

    if "hallucination" in results:
        r = results["hallucination"]
        metrics["hallucination_rate"] = {
            "value": r.get("hallucination_rate"),
            "target": r.get("target"),
            "met": r.get("target_met"),
        }

    overall_pass = all(m.get("met", False) for m in metrics.values())

    summary = {
        "timestamp": datetime.utcnow().isoformat(timespec="seconds"),
        "overall_pass": overall_pass,
        "metrics": metrics,
        "detail_files": {
            "parsing": "eval/results/parsing_result.json",
            "retrieval": "eval/results/retrieval_result.json",
            "guardrail": "eval/results/guardrail_result.json",
            "hallucination": "eval/results/hallucination_result.json",
        },
    }

    summary_path = output_dir / "eval_summary.json"
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  汇总报告: {summary_path}")


def main() -> None:
    args = build_parser().parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    mode = args.mode
    delay = args.delay
    verbose = args.verbose
    results: dict[str, dict] = {}

    if mode in ("parsing", "all"):
        try:
            results["parsing"] = run_parsing(output_dir, delay=delay, verbose=verbose)
        except Exception as exc:
            print(f"  [ERROR] Parsing eval failed: {exc}")
            results["parsing"] = {}

    if mode in ("retrieval", "all"):
        try:
            results["retrieval"] = run_retrieval(output_dir, verbose=verbose)
        except Exception as exc:
            print(f"  [ERROR] Retrieval eval failed: {exc}")
            results["retrieval"] = {}

    if mode in ("guardrail", "all"):
        try:
            results["guardrail"] = run_guardrail(output_dir, delay=delay, verbose=verbose)
        except Exception as exc:
            print(f"  [ERROR] Guardrail eval failed: {exc}")
            results["guardrail"] = {}

    if mode in ("hallucination", "all"):
        try:
            results["hallucination"] = run_hallucination(output_dir, verbose=verbose)
        except Exception as exc:
            print(f"  [ERROR] Hallucination eval failed: {exc}")
            results["hallucination"] = {}

    if mode == "all":
        save_summary(results, output_dir)
        print_summary_report(results)


if __name__ == "__main__":
    main()
