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


def evaluate_crowded_gates(
    crowded_report: dict[str, Any],
    *,
    overlap_rate: float | None = None,
    walkforward_passed_windows: int | None = None,
    walkforward_total_windows: int = 2,
    safety_flags: list[str] | None = None,
) -> dict[str, Any]:
    safety_flags = list(safety_flags or [])
    per_regime = crowded_report.get("per_regime", {})
    crowded = per_regime.get("crowded_leverage", {})
    overall = crowded_report.get("performance", {})
    decision_summary = crowded_report.get("decision_summary", {})

    crowded_er = _float_or_none(crowded.get("expectancy_r"))
    crowded_trades = int(crowded.get("trades_count", 0) or 0)
    total_trades = int(overall.get("trades_count", 0) or 0)
    capture_rate = _float_or_none(decision_summary.get("liquidation_capture_rate"))

    gates = [
        _gate("crowded_leverage_er", crowded_er is not None and crowded_er > 1.5, crowded_er, "> 1.5"),
        _gate("liquidation_capture", capture_rate is not None and capture_rate >= 0.50, capture_rate, ">= 0.50"),
        _gate("overlap_control", overlap_rate is not None and overlap_rate < 0.30, overlap_rate, "< 0.30"),
        _gate("minimum_total_trades", total_trades >= 20, total_trades, ">= 20"),
        _gate("crowded_trade_count", crowded_trades >= 10, crowded_trades, ">= 10 target-regime trades"),
        _gate(
            "walkforward",
            walkforward_passed_windows is not None and walkforward_passed_windows == walkforward_total_windows,
            None if walkforward_passed_windows is None else f"{walkforward_passed_windows}/{walkforward_total_windows}",
            f"{walkforward_total_windows}/{walkforward_total_windows}",
        ),
        _gate("safety_flags", not safety_flags, safety_flags, "[]"),
        _gate("explainability", _signals_have_reasons(crowded_report), "checked", "all signals include reasons[]"),
    ]
    blocking_failures = [gate for gate in gates if not gate["passed"]]
    red_flags = _red_flags(
        crowded_er=crowded_er,
        capture_rate=capture_rate,
        overlap_rate=overlap_rate,
        total_trades=total_trades,
        overall_pf=_float_or_none(overall.get("profit_factor")),
        overall_er=_float_or_none(overall.get("expectancy_r")),
        overall_win_rate=_float_or_none(overall.get("win_rate")),
    )
    return {
        "setup_type": "crowded_unwind",
        "verdict": _verdict(blocking_failures=blocking_failures, red_flags=red_flags),
        "gates": gates,
        "red_flags": red_flags,
        "notes": [
            "Missing overlap or walk-forward evidence blocks candidate status.",
            "Initial hard stops reject if sample, crowded ER, or liquidation capture fail.",
        ],
    }


def _gate(name: str, passed: bool, actual: Any, required: str) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), "actual": actual, "required": required}


def _red_flags(
    *,
    crowded_er: float | None,
    capture_rate: float | None,
    overlap_rate: float | None,
    total_trades: int,
    overall_pf: float | None,
    overall_er: float | None,
    overall_win_rate: float | None,
) -> list[dict[str, Any]]:
    flags: list[dict[str, Any]] = []
    if total_trades == 0:
        flags.append({"flag": "no_trades", "action": "REJECT_OR_ITERATE"})
    if crowded_er is not None and crowded_er < 0.5:
        flags.append({"flag": "crowded_leverage_er_below_edge_threshold", "action": "REJECT"})
    if capture_rate is not None and capture_rate < 0.40:
        flags.append({"flag": "liquidation_capture_not_predictive", "action": "REJECT"})
    if overlap_rate is not None and overlap_rate > 0.40:
        flags.append({"flag": "high_overlap_with_sweep_reclaim", "action": "REJECT"})
    if overall_pf is not None and overall_pf > 6.0:
        flags.append({"flag": "profit_factor_too_high_review_required", "action": "REVIEW"})
    if overall_er is not None and overall_er > 5.0:
        flags.append({"flag": "expectancy_too_high_review_required", "action": "REVIEW"})
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
    parser = argparse.ArgumentParser(description="Evaluate crowded_unwind hard gates.")
    parser.add_argument("--crowded-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("research_lab/reports/crowded_gate_results.json"))
    parser.add_argument("--overlap-rate", type=float)
    parser.add_argument("--wf-passed-windows", type=int)
    parser.add_argument("--wf-total-windows", type=int, default=2)
    parser.add_argument("--safety-flag", action="append", default=[])
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    report = json.loads(args.crowded_report.read_text(encoding="utf-8"))
    result = evaluate_crowded_gates(
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
