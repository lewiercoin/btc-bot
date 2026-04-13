from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

from backtest.backtest_runner import BacktestConfig
from research_lab.autoresearch_loop import run_autoresearch_loop
from research_lab.baseline_gate import BaselineGateError, check_baseline
from research_lab.approval import write_approval_bundle
from research_lab.cli import main as research_lab_main
from research_lab.constants import PARAM_STATUS_ACTIVE, PARAM_STATUS_FROZEN, PARAM_STATUS_UNSUPPORTED
from research_lab.constraints import validate_param_vector
from research_lab.experiment_store import init_store, save_recommendation, save_trial, save_walkforward
from research_lab.param_registry import build_param_registry, get_active_params
from research_lab.pareto import compute_pareto_frontier
from research_lab.protocol import hash_protocol
from research_lab.reporter import build_experiment_report
from research_lab.settings_adapter import build_candidate_settings, diff_settings
from research_lab.types import (
    NestedWalkForwardCandidateSummary,
    NestedWalkForwardReport,
    ObjectiveMetrics,
    RecommendationDraft,
    SignalFunnel,
    TrialEvaluation,
    WalkForwardReport,
    WalkForwardWindow,
)
from research_lab import autoresearch_loop as autoresearch_loop_module
from research_lab.integrations import optuna_driver as optuna_driver_module
from research_lab import walkforward as walkforward_module
from research_lab.workflows import optimize_loop as optimize_loop_module
from research_lab.workflows import replay_candidate as replay_candidate_module
from settings import load_settings


def _trial(trial_id: str, expectancy_r: float, profit_factor: float, max_drawdown_pct: float) -> TrialEvaluation:
    return TrialEvaluation(
        trial_id=trial_id,
        params={},
        metrics=ObjectiveMetrics(
            expectancy_r=expectancy_r,
            profit_factor=profit_factor,
            max_drawdown_pct=max_drawdown_pct,
            trades_count=100,
            sharpe_ratio=1.0,
            pnl_abs=1000.0,
            win_rate=0.5,
        ),
        funnel=SignalFunnel(
            signals_generated=10,
            signals_regime_blocked=1,
            signals_governance_rejected=1,
            signals_risk_rejected=1,
            signals_executed=7,
        ),
        rejected_reason=None,
    )


def _trial_with_params(
    trial_id: str,
    params: dict[str, float],
    *,
    expectancy_r: float,
    profit_factor: float,
    max_drawdown_pct: float,
    trades_count: int = 20,
) -> TrialEvaluation:
    return TrialEvaluation(
        trial_id=trial_id,
        params=params,
        metrics=ObjectiveMetrics(
            expectancy_r=expectancy_r,
            profit_factor=profit_factor,
            max_drawdown_pct=max_drawdown_pct,
            trades_count=trades_count,
            sharpe_ratio=1.0,
            pnl_abs=100.0,
            win_rate=0.5,
        ),
        funnel=SignalFunnel(
            signals_generated=10,
            signals_regime_blocked=1,
            signals_governance_rejected=1,
            signals_risk_rejected=1,
            signals_executed=7,
        ),
        rejected_reason=None,
    )


def _autoresearch_protocol(*, walkforward_mode: str = "post_hoc") -> dict[str, object]:
    return {
        "walkforward_mode": walkforward_mode,
        "train_days": 90,
        "validation_days": 30,
        "step_days": 30,
        "min_trades_per_window": 10,
        "min_expectancy_r_per_window": 0.0,
        "min_profit_factor_per_window": 1.0,
        "max_drawdown_pct_per_window": 50.0,
        "min_sharpe_ratio_per_window": 0.0,
        "min_trades_full_candidate": 30,
        "fragility_degradation_threshold_pct": 30.0,
        "promotion_requires_all_windows_pass": False,
        "promotion_requires_median_pass": True,
    }


def _write_protocol(path: Path, *, walkforward_mode: str = "post_hoc") -> Path:
    path.write_text(
        json.dumps(_autoresearch_protocol(walkforward_mode=walkforward_mode), indent=2),
        encoding="utf-8",
    )
    return path


class _FakeSnapshotConn:
    def close(self) -> None:
        return None


class _FakeOptunaTrial:
    def __init__(self, number: int) -> None:
        self.number = number
        self.user_attrs: dict[str, object] = {}

    def set_user_attr(self, key: str, value: object) -> None:
        self.user_attrs[key] = value


class _FakeOptunaStudy:
    def __init__(self) -> None:
        self.metric_names: list[str] | None = None
        self.trials: list[_FakeOptunaTrial] = []
        self.results: list[tuple[float, float, float]] = []
        self.enqueued_params: list[dict[str, object]] = []

    def set_metric_names(self, names: list[str]) -> None:
        self.metric_names = names

    def enqueue_trial(self, params: dict[str, object]) -> None:
        self.enqueued_params.append(dict(params))

    def optimize(self, objective, n_trials: int) -> None:
        for number in range(int(n_trials)):
            trial = _FakeOptunaTrial(number)
            self.trials.append(trial)
            self.results.append(objective(trial))


def _patch_autoresearch_snapshot_io(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        autoresearch_loop_module,
        "create_trial_snapshot",
        lambda *args, **kwargs: tmp_path / "snapshot.db",
    )
    monkeypatch.setattr(
        autoresearch_loop_module,
        "open_snapshot_connection",
        lambda _: _FakeSnapshotConn(),
    )
    monkeypatch.setattr(autoresearch_loop_module, "verify_required_tables", lambda conn: None)


def test_param_registry_frozen_params_are_correct() -> None:
    registry = build_param_registry()

    assert registry["weight_force_order_spike"].status == PARAM_STATUS_FROZEN
    assert registry["ema_fast"].status == PARAM_STATUS_FROZEN
    assert registry["ema_slow"].status == PARAM_STATUS_FROZEN
    assert registry["ema_trend_gap_pct"].status == PARAM_STATUS_ACTIVE
    assert registry["compression_atr_norm_max"].status == PARAM_STATUS_ACTIVE
    assert registry["crowded_funding_extreme_pct"].status == PARAM_STATUS_FROZEN
    assert registry["crowded_oi_zscore_min"].status == PARAM_STATUS_FROZEN
    assert registry["regime_direction_whitelist"].status == PARAM_STATUS_FROZEN
    assert registry["session_start_hour_utc"].status == PARAM_STATUS_FROZEN
    assert registry["session_end_hour_utc"].status == PARAM_STATUS_FROZEN
    assert registry["allow_long_in_uptrend"].status == PARAM_STATUS_ACTIVE
    assert registry["allow_long_in_uptrend"].domain_type == "bool"
    assert registry["weight_ema_trend_alignment"].status == PARAM_STATUS_ACTIVE
    assert registry["weight_ema_trend_alignment"].low == 0.0
    assert registry["weight_ema_trend_alignment"].high == 5.0
    assert registry["ema_trend_gap_pct"].default_value == 0.0025
    assert registry["compression_atr_norm_max"].default_value == 0.0055
    assert registry["crowded_funding_extreme_pct"].default_value == 85.0
    assert registry["crowded_oi_zscore_min"].default_value == 1.5
    assert registry["force_order_history_points"].status == PARAM_STATUS_UNSUPPORTED
    assert "allow_long_in_uptrend" in get_active_params()
    assert "ema_trend_gap_pct" in get_active_params()
    assert "compression_atr_norm_max" in get_active_params()
    assert "weight_ema_trend_alignment" in get_active_params()


