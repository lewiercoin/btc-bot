#!/usr/bin/env python3
"""Research-only reclaim/rejection feasibility diagnostic V1.

This module is isolated from the live trading path. It reads a research
snapshot in read-only mode, computes deterministic cohorts, and writes JSON,
SHA256, and markdown artifacts for Claude audit.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sqlite3
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any, Iterable

import pandas as pd

if __name__ == "__main__" and sys.path:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if os.path.abspath(sys.path[0]) == script_dir:
        sys.path.pop(0)
        sys.path.insert(0, os.path.dirname(os.path.dirname(script_dir)))

from research_lab.level_scanner import ScannerConfig, scan_levels  # noqa: E402


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CANONICAL_DB_PATH = PROJECT_ROOT / "research_lab" / "data" / "crowded_unwind_backtest.db"
FALLBACK_RESEARCH_SNAPSHOT = PROJECT_ROOT / "research_lab" / "snapshots" / "replay-optuna-default-v3-trial-00095.db"
DEFAULT_OUTPUT_JSON = PROJECT_ROOT / "research_lab" / "analysis_output" / "reclaim_rejection_feasibility_v1.json"
DEFAULT_OUTPUT_SHA = PROJECT_ROOT / "research_lab" / "analysis_output" / "reclaim_rejection_feasibility_v1.sha256"
DEFAULT_REPORT = PROJECT_ROOT / "research_lab" / "analysis_output" / "reclaim_rejection_feasibility_v1_report.md"


EVENT_STUDY_BASELINE_DEFAULTS = {
    "sweep_proximity_atr": 0.4,
    "level_min_age_bars": 5,
    "min_hits": 3,
    "equal_level_lookback": 50,
    "equal_level_tol_atr": 0.25,
    "wick_min_atr": 0.3,
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
class FlowBar:
    bucket_time: datetime
    taker_buy_volume: float
    taker_sell_volume: float
    tfi: float
    cvd_delta: float
    source_rows: int


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
class DiagnosticConfig:
    symbol: str = "BTCUSDT"
    timeframe: str = "15m"
    study_start: str = "2022-01-01"
    study_end: str = "2026-03-01"
    atr_period: int = 14
    swing_left_bars: int = 3
    swing_right_bars: int = 1
    wick_to_body_min: float = 2.0
    wick_range_share_min: float = 0.6
    wick_atr_min: float = 1.0
    fixed_exit_stop_atr: float = 1.0
    fixed_exit_target_atr: float = 2.0
    fixed_exit_max_hold_bars: int = 16
    f3_post_entry_bars: int = 5
    round_trip_cost_pct: float = 0.0010
    deterministic_control_seed_shift: int = 137
    max_json_events: int = 50000


@dataclass(frozen=True, slots=True)
class RejectionCandidate:
    direction: str
    detection_bar: int
    state_known_bar: int
    zone_bottom: float
    zone_top: float
    wick_size: float
    wick_to_body: float
    wick_range_share: float
    wick_atr: float
    atr_at_detection: float


@dataclass(slots=True)
class RejectionEvent:
    event_id: str
    cohort_source: str
    direction: str
    detection_bar: int
    state_known_bar: int
    entry_candidate_bar: int
    return_start_bar: int
    label_available_bar: int
    detection_time_utc: str
    state_known_time_utc: str
    entry_candidate_time_utc: str
    return_start_time_utc: str
    zone_bottom: float
    zone_top: float
    atr_at_detection: float
    atr_at_entry_candidate: float | None
    level_id: str | None = None
    level_category: str | None = None
    level_available_at: str | None = None
    confluence: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)


def parse_ts(raw: Any) -> datetime:
    if isinstance(raw, datetime):
        return raw.astimezone(timezone.utc) if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
    parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    return parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def floor_15m(ts: datetime) -> datetime:
    ts = ts.astimezone(timezone.utc)
    minute = (ts.minute // 15) * 15
    return ts.replace(minute=minute, second=0, microsecond=0)


def json_ready(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return json_ready(asdict(value))
    if isinstance(value, dict):
        return {str(key): json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(item) for item in value]
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, pd.Timestamp):
        return value.tz_convert("UTC").isoformat() if value.tzinfo else value.tz_localize("UTC").isoformat()
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value
    return value


def safe_median(values: Iterable[float | None]) -> float | None:
    cleaned = [float(value) for value in values if value is not None and math.isfinite(float(value))]
    return median(cleaned) if cleaned else None


def safe_mean(values: Iterable[float | None]) -> float | None:
    cleaned = [float(value) for value in values if value is not None and math.isfinite(float(value))]
    return mean(cleaned) if cleaned else None


def profit_factor(returns: Iterable[float | None]) -> float | None:
    cleaned = [float(value) for value in returns if value is not None and math.isfinite(float(value))]
    if not cleaned:
        return None
    gains = sum(value for value in cleaned if value > 0)
    losses = abs(sum(value for value in cleaned if value < 0))
    if losses == 0:
        return None if gains == 0 else 999.0
    return gains / losses


def pearson(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    mx = mean(xs)
    my = mean(ys)
    numerator = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if dx == 0 or dy == 0:
        return None
    return numerator / (dx * dy)


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
        WHERE symbol = ? AND timeframe = ? AND open_time >= ? AND open_time <= ?
        ORDER BY open_time ASC
        """,
        (symbol, timeframe, start.isoformat(), end.isoformat()),
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


