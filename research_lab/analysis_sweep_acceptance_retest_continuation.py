#!/usr/bin/env python3
"""Offline sweep-acceptance retest continuation feasibility study.

This extends the simple no-reclaim continuation screen with a sequence:

    acceptance beyond swept level -> retest -> hold -> second impulse -> entry

It is research-only and does not import or modify runtime decision layers.
"""

from __future__ import annotations

import os
import sys

if __name__ == "__main__" and sys.path:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if os.path.abspath(sys.path[0]) == script_dir:
        sys.path.pop(0)
        sys.path.insert(0, os.path.dirname(script_dir))

import argparse
import json
import sqlite3
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any

from research_lab.analysis_sweep_acceptance_continuation import (
    MAKER_FEE_PCT,
    SLIPPAGE_BPS_PER_SIDE,
    TAKER_FEE_PCT,
    Candle,
    compute_atr,
    cost_in_r,
    detect_equal_levels,
    load_candles,
    load_tfi_15m,
    parse_ts,
)


DEFAULT_DB_PATH = Path("research_lab/data/crowded_unwind_backtest.db")
DEFAULT_OUTPUT_PATH = Path("research_lab/analysis_output/sweep_acceptance_retest_continuation_20220101_20260329.json")
DEFAULT_REPORT_PATH = Path("research_lab/reports/sweep_acceptance_retest_continuation_feasibility_20220101_20260329.md")


@dataclass(frozen=True, slots=True)
class RetestConfig:
    config_id: str
    equal_level_lookback: int = 50
    equal_level_tol_atr: float = 0.25
    min_hits: int = 3
    min_age_bars: int = 5
    atr_period: int = 14
    sweep_buf_atr: float = 0.15
    proximity_atr: float = 0.40
    reclaim_buf_atr: float = 0.07
    acceptance_buf_atr: float = 0.05
    wick_min_atr: float = 0.15
    min_sweep_depth_pct: float = 0.00649
    retest_window_bars: int = 8
    retest_tolerance_atr: float = 0.25
    max_reentry_atr: float = 0.15
    impulse_buf_atr: float = 0.05
    tfi_abs_min: float | None = None
    require_retest_tfi: bool = False
    stop_atr_beyond_level: float = 0.75
    target_r: float = 2.0
    max_hold_bars: int = 48
    directions: tuple[str, ...] = ("LONG", "SHORT")


@dataclass(frozen=True, slots=True)
class RetestSignal:
    symbol: str
    config_id: str
    direction: str
    sweep_side: str
    trigger_idx: int
    retest_idx: int
    impulse_idx: int
    entry_idx: int
    trigger_time: datetime
    retest_time: datetime
    impulse_time: datetime
    entry_time: datetime
    level: float
    entry_price: float
    stop_price: float
    target_price: float
    atr: float
    sweep_depth_pct: float
    trigger_tfi: float
    retest_tfi: float
    impulse_tfi: float


@dataclass(frozen=True, slots=True)
class RetestTrade:
    signal: RetestSignal
    exit_idx: int
    exit_time: datetime
    exit_price: float
    gross_pnl_r: float
    net_pnl_r: float
    cost_r: float
    exit_reason: str
    mfe_r: float
    mae_r: float


@dataclass(slots=True)
class ConfigRun:
    config: RetestConfig
    bars_evaluated: int = 0
    acceptance_candidates: int = 0
    retest_candidates: int = 0
    impulse_candidates: int = 0
    trades: list[RetestTrade] = field(default_factory=list)
    rejection_reasons: Counter[str] = field(default_factory=Counter)


def _tfi_pass(direction: str, tfi: float, threshold: float | None) -> bool:
    if threshold is None:
        return True
    return tfi >= threshold if direction == "LONG" else tfi <= -threshold


