from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from core.models import ExecutableSignal, Position, RiskRuntimeState
from core.risk_engine import RiskConfig, RiskEngine


def _signal(
    *,
    direction: str = "LONG",
    entry_price: float = 100.0,
    stop_loss: float = 95.0,
    take_profit_1: float = 110.0,
    take_profit_2: float = 120.0,
    rr_ratio: float = 3.0,
) -> ExecutableSignal:
    return ExecutableSignal(
        signal_id="sig-risk-test",
        timestamp=datetime(2026, 4, 27, 12, 0, tzinfo=timezone.utc),
        direction=direction,
        entry_price=entry_price,
        stop_loss=stop_loss,
        take_profit_1=take_profit_1,
        take_profit_2=take_profit_2,
        rr_ratio=rr_ratio,
        approved_by_governance=True,
        governance_notes=["approved"],
    )


def _position(
    *,
    direction: str = "LONG",
    entry_price: float = 100.0,
    stop_loss: float = 95.0,
    take_profit_1: float = 110.0,
    take_profit_2: float = 120.0,
    size: float = 2.0,
    opened_at: datetime | None = None,
) -> Position:
    opened = opened_at or datetime(2026, 4, 27, 12, 0, tzinfo=timezone.utc)
    return Position(
        position_id="pos-risk-test",
        symbol="BTCUSDT",
        direction=direction,
        status="OPEN",
        entry_price=entry_price,
        size=size,
        leverage=5,
        stop_loss=stop_loss,
        take_profit_1=take_profit_1,
        take_profit_2=take_profit_2,
        opened_at=opened,
        updated_at=opened,
        signal_id="sig-risk-test",
    )


def test_evaluate_sizes_by_risk_capital_when_not_leverage_capped() -> None:
    engine = RiskEngine(RiskConfig(risk_per_trade_pct=0.01, min_rr=2.0, max_leverage=5))

    decision = engine.evaluate(_signal(), equity=10_000.0, open_positions=0)

    assert decision.allowed is True
    assert decision.reason is None
    assert decision.leverage == 3
    assert decision.size == pytest.approx(20.0)


def test_evaluate_caps_size_by_selected_leverage() -> None:
    engine = RiskEngine(RiskConfig(risk_per_trade_pct=0.50, min_rr=2.0, max_leverage=5))

    decision = engine.evaluate(_signal(entry_price=100.0, stop_loss=99.5), equity=1_000.0, open_positions=0)

    assert decision.allowed is True
    assert decision.leverage == 5
    assert decision.size == pytest.approx(50.0)


def test_evaluate_selects_high_vol_leverage_when_stop_distance_is_wide() -> None:
    engine = RiskEngine(RiskConfig(min_rr=2.0, max_leverage=5, high_vol_leverage=3, high_vol_stop_distance_pct=0.01))

    high_vol = engine.evaluate(_signal(entry_price=100.0, stop_loss=99.0), equity=10_000.0, open_positions=0)
    normal_vol = engine.evaluate(_signal(entry_price=100.0, stop_loss=99.01), equity=10_000.0, open_positions=0)

    assert high_vol.leverage == 3
    assert normal_vol.leverage == 5


@pytest.mark.parametrize(
    ("equity", "open_positions", "signal", "runtime", "expected_reason"),
    [
        (0.0, 0, _signal(), RiskRuntimeState(), "invalid_equity"),
        (10_000.0, 2, _signal(), RiskRuntimeState(), "max_open_positions"),
        (10_000.0, 0, _signal(rr_ratio=1.9), RiskRuntimeState(), "rr_below_min:1.900"),
        (10_000.0, 0, _signal(entry_price=100.0, stop_loss=100.0), RiskRuntimeState(), "invalid_stop_distance"),
        (10_000.0, 0, _signal(), RiskRuntimeState(consecutive_losses=3), "max_consecutive_losses"),
        (10_000.0, 0, _signal(), RiskRuntimeState(daily_dd_pct=0.03), "daily_dd_limit"),
        (10_000.0, 0, _signal(), RiskRuntimeState(weekly_dd_pct=0.06), "weekly_dd_limit"),
    ],
)
def test_evaluate_vetoes_safety_gate_failures(
    equity: float,
    open_positions: int,
    signal: ExecutableSignal,
    runtime: RiskRuntimeState,
    expected_reason: str,
) -> None:
    engine = RiskEngine(
        RiskConfig(min_rr=2.0, max_open_positions=2, max_consecutive_losses=3, daily_dd_limit=0.03, weekly_dd_limit=0.06),
        state_provider=lambda: runtime,
    )

    decision = engine.evaluate(signal, equity=equity, open_positions=open_positions)

    assert decision.allowed is False
    assert decision.size == 0.0
    assert decision.leverage == 0
    assert decision.reason == expected_reason


