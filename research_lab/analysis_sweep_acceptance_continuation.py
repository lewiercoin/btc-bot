#!/usr/bin/env python3
"""Offline sweep-acceptance continuation feasibility study.

This research checkpoint tests the setup that live sweep-reclaim intentionally
does not trade:

    HIGH sweep + no reclaim + close accepted above level -> LONG continuation
    LOW sweep + no reclaim + close accepted below level -> SHORT continuation

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
from typing import Any, Iterable


DEFAULT_DB_PATH = Path("research_lab/data/crowded_unwind_backtest.db")
DEFAULT_OUTPUT_PATH = Path("research_lab/analysis_output/sweep_acceptance_continuation_20220101_20260329.json")
DEFAULT_REPORT_PATH = Path("research_lab/reports/sweep_acceptance_continuation_feasibility_20220101_20260329.md")

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
class AcceptanceConfig:
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
    wick_min_atr: float = 0.20
    min_sweep_depth_pct: float = 0.00649
    tfi_abs_min: float | None = None
    entry_mode: str = "next_open"
    pullback_max_bars: int = 8
    pullback_tolerance_atr: float = 0.25
    stop_atr_beyond_level: float = 0.75
    target_r: float = 2.0
    max_hold_bars: int = 48
    directions: tuple[str, ...] = ("LONG", "SHORT")


@dataclass(frozen=True, slots=True)
class AcceptanceSignal:
    symbol: str
    config_id: str
    direction: str
    sweep_side: str
    trigger_idx: int
    entry_idx: int
    trigger_time: datetime
    entry_time: datetime
    level: float
    entry_price: float
    stop_price: float
    target_price: float
    atr: float
    sweep_depth_pct: float
    tfi_15m: float
    entry_mode: str


@dataclass(frozen=True, slots=True)
class AcceptanceTrade:
    signal: AcceptanceSignal
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
    config: AcceptanceConfig
    bars_evaluated: int = 0
    candidates_before_entry: int = 0
    trades: list[AcceptanceTrade] = field(default_factory=list)
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
        Candle(parse_ts(row[0]), float(row[1]), float(row[2]), float(row[3]), float(row[4]), float(row[5]))
        for row in rows
    ]


def load_tfi_15m(
    conn: sqlite3.Connection,
    *,
    symbol: str,
    start: datetime,
    end: datetime,
) -> dict[datetime, float]:
    rows = conn.execute(
        """
        SELECT bucket_time, tfi
        FROM aggtrade_buckets
        WHERE symbol = ? AND timeframe = '15m'
          AND bucket_time >= ? AND bucket_time <= ?
        ORDER BY bucket_time ASC
        """,
        (symbol, start.isoformat(), end.isoformat()),
    ).fetchall()
    return {parse_ts(row[0]): float(row[1]) for row in rows}


def _mean(values: Iterable[float]) -> float:
    items = list(values)
    return sum(items) / len(items) if items else 0.0


def compute_atr(candles: list[Candle], period: int) -> float:
    if len(candles) < 2:
        return 0.0
    true_ranges: list[float] = []
    for idx in range(1, len(candles)):
        candle = candles[idx]
        prev_close = candles[idx - 1].close
        true_ranges.append(max(candle.high - candle.low, abs(candle.high - prev_close), abs(candle.low - prev_close)))
    window = true_ranges[-period:] if len(true_ranges) >= period else true_ranges
    return _mean(window)


def detect_equal_levels(
    levels: list[tuple[int, float]],
    *,
    tolerance: float,
    min_hits: int,
    min_age_bars: int,
) -> list[float]:
    if not levels:
        return []
    sorted_levels = sorted(levels, key=lambda item: item[1])
    clusters: list[list[tuple[int, float]]] = [[sorted_levels[0]]]
    for item in sorted_levels[1:]:
        if abs(item[1] - clusters[-1][-1][1]) <= tolerance:
            clusters[-1].append(item)
        else:
            clusters.append([item])
    output: list[float] = []
    for cluster in clusters:
        if len(cluster) < min_hits:
            continue
        indices = [idx for idx, _ in cluster]
        if max(indices) - min(indices) < min_age_bars:
            continue
        output.append(round(_mean(price for _, price in cluster), 2))
    return output


def cost_in_r(*, entry: float, exit_price: float, stop_distance: float) -> float:
    if stop_distance <= 0:
        return 0.0
    slippage_pct = SLIPPAGE_BPS_PER_SIDE / 10_000.0
    entry_cost = entry * (TAKER_FEE_PCT + slippage_pct)
    exit_cost = exit_price * (MAKER_FEE_PCT + slippage_pct)
    return (entry_cost + exit_cost) / stop_distance


def _tfi_pass(direction: str, tfi: float, threshold: float | None) -> bool:
    if threshold is None:
        return True
    if direction == "LONG":
        return tfi >= threshold
    return tfi <= -threshold


def _entry_from_pullback(
    candles: list[Candle],
    *,
    trigger_idx: int,
    direction: str,
    level: float,
    atr: float,
    config: AcceptanceConfig,
) -> int | None:
    end_idx = min(len(candles) - 1, trigger_idx + config.pullback_max_bars)
    tolerance = config.pullback_tolerance_atr * atr
    for idx in range(trigger_idx + 1, end_idx + 1):
        candle = candles[idx]
        if direction == "LONG":
            touched = candle.low <= level + tolerance
            held = candle.close >= level
        else:
            touched = candle.high >= level - tolerance
            held = candle.close <= level
        if touched and held and idx + 1 < len(candles):
            return idx + 1
    return None


def maybe_signal(
    candles: list[Candle],
    tfi_by_time: dict[datetime, float],
    idx: int,
    *,
    symbol: str,
    config: AcceptanceConfig,
) -> tuple[AcceptanceSignal | None, str]:
    if idx + 1 >= len(candles):
        return None, "no_future_entry_bar"
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
    tfi = tfi_by_time.get(trigger.open_time, 0.0)

    detected: tuple[str, str, float, float] | None = None
    for level in equal_highs:
        if abs(trigger.open - level) > proximity:
            continue
        swept = trigger.high > level + sweep_buffer
        reclaimed = trigger.close < level - reclaim_buffer and (trigger.high - body_high) >= wick_min
        accepted = trigger.close > level + acceptance_buffer
        if swept and not reclaimed and accepted:
            depth = abs(trigger.high - level) / level if level else 0.0
            detected = ("LONG", "HIGH", level, depth)
            break

    if detected is None:
        for level in equal_lows:
            if abs(trigger.open - level) > proximity:
                continue
            swept = trigger.low < level - sweep_buffer
            reclaimed = trigger.close > level + reclaim_buffer and (body_low - trigger.low) >= wick_min
            accepted = trigger.close < level - acceptance_buffer
            if swept and not reclaimed and accepted:
                depth = abs(level - trigger.low) / level if level else 0.0
                detected = ("SHORT", "LOW", level, depth)
                break

    if detected is None:
        return None, "no_sweep_acceptance"

    direction, sweep_side, level, depth = detected
    if direction not in config.directions:
        return None, "direction_filtered"
    if depth < config.min_sweep_depth_pct:
        return None, "sweep_too_shallow"
    if not _tfi_pass(direction, tfi, config.tfi_abs_min):
        return None, "tfi_not_confirmed"

    if config.entry_mode == "next_open":
        entry_idx = idx + 1
    elif config.entry_mode == "pullback_hold":
        entry_idx = _entry_from_pullback(
            candles,
            trigger_idx=idx,
            direction=direction,
            level=level,
            atr=atr,
            config=config,
        )
        if entry_idx is None:
            return None, "no_pullback_hold_entry"
    else:
        raise ValueError(f"Unsupported entry_mode: {config.entry_mode}")

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

    return AcceptanceSignal(
        symbol=symbol,
        config_id=config.config_id,
        direction=direction,
        sweep_side=sweep_side,
        trigger_idx=idx,
        entry_idx=entry_idx,
        trigger_time=trigger.open_time,
        entry_time=candles[entry_idx].open_time,
        level=level,
        entry_price=entry,
        stop_price=stop,
        target_price=target,
        atr=atr,
        sweep_depth_pct=depth,
        tfi_15m=tfi,
        entry_mode=config.entry_mode,
    ), "candidate"


def simulate_trade(candles: list[Candle], signal: AcceptanceSignal, max_hold_bars: int) -> AcceptanceTrade:
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
    return AcceptanceTrade(
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


def summarize_trades(trades: list[AcceptanceTrade], *, use_net: bool = True) -> dict[str, Any]:
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


def summarize_by(trades: list[AcceptanceTrade], key_fn) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[AcceptanceTrade]] = defaultdict(list)
    for trade in trades:
        grouped[str(key_fn(trade))].append(trade)
    return {key: summarize_trades(items) for key, items in sorted(grouped.items())}


def configs() -> list[AcceptanceConfig]:
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
        "wick_min_atr": 0.20,
        "stop_atr_beyond_level": 0.75,
        "target_r": 2.0,
        "max_hold_bars": 48,
    }
    return [
        AcceptanceConfig(config_id="SAC_LIVE_DEPTH_NEXT_OPEN", min_sweep_depth_pct=0.00649, entry_mode="next_open", **base),
        AcceptanceConfig(config_id="SAC_LIVE_DEPTH_PULLBACK_HOLD", min_sweep_depth_pct=0.00649, entry_mode="pullback_hold", **base),
        AcceptanceConfig(config_id="SAC_NEARMISS_NEXT_OPEN", min_sweep_depth_pct=0.0045, entry_mode="next_open", **base),
        AcceptanceConfig(config_id="SAC_NEARMISS_PULLBACK_HOLD", min_sweep_depth_pct=0.0045, entry_mode="pullback_hold", **base),
        AcceptanceConfig(config_id="SAC_NEARMISS_TFI_PULLBACK", min_sweep_depth_pct=0.0045, tfi_abs_min=0.18, entry_mode="pullback_hold", **base),
        AcceptanceConfig(config_id="SAC_LIVE_DEPTH_LONG_ONLY", min_sweep_depth_pct=0.00649, entry_mode="next_open", directions=("LONG",), **base),
        AcceptanceConfig(config_id="SAC_LIVE_DEPTH_LONG_TFI", min_sweep_depth_pct=0.00649, tfi_abs_min=0.18, entry_mode="next_open", directions=("LONG",), **base),
        AcceptanceConfig(
            config_id="SAC_STRICT_TFI_PULLBACK",
            min_sweep_depth_pct=0.00649,
            tfi_abs_min=0.18,
            entry_mode="pullback_hold",
            target_r=2.5,
            max_hold_bars=64,
            **{k: v for k, v in base.items() if k not in {"target_r", "max_hold_bars"}},
        ),
    ]


def run_config(
    candles: list[Candle],
    tfi_by_time: dict[datetime, float],
    *,
    symbol: str,
    config: AcceptanceConfig,
) -> ConfigRun:
    run = ConfigRun(config=config)
    idx = max(config.equal_level_lookback, config.atr_period + 1)
    while idx < len(candles) - 1:
        run.bars_evaluated += 1
        signal, reason = maybe_signal(candles, tfi_by_time, idx, symbol=symbol, config=config)
        if signal is None:
            run.rejection_reasons[reason] += 1
            idx += 1
            continue
        run.candidates_before_entry += 1
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
            "candidates_before_entry": run.candidates_before_entry,
            "rejection_reasons": dict(run.rejection_reasons.most_common(20)),
            "gross_metrics": summarize_trades(trades, use_net=False),
            "net_metrics": summarize_trades(trades, use_net=True),
            "by_direction": summarize_by(trades, lambda trade: trade.signal.direction),
            "by_sweep_side": summarize_by(trades, lambda trade: trade.signal.sweep_side),
            "by_year_month": summarize_by(trades, lambda trade: trade.signal.entry_time.strftime("%Y-%m")),
            "sample_trades": [
                {
                    "trigger_time": trade.signal.trigger_time.isoformat(),
                    "entry_time": trade.signal.entry_time.isoformat(),
                    "direction": trade.signal.direction,
                    "sweep_side": trade.signal.sweep_side,
                    "sweep_depth_pct": round(trade.signal.sweep_depth_pct, 6),
                    "tfi_15m": round(trade.signal.tfi_15m, 4),
                    "exit_reason": trade.exit_reason,
                    "gross_pnl_r": round(trade.gross_pnl_r, 4),
                    "net_pnl_r": round(trade.net_pnl_r, 4),
                    "cost_r": round(trade.cost_r, 4),
                }
                for trade in trades[:20]
            ],
        })

    return {
        "milestone": "SWEEP-ACCEPTANCE-CONTINUATION-RESEARCH-V1",
        "source_db_path": str(db_path),
        "symbol": symbol,
        "timeframe": "15m",
        "date_range": {"start": start.date().isoformat(), "end": end.date().isoformat()},
        "candles_loaded": len(candles),
        "tfi_buckets_loaded": len(tfi_by_time),
        "cost_model": {
            "entry_fee": "taker",
            "exit_fee": "maker",
            "maker_fee_pct": MAKER_FEE_PCT,
            "taker_fee_pct": TAKER_FEE_PCT,
            "slippage_bps_per_side": SLIPPAGE_BPS_PER_SIDE,
            "funding": "excluded_first_pass",
        },
        "methodology": {
            "setup": "sweep without reclaim, then close accepted beyond swept level in continuation direction",
            "entry_modes": {
                "next_open": "enter next 15m open after acceptance close",
                "pullback_hold": "wait up to N bars for retest/hold of swept level, then enter next open",
            },
            "lookahead": "equal levels use prior bars only; entry uses future only after trigger is known",
            "exit": "SL before TP if both touched in same candle; timeout after max_hold_bars",
        },
        "runs": payload_runs,
    }


def render_report(payload: dict[str, Any]) -> str:
    lines = [
        "# Sweep Acceptance Continuation Feasibility",
        "",
        "Research-only checkpoint for the missing setup observed in production: sweep without reclaim followed by acceptance beyond the swept level.",
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
        "| Config | Trades | Net ER | Net PnL R | Net PF | Win Rate | Median R | Avg Cost R | Max DD R | Candidates |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for run in payload["runs"]:
        metrics = run["net_metrics"]
        lines.append(
            f"| `{run['config']['config_id']}` | {metrics['trades']} | {metrics['expectancy_r']:.4f} | "
            f"{metrics['pnl_r']:.2f} | {metrics['profit_factor']:.2f} | {metrics['win_rate']:.2%} | "
            f"{metrics['median_r']:.4f} | {metrics['avg_cost_r']:.4f} | {metrics['max_drawdown_r']:.2f} | "
            f"{run['candidates_before_entry']} |"
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
        "- This is a different setup from sweep-reclaim. It treats failure to reclaim as acceptance, not as a false breakout.",
        "- Immediate entries and pullback-hold entries are separated because impulse closes often retrace before any continuation.",
        "- This checkpoint is a feasibility screen only. Promotion would require multi-asset, net-cost parity and walk-forward validation.",
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
