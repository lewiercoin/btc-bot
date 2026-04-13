from __future__ import annotations

import dataclasses
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from backtest.backtest_runner import BacktestConfig
from settings import AppSettings

from research_lab.constants import MAX_TRADES_DEFAULT, MIN_TRADES_DEFAULT
from research_lab.constraints import validate_param_vector
from research_lab.db_snapshot import create_trial_snapshot, open_snapshot_connection, verify_required_tables
from research_lab.experiment_store import init_store, load_trials, save_trial
from research_lab.objective import evaluate_candidate
from research_lab.param_registry import get_active_params
from research_lab.pareto import compute_pareto_frontier, rank_pareto_candidates
from research_lab.settings_adapter import build_candidate_settings
from research_lab.types import ObjectiveMetrics, SignalFunnel, TrialEvaluation

if TYPE_CHECKING:
    import optuna


_HARD_MIN_TRADES_FLOOR = 80


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
        # Coupled pair: ema_slow must be > ema_fast
        if name == "ema_slow":
            if spec.low is None or spec.high is None:
                raise ValueError(f"Missing int bounds for active parameter {name}")
            ema_fast_val = sampled.get("ema_fast", int(spec.low))
            low = max(int(spec.low), int(ema_fast_val) + 1)
            sampled[name] = trial.suggest_int(name, low, int(spec.high), step=1)
            continue

        # Coupled pair: tp2_atr_mult must be > tp1_atr_mult
        if name == "tp2_atr_mult":
            if spec.low is None or spec.high is None:
                raise ValueError(f"Missing float bounds for active parameter {name}")
            tp1_val = sampled.get("tp1_atr_mult", float(spec.low))
            low = max(float(spec.low), round(float(tp1_val) + 0.1, 1))
            sampled[name] = trial.suggest_float(name, low, float(spec.high), step=0.1)
            continue

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
        protocol_hash=None,
    )


