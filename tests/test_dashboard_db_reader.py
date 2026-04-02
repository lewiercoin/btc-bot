from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from dashboard.db_reader import read_positions_from_conn, read_status_from_conn, read_trades_from_conn
from storage.db import init_db
from storage.repositories import insert_position, insert_trade_log_open, upsert_bot_state


def _make_conn(schema_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn, schema_path)
    return conn


def test_read_status_from_conn_returns_null_payload_when_state_missing(tmp_path: Path) -> None:
    schema_path = Path(__file__).resolve().parents[1] / "storage" / "schema.sql"
    conn = _make_conn(schema_path)
    try:
        payload = read_status_from_conn(conn)
    finally:
        conn.close()

    assert payload["bot_state"] is None
    assert payload["uptime_seconds"] is None
    assert payload["dashboard_version"] == "m1"


def test_read_status_positions_and_trades_from_conn() -> None:
    schema_path = Path(__file__).resolve().parents[1] / "storage" / "schema.sql"
    conn = _make_conn(schema_path)
    opened_at = datetime(2026, 4, 2, 10, 0, tzinfo=timezone.utc)
    closed_at = datetime(2026, 4, 2, 12, 30, tzinfo=timezone.utc)

    try:
        upsert_bot_state(
            conn,
            state=SimpleNamespace(
                mode="PAPER",
                healthy=True,
                safe_mode=False,
                open_positions_count=1,
                consecutive_losses=2,
                daily_dd_pct=0.01,
                weekly_dd_pct=0.02,
                last_trade_at=closed_at,
                last_error=None,
            ),
            timestamp=closed_at,
        )
        conn.execute(
            """
            INSERT INTO signal_candidates (
                signal_id, timestamp, direction, setup_type, confluence_score, regime,
                reasons_json, features_json, schema_version, config_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("sig-1", opened_at.isoformat(), "LONG", "test", 3.0, "normal", "[]", "{}", "v1.0", "abc"),
        )
        conn.execute(
            """
            INSERT INTO signal_candidates (
                signal_id, timestamp, direction, setup_type, confluence_score, regime,
                reasons_json, features_json, schema_version, config_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("sig-closed", opened_at.isoformat(), "LONG", "test", 3.0, "normal", "[]", "{}", "v1.0", "abc"),
        )
        conn.execute(
            """
            INSERT INTO executable_signals (
                signal_id, timestamp, direction, entry_price, stop_loss, take_profit_1,
                take_profit_2, rr_ratio, governance_notes_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("sig-1", opened_at.isoformat(), "LONG", 83000.0, 82000.0, 84000.0, 85000.0, 3.0, "[]"),
        )
        conn.execute(
            """
            INSERT INTO executable_signals (
                signal_id, timestamp, direction, entry_price, stop_loss, take_profit_1,
                take_profit_2, rr_ratio, governance_notes_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("sig-closed", opened_at.isoformat(), "LONG", 83000.0, 82000.0, 84000.0, 85000.0, 3.0, "[]"),
        )
        insert_position(
            conn,
            position_id="pos-1",
            signal_id="sig-1",
            symbol="BTCUSDT",
            direction="LONG",
            status="OPEN",
            entry_price=83000.0,
            size=0.1,
            leverage=2,
            stop_loss=82000.0,
            take_profit_1=84000.0,
            take_profit_2=85000.0,
            opened_at=opened_at,
            updated_at=opened_at,
        )
        insert_position(
            conn,
            position_id="pos-closed",
            signal_id="sig-closed",
            symbol="BTCUSDT",
            direction="LONG",
            status="CLOSED",
            entry_price=83000.0,
            size=0.1,
            leverage=2,
            stop_loss=82000.0,
            take_profit_1=84000.0,
            take_profit_2=85000.0,
            opened_at=opened_at,
            updated_at=closed_at,
        )
        insert_trade_log_open(
            conn,
            trade_id="trd-1",
            signal_id="sig-closed",
            position_id="pos-closed",
            opened_at=opened_at,
            direction="LONG",
            regime="normal",
            confluence_score=3.4,
            entry_price=83000.0,
            size=0.1,
            features_at_entry_json={},
            schema_version="v1.0",
            config_hash="abc",
        )
        conn.execute(
            """
            UPDATE trade_log
            SET position_id = ?, exit_price = ?, pnl_abs = ?, pnl_r = ?, closed_at = ?, exit_reason = ?
            WHERE trade_id = ?
            """,
            ("pos-closed", 83500.0, 50.0, 0.5, closed_at.isoformat(), "tp1", "trd-1"),
        )
        conn.commit()

        status_payload = read_status_from_conn(conn)
        positions_payload = read_positions_from_conn(conn, now=closed_at)
        trades_payload = read_trades_from_conn(conn, limit=20)
    finally:
        conn.close()

    assert status_payload["bot_state"] is not None
    assert status_payload["bot_state"]["mode"] == "PAPER"
    assert status_payload["bot_state"]["healthy"] is True
    assert status_payload["bot_state"]["state_timestamp"] == closed_at.isoformat()

    assert len(positions_payload["positions"]) == 1
    assert positions_payload["positions"][0]["position_id"] == "pos-1"
    assert positions_payload["positions"][0]["direction"] == "LONG"
    assert positions_payload["data_age_seconds"] == (closed_at - opened_at).total_seconds()

    assert len(trades_payload["trades"]) == 1
    assert trades_payload["trades"][0]["trade_id"] == "trd-1"
    assert trades_payload["trades"][0]["outcome"] == "WIN"
    assert trades_payload["trades"][0]["closed_at"] == closed_at.isoformat()
