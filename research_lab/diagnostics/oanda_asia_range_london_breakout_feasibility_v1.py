"""Research-only OANDA Asia range to London breakout feasibility diagnostic.

Implements OANDA_ASIA_RANGE_LONDON_BREAKOUT_FEASIBILITY_V1:

    Asia range is built from completed 00:00-07:00 UTC M15 bars only.
    London breakout is known at the close of bar i in 07:00-09:00 UTC.
    Entry candidate is bar i+1 open.
    Primary returns are measured from bar i+1 open, never from detection bar.

This module is isolated from the live path. It reads validated cached OANDA
mid-price candles, runs a deterministic research diagnostic, and writes
research artifacts only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, time, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_PATH = PROJECT_ROOT / "research_lab" / "analysis_output" / "oanda_eur_usd_m15_candles_20240101_20260529.json"
DEFAULT_REPORT_PATH = PROJECT_ROOT / "research_lab" / "reports" / "oanda_asia_range_london_breakout_feasibility_v1.md"
DEFAULT_JSON_PATH = PROJECT_ROOT / "research_lab" / "reports" / "oanda_asia_range_london_breakout_feasibility_v1.json"

TRIAL_00095_REFERENCE = {
    "er": 2.121,
    "profit_factor": 4.216,
    "win_rate": 0.5657,
    "trades": 274,
    "source": "trial_00095_conditional_edge_attribution_v1.md",
}

FOLD_WINDOWS = (
    ("fold_1_2024H1", datetime(2024, 1, 1, tzinfo=timezone.utc), datetime(2024, 7, 1, tzinfo=timezone.utc)),
    ("fold_2_2024H2", datetime(2024, 7, 1, tzinfo=timezone.utc), datetime(2025, 1, 1, tzinfo=timezone.utc)),
    ("fold_3_2025", datetime(2025, 1, 1, tzinfo=timezone.utc), datetime(2026, 1, 1, tzinfo=timezone.utc)),
    ("fold_4_2026", datetime(2026, 1, 1, tzinfo=timezone.utc), datetime(2027, 1, 1, tzinfo=timezone.utc)),
)

PRIMARY_COHORT = "main_asia_range_london_breakout"
CONTROL_COHORTS = (
    "control_random_session_timing_137",
    "control_opposite_direction",
    "control_same_breakout_outside_london_ny",
    "control_breakout_without_prior_asia_compression",
    "control_compression_without_breakout",
    "control_shifted_entry_plus2",
    "control_weekday_shuffled",
    "control_previous_day_range_breakout",
)
MIN_DECISION_CONTROL_EVENTS = 25


@dataclass(frozen=True, slots=True)
class DiagnosticConfig:
    instrument: str = "EUR_USD"
    granularity: str = "M15"
    atr_period: int = 14
    asia_start: str = "00:00"
    asia_end: str = "07:00"
    london_start: str = "07:00"
    london_end: str = "09:00"
    ny_start: str = "13:00"
    ny_end: str = "16:00"
    breakout_buffer_atr: float = 0.05
    risk_buffer_atr: float = 0.05
    primary_horizon_bars: int = 5
    secondary_horizon_bars: int = 8
    tertiary_horizon_bars: int = 10
    primary_cost_pct: float = 0.00015
    sensitivity_costs_pct: tuple[float, ...] = (0.00010, 0.00015, 0.00020)
    random_offset_bars: int = 137
    weekday_shuffle_offset_bars: int = 96
    expected_asia_bars: int = 28
    expected_london_bars: int = 8
    max_serialized_events_per_cohort: int = 75


@dataclass(frozen=True, slots=True)
class Candle:
    index: int
    time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True, slots=True)
class RangeReference:
    session_date: str
    start_index: int
    end_index: int
    high: float
    low: float
    open: float
    close: float
    range_pct: float
    range_atr: float
    range_width_bucket: str
    source: str


@dataclass(frozen=True, slots=True)
class BreakoutSignal:
    cohort: str
    session_date: str
    direction: str
    range_reference: RangeReference
    detection_bar: int
    atr14: float
    metadata: dict[str, Any]


@dataclass(frozen=True, slots=True)
class CohortEvent:
    cohort: str
    session_date: str
    direction: str
    range_start_bar: int
    range_end_bar: int
    range_known_bar: int
    detection_bar: int
    state_known_bar: int
    confirmation_bar: int
    entry_candidate_bar: int
    label_available_bar: int
    return_start_bar: int
    detection_time_utc: str
    state_known_time_utc: str
    entry_time_utc: str
    exit_time_utc: str
    entry_price: float
    exit_price: float
    stop_reference_price: float
    risk_pct: float
    gross_return_pct: float
    net_return_pct: float
    r_return: float
    return_5bar_pct: float | None
    return_8bar_pct: float | None
    return_10bar_pct: float | None
    mfe_before_entry: float
    mfe_after_entry: float
    mae_after_entry: float
    total_mfe: float
    mfe_consumed_pct: float
    entry_to_mfe_bars: int | None
    asia_high: float
    asia_low: float
    asia_range_pct: float
    asia_range_atr: float
    atr14: float
    breakout_buffer_price: float
    metadata: dict[str, Any]


def parse_ts(value: Any) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def parse_hhmm(value: str) -> time:
    hour, minute = value.split(":")
    return time(int(hour), int(minute), tzinfo=timezone.utc)


def in_window(ts: datetime, start: str, end: str) -> bool:
    current = ts.timetz()
    return parse_hhmm(start) <= current < parse_hhmm(end)


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * pct / 100.0
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    weight = rank - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def load_candles(path: Path) -> list[Candle]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    return [
        Candle(
            index=index,
            time=parse_ts(row["time"]),
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
            volume=float(row.get("volume", 0.0)),
        )
        for index, row in enumerate(rows)
    ]


def data_quality(candles: list[Candle]) -> dict[str, Any]:
    bad_ohlc = 0
    duplicates = 0
    gaps_gt_24h = 0
    gaps_gt_72h = 0
    max_gap_hours = 0.0
    seen: set[str] = set()
    prev: datetime | None = None
    for candle in candles:
        key = iso(candle.time)
        if key in seen:
            duplicates += 1
        seen.add(key)
        if not (
            candle.high >= candle.low
            and candle.high >= candle.open
            and candle.high >= candle.close
            and candle.low <= candle.open
            and candle.low <= candle.close
        ):
            bad_ohlc += 1
        if prev is not None:
            gap_hours = (candle.time - prev).total_seconds() / 3600.0
            max_gap_hours = max(max_gap_hours, gap_hours)
            if gap_hours > 24:
                gaps_gt_24h += 1
            if gap_hours > 72:
                gaps_gt_72h += 1
        prev = candle.time
    gate = "PASS" if len(candles) >= 30000 and bad_ohlc == 0 and duplicates == 0 else "BLOCKED"
    return {
        "count": len(candles),
        "first": iso(candles[0].time) if candles else None,
        "last": iso(candles[-1].time) if candles else None,
        "ohlc_bad_rows": bad_ohlc,
        "duplicates": duplicates,
        "gaps_gt_24h": gaps_gt_24h,
        "gaps_gt_72h": gaps_gt_72h,
        "max_gap_hours": round(max_gap_hours, 2),
        "data_gate": gate,
    }


def compute_atr(candles: list[Candle], end_index: int, period: int = 14) -> float:
    if end_index < 1:
        return 0.0
    start = max(1, end_index - period + 1)
    true_ranges: list[float] = []
    for idx in range(start, end_index + 1):
        candle = candles[idx]
        prev_close = candles[idx - 1].close
        true_ranges.append(
            max(
                candle.high - candle.low,
                abs(candle.high - prev_close),
                abs(candle.low - prev_close),
            )
        )
    return mean(true_ranges) if true_ranges else 0.0


def group_by_date(candles: list[Candle]) -> dict[str, list[Candle]]:
    grouped: dict[str, list[Candle]] = defaultdict(list)
    for candle in candles:
        grouped[candle.time.date().isoformat()].append(candle)
    return dict(grouped)


def window_candles(day: list[Candle], start: str, end: str) -> list[Candle]:
    return [candle for candle in day if in_window(candle.time, start, end)]


def make_range(
    candles: list[Candle],
    session_date: str,
    atr: float,
    bucket_threshold: float,
    source: str,
) -> RangeReference | None:
    if not candles:
        return None
    high = max(candle.high for candle in candles)
    low = min(candle.low for candle in candles)
    mid = (high + low) / 2.0
    range_pct = 0.0 if mid == 0 else (high - low) / mid
    return RangeReference(
        session_date=session_date,
        start_index=candles[0].index,
        end_index=candles[-1].index,
        high=high,
        low=low,
        open=candles[0].open,
        close=candles[-1].close,
        range_pct=range_pct,
        range_atr=(high - low) / atr if atr > 0 else 0.0,
        range_width_bucket="top_half" if range_pct >= bucket_threshold else "bottom_half",
        source=source,
    )


def build_asia_ranges(
    candles: list[Candle],
    config: DiagnosticConfig,
) -> tuple[dict[str, RangeReference], dict[str, list[Candle]], dict[str, Any]]:
    grouped = group_by_date(candles)
    raw_widths: list[float] = []
    candidates: list[tuple[str, list[Candle], float]] = []
    skipped_incomplete = 0
    for session_date, day in grouped.items():
        asia = window_candles(day, config.asia_start, config.asia_end)
        if len(asia) != config.expected_asia_bars:
            skipped_incomplete += 1
            continue
        atr = compute_atr(candles, asia[-1].index, config.atr_period)
        high = max(candle.high for candle in asia)
        low = min(candle.low for candle in asia)
        mid = (high + low) / 2.0
        raw_widths.append(0.0 if mid == 0 else (high - low) / mid)
        candidates.append((session_date, asia, atr))
    threshold = median(raw_widths) if raw_widths else 0.0
    ranges: dict[str, RangeReference] = {}
    valid_days: dict[str, list[Candle]] = {}
    for session_date, asia, atr in candidates:
        ref = make_range(asia, session_date, atr, threshold, "same_day_asia")
        if ref:
            ranges[session_date] = ref
            valid_days[session_date] = grouped[session_date]
    return ranges, valid_days, {
        "asia_range_width_median": threshold,
        "complete_asia_sessions": len(ranges),
        "skipped_incomplete_asia_sessions": skipped_incomplete,
    }


def previous_trading_day_ranges(
    candles: list[Candle],
    config: DiagnosticConfig,
    bucket_threshold: float,
) -> dict[str, RangeReference]:
    grouped = group_by_date(candles)
    ordered_dates = sorted(grouped)
    refs: dict[str, RangeReference] = {}
    previous_ref: RangeReference | None = None
    for session_date in ordered_dates:
        day = grouped[session_date]
        day_bars = [candle for candle in day if time(0, 0, tzinfo=timezone.utc) <= candle.time.timetz() < time(23, 59, tzinfo=timezone.utc)]
        if previous_ref is not None:
            refs[session_date] = previous_ref
        if day_bars:
            atr = compute_atr(candles, day_bars[-1].index, config.atr_period)
            previous_ref = make_range(day_bars, session_date, atr, bucket_threshold, "previous_trading_day")
    return refs


def detect_first_breakout(
    candles: list[Candle],
    source: RangeReference,
    window: list[Candle],
    config: DiagnosticConfig,
) -> BreakoutSignal | None:
    for candle in window:
        atr = compute_atr(candles, candle.index, config.atr_period)
        if atr <= 0:
            continue
        buffer_price = config.breakout_buffer_atr * atr
        if candle.close > source.high + buffer_price:
            return BreakoutSignal(
                cohort=PRIMARY_COHORT,
                session_date=source.session_date,
                direction="LONG",
                range_reference=source,
                detection_bar=candle.index,
                atr14=atr,
                metadata={"breakout_buffer_price": buffer_price},
            )
        if candle.close < source.low - buffer_price:
            return BreakoutSignal(
                cohort=PRIMARY_COHORT,
                session_date=source.session_date,
                direction="SHORT",
                range_reference=source,
                detection_bar=candle.index,
                atr14=atr,
                metadata={"breakout_buffer_price": buffer_price},
            )
    return None


def opposite_direction(direction: str) -> str:
    return "SHORT" if direction == "LONG" else "LONG"


def _gross_return(entry: float, exit_price: float, direction: str) -> float:
    if direction == "LONG":
        return (exit_price - entry) / entry
    return (entry - exit_price) / entry


def _mfe_mae(
    candles: list[Candle],
    detection_index: int,
    entry_index: int,
    exit_index: int,
    entry_price: float,
    direction: str,
) -> tuple[float, float, float, float, int | None]:
    detection = candles[detection_index]
    before_window = candles[detection_index:entry_index]
    after_window = candles[entry_index:exit_index + 1]
    if direction == "LONG":
        mfe_before = max((candle.high - detection.close for candle in before_window), default=0.0)
        mfe_after = max((candle.high - entry_price for candle in after_window), default=0.0)
        mae_after = max((entry_price - candle.low for candle in after_window), default=0.0)
        best_offset = max(((candle.high, offset) for offset, candle in enumerate(after_window)), default=(0.0, None))[1]
    else:
        mfe_before = max((detection.close - candle.low for candle in before_window), default=0.0)
        mfe_after = max((entry_price - candle.low for candle in after_window), default=0.0)
        mae_after = max((candle.high - entry_price for candle in after_window), default=0.0)
        best_offset = max(((-candle.low, offset) for offset, candle in enumerate(after_window)), default=(0.0, None))[1]
    mfe_before = max(0.0, mfe_before)
    mfe_after = max(0.0, mfe_after)
    mae_after = max(0.0, mae_after)
    total = mfe_before + mfe_after
    consumed = mfe_before / total if total > 0 else 0.0
    return mfe_before, mfe_after, mae_after, consumed, best_offset


def build_event(
    cohort: str,
    candles: list[Candle],
    signal: BreakoutSignal,
    config: DiagnosticConfig,
    entry_delay_bars: int = 1,
    direction: str | None = None,
    cost_pct: float | None = None,
    fixed_risk_pct: float | None = None,
    metadata: dict[str, Any] | None = None,
) -> CohortEvent | None:
    direction = direction or signal.direction
    cost = config.primary_cost_pct if cost_pct is None else cost_pct
    entry_index = signal.detection_bar + entry_delay_bars
    exit_index = entry_index + config.primary_horizon_bars
    if entry_index >= len(candles) or exit_index >= len(candles):
        return None
    entry = candles[entry_index]
    exit_candle = candles[exit_index]
    ref = signal.range_reference
    buffer_price = config.risk_buffer_atr * signal.atr14
    if direction == "LONG":
        stop_reference = ref.low - buffer_price
        risk_pct = abs(entry.open - stop_reference) / entry.open if entry.open else 0.0
    else:
        stop_reference = ref.high + buffer_price
        risk_pct = abs(stop_reference - entry.open) / entry.open if entry.open else 0.0
    if fixed_risk_pct is not None:
        risk_pct = fixed_risk_pct
        stop_reference = entry.open * (1 - risk_pct) if direction == "LONG" else entry.open * (1 + risk_pct)
    if risk_pct <= 0:
        return None

    gross = _gross_return(entry.open, exit_candle.close, direction)
    net = gross - cost
    r_return = net / risk_pct
    secondary_index = entry_index + config.secondary_horizon_bars
    tertiary_index = entry_index + config.tertiary_horizon_bars
    return_8 = _gross_return(entry.open, candles[secondary_index].close, direction) if secondary_index < len(candles) else None
    return_10 = _gross_return(entry.open, candles[tertiary_index].close, direction) if tertiary_index < len(candles) else None
    mfe_before, mfe_after, mae_after, consumed, best_offset = _mfe_mae(
        candles,
        signal.detection_bar,
        entry_index,
        exit_index,
        entry.open,
        direction,
    )
    merged_metadata = dict(signal.metadata)
    if metadata:
        merged_metadata.update(metadata)
    merged_metadata["round_trip_cost_pct"] = cost
    return CohortEvent(
        cohort=cohort,
        session_date=signal.session_date,
        direction=direction,
        range_start_bar=ref.start_index,
        range_end_bar=ref.end_index,
        range_known_bar=ref.end_index + 1,
        detection_bar=signal.detection_bar,
        state_known_bar=signal.detection_bar,
        confirmation_bar=signal.detection_bar,
        entry_candidate_bar=entry_index,
        label_available_bar=exit_index,
        return_start_bar=entry_index,
        detection_time_utc=iso(candles[signal.detection_bar].time),
        state_known_time_utc=iso(candles[signal.detection_bar].time),
        entry_time_utc=iso(entry.time),
        exit_time_utc=iso(exit_candle.time),
        entry_price=entry.open,
        exit_price=exit_candle.close,
        stop_reference_price=stop_reference,
        risk_pct=risk_pct,
        gross_return_pct=gross,
        net_return_pct=net,
        r_return=r_return,
        return_5bar_pct=gross,
        return_8bar_pct=return_8,
        return_10bar_pct=return_10,
        mfe_before_entry=mfe_before,
        mfe_after_entry=mfe_after,
        mae_after_entry=mae_after,
        total_mfe=mfe_before + mfe_after,
        mfe_consumed_pct=consumed,
        entry_to_mfe_bars=best_offset,
        asia_high=ref.high,
        asia_low=ref.low,
        asia_range_pct=ref.range_pct,
        asia_range_atr=ref.range_atr,
        atr14=signal.atr14,
        breakout_buffer_price=signal.metadata.get("breakout_buffer_price", config.breakout_buffer_atr * signal.atr14),
        metadata=merged_metadata,
    )


def build_main_signals(
    candles: list[Candle],
    config: DiagnosticConfig,
    ranges: dict[str, RangeReference],
    valid_days: dict[str, list[Candle]],
) -> list[BreakoutSignal]:
    signals: list[BreakoutSignal] = []
    for session_date, ref in ranges.items():
        london = window_candles(valid_days[session_date], config.london_start, config.london_end)
        if len(london) != config.expected_london_bars:
            continue
        signal = detect_first_breakout(candles, ref, london, config)
        if signal:
            signals.append(signal)
    return signals


def build_outside_london_signals(
    candles: list[Candle],
    config: DiagnosticConfig,
    ranges: dict[str, RangeReference],
    valid_days: dict[str, list[Candle]],
) -> list[BreakoutSignal]:
    signals: list[BreakoutSignal] = []
    for session_date, ref in ranges.items():
        ny_window = window_candles(valid_days[session_date], config.ny_start, config.ny_end)
        signal = detect_first_breakout(candles, ref, ny_window, config)
        if signal:
            signals.append(
                BreakoutSignal(
                    cohort="control_same_breakout_outside_london_ny",
                    session_date=signal.session_date,
                    direction=signal.direction,
                    range_reference=signal.range_reference,
                    detection_bar=signal.detection_bar,
                    atr14=signal.atr14,
                    metadata={**signal.metadata, "control": "ny_overlap_detection"},
                )
            )
    return signals


def build_compression_without_breakout_signals(
    candles: list[Candle],
    config: DiagnosticConfig,
    ranges: dict[str, RangeReference],
    valid_days: dict[str, list[Candle]],
    main_signal_dates: set[str],
) -> list[BreakoutSignal]:
    signals: list[BreakoutSignal] = []
    for session_date, ref in ranges.items():
        if session_date in main_signal_dates or ref.range_width_bucket != "bottom_half":
            continue
        london = window_candles(valid_days[session_date], config.london_start, config.london_end)
        if len(london) != config.expected_london_bars:
            continue
        atr = compute_atr(candles, london[-1].index, config.atr_period)
        if atr <= 0:
            continue
        direction = "LONG" if london[-1].close >= london[0].open else "SHORT"
        signals.append(
            BreakoutSignal(
                cohort="control_compression_without_breakout",
                session_date=session_date,
                direction=direction,
                range_reference=ref,
                detection_bar=london[-1].index,
                atr14=atr,
                metadata={
                    "control": "compression_without_breakout",
                    "direction_rule": "07_00_to_08_45_london_net_move_known_at_08_45_close",
                    "breakout_buffer_price": config.breakout_buffer_atr * atr,
                },
            )
        )
    return signals


def build_previous_day_range_signals(
    candles: list[Candle],
    config: DiagnosticConfig,
    previous_ranges: dict[str, RangeReference],
    valid_days: dict[str, list[Candle]],
) -> list[BreakoutSignal]:
    signals: list[BreakoutSignal] = []
    for session_date, ref in previous_ranges.items():
        if session_date not in valid_days:
            continue
        london = window_candles(valid_days[session_date], config.london_start, config.london_end)
        if len(london) != config.expected_london_bars:
            continue
        signal = detect_first_breakout(candles, ref, london, config)
        if signal:
            signals.append(
                BreakoutSignal(
                    cohort="control_previous_day_range_breakout",
                    session_date=session_date,
                    direction=signal.direction,
                    range_reference=signal.range_reference,
                    detection_bar=signal.detection_bar,
                    atr14=signal.atr14,
                    metadata={**signal.metadata, "control": "previous_day_range"},
                )
            )
    return signals


def build_cohorts(candles: list[Candle], config: DiagnosticConfig) -> tuple[dict[str, list[CohortEvent]], dict[str, Any]]:
    ranges, valid_days, range_meta = build_asia_ranges(candles, config)
    width_threshold = range_meta["asia_range_width_median"]
    previous_ranges = previous_trading_day_ranges(candles, config, width_threshold)
    main_signals = build_main_signals(candles, config, ranges, valid_days)
    main_events = [
        event
        for signal in main_signals
        if (event := build_event(PRIMARY_COHORT, candles, signal, config, entry_delay_bars=1)) is not None
    ]
    cohorts: dict[str, list[CohortEvent]] = {PRIMARY_COHORT: main_events}

    random_events: list[CohortEvent] = []
    for source_event, signal in zip(main_events, main_signals):
        shifted_detection = signal.detection_bar + config.random_offset_bars
        if shifted_detection >= len(candles):
            continue
        shifted_signal = BreakoutSignal(
            cohort="control_random_session_timing_137",
            session_date=source_event.session_date,
            direction=source_event.direction,
            range_reference=signal.range_reference,
            detection_bar=shifted_detection,
            atr14=signal.atr14,
            metadata={"control": "random_offset_137", "source_detection_bar": signal.detection_bar},
        )
        event = build_event(
            "control_random_session_timing_137",
            candles,
            shifted_signal,
            config,
            entry_delay_bars=1,
            fixed_risk_pct=source_event.risk_pct,
        )
        if event:
            random_events.append(event)
    cohorts["control_random_session_timing_137"] = random_events

    cohorts["control_opposite_direction"] = [
        event
        for signal in main_signals
        if (
            event := build_event(
                "control_opposite_direction",
                candles,
                signal,
                config,
                entry_delay_bars=1,
                direction=opposite_direction(signal.direction),
                metadata={"control": "opposite_direction"},
            )
        )
        is not None
    ]

    cohorts["control_same_breakout_outside_london_ny"] = [
        event
        for signal in build_outside_london_signals(candles, config, ranges, valid_days)
        if (event := build_event("control_same_breakout_outside_london_ny", candles, signal, config, entry_delay_bars=1)) is not None
    ]

    cohorts["control_breakout_without_prior_asia_compression"] = [
        event
        for event in main_events
        if event.metadata.get("range_width_bucket") == "top_half" or event.asia_range_pct >= width_threshold
    ]

    main_dates = {signal.session_date for signal in main_signals}
    cohorts["control_compression_without_breakout"] = [
        event
        for signal in build_compression_without_breakout_signals(candles, config, ranges, valid_days, main_dates)
        if (event := build_event("control_compression_without_breakout", candles, signal, config, entry_delay_bars=1)) is not None
    ]

    cohorts["control_shifted_entry_plus2"] = [
        event
        for signal in main_signals
        if (event := build_event("control_shifted_entry_plus2", candles, signal, config, entry_delay_bars=3)) is not None
    ]

    weekday_events: list[CohortEvent] = []
    for source_event, signal in zip(main_events, main_signals):
        shifted_detection = signal.detection_bar + config.weekday_shuffle_offset_bars
        if shifted_detection >= len(candles):
            continue
        shifted_signal = BreakoutSignal(
            cohort="control_weekday_shuffled",
            session_date=source_event.session_date,
            direction=source_event.direction,
            range_reference=signal.range_reference,
            detection_bar=shifted_detection,
            atr14=signal.atr14,
            metadata={"control": "weekday_rotation_plus_96_bars", "source_detection_bar": signal.detection_bar},
        )
        event = build_event(
            "control_weekday_shuffled",
            candles,
            shifted_signal,
            config,
            entry_delay_bars=1,
            fixed_risk_pct=source_event.risk_pct,
        )
        if event:
            weekday_events.append(event)
    cohorts["control_weekday_shuffled"] = weekday_events

    cohorts["control_previous_day_range_breakout"] = [
        event
        for signal in build_previous_day_range_signals(candles, config, previous_ranges, valid_days)
        if (event := build_event("control_previous_day_range_breakout", candles, signal, config, entry_delay_bars=1)) is not None
    ]

    for name in CONTROL_COHORTS:
        cohorts.setdefault(name, [])

    return cohorts, {
        **range_meta,
        "valid_session_days": len(valid_days),
        "main_signal_days": len(main_signals),
        "control_5_entry_rule": "09:00 open after 08:45 close direction from London net move; no future bars used",
    }


def profit_factor(values: list[float]) -> float | None:
    gains = sum(value for value in values if value > 0)
    losses = abs(sum(value for value in values if value < 0))
    if losses == 0:
        return None
    return gains / losses


def cohort_metrics(events: list[CohortEvent]) -> dict[str, Any]:
    if not events:
        return {
            "count": 0,
            "er": None,
            "median_r": None,
            "profit_factor": None,
            "win_rate": None,
            "median_net_return_pct": None,
            "median_gross_return_pct": None,
            "median_mfe_consumed_pct": None,
            "median_mfe_after_entry": None,
            "median_mae_after_entry": None,
            "median_risk_pct": None,
            "decision_grade": False,
        }
    r_values = [event.r_return for event in events]
    net = [event.net_return_pct for event in events]
    return {
        "count": len(events),
        "er": mean(r_values),
        "median_r": median(r_values),
        "profit_factor": profit_factor(r_values),
        "win_rate": mean([value > 0 for value in net]),
        "median_net_return_pct": median(net),
        "median_gross_return_pct": median([event.gross_return_pct for event in events]),
        "median_mfe_consumed_pct": median([event.mfe_consumed_pct for event in events]),
        "median_mfe_after_entry": median([event.mfe_after_entry for event in events]),
        "median_mae_after_entry": median([event.mae_after_entry for event in events]),
        "median_risk_pct": median([event.risk_pct for event in events]),
        "decision_grade": len(events) >= MIN_DECISION_CONTROL_EVENTS,
    }


def fold_for_timestamp(value: datetime) -> str:
    for name, start, end in FOLD_WINDOWS:
        if start <= value < end:
            return name
    return "outside"


def fold_metrics(events: list[CohortEvent]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for fold_name, _, _ in FOLD_WINDOWS:
        subset = [event for event in events if fold_for_timestamp(parse_ts(event.entry_time_utc)) == fold_name]
        metrics = cohort_metrics(subset)
        positive = bool(
            metrics["count"] >= 25
            and metrics["median_net_return_pct"] is not None
            and metrics["median_net_return_pct"] > 0
            and metrics["er"] is not None
            and metrics["er"] > 1.0
        )
        rows.append({"fold": fold_name, **metrics, "positive": positive})
    return rows


def direction_metrics(events: list[CohortEvent]) -> dict[str, dict[str, Any]]:
    return {
        direction: cohort_metrics([event for event in events if event.direction == direction])
        for direction in ("LONG", "SHORT")
    }


def cost_adjusted_metrics(events: list[CohortEvent], cost_pct: float) -> dict[str, Any]:
    adjusted: list[CohortEvent] = []
    for event in events:
        net = event.gross_return_pct - cost_pct
        adjusted.append(
            CohortEvent(
                **{
                    **asdict(event),
                    "net_return_pct": net,
                    "r_return": net / event.risk_pct if event.risk_pct > 0 else 0.0,
                    "metadata": {**event.metadata, "round_trip_cost_pct": cost_pct},
                }
            )
        )
    return cohort_metrics(adjusted)


def horizon_metrics(events: list[CohortEvent], horizon: int, cost_pct: float) -> dict[str, Any]:
    synthetic: list[CohortEvent] = []
    attr = {5: "return_5bar_pct", 8: "return_8bar_pct", 10: "return_10bar_pct"}[horizon]
    for event in events:
        gross = getattr(event, attr)
        if gross is None:
            continue
        net = gross - cost_pct
        synthetic.append(
            CohortEvent(
                **{
                    **asdict(event),
                    "gross_return_pct": gross,
                    "net_return_pct": net,
                    "r_return": net / event.risk_pct if event.risk_pct > 0 else 0.0,
                    "metadata": {**event.metadata, "horizon_bars": horizon},
                }
            )
        )
    return cohort_metrics(synthetic)


def evaluate_gates(cohort_results: dict[str, dict[str, Any]], folds: list[dict[str, Any]]) -> dict[str, Any]:
    main = cohort_results[PRIMARY_COHORT]
    main_er = main["er"]
    main_pf = main["profit_factor"]
    main_count = int(main["count"] or 0)
    main_median_net = main["median_net_return_pct"]
    main_mfe = main["median_mfe_consumed_pct"]
    positive_folds = sum(1 for fold in folds if fold["positive"])

    controls_better: list[str] = []
    for name, metrics in cohort_results.items():
        if name == PRIMARY_COHORT:
            continue
        control_er = metrics.get("er")
        if (
            metrics.get("count", 0) >= MIN_DECISION_CONTROL_EVENTS
            and control_er is not None
            and main_er is not None
            and control_er > main_er
        ):
            controls_better.append(name)

    stop_reasons: list[str] = []
    if main_count < 100:
        stop_reasons.append(f"sample_size_lt_100:{main_count}")
    if main_count < 200:
        stop_reasons.append(f"primary_event_count_collapsed_below_200:{main_count}")
    if main_median_net is None or main_median_net <= 0:
        stop_reasons.append("median_net_return_lte_0_at_0_015pct_cost")
    if main_er is None or main_er < 1.0:
        stop_reasons.append("er_lt_1_0")
    if main_pf is None or main_pf < 1.2:
        stop_reasons.append("profit_factor_lt_1_2")
    if main_mfe is not None and main_mfe > 0.70:
        stop_reasons.append("median_mfe_consumed_gt_70pct")
    if controls_better:
        stop_reasons.append("control_cohort_outperforms_main:" + ",".join(controls_better))
    if positive_folds < 2:
        stop_reasons.append(f"walk_forward_fewer_than_2_positive_folds:{positive_folds}")

    explore_passed = (
        main_count >= 200
        and main_median_net is not None
        and main_median_net > 0
        and main_er is not None
        and main_er > 1.3
        and main_pf is not None
        and main_pf > 1.5
        and main_mfe is not None
        and main_mfe < 0.60
        and not controls_better
        and positive_folds >= 3
    )
    if stop_reasons:
        recommendation = "STOP"
    elif explore_passed:
        recommendation = "EXPLORE"
    else:
        recommendation = "INCONCLUSIVE"
    return {
        "recommendation": recommendation,
        "stop_reasons": stop_reasons,
        "explore_reasons": ["all_explore_gates_passed"] if explore_passed else [],
        "positive_folds": positive_folds,
        "controls_better": controls_better,
    }


def serialize_sample(events: list[CohortEvent], limit: int) -> list[dict[str, Any]]:
    return [asdict(event) for event in events[:limit]]


def run_diagnostic(config: DiagnosticConfig, data_path: Path = DEFAULT_DATA_PATH) -> dict[str, Any]:
    candles = load_candles(data_path)
    dq = data_quality(candles)
    cohorts, session_meta = build_cohorts(candles, config)
    cohort_results = {name: cohort_metrics(events) for name, events in cohorts.items()}
    folds = fold_metrics(cohorts[PRIMARY_COHORT])
    gates = evaluate_gates(cohort_results, folds)
    main_events = cohorts[PRIMARY_COHORT]
    payload = {
        "diagnostic": "OANDA_ASIA_RANGE_LONDON_BREAKOUT_FEASIBILITY_V1",
        "created_at_utc": iso(datetime.now(timezone.utc)),
        "config": asdict(config),
        "data_source": {"source": str(data_path), "fetched": False},
        "data_quality": dq,
        "session_meta": session_meta,
        "trial_00095_reference": TRIAL_00095_REFERENCE,
        "cohort_metrics": cohort_results,
        "direction_metrics": direction_metrics(main_events),
        "fold_metrics": folds,
        "cost_sensitivity": {
            f"{cost:.5f}": cost_adjusted_metrics(main_events, cost)
            for cost in config.sensitivity_costs_pct
        },
        "horizon_sensitivity": {
            f"{horizon}_bars": horizon_metrics(main_events, horizon, config.primary_cost_pct)
            for horizon in (config.primary_horizon_bars, config.secondary_horizon_bars, config.tertiary_horizon_bars)
        },
        "gate_evaluation": gates,
        "event_samples": {
            name: serialize_sample(events, config.max_serialized_events_per_cohort)
            for name, events in cohorts.items()
        },
    }
    return payload


def artifact_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pct(value: Any, digits: int = 2) -> str:
    if value is None:
        return "N/A"
    return f"{float(value) * 100:.{digits}f}%"


def fmt(value: Any, digits: int = 4) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _metrics_row(name: str, metrics: dict[str, Any]) -> str:
    return (
        f"| `{name}` | {metrics['count']} | {fmt(metrics['er'])} | {fmt(metrics['profit_factor'])} | "
        f"{pct(metrics['win_rate'])} | {pct(metrics['median_net_return_pct'], 4)} | "
        f"{pct(metrics['median_mfe_consumed_pct'])} |"
    )


def write_report(path: Path, payload: dict[str, Any], json_path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    gates = payload["gate_evaluation"]
    dq = payload["data_quality"]
    main = payload["cohort_metrics"][PRIMARY_COHORT]
    config = payload["config"]
    lines: list[str] = [
        "# OANDA_ASIA_RANGE_LONDON_BREAKOUT_FEASIBILITY_V1",
        "",
        f"**Date:** {payload['created_at_utc']}",
        "**Type:** Research-only OANDA session edge diagnostic",
        f"**Recommendation:** {gates['recommendation']}",
        "",
        "## 1. Executive Summary",
        "",
        "This diagnostic tests one OANDA-native session mechanism: `EUR_USD M15` Asia range to London breakout.",
        "It does not rescue OANDA sweep/reclaim, does not use SMC logic, does not run Optuna, and does not modify production code.",
        "",
        f"- Main events: `{main['count']}`",
        f"- Main ER: `{fmt(main['er'])}`",
        f"- Main PF: `{fmt(main['profit_factor'])}`",
        f"- Main win rate: `{pct(main['win_rate'])}`",
        f"- Main median net return at 0.015% cost: `{pct(main['median_net_return_pct'], 4)}`",
        f"- Main median MFE consumed before entry: `{pct(main['median_mfe_consumed_pct'])}`",
        f"- Positive folds: `{gates['positive_folds']} / 4`",
        f"- STOP reasons: `{', '.join(gates['stop_reasons']) if gates['stop_reasons'] else 'None'}`",
        "",
        "## 2. OANDA Sweep/Reclaim Boundary Statement",
        "",
        "- `XAU_USD H1` sweep/reclaim remains `STOP` due sample collapse.",
        "- `EUR_USD M15` sweep/reclaim remains `STOP` due negative expectancy and control outperformance.",
        "- This diagnostic is session-driven forex structure only: Asia range -> London breakout.",
        "",
        "## 3. Data Quality",
        "",
        "| Field | Value |",
        "| --- | ---: |",
        f"| Candle count | {dq['count']} |",
        f"| First candle | {dq['first']} |",
        f"| Last candle | {dq['last']} |",
        f"| OHLC bad rows | {dq['ohlc_bad_rows']} |",
        f"| Duplicate timestamps | {dq['duplicates']} |",
        f"| Gaps > 24h | {dq['gaps_gt_24h']} |",
        f"| Gaps > 72h | {dq['gaps_gt_72h']} |",
        f"| Max gap hours | {dq['max_gap_hours']} |",
        f"| Data gate | {dq['data_gate']} |",
        "",
        "## 4. Frozen Parameter Table",
        "",
        "| Parameter | Value |",
        "| --- | --- |",
        f"| Instrument | `{config['instrument']}` |",
        f"| Timeframe | `{config['granularity']}` |",
        f"| Asia range | `{config['asia_start']}-{config['asia_end']} UTC` |",
        f"| London breakout | `{config['london_start']}-{config['london_end']} UTC` |",
        f"| Breakout buffer | `{config['breakout_buffer_atr']} * ATR14` |",
        f"| Entry | `i+1 open` |",
        f"| Primary horizon | `{config['primary_horizon_bars']}` bars |",
        f"| Secondary horizon | `{config['secondary_horizon_bars']}` bars |",
        f"| Tertiary horizon | `{config['tertiary_horizon_bars']}` bars |",
        f"| Primary cost | `{pct(config['primary_cost_pct'], 4)}` |",
        f"| Compression filter | `None` |",
        "",
        "## 5. Timing Model Verification",
        "",
        "- `range_known_bar` is the first bar after the completed Asia range.",
        "- `state_known_bar = detection_bar` at London breakout bar close.",
        "- `entry_candidate_bar = detection_bar + 1`.",
        "- `return_start_bar = entry_candidate_bar`.",
        "- Detection-bar movement is used only for MFE-before-entry audit metrics.",
        "",
        "## 6. Main Cohort Metrics",
        "",
        "| Cohort | Count | ER | PF | Win Rate | Median Net | Median MFE Consumed |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        _metrics_row(PRIMARY_COHORT, main),
        "",
        "## 7. Control Cohort Metrics",
        "",
        "| Cohort | Count | ER | PF | Win Rate | Median Net | Median MFE Consumed |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name in CONTROL_COHORTS:
        lines.append(_metrics_row(name, payload["cohort_metrics"][name]))
    lines.extend([
        "",
        "## 8. Direction Split",
        "",
        "| Direction | Count | ER | PF | Win Rate | Median Net | Median MFE Consumed |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ])
    for direction, metrics in payload["direction_metrics"].items():
        lines.append(_metrics_row(direction, metrics))
    lines.extend([
        "",
        "## 9. Walk-Forward Folds",
        "",
        "| Fold | Count | ER | PF | Median Net | Median MFE Consumed | Positive |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ])
    for row in payload["fold_metrics"]:
        lines.append(
            f"| `{row['fold']}` | {row['count']} | {fmt(row['er'])} | {fmt(row['profit_factor'])} | "
            f"{pct(row['median_net_return_pct'], 4)} | {pct(row['median_mfe_consumed_pct'])} | {row['positive']} |"
        )
    lines.extend([
        "",
        "## 10. Cost Sensitivity",
        "",
        "| Round-trip Cost | Count | ER | PF | Win Rate | Median Net |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ])
    for cost, metrics in payload["cost_sensitivity"].items():
        lines.append(
            f"| `{cost}` | {metrics['count']} | {fmt(metrics['er'])} | {fmt(metrics['profit_factor'])} | "
            f"{pct(metrics['win_rate'])} | {pct(metrics['median_net_return_pct'], 4)} |"
        )
    lines.extend([
        "",
        "## 11. Horizon Sensitivity",
        "",
        "| Horizon | Count | ER | PF | Win Rate | Median Net |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ])
    for horizon, metrics in payload["horizon_sensitivity"].items():
        lines.append(
            f"| `{horizon}` | {metrics['count']} | {fmt(metrics['er'])} | {fmt(metrics['profit_factor'])} | "
            f"{pct(metrics['win_rate'])} | {pct(metrics['median_net_return_pct'], 4)} |"
        )
    lines.extend([
        "",
        "## 12. MFE Accessibility",
        "",
        f"- Median MFE consumed before entry: `{pct(main['median_mfe_consumed_pct'])}`.",
        f"- Median post-entry MFE: `{fmt(main['median_mfe_after_entry'], 6)}`.",
        f"- Median post-entry MAE: `{fmt(main['median_mae_after_entry'], 6)}`.",
        "- STOP gate: median consumed > 70%. EXPLORE target: < 60%.",
        "",
        "## 13. BTC Baseline Comparison",
        "",
        "| Metric | BTC trial-00095 | OANDA Asia Range |",
        "| --- | ---: | ---: |",
        f"| ER | {TRIAL_00095_REFERENCE['er']} | {fmt(main['er'])} |",
        f"| PF | {TRIAL_00095_REFERENCE['profit_factor']} | {fmt(main['profit_factor'])} |",
        f"| Win rate | {pct(TRIAL_00095_REFERENCE['win_rate'])} | {pct(main['win_rate'])} |",
        f"| Trades/events | {TRIAL_00095_REFERENCE['trades']} | {main['count']} |",
        "",
        "## 14. Invalidation Gate Evaluation",
        "",
        f"- Recommendation: `{gates['recommendation']}`",
        f"- STOP reasons: `{gates['stop_reasons']}`",
        f"- EXPLORE reasons: `{gates['explore_reasons']}`",
        f"- Controls better than main: `{gates['controls_better']}`",
        f"- Positive folds: `{gates['positive_folds']} / 4`",
        f"- Decision-grade control threshold: `{MIN_DECISION_CONTROL_EVENTS}` events",
        "",
        "## 15. Session Construction Notes",
        "",
        f"- Complete Asia sessions: `{payload['session_meta']['complete_asia_sessions']}`.",
        f"- Skipped incomplete Asia sessions: `{payload['session_meta']['skipped_incomplete_asia_sessions']}`.",
        f"- Valid session days: `{payload['session_meta']['valid_session_days']}`.",
        f"- Main signal days: `{payload['session_meta']['main_signal_days']}`.",
        f"- Control 5 entry rule: `{payload['session_meta']['control_5_entry_rule']}`.",
        "",
        "## 16. Artifact",
        "",
        f"- JSON path: `{json_path.as_posix()}`",
        f"- JSON SHA256: `{artifact_sha256(json_path) if json_path.exists() else 'pending'}`",
        "",
        "## 17. Recommendation",
        "",
        f"### Verdict: {gates['recommendation']}",
        "",
    ])
    if gates["recommendation"] == "STOP":
        lines.extend([
            f"**Reason:** {'; '.join(gates['stop_reasons'])}",
            "",
            "**Next:** Do not port this OANDA session candidate to runtime. Consider the separately planned `NY_REVERSAL_AFTER_LONDON_EXTENSION` path or return to multi-asset crypto.",
        ])
    elif gates["recommendation"] == "EXPLORE":
        lines.extend([
            "**Reason:** Main cohort passed the pre-declared EXPLORE gates after realistic entry, primary costs, controls, MFE accessibility, and walk-forward validation.",
            "",
            "**Next:** Plan V2 optimization or OANDA paper-trading architecture separately. This diagnostic does not authorize production changes.",
        ])
    else:
        lines.extend([
            "**Reason:** Results did not trigger hard STOP but did not meet all EXPLORE gates.",
            "",
            "**Next:** Decide whether to test `NY_REVERSAL_AFTER_LONDON_EXTENSION` or return to multi-asset crypto.",
        ])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-path", type=Path, default=DEFAULT_DATA_PATH)
    parser.add_argument("--report-path", type=Path, default=DEFAULT_REPORT_PATH)
    parser.add_argument("--json-path", type=Path, default=DEFAULT_JSON_PATH)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    config = DiagnosticConfig()
    payload = run_diagnostic(config, args.data_path)
    write_json(args.json_path, payload)
    write_report(args.report_path, payload, args.json_path)
    print(json.dumps({"recommendation": payload["gate_evaluation"]["recommendation"], "report": str(args.report_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
