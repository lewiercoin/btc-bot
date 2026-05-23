from __future__ import annotations

import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run_multi_asset_backtest import _generate_15min_timestamps, _parse_iso_datetime, _to_utc


def test_generate_15min_timestamps():
    """Test 15-minute timestamp generation."""
    start = datetime(2026, 5, 21, 10, 0, tzinfo=timezone.utc)
    end = datetime(2026, 5, 21, 11, 0, tzinfo=timezone.utc)
    timestamps = _generate_15min_timestamps(start, end)
    # Should generate 10:15, 10:30, 10:45 (11:00 is exclusive)
    assert len(timestamps) == 3
    assert timestamps[0] == datetime(2026, 5, 21, 10, 15, tzinfo=timezone.utc)
    assert timestamps[-1] == datetime(2026, 5, 21, 10, 45, tzinfo=timezone.utc)


def test_parse_iso_datetime():
    """Test ISO datetime parsing."""
    # Full datetime
    dt = _parse_iso_datetime("2026-05-21T10:00:00Z", is_end=False)
    assert dt == datetime(2026, 5, 21, 10, 0, tzinfo=timezone.utc)

    # Date-only (start)
    dt = _parse_iso_datetime("2026-05-21", is_end=False)
    assert dt == datetime(2026, 5, 21, 0, 0, tzinfo=timezone.utc)

    # Date-only (end) - should add 1 day
    dt = _parse_iso_datetime("2026-05-21", is_end=True)
    assert dt == datetime(2026, 5, 22, 0, 0, tzinfo=timezone.utc)


def test_to_utc():
    """Test UTC conversion."""
    # Naive datetime
    dt = _to_utc(datetime(2026, 5, 21, 10, 0))
    assert dt.tzinfo == timezone.utc
    assert dt == datetime(2026, 5, 21, 10, 0, tzinfo=timezone.utc)

    # UTC datetime
    dt = _to_utc(datetime(2026, 5, 21, 10, 0, tzinfo=timezone.utc))
    assert dt.tzinfo == timezone.utc

    # Non-UTC datetime
    from datetime import timezone as tz
    dt = _to_utc(datetime(2026, 5, 21, 12, 0, tzinfo=tz(timedelta(hours=2))))
    assert dt == datetime(2026, 5, 21, 10, 0, tzinfo=timezone.utc)


def test_cli_import():
    """Test that the CLI module can be imported."""
    import scripts.run_multi_asset_backtest as mab
    assert hasattr(mab, "main")
    assert hasattr(mab, "_parse_args")
    assert hasattr(mab, "run_multi_asset_replay")


if __name__ == "__main__":
    test_generate_15min_timestamps()
    test_parse_iso_datetime()
    test_to_utc()
    test_cli_import()
    print("All smoke tests passed.")
