from __future__ import annotations

import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from research_lab.diagnostics.volume_confirmed_range_breakout_feasibility_v1 import (
    AggTradeBucket,
    Candle,
    DiagnosticConfig,
    breakout_state,
    build_cohorts,
    build_event,
    inspect_schema,
    iso,
    run_diagnostic,
)


def _ts(index: int) -> datetime:
    return datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=15 * index)


def _config() -> DiagnosticConfig:
    return DiagnosticConfig(
        range_lookback_bars=5,
        range_baseline_bars=10,
        compression_percentile=35.0,
        wide_range_percentile=65.0,
        breakout_distance_pct=0.001,
        volume_multiple=1.5,
        low_volume_multiple=1.0,
        entry_delay_bars=1,
        shifted_entry_delay_bars=3,
        outcome_horizon_bars=5,
        round_trip_cost_pct=0.001,
        fixed_risk_pct=0.01,
        random_offset_bars=11,
        max_serialized_events_per_cohort=100,
    )


def _candle(
    index: int,
    open_: float = 100.0,
    high: float = 101.0,
    low: float = 99.0,
    close: float = 100.0,
    volume: float = 100.0,
) -> Candle:
    return Candle(index=index, open_time=_ts(index), open=open_, high=high, low=low, close=close, volume=volume)


def _bucket(index: int, tfi: float = 0.1) -> AggTradeBucket:
    return AggTradeBucket(
        bucket_time=_ts(index),
        taker_buy_volume=60.0 if tfi > 0 else 40.0,
        taker_sell_volume=40.0 if tfi > 0 else 60.0,
        tfi=tfi,
        cvd=float(index),
    )


def _buckets(count: int, default_tfi: float = 0.1) -> dict[str, AggTradeBucket]:
    return {iso(_ts(idx)): _bucket(idx, default_tfi) for idx in range(count)}


def _base_candles(count: int = 60) -> list[Candle]:
    candles: list[Candle] = []
    for idx in range(count):
        candles.append(_candle(idx))
    return candles


def test_breakout_state_excludes_current_bar_from_range() -> None:
    candles = _base_candles()
    candles[20] = _candle(20, open_=100.0, high=104.0, low=100.0, close=103.0, volume=200.0)
    buckets = _buckets(len(candles), 0.2)
    config = _config()

    state = breakout_state(candles, buckets, 20, config)

    assert state is not None
    assert state.direction == "LONG"
    assert state.range_high == 101.0
    assert state.range_low == 99.0
    assert state.detection_bar == 20


def test_build_event_enforces_next_bar_entry_and_return_start() -> None:
    candles = _base_candles()
    candles[20] = _candle(20, high=104.0, low=100.0, close=103.0, volume=200.0)
    candles[21] = _candle(21, open_=103.0, high=105.0, low=102.0, close=104.0, volume=100.0)
    candles[25] = _candle(25, open_=105.0, high=107.0, low=104.0, close=106.0, volume=100.0)
    state = breakout_state(candles, _buckets(len(candles), 0.2), 20, _config())
    assert state is not None

    event = build_event(
        cohort="main_volume_confirmed_range_breakout",
        candles=candles,
        state=state,
        entry_delay_bars=1,
        config=_config(),
    )

    assert event is not None
    assert event.range_detection_bar == 19
    assert event.detection_bar == 20
    assert event.state_known_bar == 20
    assert event.entry_candidate_bar == 21
    assert event.return_start_bar == 21
    assert event.label_available_bar == 21
    assert event.exit_bar == 25
    assert event.net_return_pct != ((candles[25].close - candles[20].close) / candles[20].close)


def test_mfe_accessibility_before_and_after_entry() -> None:
    candles = _base_candles()
    candles[20] = _candle(20, open_=100.0, high=104.0, low=100.0, close=103.0, volume=200.0)
    candles[21] = _candle(21, open_=103.0, high=104.0, low=101.0, close=103.5)
    candles[22] = _candle(22, open_=103.5, high=107.0, low=103.0, close=106.0)
    state = breakout_state(candles, _buckets(len(candles), 0.2), 20, _config())
    assert state is not None

    event = build_event(
        cohort="main_volume_confirmed_range_breakout",
        candles=candles,
        state=state,
        entry_delay_bars=1,
        config=_config(),
    )

    assert event is not None
    assert event.mfe_before_entry == 1.0
    assert event.mfe_after_entry == 4.0
    assert event.total_mfe == 5.0
    assert event.mfe_consumed_pct == 0.2


