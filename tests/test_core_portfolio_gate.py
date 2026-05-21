from __future__ import annotations

from datetime import datetime, timezone

from core.portfolio_gate import (
    PortfolioRiskConfig,
    PortfolioRiskState,
    PortfolioSignal,
    PortfolioVetoReason,
    RuntimePortfolioGate,
    sort_portfolio_signals,
)


NOW = datetime(2026, 5, 21, 10, 30, tzinfo=timezone.utc)


def _signal(symbol: str, *, risk_pct: float = 0.0035, notional_pct: float = 0.30) -> PortfolioSignal:
    return PortfolioSignal(
        symbol=symbol,
        timestamp=NOW,
        direction="LONG",
        signal_id=f"{symbol}-sig",
        risk_pct=risk_pct,
        gross_notional_pct=notional_pct,
    )


def test_runtime_portfolio_gate_orders_same_bar_by_contract_symbol_order() -> None:
    ordered = sort_portfolio_signals([_signal("SOLUSDT"), _signal("ETHUSDT"), _signal("BTCUSDT")])

    assert [signal.symbol for signal in ordered] == ["BTCUSDT", "ETHUSDT", "SOLUSDT"]


def test_runtime_portfolio_gate_allows_btc_eth_when_caps_pass() -> None:
    decisions = RuntimePortfolioGate().evaluate_batch(
        [_signal("ETHUSDT"), _signal("BTCUSDT")],
        symbol_states={},
        portfolio_state=PortfolioRiskState(),
        now=NOW,
    )

    assert [decision.signal.symbol for decision in decisions] == ["BTCUSDT", "ETHUSDT"]
    assert [decision.approved for decision in decisions] == [True, True]
    assert decisions[-1].portfolio_risk_after_pct == 0.007


def test_runtime_portfolio_gate_vetoes_second_signal_when_risk_cap_exceeded() -> None:
    decisions = RuntimePortfolioGate(PortfolioRiskConfig(max_total_risk_pct_open=0.005)).evaluate_batch(
        [_signal("BTCUSDT"), _signal("ETHUSDT")],
        symbol_states={},
        portfolio_state=PortfolioRiskState(),
        now=NOW,
    )

    assert decisions[0].approved is True
    assert decisions[1].approved is False
    assert decisions[1].veto_reason == PortfolioVetoReason.PORTFOLIO_RISK_CAP_EXCEEDED.value
