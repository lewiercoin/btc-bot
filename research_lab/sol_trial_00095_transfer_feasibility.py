#!/usr/bin/env python3
"""SOL transfer feasibility replay for frozen trial-00095 parameters.

Research Lab only. Replays frozen BTC trial-00095 on audited SOL data, then
compares the existing BTC+ETH portfolio baseline against BTC+ETH+SOL using the
offline portfolio gate. This does not approve SOL shadow, PAPER, or runtime.
"""

from __future__ import annotations

import argparse
import json
import statistics
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from research_lab.eth_trial_00095_transfer_feasibility import (
    DEFAULT_ETH_DB,
    DEFAULT_STORE,
    END,
    START,
    TRIAL_00095_ID,
    TransferGates,
    builder_verdict as transfer_builder_verdict,
    evaluate_gates as evaluate_transfer_gates,
    fold_windows,
    resolve_trial_store_path,
)
from research_lab.multi_asset_full_pipeline_replay import (
    DEFAULT_BTC_DB,
    PipelineReplayResult,
    run_symbol_pipeline,
)
from research_lab.portfolio_replay_harness import (
    ArtifactTrade,
    ReplayTradeResult,
    compute_metrics,
    run_artifact_portfolio_replay,
    symbol_metrics,
    veto_breakdown,
)


SYMBOLS_3 = ("BTCUSDT", "ETHUSDT", "SOLUSDT")
DEFAULT_SOL_DB = Path("research_lab/snapshots/replay-run-sol-historical-2022-2026.db")
DEFAULT_REPORT = Path("docs/analysis/SOL_TRIAL_00095_TRANSFER_FEASIBILITY_2026-05-20.md")

BTC_ETH_BASELINE = {
    "trades": 696,
    "er": 1.955,
    "pf": 3.60,
    "max_drawdown_r": 13.74,
}


@dataclass(frozen=True, slots=True)
class PortfolioTransferGates:
    min_portfolio_trades: int = 696
    min_portfolio_er: float = 1.5
    min_portfolio_pf: float = 2.0
    max_portfolio_dd_r: float = 20.0
    min_sol_approved_trades: int = 20


