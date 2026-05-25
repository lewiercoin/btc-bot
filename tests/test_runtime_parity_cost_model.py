from __future__ import annotations

from datetime import datetime, timezone

import pytest

from core.models import Position
from scripts.run_runtime_parity_backtest import (
    CostModelConfig,
    DynamicThresholdConfig,
    SymbolRuntime,
    _dynamic_min_sweep_depth_pct,
    _portfolio_state,
    calculate_trade_costs,
)


def test_calculate_trade_costs_applies_fees_slippage_and_funding() -> None:
    opened_at = datetime(2026, 1, 1, 7, 30, tzinfo=timezone.utc)
    closed_at = datetime(2026, 1, 1, 8, 30, tzinfo=timezone.utc)
    position = Position(
        position_id="p1",
        symbol="BTCUSDT",
        direction="LONG",
        status="OPEN",
        entry_price=100.0,
        size=10.0,
        leverage=1,
        stop_loss=95.0,
        take_profit_1=110.0,
        take_profit_2=120.0,
        opened_at=opened_at,
        updated_at=opened_at,
        signal_id="s1",
    )

    costs = calculate_trade_costs(
        position=position,
        exit_price=110.0,
        gross_pnl_abs=100.0,
        gross_pnl_r=2.0,
        closed_at=closed_at,
        funding_samples=[
            {"funding_time": datetime(2026, 1, 1, 8, 0, tzinfo=timezone.utc), "funding_rate": 0.0001}
        ],
        config=CostModelConfig(
            maker_fee_pct=0.0002,
            taker_fee_pct=0.0005,
            slippage_bps_per_side=3.0,
            funding_enabled=True,
            funding_fallback_rate_per_8h=0.0001,
        ),
    )

    assert costs.entry_fee == pytest.approx(0.5)
    assert costs.exit_fee == pytest.approx(0.22)
    assert costs.slippage_total == pytest.approx(0.63)
    assert costs.funding_paid == pytest.approx(0.1)
    assert costs.total_cost == pytest.approx(1.45)
    assert costs.net_pnl_abs == pytest.approx(98.55)
    assert costs.risk_abs == pytest.approx(50.0)
    assert costs.net_pnl_r == pytest.approx(1.971)


def test_dynamic_threshold_uses_fixed_base_when_disabled() -> None:
    threshold = _dynamic_min_sweep_depth_pct(
        base_threshold=0.00649,
        atr_4h_norm=0.012,
        config=DynamicThresholdConfig(mode="fixed"),
    )

    assert threshold == pytest.approx(0.00649)


def test_dynamic_threshold_clamps_atr_relative_value() -> None:
    cfg = DynamicThresholdConfig(
        mode="atr_4h_relative",
        atr_multiplier=0.25,
        floor_threshold=0.0025,
        ceiling_threshold=0.0075,
    )

    assert _dynamic_min_sweep_depth_pct(base_threshold=0.00649, atr_4h_norm=0.020, config=cfg) == pytest.approx(0.005)
    assert _dynamic_min_sweep_depth_pct(base_threshold=0.00649, atr_4h_norm=0.001, config=cfg) == pytest.approx(0.0025)
    assert _dynamic_min_sweep_depth_pct(base_threshold=0.00649, atr_4h_norm=0.100, config=cfg) == pytest.approx(0.0075)


def test_portfolio_state_resets_stale_daily_and_weekly_runtime_pnl() -> None:
    runtime = SymbolRuntime(
        trades_today=3,
        current_day="2026-01-01",
        current_week="2026-W01",
        daily_pnl_r=-3.0,
        weekly_pnl_r=-5.0,
    )

    _, symbol_states = _portfolio_state(
        [],
        {"BTCUSDT": runtime},
        now=datetime(2026, 1, 12, 12, 0, tzinfo=timezone.utc),
    )

    assert symbol_states["BTCUSDT"].trades_today == 0
    assert symbol_states["BTCUSDT"].daily_pnl_r == 0.0
    assert symbol_states["BTCUSDT"].weekly_pnl_r == 0.0
