from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

from research_lab.backfill_sol_historical_data import (
    builder_verdict,
    checkpoint_summary,
    checkpoint_status,
    dataset_verdict,
    expected_days,
    init_sol_pilot_db,
    mark_checkpoint,
)
from research_lab.eth_historical_backfill_pilot import DayStats
from research_lab.hypotheses.spec import load_hypothesis_spec


def test_sol_checkpoint_records_done_status() -> None:
    conn = sqlite3.connect(":memory:")
    init_sol_pilot_db(conn)

    mark_checkpoint(
        conn,
        DayStats(
            day=date(2026, 5, 15),
            klines_15m=96,
            klines_4h=6,
            funding=3,
            open_interest=288,
            aggtrade_rows=10_000,
            aggtrade_buckets_60s=1440,
            aggtrade_buckets_15m=96,
            downloaded_bytes=123,
        ),
    )

    assert checkpoint_summary(conn)["DONE"] == 1
    conn.close()


def test_sol_checkpoint_records_failed_status() -> None:
    conn = sqlite3.connect(":memory:")
    init_sol_pilot_db(conn)

    mark_checkpoint(conn, DayStats(day=date(2026, 5, 15), errors=("aggtrades:404",)))

    summary = checkpoint_summary(conn)
    assert summary["FAILED"] == 1
    assert summary["failed_days"][0]["day"] == "2026-05-15"
    conn.close()


def test_builder_verdict_passes_clean_quality() -> None:
    quality = {
        "ohlc_errors": 0,
        "missing_rates": {
            "candles_15m": 0.0,
            "candles_4h": 0.0,
            "funding": 0.0,
            "open_interest": 0.0,
            "aggtrade_60s": 0.0,
            "aggtrade_15m": 0.0,
        },
    }

    assert builder_verdict(quality, {"DONE": 3, "failed_days": []}) == "PASS_SOL_BACKFILL_PILOT_FULL_BACKFILL_READY"


def test_builder_verdict_blocks_missingness() -> None:
    quality = {
        "ohlc_errors": 0,
        "missing_rates": {
            "candles_15m": 0.02,
            "candles_4h": 0.0,
            "funding": 0.0,
            "open_interest": 0.0,
            "aggtrade_60s": 0.0,
            "aggtrade_15m": 0.0,
        },
    }

    assert builder_verdict(quality, {"DONE": 3, "failed_days": []}) == "NEEDS_FIX_MISSINGNESS_ABOVE_GATE"


def test_checkpoint_status_supports_resume_skip() -> None:
    conn = sqlite3.connect(":memory:")
    init_sol_pilot_db(conn)
    day = date(2026, 5, 15)

    assert checkpoint_status(conn, day) is None
    mark_checkpoint(conn, DayStats(day=day))

    assert checkpoint_status(conn, day) == "DONE"
    conn.close()


def test_expected_days_uses_exclusive_end() -> None:
    assert expected_days(date(2022, 1, 1), date(2022, 1, 4)) == 3


def test_dataset_verdict_requires_complete_dataset() -> None:
    quality = {
        "ohlc_errors": 0,
        "missing_rates": {
            "candles_15m": 0.0,
            "candles_4h": 0.0,
            "funding": 0.0,
            "open_interest": 0.0,
            "aggtrade_60s": 0.0,
            "aggtrade_15m": 0.0,
        },
    }

    assert dataset_verdict(quality, {"DONE": 1, "failed_days": []}, complete=False) == "PARTIAL_SOL_BACKFILL_IN_PROGRESS"
    assert dataset_verdict(quality, {"DONE": 3, "failed_days": []}, complete=True) == "DATASET_COMPLETE_READY_FOR_AUDIT"


def test_sol_backfill_pilot_hypothesis_spec_is_valid() -> None:
    spec = load_hypothesis_spec(Path("research_lab/hypotheses/active/sol_historical_backfill_pilot.json"))

    assert spec.hypothesis_id == "SOL_HISTORICAL_BACKFILL_PILOT_V1"
    assert spec.hypothesis_class == "diagnostic_only"
    assert "SOL trial-00095 transfer backtest" in spec.out_of_scope


def test_sol_backfill_dataset_hypothesis_spec_is_valid() -> None:
    spec = load_hypothesis_spec(Path("research_lab/hypotheses/active/sol_historical_backfill_dataset.json"))

    assert spec.hypothesis_id == "SOL_HISTORICAL_BACKFILL_DATASET_V1"
    assert spec.hypothesis_class == "diagnostic_only"
    assert "SOL trial-00095 transfer backtest" in spec.out_of_scope