def load_flow_15m(
    conn: sqlite3.Connection,
    *,
    symbol: str,
    start: datetime,
    end: datetime,
) -> tuple[dict[datetime, FlowBar], dict[str, Any]]:
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    if "aggtrade_buckets" not in tables:
        return {}, {"source": "aggtrade_buckets", "status": "MISSING_TABLE", "rows": 0}

    rows = conn.execute(
        """
        SELECT bucket_time, taker_buy_volume, taker_sell_volume, tfi, cvd
        FROM aggtrade_buckets
        WHERE symbol = ? AND timeframe = '60s' AND bucket_time >= ? AND bucket_time <= ?
        ORDER BY bucket_time ASC
        """,
        (symbol, start.isoformat(), end.isoformat()),
    ).fetchall()
    source = "aggtrade_buckets_60s_aggregated_to_15m"
    if not rows:
        rows = conn.execute(
            """
            SELECT bucket_time, taker_buy_volume, taker_sell_volume, tfi, cvd
            FROM aggtrade_buckets
            WHERE symbol = ? AND timeframe = '15m' AND bucket_time >= ? AND bucket_time <= ?
            ORDER BY bucket_time ASC
            """,
            (symbol, start.isoformat(), end.isoformat()),
        ).fetchall()
        source = "aggtrade_buckets_15m_fallback"

    grouped: dict[datetime, list[tuple[float, float, float | None, float | None]]] = defaultdict(list)
    for row in rows:
        bucket = floor_15m(parse_ts(row[0]))
        buy = float(row[1] or 0.0)
        sell = float(row[2] or 0.0)
        tfi = float(row[3]) if row[3] is not None else None
        cvd = float(row[4]) if row[4] is not None else None
        grouped[bucket].append((buy, sell, tfi, cvd))

    flow: dict[datetime, FlowBar] = {}
    missing_cvd = 0
    for bucket, items in grouped.items():
        buy_sum = sum(item[0] for item in items)
        sell_sum = sum(item[1] for item in items)
        total = buy_sum + sell_sum
        tfi_value = ((buy_sum - sell_sum) / total) if total > 0 else 0.0
        cvd_values = [item[3] for item in items if item[3] is not None]
        if len(cvd_values) >= 2:
            cvd_delta = float(cvd_values[-1] - cvd_values[0])
        elif len(cvd_values) == 1:
            cvd_delta = float(cvd_values[0])
        else:
            missing_cvd += 1
            cvd_delta = 0.0
        flow[bucket] = FlowBar(
            bucket_time=bucket,
            taker_buy_volume=buy_sum,
            taker_sell_volume=sell_sum,
            tfi=tfi_value,
            cvd_delta=cvd_delta,
            source_rows=len(items),
        )

    return flow, {
        "source": source,
        "input_rows": len(rows),
        "aggregated_15m_rows": len(flow),
        "missing_cvd_groups": missing_cvd,
        "cvd_proxy": "last_cvd_minus_first_cvd_inside_15m_bucket; fallback single value when only one row exists",
        "tfi_proxy": "sum(taker_buy_volume - taker_sell_volume) / sum(total_taker_volume)",
    }


def validate_candles(candles: list[Candle]) -> DataQuality:
    seen: set[datetime] = set()
    duplicates = 0
    non_monotonic = 0
    ohlc_violations = 0
    deltas: Counter[int] = Counter()
    previous: datetime | None = None
    for candle in candles:
        if candle.open_time in seen:
            duplicates += 1
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
        duplicate_timestamps=duplicates,
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


def confirmed_swing_maps(
    candles: list[Candle],
    *,
    left: int,
    right: int,
) -> tuple[dict[int, int], dict[int, int]]:
    high_confirmed: dict[int, int] = {}
    low_confirmed: dict[int, int] = {}
    last_pivot = len(candles) - right - 1
    for idx in range(left, last_pivot + 1):
        left_window = candles[idx - left : idx]
        right_window = candles[idx + 1 : idx + right + 1]
        current = candles[idx]
        if all(current.high > item.high for item in left_window + right_window):
            high_confirmed[idx] = idx + right
        if all(current.low < item.low for item in left_window + right_window):
            low_confirmed[idx] = idx + right
    return high_confirmed, low_confirmed


def detect_rejection_candidates(
    candles: list[Candle],
    atr: list[float | None],
    config: DiagnosticConfig,
) -> list[RejectionCandidate]:
    high_swings, low_swings = confirmed_swing_maps(candles, left=config.swing_left_bars, right=config.swing_right_bars)
    candidates: list[RejectionCandidate] = []
    tick_epsilon = 1e-9
    for idx, candle in enumerate(candles):
        if idx + 1 >= len(candles):
            continue
        atr_value = atr[idx]
        if atr_value is None or atr_value <= 0:
            continue
        candle_range = candle.high - candle.low
        if candle_range <= 0:
            continue
        body = abs(candle.close - candle.open)
        body_for_ratio = max(body, tick_epsilon)
        upper_wick = candle.high - max(candle.open, candle.close)
        lower_wick = min(candle.open, candle.close) - candle.low
        state_known = idx + 1

        if (
            idx in high_swings
            and high_swings[idx] <= state_known
            and upper_wick / body_for_ratio >= config.wick_to_body_min
            and upper_wick / candle_range >= config.wick_range_share_min
            and upper_wick / atr_value >= config.wick_atr_min
        ):
            candidates.append(
                RejectionCandidate(
                    direction="SHORT",
                    detection_bar=idx,
                    state_known_bar=state_known,
                    zone_bottom=max(candle.open, candle.close),
                    zone_top=candle.high,
                    wick_size=upper_wick,
                    wick_to_body=upper_wick / body_for_ratio,
                    wick_range_share=upper_wick / candle_range,
                    wick_atr=upper_wick / atr_value,
                    atr_at_detection=atr_value,
                )
            )

        if (
            idx in low_swings
            and low_swings[idx] <= state_known
            and lower_wick / body_for_ratio >= config.wick_to_body_min
            and lower_wick / candle_range >= config.wick_range_share_min
            and lower_wick / atr_value >= config.wick_atr_min
        ):
            candidates.append(
                RejectionCandidate(
                    direction="LONG",
                    detection_bar=idx,
                    state_known_bar=state_known,
                    zone_bottom=candle.low,
                    zone_top=min(candle.open, candle.close),
                    wick_size=lower_wick,
                    wick_to_body=lower_wick / body_for_ratio,
                    wick_range_share=lower_wick / candle_range,
                    wick_atr=lower_wick / atr_value,
                    atr_at_detection=atr_value,
                )
            )
    return candidates


def confluence_passes(direction: str, flow: FlowBar | None) -> bool:
    if flow is None:
        return False
    if direction == "LONG":
        return flow.tfi > 0 and flow.cvd_delta >= 0
    return flow.tfi < 0 and flow.cvd_delta <= 0


