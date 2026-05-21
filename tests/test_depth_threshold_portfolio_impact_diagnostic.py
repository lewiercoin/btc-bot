from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from research_lab.depth_threshold_portfolio_impact_diagnostic import (
    ASSET_SPECIFIC_DEPTH,
    FROZEN_DEPTH,
    DiagnosticGates,
    MILESTONE,
    correlation_matrix,
    evaluate_scenario_gates,
    same_bar_overlap_by_pair,
    scenario_grid,
    scenario_verdict,
)
from research_lab.hypotheses.spec import load_hypothesis_spec
from research_lab.portfolio_replay_harness import ArtifactTrade


def _trade(symbol: str, day: int, pnl_r: float, minute: int = 0) -> ArtifactTrade:
    return ArtifactTrade(
        symbol=symbol,
        trade_id=f"{symbol}-{day}-{minute}",
        opened_at=datetime(2025, 1, day, 12, minute, tzinfo=timezone.utc),
        direction="LONG",
        pnl_r=pnl_r,
        risk_pct=0.0015 if symbol == "SOLUSDT" else 0.0035,
    )


def _scenario(*, portfolio_trades: int, sol_trades: int, er: float = 2.0, dd: float = 5.0) -> dict:
    return {
        "standalone": {
            "BTCUSDT": {"trades": 50},
            "ETHUSDT": {"trades": 60},
            "SOLUSDT": {"trades": sol_trades},
        },
        "portfolio_metrics": {
            "trades": portfolio_trades,
            "er": er,
            "pf": 3.0,
            "max_drawdown_r": dd,
        },
        "max_abs_daily_corr": 0.2,
        "max_same_bar_overlap_share": 0.04,
    }


def test_scenario_grid_keeps_current_shadow_profile_explicit() -> None:
    scenarios = {item.scenario_id: item for item in scenario_grid()}

    assert scenarios["both_frozen_transfer"].eth_depth == FROZEN_DEPTH
    assert scenarios["both_frozen_transfer"].sol_depth == FROZEN_DEPTH
    assert scenarios["current_shadow_profile"].eth_depth == ASSET_SPECIFIC_DEPTH
    assert scenarios["current_shadow_profile"].sol_depth == FROZEN_DEPTH
    assert scenarios["eth_sol_asset_specific"].eth_depth == ASSET_SPECIFIC_DEPTH
    assert scenarios["eth_sol_asset_specific"].sol_depth == ASSET_SPECIFIC_DEPTH


def test_correlation_matrix_zero_fills_inactive_days() -> None:
    matrix = correlation_matrix(
        [
            _trade("BTCUSDT", 1, 1.0),
            _trade("BTCUSDT", 2, -1.0),
            _trade("ETHUSDT", 1, 1.0),
            _trade("SOLUSDT", 3, -1.0),
        ]
    )

    assert set(matrix) == {"BTCUSDT", "ETHUSDT", "SOLUSDT"}
    assert matrix["BTCUSDT"]["BTCUSDT"] == 1.0
    assert matrix["BTCUSDT"]["ETHUSDT"] != 0.0


def test_same_bar_overlap_by_pair_counts_15m_collisions() -> None:
    overlap = same_bar_overlap_by_pair(
        [
            _trade("BTCUSDT", 1, 1.0, minute=0),
            _trade("ETHUSDT", 1, 1.0, minute=5),
            _trade("SOLUSDT", 2, 1.0, minute=30),
        ]
    )

    assert overlap["BTCUSDT_ETHUSDT"]["same_15m_bars"] == 1
    assert overlap["BTCUSDT_SOLUSDT"]["same_15m_bars"] == 0


def test_verdict_supports_asset_specific_when_frequency_and_portfolio_pass() -> None:
    payload = {
        "scenarios": {
            "both_frozen_transfer": _scenario(portfolio_trades=300, sol_trades=100, er=1.8),
            "current_shadow_profile": _scenario(portfolio_trades=280, sol_trades=100, er=1.9),
            "eth_sol_asset_specific": _scenario(portfolio_trades=270, sol_trades=70, er=2.0),
        }
    }

    gates = evaluate_scenario_gates(payload, DiagnosticGates())

    assert all(item["pass"] for item in gates.values())
    assert scenario_verdict(payload, DiagnosticGates()) == "ASSET_SPECIFIC_DEPTH_SUPPORTED_FOR_SHADOW_DECISION"


def test_verdict_keeps_current_profile_when_sol_retention_fails() -> None:
    payload = {
        "scenarios": {
            "both_frozen_transfer": _scenario(portfolio_trades=300, sol_trades=100, er=1.8),
            "current_shadow_profile": _scenario(portfolio_trades=280, sol_trades=100, er=1.9),
            "eth_sol_asset_specific": _scenario(portfolio_trades=270, sol_trades=40, er=2.0),
        }
    }

    gates = evaluate_scenario_gates(payload, DiagnosticGates())

    assert gates["min_sol_trade_retention_pct"]["pass"] is False
    assert scenario_verdict(payload, DiagnosticGates()) == "KEEP_CURRENT_SHADOW_PROFILE_PENDING_FORWARD_EVIDENCE"


def test_depth_threshold_hypothesis_spec_is_valid() -> None:
    spec = load_hypothesis_spec(Path("research_lab/hypotheses/active/depth_threshold_portfolio_impact_diagnostic.json"))

    assert spec.hypothesis_id == MILESTONE
    assert spec.hypothesis_class == "diagnostic_only"
    assert "PAPER or LIVE orders." in spec.out_of_scope
