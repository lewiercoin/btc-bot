from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

from scripts.server.run_daily_data_collector import (
    compute_rolling_bias_5d,
    extract_coinglass_flow_usd,
    merge_preferred_etf_flows,
    resolve_collection_start,
)
from scripts.server.run_force_order_collector import insert_force_orders, normalize_rest_force_order_event
from storage.db import connect, init_db, transaction


def test_normalize_rest_force_order_event_prefers_update_time_and_avg_price() -> None:
    event = normalize_rest_force_order_event(
        {
            "symbol": "BTCUSDT",
            "side": "SELL",
            "executedQty": "1.25",
            "price": "82000.0",
            "avgPrice": "81950.5",
            "time": 1_700_000_000_000,
            "updateTime": 1_700_000_010_000,
        }
    )

    assert event["symbol"] == "BTCUSDT"
    assert event["side"] == "SELL"
    assert event["qty"] == 1.25
    assert event["price"] == 81950.5
    assert event["event_time"] == datetime.fromtimestamp(1_700_000_010_000 / 1000, tz=timezone.utc)


def test_insert_force_orders_is_idempotent_without_unique_constraint(tmp_path: Path) -> None:
    db_path = tmp_path / "btc_bot.db"
    schema_path = Path(__file__).resolve().parents[1] / "storage" / "schema.sql"

    conn = connect(db_path)
    try:
        init_db(conn, schema_path)
        event = {
            "symbol": "BTCUSDT",
            "event_time": datetime(2026, 4, 11, 0, 0, tzinfo=timezone.utc),
            "side": "BUY",
            "qty": 2.0,
            "price": 84_000.0,
        }

        with transaction(conn):
            first_inserted = insert_force_orders(conn, [event, event])
        with transaction(conn):
            second_inserted = insert_force_orders(conn, [event])

        stored_rows = conn.execute("SELECT COUNT(*) FROM force_orders").fetchone()[0]
    finally:
        conn.close()

    assert first_inserted == 1
    assert second_inserted == 0
    assert stored_rows == 1


def test_resolve_collection_start_uses_initial_for_first_run() -> None:
    assert resolve_collection_start(None, date(2024, 1, 10)) == date(2024, 1, 10)


def test_resolve_collection_start_advances_by_one_day() -> None:
    assert resolve_collection_start(date(2026, 4, 10), date(2024, 1, 10)) == date(2026, 4, 11)


def test_extract_coinglass_flow_usd_uses_nested_etf_flows_when_needed() -> None:
    item = {
        "timestamp": 1_712_000_000_000,
        "etf_flows": [
            {"etf_ticker": "IBIT", "change_usd": 12_500_000},
            {"etf_ticker": "FBTC", "changeUsd": -2_500_000},
        ],
    }

    assert extract_coinglass_flow_usd(item) == 10_000_000


def test_merge_preferred_etf_flows_prefers_primary_values() -> None:
    merged = merge_preferred_etf_flows(
        primary_rows=[(date(2026, 4, 10), 15.0)],
        fallback_rows=[(date(2026, 4, 9), 5.0), (date(2026, 4, 10), 10.0)],
    )

    assert merged == [
        (date(2026, 4, 9), 5.0),
        (date(2026, 4, 10), 15.0),
    ]


def test_compute_rolling_bias_5d_uses_last_five_observed_rows() -> None:
    rolling = compute_rolling_bias_5d(
        [
            (date(2026, 4, 1), 1.0),
            (date(2026, 4, 2), 2.0),
            (date(2026, 4, 3), 3.0),
            (date(2026, 4, 4), 4.0),
            (date(2026, 4, 7), 5.0),
            (date(2026, 4, 8), 6.0),
        ]
    )

    assert rolling[-1] == (date(2026, 4, 8), 20.0)