def find_entry_candidate(
    candidate: RejectionCandidate,
    candles: list[Candle],
    flow_by_time: dict[datetime, FlowBar],
) -> tuple[int, FlowBar] | None:
    for idx in range(candidate.state_known_bar + 1, len(candles) - 1):
        candle = candles[idx]
        if candidate.direction == "LONG":
            reclaim = candle.close > candidate.zone_top
        else:
            reclaim = candle.close < candidate.zone_bottom
        if not reclaim:
            continue
        flow = flow_by_time.get(candle.open_time)
        if confluence_passes(candidate.direction, flow):
            return idx, flow  # type: ignore[return-value]
    return None


def event_id(*parts: Any) -> str:
    payload = "|".join(str(part) for part in parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def build_rejection_events(
    candidates: list[RejectionCandidate],
    candles: list[Candle],
    atr: list[float | None],
    flow_by_time: dict[datetime, FlowBar],
    config: DiagnosticConfig,
) -> list[RejectionEvent]:
    events: list[RejectionEvent] = []
    for candidate in candidates:
        entry = find_entry_candidate(candidate, candles, flow_by_time)
        if entry is None:
            continue
        entry_bar, flow = entry
        return_start = entry_bar + 1
        label_available = min(len(candles) - 1, return_start + config.fixed_exit_max_hold_bars)
        if return_start >= len(candles):
            continue
        event = RejectionEvent(
            event_id=event_id("reclaim_rejection", candidate.direction, candles[candidate.detection_bar].open_time.isoformat()),
            cohort_source="reclaim_rejection",
            direction=candidate.direction,
            detection_bar=candidate.detection_bar,
            state_known_bar=candidate.state_known_bar,
            entry_candidate_bar=entry_bar,
            return_start_bar=return_start,
            label_available_bar=label_available,
            detection_time_utc=candles[candidate.detection_bar].open_time.isoformat(),
            state_known_time_utc=candles[candidate.state_known_bar].open_time.isoformat(),
            entry_candidate_time_utc=candles[entry_bar].open_time.isoformat(),
            return_start_time_utc=candles[return_start].open_time.isoformat(),
            zone_bottom=candidate.zone_bottom,
            zone_top=candidate.zone_top,
            atr_at_detection=candidate.atr_at_detection,
            atr_at_entry_candidate=atr[entry_bar],
            confluence={
                "source": "aggtrade_buckets.cvd",
                "tfi": flow.tfi,
                "cvd_delta": flow.cvd_delta,
                "source_rows": flow.source_rows,
            },
        )
        events.append(event)
    return events


def candles_to_frame(candles: list[Candle]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp": [candle.open_time for candle in candles],
            "open": [candle.open for candle in candles],
            "high": [candle.high for candle in candles],
            "low": [candle.low for candle in candles],
            "close": [candle.close for candle in candles],
            "volume": [candle.volume for candle in candles],
        }
    )


def build_provenance_levels(candles: list[Candle], config: DiagnosticConfig) -> pd.DataFrame:
    scanner_config = ScannerConfig(
        symbol=config.symbol,
        timeframe=config.timeframe,
        include_session_extremes=False,
        include_previous_periods=False,
        include_equal_clusters=True,
        include_anchored_vwap=False,
        include_round_numbers=False,
        include_liquidation_placeholder=False,
        atr_period=config.atr_period,
        swing_left_bars=config.swing_left_bars,
        swing_right_bars=config.swing_right_bars,
        equal_cluster_min_hits=2,
        equal_cluster_lookback_bars=96,
        equal_cluster_tolerance_atr=0.25,
        metadata={"consumer": "reclaim_rejection_feasibility_v1"},
    )
    return scan_levels(candles_to_frame(candles), scanner_config)


def find_level_provenance(event: RejectionEvent, levels: pd.DataFrame) -> dict[str, Any] | None:
    if levels.empty:
        return None
    state_known = parse_ts(event.state_known_time_utc)
    wanted_side = "LOW" if event.direction == "LONG" else "HIGH"
    available = levels[
        (levels["available_at"] <= pd.Timestamp(state_known))
        & (levels["side"].isin([wanted_side, "MID", "ROUND"]))
        & (levels["top"].astype(float) >= event.zone_bottom)
        & (levels["bottom"].astype(float) <= event.zone_top)
    ]
    if available.empty:
        return None
    row = available.sort_values(["available_at", "category", "level_id"], kind="stable").iloc[-1]
    return {
        "level_id": str(row["level_id"]),
        "level_category": str(row["category"]),
        "level_available_at": pd.Timestamp(row["available_at"]).isoformat(),
    }


def attach_level_provenance(events: list[RejectionEvent], levels: pd.DataFrame) -> tuple[list[RejectionEvent], list[RejectionEvent]]:
    with_provenance: list[RejectionEvent] = []
    for event in events:
        provenance = find_level_provenance(event, levels)
        if provenance is None:
            continue
        event.level_id = provenance["level_id"]
        event.level_category = provenance["level_category"]
        event.level_available_at = provenance["level_available_at"]
        with_provenance.append(event)
    return with_provenance, list(events)


def favorable_return(entry_price: float, high: float, low: float, direction: str) -> float:
    if entry_price <= 0:
        return 0.0
    if direction == "LONG":
        return (high - entry_price) / entry_price
    return (entry_price - low) / entry_price


def adverse_return(entry_price: float, high: float, low: float, direction: str) -> float:
    if entry_price <= 0:
        return 0.0
    if direction == "LONG":
        return (low - entry_price) / entry_price
    return (entry_price - high) / entry_price


def mfe_before_entry(candles: list[Candle], event: RejectionEvent) -> float | None:
    start = event.detection_bar
    end = event.entry_candidate_bar
    if start < 0 or end <= start or end >= len(candles):
        return None
    entry_price = candles[start].close
    window = candles[start + 1 : end + 1]
    if not window:
        return None
    if event.direction == "LONG":
        return max(0.0, (max(candle.high for candle in window) - entry_price) / entry_price)
    return max(0.0, (entry_price - min(candle.low for candle in window)) / entry_price)


