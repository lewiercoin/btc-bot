#!/usr/bin/env python3
"""Depth-threshold portfolio impact diagnostic for ETH/SOL shadow decisions.

Research Lab only. This diagnostic compares the frozen transfer depth
threshold against the audited ETH/SOL asset-specific threshold before changing
the SOL shadow profile. It does not modify runtime, sidecar, PAPER, LIVE, M4,
settings, or production storage.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import math
import shutil
import sqlite3
import statistics
import tempfile
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from backtest.backtest_runner import BacktestConfig, BacktestRunner
from research_lab.eth_trial_00095_transfer_feasibility import (
    DEFAULT_ETH_DB,
    DEFAULT_STORE,
    END,
    TRIAL_00095_ID,
    _derive_1h_candles,
    _ensure_runtime_tables,
    load_trial_params,
    resolve_trial_store_path,
)
from research_lab.multi_asset_full_pipeline_replay import DEFAULT_BTC_DB, run_symbol_pipeline
from research_lab.portfolio_replay_harness import (
    ArtifactTrade,
    ReplayTradeResult,
    compute_metrics,
    run_artifact_portfolio_replay,
    symbol_metrics,
    veto_breakdown,
)
from research_lab.settings_adapter import build_candidate_settings
from research_lab.sol_trial_00095_transfer_feasibility import DEFAULT_SOL_DB
from settings import AppSettings, load_settings


MILESTONE = "DEPTH_THRESHOLD_PORTFOLIO_IMPACT_DIAGNOSTIC_V1"
DEFAULT_REPORT = Path("docs/analysis/DEPTH_THRESHOLD_PORTFOLIO_IMPACT_DIAGNOSTIC_2026-05-21.md")
OOS_START = "2025-01-01"
OOS_END = END
FROZEN_DEPTH = 0.00649
ASSET_SPECIFIC_DEPTH = 0.0075
SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT")
RISK_BY_SYMBOL = {
    "BTCUSDT": 0.0035,
    "ETHUSDT": 0.0035,
    "SOLUSDT": 0.0015,
}


@dataclass(frozen=True, slots=True)
class ThresholdScenario:
    scenario_id: str
    eth_depth: float
    sol_depth: float
    description: str


@dataclass(frozen=True, slots=True)
class DiagnosticGates:
    min_portfolio_trades: int = 250
    min_sol_trade_retention_pct: float = 0.65
    max_portfolio_dd_r: float = 20.0
    max_daily_corr_abs: float = 0.70
    max_same_bar_overlap_share: float = 0.10


def scenario_grid() -> tuple[ThresholdScenario, ...]:
    return (
        ThresholdScenario(
            scenario_id="both_frozen_transfer",
            eth_depth=FROZEN_DEPTH,
            sol_depth=FROZEN_DEPTH,
            description="ETH and SOL use frozen BTC trial-00095 transfer depth.",
        ),
        ThresholdScenario(
            scenario_id="current_shadow_profile",
            eth_depth=ASSET_SPECIFIC_DEPTH,
            sol_depth=FROZEN_DEPTH,
            description="Current production shadow profile: ETH asset-specific, SOL frozen transfer.",
        ),
        ThresholdScenario(
            scenario_id="eth_sol_asset_specific",
            eth_depth=ASSET_SPECIFIC_DEPTH,
            sol_depth=ASSET_SPECIFIC_DEPTH,
            description="Candidate profile: ETH and SOL use audited asset-specific depth.",
        ),
    )


def build_symbol_settings(
    *,
    base_settings: AppSettings,
    trial_params: dict[str, Any],
    symbol: str,
    min_sweep_depth_pct: float,
) -> AppSettings:
    merged = {**trial_params, "min_sweep_depth_pct": min_sweep_depth_pct}
    candidate = build_candidate_settings(base_settings, merged)
    strategy = dataclasses.replace(candidate.strategy, symbol=symbol.upper())
    return dataclasses.replace(candidate, strategy=strategy)


def prepare_alt_replay_db(*, source_db: Path, target_db: Path, symbol: str) -> None:
    shutil.copy2(str(source_db), str(target_db))
    conn = sqlite3.connect(str(target_db))
    try:
        _ensure_runtime_tables(conn)
        _derive_1h_candles(conn, symbol=symbol.upper())
        conn.commit()
    finally:
        conn.close()


def reset_replay_artifact_tables(conn: sqlite3.Connection) -> None:
    _ensure_runtime_tables(conn)
    conn.execute("DELETE FROM signal_candidates")
    conn.execute("DELETE FROM executable_signals")
    conn.execute("DELETE FROM positions")
    conn.execute("DELETE FROM trade_log")
    conn.commit()


def run_alt_threshold_replay(
    *,
    symbol: str,
    source_db: Path,
    settings: AppSettings,
    start: str,
    end: str,
) -> tuple[Any, tuple[ArtifactTrade, ...]]:
    symbol = symbol.upper()
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        prepare_alt_replay_db(source_db=source_db, target_db=tmp_path, symbol=symbol)
        conn = sqlite3.connect(str(tmp_path))
        conn.row_factory = sqlite3.Row
        try:
            reset_replay_artifact_tables(conn)
            runner = BacktestRunner(conn, settings=settings)
            result = runner.run(
                BacktestConfig(
                    start_date=start,
                    end_date=end,
                    symbol=symbol,
                    initial_equity=10_000.0,
                    fee_rate_maker=0.0004,
                    fee_rate_taker=0.0004,
                )
            )
        finally:
            conn.close()
    finally:
        tmp_path.unlink(missing_ok=True)
        tmp_path.with_name(tmp_path.name + "-wal").unlink(missing_ok=True)
        tmp_path.with_name(tmp_path.name + "-shm").unlink(missing_ok=True)

    return result.performance, tuple(trade_to_artifact(trade, symbol=symbol) for trade in result.trades)


def trade_to_artifact(trade: Any, *, symbol: str) -> ArtifactTrade:
    if trade.closed_at is None:
        raise RuntimeError(f"Trade {trade.trade_id} has no closed_at timestamp")
    symbol = symbol.upper()
    return ArtifactTrade(
        symbol=symbol,
        trade_id=str(trade.trade_id),
        opened_at=to_utc(trade.opened_at),
        direction=str(trade.direction).upper(),
        pnl_r=float(trade.pnl_r),
        regime=str(trade.regime),
        risk_pct=RISK_BY_SYMBOL[symbol],
    )


def clone_with_risk(trades: Iterable[ArtifactTrade]) -> tuple[ArtifactTrade, ...]:
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
                risk_pct=RISK_BY_SYMBOL[trade.symbol],
                gross_notional_pct=trade.gross_notional_pct,
            )
        )
    return tuple(cloned)


def to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def daily_pnl_by_symbol(trades: Iterable[ArtifactTrade | ReplayTradeResult]) -> dict[str, dict[str, float]]:
    daily: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for trade in trades:
        daily[trade.symbol][trade.opened_at.date().isoformat()] += float(trade.pnl_r)
    return {symbol: dict(rows) for symbol, rows in daily.items()}


def pearson(xs: list[float], ys: list[float]) -> float:
    if len(xs) != len(ys) or len(xs) < 2:
        return 0.0
    x_mean = statistics.mean(xs)
    y_mean = statistics.mean(ys)
    numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))
    x_var = sum((x - x_mean) ** 2 for x in xs)
    y_var = sum((y - y_mean) ** 2 for y in ys)
    if x_var <= 1e-12 or y_var <= 1e-12:
        return 0.0
    return numerator / math.sqrt(x_var * y_var)


def correlation_matrix(trades: Iterable[ArtifactTrade | ReplayTradeResult]) -> dict[str, dict[str, float]]:
    daily = daily_pnl_by_symbol(trades)
    days = sorted({day for rows in daily.values() for day in rows})
    matrix: dict[str, dict[str, float]] = {}
    for left in SYMBOLS:
        matrix[left] = {}
        for right in SYMBOLS:
            xs = [daily.get(left, {}).get(day, 0.0) for day in days]
            ys = [daily.get(right, {}).get(day, 0.0) for day in days]
            matrix[left][right] = pearson(xs, ys)
    return matrix


def floor_15m(ts: datetime) -> datetime:
    minute = (ts.minute // 15) * 15
    return ts.replace(minute=minute, second=0, microsecond=0)


def same_bar_overlap_by_pair(trades: Iterable[ArtifactTrade | ReplayTradeResult]) -> dict[str, dict[str, Any]]:
    bars_by_symbol: dict[str, set[datetime]] = {symbol: set() for symbol in SYMBOLS}
    for trade in trades:
        bars_by_symbol[trade.symbol].add(floor_15m(trade.opened_at))

    pairs = (("BTCUSDT", "ETHUSDT"), ("BTCUSDT", "SOLUSDT"), ("ETHUSDT", "SOLUSDT"))
    output: dict[str, dict[str, Any]] = {}
    for left, right in pairs:
        left_bars = bars_by_symbol[left]
        right_bars = bars_by_symbol[right]
        unique = left_bars | right_bars
        overlap = left_bars & right_bars
        output[f"{left}_{right}"] = {
            "same_15m_bars": len(overlap),
            "unique_signal_bars": len(unique),
            "overlap_share": len(overlap) / len(unique) if unique else 0.0,
        }
    return output


def max_abs_offdiag_corr(matrix: dict[str, dict[str, float]]) -> float:
    values = []
    for left in SYMBOLS:
        for right in SYMBOLS:
            if left != right:
                values.append(abs(matrix.get(left, {}).get(right, 0.0)))
    return max(values) if values else 0.0


def max_pair_overlap(overlap: dict[str, dict[str, Any]]) -> float:
    return max((float(item["overlap_share"]) for item in overlap.values()), default=0.0)


def pct_delta(value: float, reference: float) -> float:
    if abs(reference) < 1e-12:
        return 0.0
    return (value - reference) / reference


def scenario_verdict(payload: dict[str, Any], gates: DiagnosticGates) -> str:
    current = payload["scenarios"]["current_shadow_profile"]
    candidate = payload["scenarios"]["eth_sol_asset_specific"]
    frozen = payload["scenarios"]["both_frozen_transfer"]
    sol_retention = candidate["standalone"]["SOLUSDT"]["trades"] / max(frozen["standalone"]["SOLUSDT"]["trades"], 1)
    if (
        candidate["portfolio_metrics"]["trades"] >= gates.min_portfolio_trades
        and sol_retention >= gates.min_sol_trade_retention_pct
        and candidate["portfolio_metrics"]["max_drawdown_r"] <= gates.max_portfolio_dd_r
        and candidate["max_abs_daily_corr"] <= gates.max_daily_corr_abs
        and candidate["max_same_bar_overlap_share"] <= gates.max_same_bar_overlap_share
        and candidate["portfolio_metrics"]["er"] >= current["portfolio_metrics"]["er"]
    ):
        return "ASSET_SPECIFIC_DEPTH_SUPPORTED_FOR_SHADOW_DECISION"
    return "KEEP_CURRENT_SHADOW_PROFILE_PENDING_FORWARD_EVIDENCE"


def evaluate_scenario_gates(payload: dict[str, Any], gates: DiagnosticGates) -> dict[str, dict[str, Any]]:
    candidate = payload["scenarios"]["eth_sol_asset_specific"]
    frozen = payload["scenarios"]["both_frozen_transfer"]
    sol_retention = candidate["standalone"]["SOLUSDT"]["trades"] / max(frozen["standalone"]["SOLUSDT"]["trades"], 1)
    return {
        "min_portfolio_trades": {
            "value": candidate["portfolio_metrics"]["trades"],
            "threshold": gates.min_portfolio_trades,
            "pass": candidate["portfolio_metrics"]["trades"] >= gates.min_portfolio_trades,
        },
        "min_sol_trade_retention_pct": {
            "value": sol_retention,
            "threshold": gates.min_sol_trade_retention_pct,
            "pass": sol_retention >= gates.min_sol_trade_retention_pct,
        },
        "max_portfolio_dd_r": {
            "value": candidate["portfolio_metrics"]["max_drawdown_r"],
            "threshold": gates.max_portfolio_dd_r,
            "pass": candidate["portfolio_metrics"]["max_drawdown_r"] <= gates.max_portfolio_dd_r,
        },
        "max_daily_corr_abs": {
            "value": candidate["max_abs_daily_corr"],
            "threshold": gates.max_daily_corr_abs,
            "pass": candidate["max_abs_daily_corr"] <= gates.max_daily_corr_abs,
        },
        "max_same_bar_overlap_share": {
            "value": candidate["max_same_bar_overlap_share"],
            "threshold": gates.max_same_bar_overlap_share,
            "pass": candidate["max_same_bar_overlap_share"] <= gates.max_same_bar_overlap_share,
        },
    }


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
    trial_params = load_trial_params(resolved_store, trial_id=TRIAL_00095_ID)
    base_settings = load_settings(profile="research")

    btc = run_symbol_pipeline(symbol="BTCUSDT", source_db=btc_db, store_path=resolved_store, start=start, end=end)
    btc_trades = clone_with_risk(btc.trades)

    eth_by_depth: dict[float, tuple[ArtifactTrade, ...]] = {}
    sol_by_depth: dict[float, tuple[ArtifactTrade, ...]] = {}
    standalone_perf: dict[str, dict[str, Any]] = {}
    for depth in (FROZEN_DEPTH, ASSET_SPECIFIC_DEPTH):
        eth_settings = build_symbol_settings(base_settings=base_settings, trial_params=trial_params, symbol="ETHUSDT", min_sweep_depth_pct=depth)
        eth_perf, eth_trades = run_alt_threshold_replay(symbol="ETHUSDT", source_db=eth_db, settings=eth_settings, start=start, end=end)
        eth_by_depth[depth] = eth_trades
        standalone_perf[f"ETHUSDT_{depth:.5f}"] = asdict(eth_perf)

        sol_settings = build_symbol_settings(base_settings=base_settings, trial_params=trial_params, symbol="SOLUSDT", min_sweep_depth_pct=depth)
        sol_perf, sol_trades = run_alt_threshold_replay(symbol="SOLUSDT", source_db=sol_db, settings=sol_settings, start=start, end=end)
        sol_by_depth[depth] = sol_trades
        standalone_perf[f"SOLUSDT_{depth:.5f}"] = asdict(sol_perf)

    scenarios: dict[str, Any] = {}
    for scenario in scenario_grid():
        trades = [*btc_trades, *eth_by_depth[scenario.eth_depth], *sol_by_depth[scenario.sol_depth]]
        portfolio = run_artifact_portfolio_replay(trades, symbols=SYMBOLS)
        matrix = correlation_matrix(portfolio.approved_trades)
        overlap = same_bar_overlap_by_pair(portfolio.approved_trades)
        scenarios[scenario.scenario_id] = {
            "description": scenario.description,
            "thresholds": {"ETHUSDT": scenario.eth_depth, "SOLUSDT": scenario.sol_depth},
            "standalone": {
                "BTCUSDT": {"trades": len(btc_trades), "performance": asdict(btc.performance)},
                "ETHUSDT": {"trades": len(eth_by_depth[scenario.eth_depth]), "performance": standalone_perf[f"ETHUSDT_{scenario.eth_depth:.5f}"]},
                "SOLUSDT": {"trades": len(sol_by_depth[scenario.sol_depth]), "performance": standalone_perf[f"SOLUSDT_{scenario.sol_depth:.5f}"]},
            },
            "portfolio_metrics": compute_metrics(portfolio.approved_trades),
            "symbol_metrics": symbol_metrics(portfolio.approved_trades),
            "veto_breakdown": veto_breakdown(portfolio.vetoes),
            "veto_count": len(portfolio.vetoes),
            "approved_count": len(portfolio.approved_trades),
            "cap_utilization": {
                "max_total_risk_pct": portfolio.max_total_risk_pct,
                "max_gross_notional_pct": portfolio.max_gross_notional_pct,
                "max_directional_notional_pct": portfolio.max_directional_notional_pct,
                "max_open_positions": portfolio.max_open_positions,
            },
            "correlation_matrix_daily_r": matrix,
            "max_abs_daily_corr": max_abs_offdiag_corr(matrix),
            "same_bar_overlap": overlap,
            "max_same_bar_overlap_share": max_pair_overlap(overlap),
        }

    gates = DiagnosticGates()
    payload: dict[str, Any] = {
        "milestone": MILESTONE,
        "status": "PENDING_VERDICT",
        "start": start,
        "end": end,
        "btc_db": str(btc_db),
        "eth_db": str(eth_db),
        "sol_db": str(sol_db),
        "store_path": str(resolved_store),
        "trial_id": TRIAL_00095_ID,
        "risk_by_symbol": RISK_BY_SYMBOL,
        "scenarios": scenarios,
        "comparisons": build_comparisons(scenarios),
        "gate_contract": asdict(gates),
        "gates": {},
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    payload["gates"] = evaluate_scenario_gates(payload, gates)
    payload["status"] = scenario_verdict(payload, gates)
    generate_report(payload, report_path)
    return payload


def build_comparisons(scenarios: dict[str, Any]) -> dict[str, Any]:
    current = scenarios["current_shadow_profile"]
    candidate = scenarios["eth_sol_asset_specific"]
    frozen = scenarios["both_frozen_transfer"]
    return {
        "candidate_vs_current": compare_scenarios(candidate, current),
        "candidate_vs_frozen": compare_scenarios(candidate, frozen),
        "current_vs_frozen": compare_scenarios(current, frozen),
    }


def compare_scenarios(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    left_metrics = left["portfolio_metrics"]
    right_metrics = right["portfolio_metrics"]
    return {
        "portfolio_trade_delta": left_metrics["trades"] - right_metrics["trades"],
        "portfolio_trade_delta_pct": pct_delta(left_metrics["trades"], right_metrics["trades"]),
        "portfolio_er_delta_pct": pct_delta(left_metrics["er"], right_metrics["er"]),
        "portfolio_pf_delta_pct": pct_delta(left_metrics["pf"], right_metrics["pf"]),
        "portfolio_dd_delta_pct": pct_delta(left_metrics["max_drawdown_r"], right_metrics["max_drawdown_r"]),
        "eth_standalone_trade_delta": left["standalone"]["ETHUSDT"]["trades"] - right["standalone"]["ETHUSDT"]["trades"],
        "sol_standalone_trade_delta": left["standalone"]["SOLUSDT"]["trades"] - right["standalone"]["SOLUSDT"]["trades"],
    }


def generate_report(payload: dict[str, Any], report_path: Path) -> str:
    lines = [
        "# Depth Threshold Portfolio Impact Diagnostic V1",
        "",
        f"**Milestone:** `{MILESTONE}`",
        f"**Status:** `{payload['status']}`",
        "**Scope:** Research Lab diagnostic only; no runtime, sidecar, PAPER, LIVE, M4, settings, or production DB changes.",
        "",
        "## Methodology",
        "",
        "- Compare ETH/SOL `min_sweep_depth_pct` profiles on the untouched OOS window.",
        "- Keep all non-depth trial-00095 parameters frozen.",
        "- Keep BTC at frozen trial-00095.",
        "- Apply the existing offline ResearchPortfolioGate to BTC/ETH/SOL candidates.",
        "- Use BTC/ETH risk 0.35% and SOL candidate risk 0.15% for portfolio gate simulation.",
        "- Treat results as threshold decision support only; this does not approve PAPER or LIVE.",
        "",
        "## Inputs",
        "",
        f"- Window: {payload['start']} to {payload['end']} exclusive",
        f"- BTC DB: `{payload['btc_db']}`",
        f"- ETH DB: `{payload['eth_db']}`",
        f"- SOL DB: `{payload['sol_db']}`",
        f"- Trial store: `{payload['store_path']}`",
        f"- Risk by symbol: `{json.dumps(payload['risk_by_symbol'], sort_keys=True)}`",
        "",
        "## Scenario Summary",
        "",
        "| Scenario | ETH Depth | SOL Depth | Portfolio Trades | ER | PF | Max DD R | BTC Trades | ETH Trades | SOL Trades | Max Corr | Max Overlap |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for scenario_id in ("both_frozen_transfer", "current_shadow_profile", "eth_sol_asset_specific"):
        scenario = payload["scenarios"][scenario_id]
        m = scenario["portfolio_metrics"]
        standalone = scenario["standalone"]
        lines.append(
            f"| {scenario_id} | {scenario['thresholds']['ETHUSDT']:.5f} | {scenario['thresholds']['SOLUSDT']:.5f} | "
            f"{m['trades']} | {m['er']:.3f} | {m['pf']:.2f} | {m['max_drawdown_r']:.2f} | "
            f"{standalone['BTCUSDT']['trades']} | {standalone['ETHUSDT']['trades']} | {standalone['SOLUSDT']['trades']} | "
            f"{scenario['max_abs_daily_corr']:.3f} | {scenario['max_same_bar_overlap_share']:.1%} |"
        )

    lines.extend(["", "## Candidate vs Current", ""])
    comparison = payload["comparisons"]["candidate_vs_current"]
    lines.extend(
        [
            f"- Portfolio trade delta: {comparison['portfolio_trade_delta']} ({comparison['portfolio_trade_delta_pct']:.1%})",
            f"- Portfolio ER delta: {comparison['portfolio_er_delta_pct']:.1%}",
            f"- Portfolio PF delta: {comparison['portfolio_pf_delta_pct']:.1%}",
            f"- Portfolio DD delta: {comparison['portfolio_dd_delta_pct']:.1%}",
            f"- ETH standalone trade delta: {comparison['eth_standalone_trade_delta']}",
            f"- SOL standalone trade delta: {comparison['sol_standalone_trade_delta']}",
        ]
    )

    lines.extend(["", "## Scenario Details", ""])
    for scenario_id in ("both_frozen_transfer", "current_shadow_profile", "eth_sol_asset_specific"):
        scenario = payload["scenarios"][scenario_id]
        lines.extend(
            [
                f"### {scenario_id}",
                "",
                scenario["description"],
                "",
                "| Symbol | Approved Trades | ER | PF | Max DD R | Max Loss Streak |",
                "|---|---:|---:|---:|---:|---:|",
            ]
        )
        for symbol in SYMBOLS:
            metrics = scenario["symbol_metrics"].get(symbol, {"trades": 0, "er": 0.0, "pf": 0.0, "max_drawdown_r": 0.0, "max_consecutive_losses": 0})
            lines.append(
                f"| {symbol} | {metrics['trades']} | {metrics['er']:.3f} | {metrics['pf']:.2f} | "
                f"{metrics['max_drawdown_r']:.2f} | {metrics['max_consecutive_losses']} |"
            )
        lines.extend(["", "Daily R correlation matrix:", "", "| Symbol | BTCUSDT | ETHUSDT | SOLUSDT |", "|---|---:|---:|---:|"])
        matrix = scenario["correlation_matrix_daily_r"]
        for symbol in SYMBOLS:
            row = matrix.get(symbol, {})
            lines.append(f"| {symbol} | {row.get('BTCUSDT', 0.0):.3f} | {row.get('ETHUSDT', 0.0):.3f} | {row.get('SOLUSDT', 0.0):.3f} |")
        lines.extend(["", "Same-bar overlap:", ""])
        for pair, overlap in scenario["same_bar_overlap"].items():
            lines.append(
                f"- `{pair}`: {overlap['same_15m_bars']} / {overlap['unique_signal_bars']} ({overlap['overlap_share']:.1%})"
            )
        lines.extend(["", "Veto breakdown:", ""])
        if scenario["veto_breakdown"]:
            for reason, count in scenario["veto_breakdown"].items():
                lines.append(f"- `{reason}`: {count}")
        else:
            lines.append("- none")
        lines.append("")

    lines.extend(["## Gates", "", "| Gate | Value | Threshold | Result |", "|---|---:|---:|---|"])
    for gate, item in payload["gates"].items():
        result = "PASS" if item["pass"] else "FAIL"
        lines.append(f"| {gate} | {item['value']:.4g} | {item['threshold']:.4g} | {result} |")

    lines.extend(
        [
            "",
            "## Builder Interpretation",
            "",
            interpretation(payload),
            "",
            "## Audit Questions",
            "",
            "1. Does this remain research-only with no runtime/sidecar/PAPER/LIVE changes?",
            "2. Are only ETH/SOL depth thresholds varied while all other trial-00095 parameters remain frozen?",
            "3. Is the OOS comparison aligned with the asset-specific optimization reports?",
            "4. Are portfolio correlation, same-bar overlap, vetoes, and DD computed deterministically?",
            "5. Does the verdict avoid approving PAPER or runtime promotion?",
        ]
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(lines) + "\n"
    report_path.write_text(text, encoding="utf-8")
    return text


def interpretation(payload: dict[str, Any]) -> str:
    if payload["status"] == "ASSET_SPECIFIC_DEPTH_SUPPORTED_FOR_SHADOW_DECISION":
        return (
            "The OOS portfolio diagnostic supports using the ETH/SOL asset-specific depth profile as a shadow decision input. "
            "This is not PAPER approval; the next step would be an audited shadow-only threshold update or a runtime contract milestone."
        )
    return (
        "The OOS portfolio diagnostic does not justify changing the SOL shadow depth immediately. "
        "Keep the current shadow profile and collect more forward evidence before changing SOL threshold or PAPER scope."
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--btc-db", type=Path, default=DEFAULT_BTC_DB)
    parser.add_argument("--eth-db", type=Path, default=DEFAULT_ETH_DB)
    parser.add_argument("--sol-db", type=Path, default=DEFAULT_SOL_DB)
    parser.add_argument("--store", type=Path, default=DEFAULT_STORE)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--start", default=OOS_START)
    parser.add_argument("--end", default=OOS_END)
    return parser.parse_args()


def main() -> None:
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
    print(json.dumps({"milestone": payload["milestone"], "status": payload["status"], "report": str(args.report)}, sort_keys=True))


if __name__ == "__main__":
    main()