def _create_synthetic_db(db_path: Path) -> None:
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
        conn.execute(
            """
            CREATE TABLE aggtrade_buckets (
                symbol TEXT NOT NULL,
                bucket_time TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                taker_buy_volume REAL NOT NULL,
                taker_sell_volume REAL NOT NULL,
                tfi REAL NOT NULL,
                cvd REAL NOT NULL
            )
            """
        )

        candles = _base_candles(90)
        # Main long event: compressed range, volume spike, aligned TFI.
        candles[20] = _candle(20, open_=100.0, high=104.0, low=100.0, close=103.0, volume=200.0)
        candles[21] = _candle(21, open_=103.0, high=105.0, low=102.0, close=104.0)
        candles[22] = _candle(22, open_=104.0, high=107.0, low=103.0, close=106.0)
        # Low-volume aligned breakout control.
        candles[35] = _candle(35, open_=100.0, high=104.0, low=100.0, close=103.0, volume=80.0)
        # Opposite-flow control.
        candles[50] = _candle(50, open_=100.0, high=104.0, low=100.0, close=103.0, volume=200.0)
        # Wide-range control: widen prior range materially before breakout.
        for idx in range(60, 65):
            candles[idx] = _candle(idx, open_=100.0, high=105.0, low=95.0, close=100.0, volume=100.0)
        candles[65] = _candle(65, open_=100.0, high=108.0, low=100.0, close=107.0, volume=200.0)

        conn.executemany(
            "INSERT INTO candles VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("BTCUSDT", "15m", iso(c.open_time), c.open, c.high, c.low, c.close, c.volume)
                for c in candles
            ],
        )

        bucket_rows = []
        for idx in range(len(candles)):
            tfi = 0.2
            if idx == 50:
                tfi = -0.2
            bucket_rows.append(("BTCUSDT", iso(_ts(idx)), "15m", 60.0, 40.0, tfi, float(idx)))
        conn.executemany("INSERT INTO aggtrade_buckets VALUES (?, ?, ?, ?, ?, ?, ?)", bucket_rows)


def test_build_cohorts_controls_are_isolated() -> None:
    candles = _base_candles(90)
    buckets = _buckets(90, 0.2)
    candles[20] = _candle(20, high=104.0, low=100.0, close=103.0, volume=200.0)
    candles[35] = _candle(35, high=104.0, low=100.0, close=103.0, volume=80.0)
    candles[50] = _candle(50, high=104.0, low=100.0, close=103.0, volume=200.0)
    buckets[iso(_ts(50))] = _bucket(50, -0.2)
    for idx in range(60, 65):
        candles[idx] = _candle(idx, high=105.0, low=95.0, close=100.0)
    candles[65] = _candle(65, high=108.0, low=100.0, close=107.0, volume=200.0)

    cohorts = build_cohorts(candles, buckets, _config())

    assert cohorts["main_volume_confirmed_range_breakout"]
    assert cohorts["control_price_only_range_breakouts"]
    assert cohorts["control_breakout_without_volume_spike"]
    assert cohorts["control_opposite_flow_breakout"]
    assert cohorts["control_shifted_entry"]
    assert cohorts["control_random_offset"]
    assert cohorts["control_wide_range_breakout"]


def test_synthetic_diagnostic_runs_and_is_deterministic(tmp_path: Path) -> None:
    db_path = tmp_path / "synthetic.db"
    _create_synthetic_db(db_path)

    first = run_diagnostic(
        db_path=db_path,
        report_path=tmp_path / "report1.md",
        json_path=tmp_path / "artifact1.json",
        config=_config(),
    )
    second = run_diagnostic(
        db_path=db_path,
        report_path=tmp_path / "report2.md",
        json_path=tmp_path / "artifact2.json",
        config=_config(),
    )

    assert first["cohort_metrics"] == second["cohort_metrics"]
    assert first["invalidation_gates"] == second["invalidation_gates"]
    assert first["timing_model"]["return_start_bar"] == "i+1"
    assert first["cohort_metrics"]["main_volume_confirmed_range_breakout"]["count"] >= 1
    assert Path(first["manifest"]["report_path"]).exists()
    assert Path(first["manifest"]["json_path"]).exists()


def test_schema_preflight_uses_actual_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "schema.db"
    _create_synthetic_db(db_path)
    with sqlite3.connect(db_path) as conn:
        schema = inspect_schema(conn)

    assert schema["missing_required"] == {}
    assert schema["provisional_tables_present"]["ohlcv_1h"] is False
    assert schema["provisional_tables_present"]["features_1h"] is False
    assert schema["adapted_market_schema"]["price_action"] == "candles"
    assert schema["adapted_market_schema"]["volume_flow"] == "aggtrade_buckets"
