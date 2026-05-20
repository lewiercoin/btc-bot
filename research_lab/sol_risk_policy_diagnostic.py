#!/usr/bin/env python3
"""SOL risk-policy diagnostic for frozen trial-00095 portfolio replay.

Research Lab only. Tests SOL portfolio risk caps after the SOL entry population
is frozen. This does not tune entries, thresholds, exits, or runtime settings.
"""

from __future__ import annotations

import argparse
import json
import statistics
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from research_lab.eth_trial_00095_transfer_feasibility import DEFAULT_ETH_DB, DEFAULT_STORE, END, START, TRIAL_00095_ID, resolve_trial_store_path
from research_lab.multi_asset_full_pipeline_replay import DEFAULT_BTC_DB, run_symbol_pipeline
from research_lab.portfolio_replay_harness import ArtifactTrade, ReplayTradeResult, run_artifact_portfolio_replay, symbol_metrics, veto_breakdown
from research_lab.sol_trial_00095_transfer_feasibility import DEFAULT_SOL_DB


DEFAULT_REPORT = Path("docs/analysis/SOL_RISK_POLICY_DIAGNOSTIC_2026-05-20.md")
SYMBOLS_3 = ("BTCUSDT", "ETHUSDT", "SOLUSDT")
SOL_RISK_CAPS = (0.0015, 0.0020, 0.0025, 0.0030, 0.0035)
BTC_ETH_BASELINE = {
    "approved": 696,
    "er": 1.955,
    "pf": 3.60,
    "capital_dd": 0.04809,  # 13.74R * 0.35%
}


@dataclass(frozen=True, slots=True)
class RiskPolicyGates:
    max_capital_dd: float = 0.06
    min_portfolio_er: float = 1.8
    min_portfolio_pf: float = 3.0
    min_sol_approved_trades: int = 500
    min_incremental_pnl_pct: float = 0.01
    max_capital_dd_increase_vs_btc_eth: float = 0.02


def clone_with_sol_risk(trades: Iterable[ArtifactTrade], *, sol_risk_pct: float) -> list[ArtifactTrade]:
    cloned: list[ArtifactTrade] = []
    for trade in trades:
        cloned.append(
            ArtifactTrade(
                symbol=trade.symbol,
                trade_id=trade.trade_id,
                opened_at=trade.opened_at,
                direction=trade.direction,
                pnl_r=trade.pnl_r,
                regime=trade.regime,
                risk_pct=sol_risk_pct if trade.symbol == "SOLUSDT" else trade.risk_pct,
                gross_notional_pct=trade.gross_notional_pct,
            )
        )
    return cloned


def r_metrics(trades: Iterable[ReplayTradeResult]) -> dict[str, Any]:
    ordered = sorted(trades, key=lambda trade: (trade.opened_at, trade.symbol, trade.trade_id))
    pnl = [trade.pnl_r for trade in ordered]
    wins = [value for value in pnl if value > 0]
    losses = [value for value in pnl if value < 0]
    gross_loss = abs(sum(losses))
    return {
        "trades": len(pnl),
        "er": statistics.mean(pnl) if pnl else 0.0,
        "pf": sum(wins) / gross_loss if gross_loss > 0 else (float("inf") if wins else 0.0),
        "win_rate": len(wins) / len(pnl) if pnl else 0.0,
        "pnl_r_sum": sum(pnl),
        "max_drawdown_r": max_drawdown(pnl),
        "max_consecutive_losses": max_consecutive_losses(pnl),
    }


def capital_metrics(trades: Iterable[ReplayTradeResult], risk_by_key: dict[tuple[str, str], float]) -> dict[str, float]:
    ordered = sorted(trades, key=lambda trade: (trade.opened_at, trade.symbol, trade.trade_id))
    pnl_pct = [trade.pnl_r * risk_by_key[(trade.symbol, trade.trade_id)] for trade in ordered]
    wins = [value for value in pnl_pct if value > 0]
    losses = [value for value in pnl_pct if value < 0]
    gross_loss = abs(sum(losses))
    return {
        "pnl_pct_sum": sum(pnl_pct),
        "avg_trade_pct": statistics.mean(pnl_pct) if pnl_pct else 0.0,
        "pf": sum(wins) / gross_loss if gross_loss > 0 else (float("inf") if wins else 0.0),
        "max_drawdown_pct": max_drawdown(pnl_pct),
        "sharpe_like": sharpe_like(pnl_pct),
    }


