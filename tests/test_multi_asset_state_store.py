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


def test_paper_simulation_account_initializes_and_preserves_balance() -> None:
    conn = _conn()
    store = StateStore(conn, mode="PAPER")

    account = store.ensure_paper_simulation_account(
        starting_balance_usd=1000.0,
        now=NOW,
    )
    same_account = store.ensure_paper_simulation_account(
        starting_balance_usd=2500.0,
        now=NOW + timedelta(minutes=1),
    )

    assert account.current_balance_usd == 1000.0
    assert account.realized_pnl_usd == 0.0
    assert same_account.starting_balance_usd == 1000.0
    assert same_account.current_balance_usd == 1000.0


def test_paper_simulation_account_compounds_realized_pnl() -> None:
    conn = _conn()
    store = StateStore(conn, mode="PAPER")
    store.ensure_paper_simulation_account(starting_balance_usd=1000.0, now=NOW)

    after_win = store.apply_paper_simulation_pnl(pnl_abs=37.5, now=NOW + timedelta(minutes=5))
    after_loss = store.apply_paper_simulation_pnl(pnl_abs=-12.5, now=NOW + timedelta(minutes=10))

    assert after_win.current_balance_usd == 1037.5
    assert after_loss.current_balance_usd == 1025.0
    assert after_loss.realized_pnl_usd == 25.0


def test_paper_simulation_account_can_track_pnl_without_compounding() -> None:
    conn = _conn()
    store = StateStore(conn, mode="PAPER")
    store.ensure_paper_simulation_account(starting_balance_usd=1000.0, now=NOW)

    account = store.apply_paper_simulation_pnl(
        pnl_abs=50.0,
        compound_pnl=False,
        now=NOW + timedelta(minutes=5),
    )

    assert account.current_balance_usd == 1000.0
    assert account.realized_pnl_usd == 50.0


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