def test_long_exit_uses_stop_before_take_profit_for_ambiguous_candle() -> None:
    engine = RiskEngine(RiskConfig(max_hold_hours=24))
    position = _position(direction="LONG", stop_loss=95.0, take_profit_1=110.0)

    decision = engine.evaluate_exit(
        position,
        now=position.opened_at + timedelta(hours=1),
        latest_high=111.0,
        latest_low=94.0,
        latest_close=105.0,
    )

    assert decision.should_close is True
    assert decision.reason == "SL"
    assert decision.exit_price == 95.0


def test_short_exit_uses_stop_before_take_profit_for_ambiguous_candle() -> None:
    engine = RiskEngine(RiskConfig(max_hold_hours=24))
    position = _position(direction="SHORT", stop_loss=105.0, take_profit_1=90.0)

    decision = engine.evaluate_exit(
        position,
        now=position.opened_at + timedelta(hours=1),
        latest_high=106.0,
        latest_low=89.0,
        latest_close=97.0,
    )

    assert decision.should_close is True
    assert decision.reason == "SL"
    assert decision.exit_price == 105.0


def test_exit_supports_partial_take_profit_and_trailing_stop() -> None:
    engine = RiskEngine(RiskConfig(partial_exit_pct=0.5))
    position = _position(direction="LONG", stop_loss=95.0, take_profit_1=110.0)

    partial = engine.evaluate_exit(
        position,
        now=position.opened_at + timedelta(hours=1),
        latest_high=111.0,
        latest_low=99.0,
        latest_close=110.0,
        partial_exit_enabled=True,
        partial_exit_done=False,
    )
    trail = engine.evaluate_exit(
        position,
        now=position.opened_at + timedelta(hours=2),
        latest_high=104.0,
        latest_low=94.0,
        latest_close=96.0,
        partial_exit_enabled=True,
        partial_exit_done=True,
    )

    assert partial.should_close is True
    assert partial.reason == "TP_PARTIAL"
    assert partial.exit_price == 110.0
    assert partial.partial_pct == pytest.approx(0.5)
    assert trail.should_close is True
    assert trail.reason == "TP_TRAIL"
    assert trail.exit_price == 95.0


def test_exit_times_out_at_hold_limit() -> None:
    engine = RiskEngine(RiskConfig(max_hold_hours=4))
    position = _position(opened_at=datetime(2026, 4, 27, 12, 0, tzinfo=timezone.utc))

    decision = engine.evaluate_exit(
        position,
        now=datetime(2026, 4, 27, 16, 0, tzinfo=timezone.utc),
        latest_high=104.0,
        latest_low=98.0,
        latest_close=101.25,
    )

    assert decision.should_close is True
    assert decision.reason == "TIMEOUT"
    assert decision.exit_price == 101.25


def test_settlement_metrics_for_long_stop_loss_are_minus_one_r() -> None:
    engine = RiskEngine()
    position = _position(direction="LONG", entry_price=100.0, stop_loss=95.0, size=2.0)

    settlement = engine.build_settlement_metrics(
        position,
        exit_price=95.0,
        exit_reason="SL",
        candles_15m=[{"low": 94.0, "high": 108.0}],
    )

    assert settlement.pnl_abs == pytest.approx(-10.0)
    assert settlement.pnl_r == pytest.approx(-1.0)
    assert settlement.mae == pytest.approx(12.0)
    assert settlement.mfe == pytest.approx(16.0)
    assert settlement.exit_reason == "SL"


def test_settlement_metrics_for_short_take_profit_are_positive_r() -> None:
    engine = RiskEngine()
    position = _position(direction="SHORT", entry_price=100.0, stop_loss=105.0, take_profit_1=90.0, size=3.0)

    settlement = engine.build_settlement_metrics(
        position,
        exit_price=90.0,
        exit_reason="TP",
        candles_15m=[{"low": 88.0, "high": 103.0}],
    )

    assert settlement.pnl_abs == pytest.approx(30.0)
    assert settlement.pnl_r == pytest.approx(2.0)
    assert settlement.mae == pytest.approx(9.0)
    assert settlement.mfe == pytest.approx(36.0)
    assert settlement.exit_reason == "TP"


def test_settlement_metrics_returns_zero_r_for_invalid_position_risk() -> None:
    engine = RiskEngine()
    position = _position(direction="LONG", entry_price=100.0, stop_loss=100.0, size=1.0)

    settlement = engine.build_settlement_metrics(position, exit_price=101.0, exit_reason="TIMEOUT", candles_15m=[])

    assert settlement.pnl_abs == pytest.approx(1.0)
    assert settlement.pnl_r == 0.0
    assert settlement.mae == 0.0
    assert settlement.mfe == pytest.approx(1.0)
