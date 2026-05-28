"""Research-only volume-confirmed range breakout feasibility diagnostic.

Implements VOLUME_CONFIRMED_RANGE_BREAKOUT_FEASIBILITY_V1:

    range known at bar i-1
    breakout/volume/TFI state known at bar i close
    entry candidate at bar i+1
    primary returns measured from bar i+1

This module is intentionally isolated from the live path. It reads SQLite market
data and writes research artifacts only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = PROJECT_ROOT / "research_lab" / "data" / "crowded_unwind_backtest.db"
DEFAULT_REPORT_PATH = PROJECT_ROOT / "research_lab" / "reports" / "volume_confirmed_range_breakout_feasibility_v1.md"
DEFAULT_JSON_PATH = PROJECT_ROOT / "research_lab" / "reports" / "volume_confirmed_range_breakout_feasibility_v1.json"
DEFAULT_STORE_CANDIDATES = (
    PROJECT_ROOT / "research_lab" / "research_lab.db.v3",
    PROJECT_ROOT / "research_lab" / "research_lab.db",
    PROJECT_ROOT / "research_lab" / "research_lab_server.db",
)

TRIAL_00095_REFERENCE = {
    "er": 2.1,
    "profit_factor": 4.6,
    "trades": 271,
    "win_rate": 0.56,
    "source": "approved planning document / milestone tracker reference",
}

FOLD_WINDOWS = (
    ("fold_1", datetime(2020, 9, 1, tzinfo=timezone.utc), datetime(2021, 12, 31, 23, 59, tzinfo=timezone.utc)),
    ("fold_2", datetime(2022, 1, 1, tzinfo=timezone.utc), datetime(2023, 6, 30, 23, 59, tzinfo=timezone.utc)),
    ("fold_3", datetime(2023, 7, 1, tzinfo=timezone.utc), datetime(2024, 12, 31, 23, 59, tzinfo=timezone.utc)),
    ("fold_4", datetime(2025, 1, 1, tzinfo=timezone.utc), datetime(2026, 3, 28, 23, 59, tzinfo=timezone.utc)),
)


@dataclass(frozen=True, slots=True)
class DiagnosticConfig:
    symbol: str = "BTCUSDT"
    timeframe: str = "15m"
    range_lookback_bars: int = 20
    range_baseline_bars: int = 120
    compression_percentile: float = 35.0
    wide_range_percentile: float = 65.0
    breakout_distance_pct: float = 0.0015
    volume_multiple: float = 1.5
    low_volume_multiple: float = 1.0
    entry_delay_bars: int = 1
    shifted_entry_delay_bars: int = 3
    outcome_horizon_bars: int = 20
    round_trip_cost_pct: float = 0.0010
    fixed_risk_pct: float = 0.01
    random_offset_bars: int = 137
    max_serialized_events_per_cohort: int = 200

    @property
    def min_prior_bars(self) -> int:
        return self.range_lookback_bars + self.range_baseline_bars


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
class AggTradeBucket:
    bucket_time: datetime
    taker_buy_volume: float
    taker_sell_volume: float
    tfi: float
    cvd: float


@dataclass(frozen=True, slots=True)
class BreakoutState:
    detection_bar: int
    direction: str
    range_high: float
    range_low: float
    range_width_pct: float
    range_width_threshold: float
    wide_range_threshold: float
    breakout_distance_pct: float
    volume: float
    volume_baseline: float
    volume_multiple_actual: float
    tfi: float
    cvd: float


@dataclass(frozen=True, slots=True)
class CohortEvent:
    cohort: str
    range_detection_bar: int
    detection_bar: int
    state_known_bar: int
    confirmation_bar: int
    entry_candidate_bar: int
    label_available_bar: int
    return_start_bar: int
    direction: str
    detection_time_utc: str
    state_known_time_utc: str
    entry_time_utc: str
    entry_price: float
    exit_bar: int
    exit_price: float
    gross_return_pct: float
    net_return_pct: float
    r_return: float
    return_5bar_pct: float | None
    return_10bar_pct: float | None
    return_20bar_pct: float
    mfe_before_entry: float
    mfe_after_entry: float
    mae_after_entry: float
    total_mfe: float
    mfe_consumed_pct: float
    entry_to_mfe_bars: int | None
    range_high: float
    range_low: float
    range_width_pct: float
    range_width_threshold: float
    wide_range_threshold: float
    breakout_distance_pct: float
    volume: float
    volume_baseline: float
    volume_multiple_actual: float
    tfi: float
    cvd: float
    metadata: dict[str, Any]


def parse_ts(raw: Any) -> datetime:
    if isinstance(raw, datetime):
        return raw.astimezone(timezone.utc) if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
    text = str(raw).replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    return parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def table_names(conn: sqlite3.Connection) -> set[str]:
    return {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}


def table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def inspect_schema(conn: sqlite3.Connection) -> dict[str, Any]:
    names = table_names(conn)
    required = {
        "candles": {"symbol", "timeframe", "open_time", "open", "high", "low", "close", "volume"},
        "aggtrade_buckets": {
            "symbol",
            "bucket_time",
            "timeframe",
            "taker_buy_volume",
            "taker_sell_volume",
            "tfi",
            "cvd",
        },
    }
    provisional = ["ohlcv_1h", "features_1h", "trials", "trial_trades", "aggtrade", "funding_rate"]
    missing_required: dict[str, list[str]] = {}
    for table, cols in required.items():
        if table not in names:
            missing_required[table] = sorted(cols)
            continue
        missing = cols - table_columns(conn, table)
        if missing:
            missing_required[table] = sorted(missing)
    return {
        "tables": sorted(names),
        "required_tables": sorted(required),
        "missing_required": missing_required,
        "provisional_tables_present": {name: name in names for name in provisional},
        "adapted_market_schema": {
            "price_action": "candles" if "candles" in names else None,
            "volume_flow": "aggtrade_buckets" if "aggtrade_buckets" in names else None,
            "aggtrade": "aggtrade_buckets" if "aggtrade_buckets" in names else None,
            "funding": "funding" if "funding" in names else None,
            "open_interest": "open_interest" if "open_interest" in names else None,
            "benchmark_trades": "trial_trades" if "trial_trades" in names else None,
        },
    }


def load_candles(conn: sqlite3.Connection, config: DiagnosticConfig) -> list[Candle]:
    rows = conn.execute(
        """
        SELECT open_time, open, high, low, close, volume
        FROM candles
        WHERE symbol = ? AND timeframe = ?
        ORDER BY open_time ASC
        """,
        (config.symbol, config.timeframe),
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


def load_aggtrade_buckets(conn: sqlite3.Connection, config: DiagnosticConfig) -> dict[str, AggTradeBucket]:
    rows = conn.execute(
        """
        SELECT bucket_time, taker_buy_volume, taker_sell_volume, tfi, cvd
        FROM aggtrade_buckets
        WHERE symbol = ? AND timeframe = ?
        ORDER BY bucket_time ASC
        """,
        (config.symbol, config.timeframe),
    ).fetchall()
    buckets: dict[str, AggTradeBucket] = {}
    for row in rows:
        bucket_time = parse_ts(row[0])
        buckets[iso(bucket_time)] = AggTradeBucket(
            bucket_time=bucket_time,
            taker_buy_volume=float(row[1] or 0.0),
            taker_sell_volume=float(row[2] or 0.0),
            tfi=float(row[3] or 0.0),
            cvd=float(row[4] or 0.0),
        )
    return buckets


def data_quality(candles: list[Candle], buckets: dict[str, AggTradeBucket]) -> dict[str, Any]:
    duplicate_timestamps = len(candles) - len({c.open_time for c in candles})
    non_monotonic = 0
    missing_gaps = 0
    step_seconds = None
    if len(candles) >= 2:
        deltas = [
            int((right.open_time - left.open_time).total_seconds())
            for left, right in zip(candles, candles[1:])
        ]
        positive = [delta for delta in deltas if delta > 0]
        step_seconds = min(positive) if positive else None
        non_monotonic = sum(1 for delta in deltas if delta <= 0)
        if step_seconds:
            missing_gaps = sum(1 for delta in deltas if delta > step_seconds)
    ohlc_violations = sum(
        1
        for c in candles
        if c.high < max(c.open, c.close, c.low) or c.low > min(c.open, c.close, c.high)
    )
    zero_volume = sum(1 for c in candles if c.volume <= 0)
    aligned = sum(1 for c in candles if iso(c.open_time) in buckets)
    return {
        "candles": {
            "rows": len(candles),
            "start_time_utc": iso(candles[0].open_time) if candles else None,
            "end_time_utc": iso(candles[-1].open_time) if candles else None,
            "duplicate_timestamps": duplicate_timestamps,
            "non_monotonic_timestamps": non_monotonic,
            "ohlc_violations": ohlc_violations,
            "missing_bar_gaps": missing_gaps,
            "inferred_step_seconds": step_seconds,
            "zero_volume_bars": zero_volume,
        },
        "aggtrade_buckets": {
            "rows": len(buckets),
            "aligned_15m_candle_rows": aligned,
            "missing_aligned_candle_rows": len(candles) - aligned,
            "alignment_pct": (aligned / len(candles)) if candles else 0.0,
        },
    }


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (pct / 100.0) * (len(ordered) - 1)
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    weight = rank - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def signed_return(direction: str, entry_price: float, exit_price: float) -> float:
    if direction == "LONG":
        return (exit_price - entry_price) / entry_price
    return (entry_price - exit_price) / entry_price


def favorable_move(candles: list[Candle], start: int, end: int, reference: float, direction: str) -> float:
    if start > end or start >= len(candles):
        return 0.0
    end = min(end, len(candles) - 1)
    if direction == "LONG":
        return max(0.0, max(c.high for c in candles[start : end + 1]) - reference)
    return max(0.0, reference - min(c.low for c in candles[start : end + 1]))


def adverse_move(candles: list[Candle], start: int, end: int, reference: float, direction: str) -> float:
    if start > end or start >= len(candles):
        return 0.0
    end = min(end, len(candles) - 1)
    if direction == "LONG":
        return max(0.0, reference - min(c.low for c in candles[start : end + 1]))
    return max(0.0, max(c.high for c in candles[start : end + 1]) - reference)


def entry_to_mfe_offset(candles: list[Candle], start: int, end: int, direction: str) -> int | None:
    if start > end or start >= len(candles):
        return None
    end = min(end, len(candles) - 1)
    subset = candles[start : end + 1]
    if not subset:
        return None
    if direction == "LONG":
        best = max(range(len(subset)), key=lambda offset: subset[offset].high)
    else:
        best = min(range(len(subset)), key=lambda offset: subset[offset].low)
    return best


def range_width_for_end(candles: list[Candle], end_idx: int, lookback: int) -> float | None:
    start = end_idx - lookback + 1
    if start < 0 or end_idx >= len(candles):
        return None
    window = candles[start : end_idx + 1]
    close = candles[end_idx].close
    if close <= 0:
        return None
    return (max(c.high for c in window) - min(c.low for c in window)) / close


def compute_range_widths(candles: list[Candle], lookback: int) -> list[float | None]:
    return [range_width_for_end(candles, idx, lookback) for idx in range(len(candles))]


def breakout_state(
    candles: list[Candle],
    buckets: dict[str, AggTradeBucket],
    idx: int,
    config: DiagnosticConfig,
    *,
    range_widths: list[float | None] | None = None,
    wide_range: bool = False,
) -> BreakoutState | None:
    if idx < config.min_prior_bars:
        return None
    if idx + config.outcome_horizon_bars >= len(candles):
        return None
    candle = candles[idx]
    bucket = buckets.get(iso(candle.open_time))
    if bucket is None:
        return None

    range_window = candles[idx - config.range_lookback_bars : idx]
    if len(range_window) != config.range_lookback_bars:
        return None
    range_high = max(c.high for c in range_window)
    range_low = min(c.low for c in range_window)
    prev_close = candles[idx - 1].close
    if prev_close <= 0 or candle.close <= 0:
        return None
    range_width_pct = (range_high - range_low) / prev_close

    recent_widths: list[float] = []
    widths = range_widths
    for end_idx in range(idx - config.range_baseline_bars, idx):
        width = widths[end_idx] if widths is not None else range_width_for_end(
            candles,
            end_idx,
            config.range_lookback_bars,
        )
        if width is not None:
            recent_widths.append(width)
    if len(recent_widths) < config.range_baseline_bars // 2:
        return None
    low_threshold = percentile(recent_widths, config.compression_percentile)
    high_threshold = percentile(recent_widths, config.wide_range_percentile)
    if wide_range:
        if range_width_pct < high_threshold:
            return None
    elif range_width_pct > low_threshold:
        return None

    direction: str | None = None
    boundary: float | None = None
    if candle.close > range_high:
        direction = "LONG"
        boundary = range_high
    elif candle.close < range_low:
        direction = "SHORT"
        boundary = range_low
    if direction is None or boundary is None:
        return None

    distance = abs(candle.close - boundary) / candle.close
    if distance < config.breakout_distance_pct:
        return None

    baseline_volumes = [c.volume for c in range_window if c.volume > 0]
    if len(baseline_volumes) < config.range_lookback_bars // 2:
        return None
    volume_baseline = median(baseline_volumes)
    if volume_baseline <= 0:
        return None

    return BreakoutState(
        detection_bar=idx,
        direction=direction,
        range_high=range_high,
        range_low=range_low,
        range_width_pct=range_width_pct,
        range_width_threshold=low_threshold,
        wide_range_threshold=high_threshold,
        breakout_distance_pct=distance,
        volume=candle.volume,
        volume_baseline=volume_baseline,
        volume_multiple_actual=candle.volume / volume_baseline if volume_baseline else 0.0,
        tfi=bucket.tfi,
        cvd=bucket.cvd,
    )


def has_volume_spike(state: BreakoutState, config: DiagnosticConfig) -> bool:
    return state.volume > 0 and state.volume >= config.volume_multiple * state.volume_baseline


def has_low_volume(state: BreakoutState, config: DiagnosticConfig) -> bool:
    return state.volume < config.low_volume_multiple * state.volume_baseline


def has_tfi_alignment(state: BreakoutState) -> bool:
    return (state.direction == "LONG" and state.tfi > 0) or (state.direction == "SHORT" and state.tfi < 0)


def has_opposite_tfi(state: BreakoutState) -> bool:
    return (state.direction == "LONG" and state.tfi < 0) or (state.direction == "SHORT" and state.tfi > 0)


def build_event(
    *,
    cohort: str,
    candles: list[Candle],
    state: BreakoutState,
    entry_delay_bars: int,
    config: DiagnosticConfig,
    metadata: dict[str, Any] | None = None,
) -> CohortEvent | None:
    detection_bar = state.detection_bar
    entry_bar = detection_bar + entry_delay_bars
    exit_bar = entry_bar + config.outcome_horizon_bars - 1
    if exit_bar >= len(candles) or entry_bar >= len(candles):
        return None

    entry_price = candles[entry_bar].open
    exit_price = candles[exit_bar].close
    if entry_price <= 0:
        return None

    gross = signed_return(state.direction, entry_price, exit_price)
    net = gross - config.round_trip_cost_pct
    r_return = net / config.fixed_risk_pct if config.fixed_risk_pct else net

    def horizon_return(bars: int) -> float | None:
        target = entry_bar + bars - 1
        if target >= len(candles):
            return None
        return signed_return(state.direction, entry_price, candles[target].close) - config.round_trip_cost_pct

    detection_close = candles[detection_bar].close
    mfe_before = favorable_move(candles, detection_bar, detection_bar, detection_close, state.direction)
    mfe_after = favorable_move(candles, entry_bar, exit_bar, entry_price, state.direction)
    mae_after = adverse_move(candles, entry_bar, exit_bar, entry_price, state.direction)
    total_mfe = max(0.0, mfe_before) + max(0.0, mfe_after)
    consumed = 1.0 if total_mfe <= 0 else min(max(mfe_before / total_mfe, 0.0), 1.0)

    return CohortEvent(
        cohort=cohort,
        range_detection_bar=detection_bar - 1,
        detection_bar=detection_bar,
        state_known_bar=detection_bar,
        confirmation_bar=detection_bar,
        entry_candidate_bar=entry_bar,
        label_available_bar=entry_bar,
        return_start_bar=entry_bar,
        direction=state.direction,
        detection_time_utc=iso(candles[detection_bar].open_time),
        state_known_time_utc=iso(candles[detection_bar].open_time),
        entry_time_utc=iso(candles[entry_bar].open_time),
        entry_price=entry_price,
        exit_bar=exit_bar,
        exit_price=exit_price,
        gross_return_pct=gross,
        net_return_pct=net,
        r_return=r_return,
        return_5bar_pct=horizon_return(5),
        return_10bar_pct=horizon_return(10),
        return_20bar_pct=net,
        mfe_before_entry=mfe_before,
        mfe_after_entry=mfe_after,
        mae_after_entry=mae_after,
        total_mfe=total_mfe,
        mfe_consumed_pct=consumed,
        entry_to_mfe_bars=entry_to_mfe_offset(candles, entry_bar, exit_bar, state.direction),
        range_high=state.range_high,
        range_low=state.range_low,
        range_width_pct=state.range_width_pct,
        range_width_threshold=state.range_width_threshold,
        wide_range_threshold=state.wide_range_threshold,
        breakout_distance_pct=state.breakout_distance_pct,
        volume=state.volume,
        volume_baseline=state.volume_baseline,
        volume_multiple_actual=state.volume_multiple_actual,
        tfi=state.tfi,
        cvd=state.cvd,
        metadata=metadata or {},
    )


def build_cohorts(
    candles: list[Candle],
    buckets: dict[str, AggTradeBucket],
    config: DiagnosticConfig,
) -> dict[str, list[CohortEvent]]:
    cohorts = {
        "main_volume_confirmed_range_breakout": [],
        "control_price_only_range_breakouts": [],
        "control_breakout_without_volume_spike": [],
        "control_opposite_flow_breakout": [],
        "control_shifted_entry": [],
        "control_random_offset": [],
        "control_wide_range_breakout": [],
    }
    main_detection_bars: set[int] = set()
    base_states: list[BreakoutState] = []
    range_widths = compute_range_widths(candles, config.range_lookback_bars)

    max_idx = len(candles) - config.outcome_horizon_bars - config.entry_delay_bars
    for idx in range(config.min_prior_bars, max_idx):
        state = breakout_state(candles, buckets, idx, config, range_widths=range_widths)
        if state is None:
            continue
        base_states.append(state)

        price_only = build_event(
            cohort="control_price_only_range_breakouts",
            candles=candles,
            state=state,
            entry_delay_bars=config.entry_delay_bars,
            config=config,
            metadata={"control": "same range breakout without volume or TFI confirmation"},
        )
        if price_only:
            cohorts["control_price_only_range_breakouts"].append(price_only)

        if has_low_volume(state, config) and has_tfi_alignment(state):
            event = build_event(
                cohort="control_breakout_without_volume_spike",
                candles=candles,
                state=state,
                entry_delay_bars=config.entry_delay_bars,
                config=config,
                metadata={"control": "breakout with aligned TFI but low volume"},
            )
            if event:
                cohorts["control_breakout_without_volume_spike"].append(event)

        if has_volume_spike(state, config) and has_opposite_tfi(state):
            event = build_event(
                cohort="control_opposite_flow_breakout",
                candles=candles,
                state=state,
                entry_delay_bars=config.entry_delay_bars,
                config=config,
                metadata={"control": "volume breakout with opposite TFI"},
            )
            if event:
                cohorts["control_opposite_flow_breakout"].append(event)

        if has_volume_spike(state, config) and has_tfi_alignment(state):
            event = build_event(
                cohort="main_volume_confirmed_range_breakout",
                candles=candles,
                state=state,
                entry_delay_bars=config.entry_delay_bars,
                config=config,
                metadata={"mechanism": "compressed range breakout plus volume spike and TFI alignment"},
            )
            if event:
                cohorts["main_volume_confirmed_range_breakout"].append(event)
                main_detection_bars.add(state.detection_bar)
            shifted = build_event(
                cohort="control_shifted_entry",
                candles=candles,
                state=state,
                entry_delay_bars=config.shifted_entry_delay_bars,
                config=config,
                metadata={"control": "same main signal delayed to bar i+3"},
            )
            if shifted:
                cohorts["control_shifted_entry"].append(shifted)

    for event_index, state in enumerate(base_states):
        if state.detection_bar not in main_detection_bars:
            continue
        shifted_idx = state.detection_bar + config.random_offset_bars
        if shifted_idx in main_detection_bars:
            continue
        if shifted_idx + config.entry_delay_bars + config.outcome_horizon_bars - 1 >= len(candles):
            continue
        shifted_state = BreakoutState(
            detection_bar=shifted_idx,
            direction=state.direction if event_index % 2 == 0 else ("SHORT" if state.direction == "LONG" else "LONG"),
            range_high=state.range_high,
            range_low=state.range_low,
            range_width_pct=state.range_width_pct,
            range_width_threshold=state.range_width_threshold,
            wide_range_threshold=state.wide_range_threshold,
            breakout_distance_pct=state.breakout_distance_pct,
            volume=state.volume,
            volume_baseline=state.volume_baseline,
            volume_multiple_actual=state.volume_multiple_actual,
            tfi=state.tfi,
            cvd=state.cvd,
        )
        event = build_event(
            cohort="control_random_offset",
            candles=candles,
            state=shifted_state,
            entry_delay_bars=config.entry_delay_bars,
            config=config,
            metadata={
                "control": "main event shifted by deterministic +137 bars",
                "source_detection_bar": state.detection_bar,
            },
        )
        if event:
            cohorts["control_random_offset"].append(event)

    for idx in range(config.min_prior_bars, max_idx):
        state = breakout_state(candles, buckets, idx, config, range_widths=range_widths, wide_range=True)
        if state is None:
            continue
        if not (has_volume_spike(state, config) and has_tfi_alignment(state)):
            continue
        event = build_event(
            cohort="control_wide_range_breakout",
            candles=candles,
            state=state,
            entry_delay_bars=config.entry_delay_bars,
            config=config,
            metadata={"control": "same breakout requirements but prior range above 65th percentile"},
        )
        if event:
            cohorts["control_wide_range_breakout"].append(event)

    return cohorts


def profit_factor(values: list[float]) -> float:
    wins = sum(v for v in values if v > 0)
    losses = abs(sum(v for v in values if v < 0))
    if losses == 0:
        return 1_000_000.0 if wins > 0 else 0.0
    return wins / losses


def fold_metrics(events: list[CohortEvent]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for fold_name, start, end in FOLD_WINDOWS:
        subset = [
            event
            for event in events
            if start <= parse_ts(event.detection_time_utc) <= end
        ]
        returns = [event.r_return for event in subset]
        net = [event.net_return_pct for event in subset]
        result.append(
            {
                "fold": fold_name,
                "count": len(subset),
                "start_time_utc": iso(start),
                "end_time_utc": iso(end),
                "er": mean(returns) if returns else 0.0,
                "median_net_return_pct": median(net) if net else 0.0,
                "win_rate": (sum(1 for value in returns if value > 0) / len(returns)) if returns else 0.0,
                "positive_median_net": bool(net and median(net) > 0),
            }
        )
    return result


def metric_summary(events: list[CohortEvent]) -> dict[str, Any]:
    returns = [event.r_return for event in events]
    net = [event.net_return_pct for event in events]
    consumed = [event.mfe_consumed_pct for event in events]
    folds = fold_metrics(events)
    winning = [event.r_return for event in events if event.r_return > 0]
    losing = [abs(event.r_return) for event in events if event.r_return < 0]
    avg_win = mean(winning) if winning else 0.0
    avg_loss = mean(losing) if losing else 0.0
    return {
        "count": len(events),
        "er": mean(returns) if returns else 0.0,
        "median_r": median(returns) if returns else 0.0,
        "median_net_return_pct": median(net) if net else 0.0,
        "mean_net_return_pct": mean(net) if net else 0.0,
        "win_rate": (sum(1 for value in returns if value > 0) / len(returns)) if returns else 0.0,
        "profit_factor": profit_factor(returns),
        "avg_win_r": avg_win,
        "avg_loss_r": avg_loss,
        "avg_win_loss_ratio": (avg_win / avg_loss) if avg_loss > 0 else (1_000_000.0 if avg_win > 0 else 0.0),
        "median_mfe_consumed_pct": median(consumed) if consumed else None,
        "median_mfe_before_entry": median([event.mfe_before_entry for event in events]) if events else 0.0,
        "median_mfe_after_entry": median([event.mfe_after_entry for event in events]) if events else 0.0,
        "median_mae_after_entry": median([event.mae_after_entry for event in events]) if events else 0.0,
        "median_entry_to_mfe_bars": median([event.entry_to_mfe_bars for event in events if event.entry_to_mfe_bars is not None]) if events else None,
        "positive_folds": sum(1 for item in folds if item["positive_median_net"]),
        "folds": folds,
    }


def apply_gates(cohort_metrics: dict[str, dict[str, Any]], data_quality_payload: dict[str, Any]) -> dict[str, Any]:
    main = cohort_metrics["main_volume_confirmed_range_breakout"]
    controls = {
        name: metrics
        for name, metrics in cohort_metrics.items()
        if name != "main_volume_confirmed_range_breakout"
    }
    control_outperformers = [
        name for name, metrics in controls.items() if metrics["count"] > 0 and metrics["er"] > main["er"]
    ]
    consumed = main.get("median_mfe_consumed_pct")
    stop_reasons: list[str] = []
    if main["count"] < 100:
        stop_reasons.append("sample_size_below_100")
    if consumed is None:
        stop_reasons.append("mfe_consumed_unavailable")
    elif consumed > 0.70:
        stop_reasons.append("median_mfe_consumed_gt_70pct")
    if main["median_net_return_pct"] <= 0:
        stop_reasons.append("median_net_return_lte_0")
    if main["er"] < 1.2:
        stop_reasons.append("post_entry_er_lt_1_2")
    if main["profit_factor"] < 1.2:
        stop_reasons.append("profit_factor_lt_1_2")
    if main["win_rate"] < 0.45 and main["avg_win_loss_ratio"] < 1.5:
        stop_reasons.append("weak_win_rate_and_payoff")
    if control_outperformers:
        stop_reasons.append("control_cohort_outperforms_main")
    if main["positive_folds"] < 2:
        stop_reasons.append("walk_forward_fewer_than_2_positive_folds")
    missing_aligned = data_quality_payload["aggtrade_buckets"]["missing_aligned_candle_rows"]
    candle_rows = data_quality_payload["candles"]["rows"]
    if candle_rows and missing_aligned / candle_rows > 0.10:
        stop_reasons.append("aggtrade_alignment_gap_gt_10pct")

    explore = (
        main["median_net_return_pct"] > 0
        and main["er"] > 1.5
        and main["profit_factor"] > 1.5
        and (main["win_rate"] > 0.52 or (main["win_rate"] > 0.45 and main["avg_win_loss_ratio"] >= 1.5))
        and consumed is not None
        and consumed < 0.60
        and not control_outperformers
        and main["positive_folds"] >= 3
        and main["count"] >= 200
    )
    if stop_reasons:
        recommendation = "STOP"
    elif explore:
        recommendation = "EXPLORE"
    else:
        recommendation = "INCONCLUSIVE"
    return {
        "recommendation": recommendation,
        "stop_reasons": stop_reasons,
        "explore_gate_passed": explore,
        "control_outperformers": control_outperformers,
        "rules": {
            "STOP": [
                "median net return after costs <= 0",
                "post-entry ER < 1.2",
                "profit factor < 1.2",
                "median MFE consumed before entry > 70%",
                "any primary control cohort outperforms main on ER",
                "fewer than 2 of 4 folds positive",
                "sample size < 100",
            ],
            "EXPLORE": [
                "median net return after costs > 0",
                "post-entry ER > 1.5",
                "profit factor > 1.5",
                "median MFE consumed before entry < 60%",
                "main beats all controls on ER",
                "at least 3 of 4 folds positive",
                "sample size >= 200",
            ],
            "INCONCLUSIVE": ["anything between STOP and EXPLORE"],
        },
    }


def load_trial_00095_benchmark(store_candidates: tuple[Path, ...] = DEFAULT_STORE_CANDIDATES) -> dict[str, Any]:
    benchmark: dict[str, Any] = {
        "reference": TRIAL_00095_REFERENCE,
        "exact_trial_trades_available": False,
        "trial_trades_schema_status": "missing in inspected databases",
        "store_metrics": None,
    }
    for store in store_candidates:
        if not store.exists():
            continue
        try:
            with sqlite3.connect(f"file:{store}?mode=ro", uri=True) as conn:
                conn.row_factory = sqlite3.Row
                names = table_names(conn)
                if "trial_trades" in names:
                    benchmark["exact_trial_trades_available"] = True
                    benchmark["trial_trades_schema_status"] = f"available in {store}"
                if "trials" in names:
                    rows = conn.execute(
                        """
                        SELECT trial_id, metrics_json, rejected_reason
                        FROM trials
                        WHERE trial_id LIKE '%trial-00095%'
                        ORDER BY created_at_utc DESC
                        LIMIT 10
                        """
                    ).fetchall()
                    if rows:
                        parsed = []
                        for row in rows:
                            parsed.append(
                                {
                                    "store": str(store),
                                    "trial_id": row["trial_id"],
                                    "metrics": json.loads(row["metrics_json"]),
                                    "rejected_reason": row["rejected_reason"],
                                }
                            )
                        benchmark["store_metrics"] = parsed
                        return benchmark
        except sqlite3.DatabaseError:
            continue
    return benchmark


def event_overlap_with_trade_log(conn: sqlite3.Connection, main_events: list[CohortEvent]) -> dict[str, Any]:
    names = table_names(conn)
    if "trade_log" not in names:
        return {"available": False, "reason": "trade_log table missing"}
    rows = conn.execute("SELECT opened_at FROM trade_log WHERE opened_at IS NOT NULL").fetchall()
    trade_times = {iso(parse_ts(row[0]))[:16] for row in rows}
    event_times = {event.entry_time_utc[:16] for event in main_events}
    overlap = trade_times & event_times
    return {
        "available": True,
        "note": "Local trade_log is not an exact trial_trades table; use as rough timestamp overlap only.",
        "trade_log_count": len(trade_times),
        "main_event_count": len(event_times),
        "overlap_count": len(overlap),
        "overlap_pct_of_main": (len(overlap) / len(event_times)) if event_times else 0.0,
    }


def serialize_events(events: list[CohortEvent], limit: int) -> list[dict[str, Any]]:
    return [asdict(event) for event in events[:limit]]


def run_diagnostic(
    *,
    db_path: Path,
    report_path: Path,
    json_path: Path,
    config: DiagnosticConfig,
) -> dict[str, Any]:
    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
        schema = inspect_schema(conn)
        if schema["missing_required"]:
            raise RuntimeError(f"Required schema missing: {schema['missing_required']}")

        candles = load_candles(conn, config)
        buckets = load_aggtrade_buckets(conn, config)
        quality = data_quality(candles, buckets)
        cohorts = build_cohorts(candles, buckets, config)
        metrics = {name: metric_summary(events) for name, events in cohorts.items()}
        gates = apply_gates(metrics, quality)
        benchmark = load_trial_00095_benchmark()
        benchmark["trade_log_overlap"] = event_overlap_with_trade_log(
            conn,
            cohorts["main_volume_confirmed_range_breakout"],
        )

    payload = {
        "manifest": {
            "diagnostic": "VOLUME_CONFIRMED_RANGE_BREAKOUT_FEASIBILITY_V1",
            "research_only": True,
            "production_changes": False,
            "db_path": str(db_path),
            "report_path": str(report_path),
            "json_path": str(json_path),
            "generated_at_utc": iso(datetime.now(timezone.utc)),
        },
        "config": asdict(config),
        "schema": schema,
        "data_quality": quality,
        "timing_model": {
            "range_detection_bar": "i-1",
            "detection_bar": "i",
            "state_known_bar": "i",
            "confirmation_bar": "i",
            "entry_candidate_bar": "i+1",
            "label_available_bar": "i+1",
            "return_start_bar": "i+1",
            "primary_returns_from_detection_bar": False,
        },
        "cohort_metrics": metrics,
        "benchmark_comparison": benchmark,
        "invalidation_gates": gates,
        "events_sample": {
            name: serialize_events(events, config.max_serialized_events_per_cohort)
            for name, events in cohorts.items()
        },
    }

    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_text = json.dumps(payload, indent=2, sort_keys=True, allow_nan=False)
    json_path.write_text(json_text, encoding="utf-8")
    sha = hashlib.sha256(json_path.read_bytes()).hexdigest().upper()
    payload["manifest"]["json_sha256"] = sha

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(render_report(payload), encoding="utf-8")
    return payload


def fmt_float(value: Any, digits: int = 6) -> str:
    if value is None:
        return "n/a"
    if value == float("inf"):
        return "inf"
    return f"{float(value):.{digits}f}"


def render_report(payload: dict[str, Any]) -> str:
    recommendation = payload["invalidation_gates"]["recommendation"]
    metrics = payload["cohort_metrics"]
    main = metrics["main_volume_confirmed_range_breakout"]
    lines = [
        "# VOLUME_CONFIRMED_RANGE_BREAKOUT_FEASIBILITY_V1",
        "",
        "## Executive Summary",
        "",
        f"Recommendation: **{recommendation}**",
        "",
        "This is a research-only diagnostic. It did not modify production code, settings, trial-00095, execution, FeatureEngine, SignalEngine, Governance, or Risk.",
        "",
        f"- Main cohort events: `{main['count']}`",
        f"- Main post-entry ER proxy: `{fmt_float(main['er'])}`",
        f"- Main profit factor proxy: `{fmt_float(main['profit_factor'])}`",
        f"- Main win rate: `{fmt_float(main['win_rate'])}`",
        f"- Main median net return: `{fmt_float(main['median_net_return_pct'])}`",
        f"- Main median MFE consumed before entry: `{fmt_float(main['median_mfe_consumed_pct'])}`",
        f"- STOP reasons: `{', '.join(payload['invalidation_gates']['stop_reasons']) or 'none'}`",
        "",
        "## Mechanism",
        "",
        "- Define compressed range from prior 20 completed 15m bars.",
        "- Detect completed close outside prior range at bar `i`.",
        "- Require breakout-bar volume >= 1.5x prior 20-bar median volume.",
        "- Require aligned 15m TFI direction.",
        "- Enter at bar `i+1`; primary returns start at `i+1`.",
        "",
        "## Schema Pre-Flight",
        "",
        f"- Required schema missing: `{payload['schema']['missing_required']}`",
        f"- Provisional table names present: `{payload['schema']['provisional_tables_present']}`",
        f"- Adapted schema: `{payload['schema']['adapted_market_schema']}`",
        "",
        "## Data Quality",
        "",
        f"- Candles: `{payload['data_quality']['candles']}`",
        f"- Aggtrade buckets: `{payload['data_quality']['aggtrade_buckets']}`",
        "",
        "## Timing Model Verification",
        "",
        "| Bar | Value |",
        "| --- | --- |",
    ]
    for key, value in payload["timing_model"].items():
        lines.append(f"| `{key}` | `{value}` |")
    lines.extend(
        [
            "",
            "Primary returns are measured from `entry_candidate_bar`, not `detection_bar` or intrabar breakout price.",
            "",
            "## Cohort Metrics",
            "",
            "| Cohort | Count | ER | Median R | PF | Win Rate | Median Net | Median MFE Consumed | Positive Folds |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for name, row in metrics.items():
        lines.append(
            f"| `{name}` | {row['count']} | {fmt_float(row['er'])} | {fmt_float(row['median_r'])} | "
            f"{fmt_float(row['profit_factor'])} | {fmt_float(row['win_rate'])} | "
            f"{fmt_float(row['median_net_return_pct'])} | {fmt_float(row['median_mfe_consumed_pct'])} | "
            f"{row['positive_folds']} |"
        )
    lines.extend(
        [
            "",
            "## MFE Accessibility",
            "",
            f"- Main median MFE before entry: `{fmt_float(main['median_mfe_before_entry'])}`",
            f"- Main median MFE after entry: `{fmt_float(main['median_mfe_after_entry'])}`",
            f"- Main median MAE after entry: `{fmt_float(main['median_mae_after_entry'])}`",
            f"- Main median entry-to-MFE bars: `{fmt_float(main['median_entry_to_mfe_bars'])}`",
            f"- 70% consumed threshold breached: `{main['median_mfe_consumed_pct'] is not None and main['median_mfe_consumed_pct'] > 0.70}`",
            "",
            "## Control Cohorts",
            "",
            "- Price-only range breakouts: same compressed range and breakout, no volume/TFI requirements.",
            "- Breakout without volume spike: aligned TFI but low breakout-bar volume.",
            "- Opposite-flow breakout: volume spike but TFI points opposite breakout direction.",
            "- Shifted-entry: same main signal, entry delayed from `i+1` to `i+3`.",
            "- Random-offset: main events shifted by deterministic +137 bars.",
            "- Wide-range breakout: same breakout/volume/TFI requirements but prior range above 65th percentile.",
            "",
            f"Control outperformers: `{payload['invalidation_gates']['control_outperformers']}`",
            "",
            "## Trial-00095 Benchmark Comparison",
            "",
            f"- Reference benchmark: `{payload['benchmark_comparison']['reference']}`",
            f"- Exact `trial_trades` available: `{payload['benchmark_comparison']['exact_trial_trades_available']}`",
            f"- Trial trade schema status: `{payload['benchmark_comparison']['trial_trades_schema_status']}`",
            f"- Store metrics discovered: `{payload['benchmark_comparison']['store_metrics'] is not None}`",
            f"- Trade-log overlap: `{payload['benchmark_comparison']['trade_log_overlap']}`",
            "",
            "Exact `trial_trades` are not assumed. Any local `trade_log` overlap is documented as rough timestamp overlap only.",
            "",
            "## Walk-Forward Metrics",
            "",
            "| Fold | Count | ER | Median Net | Win Rate | Positive Median Net |",
            "| --- | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for fold in main["folds"]:
        lines.append(
            f"| `{fold['fold']}` | {fold['count']} | {fmt_float(fold['er'])} | "
            f"{fmt_float(fold['median_net_return_pct'])} | {fmt_float(fold['win_rate'])} | "
            f"`{fold['positive_median_net']}` |"
        )
    lines.extend(
        [
            "",
            "## Invalidation Criteria Evaluation",
            "",
            f"- Recommendation: `{recommendation}`",
            f"- STOP reasons: `{payload['invalidation_gates']['stop_reasons']}`",
            f"- EXPLORE gate passed: `{payload['invalidation_gates']['explore_gate_passed']}`",
            "",
            "## Artifact",
            "",
            f"- JSON path: `{payload['manifest']['json_path']}`",
            f"- JSON SHA256: `{payload['manifest']['json_sha256']}`",
            "",
            f"## Recommendation: {recommendation}",
            "",
            f"**Reason:** {'; '.join(payload['invalidation_gates']['stop_reasons']) if recommendation == 'STOP' else 'Gate evaluation did not trigger STOP and determines the next research status.'}",
            "",
            "**Next:** Claude Code audits this diagnostic implementation and result before any follow-up work.",
        ]
    )
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--report-path", type=Path, default=DEFAULT_REPORT_PATH)
    parser.add_argument("--json-path", type=Path, default=DEFAULT_JSON_PATH)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = run_diagnostic(
        db_path=args.db_path,
        report_path=args.report_path,
        json_path=args.json_path,
        config=DiagnosticConfig(),
    )
    print(json.dumps(payload["invalidation_gates"], indent=2, sort_keys=True))
    print(f"report={args.report_path}")
    print(f"json={args.json_path}")


if __name__ == "__main__":
    main()
