#!/usr/bin/env python3
"""SOL drawdown forensic diagnostic for frozen trial-00095 transfer results.

Research Lab only. This script does not tune entries or approve SOL runtime. It
regenerates frozen BTC/ETH/SOL trial-00095 trades and analyzes where SOL
drawdown risk comes from, including year/regime concentration, loss streaks,
daily PnL correlation, portfolio veto effects, and SOL risk-cap sensitivity.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from research_lab.eth_trial_00095_transfer_feasibility import DEFAULT_ETH_DB, DEFAULT_STORE, END, START, TRIAL_00095_ID, resolve_trial_store_path
from research_lab.multi_asset_full_pipeline_replay import DEFAULT_BTC_DB, run_symbol_pipeline
from research_lab.portfolio_replay_harness import (
    ArtifactTrade,
    ReplayTradeResult,
    compute_metrics,
    run_artifact_portfolio_replay,
    symbol_metrics,
    veto_breakdown,
)
from research_lab.sol_trial_00095_transfer_feasibility import DEFAULT_SOL_DB


SYMBOLS_3 = ("BTCUSDT", "ETHUSDT", "SOLUSDT")
DEFAULT_REPORT = Path("docs/analysis/SOL_DRAWDOWN_FORENSIC_DIAGNOSTIC_2026-05-20.md")
SOL_RISK_CAPS = (0.0020, 0.0025, 0.0030, 0.0035)


@dataclass(frozen=True, slots=True)
class DrawdownPoint:
    timestamp: datetime
    equity_r: float
    peak_r: float
    drawdown_r: float


def r_metrics(trades: Iterable[ArtifactTrade | ReplayTradeResult]) -> dict[str, Any]:
    rows = sorted(trades, key=lambda t: (t.opened_at, t.symbol, t.trade_id))
    pnl = [float(t.pnl_r) for t in rows]
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
        "max_drawdown_r": max_drawdown_r(pnl),
        "max_consecutive_losses": max_consecutive_losses(pnl),
    }


def max_drawdown_r(pnl: list[float]) -> float:
    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    for value in pnl:
        equity += value
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
    return max_dd


def max_consecutive_losses(pnl: list[float]) -> int:
    current = 0
    max_seen = 0
    for value in pnl:
        if value < 0:
            current += 1
            max_seen = max(max_seen, current)
        elif value > 0:
            current = 0
    return max_seen


def drawdown_series(trades: Iterable[ArtifactTrade | ReplayTradeResult]) -> list[DrawdownPoint]:
    equity = 0.0
    peak = 0.0
    points: list[DrawdownPoint] = []
    for trade in sorted(trades, key=lambda t: (t.opened_at, t.symbol, t.trade_id)):
        equity += float(trade.pnl_r)
        peak = max(peak, equity)
        points.append(DrawdownPoint(timestamp=trade.opened_at, equity_r=equity, peak_r=peak, drawdown_r=peak - equity))
    return points


def worst_drawdown_points(trades: Iterable[ArtifactTrade | ReplayTradeResult], *, limit: int = 10) -> list[dict[str, Any]]:
    points = sorted(drawdown_series(trades), key=lambda item: item.drawdown_r, reverse=True)[:limit]
    return [
        {
            "timestamp": point.timestamp.isoformat(),
            "equity_r": point.equity_r,
            "peak_r": point.peak_r,
            "drawdown_r": point.drawdown_r,
        }
        for point in points
    ]


def group_metrics(trades: Iterable[ArtifactTrade], key_fn: Any) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[ArtifactTrade]] = defaultdict(list)
    for trade in trades:
        groups[str(key_fn(trade))].append(trade)
    return {key: r_metrics(rows) for key, rows in sorted(groups.items())}


def loss_streak_distribution(trades: Iterable[ArtifactTrade]) -> dict[str, Any]:
    streaks: list[int] = []
    current = 0
    for trade in sorted(trades, key=lambda t: (t.opened_at, t.symbol, t.trade_id)):
        if trade.pnl_r < 0:
            current += 1
        elif trade.pnl_r > 0:
            if current:
                streaks.append(current)
            current = 0
    if current:
        streaks.append(current)
    return {
        "count": len(streaks),
        "max": max(streaks) if streaks else 0,
        "mean": statistics.mean(streaks) if streaks else 0.0,
        "p95": percentile(streaks, 0.95),
        "histogram": dict(sorted(Counter(streaks).items())),
    }


def percentile(values: list[int], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, math.ceil(q * len(ordered)) - 1))
    return float(ordered[idx])


def daily_pnl_by_symbol(trades: Iterable[ArtifactTrade | ReplayTradeResult]) -> dict[str, dict[str, float]]:
    by_symbol: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for trade in trades:
        day = trade.opened_at.date().isoformat()
        by_symbol[trade.symbol][day] += float(trade.pnl_r)
    return {symbol: dict(days) for symbol, days in by_symbol.items()}


def correlation_matrix(daily: dict[str, dict[str, float]]) -> dict[str, dict[str, float]]:
    symbols = sorted(daily)
    all_days = sorted({day for rows in daily.values() for day in rows})
    matrix: dict[str, dict[str, float]] = {}
    for left in symbols:
        matrix[left] = {}
        for right in symbols:
            xs = [daily[left].get(day, 0.0) for day in all_days]
            ys = [daily[right].get(day, 0.0) for day in all_days]
            matrix[left][right] = pearson(xs, ys)
    return matrix


def pearson(xs: list[float], ys: list[float]) -> float:
    if len(xs) != len(ys) or not xs:
        return 0.0
    x_mean = statistics.mean(xs)
    y_mean = statistics.mean(ys)
    numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))
    x_var = sum((x - x_mean) ** 2 for x in xs)
    y_var = sum((y - y_mean) ** 2 for y in ys)
    if x_var <= 1e-12 or y_var <= 1e-12:
        return 0.0
    return numerator / math.sqrt(x_var * y_var)


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


def weighted_capital_metrics(trades: Iterable[ReplayTradeResult], risk_by_key: dict[tuple[str, str], float]) -> dict[str, float]:
    ordered = sorted(trades, key=lambda trade: (trade.opened_at, trade.symbol, trade.trade_id))
    pnl_pct = [trade.pnl_r * risk_by_key.get((trade.symbol, trade.trade_id), 0.0035) for trade in ordered]
    wins = [value for value in pnl_pct if value > 0]
    losses = [value for value in pnl_pct if value < 0]
    gross_loss = abs(sum(losses))
    return {
        "pnl_pct_sum": sum(pnl_pct),
        "avg_trade_pct": statistics.mean(pnl_pct) if pnl_pct else 0.0,
        "pf": sum(wins) / gross_loss if gross_loss > 0 else (float("inf") if wins else 0.0),
        "max_drawdown_pct": max_drawdown_r(pnl_pct),
    }


def risk_cap_sensitivity(all_trades: list[ArtifactTrade]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for risk in SOL_RISK_CAPS:
        scenario_trades = clone_with_sol_risk(all_trades, sol_risk_pct=risk)
        risk_by_key = {(trade.symbol, trade.trade_id): trade.signal.risk_pct for trade in scenario_trades}
        replay = run_artifact_portfolio_replay(scenario_trades, symbols=SYMBOLS_3)
        metrics = compute_metrics(replay.approved_trades)
        out[f"{risk:.4f}"] = {
            "sol_risk_pct": risk,
            "portfolio_r_metrics": metrics,
            "capital_metrics": weighted_capital_metrics(replay.approved_trades, risk_by_key),
            "symbol_metrics": symbol_metrics(replay.approved_trades),
            "veto_breakdown": veto_breakdown(replay.vetoes),
            "veto_count": len(replay.vetoes),
            "approved_count": len(replay.approved_trades),
            "max_total_risk_pct": replay.max_total_risk_pct,
            "max_open_positions": replay.max_open_positions,
        }
    return out


def builder_verdict(payload: dict[str, Any]) -> str:
    base = payload["risk_cap_sensitivity"].get("0.0035", {})
    base_metrics = base.get("portfolio_r_metrics", {})
    if base_metrics.get("er", 0.0) >= 1.5 and base_metrics.get("pf", 0.0) >= 2.0:
        return "FORENSIC_COMPLETE_SOL_RISK_FOLLOWUP_RECOMMENDED"
    return "FORENSIC_COMPLETE_SOL_RESEARCH_ONLY_RECOMMENDED"


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
    portfolio = run_artifact_portfolio_replay(all_trades, symbols=SYMBOLS_3)
    sol_approved = [
        ArtifactTrade(
            symbol=trade.symbol,
            trade_id=trade.trade_id,
            opened_at=trade.opened_at,
            direction=trade.direction,
            pnl_r=trade.pnl_r,
        )
        for trade in portfolio.approved_trades
        if trade.symbol == "SOLUSDT"
    ]
    payload: dict[str, Any] = {
        "milestone": "SOL_DRAWDOWN_FORENSIC_DIAGNOSTIC_V1",
        "status": "PENDING_VERDICT",
        "start": start,
        "end": end,
        "btc_db": str(btc_db),
        "eth_db": str(eth_db),
        "sol_db": str(sol_db),
        "store_path": str(resolved_store),
        "trial_id": TRIAL_00095_ID,
        "pipeline_trade_counts": {"BTCUSDT": len(btc.trades), "ETHUSDT": len(eth.trades), "SOLUSDT": len(sol.trades)},
        "standalone_metrics": {
            "BTCUSDT": r_metrics(btc.trades),
            "ETHUSDT": r_metrics(eth.trades),
            "SOLUSDT": r_metrics(sol.trades),
        },
        "sol_by_year": group_metrics(sol.trades, lambda trade: trade.opened_at.year),
        "sol_by_regime": group_metrics(sol.trades, lambda trade: trade.regime or "unknown"),
        "loss_streaks": {
            "BTCUSDT": loss_streak_distribution(btc.trades),
            "ETHUSDT": loss_streak_distribution(eth.trades),
            "SOLUSDT": loss_streak_distribution(sol.trades),
        },
        "worst_sol_drawdown_points": worst_drawdown_points(sol.trades),
        "portfolio_metrics": compute_metrics(portfolio.approved_trades),
        "portfolio_symbol_metrics": symbol_metrics(portfolio.approved_trades),
        "portfolio_veto_breakdown": veto_breakdown(portfolio.vetoes),
        "portfolio_veto_count": len(portfolio.vetoes),
        "sol_after_portfolio_gate": r_metrics(sol_approved),
        "correlation_matrix_daily_r": correlation_matrix(daily_pnl_by_symbol(portfolio.approved_trades)),
        "risk_cap_sensitivity": risk_cap_sensitivity(all_trades),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    payload["status"] = builder_verdict(payload)
    generate_report(payload, report_path)
    return payload


def generate_report(payload: dict[str, Any], report_path: Path) -> str:
    sol = payload["standalone_metrics"]["SOLUSDT"]
    sol_after = payload["sol_after_portfolio_gate"]
    portfolio = payload["portfolio_metrics"]
    lines = [
        "# SOL Drawdown Forensic Diagnostic V1",
        "",
        "**Milestone:** `SOL_DRAWDOWN_FORENSIC_DIAGNOSTIC_V1`",
        f"**Status:** `{payload['status']}`",
        "**Scope:** Research Lab diagnostic only; frozen trial-00095 trade population; no runtime/core/settings changes.",
        "",
        "## Methodology",
        "",
        "- Regenerate BTC, ETH, and SOL frozen trial-00095 trades from audited datasets.",
        "- Do not change SOL entry logic, sweep thresholds, exits, or trial parameters.",
        "- Analyze SOL drawdown concentration, regime/year splits, loss streaks, daily PnL correlation, portfolio veto impact, and SOL risk-cap sensitivity.",
        "- Risk-cap sensitivity changes only offline portfolio signal risk sizing, not entry selection or thresholds.",
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
        "## SOL Standalone vs Portfolio Gate",
        "",
        "| View | Trades | ER | PF | Win Rate | Max DD R | Max Loss Streak |",
        "|---|---:|---:|---:|---:|---:|---:|",
        _metrics_row("SOL standalone", sol),
        _metrics_row("SOL after portfolio gate", sol_after),
        _metrics_row("BTC+ETH+SOL portfolio", portfolio),
        "",
        "## SOL By Year",
        "",
        "| Year | Trades | ER | PF | Win Rate | Max DD R | Max Loss Streak |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for year, metrics in payload["sol_by_year"].items():
        lines.append(_metrics_row(year, metrics))

    lines.extend(["", "## SOL By Regime", "", "| Regime | Trades | ER | PF | Win Rate | Max DD R | Max Loss Streak |", "|---|---:|---:|---:|---:|---:|---:|"])
    for regime, metrics in payload["sol_by_regime"].items():
        lines.append(_metrics_row(regime, metrics))

    lines.extend(["", "## Loss Streaks", "", "| Symbol | Streak Count | Max | Mean | P95 | Histogram |", "|---|---:|---:|---:|---:|---|"])
    for symbol, streaks in payload["loss_streaks"].items():
        lines.append(
            f"| {symbol} | {streaks['count']} | {streaks['max']} | {streaks['mean']:.2f} | "
            f"{streaks['p95']:.0f} | `{json.dumps(streaks['histogram'], sort_keys=True)}` |"
        )

    lines.extend(["", "## Worst SOL Drawdown Points", "", "| Timestamp | Equity R | Peak R | Drawdown R |", "|---|---:|---:|---:|"])
    for point in payload["worst_sol_drawdown_points"]:
        lines.append(f"| {point['timestamp']} | {point['equity_r']:.2f} | {point['peak_r']:.2f} | {point['drawdown_r']:.2f} |")

    lines.extend(["", "## Portfolio Veto Impact", ""])
    lines.append(f"- Portfolio veto count: {payload['portfolio_veto_count']}")
    for reason, count in payload["portfolio_veto_breakdown"].items():
        lines.append(f"- `{reason}`: {count}")

    lines.extend(["", "## Daily R Correlation Matrix", "", "| Symbol | BTCUSDT | ETHUSDT | SOLUSDT |", "|---|---:|---:|---:|"])
    matrix = payload["correlation_matrix_daily_r"]
    for symbol in ("BTCUSDT", "ETHUSDT", "SOLUSDT"):
        row = matrix.get(symbol, {})
        lines.append(f"| {symbol} | {row.get('BTCUSDT', 0.0):.3f} | {row.get('ETHUSDT', 0.0):.3f} | {row.get('SOLUSDT', 0.0):.3f} |")

    lines.extend(
        [
            "",
            "## SOL Risk-Cap Sensitivity",
            "",
            "| SOL Risk | Approved | ER | PF | Max DD R | Capital DD | SOL Trades | Vetoes |",
            "|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for label, scenario in payload["risk_cap_sensitivity"].items():
        r = scenario["portfolio_r_metrics"]
        cap = scenario["capital_metrics"]
        sol_symbol = scenario["symbol_metrics"].get("SOLUSDT", {})
        lines.append(
            f"| {float(label):.2%} | {scenario['approved_count']} | {r['er']:.3f} | {r['pf']:.2f} | "
            f"{r['max_drawdown_r']:.2f} | {cap['max_drawdown_pct']:.2%} | {sol_symbol.get('trades', 0)} | {scenario['veto_count']} |"
        )

    lines.extend(
        [
            "",
            "## Builder Interpretation",
            "",
            _interpretation(payload),
            "",
            "## Audit Questions",
            "",
            "1. Does this remain diagnostic-only with no runtime/core/settings changes?",
            "2. Are trial-00095 entries and thresholds frozen with no SOL tuning?",
            "3. Are DD/year/regime/loss-streak calculations deterministic and reproducible?",
            "4. Does risk-cap sensitivity avoid changing entry selection or thresholds?",
            "5. Is the recommended next step supported by the forensic evidence?",
        ]
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(lines) + "\n"
    report_path.write_text(text, encoding="utf-8")
    return text


def _metrics_row(label: str, metrics: dict[str, Any]) -> str:
    return (
        f"| {label} | {metrics['trades']} | {metrics['er']:.3f} | {metrics['pf']:.2f} | "
        f"{metrics['win_rate']:.1%} | {metrics['max_drawdown_r']:.2f} | {metrics['max_consecutive_losses']} |"
    )


def _interpretation(payload: dict[str, Any]) -> str:
    return (
        "SOL drawdown forensic analysis is complete. This report does not approve SOL shadow or runtime. "
        "Use the evidence to decide whether a separate SOL-specific risk-policy milestone is justified before any shadow design."
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
                "standalone_sol": payload["standalone_metrics"]["SOLUSDT"],
                "sol_after_portfolio_gate": payload["sol_after_portfolio_gate"],
                "portfolio": payload["portfolio_metrics"],
                "report": str(args.report),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
