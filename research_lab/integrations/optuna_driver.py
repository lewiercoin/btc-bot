from __future__ import annotations

import dataclasses
import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from backtest.backtest_runner import BacktestConfig
from settings import AppSettings

from research_lab.constants import MAX_TRADES_DEFAULT, MIN_TRADES_DEFAULT
from research_lab.constraints import validate_param_vector
from research_lab.db_snapshot import create_trial_snapshot, open_snapshot_connection, verify_required_tables
from research_lab.experiment_store import init_store, load_trials, load_trials_filtered, save_trial
from research_lab.objective import (
    build_search_space_signature,
    build_trial_context_signature,
    evaluate_candidate,
)
from research_lab.param_registry import get_active_params
from research_lab.pareto import compute_pareto_frontier, rank_pareto_candidates
from research_lab.settings_adapter import build_candidate_settings
from research_lab.types import ObjectiveMetrics, SignalFunnel, TrialEvaluation

if TYPE_CHECKING:
    import optuna


_HARD_MIN_TRADES_FLOOR = 80
logger = logging.getLogger(__name__)


def _require_optuna():
    try:
        import optuna  # type: ignore
    except ImportError as exc:  # pragma: no cover - runtime dependency check
        raise RuntimeError(
            "optuna is required for optimize workflow. Install optuna in the project environment."
        ) from exc
    return optuna


def _is_param_value_within_spec(value: Any, spec: Any) -> bool:
    if spec.domain_type == "bool":
        return isinstance(value, bool)
    if spec.domain_type == "int":
        if isinstance(value, bool):
            return False
        if not isinstance(value, int):
            return False
        if spec.low is not None and value < int(spec.low):
            return False
        if spec.high is not None and value > int(spec.high):
            return False
        return True
    if spec.domain_type == "float":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return False
        numeric = float(value)
        if spec.low is not None and numeric < float(spec.low):
            return False
        if spec.high is not None and numeric > float(spec.high):
            return False
        return True
    if spec.domain_type == "categorical":
        choices = spec.choices if spec.choices is not None else ()
        return value in choices if choices else True
    return True


def _is_warm_start_candidate_compatible(
    params: dict[str, Any],
    *,
    credible_history: bool,
    active_param_names: tuple[str, ...] | None = None,
) -> bool:
    active_specs = _filter_active_specs(active_param_names)
    warm_params = {k: v for k, v in params.items() if k in active_specs}
    if not warm_params:
        return False
    for name, value in warm_params.items():
        if not _is_param_value_within_spec(value, active_specs[name]):
            return False
    violations = validate_param_vector(warm_params)
    if violations:
        return False
    if credible_history:
        tp1 = warm_params.get("tp1_atr_mult")
        tp2 = warm_params.get("tp2_atr_mult")
        if tp1 is not None and tp2 is not None and float(tp1) >= float(tp2):
            return False
    return True


def _is_credible_history_trial(trial: TrialEvaluation) -> bool:
    return (
        trial.metrics.trades_count >= _HARD_MIN_TRADES_FLOOR
        and trial.metrics.profit_factor <= 3.0
    )


def _filter_active_specs(active_param_names: tuple[str, ...] | None) -> dict[str, Any]:
    active_specs = get_active_params()
    if active_param_names is None:
        return active_specs

    unknown = [name for name in active_param_names if name not in active_specs]
    if unknown:
        raise ValueError(f"Unknown active parameter(s) requested: {', '.join(sorted(unknown))}")
    return {name: active_specs[name] for name in active_param_names}


