"""Test quant-grade lineage: per-input timestamps and build timing persistence."""

import sqlite3
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, Mock

import pytest

from core.models import MarketSnapshot
from storage.state_store import StateStore


@pytest.fixture
def in_memory_db():
    conn = sqlite3.connect(":memory:")
    yield conn
    conn.close()


@pytest.fixture
def state_store(in_memory_db):
    return StateStore(connection=in_memory_db, mode="paper")


def test_quant_grade_lineage_schema_created(state_store):
    """Verify quant-grade lineage columns exist in market_snapshots table."""
    # Trigger migrations explicitly
    state_store._apply_migrations()

    cursor = state_store.connection.cursor()
    cursor.execute("PRAGMA table_info(market_snapshots)")
    columns = {row[1] for row in cursor.fetchall()}

    # Per-input exchange timestamps
    assert "candles_15m_exchange_ts" in columns
    assert "candles_1h_exchange_ts" in columns
    assert "candles_4h_exchange_ts" in columns
    assert "funding_exchange_ts" in columns
    assert "oi_exchange_ts" in columns
    assert "aggtrades_exchange_ts" in columns

    # Build timing
    assert "snapshot_build_started_at" in columns
    assert "snapshot_build_finished_at" in columns


def test_quant_grade_lineage_persistence(state_store):
    """Verify per-input timestamps and build timing are persisted correctly."""
    now = datetime.now(timezone.utc)
    build_start = now - timedelta(seconds=3)
    build_finish = now

    candles_15m_ts = now - timedelta(minutes=5)
    candles_1h_ts = now - timedelta(hours=1)
    candles_4h_ts = now - timedelta(hours=4)
    funding_ts = now - timedelta(hours=8)
    oi_ts = now - timedelta(seconds=1)
    aggtrades_ts = now - timedelta(seconds=2)

    snapshot = MarketSnapshot(
        symbol="BTCUSDT",
        timestamp=now,
        price=50000.0,
        bid=49995.0,
        ask=50005.0,
        candles_15m=[{"open_time": candles_15m_ts, "open": 50000, "high": 50100, "low": 49900, "close": 50050, "volume": 1000}],
        candles_1h=[{"open_time": candles_1h_ts, "open": 49800, "high": 50200, "low": 49700, "close": 50000, "volume": 5000}],
        candles_4h=[{"open_time": candles_4h_ts, "open": 49500, "high": 50300, "low": 49400, "close": 50000, "volume": 20000}],
        funding_history=[{"funding_time": funding_ts, "funding_rate": 0.0001}],
        open_interest_payload={"timestamp": oi_ts, "oi_value": 1000000},
        aggtrade_events_15m=[{"event_time": aggtrades_ts, "price": 50000, "qty": 1.0, "is_buyer_maker": True}],
        # Quant-grade lineage fields
        candles_15m_exchange_ts=candles_15m_ts,
        candles_1h_exchange_ts=candles_1h_ts,
        candles_4h_exchange_ts=candles_4h_ts,
        funding_exchange_ts=funding_ts,
        oi_exchange_ts=oi_ts,
        aggtrades_exchange_ts=aggtrades_ts,
        snapshot_build_started_at=build_start,
        snapshot_build_finished_at=build_finish,
    )

    snapshot_id = state_store.record_market_snapshot(snapshot)

    # Verify persistence
    cursor = state_store.connection.cursor()
    cursor.execute(
        """
        SELECT
            candles_15m_exchange_ts,
            candles_1h_exchange_ts,
            candles_4h_exchange_ts,
            funding_exchange_ts,
            oi_exchange_ts,
            aggtrades_exchange_ts,
            snapshot_build_started_at,
            snapshot_build_finished_at
        FROM market_snapshots
        WHERE snapshot_id = ?
        """,
        (snapshot_id,),
    )
    row = cursor.fetchone()
    assert row is not None

    # Parse timestamps
    (
        persisted_15m_ts,
        persisted_1h_ts,
        persisted_4h_ts,
        persisted_funding_ts,
        persisted_oi_ts,
        persisted_aggtrades_ts,
        persisted_build_start,
        persisted_build_finish,
    ) = row

    # Verify each timestamp was persisted correctly
    assert persisted_15m_ts == candles_15m_ts.isoformat()
    assert persisted_1h_ts == candles_1h_ts.isoformat()
    assert persisted_4h_ts == candles_4h_ts.isoformat()
    assert persisted_funding_ts == funding_ts.isoformat()
    assert persisted_oi_ts == oi_ts.isoformat()
    assert persisted_aggtrades_ts == aggtrades_ts.isoformat()
    assert persisted_build_start == build_start.isoformat()
    assert persisted_build_finish == build_finish.isoformat()