def _acceptance_candidate(
    candles: list[Candle],
    tfi_by_time: dict[datetime, float],
    idx: int,
    *,
    config: RetestConfig,
) -> tuple[tuple[str, str, float, float, float, float] | None, str]:
    min_context = max(config.equal_level_lookback, config.atr_period + 1)
    if idx < min_context:
        return None, "insufficient_history"
    trigger = candles[idx]
    atr = compute_atr(candles[max(0, idx - config.atr_period - 1) : idx + 1], config.atr_period)
    if atr <= 0:
        return None, "atr_unavailable"

    prior = candles[idx - config.equal_level_lookback : idx]
    tolerance = atr * config.equal_level_tol_atr
    equal_lows = detect_equal_levels(
        [(i, candle.low) for i, candle in enumerate(prior)],
        tolerance=tolerance,
        min_hits=config.min_hits,
        min_age_bars=config.min_age_bars,
    )
    equal_highs = detect_equal_levels(
        [(i, candle.high) for i, candle in enumerate(prior)],
        tolerance=tolerance,
        min_hits=config.min_hits,
        min_age_bars=config.min_age_bars,
    )

    body_low = min(trigger.open, trigger.close)
    body_high = max(trigger.open, trigger.close)
    sweep_buffer = config.sweep_buf_atr * atr
    proximity = config.proximity_atr * atr
    reclaim_buffer = config.reclaim_buf_atr * atr
    acceptance_buffer = config.acceptance_buf_atr * atr
    wick_min = config.wick_min_atr * atr
    trigger_tfi = tfi_by_time.get(trigger.open_time, 0.0)

    for level in equal_highs:
        if abs(trigger.open - level) > proximity:
            continue
        swept = trigger.high > level + sweep_buffer
        reclaimed = trigger.close < level - reclaim_buffer and (trigger.high - body_high) >= wick_min
        accepted = trigger.close > level + acceptance_buffer
        if swept and not reclaimed and accepted:
            depth = abs(trigger.high - level) / level if level else 0.0
            if depth < config.min_sweep_depth_pct:
                return None, "sweep_too_shallow"
            if "LONG" not in config.directions:
                return None, "direction_filtered"
            if not _tfi_pass("LONG", trigger_tfi, config.tfi_abs_min):
                return None, "trigger_tfi_not_confirmed"
            return ("LONG", "HIGH", level, depth, atr, trigger_tfi), "acceptance"

    for level in equal_lows:
        if abs(trigger.open - level) > proximity:
            continue
        swept = trigger.low < level - sweep_buffer
        reclaimed = trigger.close > level + reclaim_buffer and (body_low - trigger.low) >= wick_min
        accepted = trigger.close < level - acceptance_buffer
        if swept and not reclaimed and accepted:
            depth = abs(level - trigger.low) / level if level else 0.0
            if depth < config.min_sweep_depth_pct:
                return None, "sweep_too_shallow"
            if "SHORT" not in config.directions:
                return None, "direction_filtered"
            if not _tfi_pass("SHORT", trigger_tfi, config.tfi_abs_min):
                return None, "trigger_tfi_not_confirmed"
            return ("SHORT", "LOW", level, depth, atr, trigger_tfi), "acceptance"

    return None, "no_acceptance"


