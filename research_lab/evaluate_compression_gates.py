from __future__ import annotations

import os
import sys

if __package__ in {None, ""}:
    _script_dir = os.path.dirname(os.path.abspath(__file__))
    if _script_dir in sys.path:
        sys.path.remove(_script_dir)
    _project_root = os.path.dirname(_script_dir)
    if _project_root not in sys.path:
        sys.path.insert(0, _project_root)

import argparse
import json
from pathlib import Path
from typing import Any


def evaluate_compression_gates(
    compression_report: dict[str, Any],
    *,
    overlap_rate: float | None = None,
    walkforward_passed_windows: int | None = None,
    walkforward_total_windows: int = 2,
    safety_flags: list[str] | None = None,
) -> dict[str, Any]:
    safety_flags = list(safety_flags or [])
    per_regime = compression_report.get("per_regime", {})
    normal = per_regime.get("normal", {})
    overall = compression_report.get("performance", {})
    decision_summary = compression_report.get("decision_summary", {})

    compression_er = _float_or_none(overall.get("expectancy_r"))
    compression_trades = int(decision_summary.get("internal_compression_closed_trades", overall.get("trades_count", 0)) or 0)
    normal_er = _float_or_none(normal.get("expectancy_r"))
    total_trades = int(overall.get("trades_count", 0) or 0)
    followthrough_rate = _float_or_none(decision_summary.get("breakout_followthrough_rate"))

    gates = [
        _gate("internal_compression_er", compression_er is not None and compression_er > 1.5, compression_er, "> 1.5"),
        _gate("breakout_followthrough", followthrough_rate is not None and followthrough_rate >= 0.40, followthrough_rate, ">= 0.40"),
        _gate("overlap_control", overlap_rate is not None and overlap_rate < 0.30, overlap_rate, "< 0.30"),
        _gate("minimum_total_trades", total_trades >= 20, total_trades, ">= 20"),
        _gate("internal_compression_trade_count", compression_trades >= 10, compression_trades, ">= 10 internally detected compression trades"),
        _gate("normal_secondary_er", normal_er is None or normal_er > 0.5, normal_er, "> 0.5 or no normal trades"),
        _gate(
            "walkforward",
            walkforward_passed_windows is not None and walkforward_passed_windows == walkforward_total_windows,
            None if walkforward_passed_windows is None else f"{walkforward_passed_windows}/{walkforward_total_windows}",
            f"{walkforward_total_windows}/{walkforward_total_windows}",
        ),
        _gate("safety_flags", not safety_flags, safety_flags, "[]"),
        _gate("explainability", _signals_have_reasons(compression_report), "checked", "all signals include reasons[]"),
    ]
    blocking_failures = [gate for gate in gates if not gate["passed"]]
    red_flags = _red_flags(
        compression_er=compression_er,
        followthrough_rate=followthrough_rate,
        overlap_rate=overlap_rate,
        total_trades=total_trades,
        overall_pf=_float_or_none(overall.get("profit_factor")),
        overall_win_rate=_float_or_none(overall.get("win_rate")),
    )
    return {
        "setup_type": "compression_breakout_long",
        "verdict": _verdict(blocking_failures=blocking_failures, red_flags=red_flags),
        "gates": gates,
        "red_flags": red_flags,
        "notes": [
            "Missing overlap or walk-forward evidence blocks candidate status.",
            "This evaluator does not rescue weak results by relaxing compression gates.",
        ],
    }


def _gate(name: str, passed: bool, actual: Any, required: str) -> dict[str, Any]:
    return {
        "name": name,
        "passed": bool(passed),
        "actual": actual,
        "required": required,
    }


def _red_flags(
    *,
    compression_er: float | None,
    followthrough_rate: float | None,
    overlap_rate: float | None,
    total_trades: int,
    overall_pf: float | None,
    overall_win_rate: float | None,
) -> list[dict[str, Any]]:
    flags: list[dict[str, Any]] = []
    if total_trades == 0:
        flags.append({"flag": "no_trades", "action": "REJECT_OR_ITERATE"})
    if compression_er is not None and compression_er < 1.0:
        flags.append({"flag": "compression_er_below_edge_threshold", "action": "REJECT"})
    if followthrough_rate is not None and followthrough_rate < 0.40:
        flags.append({"flag": "breakout_followthrough_not_predictive", "action": "REJECT"})
    if overlap_rate is not None and overlap_rate > 0.40:
        flags.append({"flag": "high_overlap_with_sweep_reclaim", "action": "REJECT"})
    if overall_pf is not None and overall_pf > 6.0:
        flags.append({"flag": "profit_factor_too_high_review_required", "action": "REVIEW"})
    if overall_win_rate is not None and (overall_win_rate < 0.35 or overall_win_rate > 0.70):
        flags.append({"flag": "win_rate_outside_expected_band", "action": "REVIEW"})
    return flags


def _verdict(*, blocking_failures: list[dict[str, Any]], red_flags: list[dict[str, Any]]) -> str:
    if any(flag["action"] == "REJECT" for flag in red_flags):
        return "REJECT"
    if blocking_failures:
        return "ITERATE"
    return "CANDIDATE_FOR_PHASE_2_5"


def _signals_have_reasons(report: dict[str, Any]) -> bool:
    signals = report.get("signals", [])
    if not isinstance(signals, list):
        return False
    return all(bool(signal.get("candidate_reasons")) for signal in signals if isinstance(signal, dict))


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, str) and value.lower() in {"inf", "nan"}:
        return None
    return float(value)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate compression_breakout hard gates.")
    parser.add_argument("--compression-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("research_lab/reports/compression_gate_results.json"))
    parser.add_argument("--overlap-rate", type=float)
    parser.add_argument("--wf-passed-windows", type=int)
    parser.add_argument("--wf-total-windows", type=int, default=2)
    parser.add_argument("--safety-flag", action="append", default=[])
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    report = json.loads(args.compression_report.read_text(encoding="utf-8"))
    result = evaluate_compression_gates(
        report,
        overlap_rate=args.overlap_rate,
        walkforward_passed_windows=args.wf_passed_windows,
        walkforward_total_windows=args.wf_total_windows,
        safety_flags=list(args.safety_flag),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
