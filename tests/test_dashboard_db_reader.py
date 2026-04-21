from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from dashboard.db_reader import (
    read_alerts_from_conn,
    read_config_snapshot_from_conn,
    read_decision_funnel_from_conn,
    read_daily_metrics_from_conn,
    read_positions_from_conn,
    read_runtime_freshness_from_conn,
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
                safe_mode_entry_at=None,
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
    metrics_day = (datetime.now(timezone.utc) - timedelta(days=1)).date().isoformat()
    try:
        conn.execute(
            """
            INSERT INTO daily_metrics (date, trades_count, wins, losses, pnl_abs, pnl_r_sum, daily_dd_pct, expectancy_r)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (metrics_day, 3, 2, 1, 120.0, 0.6, 0.005, 0.2),
        )
        conn.commit()
        payload = read_daily_metrics_from_conn(conn, days=7)
    finally:
        conn.close()
    assert len(payload["metrics"]) == 1
    row = payload["metrics"][0]
    assert row["date"] == metrics_day
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


def test_read_decision_funnel_from_conn_aggregates_windows_and_reasons() -> None:
    schema_path = Path(__file__).resolve().parents[1] / "storage" / "schema.sql"
    conn = _make_conn(schema_path)
    now = datetime(2026, 4, 19, 12, 0, tzinfo=timezone.utc)
    try:
        conn.executemany(
            """
            INSERT INTO decision_outcomes (
                cycle_timestamp, outcome_group, outcome_reason, regime, config_hash, signal_id, details_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ((now - timedelta(hours=2)).isoformat(), "no_signal", "no_reclaim", "normal", "cfg-1", None, "{}"),
                ((now - timedelta(hours=3)).isoformat(), "no_signal", "uptrend_pullback_weak", "uptrend", "cfg-1", None, "{}"),
                ((now - timedelta(hours=4)).isoformat(), "signal_generated", "signal_generated", "uptrend", "cfg-1", "sig-1", "{}"),
                ((now - timedelta(days=3)).isoformat(), "risk_block", "risk_block", "downtrend", "cfg-1", "sig-2", "{}"),
                ((now - timedelta(days=8)).isoformat(), "no_signal", "no_reclaim", "normal", "cfg-1", None, "{}"),
                ((now - timedelta(hours=1)).isoformat(), "no_signal", "no_reclaim", "normal", "cfg-2", None, "{}"),
            ],
        )
        conn.commit()

        payload = read_decision_funnel_from_conn(conn, config_hash="cfg-1", now=now)
    finally:
        conn.close()

    assert payload["config_hash"] == "cfg-1"
    assert payload["windows"]["24h"]["total"] == 3
    assert payload["windows"]["24h"]["by_outcome"] == {
        "no_signal": 2,
        "signal_generated": 1,
    }
    assert payload["windows"]["24h"]["by_reason"] == {
        "no_reclaim": 1,
        "signal_generated": 1,
        "uptrend_pullback_weak": 1,
    }
    assert payload["windows"]["7d"]["total"] == 4
    assert payload["windows"]["7d"]["by_outcome"]["risk_block"] == 1


def test_read_config_snapshot_from_conn_returns_strategy_snapshot() -> None:
    schema_path = Path(__file__).resolve().parents[1] / "storage" / "schema.sql"
    conn = _make_conn(schema_path)
    captured_at = datetime(2026, 4, 19, 10, 0, tzinfo=timezone.utc)
    try:
        conn.execute(
            """
            INSERT INTO config_snapshots (config_hash, captured_at, strategy_json)
            VALUES (?, ?, ?)
            """,
            (
                "cfg-123",
                captured_at.isoformat(),
                '{"allow_uptrend_pullback": true, "uptrend_pullback_confluence_min": 8.0}',
            ),
        )
        conn.commit()

        payload = read_config_snapshot_from_conn(conn, config_hash="cfg-123")
    finally:
        conn.close()

    assert payload["config_hash"] == "cfg-123"
    assert payload["captured_at"] == captured_at.isoformat()
    assert payload["strategy"] == {
        "allow_uptrend_pullback": True,
        "uptrend_pullback_confluence_min": 8.0,
    }


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


def test_read_trades_honors_explicit_config_hash_override() -> None:
    schema_path = Path(__file__).resolve().parents[1] / "storage" / "schema.sql"
    conn = _make_conn(schema_path)
    current_closed_at = datetime(2026, 4, 13, 12, 0, tzinfo=timezone.utc)
    old_closed_at = datetime(2026, 4, 14, 12, 0, tzinfo=timezone.utc)

    try:
        conn.execute(
            """
            INSERT INTO signal_candidates (
                signal_id, timestamp, direction, setup_type, confluence_score, regime,
                reasons_json, features_json, schema_version, config_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("sig-current", current_closed_at.isoformat(), "LONG", "test", 3.0, "normal", "[]", "{}", "v1.0", "current"),
        )
        conn.execute(
            """
            INSERT INTO signal_candidates (
                signal_id, timestamp, direction, setup_type, confluence_score, regime,
                reasons_json, features_json, schema_version, config_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("sig-old", old_closed_at.isoformat(), "LONG", "test", 3.0, "normal", "[]", "{}", "v1.0", "old"),
        )
        conn.execute(
            """
            INSERT INTO executable_signals (
                signal_id, timestamp, direction, entry_price, stop_loss, take_profit_1,
                take_profit_2, rr_ratio, governance_notes_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("sig-current", current_closed_at.isoformat(), "LONG", 83000.0, 82000.0, 84000.0, 85000.0, 3.0, "[]"),
        )
        conn.execute(
            """
            INSERT INTO executable_signals (
                signal_id, timestamp, direction, entry_price, stop_loss, take_profit_1,
                take_profit_2, rr_ratio, governance_notes_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("sig-old", old_closed_at.isoformat(), "LONG", 83000.0, 82000.0, 84000.0, 85000.0, 3.0, "[]"),
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
            opened_at=current_closed_at,
            updated_at=current_closed_at,
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
            opened_at=old_closed_at,
            updated_at=old_closed_at,
        )
        insert_trade_log_open(
            conn,
            trade_id="trd-current",
            signal_id="sig-current",
            position_id="pos-current",
            opened_at=current_closed_at,
            direction="LONG",
            regime="normal",
            confluence_score=3.0,
            entry_price=83000.0,
            size=0.1,
            features_at_entry_json={},
            schema_version="v1.0",
            config_hash="current",
        )
        insert_trade_log_open(
            conn,
            trade_id="trd-old",
            signal_id="sig-old",
            position_id="pos-old",
            opened_at=old_closed_at,
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
            SET exit_price = ?, pnl_abs = ?, pnl_r = ?, closed_at = ?, exit_reason = ?
            WHERE trade_id = ?
            """,
            (83500.0, 50.0, 0.5, current_closed_at.isoformat(), "tp1", "trd-current"),
        )
        conn.execute(
            """
            UPDATE trade_log
            SET exit_price = ?, pnl_abs = ?, pnl_r = ?, closed_at = ?, exit_reason = ?
            WHERE trade_id = ?
            """,
            (83500.0, 50.0, 0.5, old_closed_at.isoformat(), "tp1", "trd-old"),
        )
        conn.commit()

        payload = read_trades_from_conn(conn, limit=10, config_hash="current")
    finally:
        conn.close()

    assert len(payload["trades"]) == 1
    assert payload["trades"][0]["trade_id"] == "trd-current"
    assert payload["trades"][0]["config_hash"] == "current"


def test_read_signals_honors_explicit_config_hash_override() -> None:
    schema_path = Path(__file__).resolve().parents[1] / "storage" / "schema.sql"
    conn = _make_conn(schema_path)
    current_ts = datetime(2026, 4, 13, 12, 0, tzinfo=timezone.utc)
    old_ts = datetime(2026, 4, 14, 12, 0, tzinfo=timezone.utc)

    try:
        conn.execute(
            """
            INSERT INTO signal_candidates (
                signal_id, timestamp, direction, setup_type, confluence_score, regime,
                reasons_json, features_json, schema_version, config_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("sig-current", current_ts.isoformat(), "LONG", "sweep_reclaim", 5.2, "normal", '["cvd_divergence"]', "{}", "v1.0", "current"),
        )
        conn.execute(
            """
            INSERT INTO signal_candidates (
                signal_id, timestamp, direction, setup_type, confluence_score, regime,
                reasons_json, features_json, schema_version, config_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("sig-old", old_ts.isoformat(), "SHORT", "sweep_reclaim", 2.8, "normal", "[]", "{}", "v1.0", "old"),
        )
        conn.commit()

        payload = read_signals_from_conn(conn, limit=10, config_hash="current")
    finally:
        conn.close()

    assert len(payload["signals"]) == 1
    assert payload["signals"][0]["signal_id"] == "sig-current"
    assert payload["signals"][0]["config_hash"] == "current"


def test_read_runtime_freshness_from_conn_returns_unavailable_when_table_missing() -> None:
    schema_path = Path(__file__).resolve().parents[1] / "storage" / "schema.sql"
    conn = _make_conn(schema_path)
    try:
        conn.execute("DROP TABLE runtime_metrics")
        conn.commit()
        payload = read_runtime_freshness_from_conn(conn)
    finally:
        conn.close()

    assert payload["runtime_available"] is False
    assert payload["decision_cycle"]["status"] == "unavailable"
    assert payload["rest_snapshot"]["built_at"] is None
    assert payload["websocket"]["healthy"] is None


def test_read_runtime_freshness_from_conn_returns_expected_schema() -> None:
    schema_path = Path(__file__).resolve().parents[1] / "storage" / "schema.sql"
    conn = _make_conn(schema_path)
    now = datetime(2026, 4, 18, 10, 15, 30, tzinfo=timezone.utc)

    try:
        conn.execute(
            """
            INSERT INTO runtime_metrics (
                id, updated_at, last_decision_cycle_started_at, last_decision_cycle_finished_at,
                last_decision_outcome, decision_cycle_status, last_snapshot_built_at, last_snapshot_symbol,
                last_15m_candle_open_at, last_1h_candle_open_at, last_4h_candle_open_at,
                last_ws_message_at, last_health_check_at, last_runtime_warning, config_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                1,
                now.isoformat(),
                datetime(2026, 4, 18, 10, 15, 0, tzinfo=timezone.utc).isoformat(),
                datetime(2026, 4, 18, 10, 15, 1, tzinfo=timezone.utc).isoformat(),
                "no_signal",
                "idle",
                datetime(2026, 4, 18, 10, 15, 0, tzinfo=timezone.utc).isoformat(),
                "BTCUSDT",
                datetime(2026, 4, 18, 10, 15, 0, tzinfo=timezone.utc).isoformat(),
                datetime(2026, 4, 18, 10, 0, 0, tzinfo=timezone.utc).isoformat(),
                datetime(2026, 4, 18, 8, 0, 0, tzinfo=timezone.utc).isoformat(),
                datetime(2026, 4, 18, 10, 15, 25, tzinfo=timezone.utc).isoformat(),
                datetime(2026, 4, 18, 10, 15, 5, tzinfo=timezone.utc).isoformat(),
                None,
                "cfg-123",
            ),
        )
        conn.commit()
        payload = read_runtime_freshness_from_conn(conn, heartbeat_seconds=30, now=now)
    finally:
        conn.close()

    assert payload["runtime_available"] is True
    assert payload["config_hash"] == "cfg-123"
    assert payload["decision_cycle"]["status"] == "idle"
    assert payload["decision_cycle"]["last_outcome"] == "no_signal"
    assert payload["decision_cycle"]["last_snapshot_age_seconds"] == 30.0
    assert payload["rest_snapshot"]["symbol"] == "BTCUSDT"
    assert payload["rest_snapshot"]["timeframes"]["15m"]["age_seconds"] == 30.0
    assert payload["rest_snapshot"]["timeframes"]["1h"]["age_seconds"] == 930.0
    assert payload["rest_snapshot"]["timeframes"]["4h"]["age_seconds"] == 8130.0
    assert payload["websocket"]["message_age_seconds"] == 5.0
    assert payload["websocket"]["healthy"] is True
    assert payload["collector"] is None


def test_read_runtime_freshness_ignores_stale_db_candles() -> None:
    schema_path = Path(__file__).resolve().parents[1] / "storage" / "schema.sql"
    conn = _make_conn(schema_path)
    now = datetime(2026, 4, 18, 10, 15, 30, tzinfo=timezone.utc)
    stale_open = datetime(2026, 4, 17, 19, 15, 0, tzinfo=timezone.utc)

    try:
        conn.execute(
            """
            INSERT INTO candles (symbol, timeframe, open_time, open, high, low, close, volume)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("BTCUSDT", "15m", stale_open.isoformat(), 1.0, 1.0, 1.0, 1.0, 1.0),
        )
        conn.execute(
            """
            INSERT INTO runtime_metrics (
                id, updated_at, last_snapshot_built_at, last_snapshot_symbol, last_15m_candle_open_at,
                last_ws_message_at, decision_cycle_status, last_decision_outcome, config_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                1,
                now.isoformat(),
                datetime(2026, 4, 18, 10, 15, 0, tzinfo=timezone.utc).isoformat(),
                "BTCUSDT",
                datetime(2026, 4, 18, 10, 15, 0, tzinfo=timezone.utc).isoformat(),
                datetime(2026, 4, 18, 10, 15, 20, tzinfo=timezone.utc).isoformat(),
                "idle",
                "no_signal",
                "cfg-123",
            ),
        )
        conn.commit()
        payload = read_runtime_freshness_from_conn(conn, heartbeat_seconds=30, now=now)
    finally:
        conn.close()

    assert payload["runtime_available"] is True
    assert payload["rest_snapshot"]["timeframes"]["15m"]["last_candle_open_at"] == "2026-04-18T10:15:00+00:00"
    assert payload["rest_snapshot"]["timeframes"]["15m"]["age_seconds"] == 30.0
