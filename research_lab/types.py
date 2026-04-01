from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ParamSpec:
    name: str
    target_section: str
    default_value: Any
    status: str
    domain_type: str
    low: Any | None = None
    high: Any | None = None
    choices: tuple[Any, ...] | None = None
    step: Any | None = None
    reason: str | None = None


@dataclass(frozen=True)
class SignalFunnel:
    signals_generated: int
    signals_regime_blocked: int
    signals_governance_rejected: int
    signals_risk_rejected: int
    signals_executed: int


@dataclass(frozen=True)
class ObjectiveMetrics:
    expectancy_r: float
    profit_factor: float
    max_drawdown_pct: float
    trades_count: int
    sharpe_ratio: float
    pnl_abs: float
    win_rate: float


@dataclass(frozen=True)
class TrialEvaluation:
    trial_id: str
    params: dict[str, Any]
    metrics: ObjectiveMetrics
    funnel: SignalFunnel
    rejected_reason: str | None
    protocol_hash: str | None = None


@dataclass(frozen=True)
class WalkForwardWindow:
    train_start: str
    train_end: str
    validation_start: str
    validation_end: str


@dataclass(frozen=True)
class WalkForwardReport:
    passed: bool
    windows_total: int
    windows_passed: int
    is_degradation_pct: float
    fragile: bool
    reasons: tuple[str, ...]
    protocol_hash: str | None = None


@dataclass(frozen=True)
class NestedWalkForwardWindowResult:
    window_index: int
    window: WalkForwardWindow
    study_name: str
    seed: int
    champion_trial_id: str | None
    champion_candidate_id: str | None
    champion_params: dict[str, Any]
    train_evaluation: TrialEvaluation | None
    validation_evaluation: TrialEvaluation | None
    validation_passed: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class NestedWalkForwardCandidateSummary:
    candidate_id: str
    params: dict[str, Any]
    windows_won: int
    windows_passed: int
    evaluation: TrialEvaluation
    contributing_window_indices: tuple[int, ...]


@dataclass(frozen=True)
class NestedWalkForwardReport:
    passed: bool
    windows_total: int
    windows_passed: int
    is_degradation_pct: float
    fragile: bool
    reasons: tuple[str, ...]
    protocol_hash: str | None = None
    mode: str = "nested"
    train_trials_total: int = 0
    selected_evaluation: TrialEvaluation | None = None
    candidate_summaries: tuple[NestedWalkForwardCandidateSummary, ...] = ()
    window_results: tuple[NestedWalkForwardWindowResult, ...] = ()


@dataclass(frozen=True)
class RecommendationDraft:
    candidate_id: str
    summary: str
    params_diff: dict[str, dict[str, Any]]
    expected_improvement: dict[str, float]
    risks: tuple[str, ...]
    approval_required: bool = True
    protocol_hash: str | None = None


@dataclass(frozen=True)
class AutoresearchCandidateResult:
    candidate_id: str
    params: dict[str, Any]
    hypothesis_rationale: str
    evaluation: TrialEvaluation
    walkforward_report: WalkForwardReport
    blocking_risks: tuple[str, ...]
    rank: int


@dataclass(frozen=True)
class AutoresearchLoopReport:
    run_id: str
    protocol_hash: str
    seed: int
    date_range_start: str
    date_range_end: str
    candidates_generated: int
    candidates_evaluated: int
    candidates_blocked: int
    stop_reason: str
    results: tuple[AutoresearchCandidateResult, ...]
    approval_bundle_written: bool
    approval_bundle_candidate_id: str | None