def forward_window_metrics(candles: list[Candle], *, start_bar: int, direction: str, bars: int, cost_pct: float) -> dict[str, Any]:
    if start_bar < 0 or start_bar + bars >= len(candles):
        return {"return": None, "net_return": None, "mfe": None, "mae": None}
    entry = candles[start_bar].open
    exit_close = candles[start_bar + bars].close
    sign = 1 if direction == "LONG" else -1
    raw_return = ((exit_close - entry) / entry) * sign if entry > 0 else None
    window = candles[start_bar : start_bar + bars + 1]
    if direction == "LONG":
        mfe = (max(candle.high for candle in window) - entry) / entry if entry > 0 else None
        mae = (min(candle.low for candle in window) - entry) / entry if entry > 0 else None
    else:
        mfe = (entry - min(candle.low for candle in window)) / entry if entry > 0 else None
        mae = (entry - max(candle.high for candle in window)) / entry if entry > 0 else None
    return {
        "return": raw_return,
        "net_return": raw_return - cost_pct if raw_return is not None else None,
        "mfe": mfe,
        "mae": mae,
    }


def fixed_exit_return(
    candles: list[Candle],
    *,
    entry_bar: int,
    entry_price: float,
    atr_value: float | None,
    direction: str,
    config: DiagnosticConfig,
) -> dict[str, Any]:
    if entry_bar < 0 or entry_bar >= len(candles) or atr_value is None or atr_value <= 0 or entry_price <= 0:
        return {"gross_return": None, "net_return": None, "outcome": "NO_DATA", "exit_bar": None, "mfe": None, "mae": None}

    stop_distance = config.fixed_exit_stop_atr * atr_value
    target_distance = config.fixed_exit_target_atr * atr_value
    if direction == "LONG":
        stop = entry_price - stop_distance
        target = entry_price + target_distance
    else:
        stop = entry_price + stop_distance
        target = entry_price - target_distance

    mfe = 0.0
    mae = 0.0
    exit_bar = min(len(candles) - 1, entry_bar + config.fixed_exit_max_hold_bars)
    exit_price = candles[exit_bar].close
    outcome = "TIMEOUT"
    for idx in range(entry_bar + 1, min(len(candles), entry_bar + config.fixed_exit_max_hold_bars + 1)):
        candle = candles[idx]
        mfe = max(mfe, favorable_return(entry_price, candle.high, candle.low, direction))
        mae = min(mae, adverse_return(entry_price, candle.high, candle.low, direction))
        if direction == "LONG":
            if candle.low <= stop:
                exit_bar = idx
                exit_price = stop
                outcome = "LOSS"
                break
            if candle.high >= target:
                exit_bar = idx
                exit_price = target
                outcome = "WIN"
                break
        else:
            if candle.high >= stop:
                exit_bar = idx
                exit_price = stop
                outcome = "LOSS"
                break
            if candle.low <= target:
                exit_bar = idx
                exit_price = target
                outcome = "WIN"
                break
    sign = 1 if direction == "LONG" else -1
    gross = ((exit_price - entry_price) / entry_price) * sign
    return {
        "gross_return": gross,
        "net_return": gross - config.round_trip_cost_pct,
        "outcome": outcome,
        "exit_bar": exit_bar,
        "mfe": mfe,
        "mae": mae,
    }


def attach_metrics(events: list[RejectionEvent], candles: list[Candle], atr: list[float | None], config: DiagnosticConfig) -> None:
    for event in events:
        return_start = event.return_start_bar
        entry_candidate_atr = atr[event.entry_candidate_bar] if event.entry_candidate_bar < len(atr) else None
        primary = fixed_exit_return(
            candles,
            entry_bar=return_start,
            entry_price=candles[return_start].open,
            atr_value=entry_candidate_atr,
            direction=event.direction,
            config=config,
        )
        detection = fixed_exit_return(
            candles,
            entry_bar=event.detection_bar,
            entry_price=candles[event.detection_bar].close,
            atr_value=atr[event.detection_bar],
            direction=event.direction,
            config=config,
        )
        post5 = forward_window_metrics(
            candles,
            start_bar=return_start,
            direction=event.direction,
            bars=config.f3_post_entry_bars,
            cost_pct=config.round_trip_cost_pct,
        )
        before = mfe_before_entry(candles, event)
        post_mfe = post5["mfe"]
        consumed_share = None
        if before is not None and post_mfe is not None and (before + post_mfe) > 0:
            consumed_share = before / (before + post_mfe)
        event.metrics = {
            "primary_fixed_exit": primary,
            "detection_bar_fixed_exit_audit_only": detection,
            "post_entry_5bar": post5,
            "mfe_before_entry": before,
            "mfe_post_entry_5bar": post_mfe,
            "consumed_share_secondary": consumed_share,
        }


def monthly_pnl(events: list[RejectionEvent]) -> dict[str, float]:
    buckets: dict[str, float] = defaultdict(float)
    for event in events:
        value = event.metrics.get("primary_fixed_exit", {}).get("net_return")
        if value is None:
            continue
        month = event.return_start_time_utc[:7]
        buckets[month] += float(value)
    return dict(sorted(buckets.items()))


def cohort_summary(events: list[RejectionEvent], candles: list[Candle]) -> dict[str, Any]:
    returns = [event.metrics.get("primary_fixed_exit", {}).get("net_return") for event in events]
    gross_returns = [event.metrics.get("primary_fixed_exit", {}).get("gross_return") for event in events]
    wins = [value for value in returns if value is not None and value > 0]
    detection_returns = [event.metrics.get("detection_bar_fixed_exit_audit_only", {}).get("net_return") for event in events]
    post_mfe = [event.metrics.get("mfe_post_entry_5bar") for event in events]
    before_mfe = [event.metrics.get("mfe_before_entry") for event in events]
    start = candles[0].open_time if candles else None
    end = candles[-1].open_time if candles else None
    days = max(1.0, ((end - start).total_seconds() / 86400.0) if start and end else 1.0)
    return {
        "count": len(events),
        "trades_per_day": len(events) / days,
        "net_profit_factor": profit_factor(returns),
        "gross_profit_factor": profit_factor(gross_returns),
        "net_return_median": safe_median(returns),
        "net_return_mean": safe_mean(returns),
        "gross_return_median": safe_median(gross_returns),
        "win_rate": (len(wins) / len(events)) if events else None,
        "detection_net_profit_factor_audit_only": profit_factor(detection_returns),
        "detection_net_return_median_audit_only": safe_median(detection_returns),
        "mfe_before_entry_median": safe_median(before_mfe),
        "mfe_post_entry_5bar_median": safe_median(post_mfe),
        "consumed_share_secondary_median": safe_median(
            event.metrics.get("consumed_share_secondary") for event in events
        ),
        "monthly_pnl": monthly_pnl(events),
    }


