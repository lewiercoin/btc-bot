from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from backtest.backtest_runner import BacktestConfig
from settings import AppSettings

from research_lab.db_snapshot import create_trial_snapshot, open_snapshot_connection, verify_required_tables
from research_lab.objective import evaluate_candidate
from research_lab.protocol import hash_protocol
from research_lab.settings_adapter import build_candidate_settings
from research_lab.types import TrialEvaluation, WalkForwardReport, WalkForwardWindow


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _is_date_only(raw: str) -> bool:
    token = raw.strip()
    return "T" not in token and " " not in token


def _parse_iso_datetime(raw: str, *, is_end: bool) -> datetime:
    parsed = _to_utc(datetime.fromisoformat(raw))
    if is_end and _is_date_only(raw):
        return parsed + timedelta(days=1)
    return parsed


def build_windows(
    data_start: str,
    data_end: str,
    protocol: dict[str, Any],
) -> list[WalkForwardWindow]:
    train_days = int(protocol["train_days"])
    validation_days = int(protocol["validation_days"])
    step_days = int(protocol["step_days"])

    start = _parse_iso_datetime(data_start, is_end=False)
    end = _parse_iso_datetime(data_end, is_end=True)

    windows: list[WalkForwardWindow] = []
    cursor = start
    while True:
        train_start = cursor
        train_end = train_start + timedelta(days=train_days)
        validation_start = train_end
        validation_end = validation_start + timedelta(days=validation_days)
        if validation_end > end:
            break

        windows.append(
            WalkForwardWindow(
                train_start=train_start.isoformat(),
                train_end=train_end.isoformat(),
                validation_start=validation_start.isoformat(),
                validation_end=validation_end.isoformat(),
            )
        )
        cursor = cursor + timedelta(days=step_days)

    return windows


def _degradation_pct(in_sample: float, out_of_sample: float) -> float:
    if abs(in_sample) < 1e-12:
        return 0.0
    return ((in_sample - out_of_sample) / abs(in_sample)) * 100.0


def _evaluate_window_segment(
    *,
    candidate_settings: AppSettings,
    source_db_path: Path,
    snapshots_dir: Path,
    segment_id: str,
    start_ts: str,
    end_ts: str,
    min_trades: int,
) -> TrialEvaluation:
    snapshot_path = create_trial_snapshot(source_db_path, snapshots_dir, segment_id)
    conn = open_snapshot_connection(snapshot_path)
    try:
        verify_required_tables(conn)
        return evaluate_candidate(
            conn,
            settings=candidate_settings,
            backtest_config=BacktestConfig(
                start_date=start_ts,
                end_date=end_ts,
                symbol=candidate_settings.strategy.symbol,
            ),
            min_trades=min_trades,
        )
    finally:
        conn.close()


def _segment_failures(
    *,
    evaluation: TrialEvaluation,
    min_expectancy_r: float,
    min_profit_factor: float,
    max_drawdown_pct: float,
    min_sharpe_ratio: float,
) -> list[str]:
    failures: list[str] = []
    if evaluation.rejected_reason is not None:
        failures.append(evaluation.rejected_reason)

    metrics = evaluation.metrics
    if metrics.expectancy_r < min_expectancy_r:
        failures.append(
            f"expectancy_r={metrics.expectancy_r:.4f} < min_expectancy_r={min_expectancy_r:.4f}"
        )
    if metrics.profit_factor < min_profit_factor:
        failures.append(
            f"profit_factor={metrics.profit_factor:.4f} < min_profit_factor={min_profit_factor:.4f}"
        )
    if metrics.max_drawdown_pct > max_drawdown_pct:
        failures.append(
            f"max_drawdown_pct={metrics.max_drawdown_pct:.4f} > max_drawdown_pct={max_drawdown_pct:.4f}"
        )
    if metrics.sharpe_ratio < min_sharpe_ratio:
        failures.append(
            f"sharpe_ratio={metrics.sharpe_ratio:.4f} < min_sharpe_ratio={min_sharpe_ratio:.4f}"
        )
    return failures


