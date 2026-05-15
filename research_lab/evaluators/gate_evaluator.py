from __future__ import annotations

import operator
from dataclasses import dataclass
from typing import Any, Callable


OPERATORS: dict[str, Callable[[float, float], bool]] = {
    ">=": operator.ge,
    "<=": operator.le,
    ">": operator.gt,
    "<": operator.lt,
    "==": operator.eq,
    "!=": operator.ne,
}
SEVERITIES = {"REQUIRED", "RECOMMENDED", "OPTIONAL"}
VERDICTS = {"PASS", "MARGINAL", "FAIL", "INCONCLUSIVE", "BLOCKED"}


@dataclass(frozen=True)
class Gate:
    name: str
    operator: str
    threshold: float
    metric_key: str
    severity: str = "REQUIRED"

    def __post_init__(self) -> None:
        if self.operator not in OPERATORS:
            raise ValueError(f"Unsupported gate operator: {self.operator}")
        if self.severity not in SEVERITIES:
            raise ValueError(f"Unsupported gate severity: {self.severity}")


@dataclass(frozen=True)
class GateResult:
    gate: Gate
    actual_value: float | None
    passed: bool
    severity: str
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.gate.name,
            "metric_key": self.gate.metric_key,
            "operator": self.gate.operator,
            "threshold": self.gate.threshold,
            "actual_value": self.actual_value,
            "passed": self.passed,
            "severity": self.severity,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class EvaluationResult:
    experiment_id: str
    verdict: str
    gate_results: tuple[GateResult, ...]
    summary: str


def evaluate_gates(
    metrics: dict[str, Any],
    gates: list[Gate],
    *,
    experiment_id: str = "",
) -> EvaluationResult:
    results = tuple(_evaluate_one(metrics, gate) for gate in gates)
    missing_required = [r for r in results if r.actual_value is None and r.severity == "REQUIRED"]
    failed_required = [r for r in results if r.actual_value is not None and not r.passed and r.severity == "REQUIRED"]
    failed_recommended = [r for r in results if r.actual_value is not None and not r.passed and r.severity == "RECOMMENDED"]

    if missing_required:
        verdict = "BLOCKED"
        summary = f"Missing required metrics: {[r.gate.metric_key for r in missing_required]}"
    elif any(r.gate.name == "min_trades" and not r.passed for r in failed_required):
        verdict = "INCONCLUSIVE"
        summary = "Insufficient trade count for decision"
    elif failed_required:
        verdict = "FAIL"
        summary = f"Required gates failed: {[r.gate.name for r in failed_required]}"
    elif failed_recommended:
        verdict = "MARGINAL"
        summary = f"Recommended gates failed: {[r.gate.name for r in failed_recommended]}"
    else:
        verdict = "PASS"
        summary = "All required gates passed"

    return EvaluationResult(
        experiment_id=experiment_id,
        verdict=verdict,
        gate_results=results,
        summary=summary,
    )


def _evaluate_one(metrics: dict[str, Any], gate: Gate) -> GateResult:
    if gate.metric_key not in metrics:
        return GateResult(
            gate=gate,
            actual_value=None,
            passed=False,
            severity=gate.severity,
            reason="metric_missing",
        )
    actual = float(metrics[gate.metric_key])
    passed = OPERATORS[gate.operator](actual, float(gate.threshold))
    return GateResult(
        gate=gate,
        actual_value=actual,
        passed=passed,
        severity=gate.severity,
        reason="pass" if passed else "threshold_failed",
    )
