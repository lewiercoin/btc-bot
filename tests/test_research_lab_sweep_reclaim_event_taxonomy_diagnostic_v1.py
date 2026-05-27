from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

from research_lab.analysis_sweep_reclaim_event_taxonomy_diagnostic_v1 import (
    DiagnosticConfig,
    Candle,
    EVENT_ACTIVE_LIQUIDITY,
    EVENT_CLOSE_BOS,
    EVENT_DELAYED_RECLAIM,
    EVENT_EQUAL_TOUCH,
    EVENT_IMMEDIATE_RECLAIM,
    EVENT_TRUE_BREAKOUT,
    EVENT_WICK_CROSSED,
    PivotConfig,
    classify_taxonomy_events,
    detect_confirmed_pivots,
    run_analysis,
)


def _candle(
    idx: int,
    *,
    open_: float | None = None,
    high: float = 101.0,
    low: float = 99.0,
    close: float = 100.0,
) -> Candle:
    open_price = close if open_ is None else open_
    return Candle(
        index=idx,
        open_time=datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=5 * idx),
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=1.0,
    )


def _config(*, window: int = 3, touch_tolerance: float = 0.0) -> DiagnosticConfig:
    return DiagnosticConfig(
        symbol="BTCUSDT",
        timeframe="5m",
        pivot=PivotConfig(left=2, right=2, strict=True, touch_tolerance=touch_tolerance),
        atr_period=2,
        reclaim_window_bars=window,
        forward_windows=(1, 2),
    )


def _event_types(events):
    return [event.event_type for event in events]


def _events(events, event_type: str):
    return [event for event in events if event.event_type == event_type]


def test_pivot_confirmation_is_right_side_delayed() -> None:
    candles = [
        _candle(0, high=100, low=95),
        _candle(1, high=105, low=96),
        _candle(2, high=110, low=97),
        _candle(3, high=106, low=96),
        _candle(4, high=107, low=95),
        _candle(5, high=112, low=98, close=108),
    ]

    pivots = detect_confirmed_pivots(candles, _config().pivot)
    high_pivots = [pivot for pivot in pivots if pivot.side == "HIGH" and pivot.pivot_index == 2]

    assert len(high_pivots) == 1
    assert high_pivots[0].confirmed_at_index == 4

    events, _ = classify_taxonomy_events(candles, _config())
    active = [
        event
        for event in events
        if event.event_type == EVENT_ACTIVE_LIQUIDITY
        and event.level_side == "HIGH"
        and event.pivot_index == 2
    ]
    wick = [
        event
        for event in events
        if event.event_type == EVENT_WICK_CROSSED
        and event.level_side == "HIGH"
        and event.pivot_index == 2
    ]

    assert active[0].detection_bar == 4
    assert wick[0].detection_bar == 5
    assert wick[0].detection_bar >= high_pivots[0].confirmed_at_index


def test_equal_touch_does_not_mark_level_taken() -> None:
    candles = [
        _candle(0, high=100, low=95),
        _candle(1, high=105, low=96),
        _candle(2, high=110, low=97),
        _candle(3, high=106, low=96),
        _candle(4, high=107, low=95),
        _candle(5, high=110, low=98, close=109),
        _candle(6, high=112, low=99, close=108),
        _candle(7, high=109, low=98, close=108),
    ]

    events, _ = classify_taxonomy_events(candles, _config())
    touches = [
        event
        for event in events
        if event.event_type == EVENT_EQUAL_TOUCH
        and event.level_side == "HIGH"
        and event.pivot_index == 2
    ]
    wick = [
        event
        for event in events
        if event.event_type == EVENT_WICK_CROSSED
        and event.level_side == "HIGH"
        and event.pivot_index == 2
    ]

    assert len(touches) == 1
    assert touches[0].detection_bar == 5
    assert touches[0].equal_touch is True
    assert len(wick) == 1
    assert wick[0].detection_bar == 6


def test_wick_cross_close_bos_and_immediate_reclaim_are_separate() -> None:
    candles = [
        _candle(0, high=100, low=95),
        _candle(1, high=105, low=96),
        _candle(2, high=110, low=97),
        _candle(3, high=106, low=96),
        _candle(4, high=107, low=95),
        _candle(5, high=112, low=98, close=108),
        _candle(6, high=109, low=98, close=108),
        _candle(7, high=108, low=97, close=107),
    ]

    events, _ = classify_taxonomy_events(candles, _config())
    high_pivot_events = [
        event.event_type
        for event in events
        if event.level_side == "HIGH"
        and event.pivot_index == 2
        and event.detection_bar == 5
    ]

    assert EVENT_WICK_CROSSED in high_pivot_events
    assert EVENT_IMMEDIATE_RECLAIM in high_pivot_events
    assert EVENT_CLOSE_BOS not in high_pivot_events


