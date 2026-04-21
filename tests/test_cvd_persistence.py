from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from core.feature_engine import FeatureEngine, FeatureEngineConfig
from core.models import MarketSnapshot
from storage.repositories import fetch_cvd_price_history, save_cvd_price_bar


def test_cvd_history_migration_creates_price_and_flow_history_table() -> None:
    migration = Path("storage/migrations/add_cvd_history_table.sql").read_text(encoding="utf-8")
    conn = sqlite3.connect(":memory:")
    conn.executescript(migration)

    conn.execute(
        """
        INSERT INTO cvd_price_history (
            symbol, timeframe, bar_time, price_close, cvd, tfi, source, captured_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "BTCUSDT",
            "15m",
            "2026-01-01T00:15:00+00:00",
            100.0,
            12.5,
            0.2,
            "mixed",
            "2026-01-01T00:15:01+00:00",
        ),
    )

    row = conn.execute(
        "SELECT symbol, timeframe, price_close, cvd, tfi, source FROM cvd_price_history"
    ).fetchone()
    assert row == ("BTCUSDT", "15m", 100.0, 12.5, 0.2, "mixed")


def test_base_schema_contains_cvd_price_history_table() -> None:
    schema = Path("storage/schema.sql").read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS cvd_price_history" in schema
    assert "idx_cvd_price_history_symbol_tf_time" in schema


def test_cvd_repository_round_trips_history_in_bar_order() -> None:
    schema = Path("storage/schema.sql")
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(schema.read_text(encoding="utf-8"))
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)

    save_cvd_price_bar(
        conn,
        symbol="BTCUSDT",
        timeframe="15m",
        bar_time=now,
        price_close=100.0,
        cvd=1.0,
        tfi=0.1,
        source="mixed",
    )
    save_cvd_price_bar(
        conn,
        symbol="BTCUSDT",
        timeframe="15m",
        bar_time=now + timedelta(minutes=15),
        price_close=101.0,
        cvd=2.0,
        tfi=0.2,
        source="mixed",
    )

    rows = fetch_cvd_price_history(conn, symbol="BTCUSDT", timeframe="15m", limit=10)

    assert [row["cvd"] for row in rows] == [1.0, 2.0]


def test_cvd_bootstrap_preserves_divergence_readiness_after_restart() -> None:
    now = datetime(2026, 1, 1, 1, 0, tzinfo=timezone.utc)
    rows = [
        {"bar_time": now - timedelta(minutes=45), "price_close": 100.0, "cvd": 1.0},
        {"bar_time": now - timedelta(minutes=30), "price_close": 101.0, "cvd": 2.0},
    ]
    engine = FeatureEngine(FeatureEngineConfig(cvd_divergence_bars=3, cvd_divergence_window_bars=3))
    engine.bootstrap_cvd_price_history(rows)

    features = engine.compute(
        MarketSnapshot(
            symbol="BTCUSDT",
            timestamp=now,
            price=99.0,
            bid=98.5,
            ask=99.5,
            aggtrades_bucket_15m={"cvd": 5.0},
        ),
        "v1.0",
        "hash",
    )

    assert features.quality["cvd_divergence"].status == "ready"
    assert features.quality["cvd_divergence"].metadata["loaded_bars"] == 3
