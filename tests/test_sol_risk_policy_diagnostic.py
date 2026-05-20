from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from research_lab.hypotheses.spec import load_hypothesis_spec
from research_lab.portfolio_replay_harness import ArtifactTrade, ReplayTradeResult
from research_lab.sol_risk_policy_diagnostic import (
    RiskPolicyGates,
    capital_metrics,
    choose_policy,
    clone_with_sol_risk,
    evaluate_gates,
    evaluate_scenario,
)


NOW = datetime(2024, 1, 1, tzinfo=timezone.utc)


def test_clone_with_sol_risk_keeps_btc_eth_unchanged() -> None:
    trades = [
        ArtifactTrade("BTCUSDT", "b", NOW, "LONG", 1.0),
        ArtifactTrade("ETHUSDT", "e", NOW, "LONG", 1.0),
        ArtifactTrade("SOLUSDT", "s", NOW, "LONG", 1.0),
    ]

    cloned = clone_with_sol_risk(trades, sol_risk_pct=0.002)

    assert cloned[0].signal.risk_pct == 0.0035
    assert cloned[1].signal.risk_pct == 0.0035
    assert cloned[2].signal.risk_pct == 0.002


def test_capital_metrics_uses_trade_specific_risk() -> None:
    trades = [
        ReplayTradeResult("SOLUSDT", "s1", NOW, NOW, "LONG", 2.0),
        ReplayTradeResult("SOLUSDT", "s2", NOW + timedelta(minutes=15), NOW, "LONG", -1.0),
    ]

    metrics = capital_metrics(trades, {("SOLUSDT", "s1"): 0.002, ("SOLUSDT", "s2"): 0.002})

    assert metrics["pnl_pct_sum"] == 0.002
    assert metrics["max_drawdown_pct"] == 0.002


def test_evaluate_gates_accepts_good_policy() -> None:
    scenario = {
        "r_metrics": {"er": 2.0, "pf": 3.2},
        "capital_metrics": {"max_drawdown_pct": 0.05},
        "sol_approved_trades": 900,
        "incremental_pnl_pct_vs_btc_eth": 0.2,
        "capital_dd_increase_vs_btc_eth": 0.01,
    }

    gates = evaluate_gates(scenario, RiskPolicyGates())

    assert all(item["pass"] for item in gates.values())


def test_choose_policy_prefers_lowest_capital_drawdown_among_passing() -> None:
    scenarios = {
        "0.0020": {
            "sol_risk_pct": 0.002,
            "capital_metrics": {"max_drawdown_pct": 0.05},
            "incremental_pnl_pct_vs_btc_eth": 0.10,
            "gates": {"a": {"pass": True}},
        },
        "0.0025": {
            "sol_risk_pct": 0.0025,
            "capital_metrics": {"max_drawdown_pct": 0.055},
            "incremental_pnl_pct_vs_btc_eth": 0.20,
            "gates": {"a": {"pass": True}},
        },
    }

    verdict, selected = choose_policy(scenarios)

    assert verdict == "SOL_APPROVED_AT_RISK_0.0020"
    assert selected is scenarios["0.0020"]


def test_evaluate_scenario_keeps_entry_population_for_risk_cap_change() -> None:
    trades = [
        ArtifactTrade("SOLUSDT", "s1", NOW, "LONG", 2.0),
        ArtifactTrade("SOLUSDT", "s2", NOW + timedelta(minutes=180), "LONG", -1.0),
    ]

    low = evaluate_scenario(trades, sol_risk_pct=0.0015)
    high = evaluate_scenario(trades, sol_risk_pct=0.0035)

    assert low["approved"] == high["approved"] == 2
    assert low["capital_metrics"]["max_drawdown_pct"] < high["capital_metrics"]["max_drawdown_pct"]


def test_sol_risk_policy_hypothesis_spec_is_valid() -> None:
    spec = load_hypothesis_spec(Path("research_lab/hypotheses/active/sol_risk_policy_diagnostic.json"))

    assert spec.hypothesis_id == "SOL_RISK_POLICY_DIAGNOSTIC_V1"
    assert spec.hypothesis_class == "diagnostic_only"
    assert "SOL shadow design" in spec.out_of_scope
