"""Research-only liquidation burst reversal diagnostic.

Implements LIQUIDATION_BURST_REVERSAL_ENTRY_FEASIBILITY_V1:

    sweep detection at bar i
    liquidation burst measured on bars i..i+2
    state known at bar i+2
    entry candidate at bar i+3
    primary returns measured from bar i+3

This module is intentionally isolated from the live path. It reads SQLite market
data and writes research artifacts only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from bisect import bisect_right
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = PROJECT_ROOT / "research_lab" / "data" / "crowded_unwind_backtest.db"
DEFAULT_REPORT_PATH = PROJECT_ROOT / "research_lab" / "reports" / "liquidation_burst_reversal_entry_feasibility_v1.md"
DEFAULT_JSON_PATH = PROJECT_ROOT / "research_lab" / "reports" / "liquidation_burst_reversal_entry_feasibility_v1.json"
DEFAULT_STORE_CANDIDATES = (
    PROJECT_ROOT / "research_lab" / "research_lab.db.v3",
    PROJECT_ROOT / "research_lab" / "research_lab.db",
    PROJECT_ROOT / "research_lab" / "research_lab_server.db",
)

TRIAL_00095_REFERENCE = {
    "er": 2.1,
    "profit_factor": 4.6,
    "trades": 271,
    "entry_timing": "sweep + reclaim around 1-2 bars from sweep",
    "source": "approved planning document / milestone tracker reference",
}


@dataclass(frozen=True, slots=True)
class DiagnosticConfig:
    symbol: str = "BTCUSDT"
    timeframe: str = "15m"
    atr_period: int = 14
    equal_level_lookback: int = 50
    equal_level_tol_atr: float = 0.25
    min_hits: int = 3
    min_age_bars: int = 5
    sweep_buf_atr: float = 0.15
    sweep_proximity_atr: float = 0.40
    baseline_lookback_bars: int = 96
    liquidation_burst_multiple: float = 2.0
    non_liquidation_multiple: float = 0.5
    burst_window_bars: int = 3
    entry_delay_bars: int = 3
    shifted_entry_delay_bars: int = 5
    outcome_horizon_bars: int = 5
    round_trip_cost_pct: float = 0.0010
    fixed_risk_pct: float = 0.01
    max_serialized_events_per_cohort: int = 200


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
class ForceBucket:
    buy_notional: float = 0.0
    sell_notional: float = 0.0
    buy_count: int = 0
    sell_count: int = 0


@dataclass(frozen=True, slots=True)
class SweepEvent:
    detection_bar: int
    direction: str
    sweep_side: str
    level: float
    atr: float


@dataclass(frozen=True, slots=True)
class CohortEvent:
    cohort: str
    detection_bar: int
    state_known_bar: int
    confirmation_bar: int
    entry_candidate_bar: int
    label_available_bar: int
    return_start_bar: int
    direction: str
    sweep_side: str | None
    detection_time_utc: str
    state_known_time_utc: str
    entry_time_utc: str
    entry_price: float
    exit_bar: int
    exit_price: float
    gross_return_pct: float
    net_return_pct: float
    r_return: float
    mfe_before_entry: float
    mfe_after_entry: float
    mae_after_entry: float
    total_mfe_from_detection: float
    mfe_consumed_pct: float | None
    expected_liq_notional: float
    opposite_liq_notional: float
    expected_baseline: float
    opposite_baseline: float
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
        "force_orders": {"symbol", "event_time", "side", "qty", "price"},
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
            "price_action": "candles",
            "liquidations": "force_orders",
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
    return {
        "rows": len(candles),
        "start_time_utc": iso(candles[0].open_time) if candles else None,
        "end_time_utc": iso(candles[-1].open_time) if candles else None,
        "duplicate_timestamps": duplicate_timestamps,
        "non_monotonic_timestamps": non_monotonic,
        "ohlc_violations": ohlc_violations,
        "missing_bar_gaps": missing_gaps,
        "inferred_step_seconds": step_seconds,
    }


def load_force_buckets(
    conn: sqlite3.Connection,
    candles: list[Candle],
    config: DiagnosticConfig,
) -> tuple[list[ForceBucket], dict[str, Any]]:
    buckets = [ForceBucket() for _ in candles]
    if not candles:
        return buckets, {"rows": 0, "mapped_rows": 0}

    starts = [c.open_time for c in candles]
    rows = conn.execute(
        """
        SELECT event_time, side, qty, price
        FROM force_orders
        WHERE symbol = ?
        ORDER BY event_time ASC
        """,
        (config.symbol,),
    ).fetchall()

    mutable = [
        {
            "buy_notional": 0.0,
            "sell_notional": 0.0,
            "buy_count": 0,
            "sell_count": 0,
        }
        for _ in candles
    ]
    mapped = 0
    min_ts: datetime | None = None
    max_ts: datetime | None = None
    for raw_time, side, qty, price in rows:
        event_time = parse_ts(raw_time)
        min_ts = event_time if min_ts is None else min(min_ts, event_time)
        max_ts = event_time if max_ts is None else max(max_ts, event_time)
        idx = bisect_right(starts, event_time) - 1
        if idx < 0 or idx >= len(candles):
            continue
        notional = float(qty) * float(price)
        if side == "BUY":
            mutable[idx]["buy_notional"] += notional
            mutable[idx]["buy_count"] += 1
        elif side == "SELL":
            mutable[idx]["sell_notional"] += notional
            mutable[idx]["sell_count"] += 1
        mapped += 1

    buckets = [ForceBucket(**row) for row in mutable]
    return buckets, {
        "rows": len(rows),
        "mapped_rows": mapped,
        "start_time_utc": iso(min_ts) if min_ts else None,
        "end_time_utc": iso(max_ts) if max_ts else None,
        "buy_rows": sum(b.buy_count for b in buckets),
        "sell_rows": sum(b.sell_count for b in buckets),
        "buy_notional": sum(b.buy_notional for b in buckets),
        "sell_notional": sum(b.sell_notional for b in buckets),
    }


def compute_atr_series(candles: list[Candle], period: int) -> list[float | None]:
    true_ranges: list[float] = []
    atr: list[float | None] = [None] * len(candles)
    for idx, candle in enumerate(candles):
        if idx == 0:
            true_ranges.append(candle.high - candle.low)
        else:
            prev_close = candles[idx - 1].close
            true_ranges.append(
                max(
                    candle.high - candle.low,
                    abs(candle.high - prev_close),
                    abs(candle.low - prev_close),
                )
            )
        if idx + 1 >= period:
            atr[idx] = mean(true_ranges[idx + 1 - period : idx + 1])
    return atr


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
    current = [sorted_levels[0]]
    for item in sorted_levels[1:]:
        if abs(item[1] - current[-1][1]) <= tolerance:
            current.append(item)
        else:
            clusters.append(current)
            current = [item]
    clusters.append(current)

    merged: list[float] = []
    for cluster in clusters:
        if len(cluster) < min_hits:
            continue
        indices = [idx for idx, _ in cluster]
        if max(indices) - min(indices) < min_age_bars:
            continue
        merged.append(mean([price for _, price in cluster]))
    return merged


def detect_sweep_events(
    candles: list[Candle],
    atr: list[float | None],
    config: DiagnosticConfig,
) -> list[SweepEvent]:
    events: list[SweepEvent] = []
    start = max(config.equal_level_lookback, config.atr_period)
    for idx in range(start, len(candles)):
        atr_value = atr[idx]
        if atr_value is None or atr_value <= 0:
            continue
        candle = candles[idx]
        recent = candles[idx - config.equal_level_lookback : idx]
        lows = [(offset, item.low) for offset, item in enumerate(recent)]
        highs = [(offset, item.high) for offset, item in enumerate(recent)]
        tolerance = atr_value * config.equal_level_tol_atr
        sweep_buffer = atr_value * config.sweep_buf_atr
        proximity = atr_value * config.sweep_proximity_atr

        low_event: SweepEvent | None = None
        for level in detect_equal_levels(lows, tolerance, config.min_hits, config.min_age_bars):
            if abs(candle.open - level) > proximity:
                continue
            if candle.low < level - sweep_buffer:
                low_event = SweepEvent(idx, "LONG", "LOW", level, atr_value)
                break
        if low_event is not None:
            events.append(low_event)
            continue

        for level in detect_equal_levels(highs, tolerance, config.min_hits, config.min_age_bars):
            if abs(candle.open - level) > proximity:
                continue
            if candle.high > level + sweep_buffer:
                events.append(SweepEvent(idx, "SHORT", "HIGH", level, atr_value))
                break
    return events


def side_notional(bucket: ForceBucket, side: str) -> float:
    return bucket.buy_notional if side == "BUY" else bucket.sell_notional


def rolling_mean_side(
    buckets: list[ForceBucket],
    *,
    side: str,
    end_exclusive: int,
    lookback: int,
) -> float | None:
    start = max(0, end_exclusive - lookback)
    values = [side_notional(bucket, side) for bucket in buckets[start:end_exclusive]]
    if len(values) < max(10, lookback // 4):
        return None
    return mean(values)


def window_notional(buckets: list[ForceBucket], start: int, length: int, side: str) -> float:
    end = min(len(buckets), start + length)
    return sum(side_notional(bucket, side) for bucket in buckets[start:end])


def expected_side_for_direction(direction: str) -> str:
    return "SELL" if direction == "LONG" else "BUY"


def opposite_side(side: str) -> str:
    return "BUY" if side == "SELL" else "SELL"


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


def build_event(
    *,
    cohort: str,
    candles: list[Candle],
    detection_bar: int,
    direction: str,
    sweep_side: str | None,
    entry_delay_bars: int,
    expected_liq_notional: float,
    opposite_liq_notional: float,
    expected_baseline: float,
    opposite_baseline: float,
    config: DiagnosticConfig,
    metadata: dict[str, Any] | None = None,
) -> CohortEvent | None:
    state_known_bar = detection_bar + config.burst_window_bars - 1
    entry_bar = detection_bar + entry_delay_bars
    exit_bar = entry_bar + config.outcome_horizon_bars - 1
    if exit_bar >= len(candles) or state_known_bar >= len(candles):
        return None

    detection_price = candles[detection_bar].close
    entry_price = candles[entry_bar].close
    exit_price = candles[exit_bar].close
    if direction == "LONG":
        gross = (exit_price - entry_price) / entry_price
    else:
        gross = (entry_price - exit_price) / entry_price
    net = gross - config.round_trip_cost_pct
    r_return = net / config.fixed_risk_pct if config.fixed_risk_pct else net

    before_end = entry_bar - 1
    mfe_before = favorable_move(candles, detection_bar, before_end, detection_price, direction)
    mfe_after = favorable_move(candles, entry_bar, exit_bar, entry_price, direction)
    mae_after = adverse_move(candles, entry_bar, exit_bar, entry_price, direction)
    total_mfe = favorable_move(candles, detection_bar, exit_bar, detection_price, direction)
    consumed = None if total_mfe <= 0 else min(max(mfe_before / total_mfe, 0.0), 1.0)

    return CohortEvent(
        cohort=cohort,
        detection_bar=detection_bar,
        state_known_bar=state_known_bar,
        confirmation_bar=state_known_bar,
        entry_candidate_bar=entry_bar,
        label_available_bar=entry_bar,
        return_start_bar=entry_bar,
        direction=direction,
        sweep_side=sweep_side,
        detection_time_utc=iso(candles[detection_bar].open_time),
        state_known_time_utc=iso(candles[state_known_bar].open_time),
        entry_time_utc=iso(candles[entry_bar].open_time),
        entry_price=entry_price,
        exit_bar=exit_bar,
        exit_price=exit_price,
        gross_return_pct=gross,
        net_return_pct=net,
        r_return=r_return,
        mfe_before_entry=mfe_before,
        mfe_after_entry=mfe_after,
        mae_after_entry=mae_after,
        total_mfe_from_detection=total_mfe,
        mfe_consumed_pct=consumed,
        expected_liq_notional=expected_liq_notional,
        opposite_liq_notional=opposite_liq_notional,
        expected_baseline=expected_baseline,
        opposite_baseline=opposite_baseline,
        metadata=metadata or {},
    )


def build_sweep_cohorts(
    candles: list[Candle],
    sweeps: list[SweepEvent],
    buckets: list[ForceBucket],
    config: DiagnosticConfig,
) -> dict[str, list[CohortEvent]]:
    cohorts = {
        "main_liquidation_burst_reversal": [],
        "control_non_liquidation_sweeps": [],
        "control_opposite_side_liquidations": [],
        "control_shifted_entry": [],
    }
    for sweep in sweeps:
        expected_side = expected_side_for_direction(sweep.direction)
        wrong_side = opposite_side(expected_side)
        expected_baseline = rolling_mean_side(
            buckets,
            side=expected_side,
            end_exclusive=sweep.detection_bar,
            lookback=config.baseline_lookback_bars,
        )
        wrong_baseline = rolling_mean_side(
            buckets,
            side=wrong_side,
            end_exclusive=sweep.detection_bar,
            lookback=config.baseline_lookback_bars,
        )
        if expected_baseline is None or wrong_baseline is None:
            continue
        expected_notional = window_notional(
            buckets,
            sweep.detection_bar,
            config.burst_window_bars,
            expected_side,
        )
        wrong_notional = window_notional(
            buckets,
            sweep.detection_bar,
            config.burst_window_bars,
            wrong_side,
        )
        expected_burst = expected_baseline > 0 and expected_notional > (
            config.liquidation_burst_multiple * expected_baseline
        )
        wrong_burst = wrong_baseline > 0 and wrong_notional > (
            config.liquidation_burst_multiple * wrong_baseline
        )
        metadata = {
            "expected_liquidation_side": expected_side,
            "opposite_liquidation_side": wrong_side,
            "sweep_level": sweep.level,
            "atr": sweep.atr,
        }
        if expected_burst:
            event = build_event(
                cohort="main_liquidation_burst_reversal",
                candles=candles,
                detection_bar=sweep.detection_bar,
                direction=sweep.direction,
                sweep_side=sweep.sweep_side,
                entry_delay_bars=config.entry_delay_bars,
                expected_liq_notional=expected_notional,
                opposite_liq_notional=wrong_notional,
                expected_baseline=expected_baseline,
                opposite_baseline=wrong_baseline,
                config=config,
                metadata=metadata,
            )
            if event:
                cohorts["main_liquidation_burst_reversal"].append(event)
                shifted = build_event(
                    cohort="control_shifted_entry",
                    candles=candles,
                    detection_bar=sweep.detection_bar,
                    direction=sweep.direction,
                    sweep_side=sweep.sweep_side,
                    entry_delay_bars=config.shifted_entry_delay_bars,
                    expected_liq_notional=expected_notional,
                    opposite_liq_notional=wrong_notional,
                    expected_baseline=expected_baseline,
                    opposite_baseline=wrong_baseline,
                    config=config,
                    metadata={**metadata, "control": "same signal delayed to bar i+5"},
                )
                if shifted:
                    cohorts["control_shifted_entry"].append(shifted)
        elif expected_baseline > 0 and expected_notional < (
            config.non_liquidation_multiple * expected_baseline
        ):
            event = build_event(
                cohort="control_non_liquidation_sweeps",
                candles=candles,
                detection_bar=sweep.detection_bar,
                direction=sweep.direction,
                sweep_side=sweep.sweep_side,
                entry_delay_bars=config.entry_delay_bars,
                expected_liq_notional=expected_notional,
                opposite_liq_notional=wrong_notional,
                expected_baseline=expected_baseline,
                opposite_baseline=wrong_baseline,
                config=config,
                metadata={**metadata, "control": "sweep without expected-side liquidation burst"},
            )
            if event:
                cohorts["control_non_liquidation_sweeps"].append(event)

        if wrong_burst and not expected_burst:
            event = build_event(
                cohort="control_opposite_side_liquidations",
                candles=candles,
                detection_bar=sweep.detection_bar,
                direction=sweep.direction,
                sweep_side=sweep.sweep_side,
                entry_delay_bars=config.entry_delay_bars,
                expected_liq_notional=expected_notional,
                opposite_liq_notional=wrong_notional,
                expected_baseline=expected_baseline,
                opposite_baseline=wrong_baseline,
                config=config,
                metadata={**metadata, "control": "wrong-side liquidation burst"},
            )
            if event:
                cohorts["control_opposite_side_liquidations"].append(event)
    return cohorts


def build_flow_only_control(
    candles: list[Candle],
    buckets: list[ForceBucket],
    config: DiagnosticConfig,
) -> list[CohortEvent]:
    events: list[CohortEvent] = []
    start = config.baseline_lookback_bars
    max_start = len(candles) - config.entry_delay_bars - config.outcome_horizon_bars
    for idx in range(start, max_start):
        for side, direction in (("SELL", "LONG"), ("BUY", "SHORT")):
            baseline = rolling_mean_side(
                buckets,
                side=side,
                end_exclusive=idx,
                lookback=config.baseline_lookback_bars,
            )
            if baseline is None or baseline <= 0:
                continue
            notional = window_notional(buckets, idx, config.burst_window_bars, side)
            if notional <= config.liquidation_burst_multiple * baseline:
                continue
            other_side = opposite_side(side)
            other_baseline = rolling_mean_side(
                buckets,
                side=other_side,
                end_exclusive=idx,
                lookback=config.baseline_lookback_bars,
            )
            other_notional = window_notional(buckets, idx, config.burst_window_bars, other_side)
            event = build_event(
                cohort="control_flow_only_ablation",
                candles=candles,
                detection_bar=idx,
                direction=direction,
                sweep_side=None,
                entry_delay_bars=config.entry_delay_bars,
                expected_liq_notional=notional,
                opposite_liq_notional=other_notional,
                expected_baseline=baseline,
                opposite_baseline=other_baseline or 0.0,
                config=config,
                metadata={
                    "liquidation_side": side,
                    "control": "liquidation burst without sweep requirement",
                },
            )
            if event:
                events.append(event)
    return events


def profit_factor(values: list[float]) -> float:
    wins = sum(v for v in values if v > 0)
    losses = abs(sum(v for v in values if v < 0))
    if losses == 0:
        return float("inf") if wins > 0 else 0.0
    return wins / losses


def metric_summary(events: list[CohortEvent]) -> dict[str, Any]:
    returns = [event.r_return for event in events]
    net = [event.net_return_pct for event in events]
    consumed = [event.mfe_consumed_pct for event in events if event.mfe_consumed_pct is not None]
    folds = fold_metrics(events)
    return {
        "count": len(events),
        "er": mean(returns) if returns else 0.0,
        "median_r": median(returns) if returns else 0.0,
        "median_net_return_pct": median(net) if net else 0.0,
        "win_rate": (sum(1 for value in returns if value > 0) / len(returns)) if returns else 0.0,
        "profit_factor": profit_factor(returns),
        "median_mfe_consumed_pct": median(consumed) if consumed else None,
        "median_mfe_before_entry": median([event.mfe_before_entry for event in events]) if events else 0.0,
        "median_mfe_after_entry": median([event.mfe_after_entry for event in events]) if events else 0.0,
        "median_mae_after_entry": median([event.mae_after_entry for event in events]) if events else 0.0,
        "positive_folds": sum(1 for item in folds if item["er"] > 0),
        "folds": folds,
    }


def fold_metrics(events: list[CohortEvent], folds: int = 4) -> list[dict[str, Any]]:
    if not events:
        return []
    ordered = sorted(events, key=lambda event: event.detection_time_utc)
    result: list[dict[str, Any]] = []
    for fold in range(folds):
        start = (len(ordered) * fold) // folds
        end = (len(ordered) * (fold + 1)) // folds
        subset = ordered[start:end]
        returns = [event.r_return for event in subset]
        result.append(
            {
                "fold": fold + 1,
                "count": len(subset),
                "start_time_utc": subset[0].detection_time_utc if subset else None,
                "end_time_utc": subset[-1].detection_time_utc if subset else None,
                "er": mean(returns) if returns else 0.0,
                "median_r": median(returns) if returns else 0.0,
                "win_rate": (sum(1 for value in returns if value > 0) / len(returns)) if returns else 0.0,
            }
        )
    return result


def apply_gates(cohort_metrics: dict[str, dict[str, Any]]) -> dict[str, Any]:
    main = cohort_metrics["main_liquidation_burst_reversal"]
    controls = {
        name: metrics
        for name, metrics in cohort_metrics.items()
        if name != "main_liquidation_burst_reversal"
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
    if main["er"] < 0.5:
        stop_reasons.append("post_entry_er_lt_0_5")
    if control_outperformers:
        stop_reasons.append("control_cohort_outperforms_main")

    explore = (
        main["er"] > 1.2
        and consumed is not None
        and consumed < 0.60
        and not control_outperformers
        and main["count"] >= 100
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
                "median_mfe_consumed_pct > 70%",
                "post_entry_er < 0.5",
                "any control cohort outperforms main cohort on ER",
            ],
            "EXPLORE": [
                "post_entry_er > 1.2",
                "median_mfe_consumed_pct < 60%",
                "main cohort outperforms all controls on ER",
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
            conn = sqlite3.connect(f"file:{store}?mode=ro", uri=True)
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
                    conn.close()
                    return benchmark
            conn.close()
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
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    schema = inspect_schema(conn)
    if schema["missing_required"]:
        raise RuntimeError(f"Required schema missing: {schema['missing_required']}")

    candles = load_candles(conn, config)
    candle_quality = data_quality(candles)
    buckets, force_quality = load_force_buckets(conn, candles, config)
    atr = compute_atr_series(candles, config.atr_period)
    sweeps = detect_sweep_events(candles, atr, config)
    cohorts = build_sweep_cohorts(candles, sweeps, buckets, config)
    cohorts["control_flow_only_ablation"] = build_flow_only_control(candles, buckets, config)
    metrics = {name: metric_summary(events) for name, events in cohorts.items()}
    gates = apply_gates(metrics)
    benchmark = load_trial_00095_benchmark()
    benchmark["trade_log_overlap"] = event_overlap_with_trade_log(
        conn,
        cohorts["main_liquidation_burst_reversal"],
    )
    conn.close()

    payload = {
        "manifest": {
            "diagnostic": "LIQUIDATION_BURST_REVERSAL_ENTRY_FEASIBILITY_V1",
            "research_only": True,
            "production_changes": False,
            "db_path": str(db_path),
            "report_path": str(report_path),
            "json_path": str(json_path),
            "generated_at_utc": iso(datetime.now(timezone.utc)),
        },
        "config": asdict(config),
        "schema": schema,
        "data_quality": {
            "candles": candle_quality,
            "force_orders": force_quality,
        },
        "timing_model": {
            "detection_bar": "i",
            "state_known_bar": "i+2",
            "confirmation_bar": "i+2",
            "entry_candidate_bar": "i+3",
            "label_available_bar": "i+3",
            "return_start_bar": "i+3",
            "primary_returns_from_detection_bar": False,
        },
        "sweep_events_total": len(sweeps),
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
    main = metrics["main_liquidation_burst_reversal"]
    lines = [
        "# LIQUIDATION_BURST_REVERSAL_ENTRY_FEASIBILITY_V1",
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
        f"- Main median MFE consumed before entry: `{fmt_float(main['median_mfe_consumed_pct'])}`",
        f"- STOP reasons: `{', '.join(payload['invalidation_gates']['stop_reasons']) or 'none'}`",
        "",
        "## Mechanism",
        "",
        "- Detect an equal-level sweep at bar `i` using completed 15m candles only.",
        "- Sum expected-side force-order notional across bars `i` through `i+2`.",
        "- Compare that notional to a pre-sweep rolling baseline ending at `i-1`.",
        "- Enter at bar `i+3`; primary returns start at `i+3`.",
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
        f"- Force orders: `{payload['data_quality']['force_orders']}`",
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
            "Primary returns are measured from `entry_candidate_bar`, not `detection_bar`. Detection-bar movement is used only for MFE-before-entry accessibility.",
            "",
            "## Cohort Metrics",
            "",
            "| Cohort | Count | ER | Median R | PF | Win Rate | Median MFE Consumed | Positive Folds |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for name, row in metrics.items():
        lines.append(
            f"| `{name}` | {row['count']} | {fmt_float(row['er'])} | {fmt_float(row['median_r'])} | "
            f"{fmt_float(row['profit_factor'])} | {fmt_float(row['win_rate'])} | "
            f"{fmt_float(row['median_mfe_consumed_pct'])} | {row['positive_folds']} |"
        )
    lines.extend(
        [
            "",
            "## MFE Accessibility",
            "",
            f"- Main median MFE before entry: `{fmt_float(main['median_mfe_before_entry'])}`",
            f"- Main median MFE after entry: `{fmt_float(main['median_mfe_after_entry'])}`",
            f"- Main median MAE after entry: `{fmt_float(main['median_mae_after_entry'])}`",
            f"- 70% consumed threshold breached: `{main['median_mfe_consumed_pct'] is not None and main['median_mfe_consumed_pct'] > 0.70}`",
            "",
            "## Control Cohorts",
            "",
            "- Non-liquidation sweeps: sweep detected, expected-side liquidation below 0.5x baseline.",
            "- Opposite-side liquidations: sweep detected, wrong-side liquidation burst.",
            "- Shifted-entry: same main signal, but entry delayed from `i+3` to `i+5`.",
            "- Flow-only ablation: liquidation burst without sweep requirement.",
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
            "The inspected market database does not contain `trial_trades`; exact trade-overlap analysis is therefore schema-blocked for this artifact. The report uses the approved trial-00095 reference metrics and documents any available store-level trial metrics separately.",
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
