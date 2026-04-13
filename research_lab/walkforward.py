from __future__ import annotations

import dataclasses
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from backtest.backtest_runner import BacktestConfig
from settings import AppSettings

from research_lab.db_snapshot import create_trial_snapshot, open_snapshot_connection, verify_required_tables
from research_lab.integrations.optuna_driver import run_optuna_study
from research_lab.objective import evaluate_candidate
from research_lab.pareto import compute_pareto_frontier, rank_pareto_candidates
from research_lab.protocol import hash_protocol
from research_lab.settings_adapter import build_candidate_settings
from research_lab.types import (
    NestedWalkForwardCandidateSummary,
    NestedWalkForwardReport,
    NestedWalkForwardWindowResult,
    ObjectiveMetrics,
    SignalFunnel,
    TrialEvaluation,
    WalkForwardReport,
    WalkForwardWindow,
)


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
    window_mode = str(protocol.get("window_mode", "rolling")).strip().lower()

    start = _parse_iso_datetime(data_start, is_end=False)
    end = _parse_iso_datetime(data_end, is_end=True)

    windows: list[WalkForwardWindow] = []
    cursor = start
    while True:
        if window_mode == "anchored_expanding":
            train_start = start
        elif window_mode == "rolling":
            train_start = cursor
        else:
            raise ValueError(
                f"Unsupported window_mode={window_mode!r}. Use 'rolling' or 'anchored_expanding'."
            )

        train_end = cursor + timedelta(days=train_days)
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
        snapshot_path.unlink(missing_ok=True)


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


def _window_seed(seed: int, index: int) -> int:
    return int(seed) + int(index)


def _nested_candidate_id(base_settings: AppSettings, candidate_params: dict[str, Any]) -> str:
    candidate_settings = build_candidate_settings(base_settings, candidate_params)
    return f"nested-{candidate_settings.config_hash[:12]}"


def _aggregate_objective_metrics(evaluations: list[TrialEvaluation]) -> ObjectiveMetrics:
    if not evaluations:
        return ObjectiveMetrics(
            expectancy_r=0.0,
            profit_factor=0.0,
            max_drawdown_pct=0.0,
            trades_count=0,
            sharpe_ratio=0.0,
            pnl_abs=0.0,
            win_rate=0.0,
        )

    count = len(evaluations)
    return ObjectiveMetrics(
        expectancy_r=sum(item.metrics.expectancy_r for item in evaluations) / count,
        profit_factor=sum(item.metrics.profit_factor for item in evaluations) / count,
        max_drawdown_pct=max(item.metrics.max_drawdown_pct for item in evaluations),
        trades_count=sum(item.metrics.trades_count for item in evaluations),
        sharpe_ratio=sum(item.metrics.sharpe_ratio for item in evaluations) / count,
        pnl_abs=sum(item.metrics.pnl_abs for item in evaluations),
        win_rate=sum(item.metrics.win_rate for item in evaluations) / count,
    )


def _aggregate_signal_funnel(evaluations: list[TrialEvaluation]) -> SignalFunnel:
    return SignalFunnel(
        signals_generated=sum(item.funnel.signals_generated for item in evaluations),
        signals_regime_blocked=sum(item.funnel.signals_regime_blocked for item in evaluations),
        signals_governance_rejected=sum(item.funnel.signals_governance_rejected for item in evaluations),
        signals_risk_rejected=sum(item.funnel.signals_risk_rejected for item in evaluations),
        signals_executed=sum(item.funnel.signals_executed for item in evaluations),
    )


def _nested_candidate_sort_key(summary: NestedWalkForwardCandidateSummary) -> tuple[Any, ...]:
    evaluation = summary.evaluation
    return (
        -summary.windows_passed,
        -summary.windows_won,
        -evaluation.metrics.expectancy_r,
        -evaluation.metrics.profit_factor,
        evaluation.metrics.max_drawdown_pct,
        -evaluation.metrics.trades_count,
        evaluation.trial_id,
    )


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


