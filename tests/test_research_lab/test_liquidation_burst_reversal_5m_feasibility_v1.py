from __future__ import annotations

import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from research_lab.diagnostics.liquidation_burst_reversal_5m_feasibility_v1 import (
    FORCE_ORDER_END,
    FORCE_ORDER_START,
    five_min_config,
    get_5m_candles,
    run_5m_diagnostic,
    save_5m_cache,
)
from research_lab.diagnostics.liquidation_burst_reversal_entry_feasibility_v1 import (
    Candle,
    build_event,
)


def _ts(index: int) -> datetime:
    return datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=5 * index)


def _candle(index: int, open_: float = 100.0, high: float = 101.0, low: float = 99.5, close: float = 100.0) -> Candle:
    return Candle(index=index, open_time=_ts(index), open=open_, high=high, low=low, close=close, volume=1.0)


def _config():
    config = five_min_config()
    return type(config)(
        timeframe="5m",
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


def _market_db(db_path: Path) -> None:
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
        force_rows = []
        for idx in range(1, 100):
            force_rows.append(("BTCUSDT", (_ts(idx) + timedelta(minutes=1)).isoformat(), "SELL", 1.0, 100.0))
            force_rows.append(("BTCUSDT", (_ts(idx) + timedelta(minutes=2)).isoformat(), "BUY", 1.0, 100.0))
        for idx in (100, 101, 102):
            force_rows.append(("BTCUSDT", (_ts(idx) + timedelta(minutes=1)).isoformat(), "SELL", 10.0, 100.0))
        for idx in (115, 116, 117):
            force_rows.append(("BTCUSDT", (_ts(idx) + timedelta(minutes=1)).isoformat(), "BUY", 10.0, 100.0))
        conn.executemany("INSERT INTO force_orders VALUES (?, ?, ?, ?, ?)", force_rows)


def _cache(cache_path: Path) -> None:
    rows = []
    for idx in range(130):
        open_, high, low, close = 100.0, 101.0, 99.5, 100.0
        if idx in {100, 110, 115}:
            high, low, close = 102.0, 98.0, 100.0
        if idx in {103, 104, 105, 106, 107}:
            high, low, close = 104.0, 99.0, 103.0
        rows.append(_candle(idx, open_, high, low, close))
    save_5m_cache(cache_path, rows, source="synthetic_test_cache", symbol="BTCUSDT")


def test_5m_cache_loads_exact_candles_without_fetch(tmp_path) -> None:
    market_path = tmp_path / "market.db"
    cache_path = tmp_path / "cache.db"
    _market_db(market_path)
    _cache(cache_path)
    with sqlite3.connect(market_path) as conn:
        candles, metadata = get_5m_candles(conn, cache_path=cache_path, config=_config(), allow_fetch=False)

    assert len(candles) == 130
    assert candles[1].open_time - candles[0].open_time == timedelta(minutes=5)
    assert metadata["method"] == "cache"
    assert metadata["source"] == "synthetic_test_cache"


def test_5m_timing_model_is_same_bar_units_but_15_minutes() -> None:
    candles = [_candle(i) for i in range(15)]
    candles[6] = _candle(6, high=102.0, low=98.0, close=100.0)
    candles[7] = _candle(7, high=102.0, low=99.0, close=100.0)
    candles[8] = _candle(8, high=102.0, low=99.0, close=100.0)
    candles[9] = _candle(9, high=104.0, low=99.0, close=101.0)
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
    assert event.state_known_bar == event.detection_bar + 2
    assert event.entry_candidate_bar == event.detection_bar + 3
    assert event.return_start_bar == event.entry_candidate_bar
    detection = parse_iso(event.detection_time_utc)
    entry = parse_iso(event.entry_time_utc)
    assert entry - detection == timedelta(minutes=15)


def test_5m_diagnostic_controls_and_comparison(tmp_path) -> None:
    market_path = tmp_path / "market.db"
    cache_path = tmp_path / "cache.db"
    report_path = tmp_path / "report.md"
    json_path = tmp_path / "artifact.json"
    _market_db(market_path)
    _cache(cache_path)

    payload = run_5m_diagnostic(
        db_path=market_path,
        cache_path=cache_path,
        report_path=report_path,
        json_path=json_path,
        config=_config(),
        allow_fetch=False,
    )

    assert report_path.exists()
    assert json_path.exists()
    assert payload["timing_model"]["entry_delay_minutes"] == 15
    assert payload["comparison_15m_vs_5m"]["entry_delay_minutes"] == {"15m": 45, "5m": 15}
    assert payload["cohort_metrics"]["main_liquidation_burst_reversal"]["count"] >= 1
    assert payload["cohort_metrics"]["control_non_liquidation_sweeps"]["count"] >= 1
    assert payload["cohort_metrics"]["control_opposite_side_liquidations"]["count"] >= 1
    assert payload["cohort_metrics"]["control_shifted_entry"]["count"] >= 1
    assert payload["cohort_metrics"]["control_flow_only_ablation"]["count"] >= 1


def test_5m_diagnostic_is_deterministic(tmp_path) -> None:
    market_path = tmp_path / "market.db"
    cache_path = tmp_path / "cache.db"
    _market_db(market_path)
    _cache(cache_path)

    first = run_5m_diagnostic(
        db_path=market_path,
        cache_path=cache_path,
        report_path=tmp_path / "report1.md",
        json_path=tmp_path / "artifact1.json",
        config=_config(),
        allow_fetch=False,
    )
    second = run_5m_diagnostic(
        db_path=market_path,
        cache_path=cache_path,
        report_path=tmp_path / "report2.md",
        json_path=tmp_path / "artifact2.json",
        config=_config(),
        allow_fetch=False,
    )

    assert first["cohort_metrics"] == second["cohort_metrics"]
    assert first["comparison_15m_vs_5m"] == second["comparison_15m_vs_5m"]
    assert first["invalidation_gates"] == second["invalidation_gates"]


def test_force_order_range_constants_are_5m_aligned() -> None:
    assert FORCE_ORDER_START == datetime(2022, 1, 1, tzinfo=timezone.utc)
    assert FORCE_ORDER_END.minute % 5 == 0


def parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value).astimezone(timezone.utc)
