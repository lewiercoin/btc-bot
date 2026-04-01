from __future__ import annotations

import dataclasses
from datetime import date, datetime
from pathlib import Path
from typing import Any

from backtest.backtest_runner import BacktestConfig
from settings import AppSettings

from research_lab.approval import build_recommendation
from research_lab.constants import MIN_TRADES_DEFAULT
from research_lab.db_snapshot import create_trial_snapshot, open_snapshot_connection, verify_required_tables
from research_lab.experiment_store import load_trials, save_recommendation, save_trial, save_walkforward
from research_lab.objective import evaluate_candidate
from research_lab.settings_adapter import build_candidate_settings
from research_lab.walkforward import build_windows, load_protocol, run_walkforward


def _to_range_value(value: datetime | date | str) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def replay_candidate(
    *,
    candidate_id: str,
    base_settings: AppSettings,
    source_db_path: Path,
    snapshots_dir: Path,
    store_path: Path,
    backtest_config: BacktestConfig,
    protocol_path: Path | None = None,
) -> dict[str, Any]:
    trials = load_trials(store_path)
    matched = [trial for trial in trials if trial.trial_id == candidate_id]
    if not matched:
        raise ValueError(f"Candidate {candidate_id!r} not found in experiment store.")
    selected = matched[-1]

    protocol_file = protocol_path or (Path(__file__).resolve().parents[1] / "configs" / "default_protocol.json")
    protocol = load_protocol(protocol_file)
    min_trades_full_candidate = int(protocol.get("min_trades_full_candidate", MIN_TRADES_DEFAULT))

    candidate_settings = build_candidate_settings(base_settings, selected.params)
    snapshot_path = create_trial_snapshot(source_db_path, snapshots_dir, f"replay-{candidate_id}")
    conn = open_snapshot_connection(snapshot_path)
    try:
        verify_required_tables(conn)
        evaluation_raw = evaluate_candidate(
            conn,
            settings=candidate_settings,
            backtest_config=backtest_config,
            min_trades=min_trades_full_candidate,
        )
    finally:
        conn.close()
    evaluation = dataclasses.replace(evaluation_raw, trial_id=candidate_id, params=selected.params)
    save_trial(evaluation, store_path)

    windows = build_windows(
        data_start=_to_range_value(backtest_config.start_date),
        data_end=_to_range_value(backtest_config.end_date),
        protocol=protocol,
    )
    walkforward_report = run_walkforward(
        base_settings=base_settings,
        candidate_params=selected.params,
        windows=windows,
        source_db_path=source_db_path,
        snapshots_dir=snapshots_dir,
        protocol=protocol,
    )
    save_walkforward(candidate_id, walkforward_report, store_path)

    recommendation = build_recommendation(
        base_settings=base_settings,
        candidate_settings=candidate_settings,
        evaluation=evaluation,
        walkforward_report=walkforward_report,
    )
    save_recommendation(recommendation, store_path)
    return {
        "candidate_id": candidate_id,
        "walkforward_passed": walkforward_report.passed,
        "walkforward_fragile": walkforward_report.fragile,
        "walkforward_windows_total": walkforward_report.windows_total,
        "walkforward_windows_passed": walkforward_report.windows_passed,
    }
