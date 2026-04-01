from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any

from backtest.backtest_runner import BacktestConfig
from settings import AppSettings

from research_lab.approval import build_recommendation
from research_lab.baseline_gate import check_baseline
from research_lab.constants import MIN_TRADES_DEFAULT
from research_lab.experiment_store import save_recommendation, save_walkforward
from research_lab.integrations.optuna_driver import run_optuna_study
from research_lab.pareto import compute_pareto_frontier, rank_pareto_candidates
from research_lab.settings_adapter import build_candidate_settings
from research_lab.walkforward import build_windows, load_protocol, run_walkforward


def _to_range_value(value: datetime | date | str) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def run_optimize_loop(
    *,
    source_db_path: Path,
    store_path: Path,
    snapshots_dir: Path,
    backtest_config: BacktestConfig,
    base_settings: AppSettings,
    n_trials: int,
    study_name: str,
    seed: int = 42,
    protocol_path: Path | None = None,
) -> dict[str, Any]:
    protocol_file = protocol_path or (Path(__file__).resolve().parents[1] / "configs" / "default_protocol.json")
    protocol = load_protocol(protocol_file)
    min_trades_full_candidate = int(protocol.get("min_trades_full_candidate", MIN_TRADES_DEFAULT))

    check_baseline(
        source_db_path=source_db_path,
        backtest_config=backtest_config,
        base_settings=base_settings,
    )
    trials = run_optuna_study(
        source_db_path=source_db_path,
        store_path=store_path,
        snapshots_dir=snapshots_dir,
        backtest_config=backtest_config,
        base_settings=base_settings,
        n_trials=n_trials,
        study_name=study_name,
        seed=seed,
        min_trades_full_candidate=min_trades_full_candidate,
    )
    frontier = rank_pareto_candidates(compute_pareto_frontier(trials))

    windows = build_windows(
        data_start=_to_range_value(backtest_config.start_date),
        data_end=_to_range_value(backtest_config.end_date),
        protocol=protocol,
    )

    recommendations_count = 0
    for trial in frontier:
        report = run_walkforward(
            base_settings=base_settings,
            candidate_params=trial.params,
            windows=windows,
            source_db_path=source_db_path,
            snapshots_dir=snapshots_dir,
            protocol=protocol,
        )
        save_walkforward(trial.trial_id, report, store_path)

        candidate_settings = build_candidate_settings(base_settings, trial.params)
        recommendation = build_recommendation(
            base_settings=base_settings,
            candidate_settings=candidate_settings,
            evaluation=trial,
            walkforward_report=report,
        )
        save_recommendation(recommendation, store_path)
        recommendations_count += 1

    return {
        "trials_total": len(trials),
        "pareto_candidates": len(frontier),
        "walkforward_windows": len(windows),
        "recommendations_saved": recommendations_count,
    }
