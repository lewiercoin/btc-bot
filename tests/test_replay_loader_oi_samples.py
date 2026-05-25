from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from backtest.replay_loader import ReplayLoader


def test_replay_loader_uses_oi_samples_when_open_interest_is_absent() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(Path("storage/schema.sql").read_text(encoding="utf-8"))
    ts = datetime(2026, 3, 20, 0, 0, tzinfo=timezone.utc)
    conn.execute(
        """
        INSERT INTO candles (symbol, timeframe, open_time, open, high, low, close, volume)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("ETHUSDT", "15m", ts.isoformat(), 100.0, 101.0, 99.0, 100.5, 10.0),
    )
    conn.execute(
        """
        INSERT INTO oi_samples (symbol, timestamp, oi_value, source, captured_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        ("ETHUSDT", ts.isoformat(), 12345.0, "backfill", ts.isoformat()),
    )

    snapshots = ReplayLoader(conn).load(
        start_date=ts,
        end_date=ts.replace(minute=15),
        symbol="ETHUSDT",
    ).snapshots

    assert len(snapshots) == 1
    assert snapshots[0].open_interest == 12345.0
