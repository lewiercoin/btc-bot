"""Research-only trend/range state shift feasibility diagnostic.

Implements TREND_RANGE_STATE_SHIFT_FEASIBILITY_V1:

    Latched range state (ADX <= 20, CHOP >= 61.8) ->
    Explicit trend state (ADX >= 25, CHOP <= 38.2, |+DI - -DI| >= 5)
    Entry at bar i+1, returns from i+1
    ADX lag audit mandatory

This module is intentionally isolated from the live path. It reads SQLite market
data and writes research artifacts only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = PROJECT_ROOT / "research_lab" / "data" / "crowded_unwind_backtest.db"
DEFAULT_REPORT_PATH = PROJECT_ROOT / "research_lab" / "reports" / "trend_range_state_shift_feasibility_v1.md"
DEFAULT_JSON_PATH = PROJECT_ROOT / "research_lab" / "reports" / "trend_range_state_shift_feasibility_v1.json"

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
    di_period: int = 14
    adx_smoothing: int = 14
    chop_period: int = 14
    warmup_bars: int = 150
    adx_range_threshold: float = 20.0
    adx_trend_threshold: float = 25.0
    chop_range_threshold: float = 61.8
    chop_trend_threshold: float = 38.2
    di_spread_threshold: float = 5.0
    staleness_limit: int = 12
    outcome_horizon_bars: int = 20
    outcome_5bar: int = 5
    outcome_10bar: int = 10
    outcome_40bar: int = 40
    round_trip_cost_pct: float = 0.0010
    round_trip_cost_sensitivity: float = 0.0015
    fixed_risk_pct: float = 0.01
    random_offset_bars: int = 137
    shifted_entry_delay_bars: int = 3
    raw_move_lookback: int = 10
    max_serialized_events_per_cohort: int = 200
    volatility_low_pct: float = 35.0
    volatility_high_pct: float = 65.0
    momentum_lookback: int = 20


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
class IndicatorState:
    adx: float
    plus_di: float
    minus_di: float
    chop: float


@dataclass(frozen=True, slots=True)
class LatchedState:
    state: str  # "RANGE", "TREND_LONG", "TREND_SHORT", "NEUTRAL"
    last_explicit_range_bar: int | None
    last_explicit_trend_bar: int | None


@dataclass(frozen=True, slots=True)
class TransitionEvent:
    detection_bar: int
    direction: str  # "LONG" or "SHORT"
    last_explicit_range_bar: int
    adx: float
    plus_di: float
    minus_di: float
    chop: float


@dataclass(frozen=True, slots=True)
class LagAudit:
    raw_move_start_bar: int
    adx_lag_bars: int
    lag_mfe_before_entry: float
    lag_mfe_after_entry: float
    lag_mfe_consumed_pct: float


@dataclass(slots=True)
class CohortEvent:
    cohort: str
    detection_bar: int
    state_known_bar: int
    entry_candidate_bar: int
    return_start_bar: int
    direction: str
    detection_time_utc: str
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
    return_40bar_pct: float | None
    mfe_before_entry: float
    mfe_after_entry: float
    mae_after_entry: float
    total_mfe: float
    mfe_consumed_pct: float
    entry_to_mfe_bars: int | None
    adx: float
    plus_di: float
    minus_di: float
    chop: float
    last_explicit_range_bar: int
    structural_stop: float | None
    r_multiple: float | None
    lag_audit: dict[str, Any] | None
    metadata: dict[str, Any]


# --- Utility functions ---

def parse_ts(raw: Any) -> datetime:
    if isinstance(raw, datetime):
        return raw.astimezone(timezone.utc) if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
    text = str(raw).replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    return parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def fmt_float(value: Any, digits: int = 6) -> str:
    if value is None:
        return "n/a"
    if value == float("inf"):
        return "inf"
    return f"{float(value):.{digits}f}"


# --- ADX/CHOP Calculation (deterministic, Wilder smoothing) ---

def compute_indicators(candles: list[Candle], config: DiagnosticConfig) -> list[IndicatorState | None]:
    """Compute ADX, +DI, -DI, CHOP for each bar. Returns None for warmup bars."""
    n = len(candles)
    period = config.di_period
    adx_smooth = config.adx_smoothing
    chop_period = config.chop_period

    # Pre-compute True Range, +DM, -DM
    tr = [0.0] * n
    plus_dm = [0.0] * n
    minus_dm = [0.0] * n

    for i in range(1, n):
        high_i = candles[i].high
        low_i = candles[i].low
        prev_close = candles[i - 1].close
        tr[i] = max(high_i - low_i, abs(high_i - prev_close), abs(low_i - prev_close))

        up_move = high_i - candles[i - 1].high
        down_move = candles[i - 1].low - low_i
        if up_move > down_move and up_move > 0:
            plus_dm[i] = up_move
        if down_move > up_move and down_move > 0:
            minus_dm[i] = down_move

    # Wilder smoothing for TR, +DM, -DM
    # First smoothed value = sum of first `period` raw values (starting from index 1)
    smooth_tr = [0.0] * n
    smooth_plus_dm = [0.0] * n
    smooth_minus_dm = [0.0] * n

    # We need at least period+1 bars (indices 1..period for first sum)
    if n < period + 1:
        return [None] * n

    # First smoothed values at index `period`
    smooth_tr[period] = sum(tr[1:period + 1])
    smooth_plus_dm[period] = sum(plus_dm[1:period + 1])
    smooth_minus_dm[period] = sum(minus_dm[1:period + 1])

    for i in range(period + 1, n):
        smooth_tr[i] = smooth_tr[i - 1] - smooth_tr[i - 1] / period + tr[i]
        smooth_plus_dm[i] = smooth_plus_dm[i - 1] - smooth_plus_dm[i - 1] / period + plus_dm[i]
        smooth_minus_dm[i] = smooth_minus_dm[i - 1] - smooth_minus_dm[i - 1] / period + minus_dm[i]

    # +DI, -DI, DX
    plus_di_arr = [0.0] * n
    minus_di_arr = [0.0] * n
    dx_arr = [0.0] * n
    di_valid = [False] * n

    for i in range(period, n):
        if smooth_tr[i] == 0:
            di_valid[i] = False
            continue
        plus_di_arr[i] = 100.0 * smooth_plus_dm[i] / smooth_tr[i]
        minus_di_arr[i] = 100.0 * smooth_minus_dm[i] / smooth_tr[i]
        di_sum = plus_di_arr[i] + minus_di_arr[i]
        if di_sum == 0:
            dx_arr[i] = 0.0
        else:
            dx_arr[i] = 100.0 * abs(plus_di_arr[i] - minus_di_arr[i]) / di_sum
        di_valid[i] = True

    # ADX: first ADX = average of first `adx_smooth` DX values starting at index `period`
    adx_arr = [0.0] * n
    adx_valid = [False] * n
    first_adx_idx = period + adx_smooth - 1  # index where first ADX is available

    if first_adx_idx >= n:
        return [None] * n

    # Collect first adx_smooth DX values
    first_dx_values = []
    for i in range(period, period + adx_smooth):
        if i >= n:
            return [None] * n
        first_dx_values.append(dx_arr[i])

    adx_arr[first_adx_idx] = sum(first_dx_values) / adx_smooth
    adx_valid[first_adx_idx] = True

    for i in range(first_adx_idx + 1, n):
        adx_arr[i] = (adx_arr[i - 1] * (adx_smooth - 1) + dx_arr[i]) / adx_smooth
        adx_valid[i] = True

    # CHOP calculation
    chop_arr = [0.0] * n
    chop_valid = [False] * n
    log_period = math.log10(chop_period)

    for i in range(chop_period - 1, n):
        window_start = i - chop_period + 1
        sum_tr_window = sum(tr[max(1, window_start):i + 1])
        # For bars in the window before index 1, TR is 0 (handled by max(1, ..))
        if window_start < 1:
            sum_tr_window = sum(tr[1:i + 1])

        range_high = max(candles[j].high for j in range(window_start, i + 1))
        range_low = min(candles[j].low for j in range(window_start, i + 1))
        range_span = range_high - range_low

        if range_span <= 0:
            chop_arr[i] = 100.0
            chop_valid[i] = False  # excluded from directional event generation
        else:
            ratio = sum_tr_window / range_span
            if ratio <= 0:
                chop_arr[i] = 0.0
            else:
                chop_arr[i] = 100.0 * math.log10(ratio) / log_period
            chop_valid[i] = True

    # Build result
    results: list[IndicatorState | None] = [None] * n
    for i in range(n):
        if not adx_valid[i] or not di_valid[i] or not chop_valid[i]:
            continue
        results[i] = IndicatorState(
            adx=adx_arr[i],
            plus_di=plus_di_arr[i],
            minus_di=minus_di_arr[i],
            chop=chop_arr[i],
        )

    return results


# --- State Machine ---

def run_state_machine(
    candles: list[Candle],
    indicators: list[IndicatorState | None],
    config: DiagnosticConfig,
) -> list[TransitionEvent]:
    """Detect RANGE_TO_TREND transitions using latched state machine."""
    n = len(candles)
    events: list[TransitionEvent] = []

    # Track latched state
    current_latched = "NEUTRAL"
    last_explicit_range_bar: int | None = None
    last_explicit_trend_bar: int | None = None

    for i in range(n):
        if i < config.warmup_bars:
            # Update state during warmup but don't generate events
            ind = indicators[i]
            if ind is not None:
                if ind.adx <= config.adx_range_threshold and ind.chop >= config.chop_range_threshold:
                    current_latched = "RANGE"
                    last_explicit_range_bar = i
                elif (ind.adx >= config.adx_trend_threshold
                      and ind.chop <= config.chop_trend_threshold
                      and abs(ind.plus_di - ind.minus_di) >= config.di_spread_threshold):
                    if ind.plus_di > ind.minus_di:
                        current_latched = "TREND_LONG"
                    else:
                        current_latched = "TREND_SHORT"
                    last_explicit_trend_bar = i
            continue

        ind = indicators[i]
        if ind is None:
            continue

        # Classify current bar
        is_explicit_range = (
            ind.adx <= config.adx_range_threshold
            and ind.chop >= config.chop_range_threshold
        )
        is_explicit_trend = (
            ind.adx >= config.adx_trend_threshold
            and ind.chop <= config.chop_trend_threshold
            and abs(ind.plus_di - ind.minus_di) >= config.di_spread_threshold
        )

        # Check for transition BEFORE updating latched state
        if is_explicit_trend and current_latched == "RANGE":
            # Staleness check
            if last_explicit_range_bar is not None and (i - last_explicit_range_bar) <= config.staleness_limit:
                # Direction from DI
                if ind.plus_di > ind.minus_di:
                    direction = "LONG"
                elif ind.minus_di > ind.plus_di:
                    direction = "SHORT"
                else:
                    # Equal DI, no event
                    direction = None

                if direction is not None:
                    events.append(TransitionEvent(
                        detection_bar=i,
                        direction=direction,
                        last_explicit_range_bar=last_explicit_range_bar,
                        adx=ind.adx,
                        plus_di=ind.plus_di,
                        minus_di=ind.minus_di,
                        chop=ind.chop,
                    ))

        # Update latched state
        if is_explicit_range:
            current_latched = "RANGE"
            last_explicit_range_bar = i
        elif is_explicit_trend:
            if ind.plus_di > ind.minus_di:
                current_latched = "TREND_LONG"
            elif ind.minus_di > ind.plus_di:
                current_latched = "TREND_SHORT"
            else:
                current_latched = "TREND_LONG"  # tie-break, won't generate event anyway
            last_explicit_trend_bar = i
        # Neutral bars do not update latched state

    return events


# --- MFE/MAE Calculation ---

def favorable_move(candles: list[Candle], start: int, end: int, reference: float, direction: str) -> float:
    if start > end or start >= len(candles):
        return 0.0
    end = min(end, len(candles) - 1)
    if direction == "LONG":
        return max(0.0, max(c.high for c in candles[start:end + 1]) - reference)
    return max(0.0, reference - min(c.low for c in candles[start:end + 1]))


def adverse_move(candles: list[Candle], start: int, end: int, reference: float, direction: str) -> float:
    if start > end or start >= len(candles):
        return 0.0
    end = min(end, len(candles) - 1)
    if direction == "LONG":
        return max(0.0, reference - min(c.low for c in candles[start:end + 1]))
    return max(0.0, max(c.high for c in candles[start:end + 1]) - reference)


def entry_to_mfe_offset(candles: list[Candle], start: int, end: int, direction: str) -> int | None:
    if start > end or start >= len(candles):
        return None
    end = min(end, len(candles) - 1)
    subset = candles[start:end + 1]
    if not subset:
        return None
    if direction == "LONG":
        best = max(range(len(subset)), key=lambda offset: subset[offset].high)
    else:
        best = min(range(len(subset)), key=lambda offset: subset[offset].low)
    return best


# --- ADX Lag Audit ---

def compute_lag_audit(
    candles: list[Candle],
    event: TransitionEvent,
    entry_bar: int,
    entry_price: float,
    config: DiagnosticConfig,
) -> LagAudit:
    """Compute raw_move_start_bar and lag-adjusted MFE."""
    detection_bar = event.detection_bar
    range_bar = event.last_explicit_range_bar
    direction = event.direction

    # Find raw_move_start_bar: earliest bar in [range_bar+1, detection_bar]
    # where close breaks prior 10-bar high/low in event direction
    raw_move_start = detection_bar  # default if none found

    search_start = range_bar + 1
    for i in range(search_start, detection_bar + 1):
        lookback_start = max(0, i - config.raw_move_lookback)
        if lookback_start >= i:
            continue
        if direction == "LONG":
            prior_high = max(candles[j].close for j in range(lookback_start, i))
            if candles[i].close > prior_high:
                raw_move_start = i
                break
        else:
            prior_low = min(candles[j].close for j in range(lookback_start, i))
            if candles[i].close < prior_low:
                raw_move_start = i
                break

    adx_lag_bars = detection_bar - raw_move_start

    # Lag-adjusted MFE: before_entry starts at raw_move_start
    exit_bar = min(entry_bar + config.outcome_horizon_bars - 1, len(candles) - 1)

    # MFE from raw_move_start through entry_bar - 1
    if raw_move_start < entry_bar:
        ref_price = candles[raw_move_start].open if raw_move_start < len(candles) else entry_price
        lag_mfe_before = favorable_move(candles, raw_move_start, entry_bar - 1, ref_price, direction)
    else:
        lag_mfe_before = 0.0

    # MFE from entry_bar through exit_bar
    lag_mfe_after = favorable_move(candles, entry_bar, exit_bar, entry_price, direction)

    total = lag_mfe_before + lag_mfe_after
    if total <= 0:
        consumed = 1.0
    else:
        consumed = lag_mfe_before / total

    return LagAudit(
        raw_move_start_bar=raw_move_start,
        adx_lag_bars=adx_lag_bars,
        lag_mfe_before_entry=lag_mfe_before,
        lag_mfe_after_entry=lag_mfe_after,
        lag_mfe_consumed_pct=consumed,
    )


# --- Structural Stop ---

def compute_structural_stop(candles: list[Candle], event: TransitionEvent) -> float | None:
    """Structural stop: min low (LONG) or max high (SHORT) between range_bar and detection_bar."""
    range_bar = event.last_explicit_range_bar
    detection_bar = event.detection_bar

    if range_bar >= detection_bar:
        return None

    window = candles[range_bar:detection_bar + 1]
    if not window:
        return None

    if event.direction == "LONG":
        return min(c.low for c in window)
    else:
        return max(c.high for c in window)


# --- Event Builder ---

def build_main_event(
    candles: list[Candle],
    event: TransitionEvent,
    config: DiagnosticConfig,
    cohort: str = "main_range_to_trend",
    entry_delay: int = 1,
    metadata: dict[str, Any] | None = None,
) -> CohortEvent | None:
    """Build a CohortEvent from a TransitionEvent."""
    detection_bar = event.detection_bar
    entry_bar = detection_bar + entry_delay
    exit_bar = entry_bar + config.outcome_horizon_bars - 1

    if exit_bar >= len(candles) or entry_bar >= len(candles):
        return None

    entry_price = candles[entry_bar].open
    if entry_price <= 0:
        return None

    exit_price = candles[exit_bar].close
    direction = event.direction

    # Returns
    def signed_return(ep: float, xp: float) -> float:
        if direction == "LONG":
            return (xp - ep) / ep
        return (ep - xp) / ep

    gross = signed_return(entry_price, exit_price)
    net = gross - config.round_trip_cost_pct
    r_return = net / config.fixed_risk_pct if config.fixed_risk_pct else net

    def horizon_return(bars: int) -> float | None:
        target = entry_bar + bars - 1
        if target >= len(candles):
            return None
        return signed_return(entry_price, candles[target].close) - config.round_trip_cost_pct

    # Primary MFE before entry (detection_bar only for 1-bar delay)
    detection_close = candles[detection_bar].close
    mfe_before = favorable_move(candles, detection_bar, entry_bar - 1, detection_close, direction)
    mfe_after = favorable_move(candles, entry_bar, exit_bar, entry_price, direction)
    mae_after = adverse_move(candles, entry_bar, exit_bar, entry_price, direction)
    total_mfe = max(0.0, mfe_before) + max(0.0, mfe_after)
    consumed = 1.0 if total_mfe <= 0 else min(max(mfe_before / total_mfe, 0.0), 1.0)

    # Structural stop
    structural_stop = compute_structural_stop(candles, event)
    r_multiple: float | None = None
    if structural_stop is not None:
        if direction == "LONG":
            stop_dist = entry_price - structural_stop
        else:
            stop_dist = structural_stop - entry_price
        if stop_dist > 0:
            r_multiple = (net * entry_price) / stop_dist

    # ADX lag audit (only for main cohort and shifted entry)
    lag_audit: LagAudit | None = None
    if cohort in ("main_range_to_trend", "control_shifted_entry"):
        lag_audit = compute_lag_audit(candles, event, entry_bar, entry_price, config)

    return CohortEvent(
        cohort=cohort,
        detection_bar=detection_bar,
        state_known_bar=detection_bar,
        entry_candidate_bar=entry_bar,
        return_start_bar=entry_bar,
        direction=direction,
        detection_time_utc=iso(candles[detection_bar].open_time),
        entry_time_utc=iso(candles[entry_bar].open_time),
        entry_price=entry_price,
        exit_bar=exit_bar,
        exit_price=exit_price,
        gross_return_pct=gross,
        net_return_pct=net,
        r_return=r_return,
        return_5bar_pct=horizon_return(config.outcome_5bar),
        return_10bar_pct=horizon_return(config.outcome_10bar),
        return_20bar_pct=net,
        return_40bar_pct=horizon_return(config.outcome_40bar),
        mfe_before_entry=mfe_before,
        mfe_after_entry=mfe_after,
        mae_after_entry=mae_after,
        total_mfe=total_mfe,
        mfe_consumed_pct=consumed,
        entry_to_mfe_bars=entry_to_mfe_offset(candles, entry_bar, exit_bar, direction),
        adx=event.adx,
        plus_di=event.plus_di,
        minus_di=event.minus_di,
        chop=event.chop,
        last_explicit_range_bar=event.last_explicit_range_bar,
        structural_stop=structural_stop,
        r_multiple=r_multiple,
        lag_audit=asdict(lag_audit) if lag_audit else None,
        metadata=metadata or {},
    )


# --- Control Cohorts ---

def build_control_simple_volatility(
    candles: list[Candle],
    config: DiagnosticConfig,
) -> list[CohortEvent]:
    """Control 1: Simple volatility percentile transition."""
    n = len(candles)
    events: list[CohortEvent] = []
    period = config.di_period  # 14-bar realized volatility

    # Compute 14-bar realized volatility (std of log returns)
    vol = [0.0] * n
    for i in range(period, n):
        log_returns = []
        for j in range(i - period + 1, i + 1):
            if candles[j - 1].close > 0 and candles[j].close > 0:
                log_returns.append(math.log(candles[j].close / candles[j - 1].close))
        if log_returns:
            m = sum(log_returns) / len(log_returns)
            variance = sum((r - m) ** 2 for r in log_returns) / len(log_returns)
            vol[i] = math.sqrt(variance)

    # Latched state based on rolling percentile of vol
    latched_low = False
    last_low_bar: int | None = None
    baseline_size = 120

    for i in range(config.warmup_bars, n):
        if i < baseline_size + period:
            continue
        # Get baseline volatilities
        baseline_vols = [vol[j] for j in range(i - baseline_size, i) if vol[j] > 0]
        if len(baseline_vols) < baseline_size // 2:
            continue

        sorted_vols = sorted(baseline_vols)
        low_thresh = _percentile_sorted(sorted_vols, config.volatility_low_pct)
        high_thresh = _percentile_sorted(sorted_vols, config.volatility_high_pct)

        current_vol = vol[i]
        is_low = current_vol <= low_thresh and current_vol > 0
        is_high = current_vol >= high_thresh

        if is_low:
            latched_low = True
            last_low_bar = i

        if is_high and latched_low and last_low_bar is not None:
            if (i - last_low_bar) <= config.staleness_limit:
                # Direction from 20-bar momentum
                if i >= config.momentum_lookback:
                    momentum = candles[i].close - candles[i - config.momentum_lookback].close
                    direction = "LONG" if momentum > 0 else "SHORT"
                else:
                    direction = "LONG"

                entry_bar = i + 1
                exit_bar = entry_bar + config.outcome_horizon_bars - 1
                if exit_bar < n and entry_bar < n:
                    entry_price = candles[entry_bar].open
                    if entry_price > 0:
                        evt = _build_control_event(
                            candles, i, entry_bar, exit_bar, direction,
                            config, "control_simple_volatility",
                            {"control": "14-bar vol rising from <35th to >65th percentile"},
                        )
                        if evt:
                            events.append(evt)
            latched_low = False

    return events


def build_control_adx_only(
    candles: list[Candle],
    indicators: list[IndicatorState | None],
    config: DiagnosticConfig,
) -> list[CohortEvent]:
    """Control 2: ADX-only transition (no CHOP requirement)."""
    n = len(candles)
    events: list[CohortEvent] = []
    latched_low = False
    last_low_bar: int | None = None

    for i in range(config.warmup_bars, n):
        ind = indicators[i]
        if ind is None:
            continue

        is_low_adx = ind.adx <= config.adx_range_threshold
        is_high_adx = ind.adx >= config.adx_trend_threshold

        if is_low_adx:
            latched_low = True
            last_low_bar = i

        if is_high_adx and latched_low and last_low_bar is not None:
            if (i - last_low_bar) <= config.staleness_limit:
                if ind.plus_di > ind.minus_di:
                    direction = "LONG"
                elif ind.minus_di > ind.plus_di:
                    direction = "SHORT"
                else:
                    latched_low = False
                    continue

                entry_bar = i + 1
                exit_bar = entry_bar + config.outcome_horizon_bars - 1
                if exit_bar < n and entry_bar < n:
                    entry_price = candles[entry_bar].open
                    if entry_price > 0:
                        evt = _build_control_event(
                            candles, i, entry_bar, exit_bar, direction,
                            config, "control_adx_only",
                            {"control": "ADX-only transition, no CHOP requirement"},
                        )
                        if evt:
                            events.append(evt)
            latched_low = False

    return events


def build_control_chop_only(
    candles: list[Candle],
    indicators: list[IndicatorState | None],
    config: DiagnosticConfig,
) -> list[CohortEvent]:
    """Control 3: CHOP-only transition (no ADX requirement)."""
    n = len(candles)
    events: list[CohortEvent] = []
    latched_high = False
    last_high_bar: int | None = None

    for i in range(config.warmup_bars, n):
        ind = indicators[i]
        if ind is None:
            continue

        is_high_chop = ind.chop >= config.chop_range_threshold
        is_low_chop = ind.chop <= config.chop_trend_threshold

        if is_high_chop:
            latched_high = True
            last_high_bar = i

        if is_low_chop and latched_high and last_high_bar is not None:
            if (i - last_high_bar) <= config.staleness_limit:
                # Direction from 20-bar momentum
                if i >= config.momentum_lookback:
                    momentum = candles[i].close - candles[i - config.momentum_lookback].close
                    direction = "LONG" if momentum > 0 else "SHORT"
                else:
                    direction = "LONG"

                entry_bar = i + 1
                exit_bar = entry_bar + config.outcome_horizon_bars - 1
                if exit_bar < n and entry_bar < n:
                    entry_price = candles[entry_bar].open
                    if entry_price > 0:
                        evt = _build_control_event(
                            candles, i, entry_bar, exit_bar, direction,
                            config, "control_chop_only",
                            {"control": "CHOP-only transition, no ADX requirement"},
                        )
                        if evt:
                            events.append(evt)
            latched_high = False

    return events


def build_control_shifted_entry(
    candles: list[Candle],
    main_events: list[TransitionEvent],
    config: DiagnosticConfig,
) -> list[CohortEvent]:
    """Control 4: Same main signal, entry delayed to i+3."""
    events: list[CohortEvent] = []
    for te in main_events:
        evt = build_main_event(
            candles, te, config,
            cohort="control_shifted_entry",
            entry_delay=config.shifted_entry_delay_bars,
            metadata={"control": "same main signal, entry delayed to i+3"},
        )
        if evt:
            events.append(evt)
    return events


def build_control_same_state_non_transition(
    candles: list[Candle],
    indicators: list[IndicatorState | None],
    main_events: list[TransitionEvent],
    config: DiagnosticConfig,
) -> list[CohortEvent]:
    """Control 5: Explicit trend state but prior latched state was NOT range."""
    n = len(candles)
    events: list[CohortEvent] = []
    main_bars = {te.detection_bar for te in main_events}

    # Run state machine to find bars with explicit trend but NOT preceded by range
    current_latched = "NEUTRAL"
    last_explicit_range_bar: int | None = None

    for i in range(n):
        ind = indicators[i]
        if ind is None:
            continue

        is_explicit_range = (
            ind.adx <= config.adx_range_threshold
            and ind.chop >= config.chop_range_threshold
        )
        is_explicit_trend = (
            ind.adx >= config.adx_trend_threshold
            and ind.chop <= config.chop_trend_threshold
            and abs(ind.plus_di - ind.minus_di) >= config.di_spread_threshold
        )

        if i >= config.warmup_bars and is_explicit_trend and i not in main_bars:
            # This is a trend state bar that is NOT a main transition event
            if current_latched != "RANGE":
                if ind.plus_di > ind.minus_di:
                    direction = "LONG"
                elif ind.minus_di > ind.plus_di:
                    direction = "SHORT"
                else:
                    if is_explicit_range:
                        current_latched = "RANGE"
                        last_explicit_range_bar = i
                    elif is_explicit_trend:
                        current_latched = "TREND_LONG"
                    continue

                entry_bar = i + 1
                exit_bar = entry_bar + config.outcome_horizon_bars - 1
                if exit_bar < n and entry_bar < n:
                    entry_price = candles[entry_bar].open
                    if entry_price > 0:
                        evt = _build_control_event(
                            candles, i, entry_bar, exit_bar, direction,
                            config, "control_same_state_non_transition",
                            {"control": "explicit trend state, prior latched NOT range"},
                        )
                        if evt:
                            events.append(evt)

        # Update latched state
        if is_explicit_range:
            current_latched = "RANGE"
            last_explicit_range_bar = i
        elif is_explicit_trend:
            if ind.plus_di > ind.minus_di:
                current_latched = "TREND_LONG"
            else:
                current_latched = "TREND_SHORT"

    return events


def build_control_opposite_regime(
    candles: list[Candle],
    indicators: list[IndicatorState | None],
    config: DiagnosticConfig,
) -> list[CohortEvent]:
    """Control 6: Trend-to-range transition (opposite regime)."""
    n = len(candles)
    events: list[CohortEvent] = []
    current_latched = "NEUTRAL"
    last_trend_direction: str | None = None
    last_explicit_trend_bar: int | None = None

    for i in range(n):
        ind = indicators[i]
        if ind is None:
            continue

        is_explicit_range = (
            ind.adx <= config.adx_range_threshold
            and ind.chop >= config.chop_range_threshold
        )
        is_explicit_trend = (
            ind.adx >= config.adx_trend_threshold
            and ind.chop <= config.chop_trend_threshold
            and abs(ind.plus_di - ind.minus_di) >= config.di_spread_threshold
        )

        if i >= config.warmup_bars and is_explicit_range:
            if current_latched in ("TREND_LONG", "TREND_SHORT") and last_explicit_trend_bar is not None:
                if (i - last_explicit_trend_bar) <= config.staleness_limit:
                    # Use prior trend direction for continuation test
                    direction = last_trend_direction if last_trend_direction else "LONG"
                    entry_bar = i + 1
                    exit_bar = entry_bar + config.outcome_horizon_bars - 1
                    if exit_bar < n and entry_bar < n:
                        entry_price = candles[entry_bar].open
                        if entry_price > 0:
                            evt = _build_control_event(
                                candles, i, entry_bar, exit_bar, direction,
                                config, "control_opposite_regime",
                                {"control": "trend-to-range transition, continuation in prior trend direction"},
                            )
                            if evt:
                                events.append(evt)

        # Update latched state
        if is_explicit_range:
            current_latched = "RANGE"
        elif is_explicit_trend:
            if ind.plus_di > ind.minus_di:
                current_latched = "TREND_LONG"
                last_trend_direction = "LONG"
            else:
                current_latched = "TREND_SHORT"
                last_trend_direction = "SHORT"
            last_explicit_trend_bar = i

    return events


def build_control_random_offset(
    candles: list[Candle],
    main_events: list[TransitionEvent],
    config: DiagnosticConfig,
) -> list[CohortEvent]:
    """Control 7: Shift main event timestamps by +137 bars."""
    events: list[CohortEvent] = []
    main_bars = {te.detection_bar for te in main_events}
    n = len(candles)

    for te in main_events:
        shifted_bar = te.detection_bar + config.random_offset_bars
        if shifted_bar in main_bars:
            continue
        entry_bar = shifted_bar + 1
        exit_bar = entry_bar + config.outcome_horizon_bars - 1
        if exit_bar >= n or entry_bar >= n or shifted_bar >= n:
            continue
        entry_price = candles[entry_bar].open
        if entry_price <= 0:
            continue

        evt = _build_control_event(
            candles, shifted_bar, entry_bar, exit_bar, te.direction,
            config, "control_random_offset",
            {"control": "main event shifted by +137 bars", "source_detection_bar": te.detection_bar},
        )
        if evt:
            events.append(evt)

    return events


def _build_control_event(
    candles: list[Candle],
    detection_bar: int,
    entry_bar: int,
    exit_bar: int,
    direction: str,
    config: DiagnosticConfig,
    cohort: str,
    metadata: dict[str, Any],
) -> CohortEvent | None:
    """Generic control event builder."""
    if exit_bar >= len(candles) or entry_bar >= len(candles):
        return None
    entry_price = candles[entry_bar].open
    if entry_price <= 0:
        return None

    exit_price = candles[exit_bar].close

    def signed_return(ep: float, xp: float) -> float:
        if direction == "LONG":
            return (xp - ep) / ep
        return (ep - xp) / ep

    gross = signed_return(entry_price, exit_price)
    net = gross - config.round_trip_cost_pct
    r_return = net / config.fixed_risk_pct if config.fixed_risk_pct else net

    def horizon_return(bars: int) -> float | None:
        target = entry_bar + bars - 1
        if target >= len(candles):
            return None
        return signed_return(entry_price, candles[target].close) - config.round_trip_cost_pct

    detection_close = candles[detection_bar].close
    mfe_before = favorable_move(candles, detection_bar, entry_bar - 1, detection_close, direction)
    mfe_after = favorable_move(candles, entry_bar, exit_bar, entry_price, direction)
    mae_after = adverse_move(candles, entry_bar, exit_bar, entry_price, direction)
    total_mfe = max(0.0, mfe_before) + max(0.0, mfe_after)
    consumed = 1.0 if total_mfe <= 0 else min(max(mfe_before / total_mfe, 0.0), 1.0)

    return CohortEvent(
        cohort=cohort,
        detection_bar=detection_bar,
        state_known_bar=detection_bar,
        entry_candidate_bar=entry_bar,
        return_start_bar=entry_bar,
        direction=direction,
        detection_time_utc=iso(candles[detection_bar].open_time),
        entry_time_utc=iso(candles[entry_bar].open_time),
        entry_price=entry_price,
        exit_bar=exit_bar,
        exit_price=exit_price,
        gross_return_pct=gross,
        net_return_pct=net,
        r_return=r_return,
        return_5bar_pct=horizon_return(config.outcome_5bar),
        return_10bar_pct=horizon_return(config.outcome_10bar),
        return_20bar_pct=net,
        return_40bar_pct=horizon_return(config.outcome_40bar),
        mfe_before_entry=mfe_before,
        mfe_after_entry=mfe_after,
        mae_after_entry=mae_after,
        total_mfe=total_mfe,
        mfe_consumed_pct=consumed,
        entry_to_mfe_bars=entry_to_mfe_offset(candles, entry_bar, exit_bar, direction),
        adx=0.0,
        plus_di=0.0,
        minus_di=0.0,
        chop=0.0,
        last_explicit_range_bar=detection_bar,
        structural_stop=None,
        r_multiple=None,
        lag_audit=None,
        metadata=metadata,
    )


def _percentile_sorted(sorted_values: list[float], pct: float) -> float:
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    rank = (pct / 100.0) * (len(sorted_values) - 1)
    lower = int(rank)
    upper = min(lower + 1, len(sorted_values) - 1)
    weight = rank - lower
    return sorted_values[lower] * (1.0 - weight) + sorted_values[upper] * weight


# --- Metrics ---

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
            event for event in events
            if start <= parse_ts(event.detection_time_utc) <= end
        ]
        returns = [event.r_return for event in subset]
        net = [event.net_return_pct for event in subset]
        result.append({
            "fold": fold_name,
            "count": len(subset),
            "start_time_utc": iso(start),
            "end_time_utc": iso(end),
            "er": mean(returns) if returns else 0.0,
            "median_net_return_pct": median(net) if net else 0.0,
            "win_rate": (sum(1 for v in returns if v > 0) / len(returns)) if returns else 0.0,
            "positive_median_net": bool(net and median(net) > 0),
        })
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

    # Lag audit aggregate (only for cohorts that have it)
    lag_audits = [event.lag_audit for event in events if event.lag_audit is not None]
    lag_summary: dict[str, Any] | None = None
    if lag_audits:
        lag_bars = [la["adx_lag_bars"] for la in lag_audits]
        lag_consumed = [la["lag_mfe_consumed_pct"] for la in lag_audits]
        lag_summary = {
            "count": len(lag_audits),
            "median_adx_lag_bars": median(lag_bars),
            "mean_adx_lag_bars": mean(lag_bars),
            "median_lag_mfe_consumed_pct": median(lag_consumed),
            "mean_lag_mfe_consumed_pct": mean(lag_consumed),
        }

    return {
        "count": len(events),
        "er": mean(returns) if returns else 0.0,
        "median_r": median(returns) if returns else 0.0,
        "median_net_return_pct": median(net) if net else 0.0,
        "mean_net_return_pct": mean(net) if net else 0.0,
        "win_rate": (sum(1 for v in returns if v > 0) / len(returns)) if returns else 0.0,
        "profit_factor": profit_factor(returns),
        "avg_win_r": avg_win,
        "avg_loss_r": avg_loss,
        "avg_win_loss_ratio": (avg_win / avg_loss) if avg_loss > 0 else (1_000_000.0 if avg_win > 0 else 0.0),
        "median_mfe_consumed_pct": median(consumed) if consumed else None,
        "median_mfe_before_entry": median([e.mfe_before_entry for e in events]) if events else 0.0,
        "median_mfe_after_entry": median([e.mfe_after_entry for e in events]) if events else 0.0,
        "median_mae_after_entry": median([e.mae_after_entry for e in events]) if events else 0.0,
        "median_entry_to_mfe_bars": median([e.entry_to_mfe_bars for e in events if e.entry_to_mfe_bars is not None]) if events else None,
        "positive_folds": sum(1 for f in folds if f["positive_median_net"]),
        "folds": folds,
        "lag_audit_summary": lag_summary,
    }


# --- Invalidation Gates ---

def apply_gates(cohort_metrics: dict[str, dict[str, Any]]) -> dict[str, Any]:
    main = cohort_metrics["main_range_to_trend"]
    controls = {
        name: metrics for name, metrics in cohort_metrics.items()
        if name != "main_range_to_trend"
    }
    control_outperformers = [
        name for name, metrics in controls.items()
        if metrics["count"] > 0 and metrics["er"] > main["er"]
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

    # ADX lag STOP gate
    lag = main.get("lag_audit_summary")
    if lag is not None:
        if lag["median_adx_lag_bars"] > 3 and lag["median_lag_mfe_consumed_pct"] > 0.70:
            stop_reasons.append("adx_lag_gt_3_and_lag_mfe_consumed_gt_70pct")

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
        and (lag is None or lag["median_lag_mfe_consumed_pct"] <= 0.70)
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
                "ADX lag > 3 bars AND lag-adjusted MFE consumed > 70%",
                "any primary control cohort outperforms main on ER",
                "fewer than 2 of 4 folds positive",
                "sample size < 100",
            ],
            "EXPLORE": [
                "median net return after costs > 0",
                "post-entry ER > 1.5",
                "profit factor > 1.5",
                "median MFE consumed before entry < 60%",
                "lag-adjusted MFE consumed < 70%",
                "main beats all controls on ER",
                "at least 3 of 4 folds positive",
                "sample size >= 200",
            ],
            "INCONCLUSIVE": ["anything between STOP and EXPLORE"],
        },
    }


# --- Data Loading ---

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


def data_quality(candles: list[Candle]) -> dict[str, Any]:
    duplicate_timestamps = len(candles) - len({c.open_time for c in candles})
    non_monotonic = 0
    missing_gaps = 0
    step_seconds = None
    if len(candles) >= 2:
        deltas = [
            int((right.open_time - left.open_time).total_seconds())
            for left, right in zip(candles, candles[1:])
        ]
        positive = [d for d in deltas if d > 0]
        step_seconds = min(positive) if positive else None
        non_monotonic = sum(1 for d in deltas if d <= 0)
        if step_seconds:
            missing_gaps = sum(1 for d in deltas if d > step_seconds)
    ohlc_violations = sum(
        1 for c in candles
        if c.high < max(c.open, c.close, c.low) or c.low > min(c.open, c.close, c.high)
    )
    zero_volume = sum(1 for c in candles if c.volume <= 0)
    return {
        "rows": len(candles),
        "start_time_utc": iso(candles[0].open_time) if candles else None,
        "end_time_utc": iso(candles[-1].open_time) if candles else None,
        "duplicate_timestamps": duplicate_timestamps,
        "non_monotonic_timestamps": non_monotonic,
        "ohlc_violations": ohlc_violations,
        "missing_bar_gaps": missing_gaps,
        "inferred_step_seconds": step_seconds,
        "zero_volume_bars": zero_volume,
    }


# --- Report Rendering ---

def render_report(payload: dict[str, Any]) -> str:
    recommendation = payload["invalidation_gates"]["recommendation"]
    metrics = payload["cohort_metrics"]
    main = metrics["main_range_to_trend"]
    lag = main.get("lag_audit_summary")

    lines = [
        "# TREND_RANGE_STATE_SHIFT_FEASIBILITY_V1",
        "",
        "## Executive Summary",
        "",
        f"Recommendation: **{recommendation}**",
        "",
        "This is a research-only diagnostic. It did not modify production code, settings, trial-00095, execution, FeatureEngine, SignalEngine, Governance, or Risk.",
        "",
        f"- Main cohort events: `{main['count']}`",
        f"- Main post-entry ER: `{fmt_float(main['er'])}`",
        f"- Main profit factor: `{fmt_float(main['profit_factor'])}`",
        f"- Main win rate: `{fmt_float(main['win_rate'])}`",
        f"- Main median net return: `{fmt_float(main['median_net_return_pct'])}`",
        f"- Main median MFE consumed before entry: `{fmt_float(main['median_mfe_consumed_pct'])}`",
        f"- STOP reasons: `{', '.join(payload['invalidation_gates']['stop_reasons']) or 'none'}`",
        "",
        "## Mechanism",
        "",
        "- Latched range state: ADX <= 20 AND CHOP >= 61.8",
        "- Explicit trend state: ADX >= 25 AND CHOP <= 38.2 AND |+DI - -DI| >= 5",
        "- Direction from +DI/-DI at transition bar",
        "- Hysteresis: latched state machine with 12-bar staleness limit",
        "- Entry at bar i+1; primary returns start at i+1",
        "- 150-candle warmup for Wilder smoothing stability",
        "",
        "## ADX Lag Audit",
        "",
    ]

    if lag:
        lines.extend([
            f"- Median ADX lag bars: `{fmt_float(lag['median_adx_lag_bars'], 2)}`",
            f"- Mean ADX lag bars: `{fmt_float(lag['mean_adx_lag_bars'], 2)}`",
            f"- Median lag-adjusted MFE consumed: `{fmt_float(lag['median_lag_mfe_consumed_pct'])}`",
            f"- Mean lag-adjusted MFE consumed: `{fmt_float(lag['mean_lag_mfe_consumed_pct'])}`",
            f"- Lag STOP triggered: `{lag['median_adx_lag_bars'] > 3 and lag['median_lag_mfe_consumed_pct'] > 0.70}`",
        ])
    else:
        lines.append("- No lag audit data available (no main events)")

    lines.extend([
        "",
        "## Data Quality",
        "",
        f"- Candles: `{payload['data_quality']}`",
        "",
        "## Timing Model Verification",
        "",
        "| Bar | Value |",
        "| --- | --- |",
    ])
    for key, value in payload["timing_model"].items():
        lines.append(f"| `{key}` | `{value}` |")

    lines.extend([
        "",
        "Primary returns are measured from `entry_candidate_bar = i+1`, not from `detection_bar` or `raw_move_start_bar`.",
        "",
        "## Cohort Metrics",
        "",
        "| Cohort | Count | ER | Median R | PF | Win Rate | Median Net | Median MFE Consumed | Positive Folds |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ])
    for name, row in metrics.items():
        lines.append(
            f"| `{name}` | {row['count']} | {fmt_float(row['er'])} | {fmt_float(row['median_r'])} | "
            f"{fmt_float(row['profit_factor'])} | {fmt_float(row['win_rate'])} | "
            f"{fmt_float(row['median_net_return_pct'])} | {fmt_float(row['median_mfe_consumed_pct'])} | "
            f"{row['positive_folds']} |"
        )

    lines.extend([
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
        "- Simple volatility: 14-bar vol rising from <35th to >65th percentile, direction from 20-bar momentum.",
        "- ADX-only: latched ADX<=20 to ADX>=25, no CHOP. Direction from +DI/-DI.",
        "- CHOP-only: latched CHOP>=61.8 to CHOP<=38.2, no ADX. Direction from 20-bar momentum.",
        "- Shifted-entry: same main signal, entry delayed from i+1 to i+3.",
        "- Same-state non-transition: explicit trend state but prior latched state was NOT range.",
        "- Opposite-regime: trend-to-range transition, continuation in prior trend direction.",
        "- Random-offset: main events shifted by deterministic +137 bars.",
        "",
        f"Control outperformers: `{payload['invalidation_gates']['control_outperformers']}`",
        "",
        "## Trial-00095 Benchmark Comparison",
        "",
        f"- Reference benchmark: `{payload['benchmark_comparison']}`",
        "",
        "## Walk-Forward Metrics",
        "",
        "| Fold | Count | ER | Median Net | Win Rate | Positive Median Net |",
        "| --- | ---: | ---: | ---: | ---: | --- |",
    ])
    for fold in main["folds"]:
        lines.append(
            f"| `{fold['fold']}` | {fold['count']} | {fmt_float(fold['er'])} | "
            f"{fmt_float(fold['median_net_return_pct'])} | {fmt_float(fold['win_rate'])} | "
            f"`{fold['positive_median_net']}` |"
        )

    lines.extend([
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
        f"- JSON SHA256: `{payload['manifest'].get('json_sha256', 'pending')}`",
        "",
        f"## Recommendation: {recommendation}",
        "",
    ])

    if recommendation == "STOP":
        lines.append(f"**Reason:** {'; '.join(payload['invalidation_gates']['stop_reasons'])}")
    elif recommendation == "EXPLORE":
        lines.append("**Reason:** All STOP gates cleared and EXPLORE criteria met.")
    else:
        lines.append("**Reason:** Between STOP and EXPLORE thresholds.")

    lines.extend([
        "",
        "**Next:** Claude Code audits this diagnostic implementation and result before any follow-up work.",
    ])

    return "\n".join(lines) + "\n"


# --- Main Diagnostic Runner ---

def build_all_cohorts(
    candles: list[Candle],
    indicators: list[IndicatorState | None],
    config: DiagnosticConfig,
) -> dict[str, list[CohortEvent]]:
    """Build all cohorts: main + 7 controls."""
    # Main events via state machine
    transition_events = run_state_machine(candles, indicators, config)

    # Build main cohort
    main_events: list[CohortEvent] = []
    for te in transition_events:
        evt = build_main_event(candles, te, config)
        if evt:
            main_events.append(evt)

    cohorts: dict[str, list[CohortEvent]] = {
        "main_range_to_trend": main_events,
        "control_simple_volatility": build_control_simple_volatility(candles, config),
        "control_adx_only": build_control_adx_only(candles, indicators, config),
        "control_chop_only": build_control_chop_only(candles, indicators, config),
        "control_shifted_entry": build_control_shifted_entry(candles, transition_events, config),
        "control_same_state_non_transition": build_control_same_state_non_transition(
            candles, indicators, transition_events, config
        ),
        "control_opposite_regime": build_control_opposite_regime(candles, indicators, config),
        "control_random_offset": build_control_random_offset(candles, transition_events, config),
    }

    return cohorts


def run_diagnostic(
    *,
    db_path: Path,
    report_path: Path,
    json_path: Path,
    config: DiagnosticConfig,
) -> dict[str, Any]:
    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
        candles = load_candles(conn, config)

    if not candles:
        raise RuntimeError("No candles loaded from database")

    quality = data_quality(candles)
    indicators = compute_indicators(candles, config)
    cohorts = build_all_cohorts(candles, indicators, config)
    metrics = {name: metric_summary(events) for name, events in cohorts.items()}
    gates = apply_gates(metrics)

    payload = {
        "manifest": {
            "diagnostic": "TREND_RANGE_STATE_SHIFT_FEASIBILITY_V1",
            "research_only": True,
            "production_changes": False,
            "db_path": str(db_path),
            "report_path": str(report_path),
            "json_path": str(json_path),
            "generated_at_utc": iso(datetime.now(timezone.utc)),
        },
        "config": asdict(config),
        "data_quality": quality,
        "timing_model": {
            "detection_bar": "i",
            "state_known_bar": "i (at close)",
            "confirmation_bar": "i",
            "entry_candidate_bar": "i+1",
            "return_start_bar": "i+1",
            "primary_returns_from_detection_bar": False,
        },
        "cohort_metrics": metrics,
        "benchmark_comparison": TRIAL_00095_REFERENCE,
        "invalidation_gates": gates,
        "events_sample": {
            name: [asdict(e) for e in events[:config.max_serialized_events_per_cohort]]
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
