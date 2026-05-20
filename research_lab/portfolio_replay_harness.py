#!/usr/bin/env python3
"""Artifact-driven BTC+ETH portfolio replay using offline portfolio contracts."""

from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from research_lab.models.portfolio_state import (
    PortfolioGateDecision,
    PortfolioOpenPosition,
    PortfolioRiskConfig,
    PortfolioSignal,
    PortfolioTradeEvent,
    ResearchPortfolioGate,
    recover_portfolio_state,
    sort_portfolio_signals,
)


DEFAULT_BTC_TRADES = Path("research_lab/analysis_output/trial_00095_trades.json")
DEFAULT_ETH_TRADES = Path("research_lab/analysis_output/eth_trial_00095_trades.json")
DEFAULT_REPORT = Path("docs/analysis/PORTFOLIO_REPLAY_V1_2026-05-19.md")
SYMBOLS = ("BTCUSDT", "ETHUSDT")


@dataclass(frozen=True, slots=True)
class ArtifactTrade:
    symbol: str
    trade_id: str
    opened_at: datetime
    direction: str
    pnl_r: float
    regime: str = ""
    risk_pct: float | None = None
    gross_notional_pct: float = 0.30

    @property
    def signal(self) -> PortfolioSignal:
        return PortfolioSignal(
            symbol=self.symbol,
            timestamp=self.opened_at,
            direction=self.direction,
            signal_id=self.trade_id,
            risk_pct=self.risk_pct if self.risk_pct is not None else PortfolioRiskConfig().risk_per_trade_pct_per_symbol,
            gross_notional_pct=self.gross_notional_pct,
        )


@dataclass(frozen=True, slots=True)
class ReplayPosition:
    source: ArtifactTrade
    close_at: datetime
    risk_pct: float
    gross_notional_pct: float

    @property
    def open_position(self) -> PortfolioOpenPosition:
        return PortfolioOpenPosition(
            symbol=self.source.symbol,
            direction=self.source.direction,
            risk_pct=self.risk_pct,
            gross_notional_pct=self.gross_notional_pct,
            opened_at=self.source.opened_at,
        )

    @property
    def close_event(self) -> PortfolioTradeEvent:
        return PortfolioTradeEvent(
            symbol=self.source.symbol,
            pnl_r=self.source.pnl_r,
            closed_at=self.close_at,
        )


@dataclass(frozen=True, slots=True)
class ReplayTradeResult:
    symbol: str
    trade_id: str
    opened_at: datetime
    closed_at: datetime
    direction: str
    pnl_r: float


@dataclass(frozen=True, slots=True)
class VetoRecord:
    symbol: str
    trade_id: str
    timestamp: datetime
    direction: str
    veto_reason: str


@dataclass(frozen=True, slots=True)
class ReplayResult:
    approved_trades: tuple[ReplayTradeResult, ...]
    vetoes: tuple[VetoRecord, ...]
    decisions: tuple[PortfolioGateDecision, ...]
    max_total_risk_pct: float
    max_gross_notional_pct: float
    max_directional_notional_pct: float
    max_open_positions: int


def parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def load_artifact_trades(path: Path, *, symbol: str) -> list[ArtifactTrade]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise RuntimeError(f"Trade artifact must contain a list: {path}")
    trades: list[ArtifactTrade] = []
    for row in payload:
        trades.append(
            ArtifactTrade(
                symbol=str(row.get("symbol", symbol)).upper(),
                trade_id=str(row["trade_id"]),
                opened_at=parse_timestamp(str(row["opened_at"])),
                direction=str(row.get("direction", "LONG")).upper(),
                pnl_r=float(row["pnl_r"]),
                regime=str(row.get("regime", "")),
            )
        )
    return sorted(trades, key=lambda trade: (trade.opened_at, trade.symbol, trade.trade_id))


