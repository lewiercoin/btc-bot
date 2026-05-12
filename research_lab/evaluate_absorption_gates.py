from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def evaluate_absorption_gates(
    absorption_report: dict[str, Any],
    *,
    sweep_uptrend_trades: int = 0,
    overlap_rate: float | None = None,
    trend_day_capture_rate: float | None = None,
    walkforward_passed_windows: int | None = None,
    walkforward_total_windows: int = 2,
    safety_flags: list[str] | None = None,
) -> dict[str, Any]:
    safety_flags = list(safety_flags or [])
    per_regime = absorption_report.get("per_regime", {})
    uptrend = per_regime.get("uptrend", {})
    range_regime = per_regime.get("range", {})
    overall = absorption_report.get("performance", {})
    decision_summary = absorption_report.get("decision_summary", {})

    uptrend_er = _float_or_none(uptrend.get("expectancy_r"))
    uptrend_trades = int(uptrend.get("trades_count", 0) or 0)
    range_er = _float_or_none(range_regime.get("expectancy_r"))
    absorption_hit_rate = _float_or_none(decision_summary.get("absorption_confirmation_hit_rate"))
    total_trades = int(overall.get("trades_count", 0) or 0)

    gates = [
        _gate("uptrend_er", uptrend_er is not None and uptrend_er > 1.5, uptrend_er, "> 1.5"),
        _gate("uptrend_trade_coverage", uptrend_trades >= max(20, sweep_uptrend_trades + 1), uptrend_trades, f">= max(20, sweep+1={sweep_uptrend_trades + 1})"),
        _gate(
            "trend_day_capture",
            trend_day_capture_rate is not None and trend_day_capture_rate >= 0.50,
            trend_day_capture_rate,
            ">= 0.50",
        ),
        _gate(
            "overlap_control",
            overlap_rate is not None and overlap_rate < 0.30,
            overlap_rate,
            "< 0.30 hard gate; < 0.20 preferred",
        ),
        _gate("range_bleed", range_er is None or range_er > -1.0, range_er, "> -1.0 or no range trades"),
        _gate(
            "walkforward",
            walkforward_passed_windows is not None and walkforward_passed_windows == walkforward_total_windows,
            None if walkforward_passed_windows is None else f"{walkforward_passed_windows}/{walkforward_total_windows}",
            f"{walkforward_total_windows}/{walkforward_total_windows}",
        ),
        _gate("safety_flags", not safety_flags, safety_flags, "[]"),
        _gate("explainability", _signals_have_reasons(absorption_report), "checked", "all signals include reasons[]"),
        _gate("minimum_total_trades", total_trades >= 20, total_trades, ">= 20"),
    ]
    blocking_failures = [gate for gate in gates if not gate["passed"]]
    red_flags = _red_flags(
        absorption_hit_rate=absorption_hit_rate,
        overlap_rate=overlap_rate,
        trend_day_capture_rate=trend_day_capture_rate,
        uptrend_er=uptrend_er,
        total_trades=total_trades,
    )
    return {
        "setup_type": "absorption_continuation_long",
        "verdict": _verdict(blocking_failures=blocking_failures, red_flags=red_flags),
        "gates": gates,
        "red_flags": red_flags,
        "notes": [
            "This evaluator does not rescue weak results by relaxing gates.",
            "Missing overlap, trend-day capture, or walk-forward evidence blocks candidate status.",
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
    absorption_hit_rate: float | None,
    overlap_rate: float | None,
    trend_day_capture_rate: float | None,
    uptrend_er: float | None,
    total_trades: int,
) -> list[dict[str, Any]]:
    flags: list[dict[str, Any]] = []
    if total_trades == 0:
        flags.append({"flag": "no_trades", "action": "REJECT_OR_ITERATE"})
    if uptrend_er is not None and uptrend_er < 1.5:
        flags.append({"flag": "uptrend_er_below_edge_threshold", "action": "REJECT"})
    if absorption_hit_rate is not None and absorption_hit_rate < 0.50:
        flags.append({"flag": "absorption_confirmation_not_predictive", "action": "REJECT"})
    if overlap_rate is not None and overlap_rate > 0.50:
        flags.append({"flag": "high_overlap_with_sweep_reclaim", "action": "REJECT"})
    if trend_day_capture_rate is not None and trend_day_capture_rate < 0.30:
        flags.append({"flag": "misses_target_trend_structure", "action": "REJECT"})
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
    parser = argparse.ArgumentParser(description="Evaluate absorption_continuation hard gates.")
    parser.add_argument("--absorption-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("research_lab/reports/absorption_gate_results.json"))
    parser.add_argument("--sweep-uptrend-trades", type=int, default=0)
    parser.add_argument("--overlap-rate", type=float)
    parser.add_argument("--trend-day-capture-rate", type=float)
    parser.add_argument("--wf-passed-windows", type=int)
    parser.add_argument("--wf-total-windows", type=int, default=2)
    parser.add_argument("--safety-flag", action="append", default=[])
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    report = json.loads(args.absorption_report.read_text(encoding="utf-8"))
    result = evaluate_absorption_gates(
        report,
        sweep_uptrend_trades=args.sweep_uptrend_trades,
        overlap_rate=args.overlap_rate,
        trend_day_capture_rate=args.trend_day_capture_rate,
        walkforward_passed_windows=args.wf_passed_windows,
        walkforward_total_windows=args.wf_total_windows,
        safety_flags=list(args.safety_flag),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
