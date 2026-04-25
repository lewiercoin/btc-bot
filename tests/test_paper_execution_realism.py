from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from core.execution_types import ExecutionStatus
from core.models import ExecutableSignal
from execution.paper_execution_engine import PaperExecutionEngine
from storage.db import init_db
from storage.position_persister import SqlitePositionPersister


def _schema_path() -> Path:
    return Path(__file__).resolve().parents[1] / "storage" / "schema.sql"


def _make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn, _schema_path())
    return conn


def _make_executable(direction: str = "LONG") -> ExecutableSignal:
    return ExecutableSignal(
        signal_id="sig-test",
        timestamp=datetime.now(timezone.utc),
        direction=direction,
        entry_price=100.0,
        stop_loss=95.0,
        take_profit_1=110.0,
        take_profit_2=120.0,
        rr_ratio=2.0,
        approved_by_governance=True,
        governance_notes=["approved"],
    )


def test_paper_execution_charges_fees():
    """Paper execution now charges 0.04% fees (matching backtest SimpleFillModel)."""
    conn = _make_conn()
    persister = SqlitePositionPersister(conn)
    engine = PaperExecutionEngine(position_persister=persister, symbol="BTCUSDT")

    signal = _make_executable(direction="LONG")
    # Insert signal_candidate and executable_signal to satisfy FK constraints
    conn.execute(
        "INSERT INTO signal_candidates (signal_id, timestamp, direction, setup_type, confluence_score, regime, reasons_json, features_json, schema_version, config_hash) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (signal.signal_id, signal.timestamp.isoformat(), signal.direction, "test", 1.0, "NORMAL", "[]", "{}", "v1", "test"),
    )
    conn.execute(
        "INSERT INTO executable_signals (signal_id, timestamp, direction, entry_price, stop_loss, take_profit_1, take_profit_2, rr_ratio, governance_notes_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (signal.signal_id, signal.timestamp.isoformat(), signal.direction, signal.entry_price, signal.stop_loss, signal.take_profit_1, signal.take_profit_2, signal.rr_ratio, "[]"),
    )
    conn.commit()

    engine.execute_signal(
        signal,
        size=1.0,
        leverage=5,
        snapshot_price=100.0,
        bid_price=99.95,
        ask_price=100.05,
        snapshot_id="snap-123",
    )

    cursor = conn.execute("SELECT fees, filled_price FROM executions LIMIT 1")
    row = cursor.fetchone()
    assert row is not None

    # LONG = BUY, should fill at ask_price=100.05
    filled_price = row["filled_price"]
    assert abs(filled_price - 100.05) < 1e-6, f"Expected fill at ask 100.05, got {filled_price}"

    # Fees should be 0.04% of notional = 0.0004 * (100.05 * 1.0) = 0.04002
    fees = row["fees"]
    expected_fees = 0.0004 * (100.05 * 1.0)
    assert abs(fees - expected_fees) < 1e-6, f"Expected fees ~{expected_fees:.6f}, got {fees:.6f}"


def test_paper_execution_uses_bid_ask_spread():
    """Paper execution uses bid/ask spread: BUY at ask, SELL at bid."""
    conn = _make_conn()
    persister = SqlitePositionPersister(conn)
    engine = PaperExecutionEngine(position_persister=persister, symbol="BTCUSDT")

    # Test LONG (BUY): should fill at ask
    signal_long = _make_executable(direction="LONG")
    conn.execute(
        "INSERT INTO signal_candidates (signal_id, timestamp, direction, setup_type, confluence_score, regime, reasons_json, features_json, schema_version, config_hash) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (signal_long.signal_id, signal_long.timestamp.isoformat(), signal_long.direction, "test", 1.0, "NORMAL", "[]", "{}", "v1", "test"),
    )
    conn.execute(
        "INSERT INTO executable_signals (signal_id, timestamp, direction, entry_price, stop_loss, take_profit_1, take_profit_2, rr_ratio, governance_notes_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (signal_long.signal_id, signal_long.timestamp.isoformat(), signal_long.direction, signal_long.entry_price, signal_long.stop_loss, signal_long.take_profit_1, signal_long.take_profit_2, signal_long.rr_ratio, "[]"),
    )
    conn.commit()

    engine.execute_signal(
        signal_long,
        size=1.0,
        leverage=5,
        snapshot_price=100.0,
        bid_price=99.95,
        ask_price=100.05,
        snapshot_id="snap-123",
    )

    cursor = conn.execute("SELECT filled_price, side FROM executions WHERE side='BUY' LIMIT 1")
    row_long = cursor.fetchone()
    assert row_long is not None
    assert abs(row_long["filled_price"] - 100.05) < 1e-6, "LONG should fill at ask"

    # Test SHORT (SELL): should fill at bid
    signal_short = _make_executable(direction="SHORT")
    signal_short.signal_id = "sig-short"
    conn.execute(
        "INSERT INTO signal_candidates (signal_id, timestamp, direction, setup_type, confluence_score, regime, reasons_json, features_json, schema_version, config_hash) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (signal_short.signal_id, signal_short.timestamp.isoformat(), signal_short.direction, "test", 1.0, "NORMAL", "[]", "{}", "v1", "test"),
    )
    conn.execute(
        "INSERT INTO executable_signals (signal_id, timestamp, direction, entry_price, stop_loss, take_profit_1, take_profit_2, rr_ratio, governance_notes_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (signal_short.signal_id, signal_short.timestamp.isoformat(), signal_short.direction, signal_short.entry_price, signal_short.stop_loss, signal_short.take_profit_1, signal_short.take_profit_2, signal_short.rr_ratio, "[]"),
    )
    conn.commit()

    engine.execute_signal(
        signal_short,
        size=1.0,
        leverage=5,
        snapshot_price=100.0,
        bid_price=99.95,
        ask_price=100.05,
        snapshot_id="snap-456",
    )

    cursor = conn.execute("SELECT filled_price, side FROM executions WHERE side='SELL' LIMIT 1")
    row_short = cursor.fetchone()
    assert row_short is not None
    assert abs(row_short["filled_price"] - 99.95) < 1e-6, "SHORT should fill at bid"