def test_build_windows_defaults_to_rolling_mode() -> None:
    windows = walkforward_module.build_windows(
        data_start="2025-01-01",
        data_end="2025-07-01",
        protocol={
            "train_days": 90,
            "validation_days": 30,
            "step_days": 30,
        },
    )

    assert windows == [
        WalkForwardWindow(
            train_start="2025-01-01T00:00:00+00:00",
            train_end="2025-04-01T00:00:00+00:00",
            validation_start="2025-04-01T00:00:00+00:00",
            validation_end="2025-05-01T00:00:00+00:00",
        ),
        WalkForwardWindow(
            train_start="2025-01-31T00:00:00+00:00",
            train_end="2025-05-01T00:00:00+00:00",
            validation_start="2025-05-01T00:00:00+00:00",
            validation_end="2025-05-31T00:00:00+00:00",
        ),
        WalkForwardWindow(
            train_start="2025-03-02T00:00:00+00:00",
            train_end="2025-05-31T00:00:00+00:00",
            validation_start="2025-05-31T00:00:00+00:00",
            validation_end="2025-06-30T00:00:00+00:00",
        ),
    ]


def test_build_windows_supports_anchored_expanding_mode() -> None:
    windows = walkforward_module.build_windows(
        data_start="2022-01-01",
        data_end="2026-03-01",
        protocol={
            "window_mode": "anchored_expanding",
            "train_days": 730,
            "validation_days": 365,
            "step_days": 365,
        },
    )

    assert windows == [
        WalkForwardWindow(
            train_start="2022-01-01T00:00:00+00:00",
            train_end="2024-01-01T00:00:00+00:00",
            validation_start="2024-01-01T00:00:00+00:00",
            validation_end="2024-12-31T00:00:00+00:00",
        ),
        WalkForwardWindow(
            train_start="2022-01-01T00:00:00+00:00",
            train_end="2024-12-31T00:00:00+00:00",
            validation_start="2024-12-31T00:00:00+00:00",
            validation_end="2025-12-31T00:00:00+00:00",
        ),
    ]


def _make_trial_evaluation(*, trades_count: int, rejected_reason: str | None) -> TrialEvaluation:
    return TrialEvaluation(
        trial_id="raw-evaluation",
        params={},
        metrics=ObjectiveMetrics(
            expectancy_r=0.2,
            profit_factor=1.5,
            max_drawdown_pct=0.1,
            trades_count=trades_count,
            sharpe_ratio=1.0,
            pnl_abs=100.0,
            win_rate=0.5,
        ),
        funnel=SignalFunnel(
            signals_generated=10,
            signals_regime_blocked=1,
            signals_governance_rejected=1,
            signals_risk_rejected=1,
            signals_executed=7,
        ),
        rejected_reason=rejected_reason,
    )


def _run_optuna_driver_case(
    *,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    evaluation: TrialEvaluation,
) -> tuple[_FakeOptunaStudy, list[TrialEvaluation]]:
    study = _FakeOptunaStudy()
    saved_trials: list[TrialEvaluation] = []
    fake_optuna = SimpleNamespace(
        samplers=SimpleNamespace(TPESampler=lambda **kwargs: object()),
        create_study=lambda **kwargs: study,
    )

    monkeypatch.setattr(optuna_driver_module, "_require_optuna", lambda: fake_optuna)
    monkeypatch.setattr(optuna_driver_module, "build_optuna_trial_params", lambda trial: {})
    monkeypatch.setattr(optuna_driver_module, "validate_param_vector", lambda params: [])
    monkeypatch.setattr(optuna_driver_module, "build_candidate_settings", lambda base_settings, params: base_settings)
    monkeypatch.setattr(
        optuna_driver_module,
        "create_trial_snapshot",
        lambda *args, **kwargs: tmp_path / "snapshot.db",
    )
    monkeypatch.setattr(optuna_driver_module, "open_snapshot_connection", lambda _: _FakeSnapshotConn())
    monkeypatch.setattr(optuna_driver_module, "verify_required_tables", lambda conn: None)
    monkeypatch.setattr(optuna_driver_module, "evaluate_candidate", lambda *args, **kwargs: evaluation)
    monkeypatch.setattr(optuna_driver_module, "init_store", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        optuna_driver_module,
        "save_trial",
        lambda evaluation, store_path: saved_trials.append(evaluation),
    )

    settings = load_settings(project_root=tmp_path)
    optuna_driver_module.run_optuna_study(
        source_db_path=tmp_path / "source.db",
        store_path=tmp_path / "research_lab.db",
        snapshots_dir=tmp_path / "snapshots",
        backtest_config=BacktestConfig(
            start_date="2022-01-01",
            end_date="2026-03-01",
            symbol=settings.strategy.symbol,
        ),
        base_settings=settings,
        n_trials=1,
        study_name="run13-test",
        min_trades=100,
    )
    return study, saved_trials


