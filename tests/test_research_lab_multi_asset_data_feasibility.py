from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from research_lab.analysis_multi_asset_data_feasibility import (
    assess_candles,
    assess_timestamp_rows,
    evaluate_symbol,
)
from research_lab.hypotheses.spec import load_hypothesis_spec


def test_assess_candles_detects_missing_duplicates_and_ohlc_errors() -> None:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows = [
        {
            "open_time": start,
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.5,
            "volume": 1.0,
        },
        {
            "open_time": start,
            "open": 102.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.5,
            "volume": 0.0,
        },
    ]

    result = assess_candles(
        "ETHUSDT_15m",
        rows,
        interval_minutes=15,
        start=start,
        end=start + timedelta(minutes=45),
    )

    assert result.expected_count == 3
    assert result.missing_count == 2
    assert result.duplicate_count == 1
    assert result.quality_errors == 1
    assert result.zero_volume_count == 1


def test_assess_timestamp_rows_checks_expected_count() -> None:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows = [{"bucket_time": start}, {"bucket_time": start + timedelta(minutes=2)}]

    result = assess_timestamp_rows("aggtrade_60s", rows, "bucket_time", expected_interval_minutes=1, expected_count=3)

    assert result.row_count == 2
    assert result.expected_count == 3
    assert result.missing_count == 1


def test_evaluate_symbol_reports_full_backfill_required_when_local_data_absent() -> None:
    quality = {
        "row_count": 100,
        "expected_count": 100,
        "missing_count": 0,
        "missing_rate": 0.0,
        "duplicate_count": 0,
        "quality_errors": 0,
        "zero_volume_count": 0,
    }
    sample = {
        "candles_15m": {"ok": True, "quality": dict(quality)},
        "candles_4h": {"ok": True, "quality": dict(quality)},
        "funding": {"ok": True, "quality": {**quality, "row_count": 21}},
        "open_interest_15m": {"ok": True, "quality": {**quality, "row_count": 200}},
        "aggtrade_60s": {"ok": True, "quality": {**quality, "row_count": 60}},
        "book_ticker": {"ok": True, "quality": {**quality, "row_count": 1, "expected_count": 1}},
        "archive_probes": {
            "klines": {"ok": True},
            "metrics": {"ok": True},
            "aggtrades": {"ok": True},
            "liquidations": {"ok": False},
        },
    }
    inventory = {"tables": {}}

    evaluation = evaluate_symbol(sample, inventory, "ETHUSDT")

    assert evaluation["builder_verdict"] == "PASS_SAMPLE_SOURCE_FEASIBLE_FULL_BACKFILL_REQUIRED"
    assert evaluation["metrics"]["local_required_tables_present"] == 0


def test_multi_asset_data_feasibility_hypothesis_spec_is_valid() -> None:
    spec = load_hypothesis_spec(Path("research_lab/hypotheses/active/multi_asset_data_feasibility.json"))

    assert spec.hypothesis_id == "multi_asset_data_feasibility_v1"
    assert spec.hypothesis_class == "diagnostic_only"
    assert "ETH or SOL strategy backtest." in spec.out_of_scope