def max_drawdown(values: list[float]) -> float:
    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    for value in values:
        equity += value
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
    return max_dd


def max_consecutive_losses(values: list[float]) -> int:
    current = 0
    max_seen = 0
    for value in values:
        if value < 0:
            current += 1
            max_seen = max(max_seen, current)
        elif value > 0:
            current = 0
    return max_seen


def sharpe_like(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    stdev = statistics.pstdev(values)
    if stdev <= 1e-12:
        return 0.0
    return statistics.mean(values) / stdev


def evaluate_scenario(
    trades: list[ArtifactTrade],
    *,
    sol_risk_pct: float,
) -> dict[str, Any]:
    scenario_trades = clone_with_sol_risk(trades, sol_risk_pct=sol_risk_pct)
    risk_by_key = {(trade.symbol, trade.trade_id): trade.signal.risk_pct for trade in scenario_trades}
    replay = run_artifact_portfolio_replay(scenario_trades, symbols=SYMBOLS_3)
    r = r_metrics(replay.approved_trades)
    capital = capital_metrics(replay.approved_trades, risk_by_key)
    per_symbol = symbol_metrics(replay.approved_trades)
    sol = per_symbol.get("SOLUSDT", {"trades": 0, "pnl_r_sum": 0.0, "er": 0.0, "pf": 0.0})
    incremental_pnl_pct = capital["pnl_pct_sum"] - (BTC_ETH_BASELINE["approved"] * BTC_ETH_BASELINE["er"] * 0.0035)
    return {
        "sol_risk_pct": sol_risk_pct,
        "approved": len(replay.approved_trades),
        "vetoes": len(replay.vetoes),
        "r_metrics": r,
        "capital_metrics": capital,
        "symbol_metrics": per_symbol,
        "sol_approved_trades": sol.get("trades", 0),
        "sol_pnl_r_sum": sol.get("pnl_r_sum", 0.0),
        "incremental_pnl_pct_vs_btc_eth": incremental_pnl_pct,
        "capital_dd_increase_vs_btc_eth": capital["max_drawdown_pct"] - BTC_ETH_BASELINE["capital_dd"],
        "veto_breakdown": veto_breakdown(replay.vetoes),
    }


def evaluate_gates(scenario: dict[str, Any], gates: RiskPolicyGates) -> dict[str, dict[str, Any]]:
    capital = scenario["capital_metrics"]
    r = scenario["r_metrics"]
    return {
        "max_capital_dd": {
            "value": capital["max_drawdown_pct"],
            "threshold": gates.max_capital_dd,
            "pass": capital["max_drawdown_pct"] <= gates.max_capital_dd,
        },
        "min_portfolio_er": {"value": r["er"], "threshold": gates.min_portfolio_er, "pass": r["er"] >= gates.min_portfolio_er},
        "min_portfolio_pf": {"value": r["pf"], "threshold": gates.min_portfolio_pf, "pass": r["pf"] >= gates.min_portfolio_pf},
        "min_sol_approved_trades": {
            "value": scenario["sol_approved_trades"],
            "threshold": gates.min_sol_approved_trades,
            "pass": scenario["sol_approved_trades"] >= gates.min_sol_approved_trades,
        },
        "min_incremental_pnl_pct": {
            "value": scenario["incremental_pnl_pct_vs_btc_eth"],
            "threshold": gates.min_incremental_pnl_pct,
            "pass": scenario["incremental_pnl_pct_vs_btc_eth"] >= gates.min_incremental_pnl_pct,
        },
        "max_capital_dd_increase_vs_btc_eth": {
            "value": scenario["capital_dd_increase_vs_btc_eth"],
            "threshold": gates.max_capital_dd_increase_vs_btc_eth,
            "pass": scenario["capital_dd_increase_vs_btc_eth"] <= gates.max_capital_dd_increase_vs_btc_eth,
        },
    }


def choose_policy(scenarios: dict[str, dict[str, Any]]) -> tuple[str, dict[str, Any] | None]:
    passing = [(label, row) for label, row in scenarios.items() if all(gate["pass"] for gate in row["gates"].values())]
    if not passing:
        return "SOL_REJECTED_RISK_POLICY_INSUFFICIENT", None
    passing.sort(
        key=lambda item: (
            item[1]["capital_metrics"]["max_drawdown_pct"],
            -item[1]["incremental_pnl_pct_vs_btc_eth"],
            item[1]["sol_risk_pct"],
        )
    )
    label, row = passing[0]
    return f"SOL_APPROVED_AT_RISK_{label}", row


def run_analysis(
    *,
    btc_db: Path,
    eth_db: Path,
    sol_db: Path,
    store_path: Path,
    report_path: Path,
    start: str,
    end: str,
) -> dict[str, Any]:
    resolved_store = resolve_trial_store_path(store_path, trial_id=TRIAL_00095_ID)
    btc = run_symbol_pipeline(symbol="BTCUSDT", source_db=btc_db, store_path=resolved_store, start=start, end=end)
    eth = run_symbol_pipeline(symbol="ETHUSDT", source_db=eth_db, store_path=resolved_store, start=start, end=end)
    sol = run_symbol_pipeline(symbol="SOLUSDT", source_db=sol_db, store_path=resolved_store, start=start, end=end)
    all_trades = [*btc.trades, *eth.trades, *sol.trades]
    gates = RiskPolicyGates()
    scenarios: dict[str, dict[str, Any]] = {}
    for risk in SOL_RISK_CAPS:
        label = f"{risk:.4f}"
        scenario = evaluate_scenario(all_trades, sol_risk_pct=risk)
        scenario["gates"] = evaluate_gates(scenario, gates)
        scenarios[label] = scenario
    verdict, selected = choose_policy(scenarios)
    payload: dict[str, Any] = {
        "milestone": "SOL_RISK_POLICY_DIAGNOSTIC_V1",
        "status": verdict,
        "start": start,
        "end": end,
        "btc_db": str(btc_db),
        "eth_db": str(eth_db),
        "sol_db": str(sol_db),
        "store_path": str(resolved_store),
        "trial_id": TRIAL_00095_ID,
        "baseline_btc_eth": BTC_ETH_BASELINE,
        "pipeline_trade_counts": {"BTCUSDT": len(btc.trades), "ETHUSDT": len(eth.trades), "SOLUSDT": len(sol.trades)},
        "gate_contract": asdict(gates),
        "scenarios": scenarios,
        "selected_policy": selected,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    generate_report(payload, report_path)
    return payload


def generate_report(payload: dict[str, Any], report_path: Path) -> str:
    lines = [
        "# SOL Risk Policy Diagnostic V1",
        "",
        "**Milestone:** `SOL_RISK_POLICY_DIAGNOSTIC_V1`",
        f"**Status:** `{payload['status']}`",
        "**Scope:** Research Lab risk-policy diagnostic only; frozen trial-00095 entries; no runtime/core/settings changes.",
        "",
        "## Methodology",
        "",
        "- Regenerate frozen BTC, ETH, and SOL trial-00095 trades from audited datasets.",
        "- Keep BTC and ETH risk at 0.35%.",
        "- Test SOL risk caps: 0.15%, 0.20%, 0.25%, 0.30%, 0.35%.",
        "- Change only offline SOL signal risk sizing, not entry selection, thresholds, exits, or portfolio veto logic.",
        "- Compare each variant against the audited BTC+ETH baseline.",
        "",
        "## Inputs",
        "",
        f"- BTC DB: `{payload['btc_db']}`",
        f"- ETH DB: `{payload['eth_db']}`",
        f"- SOL DB: `{payload['sol_db']}`",
        f"- Trial store: `{payload['store_path']}`",
        f"- Window: {payload['start']} to {payload['end']} exclusive",
        f"- Pipeline trade counts: `{json.dumps(payload['pipeline_trade_counts'], sort_keys=True)}`",
        "",
        "## Scenario Frontier",
        "",
        "| SOL Risk | Approved | SOL Trades | ER | PF | Capital DD | Incremental PnL | DD Increase | Gates |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for label, scenario in payload["scenarios"].items():
        r = scenario["r_metrics"]
        capital = scenario["capital_metrics"]
        gates = scenario["gates"]
        passed = sum(1 for item in gates.values() if item["pass"])
        total = len(gates)
        lines.append(
            f"| {float(label):.2%} | {scenario['approved']} | {scenario['sol_approved_trades']} | "
            f"{r['er']:.3f} | {r['pf']:.2f} | {capital['max_drawdown_pct']:.2%} | "
            f"{scenario['incremental_pnl_pct_vs_btc_eth']:.2%} | "
            f"{scenario['capital_dd_increase_vs_btc_eth']:.2%} | {passed}/{total} |"
        )

    lines.extend(["", "## Selected Policy", ""])
    if payload["selected_policy"] is None:
        lines.append("- No SOL risk cap passed all predeclared gates.")
    else:
        selected = payload["selected_policy"]
        lines.extend(
            [
                f"- SOL risk cap: {selected['sol_risk_pct']:.2%}",
                f"- Approved trades: {selected['approved']}",
                f"- SOL approved trades: {selected['sol_approved_trades']}",
                f"- Portfolio ER/PF: {selected['r_metrics']['er']:.3f} / {selected['r_metrics']['pf']:.2f}",
                f"- Capital DD: {selected['capital_metrics']['max_drawdown_pct']:.2%}",
                f"- Incremental PnL vs BTC+ETH: {selected['incremental_pnl_pct_vs_btc_eth']:.2%}",
            ]
        )

    lines.extend(["", "## Gate Details", ""])
    for label, scenario in payload["scenarios"].items():
        lines.extend([f"### SOL Risk {float(label):.2%}", "", "| Gate | Value | Threshold | Result |", "|---|---:|---:|---|"])
        for gate, item in scenario["gates"].items():
            result = "PASS" if item["pass"] else "FAIL"
            lines.append(f"| {gate} | {item['value']:.4g} | {item['threshold']:.4g} | {result} |")
        lines.append("")

    lines.extend(
        [
            "## Builder Interpretation",
            "",
            _interpretation(payload),
            "",
            "## Audit Questions",
            "",
            "1. Does this remain risk-policy diagnostic only with no runtime/core/settings changes?",
            "2. Are trial-00095 entries, exits, and thresholds frozen?",
            "3. Does SOL risk-cap sensitivity change only offline signal risk sizing?",
            "4. Are gates predeclared and applied consistently across all scenarios?",
            "5. Is the selected policy or rejection verdict supported by the frontier?",
        ]
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(lines) + "\n"
    report_path.write_text(text, encoding="utf-8")
    return text


def _interpretation(payload: dict[str, Any]) -> str:
    if payload["selected_policy"] is None:
        return "No tested SOL risk cap made SOL portfolio-safe under predeclared gates. Keep SOL research-only."
    risk = payload["selected_policy"]["sol_risk_pct"]
    return (
        f"The predeclared frontier supports SOL at {risk:.2%} risk in offline research. "
        "This does not approve SOL shadow or runtime; it supports a later audited shadow-design discussion."
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--btc-db", type=Path, default=DEFAULT_BTC_DB)
    parser.add_argument("--eth-db", type=Path, default=DEFAULT_ETH_DB)
    parser.add_argument("--sol-db", type=Path, default=DEFAULT_SOL_DB)
    parser.add_argument("--store", type=Path, default=DEFAULT_STORE)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--start", default=START)
    parser.add_argument("--end", default=END)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = run_analysis(
        btc_db=args.btc_db,
        eth_db=args.eth_db,
        sol_db=args.sol_db,
        store_path=args.store,
        report_path=args.report,
        start=args.start,
        end=args.end,
    )
    print(
        json.dumps(
            {
                "status": payload["status"],
                "selected_policy": payload["selected_policy"],
                "report": str(args.report),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
