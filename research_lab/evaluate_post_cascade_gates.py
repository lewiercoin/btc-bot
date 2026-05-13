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


def evaluate_post_cascade_gates(
    report: dict[str, Any],
    *,
    overlap_rate: float | None = None,
    walkforward_passed_windows: int | None = None,
    walkforward_total_windows: int = 2,
    safety_flags: list[str] | None = None,
) -> dict[str, Any]:
    safety_flags = list(safety_flags or [])
    post = report.get("per_regime", {}).get("post_liquidation", {})
    perf = report.get("performance", {})
    summary = report.get("decision_summary", {})
    post_er = _float_or_none(post.get("expectancy_r"))
    total_trades = int(perf.get("trades_count", 0) or 0)
    post_trades = int(post.get("trades_count", 0) or 0)
    continuation_rate = _float_or_none(summary.get("cascade_continuation_rate"))
    gates = [
        _gate("post_liquidation_er", post_er is not None and post_er > 1.5, post_er, "> 1.5"),
        _gate("cascade_continuation", continuation_rate is not None and continuation_rate >= 0.60, continuation_rate, ">= 0.60"),
        _gate("minimum_total_trades", total_trades >= 20, total_trades, ">= 20"),
        _gate("post_liquidation_trade_count", post_trades >= 10, post_trades, ">= 10"),
        _gate("overlap_control", overlap_rate is not None and overlap_rate < 0.30, overlap_rate, "< 0.30"),
        _gate(
            "walkforward",
            walkforward_passed_windows is not None and walkforward_passed_windows == walkforward_total_windows,
            None if walkforward_passed_windows is None else f"{walkforward_passed_windows}/{walkforward_total_windows}",
            f"{walkforward_total_windows}/{walkforward_total_windows}",
        ),
        _gate("safety_flags", not safety_flags, safety_flags, "[]"),
        _gate("explainability", _signals_have_reasons(report), "checked", "all signals include reasons[]"),
    ]
    red_flags = _red_flags(post_er=post_er, continuation_rate=continuation_rate, total_trades=total_trades, post_trades=post_trades)
    failures = [gate for gate in gates if not gate["passed"]]
    return {
        "setup_type": "post_cascade_momentum",
        "verdict": _verdict(blocking_failures=failures, red_flags=red_flags),
        "gates": gates,
        "red_flags": red_flags,
        "notes": [
            "Overlap and walk-forward are required only after Checkpoint 1 avoids hard stops.",
            "Hard stop triggers on <10 total trades, post-liquidation ER <1.0, continuation <0.50, or wrong-regime trades.",
        ],
    }


def _gate(name: str, passed: bool, actual: Any, required: str) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), "actual": actual, "required": required}


def _red_flags(*, post_er: float | None, continuation_rate: float | None, total_trades: int, post_trades: int) -> list[dict[str, Any]]:
    flags: list[dict[str, Any]] = []
    if total_trades < 10:
        flags.append({"flag": "insufficient_sample_hard_stop", "action": "REJECT"})
    if post_trades != total_trades:
        flags.append({"flag": "wrong_regime_trades", "action": "IMPLEMENTATION_BUG"})
    if post_er is not None and post_er < 1.0:
        flags.append({"flag": "post_liquidation_er_below_hard_stop", "action": "REJECT"})
    if continuation_rate is not None and continuation_rate < 0.50:
        flags.append({"flag": "cascade_continuation_not_predictive", "action": "REJECT"})
    return flags


def _verdict(*, blocking_failures: list[dict[str, Any]], red_flags: list[dict[str, Any]]) -> str:
    if any(flag["action"] == "IMPLEMENTATION_BUG" for flag in red_flags):
        return "IMPLEMENTATION_BUG"
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
    parser = argparse.ArgumentParser(description="Evaluate post_cascade_momentum hard gates.")
    parser.add_argument("--post-cascade-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("research_lab/reports/post_cascade_gate_results.json"))
    parser.add_argument("--overlap-rate", type=float)
    parser.add_argument("--wf-passed-windows", type=int)
    parser.add_argument("--wf-total-windows", type=int, default=2)
    parser.add_argument("--safety-flag", action="append", default=[])
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    report = json.loads(args.post_cascade_report.read_text(encoding="utf-8"))
    result = evaluate_post_cascade_gates(
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
