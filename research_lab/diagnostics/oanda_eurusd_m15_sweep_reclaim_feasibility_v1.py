"""Research-only OANDA EUR_USD M15 sweep/reclaim feasibility diagnostic.

Implements OANDA_EURUSD_M15_SWEEP_RECLAIM_FEASIBILITY_V1:

    equal levels known from completed prior bars only
    sweep + reclaim state known at bar i close
    entry candidate at bar i+1
    primary returns measured from bar i+1

This module is intentionally isolated from the live path. It fetches OANDA
historical mid candles, runs a deterministic research diagnostic, and writes
research artifacts only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPORT_PATH = PROJECT_ROOT / "research_lab" / "reports" / "oanda_eurusd_m15_sweep_reclaim_feasibility_v1.md"
DEFAULT_JSON_PATH = PROJECT_ROOT / "research_lab" / "reports" / "oanda_eurusd_m15_sweep_reclaim_feasibility_v1.json"
DEFAULT_DATA_PATH = PROJECT_ROOT / "research_lab" / "analysis_output" / "oanda_eur_usd_m15_candles_20240101_20260529.json"

TRIAL_00095_REFERENCE = {
    "er": 2.121,
    "profit_factor": 4.216,
    "win_rate": 0.5657,
    "trades": 274,
    "wf_er": 2.129,
    "wf_profit_factor": 4.663,
    "wf_trades": 271,
    "source": "trial_00095_conditional_edge_attribution_v1.md",
}

FOLD_WINDOWS = (
    ("fold_1_2024H1", datetime(2024, 1, 1, tzinfo=timezone.utc), datetime(2024, 7, 1, tzinfo=timezone.utc)),
    ("fold_2_2024H2", datetime(2024, 7, 1, tzinfo=timezone.utc), datetime(2025, 1, 1, tzinfo=timezone.utc)),
    ("fold_3_2025", datetime(2025, 1, 1, tzinfo=timezone.utc), datetime(2026, 1, 1, tzinfo=timezone.utc)),
    ("fold_4_2026", datetime(2026, 1, 1, tzinfo=timezone.utc), datetime(2027, 1, 1, tzinfo=timezone.utc)),
)

PRIMARY_COHORT = "main_sweep_reclaim"
CONTROL_COHORTS = (
    "control_sweep_without_reclaim",
    "control_reclaim_without_equal_level_sweep",
    "control_random_offset_137",
    "control_shifted_entry_plus2",
    "control_shifted_entry_plus3",
    "control_opposite_direction",
    "control_shallow_sweep",
    "control_wide_range_high_volatility",
)
MIN_DECISION_CONTROL_EVENTS = 25


@dataclass(frozen=True, slots=True)
class DiagnosticConfig:
    instrument: str = "EUR_USD"
    granularity: str = "M15"
    from_time: str = "2024-01-01T00:00:00Z"
    to_time: str = "2026-05-31T00:00:00Z"
    atr_period: int = 14
    equal_level_lookback: int = 50
    equal_level_tol_atr: float = 0.09
    sweep_buf_atr: float = 0.46
    sweep_proximity_atr: float = 0.40
    reclaim_buf_atr: float = 0.07
    wick_min_atr: float = 0.20
    level_min_age_bars: int = 5
    min_hits: int = 3
    min_sweep_depth_pct: float = 0.00030
    shallow_min_depth_pct: float = 0.00010
    entry_delay_bars: int = 1
    shifted_entry_plus2_bars: int = 3
    shifted_entry_plus3_bars: int = 4
    primary_horizon_bars: int = 5
    secondary_horizon_bars: int = 10
    primary_cost_pct: float = 0.00015
    sensitivity_costs_pct: tuple[float, ...] = (0.00010, 0.00015, 0.00025)
    stop_buffer_atr: float = 0.05
    random_offset_bars: int = 137
    wide_range_percentile: float = 75.0
    max_serialized_events_per_cohort: int = 50

    @property
    def min_prior_bars(self) -> int:
        return max(self.equal_level_lookback, self.atr_period + 2)


@dataclass(frozen=True, slots=True)
class OandaCredentials:
    api_key: str
    account_id: str | None
    environment: str = "practice"

    @property
    def base_url(self) -> str:
        if self.environment == "live":
            return "https://api-fxtrade.oanda.com"
        return "https://api-fxpractice.oanda.com"


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
class SweepState:
    detection_bar: int
    direction: str
    sweep_side: str
    level: float
    sweep_depth_pct: float
    atr: float
    range_width_pct: float
    range_width_percentile: float
    reclaimed: bool
    close_vs_reclaim_buffer_atr: float
    wick_vs_min_atr: float
    sweep_vs_buffer_atr: float
    metadata: dict[str, Any]


@dataclass(frozen=True, slots=True)
class CohortEvent:
    cohort: str
    level_known_bar: int
    detection_bar: int
    sweep_bar: int
    reclaim_bar: int
    state_known_bar: int
    confirmation_bar: int
    entry_candidate_bar: int
    label_available_bar: int
    return_start_bar: int
    direction: str
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
    return_5bar_pct: float
    return_10bar_pct: float | None
    mfe_before_entry: float
    mfe_after_entry: float
    mae_after_entry: float
    total_mfe: float
    mfe_consumed_pct: float
    entry_to_mfe_bars: int | None
    sweep_side: str
    sweep_level: float
    sweep_depth_pct: float
    atr: float
    range_width_pct: float
    range_width_percentile: float
    metadata: dict[str, Any]


def parse_ts(value: Any) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


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


def percentile_rank(values: list[float], value: float) -> float:
    if not values:
        return 50.0
    return sum(1 for item in values if item <= value) / len(values) * 100.0


def compute_atr(candles: list[Candle], end_index: int, period: int) -> float:
    if end_index < 1:
        return 0.0
    start = max(1, end_index - period + 1)
    true_ranges: list[float] = []
    for idx in range(start, end_index + 1):
        current = candles[idx]
        prev_close = candles[idx - 1].close
        true_ranges.append(
            max(
                current.high - current.low,
                abs(current.high - prev_close),
                abs(current.low - prev_close),
            )
        )
    return mean(true_ranges) if true_ranges else 0.0


def detect_equal_levels(
    levels: list[tuple[int, float]],
    tolerance: float,
    min_hits: int,
    min_age_bars: int,
) -> list[float]:
    if not levels:
        return []
    sorted_levels = sorted(levels, key=lambda item: item[1])
    clusters: list[list[tuple[int, float]]] = []
    current_cluster: list[tuple[int, float]] = [sorted_levels[0]]
    for item in sorted_levels[1:]:
        if abs(item[1] - current_cluster[-1][1]) <= tolerance:
            current_cluster.append(item)
        else:
            clusters.append(current_cluster)
            current_cluster = [item]
    clusters.append(current_cluster)

    merged: list[float] = []
    for cluster in clusters:
        if len(cluster) < min_hits:
            continue
        indices = [idx for idx, _ in cluster]
        if (max(indices) - min(indices)) < min_age_bars:
            continue
        merged.append(mean(price for _, price in cluster))
    return merged


def _range_width_pct(candles: list[Candle], start: int, end: int) -> float:
    if start >= end:
        return 0.0
    window = candles[start:end]
    if not window:
        return 0.0
    high = max(c.high for c in window)
    low = min(c.low for c in window)
    mid = (high + low) / 2.0
    return 0.0 if mid == 0 else (high - low) / mid


def prior_range_widths(candles: list[Candle], config: DiagnosticConfig) -> list[float]:
    widths: list[float] = []
    for idx in range(config.min_prior_bars, len(candles)):
        start = max(0, idx - config.equal_level_lookback)
        widths.append(_range_width_pct(candles, start, idx))
    return widths


def equal_levels_for_bar(
    candles: list[Candle],
    index: int,
    atr: float,
    config: DiagnosticConfig,
) -> tuple[list[float], list[float]]:
    prior_start = max(0, index - config.equal_level_lookback)
    prior = candles[prior_start:index]
    lows = [(offset, candle.low) for offset, candle in enumerate(prior)]
    highs = [(offset, candle.high) for offset, candle in enumerate(prior)]
    tolerance = atr * config.equal_level_tol_atr if atr > 0 else 0.0
    return (
        detect_equal_levels(lows, tolerance, config.min_hits, config.level_min_age_bars),
        detect_equal_levels(highs, tolerance, config.min_hits, config.level_min_age_bars),
    )


def detect_sweep_state(
    candles: list[Candle],
    index: int,
    config: DiagnosticConfig,
    range_width_distribution: list[float],
) -> SweepState | None:
    if index < config.min_prior_bars or index + config.primary_horizon_bars >= len(candles):
        return None
    atr = compute_atr(candles, index - 1, config.atr_period)
    if atr <= 0:
        return None
    equal_lows, equal_highs = equal_levels_for_bar(candles, index, atr, config)
    latest = candles[index]
    body_low = min(latest.open, latest.close)
    body_high = max(latest.open, latest.close)
    sweep_buffer = config.sweep_buf_atr * atr
    proximity = config.sweep_proximity_atr * atr
    reclaim_buffer = config.reclaim_buf_atr * atr
    wick_min = config.wick_min_atr * atr
    range_start = max(0, index - config.equal_level_lookback)
    range_width = _range_width_pct(candles, range_start, index)
    range_pct = percentile_rank(range_width_distribution, range_width)

    for level in equal_lows:
        if abs(latest.open - level) > proximity:
            continue
        swept = latest.low < (level - sweep_buffer)
        if not swept:
            continue
        reclaimed = latest.close > (level + reclaim_buffer)
        wick_ok = (body_low - latest.low) >= wick_min
        depth = abs(level - latest.low) / level if level else 0.0
        return SweepState(
            detection_bar=index,
            direction="LONG",
            sweep_side="LOW",
            level=float(level),
            sweep_depth_pct=depth,
            atr=atr,
            range_width_pct=range_width,
            range_width_percentile=range_pct,
            reclaimed=bool(reclaimed),
            close_vs_reclaim_buffer_atr=(latest.close - (level + reclaim_buffer)) / atr,
            wick_vs_min_atr=((body_low - latest.low) - wick_min) / atr,
            sweep_vs_buffer_atr=((level - sweep_buffer) - latest.low) / atr,
            metadata={"equal_lows": len(equal_lows), "equal_highs": len(equal_highs)},
        )

    for level in equal_highs:
        if abs(latest.open - level) > proximity:
            continue
        swept = latest.high > (level + sweep_buffer)
        if not swept:
            continue
        reclaimed = latest.close < (level - reclaim_buffer)
        wick_ok = (latest.high - body_high) >= wick_min
        depth = abs(latest.high - level) / level if level else 0.0
        return SweepState(
            detection_bar=index,
            direction="SHORT",
            sweep_side="HIGH",
            level=float(level),
            sweep_depth_pct=depth,
            atr=atr,
            range_width_pct=range_width,
            range_width_percentile=range_pct,
            reclaimed=bool(reclaimed),
            close_vs_reclaim_buffer_atr=((level - reclaim_buffer) - latest.close) / atr,
            wick_vs_min_atr=((latest.high - body_high) - wick_min) / atr,
            sweep_vs_buffer_atr=(latest.high - (level + sweep_buffer)) / atr,
            metadata={"equal_lows": len(equal_lows), "equal_highs": len(equal_highs)},
        )

    return None


def detect_local_reclaim_without_equal_level(
    candles: list[Candle],
    index: int,
    config: DiagnosticConfig,
    range_width_distribution: list[float],
) -> SweepState | None:
    if index < config.min_prior_bars or index + config.primary_horizon_bars >= len(candles):
        return None
    atr = compute_atr(candles, index - 1, config.atr_period)
    if atr <= 0:
        return None
    equal_lows, equal_highs = equal_levels_for_bar(candles, index, atr, config)
    if equal_lows or equal_highs:
        return None
    latest = candles[index]
    prev = candles[index - 1]
    body_low = min(latest.open, latest.close)
    body_high = max(latest.open, latest.close)
    sweep_buffer = config.sweep_buf_atr * atr
    reclaim_buffer = config.reclaim_buf_atr * atr
    wick_min = config.wick_min_atr * atr
    range_start = max(0, index - config.equal_level_lookback)
    range_width = _range_width_pct(candles, range_start, index)
    range_pct = percentile_rank(range_width_distribution, range_width)

    if latest.low < prev.low - sweep_buffer and latest.close > prev.low + reclaim_buffer:
        return SweepState(
            detection_bar=index,
            direction="LONG",
            sweep_side="LOW",
            level=prev.low,
            sweep_depth_pct=abs(prev.low - latest.low) / prev.low if prev.low else 0.0,
            atr=atr,
            range_width_pct=range_width,
            range_width_percentile=range_pct,
            reclaimed=True,
            close_vs_reclaim_buffer_atr=(latest.close - (prev.low + reclaim_buffer)) / atr,
            wick_vs_min_atr=((body_low - latest.low) - wick_min) / atr,
            sweep_vs_buffer_atr=((prev.low - sweep_buffer) - latest.low) / atr,
            metadata={"control": "local_prior_low_reclaim"},
        )
    if latest.high > prev.high + sweep_buffer and latest.close < prev.high - reclaim_buffer:
        return SweepState(
            detection_bar=index,
            direction="SHORT",
            sweep_side="HIGH",
            level=prev.high,
            sweep_depth_pct=abs(latest.high - prev.high) / prev.high if prev.high else 0.0,
            atr=atr,
            range_width_pct=range_width,
            range_width_percentile=range_pct,
            reclaimed=True,
            close_vs_reclaim_buffer_atr=((prev.high - reclaim_buffer) - latest.close) / atr,
            wick_vs_min_atr=((latest.high - body_high) - wick_min) / atr,
            sweep_vs_buffer_atr=(latest.high - (prev.high + sweep_buffer)) / atr,
            metadata={"control": "local_prior_high_reclaim"},
        )
    return None


def opposite_direction(direction: str) -> str:
    return "SHORT" if direction == "LONG" else "LONG"


def build_event(
    cohort: str,
    candles: list[Candle],
    state: SweepState,
    config: DiagnosticConfig,
    entry_delay_bars: int,
    direction: str | None = None,
    source_index_override: int | None = None,
    cost_pct: float | None = None,
    metadata: dict[str, Any] | None = None,
) -> CohortEvent | None:
    event_index = source_index_override if source_index_override is not None else state.detection_bar
    entry_index = event_index + entry_delay_bars
    exit_index = entry_index + config.primary_horizon_bars
    if entry_index >= len(candles) or exit_index >= len(candles):
        return None
    direction = direction or state.direction
    cost = config.primary_cost_pct if cost_pct is None else cost_pct
    detection = candles[event_index]
    entry = candles[entry_index]
    exit_candle = candles[exit_index]
    entry_price = entry.open
    exit_price = exit_candle.close
    stop_buffer = state.atr * config.stop_buffer_atr

    if direction == "LONG":
        stop_reference = candles[event_index].low - stop_buffer
        risk_pct = abs(entry_price - stop_reference) / entry_price if entry_price else 0.0
        if risk_pct <= 0:
            return None
        gross_return = (exit_price - entry_price) / entry_price
        gross_return_5 = gross_return
        secondary_exit = entry_index + config.secondary_horizon_bars
        gross_return_10 = (
            (candles[secondary_exit].close - entry_price) / entry_price
            if secondary_exit < len(candles)
            else None
        )
        before_window = candles[event_index:entry_index]
        after_window = candles[entry_index:exit_index + 1]
        mfe_before = max((c.high - detection.close for c in before_window), default=0.0)
        mfe_after = max((c.high - entry_price for c in after_window), default=0.0)
        mae_after = max((entry_price - c.low for c in after_window), default=0.0)
        best_value = max((c.high, offset) for offset, c in enumerate(after_window))
    else:
        stop_reference = candles[event_index].high + stop_buffer
        risk_pct = abs(stop_reference - entry_price) / entry_price if entry_price else 0.0
        if risk_pct <= 0:
            return None
        gross_return = (entry_price - exit_price) / entry_price
        gross_return_5 = gross_return
        secondary_exit = entry_index + config.secondary_horizon_bars
        gross_return_10 = (
            (entry_price - candles[secondary_exit].close) / entry_price
            if secondary_exit < len(candles)
            else None
        )
        before_window = candles[event_index:entry_index]
        after_window = candles[entry_index:exit_index + 1]
        mfe_before = max((detection.close - c.low for c in before_window), default=0.0)
        mfe_after = max((entry_price - c.low for c in after_window), default=0.0)
        mae_after = max((c.high - entry_price for c in after_window), default=0.0)
        best_value = max((-c.low, offset) for offset, c in enumerate(after_window))

    mfe_before = max(0.0, mfe_before)
    mfe_after = max(0.0, mfe_after)
    mae_after = max(0.0, mae_after)
    total_mfe = mfe_before + mfe_after
    consumed = mfe_before / total_mfe if total_mfe > 0 else 0.0
    net_return = gross_return - cost
    r_return = net_return / risk_pct
    merged_metadata = dict(state.metadata)
    if metadata:
        merged_metadata.update(metadata)
    merged_metadata["round_trip_cost_pct"] = cost

    return CohortEvent(
        cohort=cohort,
        level_known_bar=state.detection_bar - 1,
        detection_bar=state.detection_bar,
        sweep_bar=state.detection_bar,
        reclaim_bar=state.detection_bar,
        state_known_bar=state.detection_bar,
        confirmation_bar=state.detection_bar,
        entry_candidate_bar=entry_index,
        label_available_bar=exit_index,
        return_start_bar=entry_index,
        direction=direction,
        detection_time_utc=iso(candles[state.detection_bar].time),
        state_known_time_utc=iso(candles[state.detection_bar].time),
        entry_time_utc=iso(entry.time),
        exit_time_utc=iso(exit_candle.time),
        entry_price=entry_price,
        exit_price=exit_price,
        stop_reference_price=stop_reference,
        risk_pct=risk_pct,
        gross_return_pct=gross_return,
        net_return_pct=net_return,
        r_return=r_return,
        return_5bar_pct=gross_return_5,
        return_10bar_pct=gross_return_10,
        mfe_before_entry=mfe_before,
        mfe_after_entry=mfe_after,
        mae_after_entry=mae_after,
        total_mfe=total_mfe,
        mfe_consumed_pct=consumed,
        entry_to_mfe_bars=int(best_value[1]) if after_window else None,
        sweep_side=state.sweep_side,
        sweep_level=state.level,
        sweep_depth_pct=state.sweep_depth_pct,
        atr=state.atr,
        range_width_pct=state.range_width_pct,
        range_width_percentile=state.range_width_percentile,
        metadata=merged_metadata,
    )


def build_cohorts(candles: list[Candle], config: DiagnosticConfig) -> dict[str, list[CohortEvent]]:
    cohorts: dict[str, list[CohortEvent]] = {PRIMARY_COHORT: []}
    for name in CONTROL_COHORTS:
        cohorts[name] = []
    widths = prior_range_widths(candles, config)
    wide_threshold = percentile(widths, config.wide_range_percentile)
    main_states: list[SweepState] = []

    for index in range(config.min_prior_bars, len(candles) - config.secondary_horizon_bars - 1):
        state = detect_sweep_state(candles, index, config, widths)
        if state is not None:
            if state.reclaimed and state.sweep_depth_pct >= config.min_sweep_depth_pct:
                main_event = build_event(PRIMARY_COHORT, candles, state, config, config.entry_delay_bars)
                if main_event is not None:
                    cohorts[PRIMARY_COHORT].append(main_event)
                    main_states.append(state)

                    opposite = build_event(
                        "control_opposite_direction",
                        candles,
                        state,
                        config,
                        config.entry_delay_bars,
                        direction=opposite_direction(state.direction),
                        metadata={"source_direction": state.direction},
                    )
                    if opposite is not None:
                        cohorts["control_opposite_direction"].append(opposite)

                    shifted_2 = build_event(
                        "control_shifted_entry_plus2",
                        candles,
                        state,
                        config,
                        config.shifted_entry_plus2_bars,
                        metadata={"entry_delay_bars": config.shifted_entry_plus2_bars},
                    )
                    if shifted_2 is not None:
                        cohorts["control_shifted_entry_plus2"].append(shifted_2)

                    shifted_3 = build_event(
                        "control_shifted_entry_plus3",
                        candles,
                        state,
                        config,
                        config.shifted_entry_plus3_bars,
                        metadata={"entry_delay_bars": config.shifted_entry_plus3_bars},
                    )
                    if shifted_3 is not None:
                        cohorts["control_shifted_entry_plus3"].append(shifted_3)

                    random_index = index + config.random_offset_bars
                    if random_index + config.entry_delay_bars + config.primary_horizon_bars < len(candles):
                        random_event = build_event(
                            "control_random_offset_137",
                            candles,
                            state,
                            config,
                            config.entry_delay_bars,
                            source_index_override=random_index,
                            metadata={
                                "source_detection_bar": state.detection_bar,
                                "random_offset_bars": config.random_offset_bars,
                            },
                        )
                        if random_event is not None:
                            cohorts["control_random_offset_137"].append(random_event)

                    if state.range_width_pct >= wide_threshold:
                        wide_event = build_event(
                            "control_wide_range_high_volatility",
                            candles,
                            state,
                            config,
                            config.entry_delay_bars,
                            metadata={"wide_range_threshold": wide_threshold},
                        )
                        if wide_event is not None:
                            cohorts["control_wide_range_high_volatility"].append(wide_event)

            elif not state.reclaimed:
                event = build_event(
                    "control_sweep_without_reclaim",
                    candles,
                    state,
                    config,
                    config.entry_delay_bars,
                    metadata={"reclaimed": False},
                )
                if event is not None:
                    cohorts["control_sweep_without_reclaim"].append(event)

            elif state.sweep_depth_pct < config.min_sweep_depth_pct and state.sweep_depth_pct >= config.shallow_min_depth_pct:
                event = build_event(
                    "control_shallow_sweep",
                    candles,
                    state,
                    config,
                    config.entry_delay_bars,
                    metadata={
                        "min_sweep_depth_pct": config.min_sweep_depth_pct,
                        "shallow_min_depth_pct": config.shallow_min_depth_pct,
                    },
                )
                if event is not None:
                    cohorts["control_shallow_sweep"].append(event)

        local_state = detect_local_reclaim_without_equal_level(candles, index, config, widths)
        if local_state is not None:
            event = build_event(
                "control_reclaim_without_equal_level_sweep",
                candles,
                local_state,
                config,
                config.entry_delay_bars,
            )
            if event is not None:
                cohorts["control_reclaim_without_equal_level_sweep"].append(event)

    return cohorts


def cohort_metrics(events: list[CohortEvent]) -> dict[str, Any]:
    if not events:
        return {
            "count": 0,
            "er": None,
            "profit_factor": None,
            "win_rate": None,
            "median_net_return_pct": None,
            "median_r": None,
            "median_mfe_consumed_pct": None,
            "avg_mfe_consumed_pct": None,
            "median_mfe_after_entry": None,
            "median_mae_after_entry": None,
        }
    r_values = [event.r_return for event in events]
    net_values = [event.net_return_pct for event in events]
    winners = [value for value in r_values if value > 0]
    losers = [value for value in r_values if value < 0]
    gross_wins = sum(winners)
    gross_losses = abs(sum(losers))
    return {
        "count": len(events),
        "er": mean(r_values),
        "profit_factor": (gross_wins / gross_losses) if gross_losses > 0 else (999.0 if gross_wins > 0 else 0.0),
        "win_rate": len(winners) / len(events),
        "median_net_return_pct": median(net_values),
        "median_r": median(r_values),
        "median_mfe_consumed_pct": median(event.mfe_consumed_pct for event in events),
        "avg_mfe_consumed_pct": mean(event.mfe_consumed_pct for event in events),
        "median_mfe_after_entry": median(event.mfe_after_entry for event in events),
        "median_mae_after_entry": median(event.mae_after_entry for event in events),
    }


def fold_for_time(timestamp: datetime) -> str:
    for name, start, end in FOLD_WINDOWS:
        if start <= timestamp < end:
            return name
    return "outside_folds"


def fold_metrics(events: list[CohortEvent]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for name, _, _ in FOLD_WINDOWS:
        subset = [event for event in events if fold_for_time(parse_ts(event.entry_time_utc)) == name]
        metrics = cohort_metrics(subset)
        rows.append(
            {
                "fold": name,
                **metrics,
                "positive": bool(
                    metrics["count"]
                    and metrics["median_net_return_pct"] is not None
                    and metrics["median_net_return_pct"] > 0
                    and metrics["er"] is not None
                    and metrics["er"] > 1.0
                ),
            }
        )
    return rows


def direction_metrics(events: list[CohortEvent]) -> dict[str, dict[str, Any]]:
    return {
        direction: cohort_metrics([event for event in events if event.direction == direction])
        for direction in ("LONG", "SHORT")
    }


def sensitivity_metrics(events: list[CohortEvent], config: DiagnosticConfig) -> dict[str, dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}
    for cost in config.sensitivity_costs_pct:
        adjusted: list[CohortEvent] = []
        for event in events:
            delta = cost - config.primary_cost_pct
            adjusted.append(
                CohortEvent(
                    **{
                        **asdict(event),
                        "net_return_pct": event.net_return_pct - delta,
                        "r_return": (event.net_return_pct - delta) / event.risk_pct,
                        "metadata": {**event.metadata, "round_trip_cost_pct": cost},
                    }
                )
            )
        results[f"{cost:.4%}"] = cohort_metrics(adjusted)
    return results


def data_quality(candles: list[Candle]) -> dict[str, Any]:
    bad_ohlc = 0
    duplicates = 0
    gaps_gt_24h = 0
    gaps_gt_72h = 0
    max_gap_hours = 0.0
    prev: datetime | None = None
    seen: set[str] = set()
    for candle in candles:
        key = candle.time.isoformat()
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
            gap = (candle.time - prev).total_seconds() / 3600.0
            max_gap_hours = max(max_gap_hours, gap)
            if gap > 24:
                gaps_gt_24h += 1
            if gap > 72:
                gaps_gt_72h += 1
        prev = candle.time
    return {
        "count": len(candles),
        "first": iso(candles[0].time) if candles else None,
        "last": iso(candles[-1].time) if candles else None,
        "ohlc_bad_rows": bad_ohlc,
        "duplicates": duplicates,
        "gaps_gt_24h": gaps_gt_24h,
        "gaps_gt_72h": gaps_gt_72h,
        "max_gap_hours": round(max_gap_hours, 2),
        "data_gate": "PASS" if len(candles) >= 10000 and bad_ohlc == 0 and duplicates == 0 else "FAIL",
    }


def evaluate_gates(cohort_results: dict[str, dict[str, Any]], folds: list[dict[str, Any]]) -> dict[str, Any]:
    main = cohort_results[PRIMARY_COHORT]
    stop_reasons: list[str] = []
    explore_reasons: list[str] = []
    positive_folds = sum(1 for fold in folds if fold.get("positive"))
    main_er = main.get("er")
    main_pf = main.get("profit_factor")
    main_count = int(main.get("count") or 0)
    main_median_net = main.get("median_net_return_pct")
    main_mfe_consumed = main.get("median_mfe_consumed_pct")
    controls_better = []
    for name, metrics in cohort_results.items():
        if name == PRIMARY_COHORT:
            continue
        control_er = metrics.get("er")
        if (
            control_er is not None
            and main_er is not None
            and metrics.get("count", 0) >= MIN_DECISION_CONTROL_EVENTS
            and control_er > main_er
        ):
            controls_better.append(name)

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
    if main_mfe_consumed is not None and main_mfe_consumed > 0.70:
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
        and main_mfe_consumed is not None
        and main_mfe_consumed < 0.60
        and not controls_better
        and positive_folds >= 3
    )
    if explore_passed:
        explore_reasons.append("all_explore_gates_passed")

    if stop_reasons:
        recommendation = "STOP"
    elif explore_passed:
        recommendation = "EXPLORE"
    else:
        recommendation = "INCONCLUSIVE"

    return {
        "recommendation": recommendation,
        "stop_reasons": stop_reasons,
        "explore_reasons": explore_reasons,
        "positive_folds": positive_folds,
        "controls_better": controls_better,
    }


def load_credentials(credential_file: Path | None = None) -> OandaCredentials:
    api_key = os.getenv("OANDA_API_KEY", "").strip()
    account_id = os.getenv("OANDA_ACCOUNT_ID", "").strip() or None
    environment = os.getenv("OANDA_ENVIRONMENT", "practice").strip().lower() or "practice"

    if credential_file is not None:
        text = credential_file.read_text(encoding="utf-8", errors="ignore")
        env_api = re.search(r"OANDA_API_KEY\s*[:=]\s*([^\s#]+)", text)
        env_account = re.search(r"OANDA_ACCOUNT_ID\s*[:=]\s*([^\s#]+)", text)
        env_environment = re.search(r"OANDA_ENVIRONMENT\s*[:=]\s*([^\s#]+)", text)
        token_like = re.search(r"\b[a-f0-9]{32}-[a-f0-9]{32}\b", text)
        account_like = re.search(r"\b\d{3}-\d{3}-\d{7}-\d{3}\b", text)
        if env_api:
            api_key = env_api.group(1)
        elif token_like:
            api_key = token_like.group(0)
        if env_account:
            account_id = env_account.group(1)
        elif account_like:
            account_id = account_like.group(0)
        if env_environment:
            environment = env_environment.group(1).lower()
        elif re.search(r"(?i)\b(demo|practice)\b", text):
            environment = "practice"

    if not api_key:
        raise ValueError("OANDA_API_KEY is required via environment or --credential-file")
    if environment not in {"practice", "live"}:
        environment = "practice"
    return OandaCredentials(api_key=api_key, account_id=account_id, environment=environment)


def _oanda_get(credentials: OandaCredentials, path: str, params: dict[str, str] | None = None) -> dict[str, Any]:
    query = urllib.parse.urlencode(params or {})
    url = credentials.base_url + path + (f"?{query}" if query else "")
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {credentials.api_key}"})
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 - operator-supplied trusted endpoint
        return json.loads(response.read().decode("utf-8"))


def ensure_account_id(credentials: OandaCredentials) -> OandaCredentials:
    if credentials.account_id:
        return credentials
    response = _oanda_get(credentials, "/v3/accounts")
    accounts = response.get("accounts", [])
    if not accounts:
        raise ValueError("No OANDA accounts available for provided credentials")
    return OandaCredentials(
        api_key=credentials.api_key,
        account_id=str(accounts[0]["id"]),
        environment=credentials.environment,
    )


def fetch_oanda_candles(credentials: OandaCredentials, config: DiagnosticConfig) -> list[Candle]:
    start = parse_ts(config.from_time)
    end = parse_ts(config.to_time)
    cursor = start
    candles: dict[str, Candle] = {}
    request_count = 0
    step_by_granularity = {
        "M15": timedelta(minutes=15),
        "M30": timedelta(minutes=30),
        "H1": timedelta(hours=1),
    }
    step = step_by_granularity.get(config.granularity, timedelta(hours=1))
    while cursor < end and request_count < 100:
        response = _oanda_get(
            credentials,
            f"/v3/instruments/{config.instrument}/candles",
            {
                "granularity": config.granularity,
                "price": "M",
                "from": cursor.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "count": "5000",
                "includeFirst": "true",
            },
        )
        batch = response.get("candles", [])
        request_count += 1
        complete = [row for row in batch if row.get("complete")]
        if not complete:
            break
        for row in complete:
            timestamp = parse_ts(row["time"])
            if timestamp >= end:
                continue
            mid = row["mid"]
            candles[row["time"]] = Candle(
                index=0,
                time=timestamp,
                open=float(mid["o"]),
                high=float(mid["h"]),
                low=float(mid["l"]),
                close=float(mid["c"]),
                volume=float(row.get("volume", 0.0)),
            )
        last_time = parse_ts(complete[-1]["time"])
        next_cursor = last_time + step
        if next_cursor <= cursor:
            break
        cursor = next_cursor
    ordered = sorted(candles.values(), key=lambda item: item.time)
    return [
        Candle(
            index=index,
            time=candle.time,
            open=candle.open,
            high=candle.high,
            low=candle.low,
            close=candle.close,
            volume=candle.volume,
        )
        for index, candle in enumerate(ordered)
    ]


def candles_to_json(candles: list[Candle]) -> list[dict[str, Any]]:
    return [
        {
            "time": iso(candle.time),
            "open": candle.open,
            "high": candle.high,
            "low": candle.low,
            "close": candle.close,
            "volume": candle.volume,
        }
        for candle in candles
    ]


def candles_from_json(path: Path) -> list[Candle]:
    data = json.loads(path.read_text(encoding="utf-8"))
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
        for index, row in enumerate(data)
    ]


def save_candles(path: Path, candles: list[Candle]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(candles_to_json(candles), indent=2), encoding="utf-8")


def load_or_fetch_candles(
    config: DiagnosticConfig,
    data_path: Path,
    credential_file: Path | None = None,
    refresh: bool = False,
) -> tuple[list[Candle], dict[str, Any]]:
    if data_path.exists() and not refresh:
        candles = candles_from_json(data_path)
        return candles, {"source": str(data_path), "fetched": False}
    credentials = ensure_account_id(load_credentials(credential_file))
    candles = fetch_oanda_candles(credentials, config)
    save_candles(data_path, candles)
    return candles, {
        "source": "OANDA practice REST API" if credentials.environment == "practice" else "OANDA live REST API",
        "fetched": True,
        "credential_source": "external_file_or_environment",
        "account_id_present": bool(credentials.account_id),
    }


def serialize_sample(events: list[CohortEvent], limit: int) -> list[dict[str, Any]]:
    return [asdict(event) for event in events[:limit]]


def run_diagnostic(
    config: DiagnosticConfig,
    data_path: Path = DEFAULT_DATA_PATH,
    credential_file: Path | None = None,
    refresh_data: bool = False,
) -> dict[str, Any]:
    candles, source_meta = load_or_fetch_candles(config, data_path, credential_file, refresh_data)
    dq = data_quality(candles)
    cohorts = build_cohorts(candles, config)
    cohort_results = {name: cohort_metrics(events) for name, events in cohorts.items()}
    folds = fold_metrics(cohorts[PRIMARY_COHORT])
    gates = evaluate_gates(cohort_results, folds)
    direction = direction_metrics(cohorts[PRIMARY_COHORT])
    sensitivity = sensitivity_metrics(cohorts[PRIMARY_COHORT], config)
    payload = {
        "diagnostic": "OANDA_EURUSD_M15_SWEEP_RECLAIM_FEASIBILITY_V1",
        "created_at_utc": iso(datetime.now(timezone.utc)),
        "config": asdict(config),
        "data_source": source_meta,
        "data_quality": dq,
        "trial_00095_reference": TRIAL_00095_REFERENCE,
        "cohort_metrics": cohort_results,
        "fold_metrics": folds,
        "direction_metrics": direction,
        "cost_sensitivity": sensitivity,
        "gate_evaluation": gates,
        "event_samples": {
            name: serialize_sample(events, config.max_serialized_events_per_cohort)
            for name, events in cohorts.items()
        },
    }
    return payload


def _fmt(value: Any, digits: int = 4) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def _pct(value: Any, digits: int = 2) -> str:
    if value is None:
        return "N/A"
    return f"{float(value) * 100:.{digits}f}%"


def artifact_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_report(path: Path, payload: dict[str, Any], json_path: Path | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    gates = payload["gate_evaluation"]
    dq = payload["data_quality"]
    main = payload["cohort_metrics"][PRIMARY_COHORT]
    lines: list[str] = [
        "# OANDA_EURUSD_M15_SWEEP_RECLAIM_FEASIBILITY_V1",
        "",
        f"**Date:** {payload['created_at_utc']}",
        "**Type:** Research-only OANDA sweep/reclaim transfer diagnostic",
        f"**Recommendation:** {gates['recommendation']}",
        "",
        "## Executive Summary",
        "",
        "This diagnostic tests whether the OHLC-only sweep/reclaim core from `btc-bot` transfers to OANDA `EUR_USD` M15.",
        "It does not validate SMC, does not use OB/FVG/mitigation logic, and does not modify production code.",
        "The prior `XAU_USD H1` strict transfer remains STOP; this diagnostic tests one separately approved `EUR_USD M15` candidate.",
        "",
        f"- Main events: `{main['count']}`",
        f"- Main ER: `{_fmt(main['er'])}`",
        f"- Main PF: `{_fmt(main['profit_factor'])}`",
        f"- Main win rate: `{_pct(main['win_rate'])}`",
        f"- Main median net return at 0.015% cost: `{_pct(main['median_net_return_pct'], 4)}`",
        f"- Main median MFE consumed before entry: `{_pct(main['median_mfe_consumed_pct'])}`",
        f"- Positive folds: `{gates['positive_folds']} / 4`",
        f"- STOP reasons: `{', '.join(gates['stop_reasons']) if gates['stop_reasons'] else 'None'}`",
        "",
        "## Data Quality",
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
        "## Timing Model Verification",
        "",
        "- `level_known_bar = detection_bar - 1`.",
        "- `state_known_bar = detection_bar` at bar close.",
        "- `entry_candidate_bar = detection_bar + 1` for main events.",
        "- `return_start_bar = entry_candidate_bar`.",
        "- Detection-bar movement is used only for MFE-before-entry audit metrics.",
        "",
        "## Cohort Metrics",
        "",
        "| Cohort | Count | ER | PF | Win Rate | Median Net | Median MFE Consumed |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, metrics in payload["cohort_metrics"].items():
        lines.append(
            f"| `{name}` | {metrics['count']} | {_fmt(metrics['er'])} | {_fmt(metrics['profit_factor'])} | "
            f"{_pct(metrics['win_rate'])} | {_pct(metrics['median_net_return_pct'], 4)} | "
            f"{_pct(metrics['median_mfe_consumed_pct'])} |"
        )
    lines.extend([
        "",
        "## Direction Split",
        "",
        "| Direction | Count | ER | PF | Win Rate | Median Net |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ])
    for name, metrics in payload["direction_metrics"].items():
        lines.append(
            f"| `{name}` | {metrics['count']} | {_fmt(metrics['er'])} | {_fmt(metrics['profit_factor'])} | "
            f"{_pct(metrics['win_rate'])} | {_pct(metrics['median_net_return_pct'], 4)} |"
        )
    lines.extend([
        "",
        "## Walk-Forward Folds",
        "",
        "| Fold | Count | ER | PF | Median Net | Positive |",
        "| --- | ---: | ---: | ---: | ---: | --- |",
    ])
    for row in payload["fold_metrics"]:
        lines.append(
            f"| `{row['fold']}` | {row['count']} | {_fmt(row['er'])} | {_fmt(row['profit_factor'])} | "
            f"{_pct(row['median_net_return_pct'], 4)} | {row['positive']} |"
        )
    lines.extend([
        "",
        "## Cost Sensitivity",
        "",
        "| Round-trip Cost | Count | ER | PF | Win Rate | Median Net |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ])
    for cost, metrics in payload["cost_sensitivity"].items():
        lines.append(
            f"| `{cost}` | {metrics['count']} | {_fmt(metrics['er'])} | {_fmt(metrics['profit_factor'])} | "
            f"{_pct(metrics['win_rate'])} | {_pct(metrics['median_net_return_pct'], 4)} |"
        )
    lines.extend([
        "",
        "## Baseline Comparison",
        "",
        "| Metric | BTC trial-00095 | OANDA EUR_USD M15 main |",
        "| --- | ---: | ---: |",
        f"| ER | {TRIAL_00095_REFERENCE['er']} | {_fmt(main['er'])} |",
        f"| PF | {TRIAL_00095_REFERENCE['profit_factor']} | {_fmt(main['profit_factor'])} |",
        f"| Win rate | {_pct(TRIAL_00095_REFERENCE['win_rate'])} | {_pct(main['win_rate'])} |",
        f"| Trades / events | {TRIAL_00095_REFERENCE['trades']} | {main['count']} |",
        "",
        "## Invalidation Criteria Evaluation",
        "",
        f"- Recommendation: `{gates['recommendation']}`",
        f"- STOP reasons: `{gates['stop_reasons']}`",
        f"- EXPLORE reasons: `{gates['explore_reasons']}`",
        f"- Controls better than main: `{gates['controls_better']}`",
        f"- Control outperformance gate minimum sample: `{MIN_DECISION_CONTROL_EVENTS}` events",
        "- Smaller control cohorts are reported for inspection but are not decision-grade STOP gates.",
        "",
        "## Artifact",
        "",
    ])
    if json_path is not None and json_path.exists():
        lines.append(f"- JSON path: `{json_path.as_posix()}`")
        lines.append(f"- JSON SHA256: `{artifact_sha256(json_path)}`")
    else:
        lines.append("- JSON path: not written")
    lines.extend([
        "",
        "## Recommendation",
        "",
        f"### Verdict: {gates['recommendation']}",
        "",
    ])
    if gates["recommendation"] == "STOP":
        reason = "; ".join(gates["stop_reasons"]) or "STOP gate triggered"
        lines.extend([
            f"**Reason:** {reason}",
            "",
            "**Next:** Do not port this OANDA sweep/reclaim transfer to runtime. Return to multi-asset crypto scaling or a separately planned OANDA hypothesis.",
        ])
    elif gates["recommendation"] == "EXPLORE":
        lines.extend([
            "**Reason:** Main cohort passed the predeclared EXPLORE gates after realistic entry and conservative costs.",
            "",
            "**Next:** Plan a V2 OANDA diagnostic with stricter execution modeling before any OANDA bot port.",
        ])
    else:
        lines.extend([
            "**Reason:** Results did not trigger STOP but also did not meet EXPLORE gates.",
            "",
            "**Next:** Decide whether to extend data, test a separately planned instrument, or stop OANDA transfer research.",
        ])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--credential-file", type=Path, default=None, help="Optional local OANDA credential file; never committed.")
    parser.add_argument("--data-path", type=Path, default=DEFAULT_DATA_PATH)
    parser.add_argument("--refresh-data", action="store_true", help="Fetch OANDA candles even if cached data exists.")
    parser.add_argument("--report-path", type=Path, default=DEFAULT_REPORT_PATH)
    parser.add_argument("--json-path", type=Path, default=DEFAULT_JSON_PATH)
    parser.add_argument("--from-time", default="2024-01-01T00:00:00Z")
    parser.add_argument("--to-time", default="2026-05-31T00:00:00Z")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    config = DiagnosticConfig(from_time=args.from_time, to_time=args.to_time)
    payload = run_diagnostic(
        config=config,
        data_path=args.data_path,
        credential_file=args.credential_file,
        refresh_data=args.refresh_data,
    )
    write_json(args.json_path, payload)
    write_report(args.report_path, payload, args.json_path)
    print(json.dumps({"recommendation": payload["gate_evaluation"]["recommendation"], "report": str(args.report_path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