def test_quant_grade_lineage_nullable(state_store):
    """Verify quant-grade lineage fields are nullable (backward compatible)."""
    now = datetime.now(timezone.utc)

    snapshot = MarketSnapshot(
        symbol="BTCUSDT",
        timestamp=now,
        price=50000.0,
        bid=49995.0,
        ask=50005.0,
        # No quant-grade fields provided
    )

    snapshot_id = state_store.record_market_snapshot(snapshot)

    # Verify NULL persistence
    cursor = state_store.connection.cursor()
    cursor.execute(
        """
        SELECT
            candles_15m_exchange_ts,
            snapshot_build_started_at
        FROM market_snapshots
        WHERE snapshot_id = ?
        """,
        (snapshot_id,),
    )
    row = cursor.fetchone()
    assert row is not None
    assert row[0] is None  # candles_15m_exchange_ts
    assert row[1] is None  # snapshot_build_started_at


def test_quant_grade_lineage_enables_staleness_check(state_store):
    """Verify per-input timestamps enable staleness detection."""
    now = datetime.now(timezone.utc)
    stale_candles_ts = now - timedelta(minutes=20)  # Stale: 15m candle older than expected
    fresh_oi_ts = now - timedelta(seconds=5)  # Fresh: OI just updated

    snapshot = MarketSnapshot(
        symbol="BTCUSDT",
        timestamp=now,
        price=50000.0,
        bid=49995.0,
        ask=50005.0,
        candles_15m_exchange_ts=stale_candles_ts,
        oi_exchange_ts=fresh_oi_ts,
        snapshot_build_started_at=now - timedelta(seconds=2),
        snapshot_build_finished_at=now,
    )

    snapshot_id = state_store.record_market_snapshot(snapshot)

    # Simulate staleness check query
    cursor = state_store.connection.cursor()
    cursor.execute(
        """
        SELECT
            cycle_timestamp,
            candles_15m_exchange_ts,
            oi_exchange_ts,
            (julianday(cycle_timestamp) - julianday(candles_15m_exchange_ts)) * 86400 AS candles_staleness_sec,
            (julianday(cycle_timestamp) - julianday(oi_exchange_ts)) * 86400 AS oi_staleness_sec
        FROM market_snapshots
        WHERE snapshot_id = ?
        """,
        (snapshot_id,),
    )
    row = cursor.fetchone()
    assert row is not None

    candles_staleness = row[3]
    oi_staleness = row[4]

    # Verify staleness calculation
    assert candles_staleness > 900  # >15 minutes stale
    assert oi_staleness < 10  # <10 seconds fresh


def test_quant_grade_lineage_enables_build_timing_audit(state_store):
    """Verify build timing fields enable snapshot construction latency audit."""
    now = datetime.now(timezone.utc)
    build_start = now - timedelta(seconds=2.5)
    build_finish = now

    snapshot = MarketSnapshot(
        symbol="BTCUSDT",
        timestamp=now,
        price=50000.0,
        bid=49995.0,
        ask=50005.0,
        snapshot_build_started_at=build_start,
        snapshot_build_finished_at=build_finish,
    )

    snapshot_id = state_store.record_market_snapshot(snapshot)

    # Simulate build timing audit query
    cursor = state_store.connection.cursor()
    cursor.execute(
        """
        SELECT
            snapshot_id,
            (julianday(snapshot_build_finished_at) - julianday(snapshot_build_started_at)) * 86400 AS build_duration_sec
        FROM market_snapshots
        WHERE snapshot_id = ?
        """,
        (snapshot_id,),
    )
    row = cursor.fetchone()
    assert row is not None

    build_duration = row[1]

    # Verify build timing calculation
    assert 2.4 < build_duration < 2.6  # ~2.5 seconds
