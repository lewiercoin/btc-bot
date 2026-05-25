#!/usr/bin/env python3
"""Offline BTC breakout/momentum CHOP feasibility study.

Research-only script. It does not import or modify runtime decision layers.
The goal is to test whether Choppiness Index is useful as a regime filter for
simple 15m high/low breakout continuation, not to promote a live strategy.
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
import math
import sqlite3
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any


DEFAULT_DB_PATH = Path("research_lab/data/crowded_unwind_backtest.db")
DEFAULT_OUTPUT_PATH = Path("research_lab/analysis_output/breakout_momentum_chop_20220101_20260329.json")
DEFAULT_REPORT_PATH = Path("research_lab/reports/breakout_momentum_chop_feasibility_20220101_20260329.md")

MAKER_FEE_PCT = 0.0002
TAKER_FEE_PCT = 0.0005
SLIPPAGE_BPS_PER_SIDE = 3.0


@dataclass(frozen=True, slots=True)
class Candle:
    open_time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True, slots=True)
class BreakoutConfig:
    config_id: str
    breakout_lookback_bars: int
    atr_period: int
    chop_period: int
    min_breakout_atr: float
    stop_atr: float
    target_r: float
    max_hold_bars: int
    chop_max: float | None = None
    directions: tuple[str, ...] = ("LONG", "SHORT")


@dataclass(frozen=True, slots=True)
class BreakoutSignal:
    symbol: str
    config_id: str
    direction: str
    trigger_idx: int
    entry_idx: int
    trigger_time: datetime
    entry_time: datetime
    entry_price: float
    stop_price: float
    target_price: float
    atr: float
    chop: float
    breakout_size_atr: float
    prior_high: float
    prior_low: float


@dataclass(frozen=True, slots=True)
class BreakoutTrade:
    signal: BreakoutSignal
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
    config: BreakoutConfig
    bars_evaluated: int = 0
    candidates: int = 0
    chop_rejections: int = 0
    trades: list[BreakoutTrade] = field(default_factory=list)
    rejection_reasons: Counter[str] = field(default_factory=Counter)


def parse_ts(raw: Any) -> datetime:
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
    parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def load_candles(
    conn: sqlite3.Connection,
    *,
    symbol: str,
    timeframe: str,
    start: datetime,
    end: datetime,
) -> list[Candle]:
    rows = conn.execute(
        """
        SELECT open_time, open, high, low, close, volume
        FROM candles
        WHERE symbol = ? AND timeframe = ?
          AND open_time >= ? AND open_time <= ?
        ORDER BY open_time ASC
        """,
        (symbol, timeframe, start.isoformat(), end.isoformat()),
    ).fetchall()
    return [
        Candle(
            open_time=parse_ts(row[0]),
            open=float(row[1]),
            high=float(row[2]),
            low=float(row[3]),
            close=float(row[4]),
            volume=float(row[5]),
        )
        for row in rows
    ]


def true_ranges(candles: list[Candle]) -> list[float]:
    if len(candles) < 2:
        return []
    ranges: list[float] = []
    for idx in range(1, len(candles)):
        prev_close = candles[idx - 1].close
        candle = candles[idx]
        ranges.append(max(candle.high - candle.low, abs(candle.high - prev_close), abs(candle.low - prev_close)))
    return ranges


def compute_atr(candles: list[Candle], period: int) -> float:
    ranges = true_ranges(candles)
    if not ranges:
        return 0.0
    window = ranges[-period:] if len(ranges) >= period else ranges
    return mean(window) if window else 0.0


def compute_choppiness(candles: list[Candle], period: int) -> float | None:
    """Return Choppiness Index for completed candles.

    CHOP = 100 * log10(sum(TR, n) / (max(high, n) - min(low, n))) / log10(n)
    Higher values mean range/chop. Lower values mean directional movement.
    """
    if period <= 1 or len(candles) < period + 1:
        return None
    window = candles[-period:]
    prior = candles[-period - 1 : -period]
    ranges = true_ranges([*prior, *window])
    if len(ranges) < period:
        return None
    high = max(candle.high for candle in window)
    low = min(candle.low for candle in window)
    denominator = high - low
    if denominator <= 0:
        return None
    ratio = sum(ranges[-period:]) / denominator
    if ratio <= 0:
        return None
    return 100.0 * math.log10(ratio) / math.log10(period)


def chop_bucket(chop: float | None) -> str:
    if chop is None:
        return "missing"
    if chop <= 38.2:
        return "low_trend"
    if chop >= 61.8:
        return "high_chop"
    return "mid"


def cost_in_r(*, entry: float, exit_price: float, stop_distance: float) -> float:
    if stop_distance <= 0:
        return 0.0
    slippage_pct = SLIPPAGE_BPS_PER_SIDE / 10_000.0
    entry_cost = entry * (TAKER_FEE_PCT + slippage_pct)
    exit_cost = exit_price * (MAKER_FEE_PCT + slippage_pct)
    return (entry_cost + exit_cost) / stop_distance


def maybe_signal(
    candles: list[Candle],
    idx: int,
    *,
    symbol: str,
    config: BreakoutConfig,
) -> BreakoutSignal | None:
    trigger = candles[idx]
    if idx + 1 >= len(candles):
        return None
    if idx < max(config.breakout_lookback_bars, config.atr_period + 1, config.chop_period + 1):
        return None

    prior_range = candles[idx - config.breakout_lookback_bars : idx]
    context = candles[max(0, idx - max(config.atr_period + 1, config.chop_period + 1)) : idx + 1]
    atr = compute_atr(context, config.atr_period)
    chop = compute_choppiness(context, config.chop_period)
    if atr <= 0 or chop is None:
        return None

    prior_high = max(candle.high for candle in prior_range)
    prior_low = min(candle.low for candle in prior_range)
    long_breakout_atr = (trigger.close - prior_high) / atr
    short_breakout_atr = (prior_low - trigger.close) / atr

    direction: str | None = None
    breakout_size_atr = 0.0
    if "LONG" in config.directions and long_breakout_atr >= config.min_breakout_atr:
        direction = "LONG"
        breakout_size_atr = long_breakout_atr
    elif "SHORT" in config.directions and short_breakout_atr >= config.min_breakout_atr:
        direction = "SHORT"
        breakout_size_atr = short_breakout_atr
    else:
        return None

    if config.chop_max is not None and chop > config.chop_max:
        return None

    entry = candles[idx + 1].open
    stop_distance = max(config.stop_atr * atr, entry * 0.001)
    if direction == "LONG":
        stop = entry - stop_distance
        target = entry + stop_distance * config.target_r
    else:
        stop = entry + stop_distance
        target = entry - stop_distance * config.target_r

    return BreakoutSignal(
        symbol=symbol,
        config_id=config.config_id,
        direction=direction,
        trigger_idx=idx,
        entry_idx=idx + 1,
        trigger_time=trigger.open_time,
        entry_time=candles[idx + 1].open_time,
        entry_price=entry,
        stop_price=stop,
        target_price=target,
        atr=atr,
        chop=chop,
        breakout_size_atr=breakout_size_atr,
        prior_high=prior_high,
        prior_low=prior_low,
    )


def simulate_trade(candles: list[Candle], signal: BreakoutSignal, max_hold_bars: int) -> BreakoutTrade:
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
        favourable = (candle.high - signal.entry_price) if signal.direction == "LONG" else (signal.entry_price - candle.low)
        adverse = (signal.entry_price - candle.low) if signal.direction == "LONG" else (candle.high - signal.entry_price)
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
    return BreakoutTrade(
        signal=signal,
        exit_idx=exit_idx,
        exit_time=exit_time,
        exit_price=exit_price,
        gross_pnl_r=gross_r,
        net_pnl_r=gross_r - cost_r,
        cost_r=cost_r,
        exit_reason=exit_reason,
        mfe_r=mfe_r,
        mae_r=mae_r,
    )


def summarize_trades(trades: list[BreakoutTrade], *, use_net: bool = True) -> dict[str, Any]:
    values = [trade.net_pnl_r if use_net else trade.gross_pnl_r for trade in trades]
    if not values:
        return {
            "trades": 0,
            "expectancy_r": 0.0,
            "pnl_r": 0.0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "median_r": 0.0,
            "avg_cost_r": 0.0,
            "max_drawdown_r": 0.0,
        }
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


def summarize_by(trades: list[BreakoutTrade], key_fn) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[BreakoutTrade]] = defaultdict(list)
    for trade in trades:
        grouped[str(key_fn(trade))].append(trade)
    return {key: summarize_trades(items) for key, items in sorted(grouped.items())}


def run_config(candles: list[Candle], *, symbol: str, config: BreakoutConfig) -> ConfigRun:
    run = ConfigRun(config=config)
    idx = max(config.breakout_lookback_bars, config.atr_period + 1, config.chop_period + 1)
    while idx < len(candles) - 1:
        run.bars_evaluated += 1
        raw_signal = maybe_signal(candles, idx, symbol=symbol, config=BreakoutConfig(
            config_id=config.config_id,
            breakout_lookback_bars=config.breakout_lookback_bars,
            atr_period=config.atr_period,
            chop_period=config.chop_period,
            min_breakout_atr=config.min_breakout_atr,
            stop_atr=config.stop_atr,
            target_r=config.target_r,
            max_hold_bars=config.max_hold_bars,
            chop_max=None,
            directions=config.directions,
        ))
        if raw_signal is None:
            run.rejection_reasons["no_breakout"] += 1
            idx += 1
            continue
        run.candidates += 1
        if config.chop_max is not None and raw_signal.chop > config.chop_max:
            run.chop_rejections += 1
            run.rejection_reasons["chop_above_max"] += 1
            idx += 1
            continue
        trade = simulate_trade(candles, raw_signal, config.max_hold_bars)
        run.trades.append(trade)
        idx = trade.exit_idx + 1
    return run


def configs() -> list[BreakoutConfig]:
    base = {
        "breakout_lookback_bars": 48,
        "atr_period": 14,
        "chop_period": 14,
        "min_breakout_atr": 0.25,
        "stop_atr": 1.4,
        "target_r": 2.0,
        "max_hold_bars": 32,
    }
    return [
        BreakoutConfig(config_id="BMO_BASE_NO_CHOP", **base),
        BreakoutConfig(config_id="BMO_CHOP_LOW_38_2", chop_max=38.2, **base),
        BreakoutConfig(config_id="BMO_CHOP_TREND_45", chop_max=45.0, **base),
        BreakoutConfig(config_id="BMO_LONG_ONLY_CHOP_45", chop_max=45.0, directions=("LONG",), **base),
        BreakoutConfig(config_id="BMO_SHORT_ONLY_CHOP_45", chop_max=45.0, directions=("SHORT",), **base),
        BreakoutConfig(
            config_id="BMO_STRICT_48_CHOP_45",
            breakout_lookback_bars=48,
            atr_period=14,
            chop_period=14,
            min_breakout_atr=0.50,
            stop_atr=1.4,
            target_r=2.0,
            max_hold_bars=32,
            chop_max=45.0,
        ),
        BreakoutConfig(
            config_id="BMO_STRONG_48_CHOP_45",
            breakout_lookback_bars=48,
            atr_period=14,
            chop_period=14,
            min_breakout_atr=0.75,
            stop_atr=1.2,
            target_r=2.5,
            max_hold_bars=48,
            chop_max=45.0,
        ),
        BreakoutConfig(
            config_id="BMO_STRUCT_96_CHOP_45",
            breakout_lookback_bars=96,
            atr_period=14,
            chop_period=14,
            min_breakout_atr=0.50,
            stop_atr=1.5,
            target_r=2.5,
            max_hold_bars=48,
            chop_max=45.0,
        ),
        BreakoutConfig(
            config_id="BMO_STRUCT_96_LOW_CHOP",
            breakout_lookback_bars=96,
            atr_period=14,
            chop_period=14,
            min_breakout_atr=0.50,
            stop_atr=1.5,
            target_r=2.5,
            max_hold_bars=48,
            chop_max=38.2,
        ),
    ]


def run_analysis(
    *,
    db_path: Path,
    symbol: str,
    start: datetime,
    end: datetime,
) -> dict[str, Any]:
    with sqlite3.connect(db_path) as conn:
        candles = load_candles(conn, symbol=symbol, timeframe="15m", start=start, end=end)

    runs = [run_config(candles, symbol=symbol, config=config) for config in configs()]
    payload_runs: list[dict[str, Any]] = []
    for run in runs:
        trades = run.trades
        payload_runs.append({
            "config": asdict(run.config),
            "bars_evaluated": run.bars_evaluated,
            "candidates_before_chop_filter": run.candidates,
            "chop_rejections": run.chop_rejections,
            "rejection_reasons": dict(run.rejection_reasons.most_common(20)),
            "gross_metrics": summarize_trades(trades, use_net=False),
            "net_metrics": summarize_trades(trades, use_net=True),
            "by_chop_bucket": summarize_by(trades, lambda trade: chop_bucket(trade.signal.chop)),
            "by_direction": summarize_by(trades, lambda trade: trade.signal.direction),
            "by_year_month": summarize_by(trades, lambda trade: trade.signal.entry_time.strftime("%Y-%m")),
            "sample_trades": [
                {
                    "entry_time": trade.signal.entry_time.isoformat(),
                    "direction": trade.signal.direction,
                    "chop": round(trade.signal.chop, 4),
                    "breakout_size_atr": round(trade.signal.breakout_size_atr, 4),
                    "exit_reason": trade.exit_reason,
                    "gross_pnl_r": round(trade.gross_pnl_r, 4),
                    "net_pnl_r": round(trade.net_pnl_r, 4),
                    "cost_r": round(trade.cost_r, 4),
                }
                for trade in trades[:20]
            ],
        })

    return {
        "milestone": "BREAKOUT-MOMENTUM-CHOP-RESEARCH-V1",
        "source_db_path": str(db_path),
        "symbol": symbol,
        "timeframe": "15m",
        "date_range": {"start": start.date().isoformat(), "end": end.date().isoformat()},
        "candles_loaded": len(candles),
        "cost_model": {
            "entry_fee": "taker",
            "exit_fee": "maker",
            "maker_fee_pct": MAKER_FEE_PCT,
            "taker_fee_pct": TAKER_FEE_PCT,
            "slippage_bps_per_side": SLIPPAGE_BPS_PER_SIDE,
            "funding": "excluded_first_pass",
        },
        "methodology": {
            "entry": "next_15m_open_after_breakout_close",
            "breakout": "close beyond prior N-bar high/low by min_breakout_atr",
            "exit": "SL before TP if both touched in same candle; timeout after max_hold_bars",
            "lookahead": "breakout level uses prior bars only; entry uses next bar open",
            "chop_interpretation": "low CHOP is directional/trending; high CHOP is choppy/ranging",
        },
        "runs": payload_runs,
    }


def render_report(payload: dict[str, Any]) -> str:
    lines = [
        "# Breakout/Momentum CHOP Feasibility",
        "",
        "Research-only checkpoint. This tests whether Choppiness Index improves a simple 15m breakout/momentum setup.",
        "",
        "## Method",
        "",
        f"- Symbol: `{payload['symbol']}`",
        f"- Timeframe: `{payload['timeframe']}`",
        f"- Date range: `{payload['date_range']['start']}` to `{payload['date_range']['end']}`",
        f"- Candles loaded: `{payload['candles_loaded']}`",
        "- Entry: next 15m open after a close breaks prior 48-bar high/low.",
        "- Costs: taker entry, maker exit, 3 bps slippage per side; funding excluded in this first pass.",
        "- CHOP meaning: low CHOP = directional/trending; high CHOP = range/chop.",
        "",
        "## Results",
        "",
        "| Config | Trades | Net ER | Net PnL R | Net PF | Win Rate | Median R | Avg Cost R | Max DD R | Candidates | CHOP Rejects |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for run in payload["runs"]:
        metrics = run["net_metrics"]
        lines.append(
            f"| `{run['config']['config_id']}` | {metrics['trades']} | {metrics['expectancy_r']:.4f} | "
            f"{metrics['pnl_r']:.2f} | {metrics['profit_factor']:.2f} | {metrics['win_rate']:.2%} | "
            f"{metrics['median_r']:.4f} | {metrics['avg_cost_r']:.4f} | {metrics['max_drawdown_r']:.2f} | "
            f"{run['candidates_before_chop_filter']} | {run['chop_rejections']} |"
        )

    base_run = next(run for run in payload["runs"] if run["config"]["config_id"] == "BMO_BASE_NO_CHOP")
    lines.extend([
        "",
        "## Base Run By CHOP Bucket",
        "",
        "| Bucket | Trades | Net ER | Net PnL R | Net PF | Win Rate | Median R |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ])
    for bucket, metrics in base_run["by_chop_bucket"].items():
        lines.append(
            f"| `{bucket}` | {metrics['trades']} | {metrics['expectancy_r']:.4f} | {metrics['pnl_r']:.2f} | "
            f"{metrics['profit_factor']:.2f} | {metrics['win_rate']:.2%} | {metrics['median_r']:.4f} |"
        )

    best_run = max(payload["runs"], key=lambda item: item["net_metrics"]["expectancy_r"])
    lines.extend([
        "",
        f"## Best Variant Direction Split: `{best_run['config']['config_id']}`",
        "",
        "| Direction | Trades | Net ER | Net PnL R | Net PF | Win Rate | Median R |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ])
    for direction, metrics in best_run["by_direction"].items():
        lines.append(
            f"| `{direction}` | {metrics['trades']} | {metrics['expectancy_r']:.4f} | {metrics['pnl_r']:.2f} | "
            f"{metrics['profit_factor']:.2f} | {metrics['win_rate']:.2%} | {metrics['median_r']:.4f} |"
        )

    lines.extend([
        "",
        "## Interpretation",
        "",
        "- CHOP is not a momentum signal by itself because it has no direction.",
        "- Its useful role is a regime filter: low CHOP can mark cleaner continuation conditions, while high CHOP can warn that breakout entries are likely to chop back.",
        "- This checkpoint should not be promoted. It is a feasibility screen for whether a proper breakout/momentum hypothesis deserves a stricter walk-forward study.",
    ])
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
    print(json.dumps({
        "output": str(args.output),
        "report": str(args.report),
        "runs": [
            {
                "config_id": run["config"]["config_id"],
                "trades": run["net_metrics"]["trades"],
                "net_expectancy_r": run["net_metrics"]["expectancy_r"],
                "net_profit_factor": run["net_metrics"]["profit_factor"],
            }
            for run in payload["runs"]
        ],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