def run_artifact_portfolio_replay(
    trades: Iterable[ArtifactTrade],
    *,
    config: PortfolioRiskConfig | None = None,
    hold_minutes: int = 180,
    symbols: tuple[str, ...] | None = None,
) -> ReplayResult:
    replay_symbols = tuple(symbol.upper() for symbol in (symbols or SYMBOLS))
    cfg = config or PortfolioRiskConfig(symbol_order=replay_symbols)
    gate = ResearchPortfolioGate(cfg)
    by_timestamp: dict[datetime, list[ArtifactTrade]] = defaultdict(list)
    for trade in trades:
        by_timestamp[trade.opened_at].append(trade)

    open_positions: list[ReplayPosition] = []
    closed_events: list[PortfolioTradeEvent] = []
    approved: list[ReplayTradeResult] = []
    vetoes: list[VetoRecord] = []
    decisions: list[PortfolioGateDecision] = []
    max_total_risk = 0.0
    max_gross = 0.0
    max_directional = 0.0
    max_open_positions = 0

    for timestamp in sorted(by_timestamp):
        newly_closed = [pos for pos in open_positions if pos.close_at <= timestamp]
        if newly_closed:
            closed_events.extend(pos.close_event for pos in newly_closed)
            open_positions = [pos for pos in open_positions if pos.close_at > timestamp]

        recovered = recover_portfolio_state(
            symbols=replay_symbols,
            open_positions=[pos.open_position for pos in open_positions],
            recent_trades=closed_events,
            now=timestamp,
        )
        batch = [trade.signal for trade in by_timestamp[timestamp]]
        id_to_trade = {trade.trade_id: trade for trade in by_timestamp[timestamp]}
        batch_decisions = gate.evaluate_batch(
            batch,
            symbol_states=recovered.symbols,
            portfolio_state=recovered.portfolio,
            now=timestamp,
        )
        decisions.extend(batch_decisions)

        for decision in batch_decisions:
            source = id_to_trade[decision.signal.signal_id]
            if decision.approved:
                close_at = source.opened_at + timedelta(minutes=hold_minutes)
                position = ReplayPosition(
                    source=source,
                    close_at=close_at,
                    risk_pct=decision.signal.risk_pct,
                    gross_notional_pct=decision.signal.gross_notional_pct,
                )
                open_positions.append(position)
                approved.append(
                    ReplayTradeResult(
                        symbol=source.symbol,
                        trade_id=source.trade_id,
                        opened_at=source.opened_at,
                        closed_at=close_at,
                        direction=source.direction,
                        pnl_r=source.pnl_r,
                    )
                )
            else:
                vetoes.append(
                    VetoRecord(
                        symbol=source.symbol,
                        trade_id=source.trade_id,
                        timestamp=source.opened_at,
                        direction=source.direction,
                        veto_reason=decision.veto_reason or "unknown",
                    )
                )

        post_state = recover_portfolio_state(
            symbols=replay_symbols,
            open_positions=[pos.open_position for pos in open_positions],
            recent_trades=closed_events,
            now=timestamp,
        )
        max_total_risk = max(max_total_risk, post_state.portfolio.total_risk_pct_open)
        max_gross = max(max_gross, post_state.portfolio.gross_notional_pct)
        max_directional = max(
            max_directional,
            post_state.portfolio.directional_notional_pct_long,
            post_state.portfolio.directional_notional_pct_short,
        )
        max_open_positions = max(max_open_positions, post_state.portfolio.open_positions_total)

    closed_events.extend(pos.close_event for pos in open_positions)

    return ReplayResult(
        approved_trades=tuple(sorted(approved, key=lambda trade: (trade.opened_at, trade.symbol, trade.trade_id))),
        vetoes=tuple(sorted(vetoes, key=lambda veto: (veto.timestamp, veto.symbol, veto.trade_id))),
        decisions=tuple(decisions),
        max_total_risk_pct=max_total_risk,
        max_gross_notional_pct=max_gross,
        max_directional_notional_pct=max_directional,
        max_open_positions=max_open_positions,
    )


def compute_metrics(trades: Iterable[ReplayTradeResult]) -> dict[str, Any]:
    ordered = sorted(trades, key=lambda trade: (trade.closed_at, trade.symbol, trade.trade_id))
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


