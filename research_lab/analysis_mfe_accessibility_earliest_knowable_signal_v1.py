#!/usr/bin/env python3
"""Research-only MFE accessibility / earliest-knowable-signal diagnostic.

This diagnostic maps post-sweep states by when they become knowable and measures
remaining MFE/MAE from a realistic next-bar entry. It is not a strategy, does
not modify production code, and does not write to production databases.
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
from collections import Counter, defaultdict, deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = PROJECT_ROOT / "research_lab" / "data" / "crowded_unwind_backtest.db"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "research_lab" / "analysis_output"
DEFAULT_REPORT_DIR = PROJECT_ROOT / "docs" / "analysis"

TRIAL_00095_REFERENCE = {
    "er": 2.1,
    "profit_factor": 4.6625,
    "max_drawdown_pct": 0.0651,
    "trades": 271,
    "v1_raw_wick_cross_median_5": 0.000237,
    "v1_delayed_reclaim_label_median_5": 0.000054,
    "v1_true_breakout_label_median_5": -0.000268,
    "smc_detection_5_median": 0.004348,
    "smc_entry_5_median": 0.000558,
    "smc_entry_5_net_median": -0.000442,
    "smc_entry_5_pf_proxy": 1.061059,
}

STATE_RAW_SWEEP = "raw_sweep_known"
STATE_LEVEL_QUALITY = "level_cluster_quality_known"
STATE_DEEP_SWEEP = "deep_sweep_threshold_known"
STATE_SHALLOW_NEAR_MISS = "shallow_sweep_near_miss_known"
STATE_RECLAIM = "reclaim_known"
STATE_NO_RECLAIM_1 = "no_reclaim_after_1_bar_known"
STATE_NO_RECLAIM_2 = "no_reclaim_after_2_bars_known"
STATE_NO_RECLAIM_3 = "no_reclaim_after_3_bars_known"
STATE_NO_RECLAIM_4 = "no_reclaim_after_4_bars_known"
STATE_CLOSE_BEYOND = "close_beyond_level_known"
STATE_DISPLACEMENT = "displacement_known"
STATE_DIRECTION = "direction_resolved_known"
STATE_TFI_ALIGNED = "tfi_aligned_known"
STATE_TFI_IMPULSE = "tfi_strong_impulse_known"
STATE_CVD_DIVERGENCE = "cvd_divergence_known"
STATE_CVD_ABSORPTION = "cvd_absorption_proxy_known"
STATE_FORCE_BURST = "force_order_burst_known"
STATE_FORCE_DIRECTIONAL = "force_order_directional_burst_known"
STATE_FORCE_DECAY = "force_order_decay_known"
STATE_FUNDING_SUPPORT = "funding_supportive_known"
STATE_OI_CROWDING = "oi_crowding_known"
STATE_OI_FUNDING = "oi_funding_crowding_known"
STATE_CONFLUENCE = "confluence_threshold_known"
STATE_TRIAL_CANDIDATE = "trial_00095_candidate_state"
STATE_REJECT_NO_RECLAIM = "reject_no_reclaim_known"
STATE_REJECT_SHALLOW = "reject_sweep_too_shallow_known"
STATE_REJECT_DIRECTION = "reject_direction_unresolved_known"
STATE_REJECT_CONFLUENCE = "reject_confluence_below_min_known"

DECISION_STATES = {
    STATE_RAW_SWEEP,
    STATE_RECLAIM,
    STATE_DISPLACEMENT,
    STATE_TFI_ALIGNED,
    STATE_TFI_IMPULSE,
    STATE_CVD_DIVERGENCE,
    STATE_CVD_ABSORPTION,
    STATE_FORCE_BURST,
    STATE_FORCE_DIRECTIONAL,
    STATE_FORCE_DECAY,
    STATE_FUNDING_SUPPORT,
    STATE_OI_CROWDING,
    STATE_OI_FUNDING,
    STATE_DIRECTION,
    STATE_CONFLUENCE,
    STATE_TRIAL_CANDIDATE,
    STATE_REJECT_NO_RECLAIM,
    STATE_REJECT_SHALLOW,
    STATE_REJECT_DIRECTION,
    STATE_REJECT_CONFLUENCE,
}


@dataclass(frozen=True, slots=True)
class Candle:
    index: int
    open_time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True, slots=True)
class DiagnosticConfig:
    symbol: str = "BTCUSDT"
    timeframe: str = "15m"
    atr_period: int = 27
    equal_level_lookback: int = 276
    equal_level_tol_atr: float = 0.09
    min_hits: int = 3
    min_age_bars: int = 5
    sweep_buf_atr: float = 0.46
    sweep_proximity_atr: float = 0.40
    reclaim_buf_atr: float = 0.07
    wick_min_atr: float = 0.20
    min_sweep_depth_pct: float = 0.00649
    near_miss_depth_pct: float = 0.00400
    duplicate_level_tolerance_pct: float = 0.0016
    duplicate_level_window_bars: int = 492
    max_post_bars: int = 20
    forward_windows: tuple[int, ...] = (3, 5, 10, 20)
    round_trip_cost_pct: float = 0.0010
    deterministic_control_shift_bars: int = 137
    direction_tfi_threshold: float = 0.10
    tfi_impulse_threshold: float = 0.31
    confluence_min: float = 3.90
    weight_sweep_detected: float = 2.20
    weight_reclaim_confirmed: float = 2.15
    weight_cvd_divergence: float = 3.20
    weight_tfi_impulse: float = 2.50
    weight_force_order_spike: float = 0.40
    weight_funding_supportive: float = 1.10
    cvd_divergence_bars: int = 30
    oi_z_window_bars: int = 96 * 35
    force_burst_window: int = 96
    force_burst_z: float = 2.0
    force_decay_lookback: int = 3
    max_json_rows: int = 5000


@dataclass(frozen=True, slots=True)
class DataQuality:
    rows: int
    start_time_utc: str | None
    end_time_utc: str | None
    duplicate_timestamps: int
    non_monotonic_timestamps: int
    ohlc_violations: int
    missing_bar_gaps: int
    inferred_step_seconds: int | None
    aggtrade_15m_rows: int = 0
    force_order_rows: int = 0
    funding_rows: int = 0
    open_interest_rows: int = 0


@dataclass(frozen=True, slots=True)
class MetadataPoint:
    tfi: float = 0.0
    cvd: float = 0.0
    cvd_cum: float = 0.0
    force_count: int = 0
    force_buy_qty: float = 0.0
    force_sell_qty: float = 0.0
    force_z: float = 0.0
    funding_rate: float = 0.0
    oi_value: float = 0.0
    oi_delta_pct: float = 0.0
    oi_zscore: float = 0.0


@dataclass(frozen=True, slots=True)
class SweepEvent:
    event_id: str
    symbol: str
    timeframe: str
    detection_bar: int
    direction: str
    sweep_side: str
    level: float
    atr: float
    sweep_depth_pct: float
    sweep_depth_atr: float
    cluster_count: int
    level_age_bars: int


@dataclass(slots=True)
class StateObservation:
    event_id: str
    symbol: str
    timeframe: str
    state_name: str
    direction: str
    sweep_side: str
    sweep_level: float
    sweep_depth_pct: float
    detection_bar: int
    state_known_bar: int
    entry_candidate_bar: int
    return_start_bar: int
    k: int
    detection_time_utc: str
    state_known_time_utc: str
    entry_candidate_time_utc: str
    current_bot_blocked_by: str | None
    current_bot_candidate_generated: bool
    trial_00095_candidate_state: bool
    confluence_score: float | None
    known_state_flags: list[str]
    metadata: dict[str, Any] = field(default_factory=dict)
    forward_entry: dict[str, float | None] = field(default_factory=dict)
    forward_detection_audit: dict[str, float | None] = field(default_factory=dict)
    mfe_before_state: float | None = None
    mfe_after_state_20: float | None = None
    mae_after_state_20: float | None = None
    mfe_consumed_pct: float | None = None


def parse_ts(raw: Any) -> datetime:
    if isinstance(raw, datetime):
        return raw.astimezone(timezone.utc) if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
    parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    return parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def load_candles(
    conn: sqlite3.Connection,
    *,
    symbol: str,
    timeframe: str,
    start: datetime | None = None,
    end: datetime | None = None,
) -> list[Candle]:
    clauses = ["symbol = ?", "timeframe = ?"]
    params: list[Any] = [symbol, timeframe]
    if start is not None:
        clauses.append("open_time >= ?")
        params.append(start.isoformat())
    if end is not None:
        clauses.append("open_time <= ?")
        params.append(end.isoformat())
    rows = conn.execute(
        f"""
        SELECT open_time, open, high, low, close, volume
        FROM candles
        WHERE {' AND '.join(clauses)}
        ORDER BY open_time ASC
        """,
        tuple(params),
    ).fetchall()
    return [
        Candle(
            index=idx,
            open_time=parse_ts(row[0]),
            open=float(row[1]),
            high=float(row[2]),
            low=float(row[3]),
            close=float(row[4]),
            volume=float(row[5] or 0.0),
        )
        for idx, row in enumerate(rows)
    ]


def _tables(conn: sqlite3.Connection) -> set[str]:
    return {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}


def validate_candles(candles: list[Candle], *, metadata_counts: dict[str, int] | None = None) -> DataQuality:
    if not candles:
        return DataQuality(0, None, None, 0, 0, 0, 0, None, **(metadata_counts or {}))
    duplicate_timestamps = len(candles) - len({c.open_time for c in candles})
    non_monotonic = sum(1 for prev, cur in zip(candles, candles[1:]) if cur.open_time <= prev.open_time)
    ohlc_violations = sum(
        1
        for candle in candles
        if candle.high < max(candle.open, candle.close, candle.low)
        or candle.low > min(candle.open, candle.close, candle.high)
    )
    deltas = [int((cur.open_time - prev.open_time).total_seconds()) for prev, cur in zip(candles, candles[1:])]
    step = int(median(deltas)) if deltas else None
    missing = sum(1 for delta in deltas if step and delta > step)
    return DataQuality(
        rows=len(candles),
        start_time_utc=candles[0].open_time.isoformat(),
        end_time_utc=candles[-1].open_time.isoformat(),
        duplicate_timestamps=duplicate_timestamps,
        non_monotonic_timestamps=non_monotonic,
        ohlc_violations=ohlc_violations,
        missing_bar_gaps=missing,
        inferred_step_seconds=step,
        **(metadata_counts or {}),
    )


def load_aggtrade_15m(conn: sqlite3.Connection, *, symbol: str) -> tuple[dict[datetime, tuple[float, float]], int]:
    if "aggtrade_buckets" not in _tables(conn):
        return {}, 0
    rows = conn.execute(
        """
        SELECT bucket_time, tfi, cvd
        FROM aggtrade_buckets
        WHERE symbol = ? AND timeframe = '15m'
        ORDER BY bucket_time ASC
        """,
        (symbol,),
    ).fetchall()
    return {parse_ts(row[0]): (float(row[1] or 0.0), float(row[2] or 0.0)) for row in rows}, len(rows)


def load_force_orders_by_candle(
    conn: sqlite3.Connection,
    *,
    symbol: str,
    candles: list[Candle],
) -> tuple[dict[datetime, tuple[int, float, float]], int]:
    if "force_orders" not in _tables(conn) or not candles:
        return {}, 0
    step = int((candles[1].open_time - candles[0].open_time).total_seconds()) if len(candles) > 1 else 900
    start = candles[0].open_time
    end = candles[-1].open_time
    rows = conn.execute(
        """
        SELECT event_time, side, qty
        FROM force_orders
        WHERE symbol = ? AND event_time >= ? AND event_time < ?
        ORDER BY event_time ASC
        """,
        (symbol, start.isoformat(), (end + timedelta(seconds=step)).isoformat()),
    ).fetchall()
    buckets: dict[datetime, list[float]] = defaultdict(lambda: [0.0, 0.0, 0.0])
    for event_time, side, qty in rows:
        ts = parse_ts(event_time)
        idx = int((ts - start).total_seconds() // step)
        if idx < 0 or idx >= len(candles):
            continue
        key = candles[idx].open_time
        buckets[key][0] += 1.0
        if str(side).upper() == "BUY":
            buckets[key][1] += float(qty or 0.0)
        else:
            buckets[key][2] += float(qty or 0.0)
    return {key: (int(vals[0]), vals[1], vals[2]) for key, vals in buckets.items()}, len(rows)


def _load_time_series(
    conn: sqlite3.Connection,
    *,
    table: str,
    symbol: str,
    time_col: str,
    value_col: str,
) -> tuple[list[tuple[datetime, float]], int]:
    if table not in _tables(conn):
        return [], 0
    rows = conn.execute(
        f"""
        SELECT {time_col}, {value_col}
        FROM {table}
        WHERE symbol = ?
        ORDER BY {time_col} ASC
        """,
        (symbol,),
    ).fetchall()
    return [(parse_ts(row[0]), float(row[1] or 0.0)) for row in rows], len(rows)


def align_last_known(series: list[tuple[datetime, float]], candles: list[Candle]) -> list[float]:
    values: list[float] = []
    pointer = 0
    current = 0.0
    for candle in candles:
        while pointer < len(series) and series[pointer][0] <= candle.open_time:
            current = series[pointer][1]
            pointer += 1
        values.append(current)
    return values


def compute_metadata(
    conn: sqlite3.Connection,
    *,
    candles: list[Candle],
    config: DiagnosticConfig,
) -> tuple[list[MetadataPoint], dict[str, int]]:
    agg, agg_count = load_aggtrade_15m(conn, symbol=config.symbol)
    force, force_count = load_force_orders_by_candle(conn, symbol=config.symbol, candles=candles)
    funding_series, funding_count = _load_time_series(
        conn,
        table="funding",
        symbol=config.symbol,
        time_col="funding_time",
        value_col="funding_rate",
    )
    oi_series, oi_count = _load_time_series(
        conn,
        table="open_interest",
        symbol=config.symbol,
        time_col="timestamp",
        value_col="oi_value",
    )
    funding_by_bar = align_last_known(funding_series, candles)
    oi_by_bar = align_last_known(oi_series, candles)
    metadata: list[MetadataPoint] = []
    cvd_cum = 0.0
    force_window: deque[float] = deque(maxlen=config.force_burst_window)
    force_sum = 0.0
    force_sumsq = 0.0
    oi_window: deque[float] = deque(maxlen=config.oi_z_window_bars)
    oi_sum = 0.0
    oi_sumsq = 0.0
    for idx, candle in enumerate(candles):
        tfi, cvd = agg.get(candle.open_time, (0.0, 0.0))
        cvd_cum += cvd
        force_count_i, force_buy, force_sell = force.get(candle.open_time, (0, 0.0, 0.0))
        if len(force_window) >= 5:
            avg = force_sum / len(force_window)
            variance = max((force_sumsq / len(force_window)) - (avg * avg), 0.0)
            stdev = math.sqrt(variance)
            force_z = 0.0 if stdev <= 0 else (force_count_i - avg) / stdev
        else:
            force_z = 0.0
        oi_value = oi_by_bar[idx]
        oi_prev = oi_by_bar[idx - 1] if idx > 0 else oi_value
        oi_delta = 0.0 if oi_prev == 0 else (oi_value - oi_prev) / oi_prev
        if len(oi_window) == oi_window.maxlen:
            old = oi_window.popleft()
            oi_sum -= old
            oi_sumsq -= old * old
        oi_window.append(oi_value)
        oi_sum += oi_value
        oi_sumsq += oi_value * oi_value
        if len(oi_window) > 5:
            oi_avg = oi_sum / len(oi_window)
            oi_variance = max((oi_sumsq / len(oi_window)) - (oi_avg * oi_avg), 0.0)
            oi_stdev = math.sqrt(oi_variance)
            oi_z = 0.0 if oi_stdev <= 0 else (oi_value - oi_avg) / oi_stdev
        else:
            oi_z = 0.0
        metadata.append(
            MetadataPoint(
                tfi=tfi,
                cvd=cvd,
                cvd_cum=cvd_cum,
                force_count=force_count_i,
                force_buy_qty=force_buy,
                force_sell_qty=force_sell,
                force_z=force_z,
                funding_rate=funding_by_bar[idx],
                oi_value=oi_value,
                oi_delta_pct=oi_delta,
                oi_zscore=oi_z,
            )
        )
        if len(force_window) == force_window.maxlen:
            old_force = force_window.popleft()
            force_sum -= old_force
            force_sumsq -= old_force * old_force
        force_window.append(float(force_count_i))
        force_sum += float(force_count_i)
        force_sumsq += float(force_count_i) * float(force_count_i)
    return metadata, {
        "aggtrade_15m_rows": agg_count,
        "force_order_rows": force_count,
        "funding_rows": funding_count,
        "open_interest_rows": oi_count,
    }


def _stdev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    avg = mean(values)
    return math.sqrt(sum((value - avg) ** 2 for value in values) / len(values))


def zscore(values: list[float], current: float) -> float:
    if not values:
        return 0.0
    avg = mean(values)
    stdev = _stdev(values)
    return 0.0 if stdev <= 0 else (current - avg) / stdev


def compute_atr_series(candles: list[Candle], period: int) -> list[float | None]:
    true_ranges: list[float] = []
    atr: list[float | None] = [None] * len(candles)
    for idx, candle in enumerate(candles):
        prev_close = candles[idx - 1].close if idx > 0 else candle.close
        true_range = max(
            candle.high - candle.low,
            abs(candle.high - prev_close),
            abs(candle.low - prev_close),
        )
        true_ranges.append(true_range)
        if idx + 1 >= period:
            atr[idx] = mean(true_ranges[-period:])
    return atr


def detect_equal_levels(
    levels: list[tuple[int, float]],
    tolerance: float,
    min_hits: int,
    min_age_bars: int,
) -> list[tuple[float, int, int]]:
    if not levels:
        return []
    sorted_levels = sorted(levels, key=lambda item: item[1])
    clusters: list[list[tuple[int, float]]] = []
    current_cluster = [sorted_levels[0]]
    for item in sorted_levels[1:]:
        if abs(item[1] - current_cluster[-1][1]) <= tolerance:
            current_cluster.append(item)
        else:
            clusters.append(current_cluster)
            current_cluster = [item]
    clusters.append(current_cluster)
    merged: list[tuple[float, int, int]] = []
    for cluster in clusters:
        if len(cluster) < min_hits:
            continue
        indices = [idx for idx, _ in cluster]
        age = max(indices) - min(indices)
        if age < min_age_bars:
            continue
        merged.append((round(mean([price for _, price in cluster]), 2), len(cluster), age))
    return merged


def detect_equal_levels_near(
    candles: list[Candle],
    *,
    start_idx: int,
    end_idx: int,
    side: str,
    target_price: float,
    search_radius: float,
    tolerance: float,
    min_hits: int,
    min_age_bars: int,
) -> list[tuple[float, int, int]]:
    levels: list[tuple[int, float]] = []
    for candle in candles[start_idx:end_idx]:
        price = candle.low if side == "LOW" else candle.high
        if abs(price - target_price) <= search_radius:
            levels.append((candle.index, price))
    return detect_equal_levels(levels, tolerance, min_hits, min_age_bars)


def _retired_match(retired: list[tuple[int, float]], *, idx: int, level: float, config: DiagnosticConfig) -> bool:
    horizon = idx - config.duplicate_level_window_bars
    for retired_idx, retired_level in retired:
        if retired_idx < horizon:
            continue
        baseline = max(abs(retired_level), 1e-9)
        if abs(level - retired_level) / baseline <= config.duplicate_level_tolerance_pct:
            return True
    return False


def detect_sweep_events(candles: list[Candle], atr: list[float | None], config: DiagnosticConfig) -> list[SweepEvent]:
    events: list[SweepEvent] = []
    retired_highs: list[tuple[int, float]] = []
    retired_lows: list[tuple[int, float]] = []
    for idx, candle in enumerate(candles):
        atr_value = atr[idx]
        if atr_value is None or atr_value <= 0 or idx < config.equal_level_lookback:
            continue
        tolerance = config.equal_level_tol_atr * atr_value
        proximity = config.sweep_proximity_atr * atr_value
        sweep_buffer = config.sweep_buf_atr * atr_value
        start_idx = idx - config.equal_level_lookback
        search_radius = proximity + tolerance + sweep_buffer
        equal_lows = detect_equal_levels_near(
            candles,
            start_idx=start_idx,
            end_idx=idx,
            side="LOW",
            target_price=candle.open,
            search_radius=search_radius,
            tolerance=tolerance,
            min_hits=config.min_hits,
            min_age_bars=config.min_age_bars,
        )
        equal_highs = detect_equal_levels_near(
            candles,
            start_idx=start_idx,
            end_idx=idx,
            side="HIGH",
            target_price=candle.open,
            search_radius=search_radius,
            tolerance=tolerance,
            min_hits=config.min_hits,
            min_age_bars=config.min_age_bars,
        )
        for level, cluster_count, age in equal_lows:
            if abs(candle.open - level) > proximity:
                continue
            if candle.low < level - sweep_buffer:
                if _retired_match(retired_lows, idx=idx, level=level, config=config):
                    continue
                depth = abs(level - candle.low) / max(abs(level), 1e-9)
                depth_atr = ((level - sweep_buffer) - candle.low) / atr_value
                events.append(
                    SweepEvent(
                        event_id=f"{config.symbol}-{config.timeframe}-{idx}-LOW-{level:.2f}",
                        symbol=config.symbol,
                        timeframe=config.timeframe,
                        detection_bar=idx,
                        direction="LONG",
                        sweep_side="LOW",
                        level=float(level),
                        atr=atr_value,
                        sweep_depth_pct=depth,
                        sweep_depth_atr=depth_atr,
                        cluster_count=cluster_count,
                        level_age_bars=age,
                    )
                )
                retired_lows.append((idx, level))
                break
        for level, cluster_count, age in equal_highs:
            if abs(candle.open - level) > proximity:
                continue
            if candle.high > level + sweep_buffer:
                if _retired_match(retired_highs, idx=idx, level=level, config=config):
                    continue
                depth = abs(candle.high - level) / max(abs(level), 1e-9)
                depth_atr = (candle.high - (level + sweep_buffer)) / atr_value
                events.append(
                    SweepEvent(
                        event_id=f"{config.symbol}-{config.timeframe}-{idx}-HIGH-{level:.2f}",
                        symbol=config.symbol,
                        timeframe=config.timeframe,
                        detection_bar=idx,
                        direction="SHORT",
                        sweep_side="HIGH",
                        level=float(level),
                        atr=atr_value,
                        sweep_depth_pct=depth,
                        sweep_depth_atr=depth_atr,
                        cluster_count=cluster_count,
                        level_age_bars=age,
                    )
                )
                retired_highs.append((idx, level))
                break
    return events


def is_reclaim(candle: Candle, sweep: SweepEvent, config: DiagnosticConfig) -> bool:
    reclaim_buffer = config.reclaim_buf_atr * sweep.atr
    wick_min = config.wick_min_atr * sweep.atr
    body_low = min(candle.open, candle.close)
    body_high = max(candle.open, candle.close)
    if sweep.direction == "LONG":
        return candle.close > sweep.level + reclaim_buffer and (body_low - candle.low) >= wick_min
    return candle.close < sweep.level - reclaim_buffer and (candle.high - body_high) >= wick_min


def is_close_beyond(candle: Candle, sweep: SweepEvent) -> bool:
    if sweep.direction == "LONG":
        return candle.close > sweep.level
    return candle.close < sweep.level


def is_displacement(candle: Candle, atr_value: float | None, direction: str) -> bool:
    if atr_value is None or atr_value <= 0:
        return False
    candle_range = max(candle.high - candle.low, 1e-9)
    body = abs(candle.close - candle.open)
    if body / atr_value < 0.50:
        return False
    if candle_range / atr_value < 1.00:
        return False
    if direction == "LONG":
        return candle.close > candle.open and ((candle.close - candle.low) / candle_range) >= 0.65
    return candle.close < candle.open and ((candle.high - candle.close) / candle_range) >= 0.65


def cvd_divergence(candles: list[Candle], metadata: list[MetadataPoint], idx: int, direction: str, lookback: int) -> bool:
    start = max(0, idx - lookback + 1)
    if idx - start < 3:
        return False
    window = list(range(start, idx + 1))
    if direction == "LONG":
        prev_idx = min(window[:-1], key=lambda item: candles[item].low)
        return candles[idx].low <= candles[prev_idx].low and metadata[idx].cvd_cum > metadata[prev_idx].cvd_cum
    prev_idx = max(window[:-1], key=lambda item: candles[item].high)
    return candles[idx].high >= candles[prev_idx].high and metadata[idx].cvd_cum < metadata[prev_idx].cvd_cum


def cvd_absorption_proxy(candle: Candle, point: MetadataPoint, sweep: SweepEvent) -> bool:
    candle_range = max(candle.high - candle.low, 1e-9)
    if sweep.direction == "LONG":
        closes_off_low = (candle.close - candle.low) / candle_range >= 0.55
        return point.cvd < 0 and closes_off_low
    closes_off_high = (candle.high - candle.close) / candle_range >= 0.55
    return point.cvd > 0 and closes_off_high


def force_burst(point: MetadataPoint, config: DiagnosticConfig) -> bool:
    return point.force_count > 0 and point.force_z >= config.force_burst_z


def force_directional_burst(point: MetadataPoint, direction: str, config: DiagnosticConfig) -> bool:
    if not force_burst(point, config):
        return False
    if direction == "LONG":
        return point.force_sell_qty >= point.force_buy_qty
    return point.force_buy_qty >= point.force_sell_qty


def force_decay(metadata: list[MetadataPoint], idx: int, config: DiagnosticConfig) -> bool:
    if idx < config.force_decay_lookback:
        return False
    recent = [metadata[idx - offset].force_count for offset in range(config.force_decay_lookback, -1, -1)]
    return recent[0] > 0 and all(prev >= cur for prev, cur in zip(recent, recent[1:]))


def funding_supportive(point: MetadataPoint, direction: str) -> bool:
    return point.funding_rate <= 0 if direction == "LONG" else point.funding_rate >= 0


def oi_crowding(point: MetadataPoint) -> bool:
    return abs(point.oi_zscore) >= 1.5 or abs(point.oi_delta_pct) >= 0.01


def infer_direction(sweep: SweepEvent, point: MetadataPoint, cvd_div: bool, config: DiagnosticConfig) -> str | None:
    inferred: str | None = None
    if cvd_div:
        inferred = sweep.direction
    elif point.tfi > config.direction_tfi_threshold:
        inferred = "LONG"
    elif point.tfi < -config.direction_tfi_threshold:
        inferred = "SHORT"
    return inferred if inferred == sweep.direction else None


def confluence_score(
    *,
    sweep: SweepEvent,
    reclaim: bool,
    cvd_div: bool,
    point: MetadataPoint,
    force_spike: bool,
    funding_ok: bool,
    config: DiagnosticConfig,
) -> float:
    score = config.weight_sweep_detected
    if reclaim:
        score += config.weight_reclaim_confirmed
    if cvd_div:
        score += config.weight_cvd_divergence
    if sweep.direction == "LONG" and point.tfi >= config.tfi_impulse_threshold:
        score += config.weight_tfi_impulse
    if sweep.direction == "SHORT" and point.tfi <= -config.tfi_impulse_threshold:
        score += config.weight_tfi_impulse
    if force_spike:
        score += config.weight_force_order_spike
    if funding_ok:
        score += config.weight_funding_supportive
    return score


def current_bot_blocked_by(
    *,
    sweep: SweepEvent,
    reclaim: bool,
    direction_resolved: bool,
    score: float,
    config: DiagnosticConfig,
) -> str | None:
    if sweep.sweep_depth_pct < config.min_sweep_depth_pct:
        return "sweep_too_shallow"
    if not reclaim:
        return "no_reclaim"
    if not direction_resolved:
        return "direction_unresolved"
    if score < config.confluence_min:
        return "confluence_below_min"
    return None


def favorable_move_from_price(candles: list[Candle], *, start: int, end: int, direction: str, reference_price: float) -> float | None:
    if start >= len(candles) or end < start:
        return None
    end = min(end, len(candles) - 1)
    if direction == "LONG":
        best = max(candle.high for candle in candles[start : end + 1])
        return (best - reference_price) / max(reference_price, 1e-9)
    best = min(candle.low for candle in candles[start : end + 1])
    return (reference_price - best) / max(reference_price, 1e-9)


def adverse_move_from_price(candles: list[Candle], *, start: int, end: int, direction: str, reference_price: float) -> float | None:
    if start >= len(candles) or end < start:
        return None
    end = min(end, len(candles) - 1)
    if direction == "LONG":
        worst = min(candle.low for candle in candles[start : end + 1])
        return (reference_price - worst) / max(reference_price, 1e-9)
    worst = max(candle.high for candle in candles[start : end + 1])
    return (worst - reference_price) / max(reference_price, 1e-9)


def time_to_mfe(candles: list[Candle], *, start: int, end: int, direction: str) -> int | None:
    if start >= len(candles) or end < start:
        return None
    end = min(end, len(candles) - 1)
    if direction == "LONG":
        best = max(candles[idx].high for idx in range(start, end + 1))
        for idx in range(start, end + 1):
            if candles[idx].high == best:
                return idx - start
    else:
        best = min(candles[idx].low for idx in range(start, end + 1))
        for idx in range(start, end + 1):
            if candles[idx].low == best:
                return idx - start
    return None


def forward_metrics(
    candles: list[Candle],
    *,
    start_bar: int,
    direction: str,
    windows: Iterable[int],
    cost_pct: float,
) -> dict[str, float | None]:
    metrics: dict[str, float | None] = {}
    if start_bar >= len(candles):
        for window in windows:
            metrics[f"return_{window}"] = None
            metrics[f"net_return_{window}"] = None
            metrics[f"mfe_{window}"] = None
            metrics[f"mae_{window}"] = None
            metrics[f"time_to_mfe_{window}"] = None
        return metrics
    entry = candles[start_bar].open
    for window in windows:
        end = start_bar + window
        if end >= len(candles):
            metrics[f"return_{window}"] = None
            metrics[f"net_return_{window}"] = None
            metrics[f"mfe_{window}"] = None
            metrics[f"mae_{window}"] = None
            metrics[f"time_to_mfe_{window}"] = None
            continue
        exit_close = candles[end].close
        signed = (exit_close - entry) / max(entry, 1e-9)
        if direction == "SHORT":
            signed *= -1
        metrics[f"return_{window}"] = signed
        metrics[f"net_return_{window}"] = signed - cost_pct
        metrics[f"mfe_{window}"] = favorable_move_from_price(
            candles,
            start=start_bar,
            end=end,
            direction=direction,
            reference_price=entry,
        )
        metrics[f"mae_{window}"] = adverse_move_from_price(
            candles,
            start=start_bar,
            end=end,
            direction=direction,
            reference_price=entry,
        )
        metrics[f"time_to_mfe_{window}"] = time_to_mfe(candles, start=start_bar, end=end, direction=direction)
    return metrics


def add_state(
    observations: list[StateObservation],
    *,
    seen: set[str],
    state_name: str,
    sweep: SweepEvent,
    candles: list[Candle],
    state_known_bar: int,
    known_state_flags: list[str],
    blocked_by: str | None,
    candidate_generated: bool,
    score: float | None,
    config: DiagnosticConfig,
    metadata: dict[str, Any] | None = None,
) -> None:
    if state_name in seen or state_known_bar >= len(candles):
        return
    entry_bar = state_known_bar + 1
    if entry_bar >= len(candles):
        return
    seen.add(state_name)
    detection_price = candles[sweep.detection_bar].close
    state_price = candles[state_known_bar].close
    horizon_end = min(len(candles) - 1, sweep.detection_bar + max(config.forward_windows))
    mfe_before = favorable_move_from_price(
        candles,
        start=sweep.detection_bar,
        end=state_known_bar,
        direction=sweep.direction,
        reference_price=detection_price,
    )
    total_mfe = favorable_move_from_price(
        candles,
        start=sweep.detection_bar,
        end=horizon_end,
        direction=sweep.direction,
        reference_price=detection_price,
    )
    forward = forward_metrics(
        candles,
        start_bar=entry_bar,
        direction=sweep.direction,
        windows=config.forward_windows,
        cost_pct=config.round_trip_cost_pct,
    )
    after_20 = forward.get("mfe_20")
    consumed = None
    if mfe_before is not None and total_mfe is not None and total_mfe > 1e-12:
        consumed = min(max(mfe_before / total_mfe, 0.0), 10.0)
    observations.append(
        StateObservation(
            event_id=sweep.event_id,
            symbol=sweep.symbol,
            timeframe=sweep.timeframe,
            state_name=state_name,
            direction=sweep.direction,
            sweep_side=sweep.sweep_side,
            sweep_level=sweep.level,
            sweep_depth_pct=sweep.sweep_depth_pct,
            detection_bar=sweep.detection_bar,
            state_known_bar=state_known_bar,
            entry_candidate_bar=entry_bar,
            return_start_bar=entry_bar,
            k=state_known_bar - sweep.detection_bar,
            detection_time_utc=candles[sweep.detection_bar].open_time.isoformat(),
            state_known_time_utc=candles[state_known_bar].open_time.isoformat(),
            entry_candidate_time_utc=candles[entry_bar].open_time.isoformat(),
            current_bot_blocked_by=blocked_by,
            current_bot_candidate_generated=candidate_generated,
            trial_00095_candidate_state=state_name == STATE_TRIAL_CANDIDATE or candidate_generated,
            confluence_score=score,
            known_state_flags=known_state_flags,
            metadata=metadata or {},
            forward_entry=forward,
            forward_detection_audit=forward_metrics(
                candles,
                start_bar=sweep.detection_bar,
                direction=sweep.direction,
                windows=config.forward_windows,
                cost_pct=config.round_trip_cost_pct,
            ),
            mfe_before_state=mfe_before,
            mfe_after_state_20=after_20,
            mae_after_state_20=forward.get("mae_20"),
            mfe_consumed_pct=consumed,
        )
    )
    _ = state_price


def build_state_observations(
    candles: list[Candle],
    sweeps: list[SweepEvent],
    atr: list[float | None],
    metadata_points: list[MetadataPoint],
    config: DiagnosticConfig,
) -> list[StateObservation]:
    observations: list[StateObservation] = []
    for sweep in sweeps:
        seen: set[str] = set()
        max_idx = min(len(candles) - 2, sweep.detection_bar + config.max_post_bars)
        reclaim_seen = False
        for idx in range(sweep.detection_bar, max_idx + 1):
            candle = candles[idx]
            point = metadata_points[idx] if idx < len(metadata_points) else MetadataPoint()
            reclaim = is_reclaim(candle, sweep, config)
            if reclaim:
                reclaim_seen = True
            close_beyond = is_close_beyond(candle, sweep)
            displacement = is_displacement(candle, atr[idx], sweep.direction)
            cvd_div = cvd_divergence(candles, metadata_points, idx, sweep.direction, config.cvd_divergence_bars)
            absorption = cvd_absorption_proxy(candle, point, sweep)
            burst = force_burst(point, config)
            directional_burst = force_directional_burst(point, sweep.direction, config)
            decay = force_decay(metadata_points, idx, config)
            funding_ok = funding_supportive(point, sweep.direction)
            oi_ok = oi_crowding(point)
            oi_funding_ok = oi_ok and funding_ok
            direction = infer_direction(sweep, point, cvd_div, config)
            direction_resolved = direction == sweep.direction
            tfi_aligned = point.tfi >= config.direction_tfi_threshold if sweep.direction == "LONG" else point.tfi <= -config.direction_tfi_threshold
            tfi_impulse = point.tfi >= config.tfi_impulse_threshold if sweep.direction == "LONG" else point.tfi <= -config.tfi_impulse_threshold
            score = confluence_score(
                sweep=sweep,
                reclaim=reclaim,
                cvd_div=cvd_div,
                point=point,
                force_spike=burst,
                funding_ok=funding_ok,
                config=config,
            )
            blocked_by = current_bot_blocked_by(
                sweep=sweep,
                reclaim=reclaim,
                direction_resolved=direction_resolved,
                score=score,
                config=config,
            )
            candidate = blocked_by is None
            flags = [
                name
                for name, enabled in (
                    ("raw_sweep", idx == sweep.detection_bar),
                    ("deep_sweep", sweep.sweep_depth_pct >= config.min_sweep_depth_pct),
                    ("near_miss_depth", config.near_miss_depth_pct <= sweep.sweep_depth_pct < config.min_sweep_depth_pct),
                    ("reclaim", reclaim),
                    ("close_beyond", close_beyond),
                    ("displacement", displacement),
                    ("tfi_aligned", tfi_aligned),
                    ("tfi_impulse", tfi_impulse),
                    ("cvd_divergence", cvd_div),
                    ("cvd_absorption", absorption),
                    ("force_burst", burst),
                    ("force_directional", directional_burst),
                    ("force_decay", decay),
                    ("funding_supportive", funding_ok),
                    ("oi_crowding", oi_ok),
                    ("oi_funding", oi_funding_ok),
                    ("direction_resolved", direction_resolved),
                    ("confluence_threshold", score >= config.confluence_min),
                    ("trial_candidate", candidate),
                )
                if enabled
            ]
            state_meta = {
                "tfi": point.tfi,
                "cvd": point.cvd,
                "cvd_cum": point.cvd_cum,
                "force_count": point.force_count,
                "force_z": point.force_z,
                "funding_rate": point.funding_rate,
                "oi_delta_pct": point.oi_delta_pct,
                "oi_zscore": point.oi_zscore,
                "cluster_count": sweep.cluster_count,
                "level_age_bars": sweep.level_age_bars,
            }
            if idx == sweep.detection_bar:
                add_state(
                    observations,
                    seen=seen,
                    state_name=STATE_RAW_SWEEP,
                    sweep=sweep,
                    candles=candles,
                    state_known_bar=idx,
                    known_state_flags=flags,
                    blocked_by=blocked_by,
                    candidate_generated=candidate,
                    score=score,
                    config=config,
                    metadata=state_meta,
                )
                if sweep.cluster_count >= config.min_hits:
                    add_state(
                        observations,
                        seen=seen,
                        state_name=STATE_LEVEL_QUALITY,
                        sweep=sweep,
                        candles=candles,
                        state_known_bar=idx,
                        known_state_flags=flags,
                        blocked_by=blocked_by,
                        candidate_generated=candidate,
                        score=score,
                        config=config,
                        metadata=state_meta,
                    )
                if sweep.sweep_depth_pct >= config.min_sweep_depth_pct:
                    add_state(
                        observations,
                        seen=seen,
                        state_name=STATE_DEEP_SWEEP,
                        sweep=sweep,
                        candles=candles,
                        state_known_bar=idx,
                        known_state_flags=flags,
                        blocked_by=blocked_by,
                        candidate_generated=candidate,
                        score=score,
                        config=config,
                        metadata=state_meta,
                    )
                elif sweep.sweep_depth_pct >= config.near_miss_depth_pct:
                    add_state(
                        observations,
                        seen=seen,
                        state_name=STATE_SHALLOW_NEAR_MISS,
                        sweep=sweep,
                        candles=candles,
                        state_known_bar=idx,
                        known_state_flags=flags,
                        blocked_by=blocked_by,
                        candidate_generated=candidate,
                        score=score,
                        config=config,
                        metadata=state_meta,
                    )
                if blocked_by == "sweep_too_shallow":
                    add_state(
                        observations,
                        seen=seen,
                        state_name=STATE_REJECT_SHALLOW,
                        sweep=sweep,
                        candles=candles,
                        state_known_bar=idx,
                        known_state_flags=flags,
                        blocked_by=blocked_by,
                        candidate_generated=candidate,
                        score=score,
                        config=config,
                        metadata=state_meta,
                    )
                if blocked_by == "no_reclaim":
                    add_state(
                        observations,
                        seen=seen,
                        state_name=STATE_REJECT_NO_RECLAIM,
                        sweep=sweep,
                        candles=candles,
                        state_known_bar=idx,
                        known_state_flags=flags,
                        blocked_by=blocked_by,
                        candidate_generated=candidate,
                        score=score,
                        config=config,
                        metadata=state_meta,
                    )
                if blocked_by == "direction_unresolved":
                    add_state(
                        observations,
                        seen=seen,
                        state_name=STATE_REJECT_DIRECTION,
                        sweep=sweep,
                        candles=candles,
                        state_known_bar=idx,
                        known_state_flags=flags,
                        blocked_by=blocked_by,
                        candidate_generated=candidate,
                        score=score,
                        config=config,
                        metadata=state_meta,
                    )
                if blocked_by == "confluence_below_min":
                    add_state(
                        observations,
                        seen=seen,
                        state_name=STATE_REJECT_CONFLUENCE,
                        sweep=sweep,
                        candles=candles,
                        state_known_bar=idx,
                        known_state_flags=flags,
                        blocked_by=blocked_by,
                        candidate_generated=candidate,
                        score=score,
                        config=config,
                        metadata=state_meta,
                    )
            for state_name, condition in (
                (STATE_RECLAIM, reclaim),
                (STATE_CLOSE_BEYOND, close_beyond),
                (STATE_DISPLACEMENT, displacement),
                (STATE_DIRECTION, direction_resolved),
                (STATE_TFI_ALIGNED, tfi_aligned),
                (STATE_TFI_IMPULSE, tfi_impulse),
                (STATE_CVD_DIVERGENCE, cvd_div),
                (STATE_CVD_ABSORPTION, absorption),
                (STATE_FORCE_BURST, burst),
                (STATE_FORCE_DIRECTIONAL, directional_burst),
                (STATE_FORCE_DECAY, decay),
                (STATE_FUNDING_SUPPORT, funding_ok),
                (STATE_OI_CROWDING, oi_ok),
                (STATE_OI_FUNDING, oi_funding_ok),
                (STATE_CONFLUENCE, score >= config.confluence_min),
                (STATE_TRIAL_CANDIDATE, candidate),
            ):
                if condition:
                    add_state(
                        observations,
                        seen=seen,
                        state_name=state_name,
                        sweep=sweep,
                        candles=candles,
                        state_known_bar=idx,
                        known_state_flags=flags,
                        blocked_by=blocked_by,
                        candidate_generated=candidate,
                        score=score,
                        config=config,
                        metadata=state_meta,
                    )
            k = idx - sweep.detection_bar
            if k in {1, 2, 3, 4} and not reclaim_seen:
                add_state(
                    observations,
                    seen=seen,
                    state_name={
                        1: STATE_NO_RECLAIM_1,
                        2: STATE_NO_RECLAIM_2,
                        3: STATE_NO_RECLAIM_3,
                        4: STATE_NO_RECLAIM_4,
                    }[k],
                    sweep=sweep,
                    candles=candles,
                    state_known_bar=idx,
                    known_state_flags=flags,
                    blocked_by=blocked_by,
                    candidate_generated=candidate,
                    score=score,
                    config=config,
                    metadata=state_meta,
                )
    return observations


def _values(observations: Iterable[StateObservation], key: str, *, audit: bool = False) -> list[float]:
    values: list[float] = []
    for observation in observations:
        bucket = observation.forward_detection_audit if audit else observation.forward_entry
        value = bucket.get(key)
        if value is not None:
            values.append(float(value))
    return values


def _attrs(observations: Iterable[StateObservation], attr: str) -> list[float]:
    values: list[float] = []
    for observation in observations:
        value = getattr(observation, attr)
        if value is not None:
            values.append(float(value))
    return values


def _profit_factor(values: list[float]) -> float | None:
    if not values:
        return None
    gross_profit = sum(value for value in values if value > 0)
    gross_loss = abs(sum(value for value in values if value < 0))
    if gross_loss == 0:
        return float("inf") if gross_profit > 0 else 0.0
    return gross_profit / gross_loss


def _max_drawdown(values: list[float]) -> float | None:
    if not values:
        return None
    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    for value in values:
        equity += value
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
    return max_dd


def summarize_observations(observations: list[StateObservation], config: DiagnosticConfig) -> dict[str, Any]:
    grouped: dict[str, list[StateObservation]] = defaultdict(list)
    for observation in observations:
        grouped[observation.state_name].append(observation)
    summary: dict[str, Any] = {}
    for state_name in sorted(grouped):
        rows = grouped[state_name]
        state_summary: dict[str, Any] = {
            "count": len(rows),
            "median_k_to_state": median([row.k for row in rows]) if rows else None,
            "candidate_overlap_rate": mean([1.0 if row.trial_00095_candidate_state else 0.0 for row in rows]) if rows else None,
            "mfe_before_state_median": median(_attrs(rows, "mfe_before_state")) if _attrs(rows, "mfe_before_state") else None,
            "mfe_after_state_20_median": median(_attrs(rows, "mfe_after_state_20")) if _attrs(rows, "mfe_after_state_20") else None,
            "mae_after_state_20_median": median(_attrs(rows, "mae_after_state_20")) if _attrs(rows, "mae_after_state_20") else None,
            "mfe_consumed_pct_median": median(_attrs(rows, "mfe_consumed_pct")) if _attrs(rows, "mfe_consumed_pct") else None,
        }
        for window in config.forward_windows:
            net_key = f"net_return_{window}"
            gross_key = f"return_{window}"
            mfe_key = f"mfe_{window}"
            mae_key = f"mae_{window}"
            ttm_key = f"time_to_mfe_{window}"
            net_values = _values(rows, net_key)
            gross_values = _values(rows, gross_key)
            detection_net_values = _values(rows, net_key, audit=True)
            mfe_values = _values(rows, mfe_key)
            mae_values = _values(rows, mae_key)
            ttm_values = _values(rows, ttm_key)
            state_summary[f"entry_{window}_net_return_median"] = median(net_values) if net_values else None
            state_summary[f"entry_{window}_net_return_avg"] = mean(net_values) if net_values else None
            state_summary[f"entry_{window}_gross_return_median"] = median(gross_values) if gross_values else None
            state_summary[f"detection_{window}_net_return_median_audit"] = median(detection_net_values) if detection_net_values else None
            state_summary[f"entry_{window}_win_rate"] = mean([1.0 if value > 0 else 0.0 for value in net_values]) if net_values else None
            state_summary[f"entry_{window}_pf_proxy"] = _profit_factor(net_values)
            state_summary[f"entry_{window}_max_dd_return_proxy"] = _max_drawdown(net_values)
            state_summary[f"entry_{window}_mfe_median"] = median(mfe_values) if mfe_values else None
            state_summary[f"entry_{window}_mae_median"] = median(mae_values) if mae_values else None
            state_summary[f"entry_{window}_time_to_mfe_median"] = median(ttm_values) if ttm_values else None
        summary[state_name] = state_summary
    return summary


def deterministic_control(
    observations: list[StateObservation],
    candles: list[Candle],
    config: DiagnosticConfig,
) -> dict[str, Any]:
    source = [row for row in observations if row.state_name in DECISION_STATES]
    usable = len(candles) - max(config.forward_windows) - 2
    pseudo: list[StateObservation] = []
    if usable <= 0:
        return {"method": "deterministic_shift_control", "count": 0, "summary": {}}
    seen_keys: set[tuple[str, int]] = set()
    for row in source:
        shifted = (row.entry_candidate_bar + config.deterministic_control_shift_bars) % usable
        if shifted <= 0:
            shifted = 1
        key = (row.state_name, shifted)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        pseudo_row = StateObservation(
            event_id=f"control-{row.event_id}",
            symbol=row.symbol,
            timeframe=row.timeframe,
            state_name=row.state_name,
            direction=row.direction,
            sweep_side=row.sweep_side,
            sweep_level=row.sweep_level,
            sweep_depth_pct=row.sweep_depth_pct,
            detection_bar=shifted,
            state_known_bar=shifted,
            entry_candidate_bar=shifted,
            return_start_bar=shifted,
            k=0,
            detection_time_utc=candles[shifted].open_time.isoformat(),
            state_known_time_utc=candles[shifted].open_time.isoformat(),
            entry_candidate_time_utc=candles[shifted].open_time.isoformat(),
            current_bot_blocked_by=None,
            current_bot_candidate_generated=False,
            trial_00095_candidate_state=False,
            confluence_score=None,
            known_state_flags=["deterministic_control"],
            metadata={},
            forward_entry=forward_metrics(
                candles,
                start_bar=shifted,
                direction=row.direction,
                windows=config.forward_windows,
                cost_pct=config.round_trip_cost_pct,
            ),
            forward_detection_audit={},
        )
        pseudo.append(pseudo_row)
    return {
        "method": "deterministic_shift_control",
        "shift_bars": config.deterministic_control_shift_bars,
        "count": len(pseudo),
        "summary": summarize_observations(pseudo, config),
    }


def walk_forward_summary(observations: list[StateObservation], candles: list[Candle], config: DiagnosticConfig) -> dict[str, Any]:
    if not observations or not candles:
        return {"folds": []}
    start_ts = candles[0].open_time.timestamp()
    end_ts = candles[-1].open_time.timestamp()
    fold_seconds = (end_ts - start_ts) / 4
    folds: list[dict[str, Any]] = []
    for fold_idx in range(4):
        fold_start = start_ts + fold_seconds * fold_idx
        fold_end = start_ts + fold_seconds * (fold_idx + 1)
        fold_rows = [
            row
            for row in observations
            if fold_start <= candles[row.entry_candidate_bar].open_time.timestamp() < fold_end
            and row.state_name in DECISION_STATES
        ]
        best = best_state(summarize_observations(fold_rows, config), window=5)
        folds.append(
            {
                "fold": fold_idx + 1,
                "count": len(fold_rows),
                "best_state": best.get("state_name"),
                "best_entry_5_net_median": best.get("entry_5_net_return_median"),
                "best_entry_5_pf_proxy": best.get("entry_5_pf_proxy"),
            }
        )
    return {"folds": folds}


def best_state(summary: dict[str, Any], *, window: int) -> dict[str, Any]:
    candidates: list[tuple[float, str, dict[str, Any]]] = []
    for state_name, row in summary.items():
        if state_name not in DECISION_STATES:
            continue
        value = row.get(f"entry_{window}_net_return_median")
        count = int(row.get("count") or 0)
        if value is None or count < 1:
            continue
        candidates.append((float(value), state_name, row))
    if not candidates:
        return {}
    value, state_name, row = max(candidates, key=lambda item: item[0])
    return {"state_name": state_name, **row, "best_metric": value}


def invalidation_and_decision(
    summary: dict[str, Any],
    control: dict[str, Any],
    wf: dict[str, Any],
    config: DiagnosticConfig,
) -> dict[str, Any]:
    best = best_state(summary, window=5)
    raw = summary.get(STATE_RAW_SWEEP, {})
    trial = summary.get(STATE_TRIAL_CANDIDATE, {})
    control_state_summary = (control.get("summary") or {})
    control_best = best_state(control_state_summary, window=5)
    risks: list[str] = []
    warnings: list[str] = []

    if not best:
        risks.append("FAIL: no decision state produced usable entry-timed metrics.")
        return {"decision": "INCONCLUSIVE_DATA_GAP", "risks": risks, "warnings": warnings, "best_state": best}

    best_state_name = str(best["state_name"])
    best_count = int(best.get("count") or 0)
    best_net = best.get("entry_5_net_return_median")
    best_pf = best.get("entry_5_pf_proxy")
    best_win = best.get("entry_5_win_rate")
    best_consumed = best.get("mfe_consumed_pct_median")
    best_detection = best.get("detection_5_net_return_median_audit")
    raw_net = raw.get("entry_5_net_return_median")
    trial_net = trial.get("entry_5_net_return_median")
    control_net = control_best.get("entry_5_net_return_median")

    if best_count < 300:
        risks.append("FAIL: best state sample size below 300.")
    if best_net is None or best_net <= 0:
        risks.append("FAIL: no early knowable state has positive median net return after costs.")
    if best_win is not None and best_win <= 0.51:
        risks.append("FAIL: best state win rate is approximately random after entry timing.")
    if best_consumed is not None and best_consumed >= 0.70:
        risks.append("FAIL: MFE is mostly consumed before best state is knowable.")
    if best_detection is not None and best_net is not None and best_detection > 0 and best_net <= 0:
        risks.append("FAIL: apparent edge exists only from detection-bar audit timing.")
    if control_net is not None and best_net is not None and best_net <= control_net:
        risks.append("FAIL: best state does not beat deterministic shifted control.")
    if raw_net is not None and best_net is not None and best_state_name != STATE_RAW_SWEEP and best_net <= raw_net:
        risks.append("FAIL: best state does not beat sweep-only cohort.")
    if trial_net is not None and best_net is not None and best_state_name != STATE_TRIAL_CANDIDATE and best_net <= trial_net:
        warnings.append("WARN: best non-trial state does not beat trial-00095 candidate proxy.")
    if best_state_name == STATE_TRIAL_CANDIDATE:
        warnings.append("WARN: best state is trial-00095 candidate proxy; no new edge family indicated.")
    if best_pf is not None and best_pf < 1.2:
        risks.append("FAIL: best state PF proxy is too weak after costs.")
    positive_folds = sum(
        1
        for fold in wf.get("folds", [])
        if fold.get("best_entry_5_net_median") is not None and fold.get("best_entry_5_net_median") > 0
    )
    if wf.get("folds") and positive_folds < 2:
        risks.append("FAIL: fewer than 2 of 4 walk-forward folds are positive.")

    if risks:
        if best_count < 100:
            decision = "INCONCLUSIVE_DATA_GAP"
        elif any("control" in risk for risk in risks):
            decision = "REJECT_RESULTS_METHOD_INVALID"
        else:
            decision = "STOP_SMC_RESEARCH_TRIAL_00095_ALREADY_OPTIMAL"
    elif best_state_name in {STATE_DISPLACEMENT, STATE_TFI_IMPULSE, STATE_TFI_ALIGNED}:
        decision = "PLAN_ONE_DISPLACEMENT_ENTRY_STRATEGY"
    elif best_state_name in {STATE_CVD_DIVERGENCE, STATE_CVD_ABSORPTION, STATE_FORCE_BURST, STATE_FORCE_DIRECTIONAL}:
        decision = "PLAN_ONE_ORDER_FLOW_CLASSIFICATION_STRATEGY"
    elif best_state_name in {STATE_FORCE_DECAY, STATE_OI_CROWDING, STATE_OI_FUNDING, STATE_FUNDING_SUPPORT}:
        decision = "PLAN_ONE_LIQUIDATION_UNWIND_STRATEGY"
    elif best_state_name == STATE_TRIAL_CANDIDATE:
        decision = "STOP_SMC_RESEARCH_TRIAL_00095_ALREADY_OPTIMAL"
    else:
        decision = "STOP_SMC_RESEARCH_TRIAL_00095_ALREADY_OPTIMAL"

    return {
        "decision": decision,
        "risks": risks,
        "warnings": warnings,
        "best_state": best,
        "raw_sweep_reference": raw,
        "trial_00095_candidate_proxy_reference": trial,
        "control_best_reference": control_best,
    }


def json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): json_ready(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_ready(item) for item in value]
    if hasattr(value, "__dataclass_fields__"):
        return json_ready(asdict(value))
    if isinstance(value, float) and (math.isinf(value) or math.isnan(value)):
        return str(value)
    return value


def render_report(payload: dict[str, Any]) -> str:
    def fmt(value: Any) -> str:
        if value is None:
            return "n/a"
        if isinstance(value, float):
            if math.isinf(value):
                return "inf"
            return f"{value:.6f}"
        return str(value)

    summary = payload["state_summary"]
    invalidation = payload["invalidation_checks"]
    best = invalidation.get("best_state") or {}
    lines = [
        "# MFE Accessibility Earliest Knowable Signal V1",
        "",
        f"Generated: `{payload['manifest']['generated_at_utc']}`",
        "",
        "## Scope",
        "",
        "Research-only diagnostic. No production code, FeatureEngine, SignalEngine, Governance, Risk, settings, execution, or DB schema changes.",
        "",
        "## Final Decision",
        "",
        f"`{invalidation['decision']}`",
        "",
        "## Dataset",
        "",
        f"- DB: `{payload['manifest']['db_path']}`",
        f"- Symbol/timeframe: `{payload['config']['symbol']} {payload['config']['timeframe']}`",
        f"- Candle rows: {payload['data_quality']['rows']}",
        f"- Sweep events: {payload['sweep_events_total']}",
        f"- State observations: {payload['state_observations_total']}",
        f"- Metadata rows: aggtrade={payload['data_quality']['aggtrade_15m_rows']}, force_orders={payload['data_quality']['force_order_rows']}, funding={payload['data_quality']['funding_rows']}, OI={payload['data_quality']['open_interest_rows']}",
        "",
        "## Best State",
        "",
        f"- State: `{best.get('state_name', 'n/a')}`",
        f"- Count: {best.get('count', 'n/a')}",
        f"- Median k to state: {fmt(best.get('median_k_to_state'))}",
        f"- Entry 5-bar net median: {fmt(best.get('entry_5_net_return_median'))}",
        f"- Entry 5-bar PF proxy: {fmt(best.get('entry_5_pf_proxy'))}",
        f"- Entry 5-bar win rate: {fmt(best.get('entry_5_win_rate'))}",
        f"- MFE consumed before state: {fmt(best.get('mfe_consumed_pct_median'))}",
        f"- Detection 5-bar net median audit-only: {fmt(best.get('detection_5_net_return_median_audit'))}",
        "",
        "## State Cohorts",
        "",
        "| State | Count | k med | Entry 5 net med | Entry 5 PF | Entry 5 win | MFE consumed | Trial overlap |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for state_name, row in sorted(summary.items(), key=lambda item: (-(item[1].get("count") or 0), item[0]))[:40]:
        lines.append(
            f"| {state_name} | {row.get('count', 0)} | {fmt(row.get('median_k_to_state'))} | "
            f"{fmt(row.get('entry_5_net_return_median'))} | {fmt(row.get('entry_5_pf_proxy'))} | "
            f"{fmt(row.get('entry_5_win_rate'))} | {fmt(row.get('mfe_consumed_pct_median'))} | "
            f"{fmt(row.get('candidate_overlap_rate'))} |"
        )
    lines.extend(
        [
            "",
            "## References",
            "",
            f"- Trial-00095 PF reference: {TRIAL_00095_REFERENCE['profit_factor']}",
            f"- V1 raw wick cross median 5-bar: {TRIAL_00095_REFERENCE['v1_raw_wick_cross_median_5']}",
            f"- V1 delayed reclaim label-available median 5-bar: {TRIAL_00095_REFERENCE['v1_delayed_reclaim_label_median_5']}",
            f"- SMC entry 5-bar net median: {TRIAL_00095_REFERENCE['smc_entry_5_net_median']}",
            "",
            "## Invalidation Checks",
            "",
        ]
    )
    if invalidation.get("risks"):
        lines.extend(f"- {risk}" for risk in invalidation["risks"])
    else:
        lines.append("- No hard invalidation risk triggered by configured checks.")
    if invalidation.get("warnings"):
        lines.append("")
        lines.append("## Warnings")
        lines.append("")
        lines.extend(f"- {warning}" for warning in invalidation["warnings"])
    lines.extend(
        [
            "",
            "## Timing Discipline",
            "",
            "- Primary returns are measured from `entry_candidate_bar`.",
            "- Detection-bar returns are audit-only.",
            "- Every delayed state has its own `state_known_bar`.",
            "",
            "## Non-Goals Confirmed",
            "",
            "- No strategy implementation.",
            "- No production code changes.",
            "- No FeatureEngine or SignalEngine changes.",
            "- No rescue of V1 taxonomy or failed SMC mitigation entry.",
        ]
    )
    return "\n".join(lines) + "\n"


def run_analysis(
    *,
    db_path: Path,
    output_path: Path,
    report_path: Path,
    config: DiagnosticConfig,
    start: datetime | None = None,
    end: datetime | None = None,
) -> dict[str, Any]:
    with sqlite3.connect(db_path) as conn:
        candles = load_candles(conn, symbol=config.symbol, timeframe=config.timeframe, start=start, end=end)
        metadata, metadata_counts = compute_metadata(conn, candles=candles, config=config)
    quality = validate_candles(candles, metadata_counts=metadata_counts)
    atr = compute_atr_series(candles, config.atr_period)
    sweeps = detect_sweep_events(candles, atr, config)
    observations = build_state_observations(candles, sweeps, atr, metadata, config)
    summary = summarize_observations(observations, config)
    control = deterministic_control(observations, candles, config)
    wf = walk_forward_summary(observations, candles, config)
    invalidation = invalidation_and_decision(summary, control, wf, config)
    truncated = len(observations) > config.max_json_rows
    payload = {
        "manifest": {
            "milestone": "MFE_ACCESSIBILITY_EARLIEST_KNOWABLE_SIGNAL_V1",
            "research_only": True,
            "production_changes": False,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "db_path": str(db_path),
            "output_path": str(output_path),
            "report_path": str(report_path),
        },
        "config": asdict(config),
        "data_quality": asdict(quality),
        "sweep_events_total": len(sweeps),
        "state_observations_total": len(observations),
        "state_counts": dict(Counter(row.state_name for row in observations)),
        "rejected_state_counts": dict(Counter(row.current_bot_blocked_by or "candidate" for row in observations)),
        "state_summary": summary,
        "control_cohort": control,
        "walk_forward": wf,
        "invalidation_checks": invalidation,
        "trial_00095_reference": TRIAL_00095_REFERENCE,
        "rows_truncated": truncated,
        "state_rows": [asdict(row) for row in observations[: config.max_json_rows]],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(json_ready(payload), indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(render_report(payload), encoding="utf-8")
    return payload


def parse_windows(raw: str) -> tuple[int, ...]:
    return tuple(int(part.strip()) for part in raw.split(",") if part.strip())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--report", type=Path, default=None)
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--timeframe", default="15m")
    parser.add_argument("--start")
    parser.add_argument("--end")
    parser.add_argument("--max-post-bars", type=int, default=20)
    parser.add_argument("--windows", default="3,5,10,20")
    parser.add_argument("--round-trip-cost-pct", type=float, default=0.0010)
    parser.add_argument("--max-json-rows", type=int, default=5000)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    date_tag = datetime.now(timezone.utc).date().isoformat()
    output = args.output or DEFAULT_OUTPUT_DIR / f"mfe_accessibility_earliest_knowable_signal_v1_{date_tag}.json"
    report = args.report or DEFAULT_REPORT_DIR / f"MFE_ACCESSIBILITY_EARLIEST_KNOWABLE_SIGNAL_V1_{date_tag}.md"
    config = DiagnosticConfig(
        symbol=args.symbol.upper(),
        timeframe=args.timeframe,
        max_post_bars=args.max_post_bars,
        forward_windows=parse_windows(args.windows),
        round_trip_cost_pct=args.round_trip_cost_pct,
        max_json_rows=args.max_json_rows,
    )
    payload = run_analysis(
        db_path=args.db,
        output_path=output,
        report_path=report,
        config=config,
        start=parse_ts(args.start) if args.start else None,
        end=parse_ts(args.end) if args.end else None,
    )
    print(json.dumps(json_ready({
        "decision": payload["invalidation_checks"]["decision"],
        "sweep_events_total": payload["sweep_events_total"],
        "state_observations_total": payload["state_observations_total"],
        "output": str(output),
        "report": str(report),
    }), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
