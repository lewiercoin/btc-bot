from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from research_lab.hypotheses.spec import load_hypothesis_spec
from research_lab.portfolio_replay_harness import ArtifactTrade, ReplayTradeResult
from research_lab.sol_drawdown_forensic_diagnostic import (
    clone_with_sol_risk,
    correlation_matrix,
    daily_pnl_by_symbol,
    loss_streak_distribution,
    r_metrics,
    weighted_capital_metrics,
    worst_drawdown_points,
)


NOW = datetime(2024, 1, 1, tzinfo=timezone.utc)


def test_r_metrics_and_worst_drawdown_points_are_deterministic() -> None:
    trades = [
        ArtifactTrade("SOLUSDT", "a", NOW, "LONG", 3.0),
        ArtifactTrade("SOLUSDT", "b", NOW + timedelta(minutes=15), "LONG", -1.0),
        ArtifactTrade("SOLUSDT", "c", NOW + timedelta(minutes=30), "LONG", -2.0),
        ArtifactTrade("SOLUSDT", "d", NOW + timedelta(minutes=45), "LONG", 1.0),
    ]

    metrics = r_metrics(trades)
    worst = worst_drawdown_points(trades, limit=1)

    assert metrics["trades"] == 4
    assert metrics["max_drawdown_r"] == 3.0
    assert metrics["max_consecutive_losses"] == 2
    assert worst[0]["drawdown_r"] == 3.0


def test_loss_streak_distribution_counts_completed_and_open_streaks() -> None:
    trades = [
        ArtifactTrade("SOLUSDT", "a", NOW, "LONG", -1.0),
        ArtifactTrade("SOLUSDT", "b", NOW + timedelta(minutes=15), "LONG", -1.0),
        ArtifactTrade("SOLUSDT", "c", NOW + timedelta(minutes=30), "LONG", 1.0),
        ArtifactTrade("SOLUSDT", "d", NOW + timedelta(minutes=45), "LONG", -1.0),
    ]

    streaks = loss_streak_distribution(trades)

    assert streaks["histogram"] == {1: 1, 2: 1}
    assert streaks["max"] == 2


def test_daily_correlation_matrix_zero_fills_inactive_days() -> None:
    trades = [
        ArtifactTrade("BTCUSDT", "b1", NOW, "LONG", 1.0),
        ArtifactTrade("ETHUSDT", "e1", NOW + timedelta(days=1), "LONG", -1.0),
        ArtifactTrade("SOLUSDT", "s1", NOW, "LONG", 1.0),
    ]

    matrix = correlation_matrix(daily_pnl_by_symbol(trades))

    assert matrix["BTCUSDT"]["BTCUSDT"] == 1.0
    assert "SOLUSDT" in matrix["BTCUSDT"]


def test_clone_with_sol_risk_changes_only_sol_signal_risk() -> None:
    trades = [
        ArtifactTrade("BTCUSDT", "b", NOW, "LONG", 1.0),
        ArtifactTrade("SOLUSDT", "s", NOW, "LONG", 1.0),
    ]

    cloned = clone_with_sol_risk(trades, sol_risk_pct=0.0025)

    assert cloned[0].signal.risk_pct == 0.0035
    assert cloned[1].signal.risk_pct == 0.0025


def test_weighted_capital_metrics_uses_per_trade_risk() -> None:
    trades = [
        ReplayTradeResult("SOLUSDT", "s1", NOW, NOW, "LONG", 2.0),
        ReplayTradeResult("SOLUSDT", "s2", NOW + timedelta(minutes=15), NOW, "LONG", -1.0),
    ]
    risk = {("SOLUSDT", "s1"): 0.0025, ("SOLUSDT", "s2"): 0.0025}

    metrics = weighted_capital_metrics(trades, risk)

    assert metrics["pnl_pct_sum"] == 0.0025
    assert metrics["max_drawdown_pct"] == 0.0025


def test_sol_drawdown_forensic_hypothesis_spec_is_valid() -> None:
    spec = load_hypothesis_spec(Path("research_lab/hypotheses/active/sol_drawdown_forensic_diagnostic.json"))

    assert spec.hypothesis_id == "SOL_DRAWDOWN_FORENSIC_DIAGNOSTIC_V1"
    assert spec.hypothesis_class == "diagnostic_only"
    assert "SOL shadow design" in spec.out_of_scope