def run_nested_walkforward(
    *,
    base_settings: AppSettings,
    windows: list[WalkForwardWindow],
    source_db_path: Path,
    snapshots_dir: Path,
    store_path: Path,
    protocol: dict[str, Any],
    base_n_trials: int,
    study_name_prefix: str,
    seed: int,
) -> NestedWalkForwardReport:
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
    train_trials_total = 0
    degradations: list[float] = []
    reasons: list[str] = []
    window_results: list[NestedWalkForwardWindowResult] = []
    candidate_bucket: dict[str, dict[str, Any]] = {}

    for index, window in enumerate(windows):
        window_seed = _window_seed(seed, index)
        study_name = f"{study_name_prefix}-window-{index:03d}-train"
        train_trials = run_optuna_study(
            source_db_path=source_db_path,
            store_path=store_path,
            snapshots_dir=snapshots_dir,
            backtest_config=BacktestConfig(
                start_date=window.train_start,
                end_date=window.train_end,
                symbol=base_settings.strategy.symbol,
            ),
            base_settings=base_settings,
            n_trials=int(base_n_trials),
            study_name=study_name,
            seed=window_seed,
            min_trades=min_trades_per_window,
            protocol_hash=protocol_hash,
        )
        train_trials_total += len(train_trials)
        frontier = rank_pareto_candidates(compute_pareto_frontier(train_trials))
        if not frontier:
            reason = "no_train_candidate"
            reasons.append(f"window_{index:03d}_{reason}")
            window_results.append(
                NestedWalkForwardWindowResult(
                    window_index=index,
                    window=window,
                    study_name=study_name,
                    seed=window_seed,
                    champion_trial_id=None,
                    champion_candidate_id=None,
                    champion_params={},
                    train_evaluation=None,
                    validation_evaluation=None,
                    validation_passed=False,
                    reasons=(reason,),
                )
            )
            continue

        champion_train = frontier[0]
        champion_candidate_id = _nested_candidate_id(base_settings, champion_train.params)
        champion_settings = build_candidate_settings(base_settings, champion_train.params)
        validation_raw = _evaluate_window_segment(
            candidate_settings=champion_settings,
            source_db_path=source_db_path,
            snapshots_dir=snapshots_dir,
            segment_id=f"{study_name_prefix}-window-{index:03d}-validation",
            start_ts=window.validation_start,
            end_ts=window.validation_end,
            min_trades=min_trades_per_window,
        )
        validation_evaluation = dataclasses.replace(
            validation_raw,
            trial_id=champion_candidate_id,
            params=champion_train.params,
            protocol_hash=protocol_hash,
        )
        validation_failures = _segment_failures(
            evaluation=validation_evaluation,
            min_expectancy_r=min_expectancy_r,
            min_profit_factor=min_profit_factor,
            max_drawdown_pct=max_drawdown_pct,
            min_sharpe_ratio=min_sharpe_ratio,
        )
        validation_passed = not validation_failures
        if validation_passed:
            windows_passed += 1
        degradations.append(
            _degradation_pct(champion_train.metrics.expectancy_r, validation_evaluation.metrics.expectancy_r)
        )
        for detail in validation_failures:
            reasons.append(f"window_{index:03d}_validation_failed: {detail}")

        window_results.append(
            NestedWalkForwardWindowResult(
                window_index=index,
                window=window,
                study_name=study_name,
                seed=window_seed,
                champion_trial_id=champion_train.trial_id,
                champion_candidate_id=champion_candidate_id,
                champion_params=champion_train.params,
                train_evaluation=champion_train,
                validation_evaluation=validation_evaluation,
                validation_passed=validation_passed,
                reasons=tuple(validation_failures),
            )
        )

        bucket = candidate_bucket.setdefault(
            champion_candidate_id,
            {
                "params": dict(champion_train.params),
                "evaluations": [],
                "window_indices": [],
                "windows_won": 0,
                "windows_passed": 0,
            },
        )
        bucket["evaluations"].append(validation_evaluation)
        bucket["window_indices"].append(index)
        bucket["windows_won"] += 1
        if validation_passed:
            bucket["windows_passed"] += 1

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

    candidate_summaries: list[NestedWalkForwardCandidateSummary] = []
    for candidate_id, bucket in candidate_bucket.items():
        evaluations = list(bucket["evaluations"])
        aggregated_evaluation = TrialEvaluation(
            trial_id=candidate_id,
            params=dict(bucket["params"]),
            metrics=_aggregate_objective_metrics(evaluations),
            funnel=_aggregate_signal_funnel(evaluations),
            rejected_reason=None,
            protocol_hash=protocol_hash,
        )
        candidate_summaries.append(
            NestedWalkForwardCandidateSummary(
                candidate_id=candidate_id,
                params=dict(bucket["params"]),
                windows_won=int(bucket["windows_won"]),
                windows_passed=int(bucket["windows_passed"]),
                evaluation=aggregated_evaluation,
                contributing_window_indices=tuple(bucket["window_indices"]),
            )
        )

    candidate_summaries.sort(key=_nested_candidate_sort_key)
    selected_evaluation = candidate_summaries[0].evaluation if candidate_summaries else None
    if not candidate_summaries:
        reasons.append("no_nested_candidate_available")

    return NestedWalkForwardReport(
        passed=passed,
        windows_total=windows_total,
        windows_passed=windows_passed,
        is_degradation_pct=avg_degradation,
        fragile=fragile,
        reasons=tuple(reasons),
        protocol_hash=protocol_hash,
        train_trials_total=train_trials_total,
        selected_evaluation=selected_evaluation,
        candidate_summaries=tuple(candidate_summaries),
        window_results=tuple(window_results),
    )
