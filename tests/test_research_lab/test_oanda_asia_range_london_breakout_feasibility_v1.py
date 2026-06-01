from __future__ import annotations

import sys
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from research_lab.diagnostics.oanda_asia_range_london_breakout_feasibility_v1 import (
    CONTROL_COHORTS,
    PRIMARY_COHORT,
    Candle,
    DiagnosticConfig,
    build_asia_ranges,
    build_cohorts,
    build_event,
    build_main_signals,
    cohort_metrics,
    compute_atr,
    evaluate_gates,
    fold_metrics,
)


def _ts(index: int) -> datetime:
    return datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=15 * index)


def _candle(
    index: int,
    open_: float = 1.1000,
    high: float = 1.1010,
    low: float = 1.0990,
    close: float = 1.1000,
    volume: float = 100.0,
) -> Candle:
    return Candle(
        index=index,
        time=_ts(index),
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=volume,
    )


def _day_with_breakout(start_index: int = 96, close: float = 1.1020) -> list[Candle]:
    candles: list[Candle] = []
    for offset in range(96):
        index = start_index + offset
        hour = _ts(index).hour
        if 0 <= hour < 7:
            candles.append(_candle(index, open_=1.1000, high=1.1010, low=1.0990, close=1.1000))
        elif hour == 7 and _ts(index).minute == 0:
            candles.append(_candle(index, open_=1.1002, high=1.1025, low=1.1000, close=close))
        elif hour == 7 and _ts(index).minute == 15:
            candles.append(_candle(index, open_=1.1020, high=1.1040, low=1.1015, close=1.1035))
        else:
            candles.append(_candle(index, open_=1.1000, high=1.1010, low=1.0990, close=1.1000))
    return candles


def _candles_with_history(days: int = 8) -> list[Candle]:
    candles: list[Candle] = []
    for day in range(days):
        start = day * 96
        if day == 2:
            candles.extend(_day_with_breakout(start))
        else:
            candles.extend(
                _candle(start + offset, open_=1.1000, high=1.1010, low=1.0990, close=1.1000)
                for offset in range(96)
            )
    return [
        Candle(index=index, time=candle.time, open=candle.open, high=candle.high, low=candle.low, close=candle.close, volume=candle.volume)
        for index, candle in enumerate(candles)
    ]


def _reindex(candles: list[Candle]) -> list[Candle]:
    return [
        Candle(index=index, time=candle.time, open=candle.open, high=candle.high, low=candle.low, close=candle.close, volume=candle.volume)
        for index, candle in enumerate(candles)
    ]


def _config() -> DiagnosticConfig:
    return DiagnosticConfig(
        atr_period=3,
        primary_horizon_bars=5,
        secondary_horizon_bars=8,
        tertiary_horizon_bars=10,
        random_offset_bars=13,
        weekday_shuffle_offset_bars=96,
    )


def test_atr_uses_simple_true_range_average() -> None:
    candles = [
        _candle(0, open_=10, high=11, low=9, close=10),
        _candle(1, open_=10, high=13, low=9, close=12),
        _candle(2, open_=12, high=14, low=11, close=13),
        _candle(3, open_=13, high=15, low=12, close=14),
    ]

    assert compute_atr(candles, 3, 3) == 10.0 / 3.0


def test_complete_asia_range_required() -> None:
    config = _config()
    candles = _candles_with_history(3)
    candles = _reindex([candle for candle in candles if not (candle.time.date().isoformat() == "2024-01-02" and candle.time.hour == 0 and candle.time.minute == 0)])
    ranges, valid_days, meta = build_asia_ranges(candles, config)

    assert ranges
    assert valid_days
    assert meta["skipped_incomplete_asia_sessions"] == 1
    assert all(ref.end_index + 1 == next(c.index for c in valid_days[date] if c.time.hour == 7 and c.time.minute == 0) for date, ref in ranges.items())


def test_main_signal_and_event_enforce_i_plus_1_timing() -> None:
    config = _config()
    candles = _candles_with_history(5)
    ranges, valid_days, _ = build_asia_ranges(candles, config)
    signals = build_main_signals(candles, config, ranges, valid_days)

    assert len(signals) == 1
    signal = signals[0]
    event = build_event(PRIMARY_COHORT, candles, signal, config)

    assert event is not None
    assert event.state_known_bar == event.detection_bar
    assert event.confirmation_bar == event.detection_bar
    assert event.entry_candidate_bar == event.detection_bar + 1
    assert event.return_start_bar == event.entry_candidate_bar
    assert event.label_available_bar == event.entry_candidate_bar + config.primary_horizon_bars
    detection_return = (candles[event.label_available_bar].close - candles[event.detection_bar].close) / candles[event.detection_bar].close
    assert event.net_return_pct != detection_return


def test_mfe_accessibility_before_and_after_entry() -> None:
    config = _config()
    candles = _candles_with_history(5)
    ranges, valid_days, _ = build_asia_ranges(candles, config)
    signal = build_main_signals(candles, config, ranges, valid_days)[0]
    event = build_event(PRIMARY_COHORT, candles, signal, config)

    assert event is not None
    assert event.mfe_before_entry > 0
    assert event.mfe_after_entry > 0
    assert event.total_mfe == event.mfe_before_entry + event.mfe_after_entry
    assert 0 <= event.mfe_consumed_pct <= 1


def test_build_cohorts_includes_all_predefined_controls() -> None:
    config = _config()
    candles = _candles_with_history(8)
    cohorts, _ = build_cohorts(candles, config)

    assert PRIMARY_COHORT in cohorts
    for name in CONTROL_COHORTS:
        assert name in cohorts


def test_gate_logic_stops_when_sample_too_small() -> None:
    config = _config()
    candles = _candles_with_history(5)
    ranges, valid_days, _ = build_asia_ranges(candles, config)
    signal = build_main_signals(candles, config, ranges, valid_days)[0]
    event = build_event(PRIMARY_COHORT, candles, signal, config)
    assert event is not None

    cohort_results = {PRIMARY_COHORT: cohort_metrics([event])}
    for name in CONTROL_COHORTS:
        cohort_results[name] = cohort_metrics([])
    gates = evaluate_gates(cohort_results, fold_metrics([event]))

    assert gates["recommendation"] == "STOP"
    assert any(reason.startswith("sample_size_lt_100") for reason in gates["stop_reasons"])
