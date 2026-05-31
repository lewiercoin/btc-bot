from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from research_lab.diagnostics.oanda_xauusd_sweep_reclaim_transfer_feasibility_v1 import (
    Candle,
    DiagnosticConfig,
    build_cohorts,
    build_event,
    cohort_metrics,
    detect_sweep_state,
    evaluate_gates,
    fold_metrics,
)


def _ts(index: int) -> datetime:
    return datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(hours=index)


def _config() -> DiagnosticConfig:
    return DiagnosticConfig(
        equal_level_lookback=8,
        atr_period=3,
        equal_level_tol_atr=0.05,
        sweep_buf_atr=0.10,
        sweep_proximity_atr=5.0,
        reclaim_buf_atr=0.02,
        wick_min_atr=0.0,
        level_min_age_bars=2,
        min_hits=3,
        min_sweep_depth_pct=0.00649,
        shallow_min_depth_pct=0.001,
        primary_horizon_bars=5,
        secondary_horizon_bars=10,
        random_offset_bars=13,
        max_serialized_events_per_cohort=50,
    )


def _candle(
    index: int,
    open_: float = 100.0,
    high: float = 101.0,
    low: float = 99.0,
    close: float = 100.0,
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


def _base_candles(count: int = 80) -> list[Candle]:
    candles = [_candle(index) for index in range(count)]
    for idx in (10, 13, 16, 18):
        candles[idx] = _candle(idx, open_=100.0, high=101.0, low=100.0, close=100.4)
    return candles


def test_equal_levels_are_built_from_prior_bars_only() -> None:
    config = _config()
    candles = _base_candles()
    # Current bar contains a future-looking low cluster value, but prior bars
    # already contain the valid equal low level at 100.0. Detection must use
    # prior levels, not this current-bar low as a new level.
    candles[20] = _candle(20, open_=100.05, high=101.0, low=98.9, close=100.2)

    state = detect_sweep_state(candles, 20, config, [0.02] * 40)

    assert state is not None
    assert state.level == 100.0
    assert state.detection_bar == 20
    assert state.reclaimed is True
    assert state.sweep_depth_pct > config.min_sweep_depth_pct


def test_build_event_enforces_entry_candidate_and_return_start() -> None:
    config = _config()
    candles = _base_candles()
    candles[20] = _candle(20, open_=100.05, high=101.0, low=98.9, close=100.2)
    candles[21] = _candle(21, open_=100.2, high=101.0, low=100.0, close=100.5)
    candles[26] = _candle(26, open_=102.0, high=103.0, low=101.5, close=102.5)
    state = detect_sweep_state(candles, 20, config, [0.02] * 40)
    assert state is not None

    event = build_event("main_sweep_reclaim", candles, state, config, entry_delay_bars=1)

    assert event is not None
    assert event.level_known_bar == 19
    assert event.detection_bar == 20
    assert event.state_known_bar == 20
    assert event.entry_candidate_bar == 21
    assert event.return_start_bar == 21
    assert event.label_available_bar == 26
    detection_return = (candles[26].close - candles[20].close) / candles[20].close
    assert event.net_return_pct != detection_return


def test_mfe_accessibility_before_and_after_entry() -> None:
    config = _config()
    candles = _base_candles()
    candles[20] = _candle(20, open_=100.05, high=101.2, low=98.9, close=100.2)
    candles[21] = _candle(21, open_=100.2, high=101.0, low=99.8, close=100.4)
    candles[22] = _candle(22, open_=100.4, high=103.2, low=100.1, close=102.8)
    state = detect_sweep_state(candles, 20, config, [0.02] * 40)
    assert state is not None

    event = build_event("main_sweep_reclaim", candles, state, config, entry_delay_bars=1)

    assert event is not None
    assert round(event.mfe_before_entry, 6) == 1.0
    assert round(event.mfe_after_entry, 6) == 3.0
    assert round(event.total_mfe, 6) == 4.0
    assert event.mfe_consumed_pct == 0.25


def test_build_cohorts_includes_predefined_controls() -> None:
    config = _config()
    candles = _base_candles(120)
    candles[20] = _candle(20, open_=100.05, high=101.0, low=98.9, close=100.2)
    candles[30] = _candle(30, open_=100.05, high=101.0, low=98.9, close=99.0)
    candles[40] = _candle(40, open_=99.05, high=100.0, low=98.7, close=99.3)
    for idx in (50, 53, 56):
        candles[idx] = _candle(idx, open_=100.0, high=106.0, low=94.0, close=100.0)
    candles[60] = _candle(60, open_=100.05, high=101.0, low=98.9, close=100.2)

    cohorts = build_cohorts(candles, config)

    assert cohorts["main_sweep_reclaim"]
    assert cohorts["control_opposite_direction"]
    assert cohorts["control_shifted_entry_plus2"]
    assert cohorts["control_shifted_entry_plus3"]
    assert cohorts["control_random_offset_137"]
    assert cohorts["control_sweep_without_reclaim"]
    assert cohorts["control_shallow_sweep"]


def test_gate_logic_stops_when_sample_too_small() -> None:
    config = _config()
    candles = _base_candles()
    candles[20] = _candle(20, open_=100.05, high=101.0, low=98.9, close=100.2)
    state = detect_sweep_state(candles, 20, config, [0.02] * 40)
    assert state is not None
    event = build_event("main_sweep_reclaim", candles, state, config, entry_delay_bars=1)
    assert event is not None

    cohort_results = {
        "main_sweep_reclaim": cohort_metrics([event]),
        "control_sweep_without_reclaim": cohort_metrics([]),
    }
    gates = evaluate_gates(cohort_results, fold_metrics([event]))

    assert gates["recommendation"] == "STOP"
    assert any(reason.startswith("sample_size_lt_100") for reason in gates["stop_reasons"])
