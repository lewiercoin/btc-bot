"""Research-only OANDA NY reversal after London extension diagnostic.

Implements OANDA_NY_REVERSAL_AFTER_LONDON_EXTENSION_FEASIBILITY_V1:

    London extension is measured from completed 07:00-12:00 UTC M15 bars.
    Extension state is known at 12:00 UTC.
    NY reversal is detected on the first 13:00-16:00 UTC bar closing opposite
    to the London extension direction.
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
DEFAULT_REPORT_PATH = PROJECT_ROOT / "research_lab" / "reports" / "oanda_ny_reversal_after_london_extension_feasibility_v1.md"
DEFAULT_JSON_PATH = PROJECT_ROOT / "research_lab" / "reports" / "oanda_ny_reversal_after_london_extension_feasibility_v1.json"

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

PRIMARY_COHORT = "main_ny_reversal_after_london_extension"
CONTROL_COHORTS = (
    "control_random_session_timing_97",
    "control_opposite_direction_continuation",
    "control_same_reversal_outside_ny_tokyo",
    "control_reversal_without_extension",
    "control_extension_without_reversal_continuation",
    "control_shifted_entry_plus2",
    "control_weekday_shuffled",
    "control_previous_day_london_extension",
)
MIN_DECISION_CONTROL_EVENTS = 25


@dataclass(frozen=True, slots=True)
class DiagnosticConfig:
    instrument: str = "EUR_USD"
    granularity: str = "M15"
    atr_period: int = 14
    london_start: str = "07:00"
    london_end: str = "12:00"
    ny_start: str = "13:00"
    ny_end: str = "16:00"
    tokyo_start: str = "21:00"
    tokyo_end: str = "24:00"
    extension_atr_threshold: float = 1.0
    risk_buffer_atr: float = 0.10
    primary_horizon_bars: int = 5
    secondary_horizon_bars: int = 8
    tertiary_horizon_bars: int = 10
    primary_cost_pct: float = 0.00015
    sensitivity_costs_pct: tuple[float, ...] = (0.00010, 0.00015, 0.00020)
    random_offset_bars: int = 97
    weekday_shuffle_offset_bars: int = 96
    expected_london_bars: int = 20
    expected_ny_bars: int = 12
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
class LondonExtension:
    session_date: str
    london_start_bar: int
    london_end_bar: int
    london_known_bar: int
    open: float
    close: float
    high: float
    low: float
    net_move: float
    abs_net_move: float
    atr14: float
    direction: str
    extension_multiple: float
    extended: bool
    source: str


@dataclass(frozen=True, slots=True)
class ReversalSignal:
    cohort: str
    session_date: str
    entry_direction: str
    london_direction: str
    extension: LondonExtension
    detection_bar: int
    metadata: dict[str, Any]


@dataclass(frozen=True, slots=True)
class CohortEvent:
    cohort: str
    session_date: str
    direction: str
    london_direction: str
    london_start_bar: int
    london_end_bar: int
    london_known_bar: int
    ny_overlap_start_bar: int | None
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
    london_high: float
    london_low: float
    london_net_move: float
    london_extension_multiple: float
    atr14: float
    metadata: dict[str, Any]


def parse_ts(value: Any) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def parse_hhmm(value: str) -> time:
    if value == "24:00":
        return time(23, 59, 59, 999999, tzinfo=timezone.utc)
    hour, minute = value.split(":")
    return time(int(hour), int(minute), tzinfo=timezone.utc)


def in_window(ts: datetime, start: str, end: str) -> bool:
    return parse_hhmm(start) <= ts.timetz() < parse_hhmm(end)


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
    previous: datetime | None = None
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
        if previous is not None:
            gap_hours = (candle.time - previous).total_seconds() / 3600.0
            max_gap_hours = max(max_gap_hours, gap_hours)
            if gap_hours > 24:
                gaps_gt_24h += 1
            if gap_hours > 72:
                gaps_gt_72h += 1
        previous = candle.time
    gate = "PASS" if len(candles) >= 30000 and bad_ohlc == 0 and duplicates == 0 and gaps_gt_72h == 0 else "BLOCKED"
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
    ranges: list[float] = []
    for idx in range(start, end_index + 1):
        candle = candles[idx]
        prev_close = candles[idx - 1].close
        ranges.append(
            max(
                candle.high - candle.low,
                abs(candle.high - prev_close),
                abs(candle.low - prev_close),
            )
        )
    return mean(ranges) if ranges else 0.0


def group_by_date(candles: list[Candle]) -> dict[str, list[Candle]]:
    grouped: dict[str, list[Candle]] = defaultdict(list)
    for candle in candles:
        grouped[candle.time.date().isoformat()].append(candle)
    return dict(grouped)


def window_candles(day: list[Candle], start: str, end: str) -> list[Candle]:
    return [candle for candle in day if in_window(candle.time, start, end)]


def build_london_extensions(
    candles: list[Candle],
    config: DiagnosticConfig,
    include_non_extended: bool = False,
) -> tuple[dict[str, LondonExtension], dict[str, list[Candle]], dict[str, Any]]:
    grouped = group_by_date(candles)
    extensions: dict[str, LondonExtension] = {}
    valid_days: dict[str, list[Candle]] = {}
    skipped_incomplete = 0
    for session_date, day in grouped.items():
        london = window_candles(day, config.london_start, config.london_end)
        if len(london) != config.expected_london_bars:
            skipped_incomplete += 1
            continue
        first = london[0]
        last = london[-1]
        atr = compute_atr(candles, first.index - 1, config.atr_period)
        if atr <= 0:
            continue
        net = last.close - first.open
        abs_net = abs(net)
        direction = "UP" if net > 0 else "DOWN"
        extended = abs_net > config.extension_atr_threshold * atr
        if not extended and not include_non_extended:
            continue
        extension = LondonExtension(
            session_date=session_date,
            london_start_bar=first.index,
            london_end_bar=last.index,
            london_known_bar=last.index + 1,
            open=first.open,
            close=last.close,
            high=max(candle.high for candle in london),
            low=min(candle.low for candle in london),
            net_move=net,
            abs_net_move=abs_net,
            atr14=atr,
            direction=direction,
            extension_multiple=abs_net / atr,
            extended=extended,
            source="same_day_london",
        )
        extensions[session_date] = extension
        valid_days[session_date] = day
    return extensions, valid_days, {
        "complete_london_sessions": len(extensions),
        "skipped_incomplete_london_sessions": skipped_incomplete,
    }


def previous_day_extensions(
    candles: list[Candle],
    config: DiagnosticConfig,
) -> dict[str, LondonExtension]:
    all_extensions, _, _ = build_london_extensions(candles, config, include_non_extended=False)
    refs: dict[str, LondonExtension] = {}
    previous: LondonExtension | None = None
    for session_date in sorted(group_by_date(candles)):
        if previous is not None:
            refs[session_date] = LondonExtension(
                **{
                    **asdict(previous),
                    "session_date": session_date,
                    "source": "previous_trading_day_london",
                }
            )
        if session_date in all_extensions:
            previous = all_extensions[session_date]
    return refs


def reversal_direction(london_direction: str) -> str:
    return "SHORT" if london_direction == "UP" else "LONG"


def continuation_direction(london_direction: str) -> str:
    return "LONG" if london_direction == "UP" else "SHORT"


def candle_closes_opposite(candle: Candle, london_direction: str) -> bool:
    if london_direction == "UP":
        return candle.close < candle.open
    return candle.close > candle.open


def candle_closes_with(candle: Candle, london_direction: str) -> bool:
    if london_direction == "UP":
        return candle.close > candle.open
    return candle.close < candle.open


def first_confirmation(
    window: list[Candle],
    extension: LondonExtension,
    follow_london: bool,
) -> tuple[Candle, str] | None:
    for candle in window:
        if follow_london:
            if candle_closes_with(candle, extension.direction):
                return candle, continuation_direction(extension.direction)
        elif candle_closes_opposite(candle, extension.direction):
            return candle, reversal_direction(extension.direction)
    return None


def build_signals(
    candles: list[Candle],
    config: DiagnosticConfig,
    extensions: dict[str, LondonExtension],
    valid_days: dict[str, list[Candle]],
    cohort: str,
    start: str,
    end: str,
    follow_london: bool = False,
) -> list[ReversalSignal]:
    signals: list[ReversalSignal] = []
    for session_date, extension in extensions.items():
        if session_date not in valid_days:
            continue
        window = window_candles(valid_days[session_date], start, end)
        confirmation = first_confirmation(window, extension, follow_london)
        if confirmation is None:
            continue
        detection, direction = confirmation
        signals.append(
            ReversalSignal(
                cohort=cohort,
                session_date=session_date,
                entry_direction=direction,
                london_direction=extension.direction,
                extension=extension,
                detection_bar=detection.index,
                metadata={
                    "follow_london": follow_london,
                    "confirmation_rule": "first_same_direction_close" if follow_london else "first_opposite_close",
                    "window_start_bar": window[0].index if window else None,
                },
            )
        )
    return signals


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
    before = candles[detection_index:entry_index]
    after = candles[entry_index:exit_index + 1]
    if direction == "LONG":
        mfe_before = max((candle.high - detection.close for candle in before), default=0.0)
        mfe_after = max((candle.high - entry_price for candle in after), default=0.0)
        mae_after = max((entry_price - candle.low for candle in after), default=0.0)
        best_offset = max(((candle.high, offset) for offset, candle in enumerate(after)), default=(0.0, None))[1]
    else:
        mfe_before = max((detection.close - candle.low for candle in before), default=0.0)
        mfe_after = max((entry_price - candle.low for candle in after), default=0.0)
        mae_after = max((candle.high - entry_price for candle in after), default=0.0)
        best_offset = max(((-candle.low, offset) for offset, candle in enumerate(after)), default=(0.0, None))[1]
    mfe_before = max(0.0, mfe_before)
    mfe_after = max(0.0, mfe_after)
    mae_after = max(0.0, mae_after)
    total = mfe_before + mfe_after
    return mfe_before, mfe_after, mae_after, mfe_before / total if total > 0 else 0.0, best_offset


def build_event(
    cohort: str,
    candles: list[Candle],
    signal: ReversalSignal,
    config: DiagnosticConfig,
    entry_delay_bars: int = 1,
    direction: str | None = None,
    cost_pct: float | None = None,
    fixed_risk_pct: float | None = None,
    metadata: dict[str, Any] | None = None,
) -> CohortEvent | None:
    direction = direction or signal.entry_direction
    cost = config.primary_cost_pct if cost_pct is None else cost_pct
    entry_index = signal.detection_bar + entry_delay_bars
    exit_index = entry_index + config.primary_horizon_bars
    if entry_index >= len(candles) or exit_index >= len(candles):
        return None
    extension = signal.extension
    entry = candles[entry_index]
    exit_candle = candles[exit_index]
    buffer_price = config.risk_buffer_atr * extension.atr14
    # Natural invalidation for fading an extension: if fading down-extension
    # with LONG, invalidation is below London low; if fading up-extension with
    # SHORT, invalidation is above London high.
    if direction == "LONG":
        stop_reference = extension.low - buffer_price
        risk_pct = abs(entry.open - stop_reference) / entry.open if entry.open else 0.0
    else:
        stop_reference = extension.high + buffer_price
        risk_pct = abs(stop_reference - entry.open) / entry.open if entry.open else 0.0
    if fixed_risk_pct is not None:
        risk_pct = fixed_risk_pct
        stop_reference = entry.open * (1 - risk_pct) if direction == "LONG" else entry.open * (1 + risk_pct)
    if risk_pct <= 0:
        return None
    gross = _gross_return(entry.open, exit_candle.close, direction)
    net = gross - cost
    return_8 = None
    return_10 = None
    idx8 = entry_index + config.secondary_horizon_bars
    idx10 = entry_index + config.tertiary_horizon_bars
    if idx8 < len(candles):
        return_8 = _gross_return(entry.open, candles[idx8].close, direction)
    if idx10 < len(candles):
        return_10 = _gross_return(entry.open, candles[idx10].close, direction)
    mfe_before, mfe_after, mae_after, consumed, best_offset = _mfe_mae(
        candles,
        signal.detection_bar,
        entry_index,
        exit_index,
        entry.open,
        direction,
    )
    ny_start_bar = signal.metadata.get("window_start_bar")
    merged_metadata = dict(signal.metadata)
    if metadata:
        merged_metadata.update(metadata)
    merged_metadata["round_trip_cost_pct"] = cost
    return CohortEvent(
        cohort=cohort,
        session_date=signal.session_date,
        direction=direction,
        london_direction=signal.london_direction,
        london_start_bar=extension.london_start_bar,
        london_end_bar=extension.london_end_bar,
        london_known_bar=extension.london_known_bar,
        ny_overlap_start_bar=ny_start_bar,
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
        r_return=net / risk_pct,
        return_5bar_pct=gross,
        return_8bar_pct=return_8,
        return_10bar_pct=return_10,
        mfe_before_entry=mfe_before,
        mfe_after_entry=mfe_after,
        mae_after_entry=mae_after,
        total_mfe=mfe_before + mfe_after,
        mfe_consumed_pct=consumed,
        entry_to_mfe_bars=best_offset,
        london_high=extension.high,
        london_low=extension.low,
        london_net_move=extension.net_move,
        london_extension_multiple=extension.extension_multiple,
        atr14=extension.atr14,
        metadata=merged_metadata,
    )


def build_cohorts(candles: list[Candle], config: DiagnosticConfig) -> tuple[dict[str, list[CohortEvent]], dict[str, Any]]:
    extensions, valid_days, meta = build_london_extensions(candles, config, include_non_extended=False)
    all_london, all_valid_days, all_meta = build_london_extensions(candles, config, include_non_extended=True)
    main_signals = build_signals(candles, config, extensions, valid_days, PRIMARY_COHORT, config.ny_start, config.ny_end)
    main_events = [
        event
        for signal in main_signals
        if (event := build_event(PRIMARY_COHORT, candles, signal, config, entry_delay_bars=1)) is not None
    ]
    cohorts: dict[str, list[CohortEvent]] = {PRIMARY_COHORT: main_events}

    random_events: list[CohortEvent] = []
    for source_event, signal in zip(main_events, main_signals):
        shifted = signal.detection_bar + config.random_offset_bars
        if shifted >= len(candles):
            continue
        shifted_signal = ReversalSignal(
            cohort="control_random_session_timing_97",
            session_date=signal.session_date,
            entry_direction=source_event.direction,
            london_direction=signal.london_direction,
            extension=signal.extension,
            detection_bar=shifted,
            metadata={"control": "random_offset_97", "source_detection_bar": signal.detection_bar},
        )
        event = build_event(
            "control_random_session_timing_97",
            candles,
            shifted_signal,
            config,
            entry_delay_bars=1,
            fixed_risk_pct=source_event.risk_pct,
        )
        if event:
            random_events.append(event)
    cohorts["control_random_session_timing_97"] = random_events

    cohorts["control_opposite_direction_continuation"] = [
        event
        for signal in main_signals
        if (
            event := build_event(
                "control_opposite_direction_continuation",
                candles,
                signal,
                config,
                entry_delay_bars=1,
                direction=continuation_direction(signal.london_direction),
                metadata={"control": "opposite_direction_continuation"},
            )
        )
        is not None
    ]

    tokyo_signals = build_signals(
        candles,
        config,
        extensions,
        valid_days,
        "control_same_reversal_outside_ny_tokyo",
        config.tokyo_start,
        config.tokyo_end,
    )
    cohorts["control_same_reversal_outside_ny_tokyo"] = [
        event
        for signal in tokyo_signals
        if (event := build_event("control_same_reversal_outside_ny_tokyo", candles, signal, config, entry_delay_bars=1)) is not None
    ]

    no_extension_signals = build_signals(
        candles,
        config,
        all_london,
        all_valid_days,
        "control_reversal_without_extension",
        config.ny_start,
        config.ny_end,
    )
    cohorts["control_reversal_without_extension"] = [
        event
        for signal in no_extension_signals
        if (event := build_event("control_reversal_without_extension", candles, signal, config, entry_delay_bars=1)) is not None
    ]

    continuation_signals = build_signals(
        candles,
        config,
        extensions,
        valid_days,
        "control_extension_without_reversal_continuation",
        config.ny_start,
        config.ny_end,
        follow_london=True,
    )
    cohorts["control_extension_without_reversal_continuation"] = [
        event
        for signal in continuation_signals
        if (event := build_event("control_extension_without_reversal_continuation", candles, signal, config, entry_delay_bars=1)) is not None
    ]

    cohorts["control_shifted_entry_plus2"] = [
        event
        for signal in main_signals
        if (event := build_event("control_shifted_entry_plus2", candles, signal, config, entry_delay_bars=3)) is not None
    ]

    weekday_events: list[CohortEvent] = []
    for source_event, signal in zip(main_events, main_signals):
        shifted = signal.detection_bar + config.weekday_shuffle_offset_bars
        if shifted >= len(candles):
            continue
        shifted_signal = ReversalSignal(
            cohort="control_weekday_shuffled",
            session_date=signal.session_date,
            entry_direction=source_event.direction,
            london_direction=signal.london_direction,
            extension=signal.extension,
            detection_bar=shifted,
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

    previous = previous_day_extensions(candles, config)
    previous_valid_days = {date: day for date, day in group_by_date(candles).items() if date in previous}
    previous_signals = build_signals(
        candles,
        config,
        previous,
        previous_valid_days,
        "control_previous_day_london_extension",
        config.ny_start,
        config.ny_end,
    )
    cohorts["control_previous_day_london_extension"] = [
        event
        for signal in previous_signals
        if (event := build_event("control_previous_day_london_extension", candles, signal, config, entry_delay_bars=1)) is not None
    ]

    for name in CONTROL_COHORTS:
        cohorts.setdefault(name, [])

    return cohorts, {
        **meta,
        "complete_london_sessions_all_moves": all_meta["complete_london_sessions"],
        "valid_extended_days": len(valid_days),
        "main_signal_days": len(main_signals),
        "extension_threshold_atr": config.extension_atr_threshold,
        "control_5_critical": "continuation control beats main -> STOP if decision-grade",
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


def _replace_event_return(event: CohortEvent, gross: float, cost_pct: float, metadata: dict[str, Any]) -> CohortEvent:
    net = gross - cost_pct
    return CohortEvent(
        **{
            **asdict(event),
            "gross_return_pct": gross,
            "net_return_pct": net,
            "r_return": net / event.risk_pct if event.risk_pct > 0 else 0.0,
            "metadata": {**event.metadata, **metadata},
        }
    )


def cost_adjusted_metrics(events: list[CohortEvent], cost_pct: float) -> dict[str, Any]:
    return cohort_metrics([
        _replace_event_return(event, event.gross_return_pct, cost_pct, {"round_trip_cost_pct": cost_pct})
        for event in events
    ])


def horizon_metrics(events: list[CohortEvent], horizon: int, cost_pct: float) -> dict[str, Any]:
    attr = {5: "return_5bar_pct", 8: "return_8bar_pct", 10: "return_10bar_pct"}[horizon]
    synthetic: list[CohortEvent] = []
    for event in events:
        gross = getattr(event, attr)
        if gross is None:
            continue
        synthetic.append(_replace_event_return(event, gross, cost_pct, {"horizon_bars": horizon}))
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
        and main_er >= 1.3
        and main_pf is not None
        and main_pf >= 1.5
        and main_mfe is not None
        and main_mfe < 0.60
        and not controls_better
        and positive_folds >= 3
    )
    if stop_reasons:
        verdict = "STOP"
    elif explore_passed:
        verdict = "EXPLORE"
    else:
        verdict = "INCONCLUSIVE"
    return {
        "recommendation": verdict,
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
    main = cohorts[PRIMARY_COHORT]
    return {
        "diagnostic": "OANDA_NY_REVERSAL_AFTER_LONDON_EXTENSION_FEASIBILITY_V1",
        "created_at_utc": iso(datetime.now(timezone.utc)),
        "config": asdict(config),
        "data_source": {"source": str(data_path), "fetched": False},
        "data_quality": dq,
        "session_meta": session_meta,
        "trial_00095_reference": TRIAL_00095_REFERENCE,
        "cohort_metrics": cohort_results,
        "direction_metrics": direction_metrics(main),
        "fold_metrics": folds,
        "cost_sensitivity": {
            f"{cost:.5f}": cost_adjusted_metrics(main, cost)
            for cost in config.sensitivity_costs_pct
        },
        "horizon_sensitivity": {
            f"{horizon}_bars": horizon_metrics(main, horizon, config.primary_cost_pct)
            for horizon in (config.primary_horizon_bars, config.secondary_horizon_bars, config.tertiary_horizon_bars)
        },
        "gate_evaluation": gates,
        "event_samples": {
            name: serialize_sample(events, config.max_serialized_events_per_cohort)
            for name, events in cohorts.items()
        },
    }


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
    lines = [
        "# OANDA_NY_REVERSAL_AFTER_LONDON_EXTENSION_FEASIBILITY_V1",
        "",
        f"**Date:** {payload['created_at_utc']}",
        "**Type:** Research-only OANDA session mean-reversion diagnostic",
        f"**Recommendation:** {gates['recommendation']}",
        "",
        "## 1. Executive Summary",
        "",
        "This diagnostic tests one OANDA-native session mechanism: fade extended London moves during NY overlap.",
        "It preserves ASIA_RANGE STOP and sweep/reclaim STOP as closed prior context; it does not rescue or combine them.",
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
        "## 2. Prior OANDA Boundary Statement",
        "",
        "- `ASIA_RANGE_LONDON_BREAKOUT` remains `STOP` due negative expectancy and control outperformance.",
        "- `EUR_USD M15` sweep/reclaim remains `STOP` due negative expectancy.",
        "- `XAU_USD H1` sweep/reclaim remains `STOP` due sample collapse.",
        "- This is the final OANDA session diagnostic before returning to multi-asset crypto if it stops.",
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
        f"| London session | `{config['london_start']}-{config['london_end']} UTC` |",
        f"| NY overlap | `{config['ny_start']}-{config['ny_end']} UTC` |",
        f"| Extension threshold | `{config['extension_atr_threshold']} * ATR14` |",
        "| Reversal confirmation | `first NY bar close opposite London direction` |",
        "| Entry | `i+1 open` |",
        f"| Primary horizon | `{config['primary_horizon_bars']}` bars |",
        f"| Secondary horizon | `{config['secondary_horizon_bars']}` bars |",
        f"| Tertiary horizon | `{config['tertiary_horizon_bars']}` bars |",
        f"| Risk reference | `London continuation extreme + {config['risk_buffer_atr']} * ATR14` |",
        f"| Primary cost | `{pct(config['primary_cost_pct'], 4)}` |",
        "",
        "## 5. Timing Model Verification",
        "",
        "- `london_known_bar` is the first bar after completed 07:00-12:00 UTC London session.",
        "- `state_known_bar = detection_bar` at first NY reversal bar close.",
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
        "| Metric | BTC trial-00095 | OANDA NY Reversal |",
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
        f"- Complete London sessions with extension: `{payload['session_meta']['complete_london_sessions']}`.",
        f"- Complete London sessions all moves: `{payload['session_meta']['complete_london_sessions_all_moves']}`.",
        f"- Skipped incomplete London sessions: `{payload['session_meta']['skipped_incomplete_london_sessions']}`.",
        f"- Valid extended days: `{payload['session_meta']['valid_extended_days']}`.",
        f"- Main signal days: `{payload['session_meta']['main_signal_days']}`.",
        f"- Critical continuation control: `{payload['session_meta']['control_5_critical']}`.",
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
            "**Next:** Do not pursue OANDA V2 rescue attempts. Per the approved sequence, return to multi-asset crypto expansion unless the user explicitly opens a new research family.",
        ])
    elif gates["recommendation"] == "EXPLORE":
        lines.extend([
            "**Reason:** Main cohort passed pre-declared EXPLORE gates after realistic entry, costs, controls, MFE accessibility, and walk-forward validation.",
            "",
            "**Next:** Plan V2 optimization or OANDA bot-port planning separately. This diagnostic does not authorize production changes.",
        ])
    else:
        lines.extend([
            "**Reason:** Results did not trigger hard STOP but did not meet all EXPLORE gates.",
            "",
            "**Next:** Treat OANDA NY reversal as marginal and return to multi-asset crypto per the planning document.",
        ])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


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