def _find_retest_and_impulse(
    candles: list[Candle],
    tfi_by_time: dict[datetime, float],
    *,
    trigger_idx: int,
    direction: str,
    level: float,
    atr: float,
    config: RetestConfig,
) -> tuple[int, int, str]:
    retest_end = min(len(candles) - 2, trigger_idx + config.retest_window_bars)
    retest_tolerance = config.retest_tolerance_atr * atr
    max_reentry = config.max_reentry_atr * atr
    impulse_buffer = config.impulse_buf_atr * atr

    for retest_idx in range(trigger_idx + 1, retest_end + 1):
        candle = candles[retest_idx]
        retest_tfi = tfi_by_time.get(candle.open_time, 0.0)
        if direction == "LONG":
            touched = candle.low <= level + retest_tolerance
            held = candle.close >= level - max_reentry
            wick = min(candle.open, candle.close) - candle.low
            rejected = wick >= config.wick_min_atr * atr and candle.close >= level
            if not (touched and held and rejected):
                continue
            if config.require_retest_tfi and retest_tfi < 0:
                continue
            for impulse_idx in range(retest_idx + 1, min(len(candles) - 1, retest_idx + 4) + 1):
                impulse = candles[impulse_idx]
                impulse_tfi = tfi_by_time.get(impulse.open_time, 0.0)
                if impulse.close > candle.high + impulse_buffer and _tfi_pass(direction, impulse_tfi, config.tfi_abs_min):
                    return retest_idx, impulse_idx, "sequence"
        else:
            touched = candle.high >= level - retest_tolerance
            held = candle.close <= level + max_reentry
            wick = candle.high - max(candle.open, candle.close)
            rejected = wick >= config.wick_min_atr * atr and candle.close <= level
            if not (touched and held and rejected):
                continue
            if config.require_retest_tfi and retest_tfi > 0:
                continue
            for impulse_idx in range(retest_idx + 1, min(len(candles) - 1, retest_idx + 4) + 1):
                impulse = candles[impulse_idx]
                impulse_tfi = tfi_by_time.get(impulse.open_time, 0.0)
                if impulse.close < candle.low - impulse_buffer and _tfi_pass(direction, impulse_tfi, config.tfi_abs_min):
                    return retest_idx, impulse_idx, "sequence"

    return -1, -1, "no_retest_impulse"


def maybe_signal(
    candles: list[Candle],
    tfi_by_time: dict[datetime, float],
    idx: int,
    *,
    symbol: str,
    config: RetestConfig,
) -> tuple[RetestSignal | None, str]:
    if idx + 2 >= len(candles):
        return None, "no_future_bars"
    accepted, reason = _acceptance_candidate(candles, tfi_by_time, idx, config=config)
    if accepted is None:
        return None, reason
    direction, sweep_side, level, depth, atr, trigger_tfi = accepted

    retest_idx, impulse_idx, sequence_reason = _find_retest_and_impulse(
        candles,
        tfi_by_time,
        trigger_idx=idx,
        direction=direction,
        level=level,
        atr=atr,
        config=config,
    )
    if retest_idx < 0 or impulse_idx < 0:
        return None, sequence_reason
    entry_idx = impulse_idx + 1
    if entry_idx >= len(candles):
        return None, "no_entry_after_impulse"

    entry = candles[entry_idx].open
    min_stop_distance = entry * 0.001
    if direction == "LONG":
        stop = min(level - config.stop_atr_beyond_level * atr, entry - min_stop_distance)
        stop_distance = entry - stop
        target = entry + stop_distance * config.target_r
    else:
        stop = max(level + config.stop_atr_beyond_level * atr, entry + min_stop_distance)
        stop_distance = stop - entry
        target = entry - stop_distance * config.target_r

    return RetestSignal(
        symbol=symbol,
        config_id=config.config_id,
        direction=direction,
        sweep_side=sweep_side,
        trigger_idx=idx,
        retest_idx=retest_idx,
        impulse_idx=impulse_idx,
        entry_idx=entry_idx,
        trigger_time=candles[idx].open_time,
        retest_time=candles[retest_idx].open_time,
        impulse_time=candles[impulse_idx].open_time,
        entry_time=candles[entry_idx].open_time,
        level=level,
        entry_price=entry,
        stop_price=stop,
        target_price=target,
        atr=atr,
        sweep_depth_pct=depth,
        trigger_tfi=trigger_tfi,
        retest_tfi=tfi_by_time.get(candles[retest_idx].open_time, 0.0),
        impulse_tfi=tfi_by_time.get(candles[impulse_idx].open_time, 0.0),
    ), "candidate"


