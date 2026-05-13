from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def evaluate_gates(report: dict[str, Any]) -> dict[str, Any]:
    performance = report.get("performance", {})
    decision_summary = report.get("decision_summary", {})
    closed_trades = report.get("closed_trades", [])

    total_trades = int(performance.get("trades_count", 0))
    expansion_er = float(performance.get("expectancy_r", 0.0))
    expansion_continuation_rate = float(decision_summary.get("expansion_continuation_rate", 0.0))
    expansion_entry_rate = float(decision_summary.get("expansion_entry_rate", 0.0))
    explainability_rate = _explainability_rate(closed_trades)

    gates = [
        {
            "gate": "minimum_total_trades",
            "value": total_trades,
            "pass_threshold": ">= 20",
            "reject_threshold": "< 10",
            "status": _status_min_trades(total_trades),
        },
        {
            "gate": "expansion_state_er",
            "value": expansion_er,
            "pass_threshold": "> 1.5",
            "reject_threshold": "< 1.0",
            "status": _status_er(expansion_er),
        },
        {
            "gate": "expansion_continuation_rate",
            "value": expansion_continuation_rate,
            "pass_threshold": ">= 0.60",
            "reject_threshold": "< 0.50",
            "status": _status_rate(expansion_continuation_rate, pass_at=0.60, reject_below=0.50),
        },
        {
            "gate": "expansion_entry_rate",
            "value": expansion_entry_rate,
            "pass_threshold": ">= 0.80",
            "reject_threshold": "< 0.50",
            "status": _status_rate(expansion_entry_rate, pass_at=0.80, reject_below=0.50),
        },
        {
            "gate": "explainability",
            "value": explainability_rate,
            "pass_threshold": "1.00",
            "reject_threshold": "< 1.00",
            "status": "PASS" if explainability_rate >= 1.0 else "REJECT",
        },
    ]

    red_flags: list[str] = []
    for gate in gates:
        if gate["status"] == "REJECT":
            red_flags.append(f"{gate['gate']}_reject")
        elif gate["status"] == "FAIL":
            red_flags.append(f"{gate['gate']}_fail")

    if total_trades < 10:
        verdict = "REJECT"
        reason = "insufficient_sample_hard_stop"
    elif expansion_entry_rate < 0.50:
        verdict = "TIMING_VIOLATION"
        reason = "expansion_entry_rate_below_hard_stop"
    elif expansion_er < 1.0:
        verdict = "REJECT"
        reason = "negative_or_weak_edge_hard_stop"
    elif expansion_continuation_rate < 0.50:
        verdict = "REJECT"
        reason = "expansion_exhausts_too_fast"
    elif all(gate["status"] == "PASS" for gate in gates):
        verdict = "CANDIDATE_FOR_PHASE_2_5"
        reason = "all_checkpoint_1_gates_passed"
    else:
        verdict = "ITERATE"
        reason = "marginal_checkpoint_1_results"

    return {
        "verdict": verdict,
        "reason": reason,
        "gates": gates,
        "red_flags": red_flags,
        "summary": {
            "total_trades": total_trades,
            "expansion_er": expansion_er,
            "expansion_continuation_rate": expansion_continuation_rate,
            "expansion_entry_rate": expansion_entry_rate,
            "explainability_rate": explainability_rate,
        },
    }


def _status_min_trades(value: int) -> str:
    if value >= 20:
        return "PASS"
    if value < 10:
        return "REJECT"
    return "FAIL"


def _status_er(value: float) -> str:
    if value > 1.5:
        return "PASS"
    if value < 1.0:
        return "REJECT"
    return "FAIL"


def _status_rate(value: float, *, pass_at: float, reject_below: float) -> str:
    if value >= pass_at:
        return "PASS"
    if value < reject_below:
        return "REJECT"
    return "FAIL"


def _explainability_rate(closed_trades: list[dict[str, Any]]) -> float:
    if not closed_trades:
        return 0.0
    explained = 0
    for trade in closed_trades:
        reasons = trade.get("reasons") or []
        if reasons and all(isinstance(reason, str) and reason for reason in reasons):
            explained += 1
    return explained / len(closed_trades)


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate volatility_breakout hard gates.")
    parser.add_argument("--input", default="research_lab/reports/volatility_breakout_results.json")
    parser.add_argument("--output", default="research_lab/reports/volatility_gate_results.json")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    report = json.loads(input_path.read_text(encoding="utf-8"))
    gate_results = evaluate_gates(report)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(gate_results, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(gate_results, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
