#!/usr/bin/env python3
"""Offline BTC+ETH portfolio diagnostic for frozen trial-00095 trades."""

from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from research_lab.eth_trial_00095_transfer_feasibility import (
    DEFAULT_ETH_DB,
    DEFAULT_STORE,
    END,
    START,
    run_replay,
)


DEFAULT_BTC_TRADES = Path("research_lab/analysis_output/trial_00095_trades.json")
DEFAULT_ETH_TRADES = Path("research_lab/analysis_output/eth_trial_00095_trades.json")
DEFAULT_REPORT = Path("docs/analysis/MULTI_ASSET_PORTFOLIO_DIAGNOSTIC_2026-05-19.md")


@dataclass(slots=True, frozen=True)
class PortfolioGates:
    min_combined_trades: int = 300
    min_combined_er: float = 1.5
    min_combined_pf: float = 2.0
    max_drawdown_r: float = 45.0
    max_daily_pnl_corr: float = 0.70
    max_same_bar_overlap_share: float = 0.10
    max_single_month_trade_share: float = 0.20


@dataclass(slots=True)
class TradeRecord:
    symbol: str
    trade_id: str
    opened_at: datetime
    direction: str
    regime: str
    pnl_r: float


def parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def load_btc_trades(path: Path) -> list[TradeRecord]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise RuntimeError(f"BTC trade artifact must be a list: {path}")
    trades: list[TradeRecord] = []
    for row in rows:
        trades.append(
            TradeRecord(
                symbol="BTCUSDT",
                trade_id=str(row["trade_id"]),
                opened_at=parse_timestamp(str(row["opened_at"])),
                direction=str(row.get("direction", "")),
                regime=str(row.get("regime", "")),
                pnl_r=float(row["pnl_r"]),
            )
        )
    return trades


def trade_to_json(trade: TradeRecord) -> dict[str, Any]:
    return {
        "symbol": trade.symbol,
        "trade_id": trade.trade_id,
        "opened_at": trade.opened_at.isoformat(),
        "direction": trade.direction,
        "regime": trade.regime,
        "pnl_r": trade.pnl_r,
    }


def load_eth_trades(path: Path) -> list[TradeRecord]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise RuntimeError(f"ETH trade artifact must be a list: {path}")
    return [
        TradeRecord(
            symbol=str(row.get("symbol", "ETHUSDT")),
            trade_id=str(row["trade_id"]),
            opened_at=parse_timestamp(str(row["opened_at"])),
            direction=str(row.get("direction", "")),
            regime=str(row.get("regime", "")),
            pnl_r=float(row["pnl_r"]),
        )
        for row in rows
    ]


def generate_eth_trades(
    *,
    source_db: Path,
    store_path: Path,
    output_path: Path,
) -> list[TradeRecord]:
    _performance, trades, _config_hash = run_replay(
        source_db=source_db,
        store_path=store_path,
        start=START,
        end=END,
        fee_multiplier=1.0,
    )
    records = [
        TradeRecord(
            symbol="ETHUSDT",
            trade_id=str(trade.trade_id),
            opened_at=trade.opened_at,
            direction=str(trade.direction),
            regime=str(trade.regime),
            pnl_r=float(trade.pnl_r),
        )
        for trade in trades
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps([trade_to_json(t) for t in records], indent=2, sort_keys=True), encoding="utf-8")
    return records