def run_walkforward(
    *,
    base_settings: AppSettings,
    candidate_params: dict[str, Any],
    windows: list[WalkForwardWindow],
    source_db_path: Path,
    snapshots_dir: Path,
    protocol: dict[str, Any],
) -> WalkForwardReport:
    candidate_settings = build_candidate_settings(base_settings, candidate_params)
    min_trades_per_window = int(protocol["min_trades_per_window"])
    min_expectancy_r = float(protocol.get("min_expectancy_r_per_window", 0.0))
    min_profit_factor = float(protocol.get("min_profit_factor_per_window", 1.0))
    max_drawdown_pct = float(protocol.get("max_drawdown_pct_per_window", 50.0))
    min_sharpe_ratio = float(protocol.get("min_sharpe_ratio_per_window", 0.0))
    fragile_threshold = float(protocol["fragility_degradation_threshold_pct"])
    require_all = bool(protocol["promotion_requires_all_windows_pass"])
    require_median = bool(protocol["promotion_requires_median_pass"])
    protocol_hash = hash_protocol(protocol)

    windows_total = len(windows)
    windows_passed = 0
    degradations: list[float] = []
    reasons: list[str] = []

    for index, window in enumerate(windows):
        train_segment_id = f"wf-train-{index:03d}"
        val_segment_id = f"wf-val-{index:03d}"
        train_evaluation = _evaluate_window_segment(
            candidate_settings=candidate_settings,
            source_db_path=source_db_path,
            snapshots_dir=snapshots_dir,
            segment_id=train_segment_id,
            start_ts=window.train_start,
            end_ts=window.train_end,
            min_trades=min_trades_per_window,
        )
        val_evaluation = _evaluate_window_segment(
            candidate_settings=candidate_settings,
            source_db_path=source_db_path,
            snapshots_dir=snapshots_dir,
            segment_id=val_segment_id,
            start_ts=window.validation_start,
            end_ts=window.validation_end,
            min_trades=min_trades_per_window,
        )

        train_failures = _segment_failures(
            evaluation=train_evaluation,
            min_expectancy_r=min_expectancy_r,
            min_profit_factor=min_profit_factor,
            max_drawdown_pct=max_drawdown_pct,
            min_sharpe_ratio=min_sharpe_ratio,
        )
        val_failures = _segment_failures(
            evaluation=val_evaluation,
            min_expectancy_r=min_expectancy_r,
            min_profit_factor=min_profit_factor,
            max_drawdown_pct=max_drawdown_pct,
            min_sharpe_ratio=min_sharpe_ratio,
        )

        if not train_failures and not val_failures:
            windows_passed += 1
            degradations.append(
                _degradation_pct(train_evaluation.metrics.expectancy_r, val_evaluation.metrics.expectancy_r)
            )
            continue

        for detail in train_failures:
            reasons.append(f"window_{index:03d}_train_failed: {detail}")
        for detail in val_failures:
            reasons.append(f"window_{index:03d}_validation_failed: {detail}")

    if windows_total == 0:
        reasons.append("no_windows_available")

    avg_degradation = sum(degradations) / len(degradations) if degradations else 0.0
    fragile = avg_degradation > fragile_threshold
    if fragile:
        reasons.append(
            "fragility_threshold_exceeded: "
            f"{avg_degradation:.2f}% > {fragile_threshold:.2f}%"
        )

    if require_all:
        passed = windows_total > 0 and windows_passed == windows_total and not fragile
    elif require_median:
        median_required = math.ceil(windows_total / 2) if windows_total else 0
        passed = windows_total > 0 and windows_passed >= median_required and not fragile
        if windows_total > 0 and windows_passed < median_required:
            reasons.append(f"median_windows_not_met: {windows_passed}/{windows_total}")
    else:
        passed = windows_total > 0 and windows_passed > 0 and not fragile

    if windows_total > 0 and windows_passed == 0:
        reasons.append("no_window_passed")

    return WalkForwardReport(
        passed=passed,
        windows_total=windows_total,
        windows_passed=windows_passed,
        is_degradation_pct=avg_degradation,
        fragile=fragile,
        reasons=tuple(reasons),
        protocol_hash=protocol_hash,
    )
