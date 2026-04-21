from __future__ import annotations

import sqlite3
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from core.feature_engine import FeatureEngine, FeatureEngineConfig
from core.models import MarketSnapshot
from scripts import backfill_cvd_history, backfill_oi_samples, run_backfill
from settings import DataQualityConfig, load_settings
from storage.db import init_db
from storage.repositories import fetch_cvd_price_history, fetch_oi_samples


class FakeOIRestClient:
    def __init__(self, now: datetime, *, fail: bool = False) -> None:
        self.now = now
        self.fail = fail

    def fetch_open_interest(self, symbol: str) -> dict[str, Any]:
        if self.fail:
            raise RuntimeError("forced_oi_failure")
        return {"symbol": symbol, "timestamp": self.now, "oi_value": 160.0}


class FakeCVDRestClient:
    def __init__(self, bars: list[dict[str, Any]], *, fail: bool = False) -> None:
        self.bars = bars
        self.fail = fail

    def fetch_klines(self, symbol: str, interval: str, limit: int = 500) -> list[dict[str, Any]]:
        _ = symbol
        _ = interval
        if self.fail:
            raise RuntimeError("forced_kline_failure")
        return self.bars[-limit:]


def _settings() -> Any:
    return replace(
        load_settings(),
        data_quality=DataQualityConfig(oi_baseline_days=60, cvd_divergence_bars=30),
    )


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn, Path("storage/schema.sql"))
    return conn


def _seed_open_interest(conn: sqlite3.Connection, now: datetime) -> None:
    rows = [
        (now - timedelta(days=60), 100.0),
        (now - timedelta(days=30), 120.0),
        (now - timedelta(days=4), 140.0),
    ]
    for ts, value in rows:
        conn.execute(
            """
            INSERT INTO open_interest (symbol, timestamp, oi_value)
            VALUES (?, ?, ?)
            """,
            ("BTCUSDT", ts.isoformat(), value),
        )
    conn.commit()


def _make_klines(now: datetime, count: int = 30) -> list[dict[str, Any]]:
    first = now - timedelta(minutes=15 * (count - 1))
    return [
        {
            "symbol": "BTCUSDT",
            "timeframe": "15m",
            "open_time": first + timedelta(minutes=15 * idx),
            "open": 100.0 + idx,
            "high": 101.0 + idx,
            "low": 99.0 + idx,
            "close": 100.5 + idx,
            "volume": 10.0 + idx,
        }
        for idx in range(count)
    ]


def _seed_aggtrade_buckets(conn: sqlite3.Connection, bars: list[dict[str, Any]], *, skip_every: int | None = None) -> None:
    for idx, bar in enumerate(bars):
        if skip_every is not None and idx % skip_every == 0:
            continue
        conn.execute(
            """
            INSERT INTO aggtrade_buckets (
                symbol, bucket_time, timeframe, taker_buy_volume, taker_sell_volume, tfi, cvd
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "BTCUSDT",
                bar["open_time"].isoformat(),
                "15m",
                10.0 + idx,
                8.0 + idx,
                0.1,
                float(idx + 1),
            ),
        )
    conn.commit()


def _seed_local_candles(conn: sqlite3.Connection, bars: list[dict[str, Any]]) -> None:
    for bar in bars:
        conn.execute(
            """
            INSERT INTO candles (symbol, timeframe, open_time, open, high, low, close, volume)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "BTCUSDT",
                "15m",
                bar["open_time"].isoformat(),
                float(bar["open"]),
                float(bar["high"]),
                float(bar["low"]),
                float(bar["close"]),
                float(bar["volume"]),
            ),
        )
    conn.commit()


def test_backfill_oi_on_empty_table() -> None:
    now = datetime(2026, 4, 21, 12, 0, tzinfo=timezone.utc)
    conn = _conn()
    try:
        _seed_open_interest(conn, now)
        result = backfill_oi_samples.run_backfill(
            conn=conn,
            settings=_settings(),
            rest_client=FakeOIRestClient(now),
            now=now,
        )
        rows = fetch_oi_samples(conn, symbol="BTCUSDT")
    finally:
        conn.close()

    assert result.ready is True
    assert result.days_covered == 60.0
    assert result.inserted_historical == 3
    assert result.inserted_current == 1
    assert len(rows) == 4


def test_backfill_oi_idempotent() -> None:
    now = datetime(2026, 4, 21, 12, 0, tzinfo=timezone.utc)
    conn = _conn()
    try:
        _seed_open_interest(conn, now)
        kwargs = {"conn": conn, "settings": _settings(), "rest_client": FakeOIRestClient(now), "now": now}
        backfill_oi_samples.run_backfill(**kwargs)
        first_count = conn.execute("SELECT COUNT(*) AS cnt FROM oi_samples").fetchone()["cnt"]
        second = backfill_oi_samples.run_backfill(**kwargs)
        second_count = conn.execute("SELECT COUNT(*) AS cnt FROM oi_samples").fetchone()["cnt"]
    finally:
        conn.close()

    assert first_count == 4
    assert second_count == first_count
    assert second.inserted_historical == 0
    assert second.inserted_current == 0