def build_control_events(
    primary_events: list[RejectionEvent],
    candidates: list[RejectionCandidate],
    candles: list[Candle],
    atr: list[float | None],
    flow_by_time: dict[datetime, FlowBar],
    primary_ids: set[str],
    config: DiagnosticConfig,
) -> list[RejectionEvent]:
    candidates_by_key: dict[tuple[str, str], list[RejectionCandidate]] = defaultdict(list)
    high_swings, low_swings = confirmed_swing_maps(candles, left=config.swing_left_bars, right=config.swing_right_bars)
    for candidate in candidates:
        is_extreme = candidate.detection_bar in (low_swings if candidate.direction == "LONG" else high_swings)
        if is_extreme:
            continue
        month = candles[candidate.detection_bar].open_time.strftime("%Y-%m")
        candidates_by_key[(candidate.direction, month)].append(candidate)

    controls: list[RejectionEvent] = []
    used_detection_bars: set[tuple[str, int]] = set()
    for source in primary_events:
        month = source.detection_time_utc[:7]
        pool = candidates_by_key.get((source.direction, month), [])
        if not pool:
            continue
        start = int(hashlib.sha256(source.event_id.encode("utf-8")).hexdigest(), 16) % len(pool)
        selected: RejectionCandidate | None = None
        for offset in range(len(pool)):
            item = pool[(start + offset + config.deterministic_control_seed_shift) % len(pool)]
            key = (item.direction, item.detection_bar)
            if key not in used_detection_bars:
                selected = item
                used_detection_bars.add(key)
                break
        if selected is None:
            continue
        entry = find_entry_candidate(selected, candles, flow_by_time)
        if entry is None:
            continue
        entry_bar, flow = entry
        return_start = entry_bar + 1
        if return_start >= len(candles):
            continue
        cid = event_id("control_random_wicks", selected.direction, candles[selected.detection_bar].open_time.isoformat())
        if cid in primary_ids:
            continue
        controls.append(
            RejectionEvent(
                event_id=cid,
                cohort_source="control_random_wicks",
                direction=selected.direction,
                detection_bar=selected.detection_bar,
                state_known_bar=selected.state_known_bar,
                entry_candidate_bar=entry_bar,
                return_start_bar=return_start,
                label_available_bar=min(len(candles) - 1, return_start + config.fixed_exit_max_hold_bars),
                detection_time_utc=candles[selected.detection_bar].open_time.isoformat(),
                state_known_time_utc=candles[selected.state_known_bar].open_time.isoformat(),
                entry_candidate_time_utc=candles[entry_bar].open_time.isoformat(),
                return_start_time_utc=candles[return_start].open_time.isoformat(),
                zone_bottom=selected.zone_bottom,
                zone_top=selected.zone_top,
                atr_at_detection=selected.atr_at_detection,
                atr_at_entry_candidate=atr[entry_bar],
                confluence={
                    "source": "aggtrade_buckets.cvd",
                    "tfi": flow.tfi,
                    "cvd_delta": flow.cvd_delta,
                    "source_rows": flow.source_rows,
                },
            )
        )
    return controls


def detect_wick_candidates_without_swing_filter(
    candles: list[Candle],
    atr: list[float | None],
    config: DiagnosticConfig,
) -> list[RejectionCandidate]:
    original = DiagnosticConfig(
        symbol=config.symbol,
        timeframe=config.timeframe,
        study_start=config.study_start,
        study_end=config.study_end,
        atr_period=config.atr_period,
        swing_left_bars=0,
        swing_right_bars=0,
        wick_to_body_min=config.wick_to_body_min,
        wick_range_share_min=config.wick_range_share_min,
        wick_atr_min=config.wick_atr_min,
        fixed_exit_stop_atr=config.fixed_exit_stop_atr,
        fixed_exit_target_atr=config.fixed_exit_target_atr,
        fixed_exit_max_hold_bars=config.fixed_exit_max_hold_bars,
        f3_post_entry_bars=config.f3_post_entry_bars,
        round_trip_cost_pct=config.round_trip_cost_pct,
        deterministic_control_seed_shift=config.deterministic_control_seed_shift,
        max_json_events=config.max_json_events,
    )
    return detect_rejection_candidates(candles, atr, original)


def build_baseline_levels(candles: list[Candle], config: DiagnosticConfig) -> pd.DataFrame:
    scanner_config = ScannerConfig(
        symbol=config.symbol,
        timeframe=config.timeframe,
        include_session_extremes=False,
        include_previous_periods=False,
        include_equal_clusters=True,
        include_anchored_vwap=False,
        include_round_numbers=False,
        include_liquidation_placeholder=False,
        atr_period=config.atr_period,
        swing_left_bars=3,
        swing_right_bars=1,
        equal_cluster_min_hits=EVENT_STUDY_BASELINE_DEFAULTS["min_hits"],
        equal_cluster_lookback_bars=EVENT_STUDY_BASELINE_DEFAULTS["equal_level_lookback"],
        equal_cluster_tolerance_atr=EVENT_STUDY_BASELINE_DEFAULTS["equal_level_tol_atr"],
        metadata={"consumer": "reclaim_rejection_feasibility_v1_baseline"},
    )
    return scan_levels(candles_to_frame(candles), scanner_config)


