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
class RecommendationDraft:
    candidate_id: str
    summary: str
    params_diff: dict[str, dict[str, Any]]
    expected_improvement: dict[str, float]
    risks: tuple[str, ...]
    approval_required: bool = True
    protocol_hash: str | None = None