def test_backfill_cvd_on_empty_table() -> None:
    now = datetime(2026, 4, 21, 12, 0, tzinfo=timezone.utc)
    bars = _make_klines(now)
    conn = _conn()
    try:
        _seed_aggtrade_buckets(conn, bars)
        result = backfill_cvd_history.run_backfill(
            conn=conn,
            settings=_settings(),
            rest_client=FakeCVDRestClient(bars),
            now=now,
        )
        rows = fetch_cvd_price_history(conn, symbol="BTCUSDT", timeframe="15m", limit=40)
    finally:
        conn.close()

    assert result.ready is True
    assert result.inserted_bars == 30
    assert result.real_cvd_bars == 30
    assert result.placeholder_bars == 0
    assert len(rows) == 30
    assert rows[-1]["price_close"] == bars[-1]["close"]


def test_backfill_cvd_idempotent() -> None:
    now = datetime(2026, 4, 21, 12, 0, tzinfo=timezone.utc)
    bars = _make_klines(now)
    conn = _conn()
    try:
        _seed_aggtrade_buckets(conn, bars)
        kwargs = {"conn": conn, "settings": _settings(), "rest_client": FakeCVDRestClient(bars), "now": now}
        backfill_cvd_history.run_backfill(**kwargs)
        first_count = conn.execute("SELECT COUNT(*) AS cnt FROM cvd_price_history").fetchone()["cnt"]
        second = backfill_cvd_history.run_backfill(**kwargs)
        second_count = conn.execute("SELECT COUNT(*) AS cnt FROM cvd_price_history").fetchone()["cnt"]
    finally:
        conn.close()

    assert first_count == 30
    assert second_count == first_count
    assert second.inserted_bars == 0


def test_backfill_cvd_uses_placeholder_for_aggtrade_gaps() -> None:
    now = datetime(2026, 4, 21, 12, 0, tzinfo=timezone.utc)
    bars = _make_klines(now)
    conn = _conn()
    try:
        _seed_aggtrade_buckets(conn, bars, skip_every=3)
        result = backfill_cvd_history.run_backfill(
            conn=conn,
            settings=_settings(),
            rest_client=FakeCVDRestClient(bars),
            now=now,
        )
        placeholder_count = conn.execute(
            "SELECT COUNT(*) AS cnt FROM cvd_price_history WHERE cvd = 0.0 AND tfi IS NULL"
        ).fetchone()["cnt"]
    finally:
        conn.close()

    assert result.placeholder_bars == 10
    assert placeholder_count == 10


def test_backfill_cvd_falls_back_to_local_candles_when_rest_fails() -> None:
    now = datetime(2026, 4, 21, 12, 0, tzinfo=timezone.utc)
    bars = _make_klines(now)
    conn = _conn()
    try:
        _seed_local_candles(conn, bars)
        result = backfill_cvd_history.run_backfill(
            conn=conn,
            settings=_settings(),
            rest_client=FakeCVDRestClient([], fail=True),
            now=now,
        )
    finally:
        conn.close()

    assert result.ready is True
    assert result.used_rest_klines is False
    assert result.rest_error == "forced_kline_failure"
    assert result.placeholder_bars == 30


def test_run_backfill_reports_ready_and_bootstrap_quality_ready() -> None:
    now = datetime(2026, 4, 21, 12, 0, tzinfo=timezone.utc)
    bars = _make_klines(now)
    conn = _conn()
    try:
        settings = _settings()
        _seed_open_interest(conn, now)
        _seed_aggtrade_buckets(conn, bars)
        readiness = run_backfill.run_all(
            conn=conn,
            settings=settings,
            oi_rest_client=FakeOIRestClient(now),
            cvd_rest_client=FakeCVDRestClient(bars),
            now=now,
        )
        oi_rows = fetch_oi_samples(conn, symbol="BTCUSDT", since_ts=now - timedelta(days=60))
        cvd_rows = fetch_cvd_price_history(conn, symbol="BTCUSDT", timeframe="15m", limit=30)
    finally:
        conn.close()

    engine = FeatureEngine(
        FeatureEngineConfig(
            oi_baseline_days=60,
            oi_z_window_days=60,
            cvd_divergence_bars=30,
            cvd_divergence_window_bars=30,
        )
    )
    engine.bootstrap_oi_history(oi_rows)
    engine.bootstrap_cvd_price_history(cvd_rows)
    features = engine.compute(
        MarketSnapshot(
            symbol="BTCUSDT",
            timestamp=now,
            price=130.0,
            bid=129.5,
            ask=130.5,
            open_interest=160.0,
            aggtrades_bucket_15m={"cvd": 2.0},
        ),
        "v1.0",
        "hash",
    )

    assert readiness.ready is True
    assert features.quality["oi_baseline"].status == "ready"
    assert features.quality["cvd_divergence"].status == "ready"
