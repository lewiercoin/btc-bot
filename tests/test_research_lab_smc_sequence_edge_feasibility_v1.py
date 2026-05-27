from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

from research_lab.analysis_smc_sequence_edge_feasibility_v1 import (
    Candle,
    DiagnosticConfig,
    build_sequence_events,
    compute_atr_series,
    detect_sweep_events,
    fvg_at,
    is_displacement,
    last_confirmed_swing_arrays,
    run_analysis,
)


def _candle(
    idx: int,
    *,
    open_: float,
    high: float,
    low: float,
    close: float,
) -> Candle:
    return Candle(
        index=idx,
        open_time=datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=15 * idx),
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=1.0,
    )


def _config() -> DiagnosticConfig:
    return DiagnosticConfig(
        symbol="BTCUSDT",
        timeframe="15m",
        atr_period=2,
        equal_level_lookback=6,
        equal_level_tol_atr=0.10,
        min_hits=3,
        min_age_bars=4,
        sweep_buf_atr=0.05,
        sweep_proximity_atr=10.0,
        duplicate_level_tolerance_pct=0.01,
        duplicate_level_window_bars=20,
        swing_left=1,
        swing_right=1,
        displacement_body_atr=0.20,
        displacement_range_atr=0.50,
        displacement_close_percentile=0.60,
        displacement_window_bars=3,
        structure_window_bars=4,
        fvg_min_atr=0.01,
        fvg_window_bars=4,
        mitigation_window_bars=4,
        forward_windows=(1, 2),
        deterministic_control_shift_bars=3,
    )


def _sequence_candles() -> list[Candle]:
    return [
        _candle(0, open_=100, high=101, low=99, close=100),
        _candle(1, open_=100, high=102, low=99.5, close=101),
        _candle(2, open_=101, high=103, low=99, close=102),
        _candle(3, open_=102, high=105, low=100, close=104),
        _candle(4, open_=104, high=104, low=99, close=101),
        _candle(5, open_=101, high=102, low=100, close=100.5),
        _candle(6, open_=100, high=100, low=97.5, close=99.5),
        _candle(7, open_=100, high=108, low=100, close=107),
        _candle(8, open_=106, high=109, low=101, close=108),
        _candle(9, open_=107, high=108, low=100.5, close=106),
        _candle(10, open_=106.5, high=110, low=106, close=109),
        _candle(11, open_=109, high=111, low=108, close=110),
        _candle(12, open_=110, high=112, low=109, close=111),
    ]


def test_fvg_detection_is_known_on_third_candle_close() -> None:
    candles = [
        _candle(0, open_=100, high=100, low=98, close=99),
        _candle(1, open_=100, high=103, low=99, close=102),
        _candle(2, open_=103, high=105, low=101, close=104),
    ]
    atr = [2.0, 3.0, 4.0]

    assert fvg_at(candles, atr, 1, config=_config()) is None
    zone = fvg_at(candles, atr, 2, config=_config())

    assert zone is not None
    assert zone.side == "BULLISH"
    assert zone.created_bar == 2
    assert zone.zone_low == 100
    assert zone.zone_high == 101


def test_displacement_requires_direction_body_range_and_close_location() -> None:
    config = _config()
    bullish = _candle(0, open_=100, high=108, low=99, close=107)
    weak = _candle(1, open_=100, high=102, low=99, close=100.5)
    bearish = _candle(2, open_=107, high=108, low=99, close=100)

    assert is_displacement(bullish, 10.0, direction="LONG", config=config) is True
    assert is_displacement(weak, 10.0, direction="LONG", config=config) is False
    assert is_displacement(bearish, 10.0, direction="SHORT", config=config) is True
    assert is_displacement(bearish, 10.0, direction="LONG", config=config) is False


def test_swing_not_available_before_right_side_confirmation() -> None:
    candles = _sequence_candles()
    high_arr, _ = last_confirmed_swing_arrays(candles, _config())

    assert high_arr[3] is None
    assert high_arr[4] == 105
    assert high_arr[6] == 105


def test_full_sequence_timing_uses_entry_candidate_after_mitigation() -> None:
    candles = _sequence_candles()
    config = _config()
    atr = compute_atr_series(candles, config.atr_period)
    sweeps = detect_sweep_events(candles, atr, config)
    events = build_sequence_events(candles, sweeps, atr, {}, config)

    assert len(events) == 1
    event = events[0]
    assert event.detection_bar == 6
    assert event.displacement_bar == 7
    assert event.structure_shift_bar == 7
    assert event.fvg_created_bar == 8
    assert event.mitigation_bar == 9
    assert event.entry_candidate_bar == 10
    assert event.label_available_bar == 10
    assert event.return_start_bar_detection == 6
    assert event.return_start_bar_entry_candidate == 10
    assert event.forward_detection["return_1"] != event.forward_entry_candidate["return_1"]


def test_duplicate_sweep_inflation_is_prevented_by_retired_level_window() -> None:
    candles = _sequence_candles() + [
        _candle(13, open_=100, high=101, low=97, close=99),
        _candle(14, open_=100, high=101, low=96, close=99),
    ]
    config = _config()
    atr = compute_atr_series(candles, config.atr_period)
    sweeps = detect_sweep_events(candles, atr, config)

    low_sweeps = [sweep for sweep in sweeps if sweep.sweep_side == "LOW"]
    assert len(low_sweeps) == 1
    assert low_sweeps[0].detection_bar == 6


def test_synthetic_sqlite_integration(tmp_path) -> None:
    db_path = tmp_path / "synthetic_smc.db"
    output_path = tmp_path / "out.json"
    report_path = tmp_path / "report.md"
    candles = _sequence_candles()
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE candles (
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                open_time TEXT NOT NULL,
                open REAL NOT NULL,
                high REAL NOT NULL,
                low REAL NOT NULL,
                close REAL NOT NULL,
                volume REAL NOT NULL
            )
            """
        )
        conn.executemany(
            """
            INSERT INTO candles (symbol, timeframe, open_time, open, high, low, close, volume)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "BTCUSDT",
                    "15m",
                    candle.open_time.isoformat(),
                    candle.open,
                    candle.high,
                    candle.low,
                    candle.close,
                    candle.volume,
                )
                for candle in candles
            ],
        )

    payload = run_analysis(
        db_path=db_path,
        output_path=output_path,
        report_path=report_path,
        config=_config(),
        start=None,
        end=None,
    )

    assert output_path.exists()
    assert report_path.exists()
    assert payload["manifest"]["research_only"] is True
    assert payload["manifest"]["production_changes"] is False
    assert payload["sweep_events_total"] == 1
    assert payload["sequence_events_total"] == 1
    assert payload["events"][0]["entry_candidate_bar"] == 10
