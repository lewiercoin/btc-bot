from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from core.feature_engine import FeatureEngine, FeatureEngineConfig
from core.models import MarketSnapshot
from storage.repositories import fetch_oi_samples, save_oi_sample


def test_oi_samples_migration_creates_append_only_sample_table() -> None:
    migration = Path("storage/migrations/add_oi_samples_table.sql").read_text(encoding="utf-8")
    conn = sqlite3.connect(":memory:")
    conn.executescript(migration)

    conn.execute(
        """
        INSERT INTO oi_samples (symbol, timestamp, oi_value, source, captured_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        ("BTCUSDT", "2026-01-01T00:00:00+00:00", 123.45, "rest", "2026-01-01T00:00:01+00:00"),
    )

    row = conn.execute(
        "SELECT symbol, timestamp, oi_value, source FROM oi_samples"
    ).fetchone()
    assert row == ("BTCUSDT", "2026-01-01T00:00:00+00:00", 123.45, "rest")


def test_base_schema_contains_oi_samples_table() -> None:
    schema = Path("storage/schema.sql").read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS oi_samples" in schema
    assert "idx_oi_samples_symbol_time" in schema


def test_oi_repository_round_trips_samples_in_timestamp_order() -> None:
    schema = Path("storage/schema.sql")
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(schema.read_text(encoding="utf-8"))
    now = datetime(2026, 1, 2, tzinfo=timezone.utc)

    save_oi_sample(conn, symbol="BTCUSDT", timestamp=now, oi_value=200.0, source="rest")
    save_oi_sample(conn, symbol="BTCUSDT", timestamp=now - timedelta(days=1), oi_value=100.0, source="rest")

    rows = fetch_oi_samples(conn, symbol="BTCUSDT")

    assert [row["oi_value"] for row in rows] == [100.0, 200.0]


def test_oi_baseline_bootstrap_survives_restart_when_history_is_mature() -> None:
    now = datetime(2026, 3, 1, tzinfo=timezone.utc)
    rows = [
        {"timestamp": now - timedelta(days=60), "oi_value": 100.0},
        {"timestamp": now - timedelta(days=30), "oi_value": 120.0},
    ]
    engine = FeatureEngine(FeatureEngineConfig(oi_baseline_days=60, oi_z_window_days=60))
    engine.bootstrap_oi_history(rows)

    features = engine.compute(
        MarketSnapshot(
            symbol="BTCUSDT",
            timestamp=now,
            price=100.0,
            bid=99.5,
            ask=100.5,
            open_interest=140.0,
        ),
        "v1.0",
        "hash",
    )

    assert features.quality["oi_baseline"].status == "ready"
    assert features.quality["oi_baseline"].metadata["days_covered"] == 60.0