def simulate_trade(candles: list[Candle], signal: RetestSignal, max_hold_bars: int) -> RetestTrade:
    future = candles[signal.entry_idx : min(len(candles), signal.entry_idx + max_hold_bars)]
    if not future:
        raise ValueError("Cannot simulate trade without future candles.")
    direction_mult = 1.0 if signal.direction == "LONG" else -1.0
    stop_distance = abs(signal.entry_price - signal.stop_price)
    exit_price = future[-1].close
    exit_time = future[-1].open_time
    exit_idx = signal.entry_idx + len(future) - 1
    exit_reason = "TIMEOUT"
    mfe_r = 0.0
    mae_r = 0.0
    for offset, candle in enumerate(future):
        favourable = candle.high - signal.entry_price if signal.direction == "LONG" else signal.entry_price - candle.low
        adverse = signal.entry_price - candle.low if signal.direction == "LONG" else candle.high - signal.entry_price
        mfe_r = max(mfe_r, favourable / stop_distance)
        mae_r = max(mae_r, adverse / stop_distance)
        hit_stop = candle.low <= signal.stop_price if signal.direction == "LONG" else candle.high >= signal.stop_price
        hit_target = candle.high >= signal.target_price if signal.direction == "LONG" else candle.low <= signal.target_price
        if hit_stop:
            exit_price = signal.stop_price
            exit_reason = "SL"
        elif hit_target:
            exit_price = signal.target_price
            exit_reason = "TP"
        if hit_stop or hit_target:
            exit_time = candle.open_time
            exit_idx = signal.entry_idx + offset
            break
    gross_r = ((exit_price - signal.entry_price) * direction_mult) / stop_distance
    cost_r = cost_in_r(entry=signal.entry_price, exit_price=exit_price, stop_distance=stop_distance)
    return RetestTrade(signal, exit_idx, exit_time, exit_price, gross_r, gross_r - cost_r, cost_r, exit_reason, mfe_r, mae_r)


def summarize_trades(trades: list[RetestTrade], *, use_net: bool = True) -> dict[str, Any]:
    values = [trade.net_pnl_r if use_net else trade.gross_pnl_r for trade in trades]
    if not values:
        return {"trades": 0, "expectancy_r": 0.0, "pnl_r": 0.0, "win_rate": 0.0, "profit_factor": 0.0, "median_r": 0.0, "avg_cost_r": 0.0, "max_drawdown_r": 0.0}
    wins = [value for value in values if value > 0]
    losses = [value for value in values if value < 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    for value in values:
        equity += value
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
    return {
        "trades": len(values),
        "expectancy_r": round(mean(values), 4),
        "pnl_r": round(sum(values), 4),
        "win_rate": round(len(wins) / len(values), 4),
        "profit_factor": round(gross_profit / gross_loss, 4) if gross_loss else 999.0,
        "median_r": round(median(values), 4),
        "avg_cost_r": round(mean([trade.cost_r for trade in trades]), 4),
        "max_drawdown_r": round(max_dd, 4),
    }


def summarize_by(trades: list[RetestTrade], key_fn) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[RetestTrade]] = defaultdict(list)
    for trade in trades:
        grouped[str(key_fn(trade))].append(trade)
    return {key: summarize_trades(items) for key, items in sorted(grouped.items())}


def configs() -> list[RetestConfig]:
    base = {
        "equal_level_lookback": 50,
        "equal_level_tol_atr": 0.25,
        "min_hits": 3,
        "min_age_bars": 5,
        "atr_period": 14,
        "sweep_buf_atr": 0.15,
        "proximity_atr": 0.40,
        "reclaim_buf_atr": 0.07,
        "acceptance_buf_atr": 0.05,
        "stop_atr_beyond_level": 0.75,
        "target_r": 2.0,
        "max_hold_bars": 48,
    }
    return [
        RetestConfig(config_id="SARC_LIVE_8B", min_sweep_depth_pct=0.00649, retest_window_bars=8, **base),
        RetestConfig(config_id="SARC_LIVE_12B", min_sweep_depth_pct=0.00649, retest_window_bars=12, **base),
        RetestConfig(config_id="SARC_LIVE_LONG_8B", min_sweep_depth_pct=0.00649, retest_window_bars=8, directions=("LONG",), **base),
        RetestConfig(config_id="SARC_LIVE_LONG_TFI_8B", min_sweep_depth_pct=0.00649, tfi_abs_min=0.10, retest_window_bars=8, directions=("LONG",), **base),
        RetestConfig(config_id="SARC_NEARMISS_8B", min_sweep_depth_pct=0.0045, retest_window_bars=8, **base),
        RetestConfig(config_id="SARC_NEARMISS_LONG_8B", min_sweep_depth_pct=0.0045, retest_window_bars=8, directions=("LONG",), **base),
        RetestConfig(config_id="SARC_STRICT_HOLD_LONG", min_sweep_depth_pct=0.00649, retest_window_bars=8, max_reentry_atr=0.05, impulse_buf_atr=0.10, tfi_abs_min=0.10, directions=("LONG",), **base),
        RetestConfig(config_id="SARC_WIDE_RETEST_LONG", min_sweep_depth_pct=0.00649, retest_window_bars=12, retest_tolerance_atr=0.40, directions=("LONG",), **base),
    ]


