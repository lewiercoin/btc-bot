from __future__ import annotations

import sqlite3
from pathlib import Path


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
