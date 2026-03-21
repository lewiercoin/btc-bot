from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class SymbolRules:
    symbol: str
    tick_size: float
    step_size: float
    min_qty: float
    min_notional: float
    max_leverage: int
    isolated_only: bool = True


class ExchangeGuard:
    def __init__(self, expected_symbol: str, isolated_only: bool = True) -> None:
        self.expected_symbol = expected_symbol
        self.isolated_only = isolated_only

    def validate_symbol_rules(self, rules: SymbolRules) -> None:
        if rules.symbol != self.expected_symbol:
            raise ValueError(f"Unexpected symbol {rules.symbol}; expected {self.expected_symbol}.")
        if self.isolated_only and not rules.isolated_only:
            raise ValueError("Only isolated mode is allowed in v1.0.")
        if rules.tick_size <= 0 or rules.step_size <= 0:
            raise ValueError("Invalid precision rules from exchange.")
        if rules.min_qty <= 0 or rules.min_notional <= 0:
            raise ValueError("Invalid minimum trading constraints from exchange.")
        if rules.max_leverage <= 0:
            raise ValueError("Invalid max leverage from exchange.")