def test_paper_execution_links_to_snapshot():
    """Paper execution now links to market_snapshots via snapshot_id FK."""
    conn = _make_conn()
    persister = SqlitePositionPersister(conn)
    engine = PaperExecutionEngine(position_persister=persister, symbol="BTCUSDT")

    signal = _make_executable()
    conn.execute(
        "INSERT INTO signal_candidates (signal_id, timestamp, direction, setup_type, confluence_score, regime, reasons_json, features_json, schema_version, config_hash) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (signal.signal_id, signal.timestamp.isoformat(), signal.direction, "test", 1.0, "NORMAL", "[]", "{}", "v1", "test"),
    )
    conn.execute(
        "INSERT INTO executable_signals (signal_id, timestamp, direction, entry_price, stop_loss, take_profit_1, take_profit_2, rr_ratio, governance_notes_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (signal.signal_id, signal.timestamp.isoformat(), signal.direction, signal.entry_price, signal.stop_loss, signal.take_profit_1, signal.take_profit_2, signal.rr_ratio, "[]"),
    )
    conn.commit()

    engine.execute_signal(
        signal,
        size=1.0,
        leverage=5,
        snapshot_price=100.0,
        bid_price=99.95,
        ask_price=100.05,
        snapshot_id="snap-789",
    )

    cursor = conn.execute("SELECT snapshot_id FROM executions LIMIT 1")
    row = cursor.fetchone()
    assert row is not None
    assert row["snapshot_id"] == "snap-789", "Execution should link to snapshot_id"


def test_paper_execution_fallback_to_snapshot_price():
    """If bid/ask not available, paper execution falls back to snapshot_price."""
    conn = _make_conn()
    persister = SqlitePositionPersister(conn)
    engine = PaperExecutionEngine(position_persister=persister, symbol="BTCUSDT")

    signal = _make_executable(direction="LONG")
    conn.execute(
        "INSERT INTO signal_candidates (signal_id, timestamp, direction, setup_type, confluence_score, regime, reasons_json, features_json, schema_version, config_hash) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (signal.signal_id, signal.timestamp.isoformat(), signal.direction, "test", 1.0, "NORMAL", "[]", "{}", "v1", "test"),
    )
    conn.execute(
        "INSERT INTO executable_signals (signal_id, timestamp, direction, entry_price, stop_loss, take_profit_1, take_profit_2, rr_ratio, governance_notes_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (signal.signal_id, signal.timestamp.isoformat(), signal.direction, signal.entry_price, signal.stop_loss, signal.take_profit_1, signal.take_profit_2, signal.rr_ratio, "[]"),
    )
    conn.commit()

    engine.execute_signal(
        signal,
        size=1.0,
        leverage=5,
        snapshot_price=100.0,
        bid_price=None,  # No bid/ask available
        ask_price=None,
        snapshot_id=None,
    )

    cursor = conn.execute("SELECT filled_price FROM executions LIMIT 1")
    row = cursor.fetchone()
    assert row is not None
    assert abs(row["filled_price"] - 100.0) < 1e-6, "Should fallback to snapshot_price if bid/ask missing"
