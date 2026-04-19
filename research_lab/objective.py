from __future__ import annotations

import dataclasses
import hashlib
import json
import uuid
from datetime import date, datetime
from math import isfinite
from typing import Any, Iterable

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


def _to_range_value(value: object) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def build_search_space_signature(param_names: Iterable[str]) -> str:
    canonical_names = sorted({str(name) for name in param_names})
    payload = json.dumps(canonical_names, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def build_trial_context_signature(
    *,
    protocol_hash: str | None,
    search_space_signature: str,
    start_date: object,
    end_date: object,
    baseline_version: str,
) -> str:
    context = {
        "protocol_hash": protocol_hash,
        "search_space_signature": search_space_signature,
        "date_range": f"{_to_range_value(start_date)}_{_to_range_value(end_date)}",
        "baseline_version": baseline_version,
    }
    payload = json.dumps(context, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


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
    protocol_hash: str | None = None,
    search_space_param_names: Iterable[str] | None = None,
    regime_signature: str | None = None,
    baseline_version: str | None = None,
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
    baseline_lineage = str(baseline_version or settings.config_hash)
    search_space_signature = build_search_space_signature(search_space_param_names or ())
    trial_context_signature = build_trial_context_signature(
        protocol_hash=protocol_hash,
        search_space_signature=search_space_signature,
        start_date=backtest_config.start_date,
        end_date=backtest_config.end_date,
        baseline_version=baseline_lineage,
    )
    deterministic_payload = json.dumps(flat_params, sort_keys=True, separators=(",", ":"))
    trial_id = f"{settings.config_hash[:12]}-{uuid.uuid5(uuid.NAMESPACE_DNS, deterministic_payload).hex[:12]}"
    return TrialEvaluation(
        trial_id=trial_id,
        params=flat_params,
        metrics=metrics,
        funnel=funnel,
        rejected_reason=rejected_reason,
        protocol_hash=protocol_hash,
        search_space_signature=search_space_signature,
        regime_signature=regime_signature,
        trial_context_signature=trial_context_signature,
        baseline_version=baseline_lineage,
    )

