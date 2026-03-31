from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from backtest.backtest_runner import BacktestConfig
from settings import AppSettings

from research_lab.db_snapshot import create_trial_snapshot, open_snapshot_connection, verify_required_tables
from research_lab.objective import evaluate_candidate
from research_lab.settings_adapter import build_candidate_settings
from research_lab.types import WalkForwardReport, WalkForwardWindow


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


def load_protocol(protocol_path: Path) -> dict[str, Any]:
    return json.loads(protocol_path.read_text(encoding="utf-8"))


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
) -> tuple[float, bool, str | None]:
    snapshot_path = create_trial_snapshot(source_db_path, snapshots_dir, segment_id)
    conn = open_snapshot_connection(snapshot_path)
    try:
        verify_required_tables(conn)
        evaluation = evaluate_candidate(
            conn,
            settings=candidate_settings,
            backtest_config=BacktestConfig(
                start_date=start_ts,
                end_date=end_ts,
                symbol=candidate_settings.strategy.symbol,
            ),
            min_trades=min_trades,
        )
        return evaluation.metrics.expectancy_r, evaluation.rejected_reason is None, evaluation.rejected_reason
    finally:
        conn.close()


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
    fragile_threshold = float(protocol["fragility_degradation_threshold_pct"])
    require_all = bool(protocol["promotion_requires_all_windows_pass"])
    require_median = bool(protocol["promotion_requires_median_pass"])

    windows_total = len(windows)
    windows_passed = 0
    degradations: list[float] = []
    reasons: list[str] = []

    for index, window in enumerate(windows):
        train_segment_id = f"wf-train-{index:03d}"
        val_segment_id = f"wf-val-{index:03d}"
        train_expectancy, train_ok, train_reason = _evaluate_window_segment(
            candidate_settings=candidate_settings,
            source_db_path=source_db_path,
            snapshots_dir=snapshots_dir,
            segment_id=train_segment_id,
            start_ts=window.train_start,
            end_ts=window.train_end,
            min_trades=min_trades_per_window,
        )
        val_expectancy, val_ok, val_reason = _evaluate_window_segment(
            candidate_settings=candidate_settings,
            source_db_path=source_db_path,
            snapshots_dir=snapshots_dir,
            segment_id=val_segment_id,
            start_ts=window.validation_start,
            end_ts=window.validation_end,
            min_trades=min_trades_per_window,
        )

        if train_ok and val_ok:
            windows_passed += 1
            degradations.append(_degradation_pct(train_expectancy, val_expectancy))
            continue

        detail = train_reason if not train_ok else val_reason
        reasons.append(f"window_{index:03d}_failed: {detail}")

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
    )

