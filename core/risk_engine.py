from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from core.models import ExecutableSignal


@dataclass(slots=True)
class RiskDecision:
    allowed: bool
    size: float = 0.0
    leverage: int = 0
    reason: str | None = None


@dataclass(slots=True)
class RiskRuntimeState:
    consecutive_losses: int = 0
    daily_dd_pct: float = 0.0
    weekly_dd_pct: float = 0.0


@dataclass(slots=True)
class RiskConfig:
    risk_per_trade_pct: float = 0.01
    max_leverage: int = 5
    high_vol_leverage: int = 3
    min_rr: float = 2.8
    max_open_positions: int = 2
    max_consecutive_losses: int = 3
    daily_dd_limit: float = 0.03
    weekly_dd_limit: float = 0.06
    max_hold_hours: int = 24
    high_vol_stop_distance_pct: float = 0.01


class RiskEngine:
    def __init__(
        self,
        config: RiskConfig | None = None,
        state_provider: Callable[[], RiskRuntimeState] | None = None,
    ) -> None:
        self.config = config or RiskConfig()
        self.state_provider = state_provider or (lambda: RiskRuntimeState())

    def evaluate(self, signal: ExecutableSignal, equity: float, open_positions: int) -> RiskDecision:
        if equity <= 0:
            return RiskDecision(False, reason="invalid_equity")
        if open_positions >= self.config.max_open_positions:
            return RiskDecision(False, reason="max_open_positions")
        if signal.rr_ratio < self.config.min_rr:
            return RiskDecision(False, reason=f"rr_below_min:{signal.rr_ratio:.3f}")

        runtime = self.state_provider()
        if runtime.consecutive_losses >= self.config.max_consecutive_losses:
            return RiskDecision(False, reason="max_consecutive_losses")
        if runtime.daily_dd_pct > self.config.daily_dd_limit:
            return RiskDecision(False, reason="daily_dd_limit")
        if runtime.weekly_dd_pct > self.config.weekly_dd_limit:
            return RiskDecision(False, reason="weekly_dd_limit")

        stop_distance = abs(signal.entry_price - signal.stop_loss)
        if stop_distance <= 0:
            return RiskDecision(False, reason="invalid_stop_distance")

        leverage = self._select_leverage(signal)
        risk_capital = equity * self.config.risk_per_trade_pct
        raw_size = risk_capital / stop_distance
        max_size_by_leverage = (equity * leverage) / max(signal.entry_price, 1e-8)
        size = min(raw_size, max_size_by_leverage)

        if size <= 0:
            return RiskDecision(False, reason="non_positive_size")
        return RiskDecision(True, size=size, leverage=leverage, reason=None)

    def _select_leverage(self, signal: ExecutableSignal) -> int:
        stop_distance_pct = abs(signal.entry_price - signal.stop_loss) / max(signal.entry_price, 1e-8)
        if stop_distance_pct >= self.config.high_vol_stop_distance_pct:
            return min(self.config.high_vol_leverage, self.config.max_leverage)
        return self.config.max_leverage
