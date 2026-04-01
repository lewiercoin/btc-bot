from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from backtest.backtest_runner import BacktestConfig
from research_lab.baseline_gate import BaselineGateError, check_baseline
from research_lab.approval import write_approval_bundle
from research_lab.cli import main as research_lab_main
from research_lab.constants import PARAM_STATUS_FROZEN, PARAM_STATUS_UNSUPPORTED
from research_lab.constraints import validate_param_vector
from research_lab.experiment_store import save_recommendation
from research_lab.param_registry import build_param_registry, get_active_params
from research_lab.pareto import compute_pareto_frontier
from research_lab.settings_adapter import build_candidate_settings, diff_settings
from research_lab.types import ObjectiveMetrics, RecommendationDraft, SignalFunnel, TrialEvaluation
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