def compute_metrics(trades: list[TradeRecord]) -> dict[str, Any]:
    ordered = sorted(trades, key=lambda trade: trade.opened_at)
    pnl = [trade.pnl_r for trade in ordered]
    wins = [value for value in pnl if value > 0]
    losses = [value for value in pnl if value < 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    return {
        "trades": len(ordered),
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


def daily_pnl(trades: list[TradeRecord]) -> dict[str, float]:
    totals: dict[str, float] = defaultdict(float)
    for trade in trades:
        totals[trade.opened_at.date().isoformat()] += trade.pnl_r
    return dict(totals)


def pearson_corr(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or len(a) < 2:
        return 0.0
    mean_a = statistics.mean(a)
    mean_b = statistics.mean(b)
    cov = sum((x - mean_a) * (y - mean_b) for x, y in zip(a, b))
    var_a = sum((x - mean_a) ** 2 for x in a)
    var_b = sum((y - mean_b) ** 2 for y in b)
    denom = math.sqrt(var_a * var_b)
    return cov / denom if denom > 1e-12 else 0.0


def daily_correlation(left: list[TradeRecord], right: list[TradeRecord]) -> dict[str, Any]:
    left_daily = daily_pnl(left)
    right_daily = daily_pnl(right)
    keys = sorted(set(left_daily) | set(right_daily))
    left_values = [left_daily.get(key, 0.0) for key in keys]
    right_values = [right_daily.get(key, 0.0) for key in keys]
    both_active = sum(1 for key in keys if left_daily.get(key, 0.0) != 0.0 and right_daily.get(key, 0.0) != 0.0)
    return {
        "days": len(keys),
        "both_active_days": both_active,
        "correlation": pearson_corr(left_values, right_values),
    }


def floor_15m(ts: datetime) -> datetime:
    minute = (ts.minute // 15) * 15
    return ts.replace(minute=minute, second=0, microsecond=0)


def same_bar_overlap(left: list[TradeRecord], right: list[TradeRecord]) -> dict[str, Any]:
    left_bars = {floor_15m(trade.opened_at) for trade in left}
    right_bars = {floor_15m(trade.opened_at) for trade in right}
    overlap = left_bars & right_bars
    total_unique = len(left_bars | right_bars)
    return {
        "same_15m_bars": len(overlap),
        "unique_signal_bars": total_unique,
        "overlap_share": len(overlap) / total_unique if total_unique else 0.0,
    }


def concentration(trades: list[TradeRecord]) -> dict[str, Any]:
    by_month: dict[str, int] = defaultdict(int)
    by_quarter: dict[str, int] = defaultdict(int)
    for trade in trades:
        month = trade.opened_at.strftime("%Y-%m")
        quarter = f"{trade.opened_at.year}-Q{((trade.opened_at.month - 1) // 3) + 1}"
        by_month[month] += 1
        by_quarter[quarter] += 1
    total = max(len(trades), 1)
    top_month = max(by_month.items(), key=lambda item: item[1]) if by_month else ("", 0)
    top_quarter = max(by_quarter.items(), key=lambda item: item[1]) if by_quarter else ("", 0)
    return {
        "top_month": top_month[0],
        "top_month_trades": top_month[1],
        "top_month_share": top_month[1] / total,
        "top_quarter": top_quarter[0],
        "top_quarter_trades": top_quarter[1],
        "top_quarter_share": top_quarter[1] / total,
    }


def apply_same_bar_policy(
    btc: list[TradeRecord],
    eth: list[TradeRecord],
    *,
    policy: str,
) -> list[TradeRecord]:
    all_trades = sorted([*btc, *eth], key=lambda trade: (floor_15m(trade.opened_at), trade.symbol))
    if policy == "allow_both":
        return all_trades
    selected: list[TradeRecord] = []
    seen_bars: set[datetime] = set()
    for trade in all_trades:
        bar = floor_15m(trade.opened_at)
        if bar in seen_bars:
            continue
        if policy == "btc_priority" and trade.symbol != "BTCUSDT":
            same_bar_btc = [t for t in all_trades if floor_15m(t.opened_at) == bar and t.symbol == "BTCUSDT"]
            if same_bar_btc:
                continue
        selected.append(trade)
        seen_bars.add(bar)
    return selected


def evaluate_gates(payload: dict[str, Any], gates: PortfolioGates) -> dict[str, dict[str, Any]]:
    portfolio = payload["policies"]["allow_both"]
    correlation = payload["daily_correlation"]["correlation"]
    overlap = payload["same_bar_overlap"]["overlap_share"]
    concentration_payload = payload["concentration"]
    return {
        "min_combined_trades": {"value": portfolio["trades"], "threshold": gates.min_combined_trades, "pass": portfolio["trades"] >= gates.min_combined_trades},
        "min_combined_er": {"value": portfolio["er"], "threshold": gates.min_combined_er, "pass": portfolio["er"] >= gates.min_combined_er},
        "min_combined_pf": {"value": portfolio["pf"], "threshold": gates.min_combined_pf, "pass": portfolio["pf"] >= gates.min_combined_pf},
        "max_drawdown_r": {"value": portfolio["max_drawdown_r"], "threshold": gates.max_drawdown_r, "pass": portfolio["max_drawdown_r"] <= gates.max_drawdown_r},
        "max_daily_pnl_corr": {"value": correlation, "threshold": gates.max_daily_pnl_corr, "pass": correlation <= gates.max_daily_pnl_corr},
        "max_same_bar_overlap_share": {"value": overlap, "threshold": gates.max_same_bar_overlap_share, "pass": overlap <= gates.max_same_bar_overlap_share},
        "max_single_month_trade_share": {"value": concentration_payload["top_month_share"], "threshold": gates.max_single_month_trade_share, "pass": concentration_payload["top_month_share"] <= gates.max_single_month_trade_share},
    }


def builder_verdict(gates: dict[str, dict[str, Any]]) -> str:
    if all(item["pass"] for item in gates.values()):
        return "PASS_PORTFOLIO_DIAGNOSTIC_FOR_ARCHITECTURE_DESIGN"
    if gates["max_daily_pnl_corr"]["pass"] and gates["min_combined_er"]["pass"] and gates["min_combined_pf"]["pass"]:
        return "NEEDS_PORTFOLIO_RISK_CONSTRAINTS"
    return "FAIL_PORTFOLIO_DIAGNOSTIC"


def run_diagnostic(
    *,
    btc_trades_path: Path,
    eth_trades_path: Path,
    eth_source_db: Path,
    store_path: Path,
    report_path: Path,
    force_eth_replay: bool,
) -> dict[str, Any]:
    btc = load_btc_trades(btc_trades_path)
    if eth_trades_path.exists() and not force_eth_replay:
        eth = load_eth_trades(eth_trades_path)
    else:
        eth = generate_eth_trades(source_db=eth_source_db, store_path=store_path, output_path=eth_trades_path)

    payload: dict[str, Any] = {
        "milestone": "MULTI_ASSET_PORTFOLIO_DIAGNOSTIC_V1",
        "btc_artifact": str(btc_trades_path),
        "eth_artifact": str(eth_trades_path),
        "btc": compute_metrics(btc),
        "eth": compute_metrics(eth),
        "daily_correlation": daily_correlation(btc, eth),
        "same_bar_overlap": same_bar_overlap(btc, eth),
        "concentration": concentration([*btc, *eth]),
        "policies": {
            "allow_both": compute_metrics(apply_same_bar_policy(btc, eth, policy="allow_both")),
            "first_signal_only": compute_metrics(apply_same_bar_policy(btc, eth, policy="first_signal_only")),
            "btc_priority": compute_metrics(apply_same_bar_policy(btc, eth, policy="btc_priority")),
        },
    }
    gates = PortfolioGates()
    payload["gates"] = evaluate_gates(payload, gates)
    payload["gate_contract"] = asdict(gates)
    payload["builder_verdict"] = builder_verdict(payload["gates"])
    payload["generated_at"] = datetime.now(timezone.utc).isoformat()
    generate_report(payload, report_path)
    return payload


def generate_report(payload: dict[str, Any], report_path: Path) -> str:
    lines = [
        "# Multi-Asset Portfolio Diagnostic",
        "",
        "**Milestone:** `MULTI_ASSET_PORTFOLIO_DIAGNOSTIC_V1`",
        f"**Status:** `{payload['builder_verdict']}`",
        "**Scope:** Research Lab offline portfolio diagnostic only; no runtime architecture or deployment approval.",
        "",
        "## Internal Consultation Summary",
        "",
        "- Do not design runtime first. Measure portfolio interaction first.",
        "- Use frozen BTC trial-00095 and audited ETH transfer artifacts only.",
        "- Treat same-bar conflicts and daily PnL correlation as architecture inputs, not deployment approval.",
        "- If portfolio gates pass, next step is architecture design for aggregate risk, not immediate PAPER deployment.",
        "",
        "## Inputs",
        "",
        f"- BTC trades: `{payload['btc_artifact']}`",
        f"- ETH trades: `{payload['eth_artifact']}`",
        "",
        "## Standalone Metrics",
        "",
        "| Asset | Trades | ER | PF | Win Rate | PnL R Sum | Max DD R | Max Loss Streak |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in ("btc", "eth"):
        m = payload[label]
        lines.append(
            f"| {label.upper()} | {m['trades']} | {m['er']:.3f} | {m['pf']:.2f} | "
            f"{m['win_rate']:.1%} | {m['pnl_r_sum']:.2f} | {m['max_drawdown_r']:.2f} | {m['max_consecutive_losses']} |"
        )

    lines.extend(
        [
            "",
            "## Portfolio Policies",
            "",
            "| Policy | Trades | ER | PF | Win Rate | PnL R Sum | Max DD R | Max Loss Streak |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for policy, metrics in payload["policies"].items():
        lines.append(
            f"| {policy} | {metrics['trades']} | {metrics['er']:.3f} | {metrics['pf']:.2f} | "
            f"{metrics['win_rate']:.1%} | {metrics['pnl_r_sum']:.2f} | {metrics['max_drawdown_r']:.2f} | {metrics['max_consecutive_losses']} |"
        )

    corr = payload["daily_correlation"]
    overlap = payload["same_bar_overlap"]
    conc = payload["concentration"]
    lines.extend(
        [
            "",
            "## Interaction Diagnostics",
            "",
            f"- Daily PnL correlation: {corr['correlation']:.3f} across {corr['days']} active/zero-filled days",
            f"- Both-active days: {corr['both_active_days']}",
            f"- Same 15m signal bars: {overlap['same_15m_bars']} / {overlap['unique_signal_bars']} ({overlap['overlap_share']:.1%})",
            f"- Top month concentration: {conc['top_month']} with {conc['top_month_trades']} trades ({conc['top_month_share']:.1%})",
            f"- Top quarter concentration: {conc['top_quarter']} with {conc['top_quarter_trades']} trades ({conc['top_quarter_share']:.1%})",
            "",
            "## Gates",
            "",
            "| Gate | Value | Threshold | Result |",
            "|---|---:|---:|---|",
        ]
    )
    for gate, item in payload["gates"].items():
        result = "PASS" if item["pass"] else "FAIL"
        lines.append(f"| {gate} | {item['value']:.4g} | {item['threshold']:.4g} | {result} |")

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            _interpretation(payload["builder_verdict"]),
            "",
            "## Methodology Limits",
            "",
            "- BTC artifact is the existing full replay trade list, not the 47-trade WF-only summary.",
            "- Correlation uses trade-open-day PnL buckets because BTC artifact does not include close timestamps.",
            "- Same-bar overlap is a signal-timing proxy, not full exposure overlap.",
            "- This report cannot approve runtime ETH trading or multi-asset execution.",
            "",
            "## Audit Questions",
            "",
            "1. Does this remain research-only with no runtime/core/settings changes?",
            "2. Are BTC and ETH inputs frozen/audited enough for a portfolio diagnostic?",
            "3. Are correlation, overlap, concentration, and policy metrics computed deterministically?",
            "4. Is the builder verdict supported by the preregistered gates?",
            "5. Are limitations clear enough to prevent accidental deployment interpretation?",
        ]
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(lines) + "\n"
    report_path.write_text(text, encoding="utf-8")
    return text


def _interpretation(verdict: str) -> str:
    if verdict == "PASS_PORTFOLIO_DIAGNOSTIC_FOR_ARCHITECTURE_DESIGN":
        return (
            "BTC+ETH trial-00095 artifacts support proceeding to multi-asset architecture design. "
            "The next milestone should define aggregate risk, sizing, symbol-level cooldowns, and conflict handling before any runtime implementation."
        )
    if verdict == "NEEDS_PORTFOLIO_RISK_CONSTRAINTS":
        return (
            "Combined edge quality is positive, but interaction diagnostics require explicit portfolio risk constraints before architecture design can proceed."
        )
    return "The combined BTC+ETH artifact does not support portfolio architecture work under these gates."


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--btc-trades", type=Path, default=DEFAULT_BTC_TRADES)
    parser.add_argument("--eth-trades", type=Path, default=DEFAULT_ETH_TRADES)
    parser.add_argument("--eth-source-db", type=Path, default=DEFAULT_ETH_DB)
    parser.add_argument("--store", type=Path, default=DEFAULT_STORE)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--force-eth-replay", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = run_diagnostic(
        btc_trades_path=args.btc_trades,
        eth_trades_path=args.eth_trades,
        eth_source_db=args.eth_source_db,
        store_path=args.store,
        report_path=args.report,
        force_eth_replay=args.force_eth_replay,
    )
    print(json.dumps({"verdict": payload["builder_verdict"], "policies": payload["policies"], "report": str(args.report)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
