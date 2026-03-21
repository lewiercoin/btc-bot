from __future__ import annotations

import sqlite3
from dataclasses import dataclass, replace
from datetime import date, datetime, timezone
from uuid import uuid4

from core.governance import GovernanceRuntimeState
from core.models import BotState, ExecutableSignal, Position, SignalCandidate
from core.risk_engine import RiskRuntimeState, SettlementMetrics
from storage.repositories import (
    close_position,
    fetch_open_trade_positions,
    fetch_recent_closed_trade_outcomes,
    fetch_trade_log_rows_for_day,
    get_bot_state,
    get_daily_metrics,
    get_last_closed_loss_at,
    get_latest_position_for_signal,
    get_open_trade_log_for_position,
    get_open_positions_count,
    insert_trade_log_open,
    update_trade_log_close,
    upsert_bot_state,
    upsert_daily_metrics,
)


@dataclass(slots=True)
class OpenTradeRecord:
    trade_id: str
    position: Position


class StateStore:
    def __init__(self, connection: sqlite3.Connection, mode: str) -> None:
        self.connection = connection
        self.mode = mode

    def ensure_initialized(self) -> BotState:
        existing = self.load()
        if existing is not None:
            return existing
        state = BotState(
            mode=self.mode,
            healthy=True,
            safe_mode=False,
            open_positions_count=0,
            consecutive_losses=0,
            daily_dd_pct=0.0,
            weekly_dd_pct=0.0,
            last_trade_at=None,
            last_error=None,
        )
        self.save(state)
        return state

    def save(self, state: BotState) -> None:
        upsert_bot_state(self.connection, state=state, timestamp=datetime.now(timezone.utc))
        self.connection.commit()

    def load(self) -> BotState | None:
        raw = get_bot_state(self.connection)
        if raw is None:
            return None
        return BotState(
            mode=raw["mode"],
            healthy=bool(raw["healthy"]),
            safe_mode=bool(raw["safe_mode"]),
            open_positions_count=raw["open_positions_count"],
            consecutive_losses=raw["consecutive_losses"],
            daily_dd_pct=raw["daily_dd_pct"],
            weekly_dd_pct=raw["weekly_dd_pct"],
            last_trade_at=datetime.fromisoformat(raw["last_trade_at"]) if raw["last_trade_at"] else None,
            last_error=raw["last_error"],
        )

    def get_open_positions(self) -> int:
        return get_open_positions_count(self.connection)

    def get_governance_state(self, now: datetime | None = None) -> GovernanceRuntimeState:
        ts = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        self.ensure_initialized()
        self.sync_daily_metrics(ts.date())

        state = self.load()
        assert state is not None
        metrics = get_daily_metrics(self.connection, ts.date()) or {}
        consecutive_losses = self._compute_consecutive_losses()
        last_loss_at = get_last_closed_loss_at(self.connection)

        if state.consecutive_losses != consecutive_losses:
            self.save(replace(state, consecutive_losses=consecutive_losses))

        return GovernanceRuntimeState(
            trades_today=int(metrics.get("trades_count", 0)),
            consecutive_losses=consecutive_losses,
            daily_dd_pct=state.daily_dd_pct,
            weekly_dd_pct=state.weekly_dd_pct,
            last_trade_at=state.last_trade_at,
            last_loss_at=last_loss_at,
        )

    def get_risk_state(self) -> RiskRuntimeState:
        self.ensure_initialized()
        state = self.load()
        assert state is not None
        consecutive_losses = self._compute_consecutive_losses()
        if state.consecutive_losses != consecutive_losses:
            self.save(replace(state, consecutive_losses=consecutive_losses))
            state = self.load() or state
        return RiskRuntimeState(
            consecutive_losses=consecutive_losses,
            daily_dd_pct=state.daily_dd_pct,
            weekly_dd_pct=state.weekly_dd_pct,
        )

    def sync_daily_metrics(self, day: date) -> None:
        rows = fetch_trade_log_rows_for_day(self.connection, day)
        trades_count = len(rows)

        closed_rows = [row for row in rows if row.get("closed_at")]
        wins = sum(1 for row in closed_rows if float(row.get("pnl_abs", 0.0)) > 0)
        losses = sum(1 for row in closed_rows if float(row.get("pnl_abs", 0.0)) < 0)
        pnl_abs = sum(float(row.get("pnl_abs", 0.0)) for row in closed_rows)
        pnl_r_sum = sum(float(row.get("pnl_r", 0.0)) for row in closed_rows)
        expectancy_r = pnl_r_sum / len(closed_rows) if closed_rows else 0.0

        state = self.load() or self.ensure_initialized()
        upsert_daily_metrics(
            self.connection,
            day=day,
            trades_count=trades_count,
            wins=wins,
            losses=losses,
            pnl_abs=pnl_abs,
            pnl_r_sum=pnl_r_sum,
            daily_dd_pct=state.daily_dd_pct,
            expectancy_r=expectancy_r,
        )
        self.connection.commit()

    def get_open_trade_records(self) -> list[OpenTradeRecord]:
        rows = fetch_open_trade_positions(self.connection)
        records: list[OpenTradeRecord] = []
        for row in rows:
            position = Position(
                position_id=row["position_id"],
                symbol=row["symbol"],
                direction=row["direction"],
                status=row["status"],
                entry_price=float(row["entry_price"]),
                size=float(row["size"]),
                leverage=int(row["leverage"]),
                stop_loss=float(row["stop_loss"]),
                take_profit_1=float(row["take_profit_1"]),
                take_profit_2=float(row["take_profit_2"]),
                opened_at=datetime.fromisoformat(row["opened_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
                signal_id=row["signal_id"],
            )
            records.append(OpenTradeRecord(trade_id=row["trade_id"], position=position))
        return records

    def record_trade_open(
        self,
        *,
        candidate: SignalCandidate,
        executable: ExecutableSignal,
        schema_version: str,
        config_hash: str,
    ) -> None:
        position = get_latest_position_for_signal(self.connection, executable.signal_id)
        if not position:
            raise RuntimeError(f"No position found for signal_id={executable.signal_id}")

        opened_at = datetime.fromisoformat(position["opened_at"])
        insert_trade_log_open(
            self.connection,
            trade_id=f"trd-{uuid4().hex}",
            signal_id=executable.signal_id,
            position_id=position["position_id"],
            opened_at=opened_at,
            direction=executable.direction,
            regime=candidate.regime.value,
            confluence_score=candidate.confluence_score,
            entry_price=float(position["entry_price"]),
            size=float(position["size"]),
            features_at_entry_json=candidate.features_json,
            schema_version=schema_version,
            config_hash=config_hash,
        )

        state = self.load() or self.ensure_initialized()
        updated_state = replace(
            state,
            healthy=True,
            last_error=None,
            open_positions_count=self.get_open_positions(),
            last_trade_at=opened_at,
            consecutive_losses=self._compute_consecutive_losses(),
        )
        self.save(updated_state)
        self.sync_daily_metrics(opened_at.astimezone(timezone.utc).date())

    def settle_trade_close(
        self,
        *,
        position_id: str,
        settlement: SettlementMetrics,
        closed_at: datetime,
    ) -> None:
        open_trade = get_open_trade_log_for_position(self.connection, position_id)
        if not open_trade:
            raise RuntimeError(f"No open trade_log row for position_id={position_id}")

        close_position(self.connection, position_id=position_id, closed_at=closed_at)
        update_trade_log_close(
            self.connection,
            trade_id=open_trade["trade_id"],
            closed_at=closed_at,
            exit_price=settlement.exit_price,
            pnl_abs=settlement.pnl_abs,
            pnl_r=settlement.pnl_r,
            mae=settlement.mae,
            mfe=settlement.mfe,
            exit_reason=settlement.exit_reason,
        )

        opened_at = datetime.fromisoformat(open_trade["opened_at"])
        self.sync_daily_metrics(opened_at.astimezone(timezone.utc).date())
        self.sync_daily_metrics(closed_at.astimezone(timezone.utc).date())

        state = self.load() or self.ensure_initialized()
        updated_state = replace(
            state,
            healthy=True,
            last_error=None,
            open_positions_count=self.get_open_positions(),
            consecutive_losses=self._compute_consecutive_losses(),
        )
        self.save(updated_state)

    def mark_error(self, message: str) -> None:
        state = self.load() or self.ensure_initialized()
        self.save(replace(state, healthy=False, last_error=message))

    def mark_healthy(self) -> None:
        state = self.load() or self.ensure_initialized()
        self.save(replace(state, healthy=True, last_error=None, open_positions_count=self.get_open_positions()))

    def _compute_consecutive_losses(self) -> int:
        outcomes = fetch_recent_closed_trade_outcomes(self.connection, limit=100)
        losses = 0
        for row in outcomes:
            pnl_abs = float(row["pnl_abs"])
            if pnl_abs < 0:
                losses += 1
                continue
            if pnl_abs > 0:
                break
        return losses