def veto_breakdown(vetoes: Iterable[VetoRecord]) -> dict[str, int]:
    return dict(sorted(Counter(veto.veto_reason for veto in vetoes).items()))


def symbol_metrics(trades: Iterable[ReplayTradeResult]) -> dict[str, dict[str, Any]]:
    by_symbol: dict[str, list[ReplayTradeResult]] = defaultdict(list)
    for trade in trades:
        by_symbol[trade.symbol].append(trade)
    return {symbol: compute_metrics(rows) for symbol, rows in sorted(by_symbol.items())}


def compare_to_diagnostic(replay: dict[str, Any]) -> dict[str, float]:
    diagnostic = {"trades": 818, "er": 1.9103331683723719, "pf": 3.4882055907936156, "max_drawdown_r": 19.22348190921889}
    return {
        "trade_delta": replay["trades"] - diagnostic["trades"],
        "er_delta_pct": _pct_delta(replay["er"], diagnostic["er"]),
        "pf_delta_pct": _pct_delta(replay["pf"], diagnostic["pf"]),
        "dd_delta_pct": _pct_delta(replay["max_drawdown_r"], diagnostic["max_drawdown_r"]),
    }


def _pct_delta(value: float, reference: float) -> float:
    if abs(reference) < 1e-12:
        return 0.0
    return (value - reference) / reference


