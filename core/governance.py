from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable

from core.models import ExecutableSignal, SignalCandidate


@dataclass(slots=True)
class GovernanceDecision:
    approved: bool
    notes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class GovernanceRuntimeState:
    trades_today: int = 0
    consecutive_losses: int = 0
    daily_dd_pct: float = 0.0
    weekly_dd_pct: float = 0.0
    last_trade_at: datetime | None = None
    last_loss_at: datetime | None = None


@dataclass(slots=True)
class GovernanceConfig:
    cooldown_minutes_after_loss: int = 60
    duplicate_level_tolerance_pct: float = 0.001
    duplicate_level_window_hours: int = 24
    max_trades_per_day: int = 3
    max_consecutive_losses: int = 3
    daily_dd_limit: float = 0.03
    weekly_dd_limit: float = 0.06
    session_start_hour_utc: int = 0
    session_end_hour_utc: int = 23
    no_trade_windows_utc: tuple[tuple[int, int], ...] = ()


class GovernanceLayer:
    def __init__(
        self,
        config: GovernanceConfig | None = None,
        state_provider: Callable[[], GovernanceRuntimeState] | None = None,
    ) -> None:
        self.config = config or GovernanceConfig()
        self.state_provider = state_provider or (lambda: GovernanceRuntimeState())
        self._accepted_levels: deque[tuple[datetime, float]] = deque(maxlen=200)

    def evaluate(self, candidate: SignalCandidate) -> GovernanceDecision:
        now = candidate.timestamp.astimezone(timezone.utc)
        state = self.state_provider()
        notes: list[str] = []

        if state.daily_dd_pct >= self.config.daily_dd_limit:
            return GovernanceDecision(False, [f"daily_dd_exceeded:{state.daily_dd_pct:.4f}"])
        if state.weekly_dd_pct >= self.config.weekly_dd_limit:
            return GovernanceDecision(False, [f"weekly_dd_exceeded:{state.weekly_dd_pct:.4f}"])
        if state.consecutive_losses >= self.config.max_consecutive_losses:
            return GovernanceDecision(False, [f"consecutive_losses_limit:{state.consecutive_losses}"])
        if state.trades_today >= self.config.max_trades_per_day:
            return GovernanceDecision(False, [f"max_trades_per_day:{state.trades_today}"])

        if not self._is_within_session(now):
            return GovernanceDecision(False, ["session_gated"])
        if self._is_in_no_trade_window(now):
            return GovernanceDecision(False, ["no_trade_window"])

        if state.last_loss_at is not None:
            delta = now - state.last_loss_at.astimezone(timezone.utc)
            cooldown = timedelta(minutes=self.config.cooldown_minutes_after_loss)
            if delta < cooldown:
                return GovernanceDecision(False, [f"cooldown_after_loss:{int((cooldown - delta).total_seconds())}s"])

        if self._is_duplicate_level(candidate.entry_reference, now):
            return GovernanceDecision(False, ["duplicate_level"])

        self._accepted_levels.append((now, candidate.entry_reference))
        notes.append("governance_pass")
        return GovernanceDecision(True, notes)

    def to_executable(self, candidate: SignalCandidate, decision: GovernanceDecision) -> ExecutableSignal:
        if not decision.approved:
            raise ValueError("Cannot create ExecutableSignal from rejected candidate.")

        rr_ratio = self._compute_rr(
            direction=candidate.direction,
            entry=candidate.entry_reference,
            stop=candidate.invalidation_level,
            take_profit=candidate.tp_reference_1,
        )

        return ExecutableSignal(
            signal_id=candidate.signal_id,
            timestamp=candidate.timestamp,
            direction=candidate.direction,
            entry_price=candidate.entry_reference,
            stop_loss=candidate.invalidation_level,
            take_profit_1=candidate.tp_reference_1,
            take_profit_2=candidate.tp_reference_2,
            rr_ratio=rr_ratio,
            approved_by_governance=True,
            governance_notes=decision.notes,
        )

    def _is_within_session(self, now: datetime) -> bool:
        hour = now.hour
        return self.config.session_start_hour_utc <= hour <= self.config.session_end_hour_utc

    def _is_in_no_trade_window(self, now: datetime) -> bool:
        hour = now.hour
        for start, end in self.config.no_trade_windows_utc:
            if start <= hour <= end:
                return True
        return False

    def _is_duplicate_level(self, entry_reference: float, now: datetime) -> bool:
        horizon = now - timedelta(hours=self.config.duplicate_level_window_hours)
        while self._accepted_levels and self._accepted_levels[0][0] < horizon:
            self._accepted_levels.popleft()

        for _, existing_level in self._accepted_levels:
            baseline = max(abs(existing_level), 1e-9)
            distance_pct = abs(entry_reference - existing_level) / baseline
            if distance_pct <= self.config.duplicate_level_tolerance_pct:
                return True
        return False

    @staticmethod
    def _compute_rr(direction: str, entry: float, stop: float, take_profit: float) -> float:
        risk = abs(entry - stop)
        if risk <= 0:
            return 0.0
        if direction == "LONG":
            reward = take_profit - entry
        else:
            reward = entry - take_profit
        return reward / risk if risk else 0.0
