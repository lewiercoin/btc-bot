from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

from research_lab.analysis_mfe_accessibility_earliest_knowable_signal_v1 import (
    STATE_DISPLACEMENT,
    STATE_RAW_SWEEP,
    STATE_RECLAIM,
    STATE_REJECT_SHALLOW,
    Candle,
    DiagnosticConfig,
    MetadataPoint,
    build_state_observations,
    compute_atr_series,
    detect_sweep_events,
    forward_metrics,
    run_analysis,
)


def _candle(idx: int, *, open_: float, high: float, low: float, close: float) -> Candle:
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
        reclaim_buf_atr=0.02,
        wick_min_atr=0.01,
        min_sweep_depth_pct=0.030,
        near_miss_depth_pct=0.005,
        duplicate_level_tolerance_pct=0.01,
        duplicate_level_window_bars=20,
        max_post_bars=5,
        forward_windows=(1, 2, 3),
        round_trip_cost_pct=0.001,
        deterministic_control_shift_bars=3,
        direction_tfi_threshold=0.05,
        tfi_impulse_threshold=0.10,
        confluence_min=3.0,
        force_burst_window=3,
        force_burst_z=0.5,
        max_json_rows=5000,
    )


def _candles() -> list[Candle]:
    return [
        _candle(0, open_=100, high=101, low=100.0, close=100.5),
        _candle(1, open_=101, high=102, low=100.5, close=101),
        _candle(2, open_=101, high=102, low=100.0, close=101),
        _candle(3, open_=101, high=103, low=101.0, close=102),
        _candle(4, open_=102, high=103, low=100.0, close=101),
        _candle(5, open_=101, high=102, low=100.5, close=101),
        _candle(6, open_=100, high=101, low=98.0, close=100.8),
        _candle(7, open_=101, high=108, low=100.5, close=107.5),
        _candle(8, open_=107, high=109, low=106, close=108),
        _candle(9, open_=108, high=110, low=107, close=109),
        _candle(10, open_=109, high=109.5, low=104, close=105),
    ]


def _metadata(candles: list[Candle]) -> list[MetadataPoint]:
    rows = [MetadataPoint() for _ in candles]
    rows[6] = MetadataPoint(tfi=0.12, cvd=-10, cvd_cum=-10, funding_rate=-0.0001)
    rows[7] = MetadataPoint(tfi=0.50, cvd=20, cvd_cum=10, force_count=8, force_sell_qty=8, force_z=2.0, funding_rate=-0.0001)
    rows[8] = MetadataPoint(tfi=0.20, cvd=5, cvd_cum=15, force_count=2, force_sell_qty=2, force_z=0.0, funding_rate=-0.0001)
    return rows


def test_forward_metrics_are_from_entry_bar_not_detection_bar() -> None:
    candles = _candles()
    detection = forward_metrics(candles, start_bar=6, direction="LONG", windows=(1,), cost_pct=0.001)
    entry = forward_metrics(candles, start_bar=8, direction="LONG", windows=(1,), cost_pct=0.001)

    assert detection["return_1"] != entry["return_1"]
    assert detection["mfe_1"] != entry["mfe_1"]


def test_state_timing_uses_next_bar_entry_candidate() -> None:
    candles = _candles()
    config = _config()
    atr = compute_atr_series(candles, config.atr_period)
    sweeps = detect_sweep_events(candles, atr, config)
    observations = build_state_observations(candles, sweeps, atr, _metadata(candles), config)

    raw = next(row for row in observations if row.state_name == STATE_RAW_SWEEP)
    displacement = next(row for row in observations if row.state_name == STATE_DISPLACEMENT)

    assert raw.detection_bar == 6
    assert raw.state_known_bar == 6
    assert raw.entry_candidate_bar == 7
    assert displacement.state_known_bar == 7
    assert displacement.entry_candidate_bar == 8
    assert displacement.return_start_bar == displacement.entry_candidate_bar


def test_mfe_consumed_increases_for_later_state() -> None:
    candles = _candles()
    config = _config()
    atr = compute_atr_series(candles, config.atr_period)
    sweeps = detect_sweep_events(candles, atr, config)
    observations = build_state_observations(candles, sweeps, atr, _metadata(candles), config)

    raw = next(row for row in observations if row.state_name == STATE_RAW_SWEEP)
    displacement = next(row for row in observations if row.state_name == STATE_DISPLACEMENT)

    assert raw.mfe_consumed_pct is not None
    assert displacement.mfe_consumed_pct is not None
    assert displacement.mfe_consumed_pct >= raw.mfe_consumed_pct


def test_reclaim_and_reject_states_are_separate() -> None:
    candles = _candles()
    config = _config()
    atr = compute_atr_series(candles, config.atr_period)
    sweeps = detect_sweep_events(candles, atr, config)
    observations = build_state_observations(candles, sweeps, atr, _metadata(candles), config)
    state_names = {row.state_name for row in observations}

    assert STATE_RECLAIM in state_names
    assert STATE_REJECT_SHALLOW in state_names


def test_synthetic_sqlite_integration(tmp_path) -> None:
    db_path = tmp_path / "synthetic_mfe.db"
    output_path = tmp_path / "out.json"
    report_path = tmp_path / "report.md"
    candles = _candles()
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
        conn.execute(
            """
            CREATE TABLE force_orders (
                symbol TEXT NOT NULL,
                event_time TEXT NOT NULL,
                side TEXT NOT NULL,
                qty REAL NOT NULL,
                price REAL NOT NULL
            )
            """
        )
        conn.executemany(
            "INSERT INTO candles VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
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
        conn.executemany(
            "INSERT INTO aggtrade_buckets VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                ("BTCUSDT", candle.open_time.isoformat(), "15m", 10.0, 5.0, 0.25, 5.0)
                for candle in candles
            ],
        )
        conn.execute(
            "INSERT INTO force_orders VALUES (?, ?, ?, ?, ?)",
            ("BTCUSDT", (candles[7].open_time + timedelta(minutes=1)).isoformat(), "SELL", 10.0, 99.0),
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
    assert payload["sweep_events_total"] == 2
    assert payload["state_observations_total"] >= 5
    assert payload["invalidation_checks"]["decision"] in {
        "STOP_SMC_RESEARCH_TRIAL_00095_ALREADY_OPTIMAL",
        "PLAN_ONE_DISPLACEMENT_ENTRY_STRATEGY",
        "PLAN_ONE_ORDER_FLOW_CLASSIFICATION_STRATEGY",
        "PLAN_ONE_LIQUIDATION_UNWIND_STRATEGY",
        "INCONCLUSIVE_DATA_GAP",
        "REJECT_RESULTS_METHOD_INVALID",
    }
