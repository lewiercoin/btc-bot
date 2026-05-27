#!/usr/bin/env python3
"""Research-only SMC sequence edge feasibility diagnostic.

Tests a minimal deterministic post-sweep sequence:

    equal-level liquidity sweep -> displacement -> local structure break
    -> FVG/imbalance -> mitigation/retest -> entry_candidate_bar

This script is intentionally isolated from the live trading path. It does not
import or modify FeatureEngine, SignalEngine, Governance, Risk, settings,
execution, or storage schema code.
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


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = PROJECT_ROOT / "research_lab" / "data" / "crowded_unwind_backtest.db"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "research_lab" / "analysis_output"
DEFAULT_REPORT_DIR = PROJECT_ROOT / "docs" / "analysis"

TRIAL_00095_REFERENCE = {
    "er": 2.1,
    "pf": 4.6,
    "raw_wick_cross_median_5": 0.000237,
    "delayed_reclaim_label_available_median_5": 0.000054,
    "true_breakout_label_available_median_5": -0.000268,
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
    duplicate_level_tolerance_pct: float = 0.0016
    duplicate_level_window_bars: int = 492
    swing_left: int = 2
    swing_right: int = 2
    displacement_body_atr: float = 0.50
    displacement_range_atr: float = 1.00
    displacement_close_percentile: float = 0.65
    displacement_window_bars: int = 6
    structure_window_bars: int = 10
    fvg_min_atr: float = 0.05
    fvg_window_bars: int = 8
    mitigation_window_bars: int = 20
    forward_windows: tuple[int, ...] = (3, 5, 10, 20)
    deterministic_control_shift_bars: int = 137
    round_trip_cost_pct: float = 0.0010
    max_json_events: int = 50000


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


@dataclass(frozen=True, slots=True)
class SwingPoint:
    side: str
    pivot_index: int
    confirmed_at_index: int
    price: float


@dataclass(frozen=True, slots=True)
class SweepEvent:
    symbol: str
    timeframe: str
    detection_bar: int
    direction: str
    sweep_side: str
    level: float
    atr: float
    sweep_depth_atr: float
    sequence_source: str = "equal_level"


@dataclass(frozen=True, slots=True)
class FVGZone:
    side: str
    center_bar: int
    created_bar: int
    zone_low: float
    zone_high: float
    gap_atr: float


@dataclass(slots=True)
class SequenceEvent:
    symbol: str
    timeframe: str
    direction: str
    sequence_source: str
    detection_bar: int
    displacement_bar: int
    structure_shift_bar: int
    fvg_created_bar: int
    confirmation_bar: int
    mitigation_bar: int
    entry_candidate_bar: int
    label_available_bar: int
    return_start_bar_detection: int
    return_start_bar_entry_candidate: int
    return_start_bar_label_available: int
    detection_time_utc: str
    entry_candidate_time_utc: str
    level: float
    sweep_side: str
    sweep_depth_atr: float
    structure_level: float
    fvg_zone_low: float
    fvg_zone_high: float
    fvg_gap_atr: float
    displacement_body_atr: float
    displacement_range_atr: float
    entry_price: float
    tfi_at_detection: float | None = None
    tfi_at_entry: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    forward_detection: dict[str, float | None] = field(default_factory=dict)
    forward_entry_candidate: dict[str, float | None] = field(default_factory=dict)
    forward_label_available: dict[str, float | None] = field(default_factory=dict)
    mfe_before_entry: float | None = None


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
    start: datetime | None,
    end: datetime | None,
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


def load_tfi(conn: sqlite3.Connection, *, symbol: str, timeframe: str) -> dict[datetime, float]:
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    if "aggtrade_buckets" not in tables:
        return {}
    rows = conn.execute(
        """
        SELECT bucket_time, tfi
        FROM aggtrade_buckets
        WHERE symbol = ? AND timeframe = ?
        ORDER BY bucket_time ASC
        """,
        (symbol, timeframe),
    ).fetchall()
    return {parse_ts(row[0]): float(row[1]) for row in rows}


def validate_candles(candles: list[Candle]) -> DataQuality:
    seen: set[datetime] = set()
    duplicate = 0
    non_monotonic = 0
    ohlc_violations = 0
    deltas: Counter[int] = Counter()
    previous: datetime | None = None
    for candle in candles:
        if candle.open_time in seen:
            duplicate += 1
        seen.add(candle.open_time)
        if previous is not None:
            delta = int((candle.open_time - previous).total_seconds())
            if delta <= 0:
                non_monotonic += 1
            else:
                deltas[delta] += 1
        if candle.high < max(candle.open, candle.close) or candle.low > min(candle.open, candle.close):
            ohlc_violations += 1
        previous = candle.open_time
    inferred_step = deltas.most_common(1)[0][0] if deltas else None
    gaps = 0
    if inferred_step:
        for delta, count in deltas.items():
            if delta > inferred_step:
                gaps += max(0, round(delta / inferred_step) - 1) * count
    return DataQuality(
        rows=len(candles),
        start_time_utc=candles[0].open_time.isoformat() if candles else None,
        end_time_utc=candles[-1].open_time.isoformat() if candles else None,
        duplicate_timestamps=duplicate,
        non_monotonic_timestamps=non_monotonic,
        ohlc_violations=ohlc_violations,
        missing_bar_gaps=gaps,
        inferred_step_seconds=inferred_step,
    )


def compute_atr_series(candles: list[Candle], period: int) -> list[float | None]:
    true_ranges: list[float] = []
    atr: list[float | None] = [None] * len(candles)
    previous_close: float | None = None
    for idx, candle in enumerate(candles):
        if previous_close is None:
            tr = candle.high - candle.low
        else:
            tr = max(candle.high - candle.low, abs(candle.high - previous_close), abs(candle.low - previous_close))
        true_ranges.append(tr)
        if len(true_ranges) >= period:
            atr[idx] = mean(true_ranges[-period:])
        previous_close = candle.close
    return atr


def detect_equal_levels(levels: list[tuple[int, float]], tolerance: float, min_hits: int, min_age_bars: int) -> list[float]:
    if not levels:
        return []
    clusters: list[list[tuple[int, float]]] = []
    current = [sorted(levels, key=lambda item: item[1])[0]]
    for item in sorted(levels, key=lambda item: item[1])[1:]:
        if abs(item[1] - current[-1][1]) <= tolerance:
            current.append(item)
        else:
            clusters.append(current)
            current = [item]
    clusters.append(current)
    result: list[float] = []
    for cluster in clusters:
        if len(cluster) < min_hits:
            continue
        indices = [idx for idx, _ in cluster]
        if max(indices) - min(indices) < min_age_bars:
            continue
        result.append(sum(price for _, price in cluster) / len(cluster))
    return result


def detect_swings(candles: list[Candle], *, left: int, right: int) -> list[SwingPoint]:
    swings: list[SwingPoint] = []
    last_pivot = len(candles) - right - 1
    for idx in range(left, last_pivot + 1):
        left_window = candles[idx - left : idx]
        right_window = candles[idx + 1 : idx + right + 1]
        current = candles[idx]
        if all(current.high > item.high for item in left_window + right_window):
            swings.append(SwingPoint("HIGH", idx, idx + right, current.high))
        if all(current.low < item.low for item in left_window + right_window):
            swings.append(SwingPoint("LOW", idx, idx + right, current.low))
    return swings


def last_confirmed_swing_arrays(candles: list[Candle], config: DiagnosticConfig) -> tuple[list[float | None], list[float | None]]:
    high_by_confirm: dict[int, list[float]] = defaultdict(list)
    low_by_confirm: dict[int, list[float]] = defaultdict(list)
    for swing in detect_swings(candles, left=config.swing_left, right=config.swing_right):
        if swing.side == "HIGH":
            high_by_confirm[swing.confirmed_at_index].append(swing.price)
        else:
            low_by_confirm[swing.confirmed_at_index].append(swing.price)
    high_arr: list[float | None] = [None] * len(candles)
    low_arr: list[float | None] = [None] * len(candles)
    last_high: float | None = None
    last_low: float | None = None
    for idx in range(len(candles)):
        if idx in high_by_confirm:
            last_high = high_by_confirm[idx][-1]
        if idx in low_by_confirm:
            last_low = low_by_confirm[idx][-1]
        high_arr[idx] = last_high
        low_arr[idx] = last_low
    return high_arr, low_arr


def _retired_match(retired: list[tuple[int, float]], *, idx: int, level: float, config: DiagnosticConfig) -> bool:
    tolerance = abs(level) * config.duplicate_level_tolerance_pct
    for retired_idx, retired_level in reversed(retired):
        if idx - retired_idx > config.duplicate_level_window_bars:
            break
        if abs(level - retired_level) <= tolerance:
            return True
    return False


def detect_sweep_events(candles: list[Candle], atr: list[float | None], config: DiagnosticConfig) -> list[SweepEvent]:
    events: list[SweepEvent] = []
    retired_highs: list[tuple[int, float]] = []
    retired_lows: list[tuple[int, float]] = []
    min_context = max(config.equal_level_lookback, config.atr_period + 1)
    for idx in range(min_context, len(candles)):
        atr_value = atr[idx]
        if atr_value is None or atr_value <= 0:
            continue
        candle = candles[idx]
        prior = candles[idx - config.equal_level_lookback : idx]
        tolerance = atr_value * config.equal_level_tol_atr
        equal_lows = detect_equal_levels(
            [(item.index, item.low) for item in prior],
            tolerance=tolerance,
            min_hits=config.min_hits,
            min_age_bars=config.min_age_bars,
        )
        equal_highs = detect_equal_levels(
            [(item.index, item.high) for item in prior],
            tolerance=tolerance,
            min_hits=config.min_hits,
            min_age_bars=config.min_age_bars,
        )
        sweep_buffer = config.sweep_buf_atr * atr_value
        proximity = config.sweep_proximity_atr * atr_value
        for level in equal_lows:
            if abs(candle.open - level) > proximity:
                continue
            if candle.low < level - sweep_buffer and not _retired_match(retired_lows, idx=idx, level=level, config=config):
                retired_lows.append((idx, level))
                events.append(
                    SweepEvent(
                        symbol=config.symbol,
                        timeframe=config.timeframe,
                        detection_bar=idx,
                        direction="LONG",
                        sweep_side="LOW",
                        level=float(level),
                        atr=atr_value,
                        sweep_depth_atr=(level - candle.low) / atr_value,
                    )
                )
                break
        for level in equal_highs:
            if abs(candle.open - level) > proximity:
                continue
            if candle.high > level + sweep_buffer and not _retired_match(retired_highs, idx=idx, level=level, config=config):
                retired_highs.append((idx, level))
                events.append(
                    SweepEvent(
                        symbol=config.symbol,
                        timeframe=config.timeframe,
                        detection_bar=idx,
                        direction="SHORT",
                        sweep_side="HIGH",
                        level=float(level),
                        atr=atr_value,
                        sweep_depth_atr=(candle.high - level) / atr_value,
                    )
                )
                break
    return events


def is_displacement(candle: Candle, atr_value: float | None, *, direction: str, config: DiagnosticConfig) -> bool:
    if atr_value is None or atr_value <= 0:
        return False
    body = abs(candle.close - candle.open)
    candle_range = candle.high - candle.low
    if candle_range <= 0:
        return False
    if body / atr_value < config.displacement_body_atr:
        return False
    if candle_range / atr_value < config.displacement_range_atr:
        return False
    if direction == "LONG":
        return candle.close > candle.open and ((candle.close - candle.low) / candle_range) >= config.displacement_close_percentile
    return candle.close < candle.open and ((candle.high - candle.close) / candle_range) >= config.displacement_close_percentile


def find_displacement(candles: list[Candle], atr: list[float | None], sweep: SweepEvent, config: DiagnosticConfig) -> int | None:
    end = min(len(candles), sweep.detection_bar + config.displacement_window_bars + 1)
    for idx in range(sweep.detection_bar + 1, end):
        if is_displacement(candles[idx], atr[idx], direction=sweep.direction, config=config):
            return idx
    return None


def find_structure_shift(
    candles: list[Candle],
    sweep: SweepEvent,
    *,
    last_high: list[float | None],
    last_low: list[float | None],
    config: DiagnosticConfig,
) -> tuple[int, float] | None:
    level = last_high[sweep.detection_bar] if sweep.direction == "LONG" else last_low[sweep.detection_bar]
    if level is None:
        return None
    end = min(len(candles), sweep.detection_bar + config.structure_window_bars + 1)
    for idx in range(sweep.detection_bar + 1, end):
        if sweep.direction == "LONG" and candles[idx].close > level:
            return idx, float(level)
        if sweep.direction == "SHORT" and candles[idx].close < level:
            return idx, float(level)
    return None


def fvg_at(candles: list[Candle], atr: list[float | None], created_bar: int, *, config: DiagnosticConfig) -> FVGZone | None:
    center = created_bar - 1
    if center <= 0 or created_bar >= len(candles):
        return None
    left = candles[center - 1]
    right = candles[center + 1]
    atr_value = atr[created_bar]
    if atr_value is None or atr_value <= 0:
        return None
    if left.high < right.low:
        gap = right.low - left.high
        if gap / atr_value >= config.fvg_min_atr:
            return FVGZone("BULLISH", center, created_bar, zone_low=left.high, zone_high=right.low, gap_atr=gap / atr_value)
    if left.low > right.high:
        gap = left.low - right.high
        if gap / atr_value >= config.fvg_min_atr:
            return FVGZone("BEARISH", center, created_bar, zone_low=right.high, zone_high=left.low, gap_atr=gap / atr_value)
    return None


def find_fvg(candles: list[Candle], atr: list[float | None], sweep: SweepEvent, config: DiagnosticConfig) -> FVGZone | None:
    wanted = "BULLISH" if sweep.direction == "LONG" else "BEARISH"
    start = sweep.detection_bar + 2
    end = min(len(candles), sweep.detection_bar + config.fvg_window_bars + 1)
    for created_bar in range(start, end):
        zone = fvg_at(candles, atr, created_bar, config=config)
        if zone is not None and zone.side == wanted:
            return zone
    return None


def find_mitigation(candles: list[Candle], zone: FVGZone, *, config: DiagnosticConfig) -> int | None:
    start = zone.created_bar + 1
    end = min(len(candles), zone.created_bar + config.mitigation_window_bars + 1)
    midpoint = (zone.zone_low + zone.zone_high) / 2
    for idx in range(start, end):
        candle = candles[idx]
        if zone.side == "BULLISH":
            enters = candle.low <= zone.zone_high and candle.high >= zone.zone_low
            confirms = candle.close >= midpoint or candle.close > candle.open
        else:
            enters = candle.high >= zone.zone_low and candle.low <= zone.zone_high
            confirms = candle.close <= midpoint or candle.close < candle.open
        if enters and confirms:
            return idx
    return None


def forward_metrics(
    candles: list[Candle],
    *,
    start_bar: int,
    windows: Iterable[int],
    direction: str,
    cost_pct: float = 0.0,
) -> dict[str, float | None]:
    sign = 1 if direction == "LONG" else -1
    metrics: dict[str, float | None] = {}
    if start_bar < 0 or start_bar >= len(candles):
        for window in windows:
            metrics[f"return_{window}"] = None
            metrics[f"net_return_{window}"] = None
            metrics[f"mfe_{window}"] = None
            metrics[f"mae_{window}"] = None
        return metrics
    entry = candles[start_bar].open
    for window in windows:
        end = start_bar + int(window)
        if end >= len(candles) or entry <= 0:
            metrics[f"return_{window}"] = None
            metrics[f"net_return_{window}"] = None
            metrics[f"mfe_{window}"] = None
            metrics[f"mae_{window}"] = None
            continue
        raw = ((candles[end].close - entry) / entry) * sign
        future = candles[start_bar : end + 1]
        if direction == "LONG":
            mfe = (max(item.high for item in future) - entry) / entry
            mae = (entry - min(item.low for item in future)) / entry
        else:
            mfe = (entry - min(item.low for item in future)) / entry
            mae = (max(item.high for item in future) - entry) / entry
        metrics[f"return_{window}"] = raw
        metrics[f"net_return_{window}"] = raw - cost_pct
        metrics[f"mfe_{window}"] = mfe
        metrics[f"mae_{window}"] = mae
    return metrics


def mfe_between(candles: list[Candle], *, start_bar: int, end_bar: int, direction: str) -> float | None:
    if start_bar < 0 or end_bar < start_bar or end_bar >= len(candles):
        return None
    entry = candles[start_bar].close
    window = candles[start_bar + 1 : end_bar + 1]
    if not window or entry <= 0:
        return None
    if direction == "LONG":
        return (max(item.high for item in window) - entry) / entry
    return (entry - min(item.low for item in window)) / entry


def build_sequence_events(
    candles: list[Candle],
    sweeps: list[SweepEvent],
    atr: list[float | None],
    tfi_by_time: dict[datetime, float],
    config: DiagnosticConfig,
) -> list[SequenceEvent]:
    last_high, last_low = last_confirmed_swing_arrays(candles, config)
    events: list[SequenceEvent] = []
    used_fvgs: set[tuple[str, int, float, float]] = set()
    for sweep in sweeps:
        displacement_bar = find_displacement(candles, atr, sweep, config)
        if displacement_bar is None:
            continue
        structure = find_structure_shift(candles, sweep, last_high=last_high, last_low=last_low, config=config)
        if structure is None:
            continue
        structure_bar, structure_level = structure
        zone = find_fvg(candles, atr, sweep, config)
        if zone is None:
            continue
        fvg_key = (zone.side, zone.created_bar, round(zone.zone_low, 8), round(zone.zone_high, 8))
        if fvg_key in used_fvgs:
            continue
        mitigation_bar = find_mitigation(candles, zone, config=config)
        if mitigation_bar is None:
            continue
        entry_bar = mitigation_bar + 1
        if entry_bar >= len(candles):
            continue
        used_fvgs.add(fvg_key)
        confirmation_bar = max(displacement_bar, structure_bar, zone.created_bar)
        body_atr = abs(candles[displacement_bar].close - candles[displacement_bar].open) / (atr[displacement_bar] or 1.0)
        range_atr = (candles[displacement_bar].high - candles[displacement_bar].low) / (atr[displacement_bar] or 1.0)
        event = SequenceEvent(
            symbol=sweep.symbol,
            timeframe=sweep.timeframe,
            direction=sweep.direction,
            sequence_source=sweep.sequence_source,
            detection_bar=sweep.detection_bar,
            displacement_bar=displacement_bar,
            structure_shift_bar=structure_bar,
            fvg_created_bar=zone.created_bar,
            confirmation_bar=confirmation_bar,
            mitigation_bar=mitigation_bar,
            entry_candidate_bar=entry_bar,
            label_available_bar=entry_bar,
            return_start_bar_detection=sweep.detection_bar,
            return_start_bar_entry_candidate=entry_bar,
            return_start_bar_label_available=entry_bar,
            detection_time_utc=candles[sweep.detection_bar].open_time.isoformat(),
            entry_candidate_time_utc=candles[entry_bar].open_time.isoformat(),
            level=sweep.level,
            sweep_side=sweep.sweep_side,
            sweep_depth_atr=sweep.sweep_depth_atr,
            structure_level=structure_level,
            fvg_zone_low=zone.zone_low,
            fvg_zone_high=zone.zone_high,
            fvg_gap_atr=zone.gap_atr,
            displacement_body_atr=body_atr,
            displacement_range_atr=range_atr,
            entry_price=candles[entry_bar].open,
            tfi_at_detection=tfi_by_time.get(candles[sweep.detection_bar].open_time),
            tfi_at_entry=tfi_by_time.get(candles[entry_bar].open_time),
            metadata={
                "session_metadata": utc_session(candles[entry_bar].open_time),
                "weekend_metadata": candles[entry_bar].open_time.weekday() >= 5,
                "metadata_only_note": "Regime/session/flow segmentation is metadata only, not an entry filter.",
            },
        )
        event.forward_detection = forward_metrics(
            candles,
            start_bar=event.return_start_bar_detection,
            windows=config.forward_windows,
            direction=event.direction,
            cost_pct=config.round_trip_cost_pct,
        )
        event.forward_entry_candidate = forward_metrics(
            candles,
            start_bar=event.return_start_bar_entry_candidate,
            windows=config.forward_windows,
            direction=event.direction,
            cost_pct=config.round_trip_cost_pct,
        )
        event.forward_label_available = forward_metrics(
            candles,
            start_bar=event.return_start_bar_label_available,
            windows=config.forward_windows,
            direction=event.direction,
            cost_pct=config.round_trip_cost_pct,
        )
        event.mfe_before_entry = mfe_between(
            candles,
            start_bar=event.detection_bar,
            end_bar=event.entry_candidate_bar - 1,
            direction=event.direction,
        )
        events.append(event)
    return events


def utc_session(timestamp: datetime) -> str:
    hour = timestamp.astimezone(timezone.utc).hour
    if 0 <= hour < 7:
        return "ASIA"
    if 7 <= hour < 13:
        return "EU"
    if 13 <= hour < 21:
        return "US"
    return "OFF_HOURS"


def _values(events: Iterable[SequenceEvent], bucket: str, key: str) -> list[float]:
    result: list[float] = []
    for event in events:
        metrics = getattr(event, bucket)
        value = metrics.get(key)
        if value is not None:
            result.append(float(value))
    return result


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


def summarize_group(events: list[SequenceEvent], config: DiagnosticConfig) -> dict[str, Any]:
    summary: dict[str, Any] = {"count": len(events)}
    if not events:
        return summary
    summary["directions"] = dict(Counter(event.direction for event in events))
    summary["median_bars_detection_to_entry"] = median(event.entry_candidate_bar - event.detection_bar for event in events)
    before_mfe = [event.mfe_before_entry for event in events if event.mfe_before_entry is not None]
    summary["median_mfe_before_entry"] = median(before_mfe) if before_mfe else None
    for window in config.forward_windows:
        for bucket_name, attr in (
            ("detection", "forward_detection"),
            ("entry", "forward_entry_candidate"),
            ("label_available", "forward_label_available"),
        ):
            returns = _values(events, attr, f"return_{window}")
            net_returns = _values(events, attr, f"net_return_{window}")
            mfes = _values(events, attr, f"mfe_{window}")
            maes = _values(events, attr, f"mae_{window}")
            prefix = f"{bucket_name}_{window}"
            summary[f"{prefix}_return_median"] = median(returns) if returns else None
            summary[f"{prefix}_return_avg"] = mean(returns) if returns else None
            summary[f"{prefix}_net_return_median"] = median(net_returns) if net_returns else None
            summary[f"{prefix}_net_return_avg"] = mean(net_returns) if net_returns else None
            summary[f"{prefix}_profit_factor_proxy"] = _profit_factor(net_returns)
            summary[f"{prefix}_max_dd_return_proxy"] = _max_drawdown(net_returns)
            summary[f"{prefix}_win_rate"] = sum(1 for value in returns if value > 0) / len(returns) if returns else None
            summary[f"{prefix}_mfe_median"] = median(mfes) if mfes else None
            summary[f"{prefix}_mae_median"] = median(maes) if maes else None
    return summary


def summarize_sweeps_as_baseline(sweeps: list[SweepEvent], candles: list[Candle], config: DiagnosticConfig) -> dict[str, Any]:
    pseudo_events: list[SequenceEvent] = []
    for sweep in sweeps:
        event = SequenceEvent(
            symbol=sweep.symbol,
            timeframe=sweep.timeframe,
            direction=sweep.direction,
            sequence_source="sweep_only",
            detection_bar=sweep.detection_bar,
            displacement_bar=sweep.detection_bar,
            structure_shift_bar=sweep.detection_bar,
            fvg_created_bar=sweep.detection_bar,
            confirmation_bar=sweep.detection_bar,
            mitigation_bar=sweep.detection_bar,
            entry_candidate_bar=sweep.detection_bar,
            label_available_bar=sweep.detection_bar,
            return_start_bar_detection=sweep.detection_bar,
            return_start_bar_entry_candidate=sweep.detection_bar,
            return_start_bar_label_available=sweep.detection_bar,
            detection_time_utc=candles[sweep.detection_bar].open_time.isoformat(),
            entry_candidate_time_utc=candles[sweep.detection_bar].open_time.isoformat(),
            level=sweep.level,
            sweep_side=sweep.sweep_side,
            sweep_depth_atr=sweep.sweep_depth_atr,
            structure_level=sweep.level,
            fvg_zone_low=sweep.level,
            fvg_zone_high=sweep.level,
            fvg_gap_atr=0.0,
            displacement_body_atr=0.0,
            displacement_range_atr=0.0,
            entry_price=candles[sweep.detection_bar].open,
        )
        event.forward_detection = forward_metrics(
            candles,
            start_bar=sweep.detection_bar,
            windows=config.forward_windows,
            direction=sweep.direction,
            cost_pct=config.round_trip_cost_pct,
        )
        event.forward_entry_candidate = dict(event.forward_detection)
        event.forward_label_available = dict(event.forward_detection)
        pseudo_events.append(event)
    return summarize_group(pseudo_events, config)


def deterministic_control(events: list[SequenceEvent], candles: list[Candle], config: DiagnosticConfig) -> dict[str, Any]:
    max_window = max(config.forward_windows)
    usable = max(0, len(candles) - max_window - 1)
    if usable <= 0:
        return {"method": "deterministic_shift_control", "count": 0, "summary": {}}
    pseudo: list[SequenceEvent] = []
    for source in events:
        shifted = (source.entry_candidate_bar + config.deterministic_control_shift_bars) % usable
        event = SequenceEvent(
            symbol=source.symbol,
            timeframe=source.timeframe,
            direction=source.direction,
            sequence_source="deterministic_control",
            detection_bar=shifted,
            displacement_bar=shifted,
            structure_shift_bar=shifted,
            fvg_created_bar=shifted,
            confirmation_bar=shifted,
            mitigation_bar=shifted,
            entry_candidate_bar=shifted,
            label_available_bar=shifted,
            return_start_bar_detection=shifted,
            return_start_bar_entry_candidate=shifted,
            return_start_bar_label_available=shifted,
            detection_time_utc=candles[shifted].open_time.isoformat(),
            entry_candidate_time_utc=candles[shifted].open_time.isoformat(),
            level=source.level,
            sweep_side=source.sweep_side,
            sweep_depth_atr=source.sweep_depth_atr,
            structure_level=source.structure_level,
            fvg_zone_low=source.fvg_zone_low,
            fvg_zone_high=source.fvg_zone_high,
            fvg_gap_atr=source.fvg_gap_atr,
            displacement_body_atr=source.displacement_body_atr,
            displacement_range_atr=source.displacement_range_atr,
            entry_price=candles[shifted].open,
        )
        event.forward_entry_candidate = forward_metrics(
            candles,
            start_bar=shifted,
            windows=config.forward_windows,
            direction=source.direction,
            cost_pct=config.round_trip_cost_pct,
        )
        event.forward_detection = dict(event.forward_entry_candidate)
        event.forward_label_available = dict(event.forward_entry_candidate)
        pseudo.append(event)
    return {
        "method": "deterministic_shift_control",
        "shift_bars": config.deterministic_control_shift_bars,
        "count": len(pseudo),
        "summary": summarize_group(pseudo, config),
    }


def walk_forward_summary(events: list[SequenceEvent], candles: list[Candle], config: DiagnosticConfig) -> dict[str, Any]:
    if not candles:
        return {"folds": []}
    start = candles[0].open_time
    end = candles[-1].open_time
    total_seconds = (end - start).total_seconds()
    folds: list[dict[str, Any]] = []
    for fold in range(4):
        fold_start = start.timestamp() + (total_seconds * fold / 4)
        fold_end = start.timestamp() + (total_seconds * (fold + 1) / 4)
        fold_events = [
            event
            for event in events
            if fold_start <= candles[event.entry_candidate_bar].open_time.timestamp() < fold_end
        ]
        summary = summarize_group(fold_events, config)
        summary["fold"] = fold + 1
        folds.append(summary)
    return {"folds": folds}


def invalidation_checks(
    *,
    sequence_summary: dict[str, Any],
    sweep_summary: dict[str, Any],
    control_summary: dict[str, Any],
    walk_forward: dict[str, Any],
) -> dict[str, Any]:
    risks: list[str] = []
    count = int(sequence_summary.get("count") or 0)
    entry_5 = sequence_summary.get("entry_5_return_median")
    detection_5 = sequence_summary.get("detection_5_return_median")
    entry_win = sequence_summary.get("entry_5_win_rate")
    sweep_5 = sweep_summary.get("entry_5_return_median")
    control_5 = (control_summary.get("summary") or {}).get("entry_5_return_median")
    before_mfe = sequence_summary.get("median_mfe_before_entry")
    entry_mfe = sequence_summary.get("entry_5_mfe_median")
    pf_proxy = sequence_summary.get("entry_5_profit_factor_proxy")
    expectancy_proxy = sequence_summary.get("entry_5_net_return_avg")
    if count < 100:
        risks.append("INCONCLUSIVE: OOS event count below 100.")
    if entry_5 is not None and detection_5 is not None and entry_5 < detection_5:
        risks.append("FAIL: entry-timed median return is worse than detection-bar return.")
    if entry_win is not None and entry_win <= 0.52:
        risks.append("FAIL: entry-timed win rate is approximately random.")
    if entry_5 is not None and sweep_5 is not None and entry_5 <= sweep_5:
        risks.append("FAIL: full sequence median return does not beat sweep-only baseline.")
    if entry_5 is not None and control_5 is not None and entry_5 <= control_5:
        risks.append("FAIL: full sequence median return does not beat deterministic shifted control.")
    if entry_5 is not None and entry_5 <= TRIAL_00095_REFERENCE["raw_wick_cross_median_5"]:
        risks.append("FAIL: full sequence does not beat V1 raw wick-cross median reference.")
    if before_mfe is not None and entry_mfe is not None and before_mfe >= entry_mfe:
        risks.append("FAIL: median MFE before entry is greater than or equal to post-entry 5-bar MFE.")
    if pf_proxy is not None and pf_proxy < 4.0:
        risks.append("FAIL: entry-timed 5-bar profit-factor proxy is below trial-00095 PF threshold 4.0.")
    if expectancy_proxy is not None and expectancy_proxy <= 0:
        risks.append("FAIL: entry-timed 5-bar net-return expectancy proxy is not positive after costs.")
    fragile_folds = [
        fold for fold in walk_forward.get("folds", [])
        if int(fold.get("count") or 0) < 50
    ]
    if fragile_folds:
        risks.append("FRAGILE: at least one walk-forward fold has fewer than 50 events.")
    if risks:
        verdict = "FAIL_OR_INCONCLUSIVE_REVIEW_REQUIRED"
    else:
        verdict = "POTENTIAL_PASS_REQUIRES_AUDIT"
    return {
        "verdict": verdict,
        "failed_or_risky_conditions": risks,
        "note": "No production work is justified until Claude audits these results against the approved plan.",
    }


def json_ready(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return {key: json_ready(item) for key, item in asdict(value).items()}
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(item) for item in value]
    return value


def render_report(payload: dict[str, Any]) -> str:
    manifest = payload["manifest"]
    sequence = payload["summary"]["full_sequence"]
    sweep = payload["summary"]["sweep_only"]
    control = payload["control_cohort"]["summary"]
    invalidation = payload["invalidation_checks"]

    def fmt(value: Any) -> str:
        if value is None:
            return "n/a"
        if isinstance(value, float):
            return f"{value:.6f}"
        return str(value)

    lines = [
        "# SMC_SEQUENCE_EDGE_FEASIBILITY_V1",
        "",
        "## Scope",
        "",
        "Research-only SMC sequence diagnostic. No production code, FeatureEngine facts, SignalEngine logic, Governance/Risk rules, settings/profile changes, execution changes, or DB migrations are changed by this report.",
        "",
        "V1 taxonomy remains closed/invalidated. This diagnostic tests a separate sequence hypothesis and preserves the V1 timing lesson: delayed labels must be measured from `entry_candidate_bar` or `label_available_bar`, not from `detection_bar`.",
        "",
        "## Dataset",
        "",
        f"- DB: `{manifest['db_path']}`",
        f"- Symbol/timeframe: `{manifest['symbol']}` `{manifest['timeframe']}`",
        f"- Rows: {payload['data_quality']['rows']}",
        f"- Range UTC: {payload['data_quality']['start_time_utc']} to {payload['data_quality']['end_time_utc']}",
        f"- Missing bar gaps: {payload['data_quality']['missing_bar_gaps']}",
        f"- OHLC violations: {payload['data_quality']['ohlc_violations']}",
        "",
        "## Cohorts",
        "",
        "| Cohort | Count | Det 5 Med | Entry 5 Med | Entry 5 Net Med | Entry 5 PF Proxy | Entry 5 Win | Entry 5 MFE | Entry 5 MAE |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        f"| full_sequence | {sequence.get('count', 0)} | {fmt(sequence.get('detection_5_return_median'))} | {fmt(sequence.get('entry_5_return_median'))} | {fmt(sequence.get('entry_5_net_return_median'))} | {fmt(sequence.get('entry_5_profit_factor_proxy'))} | {fmt(sequence.get('entry_5_win_rate'))} | {fmt(sequence.get('entry_5_mfe_median'))} | {fmt(sequence.get('entry_5_mae_median'))} |",
        f"| sweep_only | {sweep.get('count', 0)} | {fmt(sweep.get('detection_5_return_median'))} | {fmt(sweep.get('entry_5_return_median'))} | {fmt(sweep.get('entry_5_net_return_median'))} | {fmt(sweep.get('entry_5_profit_factor_proxy'))} | {fmt(sweep.get('entry_5_win_rate'))} | {fmt(sweep.get('entry_5_mfe_median'))} | {fmt(sweep.get('entry_5_mae_median'))} |",
        f"| deterministic_control | {payload['control_cohort'].get('count', 0)} | n/a | {fmt(control.get('entry_5_return_median'))} | {fmt(control.get('entry_5_net_return_median'))} | {fmt(control.get('entry_5_profit_factor_proxy'))} | {fmt(control.get('entry_5_win_rate'))} | {fmt(control.get('entry_5_mfe_median'))} | {fmt(control.get('entry_5_mae_median'))} |",
        "",
        "PF proxy is computed from 5-bar net event returns after the configured round-trip cost. It is not a full trade-management backtest.",
        "",
        "## Timing",
        "",
        f"- Median bars from sweep detection to entry candidate: {fmt(sequence.get('median_bars_detection_to_entry'))}",
        f"- Median MFE before entry candidate: {fmt(sequence.get('median_mfe_before_entry'))}",
        "",
        "## Trial-00095 / V1 References",
        "",
        f"- trial-00095 reference ER: {TRIAL_00095_REFERENCE['er']}",
        f"- trial-00095 reference PF: {TRIAL_00095_REFERENCE['pf']}",
        f"- V1 raw wick-cross median 5-bar reference: {TRIAL_00095_REFERENCE['raw_wick_cross_median_5']}",
        f"- V1 delayed reclaim label-available median 5-bar reference: {TRIAL_00095_REFERENCE['delayed_reclaim_label_available_median_5']}",
        "",
        "## Invalidation Verdict",
        "",
        f"- Verdict: `{invalidation['verdict']}`",
    ]
    if invalidation["failed_or_risky_conditions"]:
        for condition in invalidation["failed_or_risky_conditions"]:
            lines.append(f"- {condition}")
    else:
        lines.append("- No heuristic invalidation condition fired. This is not production approval.")
    lines.extend(["", "## Non-Goals", "", "- No FeatureEngine work.", "- No SignalEngine work.", "- No V1 taxonomy rescue.", "- No regime/session filtering.", ""])
    return "\n".join(lines)


def run_analysis(
    *,
    db_path: Path,
    output_path: Path,
    report_path: Path,
    config: DiagnosticConfig,
    start: datetime | None,
    end: datetime | None,
) -> dict[str, Any]:
    with sqlite3.connect(db_path) as conn:
        candles = load_candles(conn, symbol=config.symbol, timeframe=config.timeframe, start=start, end=end)
        tfi = load_tfi(conn, symbol=config.symbol, timeframe=config.timeframe)
    if not candles:
        raise ValueError(f"No candles found for {config.symbol} {config.timeframe} in {db_path}")
    quality = validate_candles(candles)
    if quality.ohlc_violations:
        raise ValueError(f"OHLC validation failed with {quality.ohlc_violations} violations")
    atr = compute_atr_series(candles, config.atr_period)
    sweeps = detect_sweep_events(candles, atr, config)
    sequences = build_sequence_events(candles, sweeps, atr, tfi, config)
    sequence_summary = summarize_group(sequences, config)
    sweep_summary = summarize_sweeps_as_baseline(sweeps, candles, config)
    control = deterministic_control(sequences, candles, config)
    wf = walk_forward_summary(sequences, candles, config)
    invalidation = invalidation_checks(
        sequence_summary=sequence_summary,
        sweep_summary=sweep_summary,
        control_summary=control,
        walk_forward=wf,
    )
    payload = {
        "manifest": {
            "milestone": "SMC_SEQUENCE_EDGE_FEASIBILITY_V1",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "research_only": True,
            "production_changes": False,
            "db_path": str(db_path),
            "symbol": config.symbol,
            "timeframe": config.timeframe,
            "start": start.isoformat() if start else None,
            "end": end.isoformat() if end else None,
            "config": json_ready(config),
        },
        "data_quality": json_ready(quality),
        "sweep_events_total": len(sweeps),
        "sequence_events_total": len(sequences),
        "events_included": min(len(sequences), config.max_json_events),
        "events_truncated": len(sequences) > config.max_json_events,
        "summary": {
            "full_sequence": sequence_summary,
            "sweep_only": sweep_summary,
            "walk_forward": wf,
            "metadata_only": {
                "session_counts": dict(Counter(event.metadata.get("session_metadata") for event in sequences)),
                "weekend_counts": dict(Counter(event.metadata.get("weekend_metadata") for event in sequences)),
                "note": "Regime/session/flow metadata are sanity checks only, not entry filters.",
            },
        },
        "control_cohort": control,
        "invalidation_checks": invalidation,
        "events": json_ready(sequences[: config.max_json_events]),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(render_report(payload), encoding="utf-8")
    return payload


def parse_windows(raw: str) -> tuple[int, ...]:
    values = tuple(int(item.strip()) for item in raw.split(",") if item.strip())
    if not values:
        raise argparse.ArgumentTypeError("At least one window is required")
    return values


def build_parser() -> argparse.ArgumentParser:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--timeframe", default="15m")
    parser.add_argument("--start", default=None)
    parser.add_argument("--end", default=None)
    parser.add_argument("--forward-windows", type=parse_windows, default=(3, 5, 10, 20))
    parser.add_argument("--max-json-events", type=int, default=50000)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_DIR / f"smc_sequence_edge_feasibility_v1_{today}.json")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT_DIR / f"SMC_SEQUENCE_EDGE_FEASIBILITY_V1_{today}.md")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = DiagnosticConfig(
        symbol=args.symbol,
        timeframe=args.timeframe,
        forward_windows=args.forward_windows,
        max_json_events=args.max_json_events,
    )
    payload = run_analysis(
        db_path=args.db,
        output_path=args.output,
        report_path=args.report,
        config=config,
        start=parse_ts(args.start) if args.start else None,
        end=parse_ts(args.end) if args.end else None,
    )
    print(json.dumps({
        "output": str(args.output),
        "report": str(args.report),
        "sweep_events_total": payload["sweep_events_total"],
        "sequence_events_total": payload["sequence_events_total"],
        "verdict": payload["invalidation_checks"]["verdict"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
