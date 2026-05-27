#!/usr/bin/env python3
"""Research-only sweep/reclaim event taxonomy diagnostic.

This script classifies confirmed-pivot liquidity interactions into deterministic
event labels and measures forward returns from both detection time and label
availability time. It is intentionally isolated from the live trading pipeline:
no core engines, execution services, settings overlays, or DB migrations.
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
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = PROJECT_ROOT / "research_lab" / "snapshots" / "btc_5m_2022_2026.db"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "research_lab" / "analysis_output"
DEFAULT_REPORT_DIR = PROJECT_ROOT / "docs" / "analysis"
SINGULAR_EDGE_ASSESSMENT = "docs/analysis/SWEEP_RECLAIM_SINGULAR_EDGE_ASSESSMENT_2026-05-13.md"

EVENT_CONFIRMED_PIVOT = "confirmed_pivot"
EVENT_ACTIVE_LIQUIDITY = "active_liquidity_level"
EVENT_EQUAL_TOUCH = "equal_touch"
EVENT_WICK_CROSSED = "wick_crossed_liquidity"
EVENT_CLOSE_BOS = "close_based_bos"
EVENT_IMMEDIATE_RECLAIM = "immediate_wick_sweep_reclaim"
EVENT_DELAYED_RECLAIM = "delayed_close_reclaim"
EVENT_TRUE_BREAKOUT = "true_breakout"

LIFECYCLE_EVENTS = {EVENT_CONFIRMED_PIVOT, EVENT_ACTIVE_LIQUIDITY}
DECISION_EVENTS = {
    EVENT_WICK_CROSSED,
    EVENT_CLOSE_BOS,
    EVENT_IMMEDIATE_RECLAIM,
    EVENT_DELAYED_RECLAIM,
    EVENT_TRUE_BREAKOUT,
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
class PivotConfig:
    left: int = 2
    right: int = 2
    strict: bool = True
    touch_tolerance: float = 0.0


@dataclass(frozen=True, slots=True)
class DiagnosticConfig:
    symbol: str = "BTCUSDT"
    timeframe: str = "5m"
    pivot: PivotConfig = PivotConfig()
    atr_period: int = 14
    reclaim_window_bars: int = 4
    forward_windows: tuple[int, ...] = (3, 5, 10, 20)
    cluster_tolerance_atr: float = 0.25
    cluster_history_limit: int = 500
    depth_medium_atr: float = 0.25
    depth_deep_atr: float = 0.75
    deterministic_control_shift_bars: int = 137


@dataclass(frozen=True, slots=True)
class ConfirmedPivot:
    level_id: str
    side: str
    pivot_index: int
    confirmed_at_index: int
    level_price: float
    left: int
    right: int


@dataclass(slots=True)
class TaxonomyEvent:
    symbol: str
    timeframe: str
    event_type: str
    level_side: str
    pivot_index: int
    confirmed_at_index: int
    level_price: float
    detection_bar: int
    label_available_bar: int
    return_start_bar_detection: int
    return_start_bar_label_available: int
    detection_time_utc: str
    label_available_time_utc: str
    analysis_direction: str
    direction_sign: int
    left: int
    right: int
    level_age_bars: int
    reclaim_delay_bars: int | None = None
    sweep_depth_atr: float | None = None
    sweep_depth_range: float | None = None
    wick_ratio: float | None = None
    close_reclaim: bool = False
    close_based_bos: bool = False
    no_reclaim_within_window: bool = False
    true_breakout: bool = False
    equal_touch: bool = False
    level_distance_atr_before_sweep: float | None = None
    cluster_count_near_level: int = 1
    depth_bucket: str = "not_applicable"
    cluster_bucket: str = "isolated"
    metadata: dict[str, Any] = field(default_factory=dict)
    forward_detection: dict[str, float | None] = field(default_factory=dict)
    forward_label_available: dict[str, float | None] = field(default_factory=dict)


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


class ExtremeIndex:
    """Segment tree for deterministic first-index threshold lookups."""

    def __init__(self, values: list[float], mode: str) -> None:
        if mode not in {"max", "min"}:
            raise ValueError(f"Unsupported mode: {mode}")
        self.values = values
        self.mode = mode
        self.n = len(values)
        size = 1
        while size < max(1, self.n):
            size *= 2
        self.size = size
        identity = -math.inf if mode == "max" else math.inf
        self.tree = [identity] * (2 * size)
        for idx, value in enumerate(values):
            self.tree[size + idx] = value
        combine = max if mode == "max" else min
        for idx in range(size - 1, 0, -1):
            self.tree[idx] = combine(self.tree[idx * 2], self.tree[idx * 2 + 1])

    def first_gt(self, start: int, threshold: float, *, end: int | None = None) -> int | None:
        return self._first(start, threshold, end=end, op="gt")

    def first_ge(self, start: int, threshold: float, *, end: int | None = None) -> int | None:
        return self._first(start, threshold, end=end, op="ge")

    def first_lt(self, start: int, threshold: float, *, end: int | None = None) -> int | None:
        return self._first(start, threshold, end=end, op="lt")

    def first_le(self, start: int, threshold: float, *, end: int | None = None) -> int | None:
        return self._first(start, threshold, end=end, op="le")

    def _first(self, start: int, threshold: float, *, end: int | None, op: str) -> int | None:
        if self.n == 0:
            return None
        end_exclusive = self.n if end is None else min(end, self.n)
        start = max(start, 0)
        if start >= end_exclusive:
            return None
        return self._first_node(1, 0, self.size, start, end_exclusive, threshold, op)

    def _can_prune(self, node_value: float, threshold: float, op: str) -> bool:
        if op == "gt":
            return node_value <= threshold
        if op == "ge":
            return node_value < threshold
        if op == "lt":
            return node_value >= threshold
        if op == "le":
            return node_value > threshold
        raise ValueError(op)

    def _first_node(
        self,
        node: int,
        left: int,
        right: int,
        q_left: int,
        q_right: int,
        threshold: float,
        op: str,
    ) -> int | None:
        if right <= q_left or left >= q_right:
            return None
        if self._can_prune(self.tree[node], threshold, op):
            return None
        if right - left == 1:
            return left if left < self.n else None
        mid = (left + right) // 2
        found = self._first_node(node * 2, left, mid, q_left, q_right, threshold, op)
        if found is not None:
            return found
        return self._first_node(node * 2 + 1, mid, right, q_left, q_right, threshold, op)


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


def validate_candles(candles: list[Candle]) -> DataQuality:
    seen: set[datetime] = set()
    duplicate_timestamps = 0
    non_monotonic = 0
    ohlc_violations = 0
    deltas: Counter[int] = Counter()

    previous: datetime | None = None
    for candle in candles:
        if candle.open_time in seen:
            duplicate_timestamps += 1
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
    missing_bar_gaps = 0
    if inferred_step:
        for delta, count in deltas.items():
            if delta > inferred_step:
                missing_bar_gaps += max(0, round(delta / inferred_step) - 1) * count

    return DataQuality(
        rows=len(candles),
        start_time_utc=candles[0].open_time.isoformat() if candles else None,
        end_time_utc=candles[-1].open_time.isoformat() if candles else None,
        duplicate_timestamps=duplicate_timestamps,
        non_monotonic_timestamps=non_monotonic,
        ohlc_violations=ohlc_violations,
        missing_bar_gaps=missing_bar_gaps,
        inferred_step_seconds=inferred_step,
    )


def compute_atr_series(candles: list[Candle], period: int) -> list[float | None]:
    if not candles:
        return []
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


def detect_confirmed_pivots(candles: list[Candle], config: PivotConfig) -> list[ConfirmedPivot]:
    pivots: list[ConfirmedPivot] = []
    if config.left < 1 or config.right < 1:
        raise ValueError("Pivot left/right must both be >= 1")
    last_pivot_index = len(candles) - config.right - 1
    for idx in range(config.left, last_pivot_index + 1):
        current = candles[idx]
        left_window = candles[idx - config.left : idx]
        right_window = candles[idx + 1 : idx + config.right + 1]
        if config.strict:
            is_high = all(current.high > item.high for item in left_window + right_window)
            is_low = all(current.low < item.low for item in left_window + right_window)
        else:
            is_high = all(current.high >= item.high for item in left_window + right_window)
            is_low = all(current.low <= item.low for item in left_window + right_window)
        confirmed_at = idx + config.right
        if is_high:
            pivots.append(
                ConfirmedPivot(
                    level_id=f"H:{idx}:{confirmed_at}:{current.high:.8f}",
                    side="HIGH",
                    pivot_index=idx,
                    confirmed_at_index=confirmed_at,
                    level_price=current.high,
                    left=config.left,
                    right=config.right,
                )
            )
        if is_low:
            pivots.append(
                ConfirmedPivot(
                    level_id=f"L:{idx}:{confirmed_at}:{current.low:.8f}",
                    side="LOW",
                    pivot_index=idx,
                    confirmed_at_index=confirmed_at,
                    level_price=current.low,
                    left=config.left,
                    right=config.right,
                )
            )
    pivots.sort(key=lambda item: (item.confirmed_at_index, item.pivot_index, item.side))
    return pivots


def utc_session(timestamp: datetime) -> str:
    hour = timestamp.astimezone(timezone.utc).hour
    if 0 <= hour < 7:
        return "ASIA"
    if 7 <= hour < 13:
        return "EU"
    if 13 <= hour < 21:
        return "US"
    return "OFF_HOURS"


def direction_for_event(event_type: str, side: str) -> tuple[str, int]:
    if event_type in {EVENT_CLOSE_BOS, EVENT_TRUE_BREAKOUT}:
        return ("BREAKOUT_LONG", 1) if side == "HIGH" else ("BREAKOUT_SHORT", -1)
    if event_type in {EVENT_WICK_CROSSED, EVENT_IMMEDIATE_RECLAIM, EVENT_DELAYED_RECLAIM}:
        return ("REVERSAL_SHORT", -1) if side == "HIGH" else ("REVERSAL_LONG", 1)
    return "NONE", 0


def depth_bucket(value: float | None, config: DiagnosticConfig) -> str:
    if value is None:
        return "unknown"
    if value < config.depth_medium_atr:
        return "shallow"
    if value < config.depth_deep_atr:
        return "medium"
    return "deep"


def cluster_bucket(count: int) -> str:
    if count >= 3:
        return "clustered_3_plus"
    if count == 2:
        return "paired"
    return "isolated"


def forward_metrics(
    candles: list[Candle],
    *,
    start_bar: int,
    windows: Iterable[int],
    direction_sign: int,
) -> dict[str, float | None]:
    metrics: dict[str, float | None] = {}
    if start_bar < 0 or start_bar >= len(candles):
        for window in windows:
            metrics[f"return_{window}"] = None
            metrics[f"mfe_{window}"] = None
            metrics[f"mae_{window}"] = None
        return metrics
    entry = candles[start_bar].close
    for window in windows:
        end = start_bar + int(window)
        if end >= len(candles) or entry <= 0:
            metrics[f"return_{window}"] = None
            metrics[f"mfe_{window}"] = None
            metrics[f"mae_{window}"] = None
            continue
        raw_return = (candles[end].close - entry) / entry
        signed_return = raw_return * direction_sign if direction_sign else raw_return
        future = candles[start_bar + 1 : end + 1]
        if not future or not direction_sign:
            mfe = None
            mae = None
        elif direction_sign > 0:
            mfe = (max(candle.high for candle in future) - entry) / entry
            mae = (entry - min(candle.low for candle in future)) / entry
        else:
            mfe = (entry - min(candle.low for candle in future)) / entry
            mae = (max(candle.high for candle in future) - entry) / entry
        metrics[f"return_{window}"] = signed_return
        metrics[f"mfe_{window}"] = mfe
        metrics[f"mae_{window}"] = mae
    return metrics


def _safe_ratio(numerator: float, denominator: float | None) -> float | None:
    if denominator is None or denominator <= 0:
        return None
    return numerator / denominator


def make_event(
    *,
    config: DiagnosticConfig,
    candles: list[Candle],
    atr_values: list[float | None],
    pivot: ConfirmedPivot,
    event_type: str,
    detection_bar: int,
    label_available_bar: int,
    cluster_count: int,
    reclaim_delay_bars: int | None = None,
    close_reclaim: bool = False,
    close_based_bos: bool = False,
    no_reclaim_within_window: bool = False,
    true_breakout: bool = False,
    equal_touch: bool = False,
) -> TaxonomyEvent:
    detection_candle = candles[detection_bar]
    label_candle = candles[label_available_bar]
    direction, sign = direction_for_event(event_type, pivot.side)
    atr = atr_values[detection_bar]
    prev_close = candles[detection_bar - 1].close if detection_bar > 0 else detection_candle.open
    level_distance = _safe_ratio(abs(prev_close - pivot.level_price), atr)
    sweep_depth: float | None = None
    sweep_depth_range: float | None = None
    wick_ratio: float | None = None
    candle_range = detection_candle.high - detection_candle.low
    if event_type in DECISION_EVENTS:
        if pivot.side == "HIGH":
            depth = max(0.0, detection_candle.high - pivot.level_price)
            wick = max(0.0, detection_candle.high - max(detection_candle.open, detection_candle.close))
        else:
            depth = max(0.0, pivot.level_price - detection_candle.low)
            wick = max(0.0, min(detection_candle.open, detection_candle.close) - detection_candle.low)
        sweep_depth = _safe_ratio(depth, atr)
        sweep_depth_range = _safe_ratio(depth, candle_range)
        wick_ratio = _safe_ratio(wick, candle_range)

    metadata = {
        "session_metadata": utc_session(detection_candle.open_time),
        "weekend_metadata": detection_candle.open_time.weekday() >= 5,
        "regime_metadata": None,
        "metadata_only_note": "Regime/session segmentation is metadata only and is not a candidate for entry filtering.",
    }
    event = TaxonomyEvent(
        symbol=config.symbol,
        timeframe=config.timeframe,
        event_type=event_type,
        level_side=pivot.side,
        pivot_index=pivot.pivot_index,
        confirmed_at_index=pivot.confirmed_at_index,
        level_price=pivot.level_price,
        detection_bar=detection_bar,
        label_available_bar=label_available_bar,
        return_start_bar_detection=detection_bar,
        return_start_bar_label_available=label_available_bar,
        detection_time_utc=detection_candle.open_time.isoformat(),
        label_available_time_utc=label_candle.open_time.isoformat(),
        analysis_direction=direction,
        direction_sign=sign,
        left=pivot.left,
        right=pivot.right,
        level_age_bars=detection_bar - pivot.confirmed_at_index,
        reclaim_delay_bars=reclaim_delay_bars,
        sweep_depth_atr=sweep_depth,
        sweep_depth_range=sweep_depth_range,
        wick_ratio=wick_ratio,
        close_reclaim=close_reclaim,
        close_based_bos=close_based_bos,
        no_reclaim_within_window=no_reclaim_within_window,
        true_breakout=true_breakout,
        equal_touch=equal_touch,
        level_distance_atr_before_sweep=level_distance,
        cluster_count_near_level=cluster_count,
        depth_bucket=depth_bucket(sweep_depth, config),
        cluster_bucket=cluster_bucket(cluster_count),
        metadata=metadata,
    )
    event.forward_detection = forward_metrics(
        candles,
        start_bar=event.return_start_bar_detection,
        windows=config.forward_windows,
        direction_sign=sign,
    )
    event.forward_label_available = forward_metrics(
        candles,
        start_bar=event.return_start_bar_label_available,
        windows=config.forward_windows,
        direction_sign=sign,
    )
    return event


def build_cluster_counts(pivots: list[ConfirmedPivot], candles: list[Candle], atr_values: list[float | None], config: DiagnosticConfig) -> dict[str, int]:
    counts: dict[str, int] = {}
    by_side: dict[str, list[ConfirmedPivot]] = {"HIGH": [], "LOW": []}
    for pivot in sorted(pivots, key=lambda item: item.confirmed_at_index):
        atr = atr_values[pivot.confirmed_at_index] if pivot.confirmed_at_index < len(atr_values) else None
        tolerance = (atr or 0.0) * config.cluster_tolerance_atr
        history = by_side[pivot.side][-config.cluster_history_limit :]
        if tolerance <= 0:
            count = 1
        else:
            count = 1 + sum(
                1
                for other in history
                if abs(other.level_price - pivot.level_price) <= tolerance
            )
        counts[pivot.level_id] = count
        by_side[pivot.side].append(pivot)
    return counts


def classify_taxonomy_events(
    candles: list[Candle],
    config: DiagnosticConfig,
) -> tuple[list[TaxonomyEvent], DataQuality]:
    quality = validate_candles(candles)
    if quality.ohlc_violations:
        raise ValueError(f"OHLC validation failed with {quality.ohlc_violations} violations")
    atr_values = compute_atr_series(candles, config.atr_period)
    pivots = detect_confirmed_pivots(candles, config.pivot)
    cluster_counts = build_cluster_counts(pivots, candles, atr_values, config)

    high_index = ExtremeIndex([candle.high for candle in candles], "max")
    low_index = ExtremeIndex([candle.low for candle in candles], "min")
    close_max_index = ExtremeIndex([candle.close for candle in candles], "max")
    close_min_index = ExtremeIndex([candle.close for candle in candles], "min")

    events: list[TaxonomyEvent] = []
    event_ids: set[tuple[Any, ...]] = set()

    def add(event: TaxonomyEvent) -> None:
        event_id = (
            event.symbol,
            event.timeframe,
            event.level_side,
            event.pivot_index,
            event.confirmed_at_index,
            round(event.level_price, 8),
            event.detection_bar,
            event.event_type,
        )
        if event_id not in event_ids:
            events.append(event)
            event_ids.add(event_id)

    for pivot in pivots:
        cluster_count = cluster_counts.get(pivot.level_id, 1)
        if pivot.confirmed_at_index >= len(candles):
            continue
        for lifecycle_event in (EVENT_CONFIRMED_PIVOT, EVENT_ACTIVE_LIQUIDITY):
            add(
                make_event(
                    config=config,
                    candles=candles,
                    atr_values=atr_values,
                    pivot=pivot,
                    event_type=lifecycle_event,
                    detection_bar=pivot.confirmed_at_index,
                    label_available_bar=pivot.confirmed_at_index,
                    cluster_count=cluster_count,
                )
            )

        if pivot.side == "HIGH":
            take_idx = high_index.first_gt(pivot.confirmed_at_index, pivot.level_price)
            touch_idx = high_index.first_ge(
                pivot.confirmed_at_index,
                pivot.level_price - config.pivot.touch_tolerance,
                end=take_idx,
            )
        else:
            take_idx = low_index.first_lt(pivot.confirmed_at_index, pivot.level_price)
            touch_idx = low_index.first_le(
                pivot.confirmed_at_index,
                pivot.level_price + config.pivot.touch_tolerance,
                end=take_idx,
            )

        if touch_idx is not None:
            add(
                make_event(
                    config=config,
                    candles=candles,
                    atr_values=atr_values,
                    pivot=pivot,
                    event_type=EVENT_EQUAL_TOUCH,
                    detection_bar=touch_idx,
                    label_available_bar=touch_idx,
                    cluster_count=cluster_count,
                    equal_touch=True,
                )
            )

        if take_idx is None:
            continue

        take_candle = candles[take_idx]
        if pivot.side == "HIGH":
            close_bos = take_candle.close > pivot.level_price
            immediate_reclaim = take_candle.close < pivot.level_price
            reclaim_idx = close_min_index.first_lt(take_idx + 1, pivot.level_price, end=take_idx + config.reclaim_window_bars + 1)
        else:
            close_bos = take_candle.close < pivot.level_price
            immediate_reclaim = take_candle.close > pivot.level_price
            reclaim_idx = close_max_index.first_gt(take_idx + 1, pivot.level_price, end=take_idx + config.reclaim_window_bars + 1)

        add(
            make_event(
                config=config,
                candles=candles,
                atr_values=atr_values,
                pivot=pivot,
                event_type=EVENT_WICK_CROSSED,
                detection_bar=take_idx,
                label_available_bar=take_idx,
                cluster_count=cluster_count,
                close_reclaim=immediate_reclaim,
                close_based_bos=close_bos,
            )
        )

        if close_bos:
            add(
                make_event(
                    config=config,
                    candles=candles,
                    atr_values=atr_values,
                    pivot=pivot,
                    event_type=EVENT_CLOSE_BOS,
                    detection_bar=take_idx,
                    label_available_bar=take_idx,
                    cluster_count=cluster_count,
                    close_based_bos=True,
                )
            )

        if immediate_reclaim:
            add(
                make_event(
                    config=config,
                    candles=candles,
                    atr_values=atr_values,
                    pivot=pivot,
                    event_type=EVENT_IMMEDIATE_RECLAIM,
                    detection_bar=take_idx,
                    label_available_bar=take_idx,
                    cluster_count=cluster_count,
                    close_reclaim=True,
                    reclaim_delay_bars=0,
                )
            )
        elif reclaim_idx is not None:
            add(
                make_event(
                    config=config,
                    candles=candles,
                    atr_values=atr_values,
                    pivot=pivot,
                    event_type=EVENT_DELAYED_RECLAIM,
                    detection_bar=take_idx,
                    label_available_bar=reclaim_idx,
                    cluster_count=cluster_count,
                    close_reclaim=True,
                    close_based_bos=close_bos,
                    reclaim_delay_bars=reclaim_idx - take_idx,
                )
            )
        elif close_bos and take_idx + config.reclaim_window_bars < len(candles):
            label_available = take_idx + config.reclaim_window_bars
            add(
                make_event(
                    config=config,
                    candles=candles,
                    atr_values=atr_values,
                    pivot=pivot,
                    event_type=EVENT_TRUE_BREAKOUT,
                    detection_bar=take_idx,
                    label_available_bar=label_available,
                    cluster_count=cluster_count,
                    close_based_bos=True,
                    no_reclaim_within_window=True,
                    true_breakout=True,
                )
            )

    events.sort(key=lambda event: (event.detection_bar, event.label_available_bar, event.event_type, event.pivot_index))
    return events, quality


def values_for(events: Iterable[TaxonomyEvent], field: str, metric: str) -> list[float]:
    values: list[float] = []
    for event in events:
        bucket = event.forward_detection if field == "detection" else event.forward_label_available
        value = bucket.get(metric)
        if value is not None:
            values.append(float(value))
    return values


def summarize_group(events: list[TaxonomyEvent], config: DiagnosticConfig) -> dict[str, Any]:
    summary: dict[str, Any] = {"count": len(events)}
    if not events:
        return summary
    summary["directions"] = dict(Counter(event.analysis_direction for event in events))
    summary["sides"] = dict(Counter(event.level_side for event in events))
    summary["depth_buckets"] = dict(Counter(event.depth_bucket for event in events))
    summary["cluster_buckets"] = dict(Counter(event.cluster_bucket for event in events))
    summary["median_level_age_bars"] = median(event.level_age_bars for event in events)
    for window in config.forward_windows:
        for start_name in ("detection", "label_available"):
            returns = values_for(events, start_name, f"return_{window}")
            mfes = values_for(events, start_name, f"mfe_{window}")
            maes = values_for(events, start_name, f"mae_{window}")
            prefix = f"{start_name}_{window}"
            summary[f"{prefix}_return_avg"] = mean(returns) if returns else None
            summary[f"{prefix}_return_median"] = median(returns) if returns else None
            summary[f"{prefix}_return_win_rate"] = sum(1 for value in returns if value > 0) / len(returns) if returns else None
            summary[f"{prefix}_mfe_median"] = median(mfes) if mfes else None
            summary[f"{prefix}_mae_median"] = median(maes) if maes else None
    return summary


def summarize_events(events: list[TaxonomyEvent], config: DiagnosticConfig) -> dict[str, Any]:
    by_type: dict[str, list[TaxonomyEvent]] = defaultdict(list)
    for event in events:
        by_type[event.event_type].append(event)

    required_types = [
        EVENT_CONFIRMED_PIVOT,
        EVENT_ACTIVE_LIQUIDITY,
        EVENT_EQUAL_TOUCH,
        EVENT_WICK_CROSSED,
        EVENT_CLOSE_BOS,
        EVENT_IMMEDIATE_RECLAIM,
        EVENT_DELAYED_RECLAIM,
        EVENT_TRUE_BREAKOUT,
    ]
    event_type_summary = {
        event_type: summarize_group(by_type.get(event_type, []), config) for event_type in required_types
    }
    decision_events = [event for event in events if event.event_type in DECISION_EVENTS]
    clustered_reclaim_proxy = [
        event
        for event in decision_events
        if event.event_type in {EVENT_IMMEDIATE_RECLAIM, EVENT_DELAYED_RECLAIM}
        and event.cluster_count_near_level >= 3
    ]
    required_decision_cohorts = {
        "raw_wick_cross": summarize_group(by_type.get(EVENT_WICK_CROSSED, []), config),
        "immediate_close_reclaim": summarize_group(by_type.get(EVENT_IMMEDIATE_RECLAIM, []), config),
        "delayed_close_reclaim": summarize_group(by_type.get(EVENT_DELAYED_RECLAIM, []), config),
        "close_based_bos": summarize_group(by_type.get(EVENT_CLOSE_BOS, []), config),
        "true_breakout_no_reclaim_within_window": summarize_group(by_type.get(EVENT_TRUE_BREAKOUT, []), config),
        "shallow_sweep": summarize_group([event for event in decision_events if event.depth_bucket == "shallow"], config),
        "medium_sweep": summarize_group([event for event in decision_events if event.depth_bucket == "medium"], config),
        "deep_sweep": summarize_group([event for event in decision_events if event.depth_bucket == "deep"], config),
        "clustered_equal_level_proxy": summarize_group([event for event in decision_events if event.cluster_count_near_level >= 3], config),
        "isolated_pivot": summarize_group([event for event in decision_events if event.cluster_count_near_level == 1], config),
        "current_bot_equal_level_baseline_proxy": summarize_group(clustered_reclaim_proxy, config),
    }
    metadata_only = {
        "session_metadata_counts": dict(Counter(event.metadata.get("session_metadata") for event in decision_events)),
        "weekend_metadata_counts": dict(Counter(event.metadata.get("weekend_metadata") for event in decision_events)),
        "note": "Regime/session segmentation is metadata only and is not a candidate for entry filtering in this milestone.",
    }
    return {
        "event_type_summary": event_type_summary,
        "required_decision_cohorts": required_decision_cohorts,
        "metadata_only": metadata_only,
    }


def deterministic_shift_control(events: list[TaxonomyEvent], candles: list[Candle], config: DiagnosticConfig) -> dict[str, Any]:
    source_events = [event for event in events if event.event_type in DECISION_EVENTS]
    control_rows: list[dict[str, float | None]] = []
    max_window = max(config.forward_windows)
    usable_n = max(0, len(candles) - max_window - 1)
    if usable_n <= 0:
        return {"method": "deterministic_shift", "count": 0, "summary": {}}
    for event in source_events:
        shifted = (event.detection_bar + config.deterministic_control_shift_bars) % usable_n
        metrics = forward_metrics(
            candles,
            start_bar=shifted,
            windows=config.forward_windows,
            direction_sign=event.direction_sign,
        )
        control_rows.append(metrics)
    summary: dict[str, Any] = {"count": len(control_rows)}
    for window in config.forward_windows:
        returns = [float(row[f"return_{window}"]) for row in control_rows if row.get(f"return_{window}") is not None]
        summary[f"detection_{window}_return_avg"] = mean(returns) if returns else None
        summary[f"detection_{window}_return_median"] = median(returns) if returns else None
        summary[f"detection_{window}_return_win_rate"] = sum(1 for value in returns if value > 0) / len(returns) if returns else None
    return {
        "method": "deterministic_shift_control",
        "shift_bars": config.deterministic_control_shift_bars,
        "count": len(control_rows),
        "summary": summary,
    }


def invalidation_checks(summary: dict[str, Any], control: dict[str, Any]) -> dict[str, Any]:
    cohorts = summary["required_decision_cohorts"]
    window_key = "detection_5_return_median"
    label_window_key = "label_available_5_return_median"
    wick = cohorts["raw_wick_cross"].get(window_key)
    immediate = cohorts["immediate_close_reclaim"].get(window_key)
    delayed_detection = cohorts["delayed_close_reclaim"].get(window_key)
    delayed_label = cohorts["delayed_close_reclaim"].get(label_window_key)
    true_breakout = cohorts["true_breakout_no_reclaim_within_window"].get(window_key)
    control_median = control.get("summary", {}).get(window_key)

    failed: list[str] = []
    if cohorts["raw_wick_cross"]["count"] < 100:
        failed.append("Sample size below decision-grade threshold for raw wick crosses.")
    if immediate is not None and wick is not None and immediate <= wick:
        failed.append("Immediate reclaim does not outperform raw wick cross on 5-bar median signed return.")
    if delayed_detection is not None and wick is not None and delayed_detection <= wick:
        failed.append("Delayed reclaim does not outperform raw wick cross from detection-bar timing.")
    if delayed_detection is not None and delayed_label is not None and delayed_label < delayed_detection:
        failed.append("Delayed reclaim edge weakens when measured from label-available timing.")
    if true_breakout is not None and wick is not None and abs(true_breakout - wick) < 0.0001:
        failed.append("True breakout/no-reclaim does not materially separate from raw wick cross.")
    if immediate is not None and control_median is not None and immediate <= control_median:
        failed.append("Immediate reclaim does not outperform deterministic shifted control.")

    if failed:
        verdict = "INVALIDATION_RISK_REVIEW_REQUIRED"
    else:
        verdict = "POTENTIAL_SEPARATION_REQUIRES_AUDIT"
    return {
        "verdict": verdict,
        "primary_window": "5 bars",
        "failed_or_risky_conditions": failed,
        "note": "This heuristic does not approve FeatureEngine work; Claude audit must evaluate Section 16 invalidation criteria.",
    }


def json_ready(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "__dataclass_fields__"):
        return {key: json_ready(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(item) for item in value]
    return value


def render_report(payload: dict[str, Any]) -> str:
    manifest = payload["manifest"]
    quality = payload["data_quality"]
    summary = payload["summary"]
    cohorts = summary["required_decision_cohorts"]
    invalidation = payload["invalidation_checks"]

    def fmt(value: Any) -> str:
        if value is None:
            return "n/a"
        if isinstance(value, float):
            return f"{value:.6f}"
        return str(value)

    lines = [
        "# SWEEP_RECLAIM_EVENT_TAXONOMY_DIAGNOSTIC_V1",
        "",
        "## Scope",
        "",
        "Research-only event taxonomy diagnostic. No production code, FeatureEngine facts, SignalEngine logic, Governance/Risk rules, settings/profile changes, or DB migrations are changed by this report.",
        "",
        "Trial-00095 remains the validated baseline. This diagnostic tests whether the current single-bar sweep/reclaim boolean mixes structurally different event classes.",
        "",
        f"Regime/session segmentation is metadata only and is not a candidate for entry filtering in this milestone. This follows the May 2026 Singular Edge Assessment: `{SINGULAR_EDGE_ASSESSMENT}`.",
        "",
        "## Dataset",
        "",
        f"- DB: `{manifest['db_path']}`",
        f"- Symbol/timeframe: `{manifest['symbol']}` `{manifest['timeframe']}`",
        f"- Rows: {quality['rows']}",
        f"- Range UTC: {quality['start_time_utc']} to {quality['end_time_utc']}",
        f"- Missing bar gaps: {quality['missing_bar_gaps']}",
        f"- OHLC violations: {quality['ohlc_violations']}",
        "",
        "## Timing Model",
        "",
        "Every row separates `detection_bar`, `label_available_bar`, `return_start_bar_detection`, and `return_start_bar_label_available`. Delayed reclaim and true-breakout labels are evaluated from both timing starts to avoid fake edge from unknowable labels.",
        "",
        "## Required Cohorts",
        "",
        "| Cohort | Count | Det 5 Med | Label 5 Med | Det 5 Win | Label 5 Win |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, cohort in cohorts.items():
        lines.append(
            f"| {name} | {cohort.get('count', 0)} | "
            f"{fmt(cohort.get('detection_5_return_median'))} | "
            f"{fmt(cohort.get('label_available_5_return_median'))} | "
            f"{fmt(cohort.get('detection_5_return_win_rate'))} | "
            f"{fmt(cohort.get('label_available_5_return_win_rate'))} |"
        )
    lines.extend(
        [
            "",
            "## Control Cohort",
            "",
            f"- Method: {payload['control_cohort']['method']}",
            f"- Count: {payload['control_cohort']['count']}",
            f"- Detection 5-bar median signed return: {fmt(payload['control_cohort']['summary'].get('detection_5_return_median'))}",
            "",
            "## Event Counts",
            "",
            "| Event Type | Count |",
            "| --- | ---: |",
        ]
    )
    for event_type, event_summary in summary["event_type_summary"].items():
        lines.append(f"| {event_type} | {event_summary.get('count', 0)} |")
    lines.extend(
        [
            "",
            "## Invalidation Verdict",
            "",
            f"- Verdict: `{invalidation['verdict']}`",
            f"- Primary window: {invalidation['primary_window']}",
        ]
    )
    if invalidation["failed_or_risky_conditions"]:
        for condition in invalidation["failed_or_risky_conditions"]:
            lines.append(f"- Risk: {condition}")
    else:
        lines.append("- No heuristic invalidation condition fired. This is not approval to change production behavior.")
    lines.extend(
        [
            "",
            "## Non-Goals Confirmed",
            "",
            "- No regime/session filtering.",
            "- No parameter rescue.",
            "- No new entry logic.",
            "- No CHOCH/MSS, acceptance model, failed_sweep, OB/FVG/RJB/PPDD, or Pine port.",
            "",
        ]
    )
    return "\n".join(lines)


def run_analysis(
    *,
    db_path: Path,
    output_path: Path,
    report_path: Path,
    config: DiagnosticConfig,
    start: datetime | None,
    end: datetime | None,
    max_json_events: int,
) -> dict[str, Any]:
    with sqlite3.connect(db_path) as conn:
        candles = load_candles(conn, symbol=config.symbol, timeframe=config.timeframe, start=start, end=end)
    if not candles:
        raise ValueError(f"No candles found for {config.symbol} {config.timeframe} in {db_path}")

    events, quality = classify_taxonomy_events(candles, config)
    summary = summarize_events(events, config)
    control = deterministic_shift_control(events, candles, config)
    invalidation = invalidation_checks(summary, control)
    truncated = len(events) > max_json_events

    payload = {
        "manifest": {
            "milestone": "SWEEP_RECLAIM_EVENT_TAXONOMY_DIAGNOSTIC_V1",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "db_path": str(db_path),
            "symbol": config.symbol,
            "timeframe": config.timeframe,
            "start": start.isoformat() if start else None,
            "end": end.isoformat() if end else None,
            "config": json_ready(config),
            "research_only": True,
            "production_changes": False,
        },
        "data_quality": json_ready(quality),
        "summary": summary,
        "control_cohort": control,
        "invalidation_checks": invalidation,
        "events_truncated": truncated,
        "events_included": min(len(events), max_json_events),
        "events_total": len(events),
        "events": json_ready(events[:max_json_events]),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(render_report(payload), encoding="utf-8")
    return payload


def parse_windows(raw: str) -> tuple[int, ...]:
    windows = tuple(int(item.strip()) for item in raw.split(",") if item.strip())
    if not windows:
        raise argparse.ArgumentTypeError("At least one forward window is required")
    if any(window <= 0 for window in windows):
        raise argparse.ArgumentTypeError("Forward windows must be positive integers")
    return windows


def build_parser() -> argparse.ArgumentParser:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--timeframe", default="5m")
    parser.add_argument("--start", default=None, help="UTC ISO start timestamp, optional")
    parser.add_argument("--end", default=None, help="UTC ISO end timestamp, optional")
    parser.add_argument("--left", type=int, default=2)
    parser.add_argument("--right", type=int, default=2)
    parser.add_argument("--touch-tolerance", type=float, default=0.0)
    parser.add_argument("--atr-period", type=int, default=14)
    parser.add_argument("--reclaim-window-bars", type=int, default=4)
    parser.add_argument("--forward-windows", type=parse_windows, default=(3, 5, 10, 20))
    parser.add_argument("--cluster-tolerance-atr", type=float, default=0.25)
    parser.add_argument("--cluster-history-limit", type=int, default=500)
    parser.add_argument("--control-shift-bars", type=int, default=137)
    parser.add_argument("--max-json-events", type=int, default=50000)
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_DIR / f"sweep_reclaim_event_taxonomy_diagnostic_v1_{today}.json",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=DEFAULT_REPORT_DIR / f"SWEEP_RECLAIM_EVENT_TAXONOMY_DIAGNOSTIC_V1_{today}.md",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = DiagnosticConfig(
        symbol=args.symbol,
        timeframe=args.timeframe,
        pivot=PivotConfig(left=args.left, right=args.right, strict=True, touch_tolerance=args.touch_tolerance),
        atr_period=args.atr_period,
        reclaim_window_bars=args.reclaim_window_bars,
        forward_windows=args.forward_windows,
        cluster_tolerance_atr=args.cluster_tolerance_atr,
        cluster_history_limit=args.cluster_history_limit,
        deterministic_control_shift_bars=args.control_shift_bars,
    )
    payload = run_analysis(
        db_path=args.db,
        output_path=args.output,
        report_path=args.report,
        config=config,
        start=parse_ts(args.start) if args.start else None,
        end=parse_ts(args.end) if args.end else None,
        max_json_events=args.max_json_events,
    )
    print(json.dumps({
        "output": str(args.output),
        "report": str(args.report),
        "events_total": payload["events_total"],
        "verdict": payload["invalidation_checks"]["verdict"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
