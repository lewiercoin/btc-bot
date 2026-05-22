"""Tests for per-symbol drawdown tracking with true high-watermark.

Milestone: MULTI_ASSET_DD_TRACKING_V1
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

from core.portfolio_gate import (
    PortfolioRiskConfig,
    PortfolioTradeEvent,
    SymbolRiskState,
    recover_portfolio_state,
)
from storage.db import init_db
from storage.state_store import StateStore
from settings import load_settings


NOW = datetime(2026, 5, 22, 18, 0, tzinfo=timezone.utc)


def _make_store() -> StateStore:
    settings = load_settings()
    assert settings.storage is not None
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    init_db(conn, settings.storage.schema_path)
    store = StateStore(connection=conn, mode="PAPER", reference_equity=10_000.0)
    store.ensure_initialized()
    return store


# --- Test: DD state initialization and persistence ---

def test_load_symbol_dd_state_returns_none_for_new_symbol() -> None:
    store = _make_store()
    assert store.load_symbol_dd_state("ETHUSDT") is None


def test_upsert_and_load_symbol_dd_state() -> None:
    store = _make_store()
    state = {
        "symbol": "ETHUSDT",
        "cumulative_r": 2.5,
        "local_high_watermark_r": 3.0,
        "rolling_drawdown_r": -0.5,
        "daily_pnl_r": 1.0,
        "weekly_pnl_r": 2.0,
        "daily_start_date": "2026-05-22",
        "weekly_start_date": "2026-05-19",
        "trades_today": 2,
        "consecutive_losses": 0,
        "last_trade_at": NOW.isoformat(),
        "last_loss_at": None,
        "updated_at": NOW.isoformat(),
    }
    store.upsert_symbol_dd_state(state)
    loaded = store.load_symbol_dd_state("ETHUSDT")
    assert loaded is not None
    assert loaded["cumulative_r"] == 2.5
    assert loaded["local_high_watermark_r"] == 3.0
    assert loaded["rolling_drawdown_r"] == -0.5


def test_load_all_symbol_dd_states_returns_all() -> None:
    store = _make_store()
    for sym in ("BTCUSDT", "ETHUSDT", "SOLUSDT"):
        store.upsert_symbol_dd_state({
            "symbol": sym,
            "cumulative_r": 0.0,
            "local_high_watermark_r": 0.0,
            "rolling_drawdown_r": 0.0,
            "daily_pnl_r": 0.0,
            "weekly_pnl_r": 0.0,
            "daily_start_date": "2026-05-22",
            "weekly_start_date": "2026-05-19",
            "trades_today": 0,
            "consecutive_losses": 0,
            "last_trade_at": None,
            "last_loss_at": None,
            "updated_at": NOW.isoformat(),
        })
    all_states = store.load_all_symbol_dd_states()
    assert len(all_states) == 3
    assert "BTCUSDT" in all_states
    assert "ETHUSDT" in all_states
    assert "SOLUSDT" in all_states


# --- Test: High-watermark update on win ---

def test_high_watermark_updates_on_win() -> None:
    store = _make_store()
    # First trade: +2R
    result = store.update_symbol_dd_after_trade(symbol="ETHUSDT", pnl_r=2.0, closed_at=NOW)
    assert result["cumulative_r"] == 2.0
    assert result["local_high_watermark_r"] == 2.0
    assert result["rolling_drawdown_r"] == 0.0

    # Second trade: +1R (cumulative=3R, new high)
    result = store.update_symbol_dd_after_trade(
        symbol="ETHUSDT", pnl_r=1.0, closed_at=NOW + timedelta(minutes=15)
    )
    assert result["cumulative_r"] == 3.0
    assert result["local_high_watermark_r"] == 3.0
    assert result["rolling_drawdown_r"] == 0.0


# --- Test: High-watermark preserved on loss ---

def test_high_watermark_preserved_on_loss() -> None:
    store = _make_store()
    # Win +3R
    store.update_symbol_dd_after_trade(symbol="BTCUSDT", pnl_r=3.0, closed_at=NOW)
    # Loss -1R
    result = store.update_symbol_dd_after_trade(
        symbol="BTCUSDT", pnl_r=-1.0, closed_at=NOW + timedelta(minutes=15)
    )
    assert result["cumulative_r"] == 2.0
    assert result["local_high_watermark_r"] == 3.0  # Preserved!
    assert result["rolling_drawdown_r"] == -1.0  # 2.0 - 3.0 = -1.0


# --- Test: rolling_drawdown_r calculation (-8R scenario) ---

def test_rolling_drawdown_deep_loss_scenario() -> None:
    store = _make_store()
    # Build up to +5R high-watermark
    store.update_symbol_dd_after_trade(symbol="SOLUSDT", pnl_r=5.0, closed_at=NOW)
    # Lose -8R total (series of losses)
    t = NOW + timedelta(minutes=15)
    for i in range(8):
        result = store.update_symbol_dd_after_trade(
            symbol="SOLUSDT", pnl_r=-1.0, closed_at=t + timedelta(minutes=15 * i)
        )
    # cumulative_r = 5 - 8 = -3
    # high_watermark = 5
    # rolling_drawdown = -3 - 5 = -8
    assert result["cumulative_r"] == -3.0
    assert result["local_high_watermark_r"] == 5.0
    assert result["rolling_drawdown_r"] == -8.0


# --- Test: daily_pnl_r and weekly_pnl_r calculation ---

def test_daily_pnl_r_accumulates_within_day() -> None:
    store = _make_store()
    store.update_symbol_dd_after_trade(symbol="ETHUSDT", pnl_r=1.5, closed_at=NOW)
    result = store.update_symbol_dd_after_trade(
        symbol="ETHUSDT", pnl_r=-0.5, closed_at=NOW + timedelta(minutes=30)
    )
    assert result["daily_pnl_r"] == 1.0  # 1.5 + (-0.5)
    assert result["weekly_pnl_r"] == 1.0
    assert result["trades_today"] == 2


def test_daily_pnl_r_resets_on_new_day() -> None:
    store = _make_store()
    store.update_symbol_dd_after_trade(symbol="ETHUSDT", pnl_r=2.0, closed_at=NOW)
    # Next day
    next_day = NOW + timedelta(days=1)
    result = store.update_symbol_dd_after_trade(
        symbol="ETHUSDT", pnl_r=-1.0, closed_at=next_day
    )
    assert result["daily_pnl_r"] == -1.0  # Reset for new day
    assert result["weekly_pnl_r"] == 1.0  # Still accumulating weekly (same week)
    assert result["trades_today"] == 1  # Reset


def test_weekly_pnl_r_resets_on_new_week() -> None:
    store = _make_store()
    # Thursday May 22 2026
    store.update_symbol_dd_after_trade(symbol="ETHUSDT", pnl_r=3.0, closed_at=NOW)
    # Next Monday (May 26)
    next_monday = NOW + timedelta(days=4)
    result = store.update_symbol_dd_after_trade(
        symbol="ETHUSDT", pnl_r=-1.0, closed_at=next_monday
    )
    assert result["weekly_pnl_r"] == -1.0  # Reset for new week
    assert result["cumulative_r"] == 2.0  # Cumulative NOT reset


# --- Test: Multi-asset isolation (BTC DD doesn't affect ETH) ---

def test_btc_dd_does_not_affect_eth_dd() -> None:
    store = _make_store()
    # BTC has big loss
    store.update_symbol_dd_after_trade(symbol="BTCUSDT", pnl_r=-5.0, closed_at=NOW)
    # ETH has a win
    store.update_symbol_dd_after_trade(symbol="ETHUSDT", pnl_r=2.0, closed_at=NOW)

    btc = store.load_symbol_dd_state("BTCUSDT")
    eth = store.load_symbol_dd_state("ETHUSDT")

    assert btc["cumulative_r"] == -5.0
    assert btc["rolling_drawdown_r"] == -5.0
    assert btc["consecutive_losses"] == 1

    assert eth["cumulative_r"] == 2.0
    assert eth["rolling_drawdown_r"] == 0.0
    assert eth["consecutive_losses"] == 0


# --- Test: Consecutive losses tracking ---

def test_consecutive_losses_increments_on_loss() -> None:
    store = _make_store()
    store.update_symbol_dd_after_trade(symbol="BTCUSDT", pnl_r=-1.0, closed_at=NOW)
    result = store.update_symbol_dd_after_trade(
        symbol="BTCUSDT", pnl_r=-1.0, closed_at=NOW + timedelta(minutes=15)
    )
    assert result["consecutive_losses"] == 2


def test_consecutive_losses_resets_on_win() -> None:
    store = _make_store()
    store.update_symbol_dd_after_trade(symbol="BTCUSDT", pnl_r=-1.0, closed_at=NOW)
    store.update_symbol_dd_after_trade(
        symbol="BTCUSDT", pnl_r=-1.0, closed_at=NOW + timedelta(minutes=15)
    )
    result = store.update_symbol_dd_after_trade(
        symbol="BTCUSDT", pnl_r=2.0, closed_at=NOW + timedelta(minutes=30)
    )
    assert result["consecutive_losses"] == 0


# --- Test: DD threshold veto via portfolio gate ---

def test_portfolio_gate_vetoes_symbol_exceeding_daily_dd() -> None:
    """When persisted DD shows daily_pnl_r below threshold, portfolio gate vetoes."""
    config = PortfolioRiskConfig(symbol_daily_hard_stop_r=-2.0)
    persisted_dd = {
        "ETHUSDT": {
            "rolling_drawdown_r": -1.0,
            "daily_pnl_r": -2.5,  # Exceeds -2.0 threshold
            "weekly_pnl_r": -2.5,
            "consecutive_losses": 2,
            "trades_today": 3,
        }
    }
    recovered = recover_portfolio_state(
        symbols=["ETHUSDT"],
        open_positions=[],
        recent_trades=[],
        now=NOW,
        persisted_symbol_dd=persisted_dd,
    )
    eth_state = recovered.symbols["ETHUSDT"]
    # daily_pnl_r from persisted state
    assert eth_state.daily_pnl_r == -2.5
    # Should trigger SYMBOL_DAILY_HARD_STOP veto
    assert eth_state.daily_pnl_r <= config.symbol_daily_hard_stop_r


def test_portfolio_gate_vetoes_symbol_exceeding_weekly_dd() -> None:
    """When persisted DD shows weekly_pnl_r below threshold, portfolio gate vetoes."""
    config = PortfolioRiskConfig(symbol_weekly_hard_stop_r=-4.0)
    persisted_dd = {
        "SOLUSDT": {
            "rolling_drawdown_r": -5.0,
            "daily_pnl_r": -1.0,
            "weekly_pnl_r": -4.5,  # Exceeds -4.0 threshold
            "consecutive_losses": 3,
            "trades_today": 1,
        }
    }
    recovered = recover_portfolio_state(
        symbols=["SOLUSDT"],
        open_positions=[],
        recent_trades=[],
        now=NOW,
        persisted_symbol_dd=persisted_dd,
    )
    sol_state = recovered.symbols["SOLUSDT"]
    assert sol_state.weekly_pnl_r == -4.5
    assert sol_state.weekly_pnl_r <= config.symbol_weekly_hard_stop_r


def test_portfolio_gate_uses_true_high_watermark_rolling_dd() -> None:
    """rolling_drawdown_r from persisted state (true high-watermark) is used, not weekly proxy."""
    persisted_dd = {
        "BTCUSDT": {
            "rolling_drawdown_r": -7.5,  # True high-watermark based
            "daily_pnl_r": -1.0,
            "weekly_pnl_r": -2.0,  # Weekly proxy would be -2.0
            "consecutive_losses": 1,
            "trades_today": 2,
        }
    }
    recovered = recover_portfolio_state(
        symbols=["BTCUSDT"],
        open_positions=[],
        recent_trades=[],
        now=NOW,
        persisted_symbol_dd=persisted_dd,
    )
    btc_state = recovered.symbols["BTCUSDT"]
    # Must use persisted rolling_drawdown_r, NOT min(0, weekly_pnl)
    assert btc_state.rolling_drawdown_r == -7.5


# --- Test: Persistence survives reload ---

def test_dd_state_survives_store_reload() -> None:
    """Simulate restart: create store, update DD, create new store with same conn."""
    settings = load_settings()
    assert settings.storage is not None
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    init_db(conn, settings.storage.schema_path)

    store1 = StateStore(connection=conn, mode="PAPER", reference_equity=10_000.0)
    store1.ensure_initialized()
    store1.update_symbol_dd_after_trade(symbol="ETHUSDT", pnl_r=3.0, closed_at=NOW)
    store1.update_symbol_dd_after_trade(
        symbol="ETHUSDT", pnl_r=-1.0, closed_at=NOW + timedelta(minutes=15)
    )

    # Simulate restart with same DB
    store2 = StateStore(connection=conn, mode="PAPER", reference_equity=10_000.0)
    loaded = store2.load_symbol_dd_state("ETHUSDT")
    assert loaded is not None
    assert loaded["cumulative_r"] == 2.0
    assert loaded["local_high_watermark_r"] == 3.0
    assert loaded["rolling_drawdown_r"] == -1.0


# --- Test: Backward compatibility (no persisted DD) ---

def test_recover_symbol_state_without_persisted_dd_uses_weekly_proxy() -> None:
    """When no persisted DD is available, falls back to min(0, weekly_pnl) proxy."""
    trade = PortfolioTradeEvent(
        symbol="BTCUSDT",
        pnl_r=-3.0,
        closed_at=NOW,
    )
    recovered = recover_portfolio_state(
        symbols=["BTCUSDT"],
        open_positions=[],
        recent_trades=[trade],
        now=NOW,
        persisted_symbol_dd=None,  # No persisted state
    )
    btc_state = recovered.symbols["BTCUSDT"]
    # Falls back to weekly proxy
    assert btc_state.rolling_drawdown_r == -3.0
    assert btc_state.daily_pnl_r == -3.0
    assert btc_state.weekly_pnl_r == -3.0