def _enqueue_warm_start_trials(
    study: "optuna.Study",
    *,
    base_settings: AppSettings,
    store_path: Path,
    protocol_hash: str | None,
    warm_start_top_n: int,
) -> None:
    """Enqueue baseline config + top-N Pareto winners from store as warm-start trials."""
    active_names = set(get_active_params().keys())

    baseline_params: dict[str, Any] = {}
    for k, v in dataclasses.asdict(base_settings.strategy).items():
        if k in active_names:
            baseline_params[k] = v
    for k, v in dataclasses.asdict(base_settings.risk).items():
        if k in active_names:
            baseline_params[k] = v
    if baseline_params:
        study.enqueue_trial(baseline_params)

    if store_path.exists():
        existing = load_trials(store_path)
        if protocol_hash is not None:
            candidates = [t for t in existing if t.protocol_hash == protocol_hash and t.rejected_reason is None]
        else:
            candidates = [t for t in existing if t.rejected_reason is None]
        pareto = rank_pareto_candidates(compute_pareto_frontier(candidates))
        for winner in pareto[:warm_start_top_n]:
            warm_params = {k: v for k, v in winner.params.items() if k in active_names}
            if warm_params:
                study.enqueue_trial(warm_params)


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
    min_trades: int = MIN_TRADES_DEFAULT,
    max_trades: int = MAX_TRADES_DEFAULT,
    protocol_hash: str | None = None,
    optuna_storage_path: Path | None = None,
    multivariate_tpe: bool = False,
    warm_start_from_store: bool = False,
    warm_start_top_n: int = 3,
) -> list[TrialEvaluation]:
    optuna = _require_optuna()
    init_store(store_path)
    evaluations: list[TrialEvaluation] = []

    if optuna_storage_path is not None:
        optuna_storage_path.parent.mkdir(parents=True, exist_ok=True)
        storage: Any = optuna.storages.JournalStorage(
            optuna.storages.journal.JournalFileBackend(str(optuna_storage_path))
        )
    else:
        storage = None

    def _constraints_func(trial: Any) -> list[float]:
        return list(trial.user_attrs.get("constraint_violations", []))

    sampler = optuna.samplers.TPESampler(
        seed=seed,
        multivariate=multivariate_tpe,
        constraints_func=_constraints_func,
    )

    study = optuna.create_study(
        study_name=study_name,
        sampler=sampler,
        directions=["maximize", "maximize", "minimize"],
        storage=storage,
        load_if_exists=optuna_storage_path is not None,
    )
    study.set_metric_names(["expectancy_r", "profit_factor", "max_drawdown_pct"])

    if warm_start_from_store:
        _enqueue_warm_start_trials(
            study,
            base_settings=base_settings,
            store_path=store_path,
            protocol_hash=protocol_hash,
            warm_start_top_n=warm_start_top_n,
        )

    def objective(trial: optuna.Trial) -> tuple[float, float, float]:
        wall_time_start = time.monotonic()
        trial.set_user_attr("protocol_hash", protocol_hash or "")

        trial_id = f"{study_name}-trial-{trial.number:05d}"
        sampled_params = build_optuna_trial_params(trial)

        # --- Constraint violations: logical impossibilities (hard gate) ---
        violations = validate_param_vector(sampled_params)
        if violations:
            rejection_reason = "; ".join(violations)
            trial.set_user_attr("constraint_violations", [1.0] * len(violations))
            trial.set_user_attr("rejection_reason", rejection_reason)
            trial.set_user_attr("trial_wall_time_s", round(time.monotonic() - wall_time_start, 3))
            evaluation = dataclasses.replace(
                _rejected_trial(trial_id, sampled_params, rejection_reason),
                protocol_hash=protocol_hash,
            )
            evaluations.append(evaluation)
            save_trial(evaluation, store_path)
            return (-2.0, 0.1, 1.0)

        trial.set_user_attr("constraint_violations", [])

        candidate_settings = build_candidate_settings(base_settings, sampled_params)
        snapshot_path = create_trial_snapshot(source_db_path, snapshots_dir, trial_id)
        conn = open_snapshot_connection(snapshot_path)
        try:
            verify_required_tables(conn)
            raw_evaluation = evaluate_candidate(
                conn,
                settings=candidate_settings,
                backtest_config=backtest_config,
                min_trades=int(min_trades),
                max_trades=int(max_trades),
            )
        finally:
            conn.close()
            snapshot_path.unlink(missing_ok=True)

        evaluation = dataclasses.replace(
            raw_evaluation,
            trial_id=trial_id,
            params=sampled_params,
            protocol_hash=protocol_hash,
        )
        evaluations.append(evaluation)
        save_trial(evaluation, store_path)
        if evaluation.rejected_reason is not None:
            trial.set_user_attr("rejection_reason", evaluation.rejected_reason)
        trial.set_user_attr("trial_wall_time_s", round(time.monotonic() - wall_time_start, 3))

        trades = evaluation.metrics.trades_count
        exp_r = evaluation.metrics.expectancy_r
        pf = evaluation.metrics.profit_factor
        dd = evaluation.metrics.max_drawdown_pct

        hard_min_trades = min(_HARD_MIN_TRADES_FLOOR, int(min_trades))
        if trades < hard_min_trades:
            rejection_reason = (
                f"MIN_TRADES_HARD_BLOCK: trades_count={trades} < hard_min_trades={hard_min_trades}"
            )
            trial.set_user_attr("constraint_violations", [1.0])
            trial.set_user_attr("rejection_reason", rejection_reason)
            return (-2.0, 0.1, 1.0)

        # --- Soft Penalty: too few trades above the hard floor ---
        _MIN_TRADES = int(min_trades)
        if trades < _MIN_TRADES:
            deficit = (_MIN_TRADES - trades) / _MIN_TRADES
            penalty = 0.45 * (deficit ** 2)
            exp_r = max(-1.5, exp_r - penalty)
            pf = max(0.1, pf - 0.30 * (deficit ** 2))
            dd = min(1.0, dd + 0.25 * (deficit ** 2))

        # --- Anti-overfitting guard: cap PF > 5.0, penalize zero-loss regimes ---
        if pf > 5.0:
            pf = 5.0
        if pf > 3.0 and trades >= 80:
            overfit_penalty = (pf - 3.0) * 0.8
            exp_r = exp_r - overfit_penalty
            pf = pf - overfit_penalty * 0.6

        exp_r = max(-1.5, min(2.0, exp_r))
        pf = max(0.1, min(5.0, pf))
        dd = max(0.0, min(1.0, dd))

        return (exp_r, pf, dd)

    study.optimize(objective, n_trials=int(n_trials))
    return evaluations
