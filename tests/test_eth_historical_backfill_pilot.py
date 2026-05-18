from __future__ import annotations

import io
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from research_lab.eth_historical_backfill_pilot import (
    aggregate_aggtrades,
    assert_safe_output_path,
    parse_klines,
    parse_metrics_oi,
)
from research_lab.hypotheses.spec import load_hypothesis_spec


def _zip_csv(name: str, body: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(name, body)
    return buffer.getvalue()


def test_parse_klines_skips_header_and_normalizes_rows() -> None:
    payload = _zip_csv(
        "ETHUSDT-15m-2026-01-01.csv",
        "open_time,open,high,low,close,volume\n"
        "1767225600000,100,110,90,105,12.5\n",
    )

    rows = parse_klines(payload, symbol="ETHUSDT", timeframe="15m")

    assert len(rows) == 1
    assert rows[0]["symbol"] == "ETHUSDT"
    assert rows[0]["open_time"] == datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert rows[0]["high"] == 110.0


def test_parse_metrics_oi_reads_sum_open_interest() -> None:
    payload = _zip_csv(
        "ETHUSDT-metrics-2026-01-01.csv",
        "create_time,sum_open_interest\n2026-01-01 00:00:00,12345.5\n",
    )

    rows = parse_metrics_oi(payload, symbol="ETHUSDT")

    assert len(rows) == 1
    assert rows[0]["timestamp"] == datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert rows[0]["oi_value"] == 12345.5


def test_aggregate_aggtrades_builds_60s_and_15m_buckets() -> None:
    payload = _zip_csv(
        "ETHUSDT-aggTrades-2026-01-01.csv",
        "agg_trade_id,price,quantity,first_trade_id,last_trade_id,transact_time,is_buyer_maker\n"
        "1,100,2.0,10,10,1767225600000,false\n"
        "2,101,1.0,11,11,1767225660000,true\n",
    )

    rows_60s, rows_15m, trade_count = aggregate_aggtrades(payload, symbol="ETHUSDT")

    assert trade_count == 2
    assert len(rows_60s) == 2
    assert len(rows_15m) == 1
    assert rows_15m[0]["taker_buy_volume"] == 2.0
    assert rows_15m[0]["taker_sell_volume"] == 1.0


def test_safe_output_path_rejects_runtime_storage() -> None:
    with pytest.raises(SystemExit):
        assert_safe_output_path(Path("storage/btc_bot.db"))


def test_eth_backfill_pilot_hypothesis_spec_is_valid() -> None:
    spec = load_hypothesis_spec(Path("research_lab/hypotheses/active/eth_historical_backfill_pilot.json"))

    assert spec.hypothesis_id == "eth_historical_backfill_pilot_v1"
    assert spec.hypothesis_class == "diagnostic_only"
    assert "ETH strategy backtest." in spec.out_of_scope