def build_reclaim_swing_baseline(
    candles: list[Candle],
    atr: list[float | None],
    config: DiagnosticConfig,
) -> list[RejectionEvent]:
    levels = build_baseline_levels(candles, config)
    if levels.empty:
        return []
    by_time = {candle.open_time: candle.index for candle in candles}
    events: list[RejectionEvent] = []
    seen: set[tuple[str, int]] = set()
    for _, row in levels[levels["category"] == "equal_cluster"].sort_values(["swept_at", "level_id"], kind="stable").iterrows():
        if pd.isna(row["swept_at"]):
            continue
        swept_at = pd.Timestamp(row["swept_at"]).to_pydatetime().astimezone(timezone.utc)
        idx = by_time.get(swept_at)
        if idx is None or idx + 1 >= len(candles):
            continue
        atr_value = atr[idx]
        if atr_value is None or atr_value <= 0:
            continue
        candle = candles[idx]
        side = str(row["side"])
        direction = "LONG" if side == "LOW" else "SHORT" if side == "HIGH" else None
        if direction is None:
            continue
        price = float(row["price"])
        top = float(row["top"])
        bottom = float(row["bottom"])
        proximity = abs(candle.open - price) / atr_value
        if proximity > EVENT_STUDY_BASELINE_DEFAULTS["sweep_proximity_atr"]:
            continue
        if direction == "LONG":
            swept = candle.low < bottom - EVENT_STUDY_BASELINE_DEFAULTS["wick_min_atr"] * atr_value
            reclaimed = candle.close > top
        else:
            swept = candle.high > top + EVENT_STUDY_BASELINE_DEFAULTS["wick_min_atr"] * atr_value
            reclaimed = candle.close < bottom
        key = (direction, idx)
        if not swept or not reclaimed or key in seen:
            continue
        seen.add(key)
        return_start = idx + 1
        events.append(
            RejectionEvent(
                event_id=event_id("reclaim_swing_baseline", direction, candle.open_time.isoformat(), row["level_id"]),
                cohort_source="reclaim_swing_baseline",
                direction=direction,
                detection_bar=idx,
                state_known_bar=idx,
                entry_candidate_bar=idx,
                return_start_bar=return_start,
                label_available_bar=min(len(candles) - 1, return_start + config.fixed_exit_max_hold_bars),
                detection_time_utc=candle.open_time.isoformat(),
                state_known_time_utc=candle.open_time.isoformat(),
                entry_candidate_time_utc=candle.open_time.isoformat(),
                return_start_time_utc=candles[return_start].open_time.isoformat(),
                zone_bottom=bottom,
                zone_top=top,
                atr_at_detection=atr_value,
                atr_at_entry_candidate=atr_value,
                level_id=str(row["level_id"]),
                level_category=str(row["category"]),
                level_available_at=pd.Timestamp(row["available_at"]).isoformat(),
                confluence={"source": "baseline_no_tfi_cvd_gate", "tfi": None, "cvd_delta": None, "source_rows": 0},
            )
        )
    return events


def aligned_monthly_correlation(primary_monthly: dict[str, float], baseline_monthly: dict[str, float]) -> dict[str, Any]:
    months = sorted(set(primary_monthly) | set(baseline_monthly))
    xs = [primary_monthly.get(month, 0.0) for month in months]
    ys = [baseline_monthly.get(month, 0.0) for month in months]
    non_zero_overlap = sum(1 for month in months if primary_monthly.get(month, 0.0) != 0.0 and baseline_monthly.get(month, 0.0) != 0.0)
    corr = pearson(xs, ys) if non_zero_overlap >= 3 else None
    return {
        "months": months,
        "primary_series": dict(zip(months, xs)),
        "baseline_series": dict(zip(months, ys)),
        "non_zero_overlap_months": non_zero_overlap,
        "pearson": corr,
        "status": "OK" if non_zero_overlap >= 3 and corr is not None else "INCONCLUSIVE_DATA_GAP",
    }


def gate_result(name: str, measurement: str, value: Any, threshold: str, status: str, rationale: str) -> dict[str, Any]:
    return {
        "rule": name,
        "measurement": measurement,
        "value": value,
        "threshold": threshold,
        "status": status,
        "rationale": rationale,
    }


def evaluate_gates(primary: dict[str, Any], baseline: dict[str, Any], monthly_corr: dict[str, Any]) -> dict[str, Any]:
    f1_value = primary.get("net_profit_factor")
    f2_value = primary.get("net_return_median")
    before = primary.get("mfe_before_entry_median")
    post = primary.get("mfe_post_entry_5bar_median")
    f3_value = (before / post) if before is not None and post not in (None, 0) else None
    f4_value = (primary.get("trades_per_day") or 0.0) - (baseline.get("trades_per_day") or 0.0)
    f5_value = monthly_corr.get("pearson")
    timing_pf = primary.get("net_profit_factor")
    detection_pf = primary.get("detection_net_profit_factor_audit_only")
    timing_med = primary.get("net_return_median")
    detection_med = primary.get("detection_net_return_median_audit_only")
    f6_better = False
    if detection_pf is not None and timing_pf is not None:
        f6_better = detection_pf > timing_pf * 1.30
    if detection_med is not None and timing_med is not None:
        if timing_med <= 0 < detection_med:
            f6_better = True
        elif timing_med > 0 and detection_med > timing_med * 1.30:
            f6_better = True

    gates = [
        gate_result("F-1", "Timing-correct PF from return_start_bar fixed-exit net P&L", f1_value, ">= 1.5", "PASS" if f1_value is not None and f1_value >= 1.5 else "FAIL", "Weak trade-management edge invalidates."),
        gate_result("F-2", "Median net expectancy after 0.10% round-trip cost", f2_value, ">= 0", "PASS" if f2_value is not None and f2_value >= 0 else "FAIL", "Costs must not erase the edge."),
        gate_result("F-3", "median(mfe_before_entry) / median(mfe_post_entry_5bar)", f3_value, "<= 0.70", "PASS" if f3_value is not None and f3_value <= 0.70 else "FAIL", "Entry is too late when pre-entry opportunity dominates."),
        gate_result("F-4", "Throughput increase versus reclaim_swing_baseline", f4_value, ">= 0.2 trades/day", "PASS" if f4_value >= 0.2 else "FAIL", "M1 identified throughput as bottleneck."),
        gate_result("F-5", "Pearson monthly P&L correlation with reclaim_swing_baseline", f5_value, "<= 0.5", "INCONCLUSIVE_DATA_GAP" if monthly_corr.get("status") == "INCONCLUSIVE_DATA_GAP" else "PASS" if f5_value is not None and f5_value <= 0.5 else "FAIL", "High correlation means no diversification benefit."),
        gate_result("F-6", "Detection-bar edge versus timing-correct edge", {"detection_pf": detection_pf, "timing_pf": timing_pf, "detection_median": detection_med, "timing_median": timing_med}, "<= 30% better", "FAIL" if f6_better else "PASS", "Detection-bar edge superiority signals timing leakage."),
    ]
    statuses = {gate["rule"]: gate["status"] for gate in gates}
    non_f5_fail = any(gate["status"] == "FAIL" for gate in gates if gate["rule"] != "F-5")
    if non_f5_fail or statuses["F-5"] == "FAIL":
        final = "HYPOTHESIS_INVALIDATED"
    elif statuses["F-5"] == "INCONCLUSIVE_DATA_GAP":
        final = "INCONCLUSIVE_DATA_GAP"
    else:
        final = "HYPOTHESIS_PASSED_REQUIRES_CLAUDE_AUDIT"
    return {"final_verdict": final, "rules": gates}