def artifact_metrics(trades: Iterable[ArtifactTrade]) -> dict[str, Any]:
    ordered = sorted(trades, key=lambda trade: (trade.opened_at, trade.symbol, trade.trade_id))
    pnl = [trade.pnl_r for trade in ordered]
    wins = [value for value in pnl if value > 0]
    losses = [value for value in pnl if value < 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    return {
        "trades": len(pnl),
        "er": statistics.mean(pnl) if pnl else 0.0,
        "pf": gross_profit / gross_loss if gross_loss > 0 else (float("inf") if gross_profit > 0 else 0.0),
        "win_rate": len(wins) / len(pnl) if pnl else 0.0,
        "pnl_r_sum": sum(pnl),
        "max_drawdown_r": _max_drawdown_r(pnl),
        "max_consecutive_losses": _max_consecutive_losses(pnl),
    }


def _max_drawdown_r(pnl: list[float]) -> float:
    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    for value in pnl:
        equity += value
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
    return max_dd


def _max_consecutive_losses(pnl: list[float]) -> int:
    current = 0
    max_seen = 0
    for value in pnl:
        if value < 0:
            current += 1
            max_seen = max(max_seen, current)
        elif value > 0:
            current = 0
    return max_seen


def evaluate_portfolio_gates(
    metrics: dict[str, Any],
    per_symbol: dict[str, dict[str, Any]],
    gates: PortfolioTransferGates,
) -> dict[str, dict[str, Any]]:
    sol = per_symbol.get("SOLUSDT", {})
    return {
        "min_portfolio_trades": {
            "value": metrics["trades"],
            "threshold": gates.min_portfolio_trades,
            "pass": metrics["trades"] >= gates.min_portfolio_trades,
        },
        "min_portfolio_er": {
            "value": metrics["er"],
            "threshold": gates.min_portfolio_er,
            "pass": metrics["er"] >= gates.min_portfolio_er,
        },
        "min_portfolio_pf": {
            "value": metrics["pf"],
            "threshold": gates.min_portfolio_pf,
            "pass": metrics["pf"] >= gates.min_portfolio_pf,
        },
        "max_portfolio_dd_r": {
            "value": metrics["max_drawdown_r"],
            "threshold": gates.max_portfolio_dd_r,
            "pass": metrics["max_drawdown_r"] <= gates.max_portfolio_dd_r,
        },
        "min_sol_approved_trades": {
            "value": sol.get("trades", 0),
            "threshold": gates.min_sol_approved_trades,
            "pass": sol.get("trades", 0) >= gates.min_sol_approved_trades,
        },
    }


def builder_verdict(transfer_verdict: str, portfolio_gates: dict[str, dict[str, Any]]) -> str:
    if transfer_verdict != "PASS_TRANSFER_CANDIDATE_FOR_AUDIT":
        return f"SOL_TRANSFER_{transfer_verdict}"
    if all(item["pass"] for item in portfolio_gates.values()):
        return "PASS_SOL_TRANSFER_PORTFOLIO_CANDIDATE_FOR_AUDIT"
    return "SOL_TRANSFER_PASS_PORTFOLIO_FAIL"


def portfolio_delta(metrics: dict[str, Any]) -> dict[str, float]:
    return {
        "trade_delta": metrics["trades"] - BTC_ETH_BASELINE["trades"],
        "er_delta_pct": _pct_delta(metrics["er"], BTC_ETH_BASELINE["er"]),
        "pf_delta_pct": _pct_delta(metrics["pf"], BTC_ETH_BASELINE["pf"]),
        "dd_delta_pct": _pct_delta(metrics["max_drawdown_r"], BTC_ETH_BASELINE["max_drawdown_r"]),
    }


def _pct_delta(value: float, reference: float) -> float:
    if abs(reference) < 1e-12:
        return 0.0
    return (value - reference) / reference


def _fold_payload(label: str, start: str, end: str, replay: PipelineReplayResult) -> dict[str, Any]:
    metrics = artifact_metrics(replay.trades)
    return {
        "label": label,
        "start": start,
        "end": end,
        "trades": metrics["trades"],
        "expectancy_r": metrics["er"],
        "profit_factor": metrics["pf"],
        "max_drawdown_r": metrics["max_drawdown_r"],
        "win_rate": metrics["win_rate"],
    }


def _fold_for_transfer_gate(fold: dict[str, Any]) -> Any:
    return type(
        "FoldLike",
        (),
        {
            "expectancy_r": float(fold["expectancy_r"]),
            "trades": int(fold["trades"]),
        },
    )()


def _replay_trade_result_from_artifact(trade: ArtifactTrade) -> ReplayTradeResult:
    return ReplayTradeResult(
        symbol=trade.symbol,
        trade_id=trade.trade_id,
        opened_at=trade.opened_at,
        closed_at=trade.opened_at,
        direction=trade.direction,
        pnl_r=trade.pnl_r,
    )


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
    sol_cost_15 = run_symbol_pipeline(symbol="SOLUSDT", source_db=sol_db, store_path=resolved_store, start=start, end=end, fee_multiplier=1.5)
    sol_cost_2 = run_symbol_pipeline(symbol="SOLUSDT", source_db=sol_db, store_path=resolved_store, start=start, end=end, fee_multiplier=2.0)

    fold_results: list[dict[str, Any]] = []
    for label, fold_start, fold_end in fold_windows():
        fold_replay = run_symbol_pipeline(
            symbol="SOLUSDT",
            source_db=sol_db,
            store_path=resolved_store,
            start=fold_start,
            end=fold_end,
        )
        fold_results.append(_fold_payload(label, fold_start, fold_end, fold_replay))

    sol_metrics = artifact_metrics(sol.trades)
    sol_cost_2_metrics = artifact_metrics(sol_cost_2.trades)
    transfer_gates = TransferGates()
    transfer_gate_results = evaluate_transfer_gates(
        full=sol.performance,
        cost_2x=sol_cost_2.performance,
        folds=[_fold_for_transfer_gate(fold) for fold in fold_results],
        gates=transfer_gates,
    )
    transfer_verdict = transfer_builder_verdict(transfer_gate_results, full_trades=int(sol.performance.trades_count))

    portfolio = run_artifact_portfolio_replay(
        [*btc.trades, *eth.trades, *sol.trades],
        symbols=SYMBOLS_3,
    )
    portfolio_metrics = compute_metrics(portfolio.approved_trades)
    per_symbol = symbol_metrics(portfolio.approved_trades)
    portfolio_gates = PortfolioTransferGates()
    portfolio_gate_results = evaluate_portfolio_gates(portfolio_metrics, per_symbol, portfolio_gates)
    verdict = builder_verdict(transfer_verdict, portfolio_gate_results)

    payload: dict[str, Any] = {
        "milestone": "SOL_TRIAL_00095_TRANSFER_FEASIBILITY_V1",
        "status": verdict,
        "transfer_verdict": transfer_verdict,
        "start": start,
        "end": end,
        "btc_db": str(btc_db),
        "eth_db": str(eth_db),
        "sol_db": str(sol_db),
        "store_path": str(resolved_store),
        "requested_store_path": str(store_path),
        "trial_id": TRIAL_00095_ID,
        "config_hashes": {"BTCUSDT": btc.config_hash, "ETHUSDT": eth.config_hash, "SOLUSDT": sol.config_hash},
        "pipeline_trade_counts": {"BTCUSDT": len(btc.trades), "ETHUSDT": len(eth.trades), "SOLUSDT": len(sol.trades)},
        "sol_standalone": sol_metrics,
        "sol_cost_sensitivity": {
            "1.0x": sol_metrics,
            "1.5x": artifact_metrics(sol_cost_15.trades),
            "2.0x": sol_cost_2_metrics,
        },
        "sol_folds": fold_results,
        "sol_transfer_gates": transfer_gate_results,
        "portfolio_baseline_btc_eth": BTC_ETH_BASELINE,
        "portfolio_metrics_btc_eth_sol": portfolio_metrics,
        "portfolio_delta_vs_btc_eth": portfolio_delta(portfolio_metrics),
        "portfolio_symbol_metrics": per_symbol,
        "portfolio_veto_breakdown": veto_breakdown(portfolio.vetoes),
        "portfolio_approved_count": len(portfolio.approved_trades),
        "portfolio_veto_count": len(portfolio.vetoes),
        "portfolio_cap_utilization": {
            "max_total_risk_pct": portfolio.max_total_risk_pct,
            "max_gross_notional_pct": portfolio.max_gross_notional_pct,
            "max_directional_notional_pct": portfolio.max_directional_notional_pct,
            "max_open_positions": portfolio.max_open_positions,
        },
        "portfolio_gates": portfolio_gate_results,
        "gate_contracts": {
            "sol_transfer": asdict(transfer_gates),
            "portfolio": asdict(portfolio_gates),
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    generate_report(payload, report_path)
    return payload


def generate_report(payload: dict[str, Any], report_path: Path) -> str:
    sol = payload["sol_standalone"]
    portfolio = payload["portfolio_metrics_btc_eth_sol"]
    delta = payload["portfolio_delta_vs_btc_eth"]
    lines = [
        "# SOL Trial-00095 Transfer Feasibility",
        "",
        "**Milestone:** `SOL_TRIAL_00095_TRANSFER_FEASIBILITY_V1`",
        f"**Status:** `{payload['status']}`",
        "**Scope:** Research Lab strategy transfer only; frozen BTC trial-00095 parameters replayed on audited SOL dataset; no runtime/core changes.",
        "",
        "## Methodology",
        "",
        "- Regenerate BTC, ETH, and SOL trial-00095 trades through the existing single-symbol backtest pipeline.",
        "- Use frozen trial-00095 parameters; only the research symbol changes to SOLUSDT for the transfer test.",
        "- Run each symbol on a copied temporary replay DB; source datasets remain read-only.",
        "- Apply the offline portfolio gate to BTC+ETH+SOL trade candidates using symbol-aware recovery state.",
        "- No parameter search, no threshold tuning, no post-hoc rescue, no SOL shadow/PAPER approval.",
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
        "## SOL Standalone Transfer",
        "",
        "| Trades | ER | PF | Win Rate | PnL R Sum | Max DD R | Max Loss Streak |",
        "|---:|---:|---:|---:|---:|---:|---:|",
        (
            f"| {sol['trades']} | {sol['er']:.3f} | {sol['pf']:.2f} | {sol['win_rate']:.1%} | "
            f"{sol['pnl_r_sum']:.2f} | {sol['max_drawdown_r']:.2f} | {sol['max_consecutive_losses']} |"
        ),
        "",
        "## SOL Transfer Gates",
        "",
        "| Gate | Value | Threshold | Result |",
        "|---|---:|---:|---|",
    ]
    for gate, item in payload["sol_transfer_gates"].items():
        result = "PASS" if item["pass"] else "FAIL"
        lines.append(f"| {gate} | {item['value']:.4g} | {item['threshold']:.4g} | {result} |")

    lines.extend(
        [
            "",
            "## SOL Walk-Forward Stability",
            "",
            "| Fold | Window | Trades | ER | PF | Win Rate | Max DD R |",
            "|---|---|---:|---:|---:|---:|---:|",
        ]
    )
    for fold in payload["sol_folds"]:
        lines.append(
            f"| {fold['label']} | {fold['start']} to {fold['end']} | {fold['trades']} | "
            f"{fold['expectancy_r']:.3f} | {fold['profit_factor']:.2f} | "
            f"{fold['win_rate']:.1%} | {fold['max_drawdown_r']:.2f} |"
        )

    lines.extend(
        [
            "",
            "## SOL Cost Sensitivity",
            "",
            "| Cost Multiplier | Trades | ER | PF | Max DD R |",
            "|---:|---:|---:|---:|---:|",
        ]
    )
    for label, metrics in payload["sol_cost_sensitivity"].items():
        lines.append(
            f"| {label} | {metrics['trades']} | {metrics['er']:.3f} | "
            f"{metrics['pf']:.2f} | {metrics['max_drawdown_r']:.2f} |"
        )

    lines.extend(
        [
            "",
            "## Portfolio Comparison",
            "",
            "| Portfolio | Trades | ER | PF | Max DD R |",
            "|---|---:|---:|---:|---:|",
            (
                f"| BTC+ETH baseline | {payload['portfolio_baseline_btc_eth']['trades']} | "
                f"{payload['portfolio_baseline_btc_eth']['er']:.3f} | "
                f"{payload['portfolio_baseline_btc_eth']['pf']:.2f} | "
                f"{payload['portfolio_baseline_btc_eth']['max_drawdown_r']:.2f} |"
            ),
            (
                f"| BTC+ETH+SOL replay | {portfolio['trades']} | {portfolio['er']:.3f} | "
                f"{portfolio['pf']:.2f} | {portfolio['max_drawdown_r']:.2f} |"
            ),
            "",
            f"- Trade delta vs BTC+ETH: {delta['trade_delta']:+.0f}",
            f"- ER delta vs BTC+ETH: {delta['er_delta_pct']:+.1%}",
            f"- PF delta vs BTC+ETH: {delta['pf_delta_pct']:+.1%}",
            f"- DD delta vs BTC+ETH: {delta['dd_delta_pct']:+.1%}",
            "",
            "## Portfolio Gates",
            "",
            "| Gate | Value | Threshold | Result |",
            "|---|---:|---:|---|",
        ]
    )
    for gate, item in payload["portfolio_gates"].items():
        result = "PASS" if item["pass"] else "FAIL"
        lines.append(f"| {gate} | {item['value']:.4g} | {item['threshold']:.4g} | {result} |")

    lines.extend(
        [
            "",
            "## Per-Symbol Metrics After Portfolio Gate",
            "",
            "| Symbol | Trades | ER | PF | Win Rate | PnL R Sum | Max DD R |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for symbol, metrics in payload["portfolio_symbol_metrics"].items():
        lines.append(
            f"| {symbol} | {metrics['trades']} | {metrics['er']:.3f} | {metrics['pf']:.2f} | "
            f"{metrics['win_rate']:.1%} | {metrics['pnl_r_sum']:.2f} | {metrics['max_drawdown_r']:.2f} |"
        )

    cap = payload["portfolio_cap_utilization"]
    lines.extend(
        [
            "",
            "## Portfolio Vetoes And Caps",
            "",
            f"- Approved trades: {payload['portfolio_approved_count']}",
            f"- Vetoed signals: {payload['portfolio_veto_count']}",
            f"- Max total risk: {cap['max_total_risk_pct']:.4%}",
            f"- Max gross notional: {cap['max_gross_notional_pct']:.2f}x equity",
            f"- Max directional notional: {cap['max_directional_notional_pct']:.2f}x equity",
            f"- Max open positions: {cap['max_open_positions']}",
        ]
    )
    for reason, count in payload["portfolio_veto_breakdown"].items():
        lines.append(f"- `{reason}`: {count}")

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            _interpretation(payload["status"]),
            "",
            "## Limitations",
            "",
            "- This is offline research and does not approve SOL shadow, SOL PAPER, or runtime integration.",
            "- Portfolio gate is applied to regenerated closed trades, not live intrabar exposures.",
            "- SOL threshold changes remain out of scope and would need a separate audited milestone.",
            "- M4 checkpoint remains the blocker for runtime integration decisions.",
            "",
            "## Audit Questions",
            "",
            "1. Did the milestone preserve research-only scope and avoid runtime/core/settings changes?",
            "2. Were trial-00095 parameters frozen except for the research-only symbol transfer to SOLUSDT?",
            "3. Did the replay use audited SOL data read-only through a temporary compatibility DB?",
            "4. Are SOL standalone transfer gates and BTC+ETH+SOL portfolio gates predeclared and not relaxed?",
            "5. Is the builder verdict supported by standalone, walk-forward, cost, and portfolio metrics?",
        ]
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(lines) + "\n"
    report_path.write_text(text, encoding="utf-8")
    return text


def _interpretation(status: str) -> str:
    if status == "PASS_SOL_TRANSFER_PORTFOLIO_CANDIDATE_FOR_AUDIT":
        return (
            "Frozen trial-00095 shows decision-grade SOL transfer evidence and the BTC+ETH+SOL "
            "offline portfolio remains within predeclared gates. This is not runtime approval."
        )
    if status == "SOL_TRANSFER_PASS_PORTFOLIO_FAIL":
        return (
            "Frozen trial-00095 transfers to SOL standalone, but adding SOL to the BTC+ETH portfolio "
            "fails predeclared portfolio gates. Do not proceed to shadow design without a separate decision."
        )
    return (
        "Frozen trial-00095 did not produce a complete SOL transfer pass under the predeclared gates. "
        "Do not tune SOL thresholds inside this milestone."
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
                "sol_standalone": payload["sol_standalone"],
                "portfolio_metrics": payload["portfolio_metrics_btc_eth_sol"],
                "report": str(args.report),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
