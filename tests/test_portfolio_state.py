from __future__ import annotations

from datetime import datetime, timedelta, timezone

from research_lab.models.portfolio_state import (
    PortfolioOpenPosition,
    PortfolioRiskConfig,
    PortfolioRiskState,
    PortfolioSignal,
    PortfolioTradeEvent,
    PortfolioVetoReason,
    ResearchPortfolioGate,
    SymbolRiskState,
    recover_portfolio_state,
    sort_portfolio_signals,
)


NOW = datetime(2026, 5, 19, 12, 0, tzinfo=timezone.utc)


def _signal(
    symbol: str,
    *,
    minute: int = 0,
    direction: str = "LONG",
    risk_pct: float = 0.0035,
    notional_pct: float = 0.30,
) -> PortfolioSignal:
    return PortfolioSignal(
        symbol=symbol,
        timestamp=NOW.replace(minute=minute),
        direction=direction,
        signal_id=f"{symbol}-{minute}-{direction}",
        risk_pct=risk_pct,
        gross_notional_pct=notional_pct,
        confluence_score=4.0,
    )


def test_sort_portfolio_signals_uses_timestamp_then_symbol_order() -> None:
    eth_same_bar = _signal("ETHUSDT")
    btc_same_bar = _signal("BTCUSDT")
    btc_earlier = _signal("BTCUSDT", minute=15)

    ordered = sort_portfolio_signals([eth_same_bar, btc_earlier, btc_same_bar])

    assert [s.signal_id for s in ordered] == [
        "BTCUSDT-0-LONG",
        "ETHUSDT-0-LONG",
        "BTCUSDT-15-LONG",
    ]


def test_allow_both_same_bar_when_portfolio_caps_pass() -> None:
    gate = ResearchPortfolioGate()
    decisions = gate.evaluate_batch(
        [_signal("ETHUSDT"), _signal("BTCUSDT")],
        symbol_states={},
        portfolio_state=PortfolioRiskState(),
        now=NOW,
    )

    assert [d.signal.symbol for d in decisions] == ["BTCUSDT", "ETHUSDT"]
    assert all(d.approved for d in decisions)
    assert decisions[-1].portfolio_risk_after_pct == 0.007


def test_second_same_bar_signal_vetoed_when_total_risk_cap_exceeded() -> None:
    gate = ResearchPortfolioGate(PortfolioRiskConfig(max_total_risk_pct_open=0.005))
    decisions = gate.evaluate_batch(
        [_signal("BTCUSDT"), _signal("ETHUSDT")],
        symbol_states={},
        portfolio_state=PortfolioRiskState(),
        now=NOW,
    )

    assert decisions[0].approved is True
    assert decisions[1].approved is False
    assert decisions[1].veto_reason == PortfolioVetoReason.PORTFOLIO_RISK_CAP_EXCEEDED.value


def test_directional_notional_cap_overrides_allow_both() -> None:
    gate = ResearchPortfolioGate(PortfolioRiskConfig(max_directional_notional_pct=0.50))
    decisions = gate.evaluate_batch(
        [_signal("BTCUSDT", notional_pct=0.30), _signal("ETHUSDT", notional_pct=0.30)],
        symbol_states={},
        portfolio_state=PortfolioRiskState(),
        now=NOW,
    )

    assert decisions[0].approved is True
    assert decisions[1].approved is False
    assert decisions[1].veto_reason == PortfolioVetoReason.DIRECTIONAL_NOTIONAL_CAP_EXCEEDED.value


def test_symbol_state_isolation_does_not_block_other_symbol_loss_streak() -> None:
    gate = ResearchPortfolioGate()
    symbol_states = {
        "BTCUSDT": SymbolRiskState(symbol="BTCUSDT", consecutive_losses=4),
        "ETHUSDT": SymbolRiskState(symbol="ETHUSDT", consecutive_losses=0),
    }
    decisions = gate.evaluate_batch(
        [_signal("BTCUSDT", minute=0), _signal("ETHUSDT", minute=15)],
        symbol_states=symbol_states,
        portfolio_state=PortfolioRiskState(),
        now=NOW,
    )

    assert decisions[0].approved is False
    assert decisions[0].veto_reason == PortfolioVetoReason.SYMBOL_LOSS_STREAK_PAUSE.value
    assert decisions[1].approved is True


def test_symbol_cooldown_blocks_only_that_symbol() -> None:
    gate = ResearchPortfolioGate()
    symbol_states = {
        "BTCUSDT": SymbolRiskState(symbol="BTCUSDT", last_loss_at=NOW - timedelta(minutes=30)),
        "ETHUSDT": SymbolRiskState(symbol="ETHUSDT"),
    }
    decisions = gate.evaluate_batch(
        [_signal("BTCUSDT", minute=0), _signal("ETHUSDT", minute=15)],
        symbol_states=symbol_states,
        portfolio_state=PortfolioRiskState(),
        now=NOW,
    )

    assert decisions[0].approved is False
    assert decisions[0].veto_reason == PortfolioVetoReason.SYMBOL_COOLDOWN_ACTIVE.value
    assert decisions[1].approved is True


def test_portfolio_emergency_stop_blocks_all_symbols() -> None:
    gate = ResearchPortfolioGate()
    decisions = gate.evaluate_batch(
        [_signal("BTCUSDT"), _signal("ETHUSDT")],
        symbol_states={},
        portfolio_state=PortfolioRiskState(emergency_stop_active=True),
        now=NOW,
    )

    assert all(not decision.approved for decision in decisions)
    assert {decision.veto_reason for decision in decisions} == {PortfolioVetoReason.PORTFOLIO_EMERGENCY_STOP.value}


def test_recover_portfolio_state_rebuilds_symbol_and_portfolio_views() -> None:
    state = recover_portfolio_state(
        symbols=("BTCUSDT", "ETHUSDT"),
        open_positions=[
            PortfolioOpenPosition("BTCUSDT", "LONG", 0.0035, 0.30, NOW - timedelta(hours=1)),
            PortfolioOpenPosition("ETHUSDT", "SHORT", 0.0035, 0.25, NOW - timedelta(hours=1)),
        ],
        recent_trades=[
            PortfolioTradeEvent("BTCUSDT", -1.0, NOW - timedelta(hours=2)),
            PortfolioTradeEvent("BTCUSDT", -0.5, NOW - timedelta(hours=1)),
            PortfolioTradeEvent("ETHUSDT", 2.0, NOW - timedelta(hours=1)),
        ],
        now=NOW,
    )

    assert state.portfolio.open_positions_total == 2
    assert state.portfolio.total_risk_pct_open == 0.007
    assert state.portfolio.directional_notional_pct_long == 0.30
    assert state.portfolio.directional_notional_pct_short == 0.25
    assert state.symbols["BTCUSDT"].open_positions_count == 1
    assert state.symbols["BTCUSDT"].consecutive_losses == 2
    assert state.symbols["ETHUSDT"].consecutive_losses == 0
