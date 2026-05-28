from __future__ import annotations

import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from research_lab.diagnostics.liquidation_burst_reversal_entry_feasibility_v1 import (
    Candle,
    DiagnosticConfig,
    build_event,
    inspect_schema,
    run_diagnostic,
)


def _ts(index: int) -> datetime:
    return datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=15 * index)


def _config() -> DiagnosticConfig:
    return DiagnosticConfig(
        atr_period=3,
        equal_level_lookback=10,
        equal_level_tol_atr=0.50,
        min_hits=3,
        min_age_bars=2,
        sweep_buf_atr=0.10,
        sweep_proximity_atr=5.0,
        baseline_lookback_bars=30,
        liquidation_burst_multiple=2.0,
        non_liquidation_multiple=0.5,
        burst_window_bars=3,
        entry_delay_bars=3,
        shifted_entry_delay_bars=5,
        outcome_horizon_bars=5,
        round_trip_cost_pct=0.001,
        fixed_risk_pct=0.01,
        max_serialized_events_per_cohort=100,
    )


def _candle(index: int, open_: float = 100.0, high: float = 101.0, low: float = 99.5, close: float = 100.0) -> Candle:
    return Candle(index=index, open_time=_ts(index), open=open_, high=high, low=low, close=close, volume=1.0)


def test_build_event_enforces_entry_timing_and_return_start() -> None:
    candles = [_candle(i) for i in range(15)]
    candles[6] = _candle(6, high=102.0, low=98.0, close=100.0)
    candles[7] = _candle(7, high=101.5, low=99.0, close=100.0)
    candles[8] = _candle(8, high=101.0, low=99.0, close=100.0)
    candles[9] = _candle(9, high=103.0, low=99.0, close=101.0)
    candles[10] = _candle(10, high=104.0, low=100.0, close=103.0)
    config = _config()

    event = build_event(
        cohort="main_liquidation_burst_reversal",
        candles=candles,
        detection_bar=6,
        direction="LONG",
        sweep_side="LOW",
        entry_delay_bars=config.entry_delay_bars,
        expected_liq_notional=1000.0,
        opposite_liq_notional=0.0,
        expected_baseline=100.0,
        opposite_baseline=100.0,
        config=config,
    )

    assert event is not None
    assert event.detection_bar == 6
    assert event.state_known_bar == 8
    assert event.confirmation_bar == 8
    assert event.entry_candidate_bar == 9
    assert event.return_start_bar == 9
    assert event.label_available_bar == 9
    assert event.net_return_pct != ((candles[10].close - candles[6].close) / candles[6].close)


def test_mfe_accessibility_uses_detection_to_entry_window() -> None:
    candles = [_candle(i) for i in range(15)]
    candles[6] = _candle(6, high=102.0, low=98.0, close=100.0)
    candles[7] = _candle(7, high=102.0, low=99.0, close=100.0)
    candles[8] = _candle(8, high=102.0, low=99.0, close=100.0)
    candles[9] = _candle(9, high=104.0, low=99.0, close=101.0)
    candles[10] = _candle(10, high=104.0, low=100.0, close=103.0)
    event = build_event(
        cohort="main_liquidation_burst_reversal",
        candles=candles,
        detection_bar=6,
        direction="LONG",
        sweep_side="LOW",
        entry_delay_bars=3,
        expected_liq_notional=1000.0,
        opposite_liq_notional=0.0,
        expected_baseline=100.0,
        opposite_baseline=100.0,
        config=_config(),
    )

    assert event is not None
    assert event.mfe_before_entry == 2.0
    assert event.total_mfe_from_detection == 4.0
    assert event.mfe_consumed_pct == 0.5


def _create_synthetic_db(db_path) -> None:
    config = _config()
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
            CREATE TABLE force_orders (
                symbol TEXT NOT NULL,
                event_time TEXT NOT NULL,
                side TEXT NOT NULL,
                qty REAL NOT NULL,
                price REAL NOT NULL
            )
            """
        )
        rows = []
        for idx in range(130):
            open_, high, low, close = 100.0, 101.0, 99.5, 100.0
            if idx in {100, 110, 115}:
                high, low, close = 102.0, 98.0, 100.0
            if idx in {103, 104, 105, 106, 107}:
                high, low, close = 104.0, 99.0, 103.0
            rows.append(("BTCUSDT", "15m", _ts(idx).isoformat(), open_, high, low, close, 1.0))
        conn.executemany("INSERT INTO candles VALUES (?, ?, ?, ?, ?, ?, ?, ?)", rows)

        force_rows = []
        for idx in range(1, 100):
            force_rows.append(("BTCUSDT", (_ts(idx) + timedelta(minutes=1)).isoformat(), "SELL", 1.0, 100.0))
            force_rows.append(("BTCUSDT", (_ts(idx) + timedelta(minutes=2)).isoformat(), "BUY", 1.0, 100.0))
        for idx in (100, 101, 102):
            force_rows.append(("BTCUSDT", (_ts(idx) + timedelta(minutes=1)).isoformat(), "SELL", 10.0, 100.0))
        for idx in (115, 116, 117):
            force_rows.append(("BTCUSDT", (_ts(idx) + timedelta(minutes=1)).isoformat(), "BUY", 10.0, 100.0))
        conn.executemany("INSERT INTO force_orders VALUES (?, ?, ?, ?, ?)", force_rows)

    assert config.symbol == "BTCUSDT"


def test_synthetic_diagnostic_controls_are_isolated(tmp_path) -> None:
    db_path = tmp_path / "synthetic.db"
    report_path = tmp_path / "report.md"
    json_path = tmp_path / "artifact.json"
    _create_synthetic_db(db_path)

    payload = run_diagnostic(
        db_path=db_path,
        report_path=report_path,
        json_path=json_path,
        config=_config(),
    )

    assert report_path.exists()
    assert json_path.exists()
    assert payload["schema"]["missing_required"] == {}
    assert payload["cohort_metrics"]["main_liquidation_burst_reversal"]["count"] >= 1
    assert payload["cohort_metrics"]["control_non_liquidation_sweeps"]["count"] >= 1
    assert payload["cohort_metrics"]["control_opposite_side_liquidations"]["count"] >= 1
    assert payload["cohort_metrics"]["control_shifted_entry"]["count"] >= 1
    assert payload["cohort_metrics"]["control_flow_only_ablation"]["count"] >= 1
    first = payload["events_sample"]["main_liquidation_burst_reversal"][0]
    assert first["state_known_bar"] == first["detection_bar"] + 2
    assert first["entry_candidate_bar"] == first["detection_bar"] + 3
    assert first["return_start_bar"] == first["entry_candidate_bar"]


def test_diagnostic_is_deterministic(tmp_path) -> None:
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


def test_schema_preflight_reports_missing_provisional_names(tmp_path) -> None:
    db_path = tmp_path / "schema.db"
    _create_synthetic_db(db_path)
    with sqlite3.connect(db_path) as conn:
        schema = inspect_schema(conn)

    assert schema["missing_required"] == {}
    assert schema["provisional_tables_present"]["ohlcv_1h"] is False
    assert schema["provisional_tables_present"]["features_1h"] is False
    assert schema["adapted_market_schema"]["price_action"] == "candles"
    assert schema["adapted_market_schema"]["liquidations"] == "force_orders"
