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
from research_lab.protocol import hash_protocol, load_protocol
from research_lab.settings_adapter import build_candidate_settings
from research_lab.walkforward import build_windows, run_nested_walkforward, run_walkforward


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
    walkforward_mode = str(protocol.get("walkforward_mode", "post_hoc")).strip().lower()
    protocol_hash = hash_protocol(protocol)
    min_trades_full_candidate = int(protocol.get("min_trades_full_candidate", MIN_TRADES_DEFAULT))

    check_baseline(
        source_db_path=source_db_path,
        backtest_config=backtest_config,
        base_settings=base_settings,
    )
    windows = build_windows(
        data_start=_to_range_value(backtest_config.start_date),
        data_end=_to_range_value(backtest_config.end_date),
        protocol=protocol,
    )

    if walkforward_mode == "nested":
        report = run_nested_walkforward(
            base_settings=base_settings,
            windows=windows,
            source_db_path=source_db_path,
            snapshots_dir=snapshots_dir,
            store_path=store_path,
            protocol=protocol,
            base_n_trials=int(n_trials),
            study_name_prefix=study_name,
            seed=int(seed),
        )
        report_id = report.selected_evaluation.trial_id if report.selected_evaluation is not None else f"{study_name}-nested-summary"
        save_walkforward(report_id, report, store_path)

        recommendations_count = 0
        selected_candidate_id: str | None = None
        if report.selected_evaluation is not None:
            selected_candidate_id = report.selected_evaluation.trial_id
            candidate_settings = build_candidate_settings(base_settings, report.selected_evaluation.params)
            recommendation = build_recommendation(
                base_settings=base_settings,
                candidate_settings=candidate_settings,
                evaluation=report.selected_evaluation,
                walkforward_report=report,
            )
            save_recommendation(recommendation, store_path)
            recommendations_count = 1

        return {
            "protocol_hash": protocol_hash,
            "walkforward_mode": walkforward_mode,
            "trials_total": report.train_trials_total,
            "pareto_candidates": len(report.candidate_summaries),
            "walkforward_windows": len(windows),
            "recommendations_saved": recommendations_count,
            "selected_candidate_id": selected_candidate_id,
        }

    if walkforward_mode != "post_hoc":
        raise ValueError(f"Unsupported walkforward_mode={walkforward_mode!r}. Use 'post_hoc' or 'nested'.")

    trials = run_optuna_study(
        source_db_path=source_db_path,
        store_path=store_path,
        snapshots_dir=snapshots_dir,
        backtest_config=backtest_config,
        base_settings=base_settings,
        n_trials=n_trials,
        study_name=study_name,
        seed=seed,
        min_trades=min_trades_full_candidate,
        protocol_hash=protocol_hash,
    )
    frontier = rank_pareto_candidates(compute_pareto_frontier(trials))

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
        "protocol_hash": protocol_hash,
        "walkforward_mode": walkforward_mode,
        "trials_total": len(trials),
        "pareto_candidates": len(frontier),
        "walkforward_windows": len(windows),
        "recommendations_saved": recommendations_count,
    }
