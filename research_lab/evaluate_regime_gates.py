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
    post_transition_er = float(performance.get("expectancy_r", 0.0))
    false_reversal_rate = float(decision_summary.get("false_reversal_rate", 0.0))
    whipsaw_rate = float(decision_summary.get("whipsaw_rate", 0.0))
    avg_entry_delay = float(decision_summary.get("avg_entry_delay_cycles", 0.0))
    transition_entry_rate = float(decision_summary.get("transition_entry_rate", 0.0))
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
            "gate": "post_transition_er",
            "value": post_transition_er,
            "pass_threshold": "> 1.5",
            "reject_threshold": "< 1.0",
            "status": _status_er(post_transition_er),
        },
        {
            "gate": "false_reversal_rate",
            "value": false_reversal_rate,
            "pass_threshold": "< 0.40",
            "reject_threshold": ">= 0.50",
            "status": _status_max_rate(false_reversal_rate, pass_below=0.40, reject_at=0.50),
        },
        {
            "gate": "whipsaw_rate",
            "value": whipsaw_rate,
            "pass_threshold": "< 0.30",
            "reject_threshold": ">= 0.50",
            "status": _status_max_rate(whipsaw_rate, pass_below=0.30, reject_at=0.50),
        },
        {
            "gate": "entry_delay_cycles",
            "value": avg_entry_delay,
            "pass_threshold": "<= 3",
            "reject_threshold": "> 6",
            "status": _status_entry_delay(avg_entry_delay, total_trades),
        },
        {
            "gate": "transition_entry_rate",
            "value": transition_entry_rate,
            "pass_threshold": ">= 0.70",
            "reject_threshold": "< 0.50",
            "status": _status_min_rate(transition_entry_rate, pass_at=0.70, reject_below=0.50),
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
    elif avg_entry_delay > 6:
        verdict = "TIMING_VIOLATION_15M_LATENCY"
        reason = "entry_delay_above_hard_stop"
    elif post_transition_er < 1.0:
        verdict = "REJECT"
        reason = "negative_or_weak_edge_hard_stop"
    elif false_reversal_rate >= 0.50:
        verdict = "REJECT"
        reason = "false_reversal_rate_hard_stop"
    elif whipsaw_rate >= 0.50:
        verdict = "REJECT"
        reason = "whipsaw_rate_hard_stop"
    elif all(gate["status"] == "PASS" for gate in gates):
        verdict = "CANDIDATE_READY"
        reason = "all_checkpoint_1_gates_passed"
    else:
        verdict = "REJECT"
        reason = "final_test_gate_failed_no_iteration"

    return {
        "verdict": verdict,
        "reason": reason,
        "gates": gates,
        "red_flags": red_flags,
        "summary": {
            "total_trades": total_trades,
            "post_transition_er": post_transition_er,
            "false_reversal_rate": false_reversal_rate,
            "whipsaw_rate": whipsaw_rate,
            "avg_entry_delay_cycles": avg_entry_delay,
            "transition_entry_rate": transition_entry_rate,
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


def _status_max_rate(value: float, *, pass_below: float, reject_at: float) -> str:
    if value < pass_below:
        return "PASS"
    if value >= reject_at:
        return "REJECT"
    return "FAIL"


def _status_min_rate(value: float, *, pass_at: float, reject_below: float) -> str:
    if value >= pass_at:
        return "PASS"
    if value < reject_below:
        return "REJECT"
    return "FAIL"


def _status_entry_delay(value: float, total_trades: int) -> str:
    if total_trades <= 0:
        return "REJECT"
    if value <= 3:
        return "PASS"
    if value > 6:
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
    parser = argparse.ArgumentParser(description="Evaluate regime_reversal hard gates.")
    parser.add_argument("--input", default="research_lab/reports/regime_reversal_results.json")
    parser.add_argument("--output", default="research_lab/reports/regime_gate_results.json")
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