def test_delayed_reclaim_label_available_bar_and_dual_returns() -> None:
    candles = [
        _candle(0, high=100, low=95),
        _candle(1, high=105, low=96),
        _candle(2, high=110, low=97),
        _candle(3, high=106, low=96),
        _candle(4, high=107, low=95),
        _candle(5, high=112, low=98, close=111),
        _candle(6, high=113, low=109, close=111.5),
        _candle(7, high=111, low=107, close=109),
        _candle(8, high=110, low=105, close=106),
        _candle(9, high=109, low=104, close=105),
    ]

    events, _ = classify_taxonomy_events(candles, _config(window=3))
    delayed = [
        event
        for event in events
        if event.event_type == EVENT_DELAYED_RECLAIM
        and event.level_side == "HIGH"
        and event.pivot_index == 2
    ][0]

    assert delayed.detection_bar == 5
    assert delayed.label_available_bar == 7
    assert delayed.reclaim_delay_bars == 2
    assert delayed.return_start_bar_detection == 5
    assert delayed.return_start_bar_label_available == 7
    assert delayed.forward_detection["return_1"] != delayed.forward_label_available["return_1"]


def test_true_breakout_known_only_after_reclaim_window() -> None:
    candles = [
        _candle(0, high=100, low=95),
        _candle(1, high=105, low=96),
        _candle(2, high=110, low=97),
        _candle(3, high=106, low=96),
        _candle(4, high=107, low=95),
        _candle(5, high=112, low=98, close=111),
        _candle(6, high=113, low=110, close=112),
        _candle(7, high=114, low=111, close=113),
        _candle(8, high=115, low=112, close=114),
        _candle(9, high=116, low=113, close=115),
    ]

    events, _ = classify_taxonomy_events(candles, _config(window=3))
    true_breakout = [
        event
        for event in events
        if event.event_type == EVENT_TRUE_BREAKOUT
        and event.level_side == "HIGH"
        and event.pivot_index == 2
    ][0]

    assert true_breakout.detection_bar == 5
    assert true_breakout.label_available_bar == 8
    assert true_breakout.true_breakout is True
    assert true_breakout.no_reclaim_within_window is True


def test_duplicate_event_inflation_prevented_after_level_taken() -> None:
    candles = [
        _candle(0, high=100, low=95),
        _candle(1, high=105, low=96),
        _candle(2, high=110, low=97),
        _candle(3, high=106, low=96),
        _candle(4, high=107, low=95),
        _candle(5, high=112, low=98, close=108),
        _candle(6, high=113, low=98, close=107),
        _candle(7, high=114, low=98, close=106),
    ]

    events, _ = classify_taxonomy_events(candles, _config())
    wick = [
        event
        for event in events
        if event.event_type == EVENT_WICK_CROSSED
        and event.level_side == "HIGH"
        and event.pivot_index == 2
    ]

    assert len(wick) == 1
    assert wick[0].detection_bar == 5


def test_synthetic_sqlite_integration(tmp_path) -> None:
    db_path = tmp_path / "synthetic.db"
    output_path = tmp_path / "out.json"
    report_path = tmp_path / "report.md"
    candles = [
        _candle(0, high=100, low=95),
        _candle(1, high=105, low=96),
        _candle(2, high=110, low=97),
        _candle(3, high=106, low=96),
        _candle(4, high=107, low=95),
        _candle(5, high=112, low=98, close=111),
        _candle(6, high=113, low=109, close=111.5),
        _candle(7, high=111, low=107, close=109),
        _candle(8, high=110, low=105, close=106),
        _candle(9, high=109, low=104, close=105),
    ]
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
                    "5m",
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
        config=_config(window=3),
        start=None,
        end=None,
        max_json_events=1000,
    )

    assert output_path.exists()
    assert report_path.exists()
    assert payload["manifest"]["research_only"] is True
    assert payload["manifest"]["production_changes"] is False
    assert EVENT_DELAYED_RECLAIM in _event_types(
        type("Obj", (), {"event_type": row["event_type"]}) for row in payload["events"]
    )
    assert payload["summary"]["required_decision_cohorts"]["delayed_close_reclaim"]["count"] >= 1