def run_config(candles: list[Candle], tfi_by_time: dict[datetime, float], *, symbol: str, config: RetestConfig) -> ConfigRun:
    run = ConfigRun(config=config)
    idx = max(config.equal_level_lookback, config.atr_period + 1)
    while idx < len(candles) - 2:
        run.bars_evaluated += 1
        accepted, acceptance_reason = _acceptance_candidate(candles, tfi_by_time, idx, config=config)
        if accepted is None:
            run.rejection_reasons[acceptance_reason] += 1
            idx += 1
            continue
        run.acceptance_candidates += 1
        signal, reason = maybe_signal(candles, tfi_by_time, idx, symbol=symbol, config=config)
        if signal is None:
            run.rejection_reasons[reason] += 1
            idx += 1
            continue
        run.retest_candidates += 1
        run.impulse_candidates += 1
        trade = simulate_trade(candles, signal, config.max_hold_bars)
        run.trades.append(trade)
        idx = trade.exit_idx + 1
    return run


def run_analysis(*, db_path: Path, symbol: str, start: datetime, end: datetime) -> dict[str, Any]:
    with sqlite3.connect(db_path) as conn:
        candles = load_candles(conn, symbol=symbol, timeframe="15m", start=start, end=end)
        tfi_by_time = load_tfi_15m(conn, symbol=symbol, start=start, end=end)
    runs = [run_config(candles, tfi_by_time, symbol=symbol, config=config) for config in configs()]
    payload_runs: list[dict[str, Any]] = []
    for run in runs:
        trades = run.trades
        payload_runs.append({
            "config": asdict(run.config),
            "bars_evaluated": run.bars_evaluated,
            "acceptance_candidates": run.acceptance_candidates,
            "retest_impulse_candidates": run.impulse_candidates,
            "rejection_reasons": dict(run.rejection_reasons.most_common(20)),
            "gross_metrics": summarize_trades(trades, use_net=False),
            "net_metrics": summarize_trades(trades, use_net=True),
            "by_direction": summarize_by(trades, lambda trade: trade.signal.direction),
            "by_year_month": summarize_by(trades, lambda trade: trade.signal.entry_time.strftime("%Y-%m")),
            "sample_trades": [
                {
                    "trigger_time": trade.signal.trigger_time.isoformat(),
                    "retest_time": trade.signal.retest_time.isoformat(),
                    "impulse_time": trade.signal.impulse_time.isoformat(),
                    "entry_time": trade.signal.entry_time.isoformat(),
                    "direction": trade.signal.direction,
                    "sweep_depth_pct": round(trade.signal.sweep_depth_pct, 6),
                    "trigger_tfi": round(trade.signal.trigger_tfi, 4),
                    "retest_tfi": round(trade.signal.retest_tfi, 4),
                    "impulse_tfi": round(trade.signal.impulse_tfi, 4),
                    "exit_reason": trade.exit_reason,
                    "net_pnl_r": round(trade.net_pnl_r, 4),
                    "cost_r": round(trade.cost_r, 4),
                }
                for trade in trades[:20]
            ],
        })
    return {
        "milestone": "SWEEP-ACCEPTANCE-RETEST-CONTINUATION-RESEARCH-V1",
        "source_db_path": str(db_path),
        "symbol": symbol,
        "timeframe": "15m",
        "date_range": {"start": start.date().isoformat(), "end": end.date().isoformat()},
        "candles_loaded": len(candles),
        "tfi_buckets_loaded": len(tfi_by_time),
        "cost_model": {"entry_fee": "taker", "exit_fee": "maker", "maker_fee_pct": MAKER_FEE_PCT, "taker_fee_pct": TAKER_FEE_PCT, "slippage_bps_per_side": SLIPPAGE_BPS_PER_SIDE, "funding": "excluded_first_pass"},
        "methodology": {"setup": "sweep acceptance without reclaim, retest/hold of swept level, second impulse entry", "lookahead": "levels use prior bars; entry is next open after impulse close", "exit": "SL before TP when both touched in same candle"},
        "runs": payload_runs,
    }


