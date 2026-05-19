from __future__ import annotations

from pathlib import Path

from research_lab.hypotheses.spec import load_hypothesis_spec
from research_lab.sol_trial_00095_transfer_feasibility import (
    PortfolioTransferGates,
    artifact_metrics,
    builder_verdict,
    evaluate_portfolio_gates,
    portfolio_delta,
)
from research_lab.portfolio_replay_harness import ArtifactTrade, run_artifact_portfolio_replay
from datetime import datetime, timezone, timedelta


def test_artifact_metrics_computes_r_based_summary() -> None:
    now = datetime(2024, 1, 1, tzinfo=timezone.utc)
    trades = [
        ArtifactTrade("SOLUSDT", "a", now, "LONG", 2.0),
        ArtifactTrade("SOLUSDT", "b", now + timedelta(minutes=15), "LONG", -1.0),
        ArtifactTrade("SOLUSDT", "c", now + timedelta(minutes=30), "SHORT", 1.0),
    ]

    metrics = artifact_metrics(trades)

    assert metrics["trades"] == 3
    assert metrics["er"] == 2.0 / 3.0
    assert metrics["pf"] == 3.0
    assert metrics["max_drawdown_r"] == 1.0


def test_portfolio_gates_pass_decision_grade_three_asset_payload() -> None:
    metrics = {"trades": 800, "er": 1.8, "pf": 3.0, "max_drawdown_r": 14.0}
    per_symbol = {"BTCUSDT": {"trades": 240}, "ETHUSDT": {"trades": 450}, "SOLUSDT": {"trades": 110}}

    gates = evaluate_portfolio_gates(metrics, per_symbol, PortfolioTransferGates())

    assert all(item["pass"] for item in gates.values())
    assert builder_verdict("PASS_TRANSFER_CANDIDATE_FOR_AUDIT", gates) == "PASS_SOL_TRANSFER_PORTFOLIO_CANDIDATE_FOR_AUDIT"


def test_portfolio_gates_block_low_sol_contribution() -> None:
    metrics = {"trades": 800, "er": 1.8, "pf": 3.0, "max_drawdown_r": 14.0}
    per_symbol = {"BTCUSDT": {"trades": 390}, "ETHUSDT": {"trades": 395}, "SOLUSDT": {"trades": 15}}

    gates = evaluate_portfolio_gates(metrics, per_symbol, PortfolioTransferGates())

    assert gates["min_sol_approved_trades"]["pass"] is False
    assert builder_verdict("PASS_TRANSFER_CANDIDATE_FOR_AUDIT", gates) == "SOL_TRANSFER_PASS_PORTFOLIO_FAIL"


def test_portfolio_replay_tracks_sol_symbol_state_when_symbols_supplied() -> None:
    now = datetime(2024, 1, 1, tzinfo=timezone.utc)
    losses = [
        ArtifactTrade("SOLUSDT", f"loss-{idx}", now + timedelta(minutes=idx * 30), "LONG", -0.4)
        for idx in range(4)
    ]
    blocked = ArtifactTrade("SOLUSDT", "blocked", now + timedelta(minutes=110), "LONG", 2.0)

    without_sol_state = run_artifact_portfolio_replay([*losses, blocked], hold_minutes=15)
    replay = run_artifact_portfolio_replay([*losses, blocked], symbols=("BTCUSDT", "ETHUSDT", "SOLUSDT"), hold_minutes=15)

    assert len(without_sol_state.approved_trades) == 5
    assert len(replay.approved_trades) < len(without_sol_state.approved_trades)
    assert all(veto.symbol == "SOLUSDT" for veto in replay.vetoes)
    assert {veto.veto_reason for veto in replay.vetoes} <= {
        "symbol_daily_hard_stop",
        "symbol_weekly_hard_stop",
        "symbol_loss_streak_pause",
        "symbol_cooldown_active",
    }


def test_portfolio_delta_uses_btc_eth_baseline() -> None:
    delta = portfolio_delta({"trades": 796, "er": 1.955, "pf": 3.60, "max_drawdown_r": 13.74})

    assert delta["trade_delta"] == 100
    assert delta["er_delta_pct"] == 0.0
    assert delta["pf_delta_pct"] == 0.0
    assert delta["dd_delta_pct"] == 0.0


def test_sol_transfer_hypothesis_spec_is_valid() -> None:
    spec = load_hypothesis_spec(Path("research_lab/hypotheses/active/sol_trial_00095_transfer_feasibility.json"))

    assert spec.hypothesis_id == "SOL_TRIAL_00095_TRANSFER_FEASIBILITY_V1"
    assert spec.hypothesis_class == "multi_asset_transfer"
    assert "SOL shadow design" in spec.out_of_scope