def resolve_default_db() -> tuple[Path, dict[str, Any]]:
    if CANONICAL_DB_PATH.exists():
        return CANONICAL_DB_PATH, {"canonical_db_present": True, "fallback_used": False}
    return FALLBACK_RESEARCH_SNAPSHOT, {
        "canonical_db_present": False,
        "fallback_used": True,
        "fallback_reason": "research_lab/data/crowded_unwind_backtest.db is absent on this PC; using local research snapshot, not storage/btc_bot.db",
    }


def build_payload(
    *,
    db_path: Path,
    db_resolution: dict[str, Any],
    candles: list[Candle],
    data_quality: DataQuality,
    flow_quality: dict[str, Any],
    candidates: list[RejectionCandidate],
    primary_events: list[RejectionEvent],
    ablation_events: list[RejectionEvent],
    baseline_events: list[RejectionEvent],
    control_events: list[RejectionEvent],
    config: DiagnosticConfig,
) -> dict[str, Any]:
    primary_summary = cohort_summary(primary_events, candles)
    ablation_summary = cohort_summary(ablation_events, candles)
    baseline_summary = cohort_summary(baseline_events, candles)
    control_summary = cohort_summary(control_events, candles)
    monthly_corr = aligned_monthly_correlation(primary_summary["monthly_pnl"], baseline_summary["monthly_pnl"])
    gates = evaluate_gates(primary_summary, baseline_summary, monthly_corr)
    return {
        "manifest": {
            "milestone": "M3_RECLAIM_REJECTION_DIAGNOSTIC_V1",
            "research_only": True,
            "production_changes": False,
            "deterministic_generation": True,
            "generated_at_utc": "DETERMINISTIC_NO_WALL_CLOCK",
            "db_path": str(db_path),
            "db_resolution": db_resolution,
            "symbol": config.symbol,
            "timeframe": config.timeframe,
            "study_start": config.study_start,
            "study_end": config.study_end,
            "config": json_ready(config),
            "event_study_baseline_defaults": EVENT_STUDY_BASELINE_DEFAULTS,
        },
        "data_quality": json_ready(data_quality),
        "flow_quality": flow_quality,
        "candidate_counts": {
            "wick_rejection_at_confirmed_swing": len(candidates),
            "reclaim_rejection_without_level_provenance": len(ablation_events),
            "reclaim_rejection_with_level_provenance": len(primary_events),
            "reclaim_swing_baseline": len(baseline_events),
            "control_random_wicks": len(control_events),
        },
        "cohorts": {
            "reclaim_rejection_with_level_provenance": primary_summary,
            "reclaim_rejection_without_level_provenance": ablation_summary,
            "reclaim_swing_baseline": baseline_summary,
            "control_random_wicks": control_summary,
        },
        "monthly_correlation": monthly_corr,
        "falsification_gates": gates,
        "events": {
            "primary": json_ready(primary_events[: config.max_json_events]),
            "ablation_sample": json_ready(ablation_events[: min(len(ablation_events), 1000)]),
            "baseline_sample": json_ready(baseline_events[: min(len(baseline_events), 1000)]),
            "control_sample": json_ready(control_events[: min(len(control_events), 1000)]),
        },
        "events_truncated": {
            "primary": len(primary_events) > config.max_json_events,
            "ablation_sample": len(ablation_events) > 1000,
            "baseline_sample": len(baseline_events) > 1000,
            "control_sample": len(control_events) > 1000,
        },
    }