def run_report(
    *,
    btc_trades_path: Path,
    eth_trades_path: Path,
    report_path: Path,
    hold_minutes: int,
) -> dict[str, Any]:
    trades = [
        *load_artifact_trades(btc_trades_path, symbol="BTCUSDT"),
        *load_artifact_trades(eth_trades_path, symbol="ETHUSDT"),
    ]
    result = run_artifact_portfolio_replay(trades, hold_minutes=hold_minutes)
    metrics = compute_metrics(result.approved_trades)
    payload = {
        "milestone": "PORTFOLIO_REPLAY_V1",
        "status": "READY_FOR_AUDIT",
        "method": "artifact_driven_stateful_replay",
        "hold_minutes": hold_minutes,
        "inputs": {
            "btc_trades": str(btc_trades_path),
            "eth_trades": str(eth_trades_path),
        },
        "metrics": metrics,
        "symbol_metrics": symbol_metrics(result.approved_trades),
        "veto_breakdown": veto_breakdown(result.vetoes),
        "veto_count": len(result.vetoes),
        "approved_count": len(result.approved_trades),
        "cap_utilization": {
            "max_total_risk_pct": result.max_total_risk_pct,
            "max_gross_notional_pct": result.max_gross_notional_pct,
            "max_directional_notional_pct": result.max_directional_notional_pct,
            "max_open_positions": result.max_open_positions,
        },
        "diagnostic_comparison": compare_to_diagnostic(metrics),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    generate_report(payload, report_path)
    return payload


def generate_report(payload: dict[str, Any], report_path: Path) -> str:
    metrics = payload["metrics"]
    lines = [
        "# Portfolio Replay V1",
        "",
        "**Milestone:** `PORTFOLIO_REPLAY_V1`",
        f"**Status:** `{payload['status']}`",
        "**Scope:** Research Lab artifact-driven stateful replay; no runtime deployment or production DB writes.",
        "",
        "## Methodology",
        "",
        "- Inputs are frozen BTC and ETH trial-00095 trade artifacts.",
        "- Each artifact trade is treated as a governance-passed candidate signal.",
        "- The replay maintains open positions, symbol state, portfolio state, cooldowns, caps, and vetoes over time.",
        f"- Synthetic hold window: {payload['hold_minutes']} minutes. This is required because BTC artifact lacks close timestamps.",
        "- This is not full feature-engine replay. It validates portfolio state/gate contracts before runtime work.",
        "",
        "## Combined Replay Metrics",
        "",
        "| Trades | ER | PF | Win Rate | PnL R Sum | Max DD R | Max Loss Streak |",
        "|---:|---:|---:|---:|---:|---:|---:|",
        (
            f"| {metrics['trades']} | {metrics['er']:.3f} | {metrics['pf']:.2f} | "
            f"{metrics['win_rate']:.1%} | {metrics['pnl_r_sum']:.2f} | "
            f"{metrics['max_drawdown_r']:.2f} | {metrics['max_consecutive_losses']} |"
        ),
        "",
        "## Per-Symbol Metrics",
        "",
        "| Symbol | Trades | ER | PF | Win Rate | PnL R Sum | Max DD R |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for symbol, symbol_payload in payload["symbol_metrics"].items():
        lines.append(
            f"| {symbol} | {symbol_payload['trades']} | {symbol_payload['er']:.3f} | "
            f"{symbol_payload['pf']:.2f} | {symbol_payload['win_rate']:.1%} | "
            f"{symbol_payload['pnl_r_sum']:.2f} | {symbol_payload['max_drawdown_r']:.2f} |"
        )

    cap = payload["cap_utilization"]
    lines.extend(
        [
            "",
            "## Cap Utilization",
            "",
            f"- Max total risk: {cap['max_total_risk_pct']:.4%}",
            f"- Max gross notional: {cap['max_gross_notional_pct']:.2f}x equity",
            f"- Max directional notional: {cap['max_directional_notional_pct']:.2f}x equity",
            f"- Max open positions: {cap['max_open_positions']}",
            "",
            "## Veto Breakdown",
            "",
            f"- Approved trades: {payload['approved_count']}",
            f"- Vetoed signals: {payload['veto_count']}",
        ]
    )
    if payload["veto_breakdown"]:
        for reason, count in payload["veto_breakdown"].items():
            lines.append(f"- `{reason}`: {count}")
    else:
        lines.append("- No vetoes")

    comp = payload["diagnostic_comparison"]
    lines.extend(
        [
            "",
            "## Diagnostic Comparison",
            "",
            "| Metric | Delta vs Artifact Stitching Diagnostic |",
            "|---|---:|",
            f"| Trades | {comp['trade_delta']:+.0f} |",
            f"| ER | {comp['er_delta_pct']:+.1%} |",
            f"| PF | {comp['pf_delta_pct']:+.1%} |",
            f"| Max DD R | {comp['dd_delta_pct']:+.1%} |",
            "",
            "## Interpretation",
            "",
            _interpretation(payload),
            "",
            "## Limitations",
            "",
            "- Artifact trades are treated as candidate signals; this does not rerun feature/regime/signal/governance engines.",
            "- BTC artifact has no close timestamps, so synthetic close times are deterministic approximations.",
            "- Results validate portfolio state and gate behavior, not runtime execution readiness.",
            "- ETH/BTC PAPER remains out of scope.",
        ]
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(lines) + "\n"
    report_path.write_text(text, encoding="utf-8")
    return text


def _interpretation(payload: dict[str, Any]) -> str:
    metrics = payload["metrics"]
    if metrics["er"] >= 1.5 and metrics["pf"] >= 2.0 and metrics["trades"] >= 300:
        return (
            "Stateful portfolio replay preserves decision-grade combined quality while exercising "
            "the offline SymbolRiskState, PortfolioRiskState, cap, cooldown, and veto contracts."
        )
    return (
        "Stateful portfolio replay materially weakens the diagnostic result. Investigate state tracking, "
        "synthetic hold assumptions, or overly tight caps before any runtime design work continues."
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--btc-trades", type=Path, default=DEFAULT_BTC_TRADES)
    parser.add_argument("--eth-trades", type=Path, default=DEFAULT_ETH_TRADES)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--hold-minutes", type=int, default=180)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = run_report(
        btc_trades_path=args.btc_trades,
        eth_trades_path=args.eth_trades,
        report_path=args.report,
        hold_minutes=args.hold_minutes,
    )
    print(json.dumps({"status": payload["status"], "metrics": payload["metrics"], "vetoes": payload["veto_breakdown"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
