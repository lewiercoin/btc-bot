from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from typing import Callable

from core.models import ExecutableSignal, Position, RiskRuntimeState, SettlementMetrics


@dataclass(slots=True)
class RiskDecision:
    allowed: bool
    size: float = 0.0
    leverage: int = 0
    reason: str | None = None


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
    partial_exit_pct: float = 0.5
    trailing_atr_mult: float = 1.0


@dataclass(slots=True)
class ExitDecision:
    should_close: bool
    reason: str | None = None
    exit_price: float | None = None
    partial_pct: float | None = None


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
        if runtime.daily_dd_pct >= self.config.daily_dd_limit:
            return RiskDecision(False, reason="daily_dd_limit")
        if runtime.weekly_dd_pct >= self.config.weekly_dd_limit:
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

    def evaluate_exit(
        self,
        position: Position,
        *,
        now: datetime,
        latest_high: float,
        latest_low: float,
        latest_close: float,
        partial_exit_enabled: bool = False,
        partial_exit_done: bool = False,
    ) -> ExitDecision:
        now_utc = now.astimezone(timezone.utc)
        partial_pct = min(max(self.config.partial_exit_pct, 0.0), 1.0)
        allow_partial = partial_exit_enabled and not partial_exit_done and partial_pct > 0.0
        if position.direction == "LONG":
            # Conservative ordering for ambiguous candles: SL before TP.
            if latest_low <= position.stop_loss:
                if partial_exit_done:
                    return ExitDecision(True, "TP_TRAIL", position.stop_loss)
                return ExitDecision(True, "SL", position.stop_loss)
            if not partial_exit_done and latest_high >= position.take_profit_1:
                if allow_partial and partial_pct < 1.0:
                    return ExitDecision(True, "TP_PARTIAL", position.take_profit_1, partial_pct=partial_pct)
                return ExitDecision(True, "TP", position.take_profit_1)
        else:
            if latest_high >= position.stop_loss:
                if partial_exit_done:
                    return ExitDecision(True, "TP_TRAIL", position.stop_loss)
                return ExitDecision(True, "SL", position.stop_loss)
            if not partial_exit_done and latest_low <= position.take_profit_1:
                if allow_partial and partial_pct < 1.0:
                    return ExitDecision(True, "TP_PARTIAL", position.take_profit_1, partial_pct=partial_pct)
                return ExitDecision(True, "TP", position.take_profit_1)

        hold_limit = timedelta(hours=self.config.max_hold_hours)
        if now_utc - position.opened_at.astimezone(timezone.utc) >= hold_limit:
            return ExitDecision(True, "TIMEOUT", latest_close)
        return ExitDecision(False, None, None)

    def build_settlement_metrics(
        self,
        position: Position,
        *,
        exit_price: float,
        exit_reason: str,
        candles_15m: list[dict[str, Any]],
    ) -> SettlementMetrics:
        pnl_abs = self._compute_pnl_abs(position, exit_price)
        pnl_r = self._compute_pnl_r(position, exit_price)
        mae, mfe = self._compute_mae_mfe(position, exit_price, candles_15m)
        return SettlementMetrics(
            exit_price=exit_price,
            pnl_abs=pnl_abs,
            pnl_r=pnl_r,
            mae=mae,
            mfe=mfe,
            exit_reason=exit_reason,
        )

    @staticmethod
    def _compute_pnl_abs(position: Position, exit_price: float) -> float:
        if position.direction == "LONG":
            return (exit_price - position.entry_price) * position.size
        return (position.entry_price - exit_price) * position.size

    @staticmethod
    def _compute_pnl_r(position: Position, exit_price: float) -> float:
        risk_per_unit = abs(position.entry_price - position.stop_loss)
        if risk_per_unit <= 0:
            return 0.0
        if position.direction == "LONG":
            return (exit_price - position.entry_price) / risk_per_unit
        return (position.entry_price - exit_price) / risk_per_unit

    @staticmethod
    def _compute_mae_mfe(position: Position, exit_price: float, candles_15m: list[dict[str, Any]]) -> tuple[float, float]:
        if candles_15m:
            lows = [float(c["low"]) for c in candles_15m]
            highs = [float(c["high"]) for c in candles_15m]
        else:
            lows = [exit_price]
            highs = [exit_price]

        entry = position.entry_price
        if position.direction == "LONG":
            worst_price = min(lows)
            best_price = max(highs)
            mae = max((entry - worst_price) * position.size, 0.0)
            mfe = max((best_price - entry) * position.size, 0.0)
        else:
            worst_price = max(highs)
            best_price = min(lows)
            mae = max((worst_price - entry) * position.size, 0.0)
            mfe = max((entry - best_price) * position.size, 0.0)
        return mae, mfe
