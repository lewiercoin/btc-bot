from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from core.portfolio_gate import PortfolioRiskState, SymbolRiskState
from storage.db import init_db
from storage.state_store import StateStore


NOW = datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc)


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn, Path("storage/schema.sql"))
    return conn


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    ).fetchone()
    return row is not None


def test_ensure_initialized_does_not_create_multi_asset_state_tables() -> None:
    conn = _conn()
    store = StateStore(conn, mode="PAPER")

    store.ensure_initialized()

    assert not _table_exists(conn, "symbol_state")
    assert not _table_exists(conn, "portfolio_state")


def test_ensure_multi_asset_schema_is_explicit_and_idempotent() -> None:
    conn = _conn()
    store = StateStore(conn, mode="PAPER")

    store.ensure_multi_asset_schema()
    store.ensure_multi_asset_schema()

    assert _table_exists(conn, "symbol_state")
    assert _table_exists(conn, "portfolio_state")


def test_symbol_and_portfolio_pause_state_survives_recovery_overlay() -> None:
    conn = _conn()
    store = StateStore(conn, mode="PAPER")
    pause_until = NOW + timedelta(minutes=30)
    store.upsert_symbol_state(
        "ETHUSDT",
        SymbolRiskState(symbol="ETHUSDT", symbol_paused_until=pause_until, pause_reason="operator_pause"),
        updated_at=NOW,
    )
    store.upsert_portfolio_state(
        PortfolioRiskState(portfolio_paused_until=pause_until, emergency_stop_active=True),
        updated_at=NOW,
    )

    recovered = store.recover_multi_asset_portfolio_state(("BTCUSDT", "ETHUSDT"), now=NOW)

    assert recovered.symbols["BTCUSDT"].symbol_paused_until is None
    assert recovered.symbols["ETHUSDT"].symbol_paused_until == pause_until
    assert recovered.symbols["ETHUSDT"].pause_reason == "operator_pause"
    assert recovered.portfolio.portfolio_paused_until == pause_until
    assert recovered.portfolio.emergency_stop_active is True