def build_optuna_trial_params(
    trial: optuna.Trial,
    *,
    active_param_names: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Samples ACTIVE params from param_registry using trial.suggest_*."""

    sampled: dict[str, Any] = {}
    for name, spec in sorted(_filter_active_specs(active_param_names).items()):
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
    active_param_names: tuple[str, ...] | None = None,
    warm_start_ignore_protocol: bool = False,
    regime_signature: str | None = None,
) -> None:
    """Enqueue baseline config + top-N Pareto winners from store as warm-start trials."""
    active_names = tuple(_filter_active_specs(active_param_names).keys())
    active_name_set = set(active_names)
    search_space_signature = build_search_space_signature(active_names)
    if store_path.exists():
        existing = load_trials(store_path)
        if warm_start_ignore_protocol:
            logger.warning(
                "Unsafe warm-start enabled: ignoring protocol/search-space filters for historical trials."
            )
            context_trials = existing
        else:
            if protocol_hash is None:
                context_trials = [
                    trial for trial in existing if trial.search_space_signature == search_space_signature
                ]
            else:
                context_trials = load_trials_filtered(
                    store_path,
                    protocol_hash,
                    search_space_signature,
                    regime_signature=regime_signature,
                )
            filtered_out = len(existing) - len(context_trials)
            if filtered_out > 0:
                logger.warning(
                    "Warm-start skipped %s historical trial(s) due to protocol/search-space mismatch.",
                    filtered_out,
                )
                if len(existing) > 0 and (filtered_out / len(existing)) > 0.5:
                    logger.warning(
                        "Warm-start filtered out more than 50%% of store history (%s/%s trials).",
                        filtered_out,
                        len(existing),
                    )
        candidates = [
            t
            for t in context_trials
            if t.rejected_reason is None
            and _is_warm_start_candidate_compatible(
                t.params,
                credible_history=False,
                active_param_names=active_param_names,
            )
        ]
        pareto = rank_pareto_candidates(compute_pareto_frontier(candidates))
        for winner in pareto[:warm_start_top_n]:
            warm_params = {k: v for k, v in winner.params.items() if k in active_name_set}
            if warm_params:
                study.enqueue_trial(warm_params)

    active_specs = _filter_active_specs(active_param_names)
    strategy_values = dataclasses.asdict(base_settings.strategy)
    risk_values = dataclasses.asdict(base_settings.risk)
    baseline_params: dict[str, Any] = {}
    for name, spec in active_specs.items():
        if spec.target_section == "strategy" and name in strategy_values:
            baseline_params[name] = strategy_values[name]
            continue
        if spec.target_section == "risk" and name in risk_values:
            baseline_params[name] = risk_values[name]
            continue
        if spec.target_section == "research":
            baseline_params[name] = spec.default_value
    if baseline_params:
        study.enqueue_trial(baseline_params)


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
    active_param_names: tuple[str, ...] | None = None,
    warm_start_ignore_protocol: bool = False,
    regime_signature: str | None = None,
) -> list[TrialEvaluation]:
    optuna = _require_optuna()
    init_store(store_path)
    evaluations: list[TrialEvaluation] = []
    active_search_space_names = tuple(_filter_active_specs(active_param_names).keys())
    search_space_signature = build_search_space_signature(active_search_space_names)
    trial_context_signature = build_trial_context_signature(
        protocol_hash=protocol_hash,
        search_space_signature=search_space_signature,
        start_date=backtest_config.start_date,
        end_date=backtest_config.end_date,
        baseline_version=base_settings.config_hash,
    )

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
            active_param_names=active_param_names,
            warm_start_ignore_protocol=warm_start_ignore_protocol,
            regime_signature=regime_signature,
        )

    def objective(trial: optuna.Trial) -> tuple[float, float, float]:
        wall_time_start = time.monotonic()
        trial.set_user_attr("protocol_hash", protocol_hash or "")

        trial_id = f"{study_name}-trial-{trial.number:05d}"
        sampled_params = build_optuna_trial_params(trial, active_param_names=active_param_names)

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
                search_space_signature=search_space_signature,
                regime_signature=regime_signature,
                trial_context_signature=trial_context_signature,
                baseline_version=base_settings.config_hash,
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
                candidate_params=sampled_params,
                backtest_config=backtest_config,
                min_trades=int(min_trades),
                max_trades=int(max_trades),
                protocol_hash=protocol_hash,
                search_space_param_names=active_search_space_names,
                regime_signature=regime_signature,
                baseline_version=base_settings.config_hash,
            )
        finally:
            conn.close()
            snapshot_path.unlink(missing_ok=True)

        evaluation = dataclasses.replace(
            raw_evaluation,
            trial_id=trial_id,
            params=sampled_params,
            protocol_hash=protocol_hash,
            search_space_signature=search_space_signature,
            regime_signature=regime_signature,
            trial_context_signature=trial_context_signature,
            baseline_version=base_settings.config_hash,
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
