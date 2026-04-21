from __future__ import annotations

import sqlite3
from pathlib import Path


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
