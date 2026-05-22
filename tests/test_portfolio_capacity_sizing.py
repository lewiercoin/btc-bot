from __future__ import annotations

from datetime import datetime, timezone

from core.portfolio_gate import PortfolioRiskConfig, PortfolioRiskState, PortfolioSignal
from orchestrator import _apply_portfolio_capacity_sizing


NOW = datetime(2026, 5, 22, 12, 0, tzinfo=timezone.utc)


def _signal(
    symbol: str = "BTCUSDT",
    *,
    risk_pct: float = 0.005,
    gross_notional_pct: float = 2.0,
    direction: str = "LONG",
) -> PortfolioSignal:
    return PortfolioSignal(
        symbol=symbol,
        timestamp=NOW,
        direction=direction,
        signal_id=f"{symbol}-sig",
        risk_pct=risk_pct,
        gross_notional_pct=gross_notional_pct,
    )


def test_portfolio_capacity_sizing_reduces_signal_to_available_gross_cap() -> None:
    signals, adjustments = _apply_portfolio_capacity_sizing(
        [_signal(gross_notional_pct=2.0, risk_pct=0.005)],
        portfolio_state=PortfolioRiskState(),
        config=PortfolioRiskConfig(
            max_gross_notional_pct=1.0,
            max_directional_notional_pct=1.0,
            max_total_risk_pct_open=0.007,
        ),
    )

    assert len(signals) == 1
    assert signals[0].gross_notional_pct == 1.0
    assert signals[0].risk_pct == 0.0025
    assert adjustments["BTCUSDT-sig"].size_scale == 0.5
    assert adjustments["BTCUSDT-sig"].reason == "gross_notional_cap"


def test_portfolio_capacity_sizing_reserves_capacity_in_contract_symbol_order() -> None:
    signals, adjustments = _apply_portfolio_capacity_sizing(
        [
            _signal("ETHUSDT", gross_notional_pct=0.8, risk_pct=0.003),
            _signal("BTCUSDT", gross_notional_pct=0.8, risk_pct=0.003),
        ],
        portfolio_state=PortfolioRiskState(),
        config=PortfolioRiskConfig(
            max_gross_notional_pct=1.0,
            max_directional_notional_pct=1.0,
            max_total_risk_pct_open=0.007,
            symbol_order=("BTCUSDT", "ETHUSDT", "SOLUSDT"),
        ),
    )

    assert [signal.symbol for signal in signals] == ["BTCUSDT", "ETHUSDT"]
    assert signals[0].gross_notional_pct == 0.8
    assert signals[1].gross_notional_pct == 0.19999999999999996
    assert "BTCUSDT-sig" not in adjustments
    assert adjustments["ETHUSDT-sig"].reason == "gross_notional_cap"


def test_portfolio_capacity_sizing_leaves_signal_for_gate_when_no_capacity_remains() -> None:
    original = _signal(gross_notional_pct=0.5, risk_pct=0.002)

    signals, adjustments = _apply_portfolio_capacity_sizing(
        [original],
        portfolio_state=PortfolioRiskState(gross_notional_pct=1.0, directional_notional_pct_long=1.0),
        config=PortfolioRiskConfig(
            max_gross_notional_pct=1.0,
            max_directional_notional_pct=1.0,
            max_total_risk_pct_open=0.007,
        ),
    )

    assert signals == [original]
    assert adjustments == {}
