from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

from core.models import BotState, ExecutableSignal, GovernanceRuntimeState, Position, RiskRuntimeState, SettlementMetrics, SignalCandidate
from storage.repositories import (
    close_position,
    fetch_closed_trade_pnl_series_between,
    fetch_open_positions,
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
    sum_closed_pnl_abs_before,
    update_trade_log_close,
    upsert_bot_state,
    upsert_daily_metrics,
)

LOG = logging.getLogger(__name__)


@dataclass(slots=True)
class OpenTradeRecord:
    trade_id: str
    position: Position


class StateStore:
    def __init__(self, connection: sqlite3.Connection, mode: str, reference_equity: float = 10_000.0) -> None:
        self.connection = connection
        self.mode = mode
        self.reference_equity = max(reference_equity, 1e-8)
        self._migrations_applied: bool = False

    def _apply_migrations(self) -> None:
        """Apply schema migrations idempotently. Runs once per StateStore instance."""
        if self._migrations_applied:
            return

        cursor = self.connection.cursor()

        cursor.execute("PRAGMA table_info(bot_state)")
        columns = {row[1] for row in cursor.fetchall()}

        if "safe_mode_entry_at" not in columns:
            cursor.execute("ALTER TABLE bot_state ADD COLUMN safe_mode_entry_at TEXT DEFAULT NULL")
            self.connection.commit()
            LOG.info("Migration applied: added safe_mode_entry_at column to bot_state")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS safe_mode_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                trigger TEXT,
                reason TEXT,
                probe_successes INTEGER DEFAULT 0,
                probe_failures INTEGER DEFAULT 0,
                remaining_triggers TEXT,
                timestamp TEXT NOT NULL
            )
        """)
        self.connection.commit()

        self._migrations_applied = True

    def ensure_initialized(self) -> BotState:
        self._apply_migrations()
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
        raw_entry_at = raw.get("safe_mode_entry_at")
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
            safe_mode_entry_at=datetime.fromisoformat(raw_entry_at) if raw_entry_at else None,
        )

    def get_open_positions(self) -> int:
        return get_open_positions_count(self.connection)

    def get_open_positions_snapshot(self) -> list[Position]:
        rows = fetch_open_positions(self.connection)
        positions: list[Position] = []
        for row in rows:
            positions.append(
                Position(
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
            )
        return positions

    def set_safe_mode(self, enabled: bool, reason: str | None = None, now: datetime | None = None) -> BotState:
        ts = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        state = self.refresh_runtime_state(ts)
        assert state is not None

        if enabled and not state.safe_mode:
            new_entry_at: datetime | None = ts
        elif enabled and state.safe_mode:
            new_entry_at = state.safe_mode_entry_at
        else:
            new_entry_at = None

        updated = replace(
            state,
            healthy=False if enabled else True,
            safe_mode=enabled,
            open_positions_count=self.get_open_positions(),
            last_error=reason if enabled else None,
            safe_mode_entry_at=new_entry_at,
        )
        self.save(updated)

        trigger = (reason or "").split(":")[0].strip() if reason else None
        event_type = "entered" if enabled else "cleared"
        try:
            self.connection.execute(
                """
                INSERT INTO safe_mode_events (event_type, trigger, reason, timestamp)
                VALUES (?, ?, ?, ?)
                """,
                (event_type, trigger, reason, ts.isoformat()),
            )
            self.connection.commit()
        except Exception as evt_exc:
            LOG.warning("Failed to write safe_mode event to audit table: %s", evt_exc)

        return updated

    def get_governance_state(self, now: datetime | None = None) -> GovernanceRuntimeState:
        ts = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        state = self.refresh_runtime_state(ts)
        assert state is not None
        metrics = get_daily_metrics(self.connection, ts.date()) or {}
        last_loss_at = get_last_closed_loss_at(self.connection)

        return GovernanceRuntimeState(
            trades_today=int(metrics.get("trades_count", 0)),
            consecutive_losses=state.consecutive_losses,
            daily_dd_pct=state.daily_dd_pct,
            weekly_dd_pct=state.weekly_dd_pct,
            last_trade_at=state.last_trade_at,
            last_loss_at=last_loss_at,
        )

    def get_risk_state(self) -> RiskRuntimeState:
        state = self.refresh_runtime_state()
        assert state is not None
        return RiskRuntimeState(
            consecutive_losses=state.consecutive_losses,
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

        state = self.refresh_runtime_state(opened_at)
        assert state is not None
        updated_state = replace(
            state,
            healthy=True,
            last_error=None,
            open_positions_count=self.get_open_positions(),
            last_trade_at=opened_at,
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

        state = self.refresh_runtime_state(closed_at)
        assert state is not None
        updated_state = replace(
            state,
            healthy=True,
            last_error=None,
            open_positions_count=self.get_open_positions(),
        )
        self.save(updated_state)

    def mark_error(self, message: str) -> None:
        state = self.refresh_runtime_state()
        assert state is not None
        self.save(replace(state, healthy=False, last_error=message))

    def mark_healthy(self) -> None:
        state = self.refresh_runtime_state()
        assert state is not None
        self.save(replace(state, healthy=True, last_error=None, open_positions_count=self.get_open_positions()))

    def refresh_runtime_state(self, now: datetime | None = None) -> BotState:
        ts = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        self.ensure_initialized()
        self.sync_daily_metrics(ts.date())

        current = self.load()
        assert current is not None
        consecutive_losses = self._compute_consecutive_losses(ts)
        daily_dd_pct = self._compute_daily_dd_pct(ts)
        weekly_dd_pct = self._compute_weekly_dd_pct(ts)

        refreshed = replace(
            current,
            open_positions_count=self.get_open_positions(),
            consecutive_losses=consecutive_losses,
            daily_dd_pct=daily_dd_pct,
            weekly_dd_pct=weekly_dd_pct,
        )
        self.save(refreshed)
        self.sync_daily_metrics(ts.date())
        return refreshed

    def _compute_consecutive_losses(self, now: datetime) -> int:
        outcomes = fetch_recent_closed_trade_outcomes(self.connection, limit=100)
        now_date = _to_utc(now).date()
        losses = 0
        for row in outcomes:
            closed_at_raw = row.get("closed_at")
            if not closed_at_raw:
                continue
            closed_at = closed_at_raw if isinstance(closed_at_raw, datetime) else datetime.fromisoformat(str(closed_at_raw))
            if _to_utc(closed_at).date() != now_date:
                break
            pnl_abs = float(row["pnl_abs"])
            if pnl_abs < 0:
                losses += 1
                continue
            if pnl_abs > 0:
                break
        return losses

    def _compute_daily_dd_pct(self, now: datetime) -> float:
        day_start = datetime.combine(now.date(), datetime.min.time(), tzinfo=timezone.utc)
        day_end = day_start + timedelta(days=1)
        return self._compute_period_drawdown_pct(day_start, day_end)

    def _compute_weekly_dd_pct(self, now: datetime) -> float:
        weekday = now.weekday()  # Monday=0
        week_start_date = now.date() - timedelta(days=weekday)
        week_start = datetime.combine(week_start_date, datetime.min.time(), tzinfo=timezone.utc)
        week_end = week_start + timedelta(days=7)
        return self._compute_period_drawdown_pct(week_start, week_end)

    def _compute_period_drawdown_pct(self, start_ts: datetime, end_ts: datetime) -> float:
        closed_before = sum_closed_pnl_abs_before(self.connection, start_ts)
        starting_equity = max(self.reference_equity + closed_before, 1e-8)

        peak_equity = starting_equity
        current_equity = starting_equity
        max_drawdown = 0.0

        for row in fetch_closed_trade_pnl_series_between(self.connection, start_ts, end_ts):
            current_equity += float(row["pnl_abs"])
            if current_equity > peak_equity:
                peak_equity = current_equity
            drawdown = (peak_equity - current_equity) / max(peak_equity, 1e-8)
            if drawdown > max_drawdown:
                max_drawdown = drawdown

        return min(max(max_drawdown, 0.0), 1.0)


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
