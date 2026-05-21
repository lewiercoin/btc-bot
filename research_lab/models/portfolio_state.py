"""Research compatibility wrapper for runtime-safe portfolio gate contracts."""

from __future__ import annotations

from core.portfolio_gate import (
    SYMBOL_ORDER,
    PortfolioGateDecision,
    PortfolioOpenPosition,
    PortfolioRiskConfig,
    PortfolioRiskState,
    PortfolioSignal,
    PortfolioTradeEvent,
    PortfolioVetoReason,
    RecoveredPortfolioState,
    ResearchPortfolioGate,
    RuntimePortfolioGate,
    SymbolRiskState,
    recover_portfolio_state,
    sort_portfolio_signals,
)

__all__ = [
    "SYMBOL_ORDER",
    "PortfolioGateDecision",
    "PortfolioOpenPosition",
    "PortfolioRiskConfig",
    "PortfolioRiskState",
    "PortfolioSignal",
    "PortfolioTradeEvent",
    "PortfolioVetoReason",
    "RecoveredPortfolioState",
    "ResearchPortfolioGate",
    "RuntimePortfolioGate",
    "SymbolRiskState",
    "recover_portfolio_state",
    "sort_portfolio_signals",
]