def render_report(payload: dict[str, Any]) -> str:
    lines = [
        "# Sweep Acceptance Retest Continuation Feasibility",
        "",
        "Research-only checkpoint for `acceptance -> retest -> hold -> second impulse` after a sweep without reclaim.",
        "",
        "## Method",
        "",
        f"- Symbol: `{payload['symbol']}`",
        f"- Timeframe: `{payload['timeframe']}`",
        f"- Date range: `{payload['date_range']['start']}` to `{payload['date_range']['end']}`",
        f"- Candles loaded: `{payload['candles_loaded']}`",
        f"- TFI buckets loaded: `{payload['tfi_buckets_loaded']}`",
        "- Costs: taker entry, maker exit, 3 bps slippage per side; funding excluded in this first pass.",
        "",
        "## Results",
        "",
        "| Config | Trades | Net ER | Net PnL R | Net PF | Win Rate | Median R | Avg Cost R | Max DD R | Acceptance | Retest+Impulse |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for run in payload["runs"]:
        metrics = run["net_metrics"]
        lines.append(
            f"| `{run['config']['config_id']}` | {metrics['trades']} | {metrics['expectancy_r']:.4f} | {metrics['pnl_r']:.2f} | "
            f"{metrics['profit_factor']:.2f} | {metrics['win_rate']:.2%} | {metrics['median_r']:.4f} | {metrics['avg_cost_r']:.4f} | "
            f"{metrics['max_drawdown_r']:.2f} | {run['acceptance_candidates']} | {run['retest_impulse_candidates']} |"
        )
    best_run = max(payload["runs"], key=lambda item: item["net_metrics"]["expectancy_r"])
    lines.extend(["", f"## Best Variant Direction Split: `{best_run['config']['config_id']}`", "", "| Direction | Trades | Net ER | Net PnL R | Net PF | Win Rate | Median R |", "|---|---:|---:|---:|---:|---:|---:|"])
    for direction, metrics in best_run["by_direction"].items():
        lines.append(f"| `{direction}` | {metrics['trades']} | {metrics['expectancy_r']:.4f} | {metrics['pnl_r']:.2f} | {metrics['profit_factor']:.2f} | {metrics['win_rate']:.2%} | {metrics['median_r']:.4f} |")
    lines.extend(["", "## Interpretation", "", "- This is stricter than simple no-reclaim continuation: it waits for market acceptance to be retested and confirmed by a second impulse.", "- If this remains negative, the 2026-05-25 BTC move should be treated as an understandable miss, not a reason to weaken sweep-reclaim.", "- Promotion would require multi-asset net-cost parity and walk-forward validation."])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--start", default="2022-01-01")
    parser.add_argument("--end", default="2026-03-29")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT_PATH)
    args = parser.parse_args()
    start = parse_ts(args.start)
    end = parse_ts(args.end)
    if "T" not in args.end and " " not in args.end:
        end = end.replace(hour=23, minute=59, second=59)
    payload = run_analysis(db_path=args.db_path, symbol=args.symbol.upper(), start=start, end=end)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    args.report.write_text(render_report(payload), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "report": str(args.report), "runs": [{"config_id": run["config"]["config_id"], "trades": run["net_metrics"]["trades"], "net_expectancy_r": run["net_metrics"]["expectancy_r"], "net_profit_factor": run["net_metrics"]["profit_factor"]} for run in payload["runs"]]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
