#!/usr/bin/env python3
"""Offline BTC+ETH full-pipeline regeneration plus portfolio gate replay.

This milestone stays in Research Lab. It regenerates BTC and ETH trial-00095
trade lists through the existing single-symbol backtest pipeline, then applies
the offline portfolio gate from Phase 2. It does not modify runtime code or
approve multi-asset PAPER.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import shutil
import sqlite3
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backtest.backtest_runner import BacktestConfig, BacktestRunner
from research_lab.eth_trial_00095_transfer_feasibility import (
    DEFAULT_ETH_DB,
    DEFAULT_STORE,
    END,
    START,
    _ensure_runtime_tables,
    load_trial_params,
    prepare_replay_db,
    resolve_trial_store_path,
)
from research_lab.portfolio_replay_harness import (
    ArtifactTrade,
    compute_metrics,
    run_artifact_portfolio_replay,
    symbol_metrics,
    veto_breakdown,
)
from research_lab.settings_adapter import build_candidate_settings
from settings import load_settings


DEFAULT_BTC_DB = Path("research_lab/snapshots/replay-run13-regime-aware-trial-00063.db")
DEFAULT_REPORT = Path("docs/analysis/MULTI_ASSET_FULL_PIPELINE_REPLAY_2026-05-19.md")
TRIAL_00095_ID = "optuna-default-v3-trial-00095"


@dataclass(frozen=True, slots=True)
class PipelineReplayResult:
    symbol: str
    trades: tuple[ArtifactTrade, ...]
    config_hash: str


@dataclass(frozen=True, slots=True)
class FullPipelineGates:
    min_portfolio_trades: int = 300
    min_portfolio_er: float = 1.5
    min_portfolio_pf: float = 2.0
    max_portfolio_dd_r: float = 20.0
    min_btc_trades: int = 150
    min_eth_trades: int = 300


def build_symbol_settings(*, symbol: str, store_path: Path) -> Any:
    trial_params = load_trial_params(store_path, trial_id=TRIAL_00095_ID)
    candidate = build_candidate_settings(load_settings(profile="research"), trial_params)
    strategy = dataclasses.replace(candidate.strategy, symbol=symbol.upper())
    return dataclasses.replace(candidate, strategy=strategy)


def run_symbol_pipeline(
    *,
    symbol: str,
    source_db: Path,
    store_path: Path,
    start: str,
    end: str,
    fee_multiplier: float = 1.0,
) -> PipelineReplayResult:
    symbol = symbol.upper()
    settings = build_symbol_settings(symbol=symbol, store_path=store_path)
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        if symbol == "ETHUSDT":
            prepare_replay_db(source_db, tmp_path)
        else:
            shutil.copy2(str(source_db), str(tmp_path))
            ensure_replay_compatibility_tables(tmp_path)

        conn = sqlite3.connect(str(tmp_path))
        conn.row_factory = sqlite3.Row
        try:
            runner = BacktestRunner(conn, settings=settings)
            result = runner.run(
                BacktestConfig(
                    start_date=start,
                    end_date=end,
                    symbol=symbol,
                    initial_equity=10_000.0,
                    fee_rate_maker=0.0004 * fee_multiplier,
                    fee_rate_taker=0.0004 * fee_multiplier,
                )
            )
        finally:
            conn.close()
    finally:
        tmp_path.unlink(missing_ok=True)
        tmp_path.with_name(tmp_path.name + "-wal").unlink(missing_ok=True)
        tmp_path.with_name(tmp_path.name + "-shm").unlink(missing_ok=True)

    return PipelineReplayResult(
        symbol=symbol,
        trades=tuple(trade_log_to_artifact(trade, symbol=symbol) for trade in result.trades),
        config_hash=settings.config_hash,
    )


def ensure_replay_compatibility_tables(db_path: Path) -> None:
    """Normalize writable temp replay tables without mutating the source DB."""

    conn = sqlite3.connect(str(db_path))
    try:
        _ensure_runtime_tables(conn)
        conn.commit()
    finally:
        conn.close()


def trade_log_to_artifact(trade: Any, *, symbol: str) -> ArtifactTrade:
    if trade.closed_at is None:
        raise RuntimeError(f"Trade {trade.trade_id} has no closed_at timestamp")
    return ArtifactTrade(
        symbol=symbol.upper(),
        trade_id=str(trade.trade_id),
        opened_at=_to_utc(trade.opened_at),
        direction=str(trade.direction).upper(),
        pnl_r=float(trade.pnl_r),
        regime=str(trade.regime),
    )


def evaluate_gates(metrics: dict[str, Any], per_symbol: dict[str, dict[str, Any]], gates: FullPipelineGates) -> dict[str, dict[str, Any]]:
    btc = per_symbol.get("BTCUSDT", {})
    eth = per_symbol.get("ETHUSDT", {})
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
        "min_btc_trades": {
            "value": btc.get("trades", 0),
            "threshold": gates.min_btc_trades,
            "pass": btc.get("trades", 0) >= gates.min_btc_trades,
        },
        "min_eth_trades": {
            "value": eth.get("trades", 0),
            "threshold": gates.min_eth_trades,
            "pass": eth.get("trades", 0) >= gates.min_eth_trades,
        },
    }


def builder_verdict(gates: dict[str, dict[str, Any]]) -> str:
    if all(item["pass"] for item in gates.values()):
        return "PASS_FULL_PIPELINE_REPLAY_FOR_RUNTIME_SCOPING"
    return "NEEDS_FIX_OR_RUNTIME_SCOPING_BLOCKED"


def run_analysis(
    *,
    btc_db: Path,
    eth_db: Path,
    store_path: Path,
    report_path: Path,
    start: str,
    end: str,
) -> dict[str, Any]:
    resolved_store = resolve_trial_store_path(store_path, trial_id=TRIAL_00095_ID)
    btc = run_symbol_pipeline(symbol="BTCUSDT", source_db=btc_db, store_path=resolved_store, start=start, end=end)
    eth = run_symbol_pipeline(symbol="ETHUSDT", source_db=eth_db, store_path=resolved_store, start=start, end=end)
    portfolio = run_artifact_portfolio_replay([*btc.trades, *eth.trades])
    metrics = compute_metrics(portfolio.approved_trades)
    per_symbol = symbol_metrics(portfolio.approved_trades)
    gates = FullPipelineGates()
    gate_results = evaluate_gates(metrics, per_symbol, gates)
    payload: dict[str, Any] = {
        "milestone": "MULTI_ASSET_FULL_PIPELINE_REPLAY_V1",
        "status": builder_verdict(gate_results),
        "start": start,
        "end": end,
        "btc_db": str(btc_db),
        "eth_db": str(eth_db),
        "store_path": str(resolved_store),
        "config_hashes": {"BTCUSDT": btc.config_hash, "ETHUSDT": eth.config_hash},
        "pipeline_trade_counts": {"BTCUSDT": len(btc.trades), "ETHUSDT": len(eth.trades)},
        "portfolio_metrics": metrics,
        "symbol_metrics": per_symbol,
        "veto_breakdown": veto_breakdown(portfolio.vetoes),
        "approved_count": len(portfolio.approved_trades),
        "veto_count": len(portfolio.vetoes),
        "cap_utilization": {
            "max_total_risk_pct": portfolio.max_total_risk_pct,
            "max_gross_notional_pct": portfolio.max_gross_notional_pct,
            "max_directional_notional_pct": portfolio.max_directional_notional_pct,
            "max_open_positions": portfolio.max_open_positions,
        },
        "gates": gate_results,
        "gate_contract": asdict(gates),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    generate_report(payload, report_path)
    return payload


def generate_report(payload: dict[str, Any], report_path: Path) -> str:
    metrics = payload["portfolio_metrics"]
    lines = [
        "# Multi-Asset Full Pipeline Replay V1",
        "",
        "**Milestone:** `MULTI_ASSET_FULL_PIPELINE_REPLAY_V1`",
        f"**Status:** `{payload['status']}`",
        "**Scope:** Research Lab offline replay only; no runtime, PAPER, LIVE, or production DB changes.",
        "",
        "## Methodology",
        "",
        "- Regenerate BTC and ETH trial-00095 trades through the existing single-symbol backtest pipeline.",
        "- Use frozen trial-00095 parameters; only the research symbol changes between BTCUSDT and ETHUSDT.",
        "- Run each symbol on a copied temporary replay DB; source datasets remain read-only.",
        "- Apply the offline portfolio gate from Phase 2 to regenerated trade candidates.",
        "- This validates source-pipeline regeneration plus portfolio contracts, not runtime readiness.",
        "",
        "## Inputs",
        "",
        f"- BTC DB: `{payload['btc_db']}`",
        f"- ETH DB: `{payload['eth_db']}`",
        f"- Trial store: `{payload['store_path']}`",
        f"- Window: {payload['start']} to {payload['end']} exclusive",
        f"- Pipeline trade counts: `{json.dumps(payload['pipeline_trade_counts'], sort_keys=True)}`",
        "",
        "## Portfolio Metrics",
        "",
        "| Trades | ER | PF | Win Rate | PnL R Sum | Max DD R | Max Loss Streak |",
        "|---:|---:|---:|---:|---:|---:|---:|",
        (
            f"| {metrics['trades']} | {metrics['er']:.3f} | {metrics['pf']:.2f} | "
            f"{metrics['win_rate']:.1%} | {metrics['pnl_r_sum']:.2f} | "
            f"{metrics['max_drawdown_r']:.2f} | {metrics['max_consecutive_losses']} |"
        ),
        "",
        "## Per-Symbol Metrics After Portfolio Gate",
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

    lines.extend(
        [
            "",
            "## Veto Breakdown",
            "",
            f"- Approved trades: {payload['approved_count']}",
            f"- Vetoed signals: {payload['veto_count']}",
        ]
    )
    for reason, count in payload["veto_breakdown"].items():
        lines.append(f"- `{reason}`: {count}")

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
            "## Limitations",
            "",
            "- This is still offline research and does not approve ETH/BTC PAPER.",
            "- Portfolio gate is applied to regenerated closed trades, not live intrabar exposures.",
            "- Full runtime integration still requires separate implementation, storage migration, recovery, and shadow validation.",
            "- M4 checkpoint remains the blocker for runtime integration decisions.",
        ]
    )
    text = "\n".join(lines) + "\n"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(text, encoding="utf-8")
    return text


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--btc-db", type=Path, default=DEFAULT_BTC_DB)
    parser.add_argument("--eth-db", type=Path, default=DEFAULT_ETH_DB)
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
        store_path=args.store,
        report_path=args.report,
        start=args.start,
        end=args.end,
    )
    print(
        json.dumps(
            {
                "status": payload["status"],
                "portfolio_metrics": payload["portfolio_metrics"],
                "vetoes": payload["veto_breakdown"],
                "report": str(args.report),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
