from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from core.execution_types import ExecutionStatus, FillEvent
from core.models import ExecutableSignal, RegimeState, SignalCandidate
from dashboard.db_reader import read_positions_from_conn, read_trades_from_conn
from execution.paper_execution_engine import PaperExecutionEngine
from storage.db import init_db
from storage.repositories import (
    insert_execution_fill_event,
    insert_position,
    insert_trade_log_open,
    save_executable_signal,
)
from storage.state_store import StateStore


class FakePositionPersister:
    def __init__(self) -> None:
        self.positions: list[dict[str, Any]] = []
        self.executions: list[dict[str, Any]] = []
        self.commits = 0

    def insert_position(self, **kwargs: Any) -> None:
        self.positions.append(kwargs)

    def insert_execution_fill_event(self, **kwargs: Any) -> None:
        self.executions.append(kwargs)

    def commit(self) -> None:
        self.commits += 1


def _schema_path() -> Path:
    return Path(__file__).resolve().parents[1] / "storage" / "schema.sql"


def _make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn, _schema_path())
    return conn


def _signal() -> ExecutableSignal:
    ts = datetime(2026, 4, 21, 13, 0, tzinfo=timezone.utc)
    return ExecutableSignal(
        signal_id="sig-test",
        timestamp=ts,
        direction="LONG",
        entry_price=100.0,
        stop_loss=95.0,
        take_profit_1=110.0,
        take_profit_2=120.0,
        rr_ratio=2.0,
        approved_by_governance=True,
        governance_notes=["governance_pass"],
    )


def _candidate() -> SignalCandidate:
    ts = datetime(2026, 4, 21, 13, 0, tzinfo=timezone.utc)
    return SignalCandidate(
        signal_id="sig-test",
        timestamp=ts,
        direction="LONG",
        setup_type="liquidity_sweep_reclaim_long",
        entry_reference=100.0,
        invalidation_level=95.0,
        tp_reference_1=110.0,
        tp_reference_2=120.0,
        confluence_score=5.0,
        regime=RegimeState.NORMAL,
        reasons=["reclaim_confirmed"],
        features_json={
            "atr_15m": 10.0,
            "atr_4h": 50.0,
            "atr_4h_norm": 0.01,
            "ema50_4h": 110.0,
            "ema200_4h": 100.0,
        },
    )


