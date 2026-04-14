from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from dashboard.db_reader import (
    read_alerts_from_conn,
    read_daily_metrics_from_conn,
    read_positions_from_conn,
    read_signals_from_conn,
    read_status_from_conn,
    read_trades_from_conn,
)
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
    assert trades_payload["trades"][0]["regime"] == "normal"
    assert trades_payload["trades"][0]["confluence_score"] == 3.4
    assert trades_payload["trades"][0]["exit_reason"] == "tp1"
    assert trades_payload["trades"][0]["fees_total"] == 0.0


def test_read_signals_from_conn_empty() -> None:
    schema_path = Path(__file__).resolve().parents[1] / "storage" / "schema.sql"
    conn = _make_conn(schema_path)
    try:
        payload = read_signals_from_conn(conn)
    finally:
        conn.close()
    assert payload["signals"] == []


def test_read_signals_from_conn_with_candidate_and_executable() -> None:
    schema_path = Path(__file__).resolve().parents[1] / "storage" / "schema.sql"
    conn = _make_conn(schema_path)
    ts = datetime(2026, 4, 13, 12, 0, tzinfo=timezone.utc)
    try:
        conn.execute(
            """
            INSERT INTO signal_candidates (
                signal_id, timestamp, direction, setup_type, confluence_score, regime,
                reasons_json, features_json, schema_version, config_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("sig-a", ts.isoformat(), "SHORT", "sweep_reclaim", 5.2, "downtrend",
             '["cvd_divergence", "reclaim_confirmed"]', "{}", "v1.0", "hash-abc"),
        )
        conn.execute(
            """
            INSERT INTO executable_signals (
                signal_id, timestamp, direction, entry_price, stop_loss, take_profit_1,
                take_profit_2, rr_ratio, governance_notes_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("sig-a", ts.isoformat(), "SHORT", 84000.0, 85000.0, 82000.0, 80000.0, 2.1, '[]'),
        )
        conn.commit()
        payload = read_signals_from_conn(conn, limit=10)
    finally:
        conn.close()
    assert len(payload["signals"]) == 1
    sig = payload["signals"][0]
    assert sig["signal_id"] == "sig-a"
    assert sig["direction"] == "SHORT"
    assert sig["regime"] == "downtrend"
    assert sig["confluence_score"] == 5.2
    assert sig["reasons"] == ["cvd_divergence", "reclaim_confirmed"]
    assert sig["promoted"] is True
    assert sig["rr_ratio"] == 2.1
    assert sig["config_hash"] == "hash-abc"


def test_read_signals_from_conn_not_promoted() -> None:
    schema_path = Path(__file__).resolve().parents[1] / "storage" / "schema.sql"
    conn = _make_conn(schema_path)
    ts = datetime(2026, 4, 13, 12, 0, tzinfo=timezone.utc)
    try:
        conn.execute(
            """
            INSERT INTO signal_candidates (
                signal_id, timestamp, direction, setup_type, confluence_score, regime,
                reasons_json, features_json, schema_version, config_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("sig-b", ts.isoformat(), "LONG", "sweep_reclaim", 2.8, "normal",
             '[]', "{}", "v1.0", "hash-def"),
        )
        conn.commit()
        payload = read_signals_from_conn(conn)
    finally:
        conn.close()
    assert len(payload["signals"]) == 1
    assert payload["signals"][0]["promoted"] is False
    assert payload["signals"][0]["entry_price"] is None


def test_read_daily_metrics_from_conn_empty() -> None:
    schema_path = Path(__file__).resolve().parents[1] / "storage" / "schema.sql"
    conn = _make_conn(schema_path)
    try:
        payload = read_daily_metrics_from_conn(conn)
    finally:
        conn.close()
    assert payload["metrics"] == []


def test_read_daily_metrics_from_conn_with_rows() -> None:
    schema_path = Path(__file__).resolve().parents[1] / "storage" / "schema.sql"
    conn = _make_conn(schema_path)
    try:
        conn.execute(
            """
            INSERT INTO daily_metrics (date, trades_count, wins, losses, pnl_abs, pnl_r_sum, daily_dd_pct, expectancy_r)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("2026-04-13", 3, 2, 1, 120.0, 0.6, 0.005, 0.2),
        )
        conn.commit()
        payload = read_daily_metrics_from_conn(conn, days=7)
    finally:
        conn.close()
    assert len(payload["metrics"]) == 1
    row = payload["metrics"][0]
    assert row["date"] == "2026-04-13"
    assert row["trades_count"] == 3
    assert row["wins"] == 2
    assert row["losses"] == 1
    assert row["expectancy_r"] == 0.2


def test_read_alerts_from_conn_empty() -> None:
    schema_path = Path(__file__).resolve().parents[1] / "storage" / "schema.sql"
    conn = _make_conn(schema_path)
    try:
        payload = read_alerts_from_conn(conn)
    finally:
        conn.close()
    assert payload["alerts"] == []


def test_read_alerts_from_conn_with_rows() -> None:
    schema_path = Path(__file__).resolve().parents[1] / "storage" / "schema.sql"
    conn = _make_conn(schema_path)
    ts = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(hours=1)
    try:
        conn.execute(
            """
            INSERT INTO alerts_errors (timestamp, type, severity, component, message)
            VALUES (?, ?, ?, ?, ?)
            """,
            (ts.isoformat(), "health_check", "ERROR", "orchestrator", "Bot entered safe mode"),
        )
        conn.commit()
        payload = read_alerts_from_conn(conn, limit=10)
    finally:
        conn.close()
    assert len(payload["alerts"]) == 1
    alert = payload["alerts"][0]
    assert alert["severity"] == "ERROR"
    assert alert["component"] == "orchestrator"
    assert alert["message"] == "Bot entered safe mode"


def test_read_trades_filters_by_config_hash() -> None:
    """Test that trades are filtered by the current config_hash from the most recent trade."""
    schema_path = Path(__file__).resolve().parents[1] / "storage" / "schema.sql"
    conn = _make_conn(schema_path)
    opened_at = datetime(2026, 4, 13, 10, 0, tzinfo=timezone.utc)
    closed_at = datetime(2026, 4, 13, 12, 0, tzinfo=timezone.utc)
    
    try:
        # Insert trade with config_hash="current"
        conn.execute(
            """
            INSERT INTO signal_candidates (
                signal_id, timestamp, direction, setup_type, confluence_score, regime,
                reasons_json, features_json, schema_version, config_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("sig-current", opened_at.isoformat(), "LONG", "test", 3.0, "normal", "[]", "{}", "v1.0", "current"),
        )
        conn.execute(
            """
            INSERT INTO executable_signals (
                signal_id, timestamp, direction, entry_price, stop_loss, take_profit_1,
                take_profit_2, rr_ratio, governance_notes_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("sig-current", opened_at.isoformat(), "LONG", 83000.0, 82000.0, 84000.0, 85000.0, 3.0, "[]"),
        )
        insert_position(
            conn,
            position_id="pos-current",
            signal_id="sig-current",
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
            trade_id="trd-current",
            signal_id="sig-current",
            position_id="pos-current",
            opened_at=opened_at,
            direction="LONG",
            regime="normal",
            confluence_score=3.0,
            entry_price=83000.0,
            size=0.1,
            features_at_entry_json={},
            schema_version="v1.0",
            config_hash="current",
        )
        conn.execute(
            """
            UPDATE trade_log
            SET position_id = ?, exit_price = ?, pnl_abs = ?, pnl_r = ?, closed_at = ?, exit_reason = ?
            WHERE trade_id = ?
            """,
            ("pos-current", 83500.0, 50.0, 0.5, closed_at.isoformat(), "tp1", "trd-current"),
        )
        
        # Insert trade with config_hash="old" (should be filtered out)
        old_closed_at = datetime(2026, 4, 12, 12, 0, tzinfo=timezone.utc)
        conn.execute(
            """
            INSERT INTO signal_candidates (
                signal_id, timestamp, direction, setup_type, confluence_score, regime,
                reasons_json, features_json, schema_version, config_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("sig-old", datetime(2026, 4, 12, 10, 0, tzinfo=timezone.utc).isoformat(), "LONG", "test", 3.0, "normal", "[]", "{}", "v1.0", "old"),
        )
        conn.execute(
            """
            INSERT INTO executable_signals (
                signal_id, timestamp, direction, entry_price, stop_loss, take_profit_1,
                take_profit_2, rr_ratio, governance_notes_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("sig-old", datetime(2026, 4, 12, 10, 0, tzinfo=timezone.utc).isoformat(), "LONG", 83000.0, 82000.0, 84000.0, 85000.0, 3.0, "[]"),
        )
        insert_position(
            conn,
            position_id="pos-old",
            signal_id="sig-old",
            symbol="BTCUSDT",
            direction="LONG",
            status="CLOSED",
            entry_price=83000.0,
            size=0.1,
            leverage=2,
            stop_loss=82000.0,
            take_profit_1=84000.0,
            take_profit_2=85000.0,
            opened_at=datetime(2026, 4, 12, 10, 0, tzinfo=timezone.utc),
            updated_at=old_closed_at,
        )
        insert_trade_log_open(
            conn,
            trade_id="trd-old",
            signal_id="sig-old",
            position_id="pos-old",
            opened_at=datetime(2026, 4, 12, 10, 0, tzinfo=timezone.utc),
            direction="LONG",
            regime="normal",
            confluence_score=3.0,
            entry_price=83000.0,
            size=0.1,
            features_at_entry_json={},
            schema_version="v1.0",
            config_hash="old",
        )
        conn.execute(
            """
            UPDATE trade_log
            SET position_id = ?, exit_price = ?, pnl_abs = ?, pnl_r = ?, closed_at = ?, exit_reason = ?
            WHERE trade_id = ?
            """,
            ("pos-old", 83500.0, 50.0, 0.5, old_closed_at.isoformat(), "tp1", "trd-old"),
        )
        
        conn.commit()
        payload = read_trades_from_conn(conn, limit=10)
    finally:
        conn.close()
    
    # Should only return the trade with config_hash="current" (most recent)
    assert len(payload["trades"]) == 1
    assert payload["trades"][0]["trade_id"] == "trd-current"
    assert payload["trades"][0]["config_hash"] == "current"


def test_read_signals_filters_by_config_hash() -> None:
    """Test that signals are filtered by the current config_hash from the most recent signal."""
    schema_path = Path(__file__).resolve().parents[1] / "storage" / "schema.sql"
    conn = _make_conn(schema_path)
    ts = datetime(2026, 4, 13, 12, 0, tzinfo=timezone.utc)
    
    try:
        # Insert signal with config_hash="current"
        conn.execute(
            """
            INSERT INTO signal_candidates (
                signal_id, timestamp, direction, setup_type, confluence_score, regime,
                reasons_json, features_json, schema_version, config_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("sig-current", ts.isoformat(), "LONG", "sweep_reclaim", 5.2, "normal",
             '["cvd_divergence"]', "{}", "v1.0", "current"),
        )
        
        # Insert signal with config_hash="old" (should be filtered out)
        conn.execute(
            """
            INSERT INTO signal_candidates (
                signal_id, timestamp, direction, setup_type, confluence_score, regime,
                reasons_json, features_json, schema_version, config_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("sig-old", datetime(2026, 4, 12, 12, 0, tzinfo=timezone.utc).isoformat(), "SHORT", "sweep_reclaim", 2.8, "normal",
             '[]', "{}", "v1.0", "old"),
        )
        
        conn.commit()
        payload = read_signals_from_conn(conn, limit=10)
    finally:
        conn.close()
    
    # Should only return the signal with config_hash="current" (most recent)
    assert len(payload["signals"]) == 1
    assert payload["signals"][0]["signal_id"] == "sig-current"
    assert payload["signals"][0]["config_hash"] == "current"