def test_run_optuna_study_hard_blocks_trials_below_80_trades(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    study, saved_trials = _run_optuna_driver_case(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        evaluation=_make_trial_evaluation(
            trades_count=79,
            rejected_reason="MIN_TRADES_NOT_MET: trades_count=79 < min_trades=100",
        ),
    )

    assert study.metric_names == ["expectancy_r", "profit_factor", "max_drawdown_pct"]
    assert study.results == [(-2.0, 0.1, 1.0)]
    assert study.trials[0].user_attrs["constraint_violations"] == [1.0]
    assert study.trials[0].user_attrs["rejection_reason"] == (
        "MIN_TRADES_HARD_BLOCK: trades_count=79 < hard_min_trades=80"
    )
    assert saved_trials[0].metrics.trades_count == 79


def test_run_optuna_study_soft_penalizes_trials_between_80_and_min_trades(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    study, saved_trials = _run_optuna_driver_case(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        evaluation=_make_trial_evaluation(
            trades_count=85,
            rejected_reason="MIN_TRADES_NOT_MET: trades_count=85 < min_trades=100",
        ),
    )

    exp_r, profit_factor, max_drawdown_pct = study.results[0]
    assert exp_r == pytest.approx(0.189875)
    assert profit_factor == pytest.approx(1.49325)
    assert max_drawdown_pct == pytest.approx(0.105625)
    assert study.trials[0].user_attrs["constraint_violations"] == []
    assert study.trials[0].user_attrs["rejection_reason"] == (
        "MIN_TRADES_NOT_MET: trades_count=85 < min_trades=100"
    )
    assert saved_trials[0].metrics.trades_count == 85


def test_enqueue_warm_start_trials_falls_back_to_history_when_protocol_hash_changes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = load_settings(project_root=tmp_path)
    study = _FakeOptunaStudy()
    store_path = tmp_path / "research_lab.db"
    store_path.write_text("", encoding="utf-8")
    historical_trial = TrialEvaluation(
        trial_id="historical-winner",
        params={
            "allow_long_in_uptrend": True,
            "tp1_atr_mult": 2.5,
        },
        metrics=ObjectiveMetrics(
            expectancy_r=0.6363,
            profit_factor=1.6165,
            max_drawdown_pct=0.4049,
            trades_count=339,
            sharpe_ratio=3.33,
            pnl_abs=118433.35,
            win_rate=0.277,
        ),
        funnel=SignalFunnel(
            signals_generated=10,
            signals_regime_blocked=1,
            signals_governance_rejected=1,
            signals_risk_rejected=1,
            signals_executed=7,
        ),
        rejected_reason=None,
        protocol_hash="run12-protocol-hash",
    )

    monkeypatch.setattr(optuna_driver_module, "load_trials", lambda store_path: [historical_trial])
    monkeypatch.setattr(optuna_driver_module, "compute_pareto_frontier", lambda trials: trials)
    monkeypatch.setattr(optuna_driver_module, "rank_pareto_candidates", lambda trials: trials)

    optuna_driver_module._enqueue_warm_start_trials(
        study,
        base_settings=settings,
        store_path=store_path,
        protocol_hash="run13-protocol-hash",
        warm_start_top_n=1,
    )

    assert study.enqueued_params[0]["allow_long_in_uptrend"] is False
    assert study.enqueued_params[1] == historical_trial.params


def test_constraints_rejects_invalid_vectors() -> None:
    violations = validate_param_vector(
        {
            "ema_fast": 50,
            "ema_slow": 50,
            "tp1_atr_mult": 2.0,
            "tp2_atr_mult": 2.0,
            "min_rr": 1.0,
        }
    )

    assert "ema_fast must be < ema_slow" in violations
    assert "tp1_atr_mult must be < tp2_atr_mult" in violations
    assert "min_rr must be > 1.0" in violations


def test_param_registry_unlock_ranges_are_updated() -> None:
    registry = build_param_registry()

    assert (registry["atr_period"].low, registry["atr_period"].high, registry["atr_period"].step) == (8, 50, 1)
    assert (registry["confluence_min"].low, registry["confluence_min"].high, registry["confluence_min"].step) == (
        2.5,
        4.5,
        0.1,
    )
    assert (
        registry["direction_tfi_threshold"].low,
        registry["direction_tfi_threshold"].high,
        registry["direction_tfi_threshold"].step,
    ) == (0.01, 0.5, 0.01)
    assert (
        registry["tfi_impulse_threshold"].low,
        registry["tfi_impulse_threshold"].high,
        registry["tfi_impulse_threshold"].step,
    ) == (0.05, 0.5, 0.01)
    assert (
        registry["equal_level_tol_atr"].low,
        registry["equal_level_tol_atr"].high,
        registry["equal_level_tol_atr"].step,
    ) == (0.01, 0.3, 0.01)


def test_settings_adapter_roundtrip(tmp_path: Path) -> None:
    base = load_settings(project_root=tmp_path)
    candidate = build_candidate_settings(base, {"tp1_atr_mult": 3.3})
    settings_diff = diff_settings(base, candidate)

    assert candidate.strategy.tp1_atr_mult == 3.3
    assert base.strategy.tp1_atr_mult == 2.5
    assert settings_diff == {"tp1_atr_mult": {"from": 2.5, "to": 3.3}}


def test_pareto_frontier_dominance() -> None:
    trial_a = _trial("A", expectancy_r=1.2, profit_factor=2.0, max_drawdown_pct=0.10)
    trial_b = _trial("B", expectancy_r=1.0, profit_factor=1.8, max_drawdown_pct=0.20)
    trial_c = _trial("C", expectancy_r=1.2, profit_factor=1.7, max_drawdown_pct=0.05)

    frontier = compute_pareto_frontier([trial_a, trial_b, trial_c])

    assert [trial.trial_id for trial in frontier] == ["A", "C"]


def test_approval_bundle_does_not_write_settings(tmp_path: Path) -> None:
    output_dir = tmp_path / "approval_bundle"
    recommendation = RecommendationDraft(
        candidate_id="candidate-001",
        summary="smoke recommendation",
        params_diff={"tp1_atr_mult": {"from": 2.5, "to": 3.0}},
        expected_improvement={"expectancy_r": 0.1},
        risks=(),
        approval_required=True,
    )

    write_approval_bundle(recommendation=recommendation, output_dir=output_dir)

    assert not (output_dir / "settings.py").exists()
    assert (output_dir / "recommendation.json").exists()
    assert (output_dir / "params_diff.json").exists()
    assert (output_dir / "candidate_settings.json").exists()


def test_build_approval_bundle_cli_rejects_blocking_walkforward_risk(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    store_path = tmp_path / "research_lab.db"
    output_dir = tmp_path / "approval_bundle"
    recommendation = RecommendationDraft(
        candidate_id="candidate-002",
        summary="blocked recommendation",
        params_diff={"tp1_atr_mult": {"from": 2.5, "to": 3.0}},
        expected_improvement={"expectancy_r": 0.1},
        risks=("walkforward_not_passed",),
        approval_required=True,
    )
    save_recommendation(rec=recommendation, store_path=store_path)

    with pytest.raises(SystemExit) as exc_info:
        research_lab_main(
            [
                "build-approval-bundle",
                "--candidate-id",
                recommendation.candidate_id,
                "--store-path",
                str(store_path),
                "--output-dir",
                str(output_dir),
            ]
        )

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "blocking promotion risks detected" in captured.err
    assert "walkforward_not_passed" in captured.err
    assert not output_dir.exists()


def test_build_approval_bundle_cli_writes_files_for_clean_recommendation(tmp_path: Path) -> None:
    store_path = tmp_path / "research_lab.db"
    output_dir = tmp_path / "approval_bundle"
    recommendation = RecommendationDraft(
        candidate_id="candidate-003",
        summary="clean recommendation",
        params_diff={"tp1_atr_mult": {"from": 2.5, "to": 3.0}},
        expected_improvement={"expectancy_r": 0.1},
        risks=(),
        approval_required=True,
    )
    save_recommendation(rec=recommendation, store_path=store_path)

    research_lab_main(
        [
            "build-approval-bundle",
            "--candidate-id",
            recommendation.candidate_id,
            "--store-path",
            str(store_path),
            "--output-dir",
            str(output_dir),
        ]
    )

    assert (output_dir / "recommendation.json").exists()
    assert (output_dir / "params_diff.json").exists()
    assert (output_dir / "candidate_settings.json").exists()


def test_baseline_gate_raises_on_empty_db(tmp_path: Path) -> None:
    schema_sql = (Path(__file__).resolve().parents[1] / "storage" / "schema.sql").read_text(encoding="utf-8")
    memory_conn = sqlite3.connect(":memory:")
    try:
        memory_conn.executescript(schema_sql)
        disk_db_path = tmp_path / "empty_source.db"
        disk_conn = sqlite3.connect(disk_db_path)
        try:
            memory_conn.backup(disk_conn)
        finally:
            disk_conn.close()
    finally:
        memory_conn.close()

    config = BacktestConfig(
        start_date="2025-01-01",
        end_date="2025-03-31",
        initial_equity=10_000.0,
    )
    settings = load_settings(project_root=tmp_path)

    with pytest.raises(BaselineGateError) as exc_info:
        check_baseline(
            source_db_path=disk_db_path,
            backtest_config=config,
            base_settings=settings,
        )

    message = str(exc_info.value)
    assert "trades=0" in message
    assert "2025-01-01" in message
    assert "2025-03-31" in message
    assert "aggtrade_buckets" in message


@pytest.mark.skip(reason="level_min_age_bars and min_hits don't exist in StrategyConfig at commit 8f2c6f2")
def test_run_optimize_loop_uses_protocol_min_trades_full_candidate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = load_settings(project_root=tmp_path)
    source_db_path = tmp_path / "source.db"
    store_path = tmp_path / "research_lab.db"
    snapshots_dir = tmp_path / "snapshots"
    config = BacktestConfig(
        start_date="2025-01-01",
        end_date="2025-03-31",
        initial_equity=10_000.0,
        symbol=settings.strategy.symbol,
    )

    protocol_lo = tmp_path / "protocol_lo.json"
    protocol_hi = tmp_path / "protocol_hi.json"
    protocol_payload = {
        "train_days": 90,
        "validation_days": 30,
        "step_days": 30,
        "min_trades_per_window": 10,
        "fragility_degradation_threshold_pct": 30.0,
        "promotion_requires_all_windows_pass": False,
        "promotion_requires_median_pass": True,
    }
    protocol_lo.write_text(
        json.dumps({**protocol_payload, "min_trades_full_candidate": 3}, indent=2),
        encoding="utf-8",
    )
    protocol_hi.write_text(
        json.dumps({**protocol_payload, "min_trades_full_candidate": 999}, indent=2),
        encoding="utf-8",
    )

    captured_min_trades: list[int] = []

    def fake_run_optuna_study(**kwargs):
        min_trades = int(kwargs["min_trades"])
        captured_min_trades.append(min_trades)
        if min_trades >= 999:
            return [
                TrialEvaluation(
                    trial_id="trial-rejected",
                    params={"tp1_atr_mult": 3.0},
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
                    rejected_reason="MIN_TRADES_NOT_MET",
                )
            ]
        return [
            TrialEvaluation(
                trial_id="trial-accepted",
                params={"tp1_atr_mult": 3.0},
                metrics=ObjectiveMetrics(
                    expectancy_r=0.2,
                    profit_factor=1.5,
                    max_drawdown_pct=0.1,
                    trades_count=12,
                    sharpe_ratio=1.0,
                    pnl_abs=100.0,
                    win_rate=0.5,
                ),
                funnel=SignalFunnel(
                    signals_generated=10,
                    signals_regime_blocked=1,
                    signals_governance_rejected=1,
                    signals_risk_rejected=1,
                    signals_executed=7,
                ),
                rejected_reason=None,
            )
        ]

    monkeypatch.setattr(optimize_loop_module, "check_baseline", lambda **_: None)
    monkeypatch.setattr(optimize_loop_module, "run_optuna_study", fake_run_optuna_study)
    monkeypatch.setattr(optimize_loop_module, "compute_pareto_frontier", lambda trials: [t for t in trials if t.rejected_reason is None])
    monkeypatch.setattr(optimize_loop_module, "rank_pareto_candidates", lambda frontier: frontier)
    monkeypatch.setattr(
        optimize_loop_module,
        "run_walkforward",
        lambda **_: WalkForwardReport(
            passed=True,
            windows_total=1,
            windows_passed=1,
            is_degradation_pct=0.0,
            fragile=False,
            reasons=(),
        ),
    )
    monkeypatch.setattr(optimize_loop_module, "save_walkforward", lambda *args, **kwargs: None)
    monkeypatch.setattr(optimize_loop_module, "save_recommendation", lambda *args, **kwargs: None)

    low_summary = optimize_loop_module.run_optimize_loop(
        source_db_path=source_db_path,
        store_path=store_path,
        snapshots_dir=snapshots_dir,
        backtest_config=config,
        base_settings=settings,
        n_trials=1,
        study_name="test-study",
        protocol_path=protocol_lo,
    )
    high_summary = optimize_loop_module.run_optimize_loop(
        source_db_path=source_db_path,
        store_path=store_path,
        snapshots_dir=snapshots_dir,
        backtest_config=config,
        base_settings=settings,
        n_trials=1,
        study_name="test-study",
        protocol_path=protocol_hi,
    )

    assert captured_min_trades == [3, 999]
    assert low_summary["trials_total"] == 1
    assert low_summary["pareto_candidates"] == 1
    assert low_summary["recommendations_saved"] == 1
    assert high_summary["trials_total"] == 1
    assert high_summary["pareto_candidates"] == 0
    assert high_summary["recommendations_saved"] == 0


def test_replay_candidate_uses_protocol_min_trades_full_candidate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = load_settings(project_root=tmp_path)
    config = BacktestConfig(
        start_date="2025-01-01",
        end_date="2025-03-31",
        initial_equity=10_000.0,
        symbol=settings.strategy.symbol,
    )
    protocol_path = tmp_path / "protocol.json"
    protocol_path.write_text(
        json.dumps(
            {
                "train_days": 90,
                "validation_days": 30,
                "step_days": 30,
                "min_trades_per_window": 10,
                "min_trades_full_candidate": 999,
                "fragility_degradation_threshold_pct": 30.0,
                "promotion_requires_all_windows_pass": False,
                "promotion_requires_median_pass": True,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    selected = TrialEvaluation(
        trial_id="candidate-001",
        params={"tp1_atr_mult": 3.0},
        metrics=ObjectiveMetrics(
            expectancy_r=0.2,
            profit_factor=1.5,
            max_drawdown_pct=0.1,
            trades_count=12,
            sharpe_ratio=1.0,
            pnl_abs=100.0,
            win_rate=0.5,
        ),
        funnel=SignalFunnel(
            signals_generated=10,
            signals_regime_blocked=1,
            signals_governance_rejected=1,
            signals_risk_rejected=1,
            signals_executed=7,
        ),
        rejected_reason=None,
    )

    captured_min_trades: list[int] = []

    class _FakeConn:
        def close(self) -> None:
            return None

    def fake_evaluate_candidate(connection, *, settings, backtest_config, min_trades):
        captured_min_trades.append(int(min_trades))
        return TrialEvaluation(
            trial_id="candidate-001",
            params={"tp1_atr_mult": 3.0},
            metrics=selected.metrics,
            funnel=selected.funnel,
            rejected_reason="MIN_TRADES_NOT_MET",
        )

    monkeypatch.setattr(replay_candidate_module, "load_trials", lambda _: [selected])
    monkeypatch.setattr(replay_candidate_module, "build_candidate_settings", lambda base, params: base)
    monkeypatch.setattr(replay_candidate_module, "create_trial_snapshot", lambda *args, **kwargs: tmp_path / "snapshot.db")
    monkeypatch.setattr(replay_candidate_module, "open_snapshot_connection", lambda _: _FakeConn())
    monkeypatch.setattr(replay_candidate_module, "verify_required_tables", lambda conn: None)
    monkeypatch.setattr(replay_candidate_module, "evaluate_candidate", fake_evaluate_candidate)
    monkeypatch.setattr(replay_candidate_module, "save_trial", lambda *args, **kwargs: None)
    monkeypatch.setattr(replay_candidate_module, "save_walkforward", lambda *args, **kwargs: None)
    monkeypatch.setattr(replay_candidate_module, "save_recommendation", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        replay_candidate_module,
        "run_walkforward",
        lambda **_: WalkForwardReport(
            passed=False,
            windows_total=1,
            windows_passed=0,
            is_degradation_pct=0.0,
            fragile=False,
            reasons=("no_window_passed",),
        ),
    )
    monkeypatch.setattr(
        replay_candidate_module,
        "build_recommendation",
        lambda **_: RecommendationDraft(
            candidate_id="candidate-001",
            summary="replayed",
            params_diff={},
            expected_improvement={},
            risks=("walkforward_not_passed",),
            approval_required=True,
        ),
    )

    replay_candidate_module.replay_candidate(
        candidate_id="candidate-001",
        base_settings=settings,
        source_db_path=tmp_path / "source.db",
        snapshots_dir=tmp_path / "snapshots",
        store_path=tmp_path / "research_lab.db",
        backtest_config=config,
        protocol_path=protocol_path,
    )

    assert captured_min_trades == [999]


def test_run_nested_walkforward_selects_aggregated_oos_winner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = load_settings(project_root=tmp_path)
    protocol = {
        "walkforward_mode": "nested",
        "train_days": 90,
        "validation_days": 30,
        "step_days": 30,
        "min_trades_per_window": 10,
        "min_expectancy_r_per_window": 0.0,
        "min_profit_factor_per_window": 1.0,
        "max_drawdown_pct_per_window": 50.0,
        "min_sharpe_ratio_per_window": 0.0,
        "fragility_degradation_threshold_pct": 30.0,
        "promotion_requires_all_windows_pass": False,
        "promotion_requires_median_pass": True,
    }
    params_a = {"tp1_atr_mult": 3.0}
    params_b = {"tp1_atr_mult": 3.4}
    expected_a_id = f"nested-{build_candidate_settings(settings, params_a).config_hash[:12]}"
    expected_b_id = f"nested-{build_candidate_settings(settings, params_b).config_hash[:12]}"
    windows = [
        WalkForwardWindow(
            train_start="2025-01-01T00:00:00+00:00",
            train_end="2025-03-31T00:00:00+00:00",
            validation_start="2025-03-31T00:00:00+00:00",
            validation_end="2025-04-30T00:00:00+00:00",
        ),
        WalkForwardWindow(
            train_start="2025-01-31T00:00:00+00:00",
            train_end="2025-04-30T00:00:00+00:00",
            validation_start="2025-04-30T00:00:00+00:00",
            validation_end="2025-05-30T00:00:00+00:00",
        ),
        WalkForwardWindow(
            train_start="2025-03-02T00:00:00+00:00",
            train_end="2025-05-31T00:00:00+00:00",
            validation_start="2025-05-31T00:00:00+00:00",
            validation_end="2025-06-30T00:00:00+00:00",
        ),
    ]
    captured_train_ranges: list[tuple[str, str, int, int, str]] = []
    train_trial_sets = [
        [
            TrialEvaluation(
                trial_id="win0-a",
                params=params_a,
                metrics=ObjectiveMetrics(0.30, 1.50, 10.0, 20, 1.0, 120.0, 0.55),
                funnel=SignalFunnel(10, 1, 1, 1, 7),
                rejected_reason=None,
            )
        ],
        [
            TrialEvaluation(
                trial_id="win1-b",
                params=params_b,
                metrics=ObjectiveMetrics(0.45, 1.70, 11.0, 22, 1.1, 150.0, 0.58),
                funnel=SignalFunnel(10, 1, 1, 1, 7),
                rejected_reason=None,
            )
        ],
        [
            TrialEvaluation(
                trial_id="win2-a",
                params=params_a,
                metrics=ObjectiveMetrics(0.28, 1.45, 9.0, 19, 0.9, 110.0, 0.53),
                funnel=SignalFunnel(10, 1, 1, 1, 7),
                rejected_reason=None,
            )
        ],
    ]
    validation_results = [
        TrialEvaluation(
            trial_id="val0",
            params={},
            metrics=ObjectiveMetrics(0.20, 1.20, 12.0, 12, 0.8, 60.0, 0.52),
            funnel=SignalFunnel(8, 1, 1, 1, 5),
            rejected_reason=None,
        ),
        TrialEvaluation(
            trial_id="val1",
            params={},
            metrics=ObjectiveMetrics(0.50, 1.80, 14.0, 11, 1.2, 90.0, 0.60),
            funnel=SignalFunnel(8, 1, 1, 1, 5),
            rejected_reason=None,
        ),
        TrialEvaluation(
            trial_id="val2",
            params={},
            metrics=ObjectiveMetrics(0.18, 1.10, 10.0, 10, 0.7, 50.0, 0.50),
            funnel=SignalFunnel(8, 1, 1, 1, 5),
            rejected_reason=None,
        ),
    ]

    def fake_run_optuna_study(**kwargs):
        config = kwargs["backtest_config"]
        captured_train_ranges.append(
            (
                str(config.start_date),
                str(config.end_date),
                int(kwargs["min_trades"]),
                int(kwargs["seed"]),
                str(kwargs["study_name"]),
            )
        )
        return train_trial_sets.pop(0)

    monkeypatch.setattr(walkforward_module, "run_optuna_study", fake_run_optuna_study)
    monkeypatch.setattr(walkforward_module, "_evaluate_window_segment", lambda **_: validation_results.pop(0))

    report = walkforward_module.run_nested_walkforward(
        base_settings=settings,
        windows=windows,
        source_db_path=tmp_path / "source.db",
        snapshots_dir=tmp_path / "snapshots",
        store_path=tmp_path / "research_lab.db",
        protocol=protocol,
        base_n_trials=5,
        study_name_prefix="nested-study",
        seed=7,
    )

    assert report.passed is True
    assert report.windows_passed == 3
    assert report.train_trials_total == 3
    assert report.selected_evaluation is not None
    assert report.selected_evaluation.trial_id == expected_a_id
    assert [summary.candidate_id for summary in report.candidate_summaries] == [expected_a_id, expected_b_id]
    assert report.candidate_summaries[0].windows_won == 2
    assert captured_train_ranges == [
        ("2025-01-01T00:00:00+00:00", "2025-03-31T00:00:00+00:00", 10, 7, "nested-study-window-000-train"),
        ("2025-01-31T00:00:00+00:00", "2025-04-30T00:00:00+00:00", 10, 8, "nested-study-window-001-train"),
        ("2025-03-02T00:00:00+00:00", "2025-05-31T00:00:00+00:00", 10, 9, "nested-study-window-002-train"),
    ]


@pytest.mark.skip(reason="level_min_age_bars and min_hits don't exist in StrategyConfig at commit 8f2c6f2")
def test_run_optimize_loop_uses_nested_mode_when_requested(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = load_settings(project_root=tmp_path)
    source_db_path = tmp_path / "source.db"
    store_path = tmp_path / "research_lab.db"
    snapshots_dir = tmp_path / "snapshots"
    config = BacktestConfig(
        start_date="2025-01-01",
        end_date="2025-03-31",
        initial_equity=10_000.0,
        symbol=settings.strategy.symbol,
    )
    protocol_path = tmp_path / "protocol_nested.json"
    protocol_path.write_text(
        json.dumps(
            {
                "walkforward_mode": "nested",
                "train_days": 90,
                "validation_days": 30,
                "step_days": 30,
                "min_trades_per_window": 10,
                "min_trades_full_candidate": 30,
                "fragility_degradation_threshold_pct": 30.0,
                "promotion_requires_all_windows_pass": False,
                "promotion_requires_median_pass": True,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    selected = TrialEvaluation(
        trial_id="nested-abcdef123456",
        params={"tp1_atr_mult": 3.0},
        metrics=ObjectiveMetrics(0.22, 1.55, 11.0, 21, 1.0, 130.0, 0.54),
        funnel=SignalFunnel(20, 2, 2, 2, 14),
        rejected_reason=None,
        protocol_hash="proto-hash",
    )
    report = NestedWalkForwardReport(
        passed=True,
        windows_total=2,
        windows_passed=2,
        is_degradation_pct=4.0,
        fragile=False,
        reasons=(),
        protocol_hash="proto-hash",
        train_trials_total=8,
        selected_evaluation=selected,
        candidate_summaries=(
            NestedWalkForwardCandidateSummary(
                candidate_id=selected.trial_id,
                params=selected.params,
                windows_won=2,
                windows_passed=2,
                evaluation=selected,
                contributing_window_indices=(0, 1),
            ),
        ),
    )
    captured_save_walkforward: list[str] = []
    captured_nested_args: list[dict[str, object]] = []

    monkeypatch.setattr(optimize_loop_module, "check_baseline", lambda **_: None)

    def fake_run_nested_walkforward(**kwargs):
        captured_nested_args.append(kwargs)
        return report

    monkeypatch.setattr(optimize_loop_module, "run_nested_walkforward", fake_run_nested_walkforward)
    monkeypatch.setattr(optimize_loop_module, "save_walkforward", lambda candidate_id, *_: captured_save_walkforward.append(candidate_id))
    monkeypatch.setattr(optimize_loop_module, "build_candidate_settings", lambda base, params: base)
    monkeypatch.setattr(
        optimize_loop_module,
        "build_recommendation",
        lambda **_: RecommendationDraft(
            candidate_id=selected.trial_id,
            summary="nested",
            params_diff={},
            expected_improvement={},
            risks=(),
            approval_required=True,
            protocol_hash="proto-hash",
        ),
    )
    monkeypatch.setattr(optimize_loop_module, "save_recommendation", lambda *args, **kwargs: None)

    summary = optimize_loop_module.run_optimize_loop(
        source_db_path=source_db_path,
        store_path=store_path,
        snapshots_dir=snapshots_dir,
        backtest_config=config,
        base_settings=settings,
        n_trials=8,
        study_name="nested-study",
        seed=99,
        protocol_path=protocol_path,
    )

    assert summary["walkforward_mode"] == "nested"
    assert summary["trials_total"] == 8
    assert summary["pareto_candidates"] == 1
    assert summary["recommendations_saved"] == 1
    assert summary["selected_candidate_id"] == selected.trial_id
    assert captured_save_walkforward == [selected.trial_id]
    assert len(captured_nested_args) == 1
    assert captured_nested_args[0]["base_n_trials"] == 8
    assert captured_nested_args[0]["study_name_prefix"] == "nested-study"
    assert captured_nested_args[0]["seed"] == 99


def test_replay_candidate_rejects_nested_mode(tmp_path: Path) -> None:
    settings = load_settings(project_root=tmp_path)
    config = BacktestConfig(
        start_date="2025-01-01",
        end_date="2025-03-31",
        initial_equity=10_000.0,
        symbol=settings.strategy.symbol,
    )
    protocol_path = tmp_path / "protocol_nested.json"
    protocol_path.write_text(
        json.dumps(
            {
                "walkforward_mode": "nested",
                "train_days": 90,
                "validation_days": 30,
                "step_days": 30,
                "min_trades_per_window": 10,
                "min_trades_full_candidate": 30,
                "fragility_degradation_threshold_pct": 30.0,
                "promotion_requires_all_windows_pass": False,
                "promotion_requires_median_pass": True,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    save_trial(
        TrialEvaluation(
            trial_id="candidate-001",
            params={"tp1_atr_mult": 3.0},
            metrics=ObjectiveMetrics(0.2, 1.5, 10.0, 20, 1.0, 100.0, 0.5),
            funnel=SignalFunnel(10, 1, 1, 1, 7),
            rejected_reason=None,
        ),
        tmp_path / "research_lab.db",
    )

    with pytest.raises(ValueError) as exc_info:
        replay_candidate_module.replay_candidate(
            candidate_id="candidate-001",
            base_settings=settings,
            source_db_path=tmp_path / "source.db",
            snapshots_dir=tmp_path / "snapshots",
            store_path=tmp_path / "research_lab.db",
            backtest_config=config,
            protocol_path=protocol_path,
        )

    assert "walkforward_mode='post_hoc'" in str(exc_info.value)


def test_run_walkforward_applies_multicriteria_thresholds(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = load_settings(project_root=tmp_path)
    protocol = {
        "train_days": 90,
        "validation_days": 30,
        "step_days": 30,
        "min_trades_per_window": 10,
        "min_expectancy_r_per_window": 0.0,
        "min_profit_factor_per_window": 1.0,
        "max_drawdown_pct_per_window": 50.0,
        "min_sharpe_ratio_per_window": 0.0,
        "fragility_degradation_threshold_pct": 30.0,
        "promotion_requires_all_windows_pass": False,
        "promotion_requires_median_pass": True,
    }
    segment_results = [
        TrialEvaluation(
            trial_id="wf-train-000",
            params={},
            metrics=ObjectiveMetrics(
                expectancy_r=0.30,
                profit_factor=1.40,
                max_drawdown_pct=12.0,
                trades_count=20,
                sharpe_ratio=1.20,
                pnl_abs=150.0,
                win_rate=0.55,
            ),
            funnel=SignalFunnel(
                signals_generated=10,
                signals_regime_blocked=1,
                signals_governance_rejected=1,
                signals_risk_rejected=1,
                signals_executed=7,
            ),
            rejected_reason=None,
        ),
        TrialEvaluation(
            trial_id="wf-val-000",
            params={},
            metrics=ObjectiveMetrics(
                expectancy_r=-0.10,
                profit_factor=0.90,
                max_drawdown_pct=55.0,
                trades_count=20,
                sharpe_ratio=-0.20,
                pnl_abs=-40.0,
                win_rate=0.45,
            ),
            funnel=SignalFunnel(
                signals_generated=8,
                signals_regime_blocked=1,
                signals_governance_rejected=1,
                signals_risk_rejected=1,
                signals_executed=5,
            ),
            rejected_reason=None,
        ),
    ]

    monkeypatch.setattr(
        walkforward_module,
        "_evaluate_window_segment",
        lambda **_: segment_results.pop(0),
    )

    report = walkforward_module.run_walkforward(
        base_settings=settings,
        candidate_params={},
        windows=[
            WalkForwardWindow(
                train_start="2025-01-01T00:00:00+00:00",
                train_end="2025-03-31T00:00:00+00:00",
                validation_start="2025-03-31T00:00:00+00:00",
                validation_end="2025-04-30T00:00:00+00:00",
            )
        ],
        source_db_path=tmp_path / "source.db",
        snapshots_dir=tmp_path / "snapshots",
        protocol=protocol,
    )

    assert report.passed is False
    assert report.windows_passed == 0
    assert report.protocol_hash == hash_protocol(protocol)
    assert "window_000_validation_failed: expectancy_r=-0.1000 < min_expectancy_r=0.0000" in report.reasons
    assert "window_000_validation_failed: profit_factor=0.9000 < min_profit_factor=1.0000" in report.reasons
    assert "window_000_validation_failed: max_drawdown_pct=55.0000 > max_drawdown_pct=50.0000" in report.reasons
    assert "window_000_validation_failed: sharpe_ratio=-0.2000 < min_sharpe_ratio=0.0000" in report.reasons


def test_protocol_hash_persists_through_store_and_report(tmp_path: Path) -> None:
    store_path = tmp_path / "research_lab.db"
    protocol_hash = "proto-hash-001"
    trial = TrialEvaluation(
        trial_id="candidate-001",
        params={"tp1_atr_mult": 3.0},
        metrics=ObjectiveMetrics(
            expectancy_r=0.25,
            profit_factor=1.6,
            max_drawdown_pct=9.0,
            trades_count=18,
            sharpe_ratio=1.1,
            pnl_abs=120.0,
            win_rate=0.52,
        ),
        funnel=SignalFunnel(
            signals_generated=10,
            signals_regime_blocked=1,
            signals_governance_rejected=1,
            signals_risk_rejected=1,
            signals_executed=7,
        ),
        rejected_reason=None,
        protocol_hash=protocol_hash,
    )
    report = WalkForwardReport(
        passed=True,
        windows_total=2,
        windows_passed=2,
        is_degradation_pct=5.0,
        fragile=False,
        reasons=(),
        protocol_hash=protocol_hash,
    )
    recommendation = RecommendationDraft(
        candidate_id="candidate-001",
        summary="with lineage",
        params_diff={"tp1_atr_mult": {"from": 2.5, "to": 3.0}},
        expected_improvement={"expectancy_r": 0.25},
        risks=(),
        approval_required=True,
        protocol_hash=protocol_hash,
    )

    save_trial(trial, store_path)
    save_walkforward(trial.trial_id, report, store_path)
    save_recommendation(recommendation, store_path)

    stored_trials = build_experiment_report(store_path)

    assert stored_trials["pareto_ranked"][0]["protocol_hash"] == protocol_hash
    assert stored_trials["walkforward_reports"][0]["protocol_hash"] == protocol_hash
    assert stored_trials["walkforward_reports"][0]["report_json"]["protocol_hash"] == protocol_hash
    assert stored_trials["recommendations"][0]["protocol_hash"] == protocol_hash
    assert stored_trials["recommendations"][0]["recommendation_json"]["protocol_hash"] == protocol_hash


def test_init_store_creates_protocol_hash_columns_in_fresh_schema(tmp_path: Path) -> None:
    store_path = tmp_path / "fresh_research_lab.db"
    init_store(store_path)

    conn = sqlite3.connect(store_path)
    conn.row_factory = sqlite3.Row
    try:
        trials_columns = {
            str(row["name"]): str(row["type"])
            for row in conn.execute("PRAGMA table_info(trials)").fetchall()
        }
        walkforward_columns = {
            str(row["name"]): str(row["type"])
            for row in conn.execute("PRAGMA table_info(walkforward_reports)").fetchall()
        }
        recommendations_columns = {
            str(row["name"]): str(row["type"])
            for row in conn.execute("PRAGMA table_info(recommendations)").fetchall()
        }
    finally:
        conn.close()

    assert trials_columns["protocol_hash"] == "TEXT"
    assert walkforward_columns["protocol_hash"] == "TEXT"
    assert recommendations_columns["protocol_hash"] == "TEXT"


def test_autoresearch_loop_single_pass_produces_ranked_loop_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = load_settings(project_root=tmp_path)
    protocol_path = _write_protocol(tmp_path / "protocol.json")
    output_dir = tmp_path / "autoresearch_output"
    generated_vectors = [
        {"tp1_atr_mult": 2.1, "tp2_atr_mult": 3.1},
        {"tp1_atr_mult": 2.6, "tp2_atr_mult": 3.6},
        {"tp1_atr_mult": 1.8, "tp2_atr_mult": 2.8},
    ]

    monkeypatch.setattr(autoresearch_loop_module, "check_baseline", lambda **_: None)
    monkeypatch.setattr(
        autoresearch_loop_module,
        "_generate_candidate_vectors",
        lambda **_: [dict(vector) for vector in generated_vectors],
    )
    _patch_autoresearch_snapshot_io(tmp_path, monkeypatch)
    monkeypatch.setattr(
        autoresearch_loop_module,
        "evaluate_candidate",
        lambda connection, *, settings, backtest_config, min_trades: _trial_with_params(
            trial_id=f"candidate-{settings.strategy.tp1_atr_mult:.2f}",
            params={},
            expectancy_r=float(settings.strategy.tp1_atr_mult),
            profit_factor=float(settings.strategy.tp2_atr_mult),
            max_drawdown_pct=10.0 - float(settings.strategy.tp1_atr_mult),
            trades_count=20 + int(float(settings.strategy.tp1_atr_mult) * 10),
        ),
    )
    monkeypatch.setattr(
        autoresearch_loop_module,
        "run_walkforward",
        lambda **_: WalkForwardReport(
            passed=True,
            windows_total=2,
            windows_passed=2,
            is_degradation_pct=0.0,
            fragile=False,
            reasons=(),
        ),
    )

    report = run_autoresearch_loop(
        source_db_path=tmp_path / "source.db",
        store_path=tmp_path / "research_lab.db",
        snapshots_dir=tmp_path / "snapshots",
        output_dir=output_dir,
        backtest_config=BacktestConfig(
            start_date="2025-01-01",
            end_date="2025-03-31",
            initial_equity=10_000.0,
            symbol=settings.strategy.symbol,
        ),
        base_settings=settings,
        protocol_path=protocol_path,
        max_candidates=3,
    )

    assert (output_dir / "loop_report.json").exists()
    assert len(report.results) == 3
    assert report.results[0].rank == 1
    assert report.approval_bundle_written is True
    assert (output_dir / "approval_bundle" / "recommendation.json").exists()


def test_autoresearch_loop_all_candidates_blocked_writes_no_bundle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = load_settings(project_root=tmp_path)
    protocol_path = _write_protocol(tmp_path / "protocol.json")
    output_dir = tmp_path / "autoresearch_output"
    generated_vectors = [
        {"tp1_atr_mult": 2.1, "tp2_atr_mult": 3.1},
        {"tp1_atr_mult": 2.6, "tp2_atr_mult": 3.6},
        {"tp1_atr_mult": 1.8, "tp2_atr_mult": 2.8},
    ]

    monkeypatch.setattr(autoresearch_loop_module, "check_baseline", lambda **_: None)
    monkeypatch.setattr(
        autoresearch_loop_module,
        "_generate_candidate_vectors",
        lambda **_: [dict(vector) for vector in generated_vectors],
    )
    _patch_autoresearch_snapshot_io(tmp_path, monkeypatch)
    monkeypatch.setattr(
        autoresearch_loop_module,
        "evaluate_candidate",
        lambda connection, *, settings, backtest_config, min_trades: _trial_with_params(
            trial_id=f"candidate-{settings.strategy.tp1_atr_mult:.2f}",
            params={},
            expectancy_r=float(settings.strategy.tp1_atr_mult),
            profit_factor=float(settings.strategy.tp2_atr_mult),
            max_drawdown_pct=10.0 - float(settings.strategy.tp1_atr_mult),
        ),
    )
    monkeypatch.setattr(
        autoresearch_loop_module,
        "run_walkforward",
        lambda **_: WalkForwardReport(
            passed=False,
            windows_total=2,
            windows_passed=0,
            is_degradation_pct=0.0,
            fragile=False,
            reasons=("walkforward_not_passed",),
        ),
    )

    report = run_autoresearch_loop(
        source_db_path=tmp_path / "source.db",
        store_path=tmp_path / "research_lab.db",
        snapshots_dir=tmp_path / "snapshots",
        output_dir=output_dir,
        backtest_config=BacktestConfig(
            start_date="2025-01-01",
            end_date="2025-03-31",
            initial_equity=10_000.0,
            symbol=settings.strategy.symbol,
        ),
        base_settings=settings,
        protocol_path=protocol_path,
        max_candidates=3,
    )

    assert (output_dir / "loop_report.json").exists()
    assert report.approval_bundle_written is False
    assert (output_dir / "approval_bundle").exists() is False


def test_autoresearch_loop_baseline_gate_failure_writes_empty_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = load_settings(project_root=tmp_path)
    protocol_path = _write_protocol(tmp_path / "protocol.json")
    output_dir = tmp_path / "autoresearch_output"

    def fail_baseline(**kwargs):
        raise BaselineGateError("baseline failed")

    monkeypatch.setattr(autoresearch_loop_module, "check_baseline", fail_baseline)

    report = run_autoresearch_loop(
        source_db_path=tmp_path / "source.db",
        store_path=tmp_path / "research_lab.db",
        snapshots_dir=tmp_path / "snapshots",
        output_dir=output_dir,
        backtest_config=BacktestConfig(
            start_date="2025-01-01",
            end_date="2025-03-31",
            initial_equity=10_000.0,
            symbol=settings.strategy.symbol,
        ),
        base_settings=settings,
        protocol_path=protocol_path,
        max_candidates=3,
    )

    assert report.stop_reason == "baseline_gate_failed"
    assert len(report.results) == 0
    assert (output_dir / "loop_report.json").exists()


def test_autoresearch_loop_rejects_nested_walkforward_mode(tmp_path: Path) -> None:
    settings = load_settings(project_root=tmp_path)
    protocol_path = _write_protocol(tmp_path / "protocol_nested.json", walkforward_mode="nested")

    with pytest.raises(ValueError) as exc_info:
        run_autoresearch_loop(
            source_db_path=tmp_path / "source.db",
            store_path=tmp_path / "research_lab.db",
            snapshots_dir=tmp_path / "snapshots",
            output_dir=tmp_path / "autoresearch_output",
            backtest_config=BacktestConfig(
                start_date="2025-01-01",
                end_date="2025-03-31",
                initial_equity=10_000.0,
                symbol=settings.strategy.symbol,
            ),
            base_settings=settings,
            protocol_path=protocol_path,
            max_candidates=3,
        )

    assert "autoresearch v1 requires walkforward_mode=post_hoc" in str(exc_info.value)


def test_autoresearch_loop_ranking_is_deterministic(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = load_settings(project_root=tmp_path)
    protocol_path = _write_protocol(tmp_path / "protocol.json")

    monkeypatch.setattr(autoresearch_loop_module, "check_baseline", lambda **_: None)
    _patch_autoresearch_snapshot_io(tmp_path, monkeypatch)
    monkeypatch.setattr(
        autoresearch_loop_module,
        "evaluate_candidate",
        lambda connection, *, settings, backtest_config, min_trades: _trial_with_params(
            trial_id=f"candidate-{settings.config_hash[:12]}",
            params={},
            expectancy_r=float(settings.strategy.tp1_atr_mult) + float(settings.strategy.tp2_atr_mult) / 10.0,
            profit_factor=float(settings.risk.min_rr),
            max_drawdown_pct=float(settings.risk.daily_dd_limit) * 100.0,
            trades_count=20 + int(float(settings.strategy.tp1_atr_mult) * 10),
        ),
    )
    monkeypatch.setattr(
        autoresearch_loop_module,
        "run_walkforward",
        lambda **_: WalkForwardReport(
            passed=True,
            windows_total=2,
            windows_passed=2,
            is_degradation_pct=0.0,
            fragile=False,
            reasons=(),
        ),
    )

    first_report = run_autoresearch_loop(
        source_db_path=tmp_path / "source.db",
        store_path=tmp_path / "run1.db",
        snapshots_dir=tmp_path / "snapshots_run1",
        output_dir=tmp_path / "output_run1",
        backtest_config=BacktestConfig(
            start_date="2025-01-01",
            end_date="2025-03-31",
            initial_equity=10_000.0,
            symbol=settings.strategy.symbol,
        ),
        base_settings=settings,
        protocol_path=protocol_path,
        seed=7,
        max_candidates=3,
    )
    second_report = run_autoresearch_loop(
        source_db_path=tmp_path / "source.db",
        store_path=tmp_path / "run2.db",
        snapshots_dir=tmp_path / "snapshots_run2",
        output_dir=tmp_path / "output_run2",
        backtest_config=BacktestConfig(
            start_date="2025-01-01",
            end_date="2025-03-31",
            initial_equity=10_000.0,
            symbol=settings.strategy.symbol,
        ),
        base_settings=settings,
        protocol_path=protocol_path,
        seed=7,
        max_candidates=3,
    )

    assert [result.candidate_id for result in first_report.results] == [
        result.candidate_id for result in second_report.results
    ]
