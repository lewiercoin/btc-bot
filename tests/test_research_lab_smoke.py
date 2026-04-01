from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from backtest.backtest_runner import BacktestConfig
from research_lab.baseline_gate import BaselineGateError, check_baseline
from research_lab.approval import write_approval_bundle
from research_lab.cli import main as research_lab_main
from research_lab.constants import PARAM_STATUS_FROZEN, PARAM_STATUS_UNSUPPORTED
from research_lab.constraints import validate_param_vector
from research_lab.experiment_store import save_recommendation, save_trial, save_walkforward
from research_lab.param_registry import build_param_registry, get_active_params
from research_lab.pareto import compute_pareto_frontier
from research_lab.protocol import hash_protocol
from research_lab.reporter import build_experiment_report
from research_lab.settings_adapter import build_candidate_settings, diff_settings
from research_lab.types import ObjectiveMetrics, RecommendationDraft, SignalFunnel, TrialEvaluation, WalkForwardReport, WalkForwardWindow
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


def test_param_registry_frozen_params_are_correct() -> None:
    registry = build_param_registry()

    assert registry["weight_force_order_spike"].status == PARAM_STATUS_FROZEN
    assert registry["ema_fast"].status == PARAM_STATUS_FROZEN
    assert registry["ema_slow"].status == PARAM_STATUS_FROZEN
    assert registry["ema_trend_gap_pct"].status == PARAM_STATUS_FROZEN
    assert registry["compression_atr_norm_max"].status == PARAM_STATUS_FROZEN
    assert registry["crowded_funding_extreme_pct"].status == PARAM_STATUS_FROZEN
    assert registry["crowded_oi_zscore_min"].status == PARAM_STATUS_FROZEN
    assert registry["regime_direction_whitelist"].status == PARAM_STATUS_FROZEN
    assert registry["session_start_hour_utc"].status == PARAM_STATUS_FROZEN
    assert registry["session_end_hour_utc"].status == PARAM_STATUS_FROZEN
    assert registry["ema_trend_gap_pct"].default_value == 0.0025
    assert registry["compression_atr_norm_max"].default_value == 0.0055
    assert registry["crowded_funding_extreme_pct"].default_value == 85.0
    assert registry["crowded_oi_zscore_min"].default_value == 1.5
    assert registry["force_order_history_points"].status == PARAM_STATUS_UNSUPPORTED
    assert len(get_active_params()) >= 40


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
        min_trades = int(kwargs["min_trades_full_candidate"])
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
