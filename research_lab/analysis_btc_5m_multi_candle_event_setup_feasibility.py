#!/usr/bin/env python3
"""
BTC 5m multi-candle event setup feasibility study.

Offline-only research script. It tests two 5m setup classes:

1. Compression fakeout reclaim
2. Crowded unwind reversal

The goal is more BTC trades without quality degradation. This script does not
modify production, PAPER, runtime, settings, core, or execution modules.
"""

from __future__ import annotations

import json
import math
import sqlite3
import subprocess
from bisect import bisect_right
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any

from research_lab.evaluators.gate_evaluator import Gate, evaluate_gates
from research_lab.experiments.api import create_experiment, list_experiments, record_result
from research_lab.experiments.manifest import compute_combined_manifest_hash, create_manifest


DB_5M = Path("research_lab/snapshots/btc_5m_2022_2026.db")
DB_REPLAY = Path("research_lab/snapshots/replay-run13-regime-aware-trial-00063.db")
DB_FORCE = Path("research_lab/data/crowded_unwind_backtest.db")
REGISTRY_PATH = Path("research_lab/experiments/experiments.db")
REPORT_PATH = Path("docs/analysis/BTC_5M_MULTI_CANDLE_EVENT_SETUP_FEASIBILITY_2026-05-15.md")
SYMBOL = "BTCUSDT"

ANALYSIS_START = datetime(2024, 1, 1, tzinfo=timezone.utc)
ANALYSIS_END = datetime(2026, 3, 28, tzinfo=timezone.utc)
LOOKBACK_START = ANALYSIS_START - timedelta(days=14)

BASELINE = {
    "trade_count": 47,
    "expectancy_r": 2.110,
    "profit_factor": 3.95,
    "win_rate": 51.1,
    "max_dd_r": 4.49,
    "avg_mae_r": -1.109,
    "avg_mfe_r": 6.220,
    "trades_per_month": 1.8,
}

FEE_RATE = 0.0004
SLIPPAGE_BPS = 3.0
MAX_HOLD_BARS = int(34 * 60 / 5)


@dataclass(frozen=True)
class Candle:
    open_time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

    @property
    def range(self) -> float:
        return max(self.high - self.low, 0.0)

    @property
    def body(self) -> float:
        return abs(self.close - self.open)

    @property
    def body_ratio(self) -> float:
        return self.body / self.range if self.range > 0 else 0.0


@dataclass(frozen=True)
class SetupVariant:
    setup_id: str
    variant_id: str
    params: dict[str, Any]


@dataclass(frozen=True)
class EventSignal:
    setup_id: str
    variant_id: str
    event_idx: int
    confirm_idx: int
    event_time: datetime
    entry_time: datetime
    direction: str
    entry_price: float
    stop_loss: float
    take_profit: float
    reason: str
    diagnostics: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EventTrade:
    signal: EventSignal
    exit_time: datetime
    exit_price: float
    pnl_r: float
    exit_reason: str
    mae_r: float
    mfe_r: float

    @property
    def entry_time(self) -> datetime:
        return self.signal.entry_time

    @property
    def direction(self) -> str:
        return self.signal.direction


@dataclass
class SetupRun:
    setup_id: str
    variant_id: str
    params: dict[str, Any]
    precondition_count: int = 0
    event_count: int = 0
    confirmation_count: int = 0
    raw_signal_count: int = 0
    overlap_skipped_count: int = 0
    trades: list[EventTrade] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    gate_verdict: str = "BLOCKED"
    gate_summary: str = ""
    gate_results: list[dict[str, Any]] = field(default_factory=list)


def _parse_ts(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value).replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def load_candles(path: Path, start: datetime, end: datetime) -> list[Candle]:
    with sqlite3.connect(path) as conn:
        rows = conn.execute(
            """
            SELECT open_time, open, high, low, close, volume
            FROM candles
            WHERE symbol = ? AND timeframe = '5m'
              AND open_time >= ? AND open_time <= ?
            ORDER BY open_time ASC
            """,
            (SYMBOL, start.isoformat(), end.isoformat()),
        ).fetchall()
    return [
        Candle(
            open_time=_parse_ts(row[0]),
            open=float(row[1]),
            high=float(row[2]),
            low=float(row[3]),
            close=float(row[4]),
            volume=float(row[5]),
        )
        for row in rows
    ]


def audit_data_availability() -> dict[str, Any]:
    audit: dict[str, Any] = {
        "db_5m_exists": DB_5M.exists(),
        "replay_db_exists": DB_REPLAY.exists(),
        "db_5m_tables": [],
        "replay_tables": [],
        "candles_5m_rows": 0,
        "oi_rows": 0,
        "funding_rows": 0,
        "force_order_rows": 0,
        "force_order_source": "",
        "force_order_start": "",
        "force_order_end": "",
        "aggtrade_rows": 0,
        "setup_b_data_mode": "UNKNOWN",
    }
    if DB_5M.exists():
        with sqlite3.connect(DB_5M) as conn:
            audit["db_5m_tables"] = [
                row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            ]
            audit["candles_5m_rows"] = conn.execute("SELECT COUNT(*) FROM candles").fetchone()[0]
    if DB_REPLAY.exists():
        with sqlite3.connect(DB_REPLAY) as conn:
            audit["replay_tables"] = [
                row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            ]
            if "open_interest" in audit["replay_tables"]:
                audit["oi_rows"] = conn.execute("SELECT COUNT(*) FROM open_interest").fetchone()[0]
            if "funding" in audit["replay_tables"]:
                audit["funding_rows"] = conn.execute("SELECT COUNT(*) FROM funding").fetchone()[0]
            if "force_orders" in audit["replay_tables"]:
                audit["force_order_rows"] = conn.execute("SELECT COUNT(*) FROM force_orders").fetchone()[0]
            if "aggtrade_buckets" in audit["replay_tables"]:
                audit["aggtrade_rows"] = conn.execute("SELECT COUNT(*) FROM aggtrade_buckets").fetchone()[0]
    if DB_FORCE.exists():
        with sqlite3.connect(DB_FORCE) as conn:
            tables = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
            if "force_orders" in tables:
                count, start, end = conn.execute(
                    "SELECT COUNT(*), MIN(event_time), MAX(event_time) FROM force_orders WHERE symbol = ?",
                    (SYMBOL,),
                ).fetchone()
                if count:
                    audit["force_order_rows"] = count
                    audit["force_order_source"] = str(DB_FORCE)
                    audit["force_order_start"] = start
                    audit["force_order_end"] = end
    if audit["oi_rows"] and audit["funding_rows"] and audit["force_order_rows"]:
        audit["setup_b_data_mode"] = "OI_FUNDING_FORCE_ORDERS"
    elif audit["oi_rows"] and audit["funding_rows"]:
        audit["setup_b_data_mode"] = "OI_FUNDING_WITH_CANDLE_VOLUME_PROXY"
    else:
        audit["setup_b_data_mode"] = "CANDLE_VOLUME_PROXY_ONLY"
    return audit