def fmt(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


def render_report(payload: dict[str, Any], sha256_value: str) -> str:
    manifest = payload["manifest"]
    quality = payload["data_quality"]
    cohorts = payload["cohorts"]
    gates = payload["falsification_gates"]
    lines = [
        "# RECLAIM_REJECTION_FEASIBILITY_V1",
        "",
        "## Scope",
        "",
        "Research-only diagnostic. No production code, execution path, settings, schema, or production database query is changed by this run.",
        "",
        "## Dataset",
        "",
        f"- DB: `{manifest['db_path']}`",
        f"- Canonical DB present: `{manifest['db_resolution'].get('canonical_db_present')}`",
        f"- Fallback used: `{manifest['db_resolution'].get('fallback_used')}`",
        f"- Symbol/timeframe: `{manifest['symbol']}` `{manifest['timeframe']}`",
        f"- Study window: `{manifest['study_start']}` to `{manifest['study_end']}`",
        f"- Rows: {quality['rows']}",
        f"- Range UTC: {quality['start_time_utc']} to {quality['end_time_utc']}",
        f"- Missing bar gaps: {quality['missing_bar_gaps']}",
        f"- OHLC violations: {quality['ohlc_violations']}",
        f"- Flow source: `{payload['flow_quality'].get('source')}`",
        "",
        "## Cohorts",
        "",
        "| Cohort | Count | Trades/Day | Net PF | Net Median | MFE Before Med | MFE Post 5 Med |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name in [
        "reclaim_rejection_with_level_provenance",
        "reclaim_rejection_without_level_provenance",
        "reclaim_swing_baseline",
        "control_random_wicks",
    ]:
        summary = cohorts[name]
        lines.append(
            f"| {name} | {summary['count']} | {fmt(summary['trades_per_day'])} | {fmt(summary['net_profit_factor'])} | {fmt(summary['net_return_median'])} | {fmt(summary['mfe_before_entry_median'])} | {fmt(summary['mfe_post_entry_5bar_median'])} |"
        )
    lines.extend([
        "",
        "## Falsification Gates",
        "",
        "| Rule | Measurement | Value | Threshold | Status |",
        "| --- | --- | ---: | ---: | --- |",
    ])
    for gate in gates["rules"]:
        lines.append(
            f"| {gate['rule']} | {gate['measurement']} | {fmt(gate['value'])} | {gate['threshold']} | {gate['status']} |"
        )
    lines.extend([
        "",
        "## Baseline Correlation",
        "",
        f"- F-5 status: `{payload['monthly_correlation']['status']}`",
        f"- Non-zero overlap months: {payload['monthly_correlation']['non_zero_overlap_months']}",
        f"- Pearson correlation: {fmt(payload['monthly_correlation']['pearson'])}",
        "",
        "## Verdict",
        "",
        f"- Final verdict: `{gates['final_verdict']}`",
        "- F-3 formula used: `median(mfe_before_entry) / median(mfe_post_entry_5bar)`.",
        "- Secondary consumed-share metric is reported but not used as the F-3 gate.",
        "- CVD proxy uses `aggtrade_buckets.cvd`, not `cvd_price_history`.",
        "- Trial-00095 comparison is reference-only; F-5 baseline uses event-study defaults approximated with `level_scanner` equal-cluster facts.",
        "",
        "## Artifacts",
        "",
        f"- JSON SHA256: `{sha256_value}`",
        "",
    ])
    return "\n".join(lines)


def write_artifacts(payload: dict[str, Any], json_path: Path, sha_path: Path, report_path: Path) -> str:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    sha_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    json_text = json.dumps(json_ready(payload), indent=2, sort_keys=True, allow_nan=False)
    json_path.write_text(json_text + "\n", encoding="utf-8")
    sha = hashlib.sha256(json_path.read_bytes()).hexdigest().upper()
    sha_path.write_text(f"{sha}  {json_path.name}\n", encoding="utf-8")
    report_path.write_text(render_report(payload, sha), encoding="utf-8")
    return sha


def run_diagnostic(
    *,
    db_path: Path | None,
    output_json: Path,
    output_sha: Path,
    report_path: Path,
    config: DiagnosticConfig,
) -> dict[str, Any]:
    if db_path is None:
        resolved_db, db_resolution = resolve_default_db()
    else:
        resolved_db = db_path
        db_resolution = {
            "canonical_db_present": CANONICAL_DB_PATH.exists(),
            "fallback_used": False,
            "operator_supplied_db": True,
        }
    if not resolved_db.exists():
        raise FileNotFoundError(f"Research DB not found: {resolved_db}")

    start = parse_ts(config.study_start)
    end = parse_ts(config.study_end)
    with sqlite3.connect(f"file:{resolved_db.resolve().as_posix()}?mode=ro", uri=True) as conn:
        candles = load_candles(conn, symbol=config.symbol, timeframe=config.timeframe, start=start, end=end)
        flow_by_time, flow_quality = load_flow_15m(conn, symbol=config.symbol, start=start, end=end)
    if not candles:
        raise ValueError(f"No candles found for {config.symbol} {config.timeframe} in {resolved_db}")
    data_quality = validate_candles(candles)
    if data_quality.ohlc_violations:
        raise ValueError(f"OHLC validation failed with {data_quality.ohlc_violations} violations")
    atr = compute_atr_series(candles, config.atr_period)

    candidates = detect_rejection_candidates(candles, atr, config)
    ablation_events = build_rejection_events(candidates, candles, atr, flow_by_time, config)
    provenance_levels = build_provenance_levels(candles, config)
    primary_events, ablation_events = attach_level_provenance(ablation_events, provenance_levels)
    attach_metrics(primary_events, candles, atr, config)
    attach_metrics(ablation_events, candles, atr, config)

    baseline_events = build_reclaim_swing_baseline(candles, atr, config)
    attach_metrics(baseline_events, candles, atr, config)

    control_candidates = detect_wick_candidates_without_swing_filter(candles, atr, config)
    control_events = build_control_events(
        primary_events,
        control_candidates,
        candles,
        atr,
        flow_by_time,
        {event.event_id for event in primary_events},
        config,
    )
    attach_metrics(control_events, candles, atr, config)

    payload = build_payload(
        db_path=resolved_db,
        db_resolution=db_resolution,
        candles=candles,
        data_quality=data_quality,
        flow_quality=flow_quality,
        candidates=candidates,
        primary_events=primary_events,
        ablation_events=ablation_events,
        baseline_events=baseline_events,
        control_events=control_events,
        config=config,
    )
    sha = write_artifacts(payload, output_json, output_sha, report_path)
    payload["artifact_sha256"] = sha
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-path", type=Path, default=None)
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--timeframe", default="15m")
    parser.add_argument("--study-start", default="2022-01-01")
    parser.add_argument("--study-end", default="2026-03-01")
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-sha", type=Path, default=DEFAULT_OUTPUT_SHA)
    parser.add_argument("--report-path", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--max-json-events", type=int, default=50000)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = DiagnosticConfig(
        symbol=args.symbol,
        timeframe=args.timeframe,
        study_start=args.study_start,
        study_end=args.study_end,
        max_json_events=args.max_json_events,
    )
    payload = run_diagnostic(
        db_path=args.db_path,
        output_json=args.output_json,
        output_sha=args.output_sha,
        report_path=args.report_path,
        config=config,
    )
    print(
        json.dumps(
            {
                "output_json": str(args.output_json),
                "output_sha": str(args.output_sha),
                "report": str(args.report_path),
                "verdict": payload["falsification_gates"]["final_verdict"],
                "candidate_counts": payload["candidate_counts"],
                "sha256": payload["artifact_sha256"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
