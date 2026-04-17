from __future__ import annotations

import dataclasses
import json
import uuid
from math import isfinite
from typing import Any

from backtest.backtest_runner import BacktestConfig, BacktestResult
from settings import AppSettings

from research_lab.constants import MAX_TRADES_DEFAULT, MIN_TRADES_DEFAULT
from research_lab.funnel import run_backtest_with_funnel
from research_lab.types import ObjectiveMetrics, TrialEvaluation


def _flatten_trial_params(settings: AppSettings) -> dict[str, Any]:
    params = {}
    params.update(dataclasses.asdict(settings.strategy))
    params.update(dataclasses.asdict(settings.risk))
    return params


def _to_finite_float(value: float) -> float:
    numeric = float(value)
    if isfinite(numeric):
        return numeric
    if numeric > 0:
        return 1e6
    return 0.0


def metrics_from_result(result: BacktestResult) -> ObjectiveMetrics:
    """Extracts ObjectiveMetrics from BacktestResult.performance."""

    perf = result.performance
    return ObjectiveMetrics(
        expectancy_r=_to_finite_float(perf.expectancy_r),
        profit_factor=_to_finite_float(perf.profit_factor),
        max_drawdown_pct=_to_finite_float(perf.max_drawdown_pct),
        trades_count=int(perf.trades_count),
        sharpe_ratio=_to_finite_float(perf.sharpe_ratio),
        pnl_abs=_to_finite_float(perf.pnl_abs),
        win_rate=_to_finite_float(perf.win_rate),
    )


def evaluate_candidate(
    connection,
    *,
    settings: AppSettings,
    candidate_params: dict[str, Any] | None = None,
    backtest_config: BacktestConfig,
    min_trades: int = MIN_TRADES_DEFAULT,
    max_trades: int = MAX_TRADES_DEFAULT,
) -> TrialEvaluation:
    """Runs backtest + funnel. Returns TrialEvaluation with min/max-trades rejection metadata."""

    result, funnel = run_backtest_with_funnel(
        connection,
        settings=settings,
        candidate_params=candidate_params,
        backtest_config=backtest_config,
    )
    metrics = metrics_from_result(result)
    rejected_reason: str | None = None
    if metrics.trades_count < int(min_trades):
        rejected_reason = f"MIN_TRADES_NOT_MET: trades_count={metrics.trades_count} < min_trades={int(min_trades)}"
    elif metrics.trades_count > int(max_trades):
        rejected_reason = (
            f"MAX_TRADES_VOLUME_CONSTRAINT: "
            f"trades_count={metrics.trades_count} > max_trades={int(max_trades)}"
        )

    flat_params = _flatten_trial_params(settings)
    deterministic_payload = json.dumps(flat_params, sort_keys=True, separators=(",", ":"))
    trial_id = f"{settings.config_hash[:12]}-{uuid.uuid5(uuid.NAMESPACE_DNS, deterministic_payload).hex[:12]}"
    return TrialEvaluation(
        trial_id=trial_id,
        params=flat_params,
        metrics=metrics,
        funnel=funnel,
        rejected_reason=rejected_reason,
    )