def _insert_candidate_row(conn: sqlite3.Connection, candidate: SignalCandidate, *, config_hash: str = "hash-test") -> None:
    conn.execute(
        """
        INSERT INTO signal_candidates (
            signal_id, timestamp, direction, setup_type, confluence_score, regime,
            reasons_json, features_json, schema_version, config_hash
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            candidate.signal_id,
            candidate.timestamp.isoformat(),
            candidate.direction,
            candidate.setup_type,
            candidate.confluence_score,
            candidate.regime.value,
            '["reclaim_confirmed"]',
            '{"atr_15m": 10.0}',
            "v1.0",
            config_hash,
        ),
    )


def test_paper_execution_requires_snapshot_price() -> None:
    persister = FakePositionPersister()
    engine = PaperExecutionEngine(position_persister=persister)

    with pytest.raises(ValueError, match="requires snapshot_price"):
        engine.execute_signal(_signal(), size=0.5, leverage=2)

    assert persister.positions == []
    assert persister.executions == []
    assert persister.commits == 0


def test_paper_execution_uses_snapshot_price_as_fill_and_writes_execution() -> None:
    persister = FakePositionPersister()
    engine = PaperExecutionEngine(position_persister=persister)

    engine.execute_signal(_signal(), size=0.5, leverage=2, snapshot_price=101.0)

    assert len(persister.positions) == 1
    assert len(persister.executions) == 1
    assert persister.commits == 1

    position = persister.positions[0]
    assert position["entry_price"] == 101.0
    assert position["size"] == 0.5

    execution = persister.executions[0]
    fill_event = execution["fill_event"]
    assert execution["order_type"] == "MARKET"
    assert fill_event.status is ExecutionStatus.FILLED
    assert fill_event.requested_price == 100.0
    assert fill_event.filled_price == 101.0
    assert fill_event.qty == 0.5
    assert fill_event.slippage_bps == pytest.approx(100.0)


def test_record_trade_open_persists_filled_entry_price() -> None:
    conn = _make_conn()
    try:
        opened_at = datetime(2026, 4, 21, 13, 0, tzinfo=timezone.utc)
        _insert_candidate_row(conn, _candidate())
        save_executable_signal(conn, _signal())
        insert_position(
            conn,
            position_id="paper-test",
            signal_id="sig-test",
            symbol="BTCUSDT",
            direction="LONG",
            status="OPEN",
            entry_price=100.0,
            size=0.5,
            leverage=2,
            stop_loss=95.0,
            take_profit_1=110.0,
            take_profit_2=120.0,
            opened_at=opened_at,
            updated_at=opened_at,
        )

        store = StateStore(conn, mode="PAPER")
        store.record_trade_open(
            candidate=_candidate(),
            executable=_signal(),
            schema_version="v1.0",
            config_hash="hash-test",
            filled_entry_price=101.0,
        )

        row = conn.execute("SELECT entry_price FROM trade_log WHERE signal_id = ?", ("sig-test",)).fetchone()
    finally:
        conn.close()

    assert row is not None
    assert float(row["entry_price"]) == 101.0


def test_record_trade_open_persists_modeling_features_payload() -> None:
    conn = _make_conn()
    try:
        opened_at = datetime(2026, 4, 21, 13, 0, tzinfo=timezone.utc)
        candidate = _candidate()
        _insert_candidate_row(conn, candidate)
        save_executable_signal(conn, _signal())
        insert_position(
            conn,
            position_id="paper-test",
            signal_id="sig-test",
            symbol="BTCUSDT",
            direction="LONG",
            status="OPEN",
            entry_price=100.0,
            size=0.5,
            leverage=2,
            stop_loss=95.0,
            take_profit_1=110.0,
            take_profit_2=120.0,
            opened_at=opened_at,
            updated_at=opened_at,
        )

        store = StateStore(conn, mode="PAPER")
        store.record_trade_open(
            candidate=candidate,
            executable=_signal(),
            schema_version="v1.0",
            config_hash="hash-test",
            filled_entry_price=101.0,
        )

        row = conn.execute(
            "SELECT features_at_entry_json FROM trade_log WHERE signal_id = ?",
            ("sig-test",),
        ).fetchone()
    finally:
        conn.close()

    assert row is not None
    payload = json.loads(row["features_at_entry_json"])
    assert payload["atr_15m"] == 10.0
    assert payload["atr_4h"] == 50.0
    assert payload["atr_4h_norm"] == 0.01
    assert payload["ema50_4h"] == 110.0
    assert payload["ema200_4h"] == 100.0


def test_dashboard_exposes_signal_reference_and_execution_flag_for_positions() -> None:
    conn = _make_conn()
    try:
        signal = _signal()
        opened_at = signal.timestamp
        _insert_candidate_row(conn, _candidate())
        save_executable_signal(conn, signal)
        insert_position(
            conn,
            position_id="paper-test",
            signal_id=signal.signal_id,
            symbol="BTCUSDT",
            direction="LONG",
            status="OPEN",
            entry_price=101.0,
            size=0.5,
            leverage=2,
            stop_loss=95.0,
            take_profit_1=110.0,
            take_profit_2=120.0,
            opened_at=opened_at,
            updated_at=opened_at,
        )
        insert_execution_fill_event(
            conn,
            position_id="paper-test",
            order_type="MARKET",
            fill_event=FillEvent(
                execution_id="exe-test",
                client_order_id="paper-test",
                status=ExecutionStatus.FILLED,
                side="BUY",
                requested_price=100.0,
                filled_price=101.0,
                qty=0.5,
                fees=0.0,
                slippage_bps=100.0,
                executed_at=opened_at,
            ),
        )
        conn.commit()

        payload = read_positions_from_conn(conn, now=opened_at)
    finally:
        conn.close()

    assert payload["positions"][0]["entry_price"] == 101.0
    assert payload["positions"][0]["signal_entry_reference"] == 100.0
    assert payload["positions"][0]["has_execution_record"] is True


def test_dashboard_flags_closed_trade_without_execution_record() -> None:
    conn = _make_conn()
    try:
        signal = _signal()
        opened_at = signal.timestamp
        closed_at = datetime(2026, 4, 21, 14, 0, tzinfo=timezone.utc)
        _insert_candidate_row(conn, _candidate())
        save_executable_signal(conn, signal)
        insert_position(
            conn,
            position_id="paper-test",
            signal_id=signal.signal_id,
            symbol="BTCUSDT",
            direction="LONG",
            status="CLOSED",
            entry_price=101.0,
            size=0.5,
            leverage=2,
            stop_loss=95.0,
            take_profit_1=110.0,
            take_profit_2=120.0,
            opened_at=opened_at,
            updated_at=closed_at,
        )
        insert_trade_log_open(
            conn,
            trade_id="trd-test",
            signal_id=signal.signal_id,
            position_id="paper-test",
            opened_at=opened_at,
            direction="LONG",
            regime="normal",
            confluence_score=5.0,
            entry_price=101.0,
            size=0.5,
            features_at_entry_json={},
            schema_version="v1.0",
            config_hash="hash-test",
        )
        conn.execute(
            """
            UPDATE trade_log
            SET closed_at = ?, exit_price = ?, pnl_abs = ?, pnl_r = ?, exit_reason = ?
            WHERE trade_id = ?
            """,
            (closed_at.isoformat(), 102.0, 10.0, 1.0, "TP", "trd-test"),
        )
        conn.commit()

        payload = read_trades_from_conn(conn, config_hash="hash-test")
    finally:
        conn.close()

    assert payload["trades"][0]["entry_price"] == 101.0
    assert payload["trades"][0]["signal_entry_reference"] == 100.0
    assert payload["trades"][0]["has_execution_record"] is False
