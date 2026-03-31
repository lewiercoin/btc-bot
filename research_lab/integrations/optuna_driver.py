from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import TYPE_CHECKING, Any

from backtest.backtest_runner import BacktestConfig
from settings import AppSettings

from research_lab.constraints import assert_valid
from research_lab.db_snapshot import create_trial_snapshot, open_snapshot_connection, verify_required_tables
from research_lab.experiment_store import init_store, save_trial
from research_lab.objective import evaluate_candidate
from research_lab.param_registry import get_active_params
from research_lab.settings_adapter import build_candidate_settings
from research_lab.types import ObjectiveMetrics, SignalFunnel, TrialEvaluation

if TYPE_CHECKING:
    import optuna


def _require_optuna():
    try:
        import optuna  # type: ignore
    except ImportError as exc:  # pragma: no cover - runtime dependency check
        raise RuntimeError(
            "optuna is required for optimize workflow. Install optuna in the project environment."
        ) from exc
    return optuna


def build_optuna_trial_params(trial: optuna.Trial) -> dict[str, Any]:
    """Samples ACTIVE params from param_registry using trial.suggest_*."""

    sampled: dict[str, Any] = {}
    for name, spec in sorted(get_active_params().items()):
        if spec.domain_type == "int":
            if spec.low is None or spec.high is None:
                raise ValueError(f"Missing int bounds for active parameter {name}")
            sampled[name] = trial.suggest_int(name, int(spec.low), int(spec.high), step=int(spec.step or 1))
            continue
        if spec.domain_type == "float":
            if spec.low is None or spec.high is None:
                raise ValueError(f"Missing float bounds for active parameter {name}")
            step = float(spec.step) if spec.step is not None else None
            if step is None:
                sampled[name] = trial.suggest_float(name, float(spec.low), float(spec.high))
            else:
                sampled[name] = trial.suggest_float(name, float(spec.low), float(spec.high), step=step)
            continue
        if spec.domain_type == "bool":
            sampled[name] = trial.suggest_categorical(name, [False, True])
            continue
        if spec.domain_type == "categorical":
            choices = spec.choices if spec.choices is not None else (spec.default_value,)
            sampled[name] = trial.suggest_categorical(name, list(choices))
            continue
        raise ValueError(f"Unsupported active domain type for Optuna sampling: {name}={spec.domain_type}")

    return sampled


def _rejected_trial(trial_id: str, params: dict[str, Any], reason: str) -> TrialEvaluation:
    return TrialEvaluation(
        trial_id=trial_id,
        params=params,
        metrics=ObjectiveMetrics(
            expectancy_r=0.0,
            profit_factor=0.0,
            max_drawdown_pct=1.0,
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


def run_optuna_study(
    *,
    source_db_path: Path,
    store_path: Path,
    snapshots_dir: Path,
    backtest_config: BacktestConfig,
    base_settings: AppSettings,
    n_trials: int,
    study_name: str,
    seed: int = 42,
) -> list[TrialEvaluation]:
    optuna = _require_optuna()
    init_store(store_path)
    evaluations: list[TrialEvaluation] = []

    sampler = optuna.samplers.TPESampler(seed=seed)
    study = optuna.create_study(
        study_name=study_name,
        sampler=sampler,
        directions=["maximize", "maximize", "minimize"],
    )

    def objective(trial: optuna.Trial) -> tuple[float, float, float]:
        trial_id = f"{study_name}-trial-{trial.number:05d}"
        sampled_params = build_optuna_trial_params(trial)
        try:
            assert_valid(sampled_params)
        except ValueError as exc:
            evaluation = _rejected_trial(trial_id, sampled_params, str(exc))
            evaluations.append(evaluation)
            save_trial(evaluation, store_path)
            return (0.0, 0.0, 1.0)

        candidate_settings = build_candidate_settings(base_settings, sampled_params)
        snapshot_path = create_trial_snapshot(source_db_path, snapshots_dir, trial_id)
        conn = open_snapshot_connection(snapshot_path)
        try:
            verify_required_tables(conn)
            raw_evaluation = evaluate_candidate(
                conn,
                settings=candidate_settings,
                backtest_config=backtest_config,
            )
        finally:
            conn.close()

        evaluation = dataclasses.replace(raw_evaluation, trial_id=trial_id, params=sampled_params)
        evaluations.append(evaluation)
        save_trial(evaluation, store_path)
        return (
            evaluation.metrics.expectancy_r,
            evaluation.metrics.profit_factor,
            evaluation.metrics.max_drawdown_pct,
        )

    study.optimize(objective, n_trials=int(n_trials))
    return evaluations
