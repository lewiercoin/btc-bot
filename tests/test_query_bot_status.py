from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from scripts.query_bot_status import query_bot_state, query_recent_signals
from storage.db import init_db


def _make_conn(schema_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn, schema_path)
    return conn


def test_query_recent_signals_uses_current_schema_and_derives_block_reason() -> None:
    schema_path = Path(__file__).resolve().parents[1] / "storage" / "schema.sql"
    conn = _make_conn(schema_path)
    ts = datetime(2026, 4, 28, 7, 30, tzinfo=timezone.utc)
    try:
        conn.execute(
            """
            INSERT INTO signal_candidates (
                signal_id, timestamp, direction, setup_type, confluence_score, regime,
                reasons_json, features_json, schema_version, config_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("sig-risk", ts.isoformat(), "LONG", "sweep_reclaim", 17.2, "uptrend", "[]", "{}", "v1.0", "cfg-1"),
        )
        conn.execute(
            """
            INSERT INTO executable_signals (
                signal_id, timestamp, direction, entry_price, stop_loss, take_profit_1,
                take_profit_2, rr_ratio, governance_notes_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("sig-risk", ts.isoformat(), "LONG", 78000.0, 77500.0, 79000.0, 80000.0, 1.566, "[]"),
        )
        conn.execute(
            """
            INSERT INTO decision_outcomes (
                cycle_timestamp, outcome_group, outcome_reason, regime, config_hash, signal_id, details_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (ts.isoformat(), "risk_block", "risk_block", "uptrend", "cfg-1", "sig-risk", '{"reason":"rr_below_min:1.566"}'),
        )
        conn.commit()

        signals = query_recent_signals(conn, limit=5)
    finally:
        conn.close()

    assert len(signals) == 1
    assert signals[0]["promoted"] is True
    assert signals[0]["rr_ratio"] == 1.566
    assert signals[0]["outcome_group"] == "risk_block"
    assert signals[0]["block_reason"] == "rr_below_min:1.566"


def test_query_bot_state_reads_safe_mode_reason_from_entered_event() -> None:
    schema_path = Path(__file__).resolve().parents[1] / "storage" / "schema.sql"
    conn = _make_conn(schema_path)
    ts = datetime(2026, 4, 28, 12, 0, tzinfo=timezone.utc)
    try:
        conn.execute(
            """
            INSERT INTO bot_state (
                id, timestamp, mode, healthy, safe_mode, open_positions_count,
                consecutive_losses, daily_dd_pct, weekly_dd_pct, last_trade_at, last_error, safe_mode_entry_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (1, ts.isoformat(), "PAPER", 0, 1, 0, 0, 0.0, 0.01, None, "snapshot_build_failed", ts.isoformat()),
        )
        conn.execute(
            """
            INSERT INTO safe_mode_events (
                event_type, trigger, reason, timestamp
            ) VALUES (?, ?, ?, ?)
            """,
            ("entered", "snapshot_build_failed", "snapshot_build_failed:bookTicker", ts.isoformat()),
        )
        conn.commit()

        state = query_bot_state(conn)
    finally:
        conn.close()

    assert state is not None
    assert state["safe_mode_reason"] == "snapshot_build_failed:bookTicker"
