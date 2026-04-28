from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts.modeling_context_closure_checkpoint import build_checkpoint
from storage.db import init_db


def _make_conn(schema_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn, schema_path)
    return conn


def test_build_checkpoint_reports_not_ready_without_closed_trades() -> None:
    schema_path = Path(__file__).resolve().parents[1] / "storage" / "schema.sql"
    conn = _make_conn(schema_path)
    since = datetime(2026, 4, 27, 13, 18, tzinfo=timezone.utc)
    signal_ts = since + timedelta(minutes=42)
    try:
        conn.execute(
            """
            INSERT INTO signal_candidates (
                signal_id, timestamp, direction, setup_type, confluence_score, regime,
                reasons_json, features_json, schema_version, config_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "sig-1",
                signal_ts.isoformat(),
                "LONG",
                "sweep_reclaim",
                17.2,
                "uptrend",
                "[]",
                json.dumps({"atr_4h_norm": 0.01, "ema50_4h": 77000.0, "ema200_4h": 73600.0}),
                "v1.0",
                "cfg-1",
            ),
        )
        conn.execute(
            """
            INSERT INTO executable_signals (
                signal_id, timestamp, direction, entry_price, stop_loss, take_profit_1,
                take_profit_2, rr_ratio, governance_notes_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("sig-1", signal_ts.isoformat(), "LONG", 78000.0, 77500.0, 79000.0, 80000.0, 1.566, "[]"),
        )
        conn.execute(
            """
            INSERT INTO decision_outcomes (
                cycle_timestamp, outcome_group, outcome_reason, regime, config_hash, signal_id, details_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                signal_ts.isoformat(),
                "risk_block",
                "risk_block",
                "uptrend",
                "cfg-1",
                "sig-1",
                '{"reason":"rr_below_min:1.566"}',
            ),
        )
        conn.commit()

        report = build_checkpoint(conn, since=since.isoformat(), min_closed_trades=2)
    finally:
        conn.close()

    assert report.sample["signal_candidates"] == 1
    assert report.telemetry["signal_candidates"]["complete_payload_share"] == 1.0
    assert report.risk_blocks["by_reason"] == {"rr_below_min:1.566": 1}
    assert report.verdict["ready_for_validation_rerun"] is False
    assert "closed_trades=0 < min_closed_trades=2" in report.verdict["reasons"]


def test_build_checkpoint_reports_ready_with_sufficient_closed_trade_telemetry() -> None:
    schema_path = Path(__file__).resolve().parents[1] / "storage" / "schema.sql"
    conn = _make_conn(schema_path)
    since = datetime(2026, 4, 27, 13, 18, tzinfo=timezone.utc)
    try:
        for index in range(2):
            ts = since + timedelta(hours=index + 1)
            signal_id = f"sig-{index}"
            position_id = f"pos-{index}"
            trade_id = f"trd-{index}"
            feature_payload = json.dumps(
                {
                    "atr_4h_norm": 0.009 + index * 0.001,
                    "ema50_4h": 77000.0 + index,
                    "ema200_4h": 73600.0 + index,
                }
            )
            conn.execute(
                """
                INSERT INTO signal_candidates (
                    signal_id, timestamp, direction, setup_type, confluence_score, regime,
                    reasons_json, features_json, schema_version, config_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (signal_id, ts.isoformat(), "LONG", "sweep_reclaim", 17.2, "uptrend", "[]", feature_payload, "v1.0", "cfg-1"),
            )
            conn.execute(
                """
                INSERT INTO executable_signals (
                    signal_id, timestamp, direction, entry_price, stop_loss, take_profit_1,
                    take_profit_2, rr_ratio, governance_notes_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (signal_id, ts.isoformat(), "LONG", 78000.0, 77500.0, 79000.0, 80000.0, 1.8, "[]"),
            )
            conn.execute(
                """
                INSERT INTO positions (
                    position_id, signal_id, symbol, direction, status, entry_price, size, leverage,
                    stop_loss, take_profit_1, take_profit_2, opened_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (position_id, signal_id, "BTCUSDT", "LONG", "CLOSED", 78000.0, 0.2, 5, 77500.0, 79000.0, 80000.0, ts.isoformat(), ts.isoformat()),
            )
            conn.execute(
                """
                INSERT INTO trade_log (
                    trade_id, signal_id, position_id, opened_at, closed_at, direction, regime,
                    confluence_score, entry_price, exit_price, size, fees_total, slippage_bps_avg,
                    pnl_abs, pnl_r, mae, mfe, exit_reason, features_at_entry_json, schema_version,
                    config_hash, funding_paid
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    trade_id,
                    signal_id,
                    position_id,
                    ts.isoformat(),
                    (ts + timedelta(minutes=30)).isoformat(),
                    "LONG",
                    "uptrend",
                    17.2,
                    78000.0,
                    79000.0,
                    0.2,
                    0.0,
                    0.0,
                    100.0,
                    1.0,
                    10.0,
                    100.0,
                    "TP",
                    feature_payload,
                    "v1.0",
                    "cfg-1",
                    0.0,
                ),
            )
            conn.execute(
                """
                INSERT INTO decision_outcomes (
                    cycle_timestamp, outcome_group, outcome_reason, regime, config_hash, signal_id, details_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (ts.isoformat(), "signal_generated", "signal_generated", "uptrend", "cfg-1", signal_id, "{}"),
            )
        conn.commit()

        report = build_checkpoint(conn, since=since.isoformat(), min_closed_trades=2)
    finally:
        conn.close()

    assert report.sample["trades_closed"] == 2
    assert report.telemetry["closed_trades"]["unknown_volatility_share"] == 0.0
    assert report.verdict["ready_for_validation_rerun"] is True
    assert report.verdict["reasons"] == []
