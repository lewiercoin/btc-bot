from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any

from backtest.backtest_runner import BacktestConfig
from settings import AppSettings

from research_lab.constraints import assert_valid
from research_lab.db_snapshot import create_trial_snapshot, open_snapshot_connection, verify_required_tables
from research_lab.objective import evaluate_candidate
from research_lab.param_registry import build_param_registry
from research_lab.settings_adapter import build_candidate_settings
from research_lab.types import ObjectiveMetrics, SignalFunnel, TrialEvaluation

SENSITIVITY_FOCUS_PARAMS = ("invalidation_offset_atr", "tp1_atr_mult", "tp2_atr_mult", "partial_exit_pct")
SENSITIVITY_DELTAS_PCT = (-20.0, -10.0, -5.0, 5.0, 10.0, 20.0)


def _base_candidate_defaults(base_settings: AppSettings) -> dict[str, Any]:
    defaults = {}
    defaults.update(dataclasses.asdict(base_settings.strategy))
    defaults.update(dataclasses.asdict(base_settings.risk))
    return defaults


def _reject_evaluation(trial_id: str, params: dict[str, Any], reason: str) -> TrialEvaluation:
    return TrialEvaluation(
        trial_id=trial_id,
        params=params,
        metrics=ObjectiveMetrics(
            expectancy_r=0.0,
            profit_factor=0.0,
            max_drawdown_pct=0.0,
            trades_count=0,
            sharpe_ratio=0.0,
            pnl_abs=0.0,
            win_rate=0.0,
        ),
        funnel=SignalFunnel(
            signals_generated=0,
            signals_regime_blocked=0,
            signals_governance_rejected=0,
            signals_risk_rejected=0,
            signals_executed=0,
        ),
        rejected_reason=reason,
    )


def run_local_sensitivity(
    *,
    base_settings: AppSettings,
    candidate_params: dict[str, Any],
    source_db_path: Path,
    snapshots_dir: Path,
    backtest_config: BacktestConfig,
    focus_params: tuple[str, ...] = SENSITIVITY_FOCUS_PARAMS,
    deltas_pct: tuple[float, ...] = SENSITIVITY_DELTAS_PCT,
) -> dict[str, list[TrialEvaluation]]:
    registry = build_param_registry()
    baseline = _base_candidate_defaults(base_settings)
    baseline.update(candidate_params)

    results: dict[str, list[TrialEvaluation]] = {}
    for param_name in focus_params:
        if param_name not in registry:
            continue
        spec = registry[param_name]
        base_value = baseline.get(param_name, spec.default_value)
        if not isinstance(base_value, (int, float)) or isinstance(base_value, bool):
            continue

        param_trials: list[TrialEvaluation] = []
        for delta in deltas_pct:
            scaled = float(base_value) * (1.0 + (float(delta) / 100.0))
            if spec.domain_type == "int":
                candidate_value = int(round(scaled))
            else:
                candidate_value = scaled

            varied_full_vector = dict(baseline)
            varied_full_vector[param_name] = candidate_value
            varied_params = dict(candidate_params)
            varied_params[param_name] = candidate_value
            trial_id = f"sensitivity-{param_name}-{delta:+.1f}".replace(".", "_")
            try:
                assert_valid(varied_full_vector)
            except ValueError as exc:
                param_trials.append(_reject_evaluation(trial_id, varied_params, str(exc)))
                continue

            candidate_settings = build_candidate_settings(base_settings, varied_params)
            snapshot_path = create_trial_snapshot(source_db_path, snapshots_dir, trial_id)
            conn = open_snapshot_connection(snapshot_path)
            try:
                verify_required_tables(conn)
                evaluation = evaluate_candidate(
                    conn,
                    settings=candidate_settings,
                    backtest_config=backtest_config,
                )
            finally:
                conn.close()
            param_trials.append(evaluation)

        results[param_name] = param_trials

    return results