def load_oi_funding(path: Path) -> tuple[list[tuple[datetime, float]], list[tuple[datetime, float]]]:
    if not path.exists():
        return [], []
    with sqlite3.connect(path) as conn:
        oi = [
            (_parse_ts(row[0]), float(row[1]))
            for row in conn.execute(
                "SELECT timestamp, oi_value FROM open_interest WHERE symbol = ? ORDER BY timestamp ASC",
                (SYMBOL,),
            ).fetchall()
        ]
        funding = [
            (_parse_ts(row[0]), float(row[1]))
            for row in conn.execute(
                "SELECT funding_time, funding_rate FROM funding WHERE symbol = ? ORDER BY funding_time ASC",
                (SYMBOL,),
            ).fetchall()
        ]
    return oi, funding


def floor_to_5m(ts: datetime) -> datetime:
    minute = (ts.minute // 5) * 5
    return ts.replace(minute=minute, second=0, microsecond=0)


def load_force_order_buckets(path: Path) -> dict[datetime, dict[str, float]]:
    if not path.exists():
        return {}
    buckets: dict[datetime, dict[str, float]] = defaultdict(lambda: {"buy_notional": 0.0, "sell_notional": 0.0, "total_notional": 0.0})
    with sqlite3.connect(path) as conn:
        rows = conn.execute(
            """
            SELECT event_time, side, qty, price
            FROM force_orders
            WHERE symbol = ?
            ORDER BY event_time ASC
            """,
            (SYMBOL,),
        ).fetchall()
    for event_time, side, qty, price in rows:
        bucket_time = floor_to_5m(_parse_ts(event_time))
        notional = float(qty) * float(price)
        bucket = buckets[bucket_time]
        if str(side).upper() == "BUY":
            bucket["buy_notional"] += notional
        elif str(side).upper() == "SELL":
            bucket["sell_notional"] += notional
        bucket["total_notional"] += notional
    return dict(buckets)


def compute_range(candles: list[Candle], start: int, end: int) -> tuple[float, float]:
    if start < 0 or end <= start:
        raise ValueError("invalid range window")
    window = candles[start:end]
    if not window:
        raise ValueError("empty range window")
    return max(c.high for c in window), min(c.low for c in window)


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    pos = max(0, min(len(sorted_values) - 1, int(round((len(sorted_values) - 1) * q))))
    return sorted_values[pos]


def rolling_stats(candles: list[Candle], force_buckets: dict[datetime, dict[str, float]] | None = None) -> dict[str, list[float]]:
    atr: list[float] = [0.0] * len(candles)
    bb_width: list[float] = [0.0] * len(candles)
    vol_z: list[float] = [0.0] * len(candles)
    force_total: list[float] = [0.0] * len(candles)
    force_buy: list[float] = [0.0] * len(candles)
    force_sell: list[float] = [0.0] * len(candles)
    force_z: list[float] = [0.0] * len(candles)
    force_buckets = force_buckets or {}
    for i in range(len(candles)):
        force = force_buckets.get(candles[i].open_time, {})
        force_buy[i] = float(force.get("buy_notional", 0.0))
        force_sell[i] = float(force.get("sell_notional", 0.0))
        force_total[i] = float(force.get("total_notional", 0.0))
        if i >= 14:
            atr[i] = mean(c.range for c in candles[i - 14 : i])
        if i >= 20:
            closes = [c.close for c in candles[i - 20 : i]]
            avg = mean(closes)
            variance = mean((c - avg) ** 2 for c in closes)
            bb_width[i] = (4 * math.sqrt(variance) / avg) if avg else 0.0
        if i >= 20:
            vols = [c.volume for c in candles[i - 20 : i]]
            avg_vol = mean(vols)
            variance_vol = mean((v - avg_vol) ** 2 for v in vols)
            std_vol = math.sqrt(variance_vol)
            vol_z[i] = (candles[i].volume - avg_vol) / std_vol if std_vol > 0 else 0.0
        if i >= 288:
            past_force = force_total[i - 288 : i]
            avg_force = mean(past_force)
            variance_force = mean((v - avg_force) ** 2 for v in past_force)
            std_force = math.sqrt(variance_force)
            force_z[i] = (force_total[i] - avg_force) / std_force if std_force > 0 else 0.0
    return {
        "atr": atr,
        "bb_width": bb_width,
        "vol_z": vol_z,
        "force_total": force_total,
        "force_buy": force_buy,
        "force_sell": force_sell,
        "force_z": force_z,
    }


def is_compressed(bb_width: list[float], event_idx: int, lookback: int, threshold_quantile: float) -> bool:
    if event_idx < lookback + 20:
        return False
    history = [v for v in bb_width[event_idx - lookback : event_idx] if v > 0]
    if len(history) < max(20, lookback // 2):
        return False
    current = bb_width[event_idx - 1]
    return current > 0 and current <= percentile(history, threshold_quantile)


def find_reclaim_confirmation(
    candles: list[Candle],
    event_idx: int,
    window_bars: int,
    direction: str,
    range_high: float,
    range_low: float,
) -> int | None:
    range_mid = (range_high + range_low) / 2
    for idx in range(event_idx + 1, min(len(candles), event_idx + 1 + window_bars)):
        close = candles[idx].close
        if direction == "LONG" and close > range_mid:
            return idx
        if direction == "SHORT" and close < range_mid:
            return idx
    return None


def find_snapback_confirmation(
    candles: list[Candle],
    event_idx: int,
    window_bars: int,
    direction: str,
) -> int | None:
    event_mid = (candles[event_idx].high + candles[event_idx].low) / 2
    for idx in range(event_idx + 1, min(len(candles), event_idx + 1 + window_bars)):
        close = candles[idx].close
        if direction == "LONG" and close > event_mid:
            return idx
        if direction == "SHORT" and close < event_mid:
            return idx
    return None


def latest_value_before(series: list[tuple[datetime, float]], times: list[datetime], ts: datetime) -> float | None:
    idx = bisect_right(times, ts) - 1
    if idx < 0:
        return None
    return series[idx][1]


def is_crowded_context(
    ts: datetime,
    oi: list[tuple[datetime, float]],
    oi_times: list[datetime],
    funding: list[tuple[datetime, float]],
    funding_times: list[datetime],
    lookback_bars: int,
    volume_z: float,
) -> tuple[bool, dict[str, Any]]:
    current_oi = latest_value_before(oi, oi_times, ts)
    prior_oi = latest_value_before(oi, oi_times, ts - timedelta(minutes=5 * lookback_bars))
    funding_rate = latest_value_before(funding, funding_times, ts)
    oi_change_pct = None
    if current_oi is not None and prior_oi not in (None, 0):
        oi_change_pct = (current_oi - prior_oi) / prior_oi
    oi_rising = oi_change_pct is not None and oi_change_pct > 0.002
    funding_extreme = funding_rate is not None and abs(funding_rate) >= 0.0001
    volume_extreme = volume_z >= 2.0
    return (
        bool(oi_rising or funding_extreme or volume_extreme),
        {
            "oi_change_pct": oi_change_pct,
            "funding_rate": funding_rate,
            "volume_z": volume_z,
            "oi_rising": oi_rising,
            "funding_extreme": funding_extreme,
            "volume_extreme": volume_extreme,
        },
    )


def detect_compression_fakeout(
    candles: list[Candle],
    stats: dict[str, list[float]],
    variant: SetupVariant,
    start_idx: int,
    end_idx: int,
) -> SetupRun:
    params = variant.params
    run = SetupRun(variant.setup_id, variant.variant_id, dict(params))
    signals: list[EventSignal] = []
    compression_lookback = int(params["compression_lookback"])
    range_lookback = int(params["range_lookback"])
    reclaim_window = int(params["reclaim_window_bars"])
    threshold_quantile = float(params["bb_width_quantile"])

    for i in range(max(start_idx, compression_lookback + range_lookback + 20), end_idx):
        if not is_compressed(stats["bb_width"], i, compression_lookback, threshold_quantile):
            continue
        run.precondition_count += 1
        range_high, range_low = compute_range(candles, i - range_lookback, i)
        bar = candles[i]
        direction = None
        if bar.close > range_high:
            direction = "SHORT"
        elif bar.close < range_low:
            direction = "LONG"
        if direction is None:
            continue
        run.event_count += 1
        confirm_idx = find_reclaim_confirmation(candles, i, reclaim_window, direction, range_high, range_low)
        if confirm_idx is None:
            continue
        run.confirmation_count += 1
        event_low = min(c.low for c in candles[i : confirm_idx + 1])
        event_high = max(c.high for c in candles[i : confirm_idx + 1])
        range_width = range_high - range_low
        if range_width <= 0:
            continue
        entry = candles[confirm_idx].close
        atr = stats["atr"][i] or range_width
        if direction == "LONG":
            stop = event_low - 0.1 * atr
            tp = range_high
            if not (stop < entry < tp):
                continue
        else:
            stop = event_high + 0.1 * atr
            tp = range_low
            if not (tp < entry < stop):
                continue
        signals.append(
            EventSignal(
                setup_id=variant.setup_id,
                variant_id=variant.variant_id,
                event_idx=i,
                confirm_idx=confirm_idx,
                event_time=bar.open_time,
                entry_time=candles[confirm_idx].open_time + timedelta(minutes=5),
                direction=direction,
                entry_price=entry,
                stop_loss=stop,
                take_profit=tp,
                reason="compression_fakeout_reclaim",
                diagnostics={
                    "range_high": range_high,
                    "range_low": range_low,
                    "bb_width": stats["bb_width"][i - 1],
                    "volume_z": stats["vol_z"][i],
                },
            )
        )
    run.raw_signal_count = len(signals)
    run.trades, run.overlap_skipped_count = simulate_signals(candles, signals)
    return run


def detect_crowded_unwind(
    candles: list[Candle],
    stats: dict[str, list[float]],
    variant: SetupVariant,
    start_idx: int,
    end_idx: int,
    oi: list[tuple[datetime, float]],
    funding: list[tuple[datetime, float]],
) -> SetupRun:
    params = variant.params
    run = SetupRun(variant.setup_id, variant.variant_id, dict(params))
    signals: list[EventSignal] = []
    oi_times = [v[0] for v in oi]
    funding_times = [v[0] for v in funding]
    lookback = int(params["crowding_lookback_bars"])
    forced_mult = float(params["forced_move_atr_mult"])
    snapback_window = int(params["snapback_window_bars"])
    min_body_ratio = float(params["min_body_ratio"])
    min_volume_z = float(params["min_volume_z"])
    min_force_z = float(params["min_force_z"])

    for i in range(max(start_idx, lookback + 20), end_idx):
        atr = stats["atr"][i]
        if atr <= 0:
            continue
        crowded, context = is_crowded_context(
            candles[i].open_time,
            oi,
            oi_times,
            funding,
            funding_times,
            lookback,
            stats["vol_z"][i],
        )
        if not crowded:
            continue
        run.precondition_count += 1
        bar = candles[i]
        force_z = stats["force_z"][i]
        force_buy = stats["force_buy"][i]
        force_sell = stats["force_sell"][i]
        if force_z < min_force_z:
            continue
        if bar.range < atr * forced_mult or bar.body_ratio < min_body_ratio or stats["vol_z"][i] < min_volume_z:
            continue
        if bar.close > bar.open and force_buy >= force_sell:
            direction = "SHORT"
        elif bar.close < bar.open and force_sell >= force_buy:
            direction = "LONG"
        else:
            continue
        run.event_count += 1
        confirm_idx = find_snapback_confirmation(candles, i, snapback_window, direction)
        if confirm_idx is None:
            continue
        run.confirmation_count += 1
        entry = candles[confirm_idx].close
        event_range = bar.range
        if direction == "LONG":
            stop = min(c.low for c in candles[i : confirm_idx + 1]) - 0.1 * atr
            tp = bar.open
            if not (stop < entry < tp):
                continue
        else:
            stop = max(c.high for c in candles[i : confirm_idx + 1]) + 0.1 * atr
            tp = bar.open
            if not (tp < entry < stop):
                continue
        if abs(entry - tp) < 0.25 * event_range:
            continue
        signals.append(
            EventSignal(
                setup_id=variant.setup_id,
                variant_id=variant.variant_id,
                event_idx=i,
                confirm_idx=confirm_idx,
                event_time=bar.open_time,
                entry_time=candles[confirm_idx].open_time + timedelta(minutes=5),
                direction=direction,
                entry_price=entry,
                stop_loss=stop,
                take_profit=tp,
                reason="crowded_unwind_snapback",
                diagnostics=context
                | {
                    "atr": atr,
                    "body_ratio": bar.body_ratio,
                    "event_range": bar.range,
                    "force_z": force_z,
                    "force_buy_notional": force_buy,
                    "force_sell_notional": force_sell,
                },
            )
        )
    run.raw_signal_count = len(signals)
    run.trades, run.overlap_skipped_count = simulate_signals(candles, signals)
    return run


def simulate_signals(candles: list[Candle], signals: list[EventSignal]) -> tuple[list[EventTrade], int]:
    trades: list[EventTrade] = []
    skipped = 0
    next_available_idx = -1
    sorted_signals = sorted(signals, key=lambda s: (s.confirm_idx, s.event_idx))
    for signal in sorted_signals:
        if signal.confirm_idx <= next_available_idx:
            skipped += 1
            continue
        future = candles[signal.confirm_idx + 1 : signal.confirm_idx + 1 + MAX_HOLD_BARS]
        trade = simulate_trade(signal, future, FEE_RATE, SLIPPAGE_BPS)
        if trade is None:
            continue
        trades.append(trade)
        next_available_idx = signal.confirm_idx + min(MAX_HOLD_BARS, len(future))
        for offset, candle in enumerate(future):
            if candle.open_time == trade.exit_time:
                next_available_idx = signal.confirm_idx + 1 + offset
                break
    return trades, skipped


def simulate_trade(
    signal: EventSignal,
    future: list[Candle],
    fee_rate: float,
    slippage_bps: float,
) -> EventTrade | None:
    if not future:
        return None
    slip = signal.entry_price * slippage_bps / 10000
    if signal.direction == "LONG":
        entry = signal.entry_price + slip
    else:
        entry = signal.entry_price - slip
    stop = signal.stop_loss
    tp = signal.take_profit
    risk = abs(entry - stop)
    if risk <= 0:
        return None
    exit_price = entry
    exit_time = future[0].open_time
    exit_reason = "max_hold"
    mae = 0.0
    mfe = 0.0
    for candle in future:
        if signal.direction == "LONG":
            mae = min(mae, (candle.low - entry) / risk)
            mfe = max(mfe, (candle.high - entry) / risk)
            if candle.low <= stop:
                exit_price = stop - slip
                exit_time = candle.open_time
                exit_reason = "stop_loss"
                break
            if candle.high >= tp:
                exit_price = tp - slip
                exit_time = candle.open_time
                exit_reason = "take_profit"
                break
            exit_price = candle.close
        else:
            mae = min(mae, (entry - candle.high) / risk)
            mfe = max(mfe, (entry - candle.low) / risk)
            if candle.high >= stop:
                exit_price = stop + slip
                exit_time = candle.open_time
                exit_reason = "stop_loss"
                break
            if candle.low <= tp:
                exit_price = tp + slip
                exit_time = candle.open_time
                exit_reason = "take_profit"
                break
            exit_price = candle.close
        exit_time = candle.open_time
    raw_pnl = (exit_price - entry) if signal.direction == "LONG" else (entry - exit_price)
    fee_cost = entry * fee_rate + exit_price * fee_rate
    pnl_r = (raw_pnl - fee_cost) / risk
    return EventTrade(signal=signal, exit_time=exit_time, exit_price=exit_price, pnl_r=pnl_r, exit_reason=exit_reason, mae_r=mae, mfe_r=mfe)


def compute_metrics(trades: list[EventTrade], months: float, baseline_count: int = BASELINE["trade_count"]) -> dict[str, Any]:
    if not trades:
        return {
            "trade_count": 0,
            "expectancy_r": 0.0,
            "profit_factor": 0.0,
            "win_rate": 0.0,
            "max_dd_r": 0.0,
            "frequency_ratio_vs_baseline": 0.0,
            "dd_ratio_vs_baseline": 0.0,
            "avg_mae_r": 0.0,
            "avg_mfe_r": 0.0,
            "trades_per_month": 0.0,
            "er_at_2x_cost": 0.0,
            "max_month_pnl_pct": 0.0,
            "max_day_pnl_pct": 0.0,
        }
    pnls = [t.pnl_r for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    max_dd = max_drawdown_r(pnls)
    cost = cost_sensitivity(trades)
    concentration = concentration_metrics(trades)
    return {
        "trade_count": len(trades),
        "expectancy_r": sum(pnls) / len(pnls),
        "profit_factor": gross_profit / gross_loss if gross_loss else (float("inf") if gross_profit > 0 else 0.0),
        "win_rate": len(wins) / len(trades) * 100,
        "max_dd_r": max_dd,
        "frequency_ratio_vs_baseline": len(trades) / baseline_count if baseline_count else 0.0,
        "dd_ratio_vs_baseline": max_dd / BASELINE["max_dd_r"] if BASELINE["max_dd_r"] else 0.0,
        "avg_mae_r": sum(t.mae_r for t in trades) / len(trades),
        "avg_mfe_r": sum(t.mfe_r for t in trades) / len(trades),
        "median_r": median(pnls),
        "trades_per_month": len(trades) / max(months, 0.1),
        "er_at_2x_cost": cost["2x"]["er"],
        "er_at_3x_cost": cost["3x"]["er"],
        "pf_at_2x_cost": cost["2x"]["pf"],
        "max_month_pnl_pct": concentration["max_month_pnl_pct"],
        "max_day_pnl_pct": concentration["max_day_pnl_pct"],
        "top_month": concentration["top_month"],
        "top_day": concentration["top_day"],
    }


def max_drawdown_r(pnls: list[float]) -> float:
    cumulative = 0.0
    peak = 0.0
    max_dd = 0.0
    for pnl in pnls:
        cumulative += pnl
        peak = max(peak, cumulative)
        max_dd = max(max_dd, peak - cumulative)
    return max_dd


def cost_sensitivity(trades: list[EventTrade]) -> dict[str, dict[str, float]]:
    result: dict[str, dict[str, float]] = {}
    for mult in (1, 2, 3):
        adjusted: list[float] = []
        for trade in trades:
            risk = abs(trade.signal.entry_price - trade.signal.stop_loss)
            if risk <= 0:
                continue
            extra_fee = trade.signal.entry_price * FEE_RATE * (mult - 1) * 2
            extra_slip = trade.signal.entry_price * SLIPPAGE_BPS / 10000 * (mult - 1) * 2
            adjusted.append(trade.pnl_r - (extra_fee + extra_slip) / risk)
        wins = [p for p in adjusted if p > 0]
        losses = [p for p in adjusted if p <= 0]
        gross_profit = sum(wins)
        gross_loss = abs(sum(losses))
        result[f"{mult}x"] = {
            "er": sum(adjusted) / len(adjusted) if adjusted else 0.0,
            "pf": gross_profit / gross_loss if gross_loss else (float("inf") if gross_profit > 0 else 0.0),
        }
    return result


def concentration_metrics(trades: list[EventTrade]) -> dict[str, Any]:
    monthly: dict[str, float] = defaultdict(float)
    daily: dict[str, float] = defaultdict(float)
    for trade in trades:
        monthly[trade.entry_time.strftime("%Y-%m")] += trade.pnl_r
        daily[trade.entry_time.strftime("%Y-%m-%d")] += trade.pnl_r
    total_abs_month = sum(abs(v) for v in monthly.values())
    total_abs_day = sum(abs(v) for v in daily.values())
    top_month = max(monthly, key=lambda k: abs(monthly[k])) if monthly else ""
    top_day = max(daily, key=lambda k: abs(daily[k])) if daily else ""
    return {
        "max_month_pnl_pct": abs(monthly[top_month]) / total_abs_month if total_abs_month else 0.0,
        "max_day_pnl_pct": abs(daily[top_day]) / total_abs_day if total_abs_day else 0.0,
        "top_month": top_month,
        "top_day": top_day,
    }


def direction_metrics(trades: list[EventTrade], months: float) -> dict[str, dict[str, Any]]:
    return {
        direction: compute_metrics([t for t in trades if t.direction == direction], months)
        for direction in ("LONG", "SHORT")
    }


def oos_split_metrics(trades: list[EventTrade], months: float) -> dict[str, Any]:
    if len(trades) < 60:
        return {"available": False, "reason": "insufficient_sample"}
    train = [t for t in trades if t.entry_time < datetime(2025, 1, 1, tzinfo=timezone.utc)]
    test = [t for t in trades if t.entry_time >= datetime(2025, 1, 1, tzinfo=timezone.utc)]
    train_months = 12.0
    test_months = max((ANALYSIS_END - datetime(2025, 1, 1, tzinfo=timezone.utc)).days / 30.44, 0.1)
    train_metrics = compute_metrics(train, train_months)
    test_metrics = compute_metrics(test, test_months)
    degradation = (
        test_metrics["expectancy_r"] / train_metrics["expectancy_r"]
        if train_metrics["expectancy_r"]
        else None
    )
    return {
        "available": True,
        "train": train_metrics,
        "test": test_metrics,
        "test_to_train_er_ratio": degradation,
    }


def evaluate_run(run: SetupRun, months: float) -> None:
    run.metrics = compute_metrics(run.trades, months)
    gates = [
        Gate("min_trades", ">=", 20, "trade_count", "REQUIRED"),
        Gate("min_er", ">=", 1.0, "expectancy_r", "REQUIRED"),
        Gate("min_pf", ">=", 1.5, "profit_factor", "REQUIRED"),
        Gate("min_frequency_ratio", ">=", 1.5, "frequency_ratio_vs_baseline", "REQUIRED"),
        Gate("max_dd_ratio", "<=", 1.5, "dd_ratio_vs_baseline", "REQUIRED"),
        Gate("cost_sensitivity_2x", ">=", 0.5, "er_at_2x_cost", "REQUIRED"),
        Gate("max_concentration_month", "<=", 0.6, "max_month_pnl_pct", "RECOMMENDED"),
        Gate("max_concentration_day", "<=", 0.4, "max_day_pnl_pct", "RECOMMENDED"),
    ]
    evaluation = evaluate_gates(run.metrics, gates, experiment_id=f"{run.setup_id}:{run.variant_id}")
    run.gate_verdict = evaluation.verdict
    run.gate_summary = evaluation.summary
    run.gate_results = [result.to_dict() for result in evaluation.gate_results]


def choose_candidate(runs: list[SetupRun]) -> SetupRun:
    verdict_rank = {"PASS": 0, "MARGINAL": 1, "FAIL": 2, "INCONCLUSIVE": 3, "BLOCKED": 4}
    return sorted(
        runs,
        key=lambda r: (
            verdict_rank.get(r.gate_verdict, 9),
            -float(r.metrics.get("expectancy_r", 0.0)),
            -int(r.metrics.get("trade_count", 0)),
        ),
    )[0]


def setup_verdict(candidate: SetupRun, direction_split: dict[str, dict[str, Any]]) -> str:
    if candidate.gate_verdict == "PASS":
        long_ok = direction_split["LONG"]["trade_count"] >= 20 and direction_split["LONG"]["expectancy_r"] >= 1.0
        short_ok = direction_split["SHORT"]["trade_count"] >= 20 and direction_split["SHORT"]["expectancy_r"] >= 1.0
        if short_ok and not long_ok:
            return "MARGINAL"
        return "PASS"
    return candidate.gate_verdict


def milestone_verdict(setup_verdicts: list[str]) -> str:
    if "PASS" in setup_verdicts:
        return "MULTI_CANDLE_PASS"
    if "MARGINAL" in setup_verdicts:
        return "MULTI_CANDLE_MARGINAL"
    if setup_verdicts and all(v == "BLOCKED" for v in setup_verdicts):
        return "MULTI_CANDLE_BLOCKED"
    if "BLOCKED" in setup_verdicts:
        return "PARTIAL_BLOCKED"
    return "MULTI_CANDLE_FAIL"


def git_commit_hash() -> str:
    try:
        output = subprocess.check_output(
            [r"C:\Program Files\Git\cmd\git.exe", "rev-parse", "HEAD"],
            cwd=Path.cwd(),
            text=True,
            stderr=subprocess.DEVNULL,
        )
        return output.strip()
    except Exception:
        return "unknown"


def safe_create_experiment(**kwargs: Any) -> str:
    try:
        return create_experiment(**kwargs)
    except sqlite3.IntegrityError:
        existing = list_experiments(kwargs["registry_path"], hypothesis_id=kwargs["hypothesis_id"])
        if existing:
            return existing[-1]["experiment_id"]
        raise


def record_setup_experiment(run: SetupRun, manifests: list, report_path: Path) -> str:
    experiment_id = safe_create_experiment(
        registry_path=REGISTRY_PATH,
        hypothesis_id=f"btc_5m_{run.setup_id}_v1",
        config={"variant_id": run.variant_id, **run.params},
        data_manifests=manifests,
        baseline_reference="trial-00095",
        runner_name="btc_5m_multi_candle_event_setup_runner",
        date_range_start=ANALYSIS_START.date().isoformat(),
        date_range_end=ANALYSIS_END.date().isoformat(),
        git_commit=git_commit_hash(),
    )
    record_result(
        registry_path=REGISTRY_PATH,
        experiment_id=experiment_id,
        verdict=run.gate_verdict if run.gate_verdict in {"PASS", "MARGINAL", "FAIL", "INCONCLUSIVE", "BLOCKED"} else "BLOCKED",
        metrics=run.metrics,
        gates=[_gate_result_from_dict(g) for g in run.gate_results],
        artifacts={"report": str(report_path), "script": "research_lab/analysis_btc_5m_multi_candle_event_setup_feasibility.py"},
    )
    return experiment_id


def _gate_result_from_dict(payload: dict[str, Any]):
    # record_result expects GateResult objects. Rehydrate minimally.
    from research_lab.evaluators.gate_evaluator import Gate, GateResult

    gate = Gate(
        name=payload["name"],
        operator=payload["operator"],
        threshold=float(payload["threshold"]),
        metric_key=payload["metric_key"],
        severity=payload["severity"],
    )
    return GateResult(
        gate=gate,
        actual_value=payload["actual_value"],
        passed=bool(payload["passed"]),
        severity=payload["severity"],
        reason=payload.get("reason", ""),
    )


def generate_report(
    *,
    audit: dict[str, Any],
    all_runs: list[SetupRun],
    candidates: dict[str, SetupRun],
    setup_verdicts: dict[str, str],
    direction_splits: dict[str, dict[str, dict[str, Any]]],
    oos_splits: dict[str, dict[str, Any]],
    experiment_ids: dict[str, str],
    verdict: str,
    manifest_hash: str,
) -> str:
    lines: list[str] = []
    lines.append("# BTC 5m Multi-Candle Event Setup Feasibility")
    lines.append("")
    lines.append("**Date:** 2026-05-15")
    lines.append("**Milestone:** BTC_5M_MULTI_CANDLE_EVENT_SETUP_FEASIBILITY_V1")
    lines.append(f"**Verdict:** `{verdict}`")
    lines.append(f"**Analysis Period:** {ANALYSIS_START.date()} to {ANALYSIS_END.date()}")
    lines.append("**Baseline:** trial-00095 M5 15m baseline, same analysis period")
    lines.append("")
    lines.append("> Offline research only. No production, PAPER, runtime, settings, core, execution, or orchestrator changes.")
    lines.append("")
    lines.append("## Executive Summary")
    lines.append("")
    if verdict == "MULTI_CANDLE_PASS":
        key = "At least one 5m multi-candle setup passed all gates."
    elif verdict == "MULTI_CANDLE_MARGINAL":
        key = "At least one setup was promising but failed recommended or direction-quality constraints."
    elif verdict == "PARTIAL_BLOCKED":
        key = "One setup could be tested while another was blocked by missing data."
    else:
        key = "No tested 5m multi-candle setup passed the quality and frequency gates."
    lines.append(f"- **Key Finding:** {key}")
    lines.append("- **Recommendation:** Claude Code audit required before scheduling follow-up research.")
    lines.append("")
    lines.append("## Data Sources / Manifests")
    lines.append("")
    lines.append("| Dataset | Status | Rows | Notes |")
    lines.append("|---|---|---:|---|")
    lines.append(f"| 5m candles DB | {'PASS' if audit['db_5m_exists'] else 'FAIL'} | {audit['candles_5m_rows']} | `research_lab/snapshots/btc_5m_2022_2026.db` |")
    lines.append(f"| Replay DB OI | {'PASS' if audit['oi_rows'] else 'MISSING'} | {audit['oi_rows']} | Used by Setup B precondition when available |")
    lines.append(f"| Replay DB funding | {'PASS' if audit['funding_rows'] else 'MISSING'} | {audit['funding_rows']} | Used by Setup B precondition when available |")
    force_note = audit.get("force_order_source") or "No historical force-order source found"
    if audit.get("force_order_start") and audit.get("force_order_end"):
        force_note = f"{force_note}; {audit['force_order_start']} to {audit['force_order_end']}"
    lines.append(f"| Historical force_orders | {'PASS' if audit['force_order_rows'] else 'MISSING'} | {audit['force_order_rows']} | {force_note} |")
    lines.append("")
    lines.append(f"**Data manifest hash:** `{manifest_hash[:16]}`")
    lines.append(f"**Setup B data mode:** `{audit['setup_b_data_mode']}`")
    lines.append("")
    lines.append("## Hypotheses")
    lines.append("")
    lines.append("| Setup | Mechanism | Verdict | Best Variant |")
    lines.append("|---|---|---|---|")
    lines.append(f"| Compression Fakeout Reclaim | Compression -> fakeout -> reclaim | `{setup_verdicts['compression_fakeout_reclaim']}` | `{candidates['compression_fakeout_reclaim'].variant_id}` |")
    lines.append(f"| Crowded Unwind Reversal | Crowding -> forced move -> snapback | `{setup_verdicts['crowded_unwind_reversal']}` | `{candidates['crowded_unwind_reversal'].variant_id}` |")
    lines.append("")
    lines.append("## Baseline Comparison")
    lines.append("")
    lines.append("| Metric | 15m Baseline | Compression Candidate | Crowded Candidate |")
    lines.append("|---|---:|---:|---:|")
    for key, label in (
        ("trade_count", "Trade Count"),
        ("expectancy_r", "Expectancy R"),
        ("profit_factor", "Profit Factor"),
        ("win_rate", "Win Rate %"),
        ("max_dd_r", "Max DD R"),
        ("avg_mae_r", "Avg MAE R"),
        ("avg_mfe_r", "Avg MFE R"),
    ):
        comp = candidates["compression_fakeout_reclaim"].metrics.get(key, 0)
        crowd = candidates["crowded_unwind_reversal"].metrics.get(key, 0)
        base = BASELINE.get(key, "-")
        lines.append(f"| {label} | {_fmt(base)} | {_fmt(comp)} | {_fmt(crowd)} |")
    lines.append("")
    lines.append("## All Tested Variants")
    lines.append("")
    lines.append("| Setup | Variant | Trades | ER | PF | WR% | DD R | Freq Ratio | 2x Cost ER | Verdict |")
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---|")
    for run in all_runs:
        m = run.metrics
        lines.append(
            f"| {run.setup_id} | {run.variant_id} | {m.get('trade_count', 0)} | {_fmt(m.get('expectancy_r'))} | "
            f"{_fmt(m.get('profit_factor'))} | {_fmt(m.get('win_rate'))} | {_fmt(m.get('max_dd_r'))} | "
            f"{_fmt(m.get('frequency_ratio_vs_baseline'))} | {_fmt(m.get('er_at_2x_cost'))} | `{run.gate_verdict}` |"
        )
    lines.append("")
    lines.append("## Signal Funnels")
    lines.append("")
    lines.append("| Setup | Variant | Precondition | Event | Confirmation | Raw Signals | Trades | Overlap Skipped |")
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|")
    for run in all_runs:
        lines.append(
            f"| {run.setup_id} | {run.variant_id} | {run.precondition_count} | {run.event_count} | "
            f"{run.confirmation_count} | {run.raw_signal_count} | {len(run.trades)} | {run.overlap_skipped_count} |"
        )
    lines.append("")
    lines.append("## Direction Split")
    lines.append("")
    lines.append("| Setup | Direction | Trades | ER | PF | WR% |")
    lines.append("|---|---|---:|---:|---:|---:|")
    for setup_id, split in direction_splits.items():
        for direction in ("LONG", "SHORT"):
            m = split[direction]
            lines.append(
                f"| {setup_id} | {direction} | {m.get('trade_count', 0)} | {_fmt(m.get('expectancy_r'))} | "
                f"{_fmt(m.get('profit_factor'))} | {_fmt(m.get('win_rate'))} |"
            )
    lines.append("")
    lines.append("## Concentration And OOS")
    lines.append("")
    lines.append("| Setup | Max Month % | Top Month | Max Day % | Top Day | OOS Available | Test ER |")
    lines.append("|---|---:|---|---:|---|---|---:|")
    for setup_id, run in candidates.items():
        m = run.metrics
        oos = oos_splits[setup_id]
        test_er = oos.get("test", {}).get("expectancy_r") if oos.get("available") else None
        lines.append(
            f"| {setup_id} | {_pct(m.get('max_month_pnl_pct', 0))} | {m.get('top_month', '')} | "
            f"{_pct(m.get('max_day_pnl_pct', 0))} | {m.get('top_day', '')} | {oos.get('available')} | {_fmt(test_er)} |"
        )
    lines.append("")
    lines.append("## Baseline Overlap")
    lines.append("")
    lines.append("| Setup | Overlap With trial-00095 | Status |")
    lines.append("|---|---:|---|")
    for setup_id in candidates:
        lines.append(
            f"| {setup_id} | N/A | Official trial-00095 signal timestamps are unavailable in this standalone harness |"
        )
    lines.append("")
    lines.append("## Gate Evaluation")
    lines.append("")
    for setup_id, run in candidates.items():
        lines.append(f"### {setup_id} - {run.variant_id}")
        lines.append("")
        lines.append("| Gate | Threshold | Actual | Status | Severity |")
        lines.append("|---|---:|---:|---|---|")
        for result in run.gate_results:
            status = "PASS" if result["passed"] else "FAIL"
            lines.append(
                f"| {result['name']} | {result['operator']} {result['threshold']} | "
                f"{_fmt(result['actual_value'])} | {status} | {result['severity']} |"
            )
        lines.append("")
    lines.append("## Experiment Registry")
    lines.append("")
    lines.append("| Setup | Experiment ID |")
    lines.append("|---|---|")
    for setup_id, experiment_id in experiment_ids.items():
        lines.append(f"| {setup_id} | `{experiment_id}` |")
    lines.append("")
    lines.append("## Verdict Taxonomy")
    lines.append("")
    lines.append("- `MULTI_CANDLE_PASS`: at least one setup passes all gates and materially increases trade count.")
    lines.append("- `MULTI_CANDLE_MARGINAL`: one setup improves frequency but quality is borderline or sample is fragile.")
    lines.append("- `MULTI_CANDLE_FAIL`: no setup passes quality and frequency gates.")
    lines.append("- `MULTI_CANDLE_BLOCKED`: required data unavailable for both setups.")
    lines.append("- `PARTIAL_BLOCKED`: one setup blocked, one tested.")
    lines.append("")
    lines.append("## Limitations")
    lines.append("")
    lines.append("- Standalone research harness, not BacktestRunner.")
    lines.append("- Simplified TP/SL simulation: no partial exits, no trailing, no funding accrual.")
    lines.append("- Crowded unwind uses historical force orders from `research_lab/data/crowded_unwind_backtest.db`; coverage ends 2024-12-01, so that setup is evaluated only through the available force-order period.")
    lines.append("- Official trial-00095 signal timestamps are not available in this harness, so direct overlap with baseline is not decision-grade.")
    lines.append("- No parameter rescue was performed; all predefined variants are reported.")
    lines.append("")
    lines.append("## Artifacts")
    lines.append("")
    lines.append("- Hypothesis A: `research_lab/hypotheses/active/btc_5m_compression_fakeout_reclaim.json`")
    lines.append("- Hypothesis B: `research_lab/hypotheses/active/btc_5m_crowded_unwind_reversal.json`")
    lines.append("- Script: `research_lab/analysis_btc_5m_multi_candle_event_setup_feasibility.py`")
    lines.append("- Report: `docs/analysis/BTC_5M_MULTI_CANDLE_EVENT_SETUP_FEASIBILITY_2026-05-15.md`")
    lines.append("")
    lines.append("## Next-Step Recommendation")
    lines.append("")
    if verdict == "MULTI_CANDLE_PASS":
        lines.append("Promising setup found. Next step is Claude audit, then stricter OOS/WF validation before any runtime discussion.")
    elif verdict == "MULTI_CANDLE_MARGINAL":
        lines.append("Do not promote. Use Claude audit to decide whether a bounded OOS refinement is justified.")
    else:
        lines.append("Close this branch unless Claude identifies a methodology issue. Do not rescue failed variants by expanding the grid.")
    lines.append("")
    lines.append("---")
    lines.append("*Generated by research_lab/analysis_btc_5m_multi_candle_event_setup_feasibility.py*")
    return "\n".join(lines)


def _fmt(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        if math.isinf(value):
            return "inf"
        return f"{value:.3f}"
    return str(value)


def _pct(value: Any) -> str:
    if value is None:
        return "-"
    return f"{float(value) * 100:.1f}%"


def main() -> None:
    print("=" * 72)
    print("BTC 5M MULTI-CANDLE EVENT SETUP FEASIBILITY")
    print("=" * 72)
    audit = audit_data_availability()
    print(f"5m DB tables: {audit['db_5m_tables']}")
    print(f"Replay DB OI rows: {audit['oi_rows']}, funding rows: {audit['funding_rows']}, force orders: {audit['force_order_rows']}")
    if not audit["db_5m_exists"]:
        raise FileNotFoundError(DB_5M)

    candles = load_candles(DB_5M, LOOKBACK_START, ANALYSIS_END)
    force_buckets = load_force_order_buckets(DB_FORCE)
    stats = rolling_stats(candles, force_buckets)
    oi, funding = load_oi_funding(DB_REPLAY)
    start_idx = next(i for i, candle in enumerate(candles) if candle.open_time >= ANALYSIS_START)
    end_idx = len(candles)
    candle_times = [c.open_time for c in candles]
    if audit.get("force_order_end"):
        force_end = _parse_ts(audit["force_order_end"])
        crowded_end_idx = min(end_idx, bisect_right(candle_times, force_end))
    else:
        crowded_end_idx = end_idx
    months = (ANALYSIS_END - ANALYSIS_START).days / 30.44
    crowded_months = (candles[crowded_end_idx - 1].open_time - ANALYSIS_START).days / 30.44 if crowded_end_idx > start_idx else months
    print(f"Loaded {len(candles)} 5m candles, analysis bars={end_idx - start_idx}")
    print(f"Loaded {len(force_buckets)} 5m force-order buckets; crowded analysis bars={crowded_end_idx - start_idx}")

    compression_variants = [
        SetupVariant("compression_fakeout_reclaim", "CFR_V1", {"compression_lookback": 96, "range_lookback": 24, "reclaim_window_bars": 3, "bb_width_quantile": 0.25}),
        SetupVariant("compression_fakeout_reclaim", "CFR_V2", {"compression_lookback": 144, "range_lookback": 36, "reclaim_window_bars": 3, "bb_width_quantile": 0.25}),
        SetupVariant("compression_fakeout_reclaim", "CFR_V3", {"compression_lookback": 96, "range_lookback": 48, "reclaim_window_bars": 4, "bb_width_quantile": 0.20}),
    ]
    crowded_variants = [
        SetupVariant("crowded_unwind_reversal", "CUR_V1", {"crowding_lookback_bars": 24, "forced_move_atr_mult": 1.5, "snapback_window_bars": 3, "min_body_ratio": 0.55, "min_volume_z": 1.0, "min_force_z": 2.0}),
        SetupVariant("crowded_unwind_reversal", "CUR_V2", {"crowding_lookback_bars": 48, "forced_move_atr_mult": 2.0, "snapback_window_bars": 3, "min_body_ratio": 0.60, "min_volume_z": 1.0, "min_force_z": 2.5}),
        SetupVariant("crowded_unwind_reversal", "CUR_V3", {"crowding_lookback_bars": 24, "forced_move_atr_mult": 1.5, "snapback_window_bars": 4, "min_body_ratio": 0.55, "min_volume_z": 1.5, "min_force_z": 2.0}),
    ]

    all_runs: list[SetupRun] = []
    for variant in compression_variants:
        print(f"Running {variant.setup_id} {variant.variant_id}")
        run = detect_compression_fakeout(candles, stats, variant, start_idx, end_idx)
        evaluate_run(run, months)
        all_runs.append(run)
        print(f"  trades={len(run.trades)} ER={run.metrics['expectancy_r']:.3f} PF={run.metrics['profit_factor']:.2f} verdict={run.gate_verdict}")
    for variant in crowded_variants:
        print(f"Running {variant.setup_id} {variant.variant_id}")
        run = detect_crowded_unwind(candles, stats, variant, start_idx, crowded_end_idx, oi, funding)
        evaluate_run(run, crowded_months)
        all_runs.append(run)
        print(f"  trades={len(run.trades)} ER={run.metrics['expectancy_r']:.3f} PF={run.metrics['profit_factor']:.2f} verdict={run.gate_verdict}")

    by_setup: dict[str, list[SetupRun]] = defaultdict(list)
    for run in all_runs:
        by_setup[run.setup_id].append(run)
    candidates = {setup_id: choose_candidate(runs) for setup_id, runs in by_setup.items()}
    direction_splits = {setup_id: direction_metrics(run.trades, months) for setup_id, run in candidates.items()}
    setup_verdicts = {setup_id: setup_verdict(run, direction_splits[setup_id]) for setup_id, run in candidates.items()}
    oos_splits = {setup_id: oos_split_metrics(run.trades, months) for setup_id, run in candidates.items()}
    verdict = milestone_verdict(list(setup_verdicts.values()))

    manifest = create_manifest(
        dataset_id="btc_5m_2022_2026",
        path=DB_5M,
        timeframe="5m",
        symbol=SYMBOL,
        date_start=ANALYSIS_START.date().isoformat(),
        date_end=ANALYSIS_END.date().isoformat(),
        row_count=end_idx - start_idx,
        quality_status="PASS",
        source="M5_backfill",
    )
    force_manifest = create_manifest(
        dataset_id="btc_force_orders_2022_2024",
        path=DB_FORCE,
        timeframe="event",
        symbol=SYMBOL,
        date_start=str(audit.get("force_order_start") or "missing"),
        date_end=str(audit.get("force_order_end") or "missing"),
        row_count=int(audit.get("force_order_rows") or 0),
        quality_status="PASS" if audit.get("force_order_rows") else "WARN",
        source="force_orders_backfill",
    )
    manifests = [manifest, force_manifest]
    experiment_ids = {
        setup_id: record_setup_experiment(run, manifests, REPORT_PATH)
        for setup_id, run in candidates.items()
    }
    report = generate_report(
        audit=audit,
        all_runs=all_runs,
        candidates=candidates,
        setup_verdicts=setup_verdicts,
        direction_splits=direction_splits,
        oos_splits=oos_splits,
        experiment_ids=experiment_ids,
        verdict=verdict,
        manifest_hash=compute_combined_manifest_hash(manifests),
    )
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")
    print("=" * 72)
    print(f"VERDICT: {verdict}")
    for setup_id, run in candidates.items():
        print(f"{setup_id}: {setup_verdicts[setup_id]} ({run.variant_id}) trades={len(run.trades)} ER={run.metrics['expectancy_r']:.3f}")
    print(f"Report written: {REPORT_PATH}")


if __name__ == "__main__":
    main()
