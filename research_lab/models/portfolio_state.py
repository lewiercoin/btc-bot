"""Research-only portfolio state and gate contracts for BTC+ETH replay.

These models intentionally live under research_lab. They are not imported by the
runtime bot and are not a production state contract until a later audited
promotion moves an equivalent contract into the runtime layers.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from typing import Iterable


SYMBOL_ORDER: tuple[str, ...] = ("BTCUSDT", "ETHUSDT", "SOLUSDT")


class PortfolioVetoReason(StrEnum):
    SYMBOL_PAUSED = "symbol_paused"
    SYMBOL_DAILY_HARD_STOP = "symbol_daily_hard_stop"
    SYMBOL_WEEKLY_HARD_STOP = "symbol_weekly_hard_stop"
    SYMBOL_ROLLING_PAUSE = "symbol_rolling_pause"
    SYMBOL_LOSS_STREAK_PAUSE = "symbol_loss_streak_pause"
    SYMBOL_COOLDOWN_ACTIVE = "symbol_cooldown_active"
    SYMBOL_POSITION_CAP_EXCEEDED = "symbol_position_cap_exceeded"
    PORTFOLIO_PAUSED = "portfolio_paused"
    PORTFOLIO_EMERGENCY_STOP = "portfolio_emergency_stop"
    PORTFOLIO_DAILY_HARD_STOP = "portfolio_daily_hard_stop"
    PORTFOLIO_WEEKLY_HARD_STOP = "portfolio_weekly_hard_stop"
    PORTFOLIO_LOSS_STREAK_PAUSE = "portfolio_loss_streak_pause"
    PORTFOLIO_POSITION_CAP_EXCEEDED = "portfolio_position_cap_exceeded"
    PORTFOLIO_RISK_CAP_EXCEEDED = "portfolio_risk_cap_exceeded"
    GROSS_NOTIONAL_CAP_EXCEEDED = "gross_notional_cap_exceeded"
    DIRECTIONAL_NOTIONAL_CAP_EXCEEDED = "directional_notional_cap_exceeded"


@dataclass(frozen=True, slots=True)
class PortfolioRiskConfig:
    """Offline defaults from MULTI_ASSET_PORTFOLIO_ARCHITECTURE_V1."""

    risk_per_trade_pct_per_symbol: float = 0.0035
    max_total_risk_pct_open: float = 0.0070
    max_open_positions_total: int = 2
    max_open_positions_per_symbol: int = 1
    max_gross_notional_pct: float = 1.0
    max_directional_notional_pct: float = 0.75
    portfolio_daily_soft_stop_r: float = -2.0
    portfolio_daily_hard_stop_r: float = -3.0
    portfolio_weekly_soft_stop_r: float = -4.0
    portfolio_weekly_hard_stop_r: float = -6.0
    portfolio_emergency_stop_r: float = -8.0
    symbol_daily_hard_stop_r: float = -2.0
    symbol_weekly_hard_stop_r: float = -4.0
    symbol_rolling_pause_r: float = -6.0
    symbol_loss_streak_pause: int = 4
    global_loss_streak_pause: int = 6
    loss_streak_pause_minutes: int = 125
    cooldown_after_loss_minutes: int = 125
    symbol_order: tuple[str, ...] = SYMBOL_ORDER


@dataclass(frozen=True, slots=True)
class SymbolRiskState:
    symbol: str
    open_positions_count: int = 0
    trades_today: int = 0
    consecutive_losses: int = 0
    daily_pnl_r: float = 0.0
    weekly_pnl_r: float = 0.0
    rolling_drawdown_r: float = 0.0
    last_trade_at: datetime | None = None
    last_loss_at: datetime | None = None
    symbol_paused_until: datetime | None = None
    pause_reason: str | None = None

    def is_paused(self, now: datetime) -> bool:
        return self.symbol_paused_until is not None and _to_utc(self.symbol_paused_until) > _to_utc(now)


@dataclass(frozen=True, slots=True)
class PortfolioRiskState:
    open_positions_total: int = 0
    gross_notional_pct: float = 0.0
    directional_notional_pct_long: float = 0.0
    directional_notional_pct_short: float = 0.0
    total_risk_pct_open: float = 0.0
    daily_pnl_r: float = 0.0
    weekly_pnl_r: float = 0.0
    rolling_drawdown_r: float = 0.0
    global_consecutive_losses: int = 0
    portfolio_paused_until: datetime | None = None
    emergency_stop_active: bool = False
    last_portfolio_loss_at: datetime | None = None

    def is_paused(self, now: datetime) -> bool:
        return self.portfolio_paused_until is not None and _to_utc(self.portfolio_paused_until) > _to_utc(now)


@dataclass(frozen=True, slots=True)
class PortfolioSignal:
    symbol: str
    timestamp: datetime
    direction: str
    signal_id: str
    risk_pct: float
    gross_notional_pct: float
    confluence_score: float = 0.0

    @property
    def normalized_symbol(self) -> str:
        return self.symbol.upper()

    @property
    def normalized_direction(self) -> str:
        return self.direction.upper()


@dataclass(frozen=True, slots=True)
class PortfolioGateDecision:
    signal: PortfolioSignal
    approved: bool
    veto_reason: str | None = None
    portfolio_risk_after_pct: float | None = None
    gross_notional_after_pct: float | None = None
    directional_notional_after_pct: float | None = None


@dataclass(frozen=True, slots=True)
class PortfolioOpenPosition:
    symbol: str
    direction: str
    risk_pct: float
    gross_notional_pct: float
    opened_at: datetime


@dataclass(frozen=True, slots=True)
class PortfolioTradeEvent:
    symbol: str
    pnl_r: float
    closed_at: datetime


@dataclass(frozen=True, slots=True)
class RecoveredPortfolioState:
    portfolio: PortfolioRiskState
    symbols: dict[str, SymbolRiskState]


class ResearchPortfolioGate:
    """Deterministic offline portfolio gate for candidate signal batches."""

    def __init__(self, config: PortfolioRiskConfig | None = None) -> None:
        self.config = config or PortfolioRiskConfig()

    def evaluate_batch(
        self,
        signals: Iterable[PortfolioSignal],
        *,
        symbol_states: dict[str, SymbolRiskState],
        portfolio_state: PortfolioRiskState,
        now: datetime,
    ) -> list[PortfolioGateDecision]:
        decisions: list[PortfolioGateDecision] = []
        accepted: list[PortfolioSignal] = []

        for signal in sort_portfolio_signals(signals, symbol_order=self.config.symbol_order):
            decision = self._evaluate_one(
                signal,
                symbol_state=symbol_states.get(signal.normalized_symbol, SymbolRiskState(symbol=signal.normalized_symbol)),
                portfolio_state=portfolio_state,
                accepted=accepted,
                now=now,
            )
            decisions.append(decision)
            if decision.approved:
                accepted.append(signal)

        return decisions

    def _evaluate_one(
        self,
        signal: PortfolioSignal,
        *,
        symbol_state: SymbolRiskState,
        portfolio_state: PortfolioRiskState,
        accepted: list[PortfolioSignal],
        now: datetime,
    ) -> PortfolioGateDecision:
        veto = self._symbol_veto(symbol_state, now)
        if veto is not None:
            return PortfolioGateDecision(signal=signal, approved=False, veto_reason=veto.value)

        veto = self._portfolio_veto(portfolio_state, now)
        if veto is not None:
            return PortfolioGateDecision(signal=signal, approved=False, veto_reason=veto.value)

        accepted_for_symbol = [s for s in accepted if s.normalized_symbol == signal.normalized_symbol]
        if symbol_state.open_positions_count + len(accepted_for_symbol) >= self.config.max_open_positions_per_symbol:
            return PortfolioGateDecision(
                signal=signal,
                approved=False,
                veto_reason=PortfolioVetoReason.SYMBOL_POSITION_CAP_EXCEEDED.value,
            )

        if portfolio_state.open_positions_total + len(accepted) >= self.config.max_open_positions_total:
            return PortfolioGateDecision(
                signal=signal,
                approved=False,
                veto_reason=PortfolioVetoReason.PORTFOLIO_POSITION_CAP_EXCEEDED.value,
            )

        risk_after = portfolio_state.total_risk_pct_open + sum(s.risk_pct for s in accepted) + signal.risk_pct
        if risk_after > self.config.max_total_risk_pct_open + 1e-12:
            return PortfolioGateDecision(
                signal=signal,
                approved=False,
                veto_reason=PortfolioVetoReason.PORTFOLIO_RISK_CAP_EXCEEDED.value,
                portfolio_risk_after_pct=risk_after,
            )

        gross_after = portfolio_state.gross_notional_pct + sum(s.gross_notional_pct for s in accepted) + signal.gross_notional_pct
        if gross_after > self.config.max_gross_notional_pct + 1e-12:
            return PortfolioGateDecision(
                signal=signal,
                approved=False,
                veto_reason=PortfolioVetoReason.GROSS_NOTIONAL_CAP_EXCEEDED.value,
                gross_notional_after_pct=gross_after,
            )

        directional_after = _directional_notional_after(portfolio_state, accepted, signal)
        if directional_after > self.config.max_directional_notional_pct + 1e-12:
            return PortfolioGateDecision(
                signal=signal,
                approved=False,
                veto_reason=PortfolioVetoReason.DIRECTIONAL_NOTIONAL_CAP_EXCEEDED.value,
                directional_notional_after_pct=directional_after,
            )

        return PortfolioGateDecision(
            signal=signal,
            approved=True,
            portfolio_risk_after_pct=risk_after,
            gross_notional_after_pct=gross_after,
            directional_notional_after_pct=directional_after,
        )

    def _symbol_veto(self, state: SymbolRiskState, now: datetime) -> PortfolioVetoReason | None:
        if state.is_paused(now):
            return PortfolioVetoReason.SYMBOL_PAUSED
        if state.daily_pnl_r <= self.config.symbol_daily_hard_stop_r:
            return PortfolioVetoReason.SYMBOL_DAILY_HARD_STOP
        if state.weekly_pnl_r <= self.config.symbol_weekly_hard_stop_r:
            return PortfolioVetoReason.SYMBOL_WEEKLY_HARD_STOP
        if state.rolling_drawdown_r <= self.config.symbol_rolling_pause_r:
            return PortfolioVetoReason.SYMBOL_ROLLING_PAUSE
        if state.consecutive_losses >= self.config.symbol_loss_streak_pause and _loss_streak_pause_active(
            state.last_loss_at,
            now,
            pause_minutes=self.config.loss_streak_pause_minutes,
        ):
            return PortfolioVetoReason.SYMBOL_LOSS_STREAK_PAUSE
        if state.last_loss_at is not None:
            cooldown_until = _to_utc(state.last_loss_at) + timedelta(minutes=self.config.cooldown_after_loss_minutes)
            if cooldown_until > _to_utc(now):
                return PortfolioVetoReason.SYMBOL_COOLDOWN_ACTIVE
        return None

    def _portfolio_veto(self, state: PortfolioRiskState, now: datetime) -> PortfolioVetoReason | None:
        if state.is_paused(now):
            return PortfolioVetoReason.PORTFOLIO_PAUSED
        if state.emergency_stop_active or state.rolling_drawdown_r <= self.config.portfolio_emergency_stop_r:
            return PortfolioVetoReason.PORTFOLIO_EMERGENCY_STOP
        if state.daily_pnl_r <= self.config.portfolio_daily_hard_stop_r:
            return PortfolioVetoReason.PORTFOLIO_DAILY_HARD_STOP
        if state.weekly_pnl_r <= self.config.portfolio_weekly_hard_stop_r:
            return PortfolioVetoReason.PORTFOLIO_WEEKLY_HARD_STOP
        if state.global_consecutive_losses >= self.config.global_loss_streak_pause and _loss_streak_pause_active(
            state.last_portfolio_loss_at,
            now,
            pause_minutes=self.config.loss_streak_pause_minutes,
        ):
            return PortfolioVetoReason.PORTFOLIO_LOSS_STREAK_PAUSE
        return None


def sort_portfolio_signals(
    signals: Iterable[PortfolioSignal],
    *,
    symbol_order: tuple[str, ...] = SYMBOL_ORDER,
) -> list[PortfolioSignal]:
    rank = {symbol.upper(): index for index, symbol in enumerate(symbol_order)}
    return sorted(
        signals,
        key=lambda s: (
            _to_utc(s.timestamp),
            rank.get(s.normalized_symbol, len(rank)),
            s.normalized_symbol,
            s.signal_id,
        ),
    )


def recover_portfolio_state(
    *,
    symbols: Iterable[str],
    open_positions: Iterable[PortfolioOpenPosition],
    recent_trades: Iterable[PortfolioTradeEvent],
    now: datetime,
) -> RecoveredPortfolioState:
    """Rebuild research portfolio state from deterministic inputs.

    This is a pure offline recovery simulation, not a runtime exchange sync.
    """

    normalized_symbols = tuple(symbol.upper() for symbol in symbols)
    position_list = list(open_positions)
    trade_list = list(recent_trades)
    symbol_states: dict[str, SymbolRiskState] = {}
    for symbol in normalized_symbols:
        symbol_positions = [p for p in position_list if p.symbol.upper() == symbol]
        symbol_trades = [t for t in trade_list if t.symbol.upper() == symbol]
        symbol_states[symbol] = _recover_symbol_state(symbol, symbol_positions, symbol_trades, now)

    total_risk = sum(float(p.risk_pct) for p in position_list)
    gross = sum(float(p.gross_notional_pct) for p in position_list)
    long_notional = sum(float(p.gross_notional_pct) for p in position_list if p.direction.upper() == "LONG")
    short_notional = sum(float(p.gross_notional_pct) for p in position_list if p.direction.upper() == "SHORT")
    daily_pnl = sum(t.pnl_r for t in trade_list if _same_utc_day(t.closed_at, now))
    weekly_pnl = sum(t.pnl_r for t in trade_list if _within_rolling_days(t.closed_at, now, days=7))
    portfolio = PortfolioRiskState(
        open_positions_total=len(position_list),
        gross_notional_pct=gross,
        directional_notional_pct_long=long_notional,
        directional_notional_pct_short=short_notional,
        total_risk_pct_open=total_risk,
        daily_pnl_r=daily_pnl,
        weekly_pnl_r=weekly_pnl,
        rolling_drawdown_r=min(0.0, weekly_pnl),
        global_consecutive_losses=_global_consecutive_losses(trade_list),
        last_portfolio_loss_at=_last_loss_at(trade_list),
    )
    return RecoveredPortfolioState(portfolio=portfolio, symbols=symbol_states)


def _recover_symbol_state(
    symbol: str,
    open_positions: list[PortfolioOpenPosition],
    trades: list[PortfolioTradeEvent],
    now: datetime,
) -> SymbolRiskState:
    daily_pnl = sum(t.pnl_r for t in trades if _same_utc_day(t.closed_at, now))
    weekly_pnl = sum(t.pnl_r for t in trades if _within_rolling_days(t.closed_at, now, days=7))
    return SymbolRiskState(
        symbol=symbol,
        open_positions_count=len(open_positions),
        trades_today=sum(1 for t in trades if _same_utc_day(t.closed_at, now)),
        consecutive_losses=_global_consecutive_losses(trades),
        daily_pnl_r=daily_pnl,
        weekly_pnl_r=weekly_pnl,
        rolling_drawdown_r=min(0.0, weekly_pnl),
        last_trade_at=max((_to_utc(t.closed_at) for t in trades), default=None),
        last_loss_at=_last_loss_at(trades),
    )


def _directional_notional_after(
    portfolio_state: PortfolioRiskState,
    accepted: list[PortfolioSignal],
    signal: PortfolioSignal,
) -> float:
    if signal.normalized_direction == "SHORT":
        base = portfolio_state.directional_notional_pct_short
        same_side = [s for s in accepted if s.normalized_direction == "SHORT"]
    else:
        base = portfolio_state.directional_notional_pct_long
        same_side = [s for s in accepted if s.normalized_direction == "LONG"]
    return base + sum(s.gross_notional_pct for s in same_side) + signal.gross_notional_pct


def _global_consecutive_losses(trades: list[PortfolioTradeEvent]) -> int:
    current = 0
    for trade in sorted(trades, key=lambda t: _to_utc(t.closed_at), reverse=True):
        if trade.pnl_r < 0:
            current += 1
        else:
            break
    return current


def _last_loss_at(trades: list[PortfolioTradeEvent]) -> datetime | None:
    losses = [_to_utc(t.closed_at) for t in trades if t.pnl_r < 0]
    return max(losses) if losses else None


def _same_utc_day(left: datetime, right: datetime) -> bool:
    return _to_utc(left).date() == _to_utc(right).date()


def _within_rolling_days(left: datetime, right: datetime, *, days: int) -> bool:
    left_utc = _to_utc(left)
    right_utc = _to_utc(right)
    return right_utc - timedelta(days=days) < left_utc <= right_utc


def _loss_streak_pause_active(last_loss_at: datetime | None, now: datetime, *, pause_minutes: int) -> bool:
    if last_loss_at is None:
        return True
    return _to_utc(last_loss_at) + timedelta(minutes=pause_minutes) > _to_utc(now)


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
