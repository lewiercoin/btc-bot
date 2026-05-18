from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

from research_lab.eth_historical_backfill_dataset import (
    checkpoint_status,
    expected_days,
    init_dataset_tables,
    mark_finished,
    mark_started,
)
from research_lab.eth_historical_backfill_pilot import DayStats
from research_lab.hypotheses.spec import load_hypothesis_spec


def test_checkpoint_lifecycle_records_done_status() -> None:
    conn = sqlite3.connect(":memory:")
    init_dataset_tables(conn)
    day = date(2026, 1, 1)

    mark_started(conn, day)
    assert checkpoint_status(conn, day) == "RUNNING"

    mark_finished(
        conn,
        DayStats(
            day=day,
            klines_15m=96,
            klines_4h=6,
            funding=3,
            open_interest=288,
            aggtrade_rows=1000,
            aggtrade_buckets_60s=1440,
            aggtrade_buckets_15m=96,
            downloaded_bytes=123,
        ),
    )

    assert checkpoint_status(conn, day) == "DONE"
    conn.close()


def test_checkpoint_lifecycle_marks_errors_as_failed() -> None:
    conn = sqlite3.connect(":memory:")
    init_dataset_tables(conn)
    day = date(2026, 1, 1)

    mark_started(conn, day)
    mark_finished(conn, DayStats(day=day, errors=("aggtrades:404",)))

    assert checkpoint_status(conn, day) == "FAILED"
    conn.close()


def test_expected_days_uses_exclusive_end() -> None:
    assert expected_days(date(2026, 1, 1), date(2026, 1, 4)) == 3


def test_eth_backfill_dataset_hypothesis_spec_is_valid() -> None:
    spec = load_hypothesis_spec(Path("research_lab/hypotheses/active/eth_historical_backfill_dataset.json"))

    assert spec.hypothesis_id == "eth_historical_backfill_dataset_v1"
    assert spec.hypothesis_class == "diagnostic_only"
    assert "ETH trial-00095 transfer backtest." in spec.out_of_scope
