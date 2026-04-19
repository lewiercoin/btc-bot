from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timezone
from typing import Any

from core.execution_types import FillEvent
from core.models import BotState, ExecutableSignal, SignalCandidate


def save_signal_candidate(conn: sqlite3.Connection, candidate: SignalCandidate, schema_version: str, config_hash: str) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO signal_candidates (
            signal_id, timestamp, direction, setup_type, confluence_score, regime,
            reasons_json, features_json, schema_version, config_hash
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            candidate.signal_id,
            candidate.timestamp.isoformat(),
            candidate.direction,
            candidate.setup_type,
            candidate.confluence_score,
            candidate.regime.value,
            json.dumps(candidate.reasons),
            json.dumps(candidate.features_json),
            schema_version,
            config_hash,
        ),
    )


def save_executable_signal(conn: sqlite3.Connection, signal: ExecutableSignal) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO executable_signals (
            signal_id, timestamp, direction, entry_price, stop_loss, take_profit_1,
            take_profit_2, rr_ratio, governance_notes_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            signal.signal_id,
            signal.timestamp.isoformat(),
            signal.direction,
            signal.entry_price,
            signal.stop_loss,
            signal.take_profit_1,
            signal.take_profit_2,
            signal.rr_ratio,
            json.dumps(signal.governance_notes),
        ),
    )


def upsert_bot_state(conn: sqlite3.Connection, state: BotState, timestamp: datetime | None = None) -> None:
    ts = (timestamp or datetime.now(timezone.utc)).isoformat()
    conn.execute(
        """
        INSERT INTO bot_state (
            id, timestamp, mode, healthy, safe_mode, open_positions_count, consecutive_losses,
            daily_dd_pct, weekly_dd_pct, last_trade_at, last_error, safe_mode_entry_at
        ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            timestamp = excluded.timestamp,
            mode = excluded.mode,
            healthy = excluded.healthy,
            safe_mode = excluded.safe_mode,
            open_positions_count = excluded.open_positions_count,
            consecutive_losses = excluded.consecutive_losses,
            daily_dd_pct = excluded.daily_dd_pct,
            weekly_dd_pct = excluded.weekly_dd_pct,
            last_trade_at = excluded.last_trade_at,
            last_error = excluded.last_error,
            safe_mode_entry_at = excluded.safe_mode_entry_at
        """,
        (
            ts,
            state.mode,
            1 if state.healthy else 0,
            1 if state.safe_mode else 0,
            state.open_positions_count,
            state.consecutive_losses,
            state.daily_dd_pct,
            state.weekly_dd_pct,
            state.last_trade_at.isoformat() if state.last_trade_at else None,
            state.last_error,
            state.safe_mode_entry_at.isoformat() if state.safe_mode_entry_at else None,
        ),
    )


def get_bot_state(conn: sqlite3.Connection) -> dict | None:
    row = conn.execute("SELECT * FROM bot_state WHERE id = 1").fetchone()
    if not row:
        return None
    return dict(row)


_RUNTIME_METRICS_FIELDS = (
    "last_decision_cycle_started_at",
    "last_decision_cycle_finished_at",
    "last_decision_outcome",
    "decision_cycle_status",
    "last_snapshot_built_at",
    "last_snapshot_symbol",
    "last_15m_candle_open_at",
    "last_1h_candle_open_at",
    "last_4h_candle_open_at",
    "last_ws_message_at",
    "last_health_check_at",
    "last_runtime_warning",
    "config_hash",
)


def upsert_runtime_metrics(conn: sqlite3.Connection, **fields: Any) -> None:
    unknown_fields = set(fields) - set(_RUNTIME_METRICS_FIELDS)
    if unknown_fields:
        raise ValueError(f"Unsupported runtime_metrics fields: {sorted(unknown_fields)}")

    if not fields:
        return

    field_names = ["updated_at", *fields.keys()]
    placeholders = ", ".join("?" for _ in field_names)
    updates = ", ".join(f"{field} = excluded.{field}" for field in field_names)
    values = [_normalize_runtime_metric_value(datetime.now(timezone.utc)), *(_normalize_runtime_metric_value(value) for value in fields.values())]

    conn.execute(
        f"""
        INSERT INTO runtime_metrics (id, {", ".join(field_names)})
        VALUES (1, {placeholders})
        ON CONFLICT(id) DO UPDATE SET
            {updates}
        """,
        tuple(values),
    )


def get_runtime_metrics(conn: sqlite3.Connection) -> dict | None:
    row = conn.execute("SELECT * FROM runtime_metrics WHERE id = 1").fetchone()
    if not row:
        return None
    return dict(row)


def insert_decision_outcome(
    conn: sqlite3.Connection,
    *,
    cycle_timestamp: datetime,
    outcome_group: str,
    outcome_reason: str,
    config_hash: str,
    regime: str | None = None,
    signal_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO decision_outcomes (
            cycle_timestamp, outcome_group, outcome_reason, regime, config_hash, signal_id, details_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            _normalize_runtime_metric_value(cycle_timestamp),
            outcome_group,
            outcome_reason,
            regime,
            config_hash,
            signal_id,
            json.dumps(details or {}, sort_keys=True),
        ),
    )


def fetch_decision_outcome_counts(
    conn: sqlite3.Connection,
    *,
    since_ts: datetime,
    config_hash: str | None = None,
) -> dict[str, dict[str, int]]:
    where_clause = "WHERE cycle_timestamp >= ?"
    params: list[Any] = [_normalize_runtime_metric_value(since_ts)]
    if config_hash:
        where_clause += " AND config_hash = ?"
        params.append(config_hash)

    grouped = conn.execute(
        f"""
        SELECT outcome_group, outcome_reason, COUNT(*) AS count
        FROM decision_outcomes
        {where_clause}
        GROUP BY outcome_group, outcome_reason
        """,
        tuple(params),
    ).fetchall()

    by_outcome: dict[str, int] = {}
    by_reason: dict[str, int] = {}
    for row in grouped:
        outcome_group = str(row["outcome_group"])
        outcome_reason = str(row["outcome_reason"])
        count = int(row["count"])
        by_outcome[outcome_group] = by_outcome.get(outcome_group, 0) + count
        by_reason[outcome_reason] = by_reason.get(outcome_reason, 0) + count

    return {
        "by_outcome": by_outcome,
        "by_reason": by_reason,
    }


def upsert_config_snapshot(
    conn: sqlite3.Connection,
    *,
    config_hash: str,
    captured_at: datetime,
    strategy_snapshot: dict[str, Any],
) -> None:
    conn.execute(
        """
        INSERT INTO config_snapshots (config_hash, captured_at, strategy_json)
        VALUES (?, ?, ?)
        ON CONFLICT(config_hash) DO UPDATE SET
            strategy_json = excluded.strategy_json
        """,
        (
            config_hash,
            _normalize_runtime_metric_value(captured_at),
            json.dumps(strategy_snapshot, sort_keys=True),
        ),
    )


def get_config_snapshot(conn: sqlite3.Connection, config_hash: str) -> dict | None:
    row = conn.execute(
        """
        SELECT config_hash, captured_at, strategy_json
        FROM config_snapshots
        WHERE config_hash = ?
        """,
        (config_hash,),
    ).fetchone()
    if not row:
        return None
    return dict(row)


def get_open_positions_count(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS cnt FROM positions WHERE status IN ('OPEN', 'PARTIAL')"
    ).fetchone()
    return int(row["cnt"]) if row else 0


def fetch_open_positions(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """
        SELECT
            position_id,
            signal_id,
            symbol,
            direction,
            status,
            entry_price,
            size,
            leverage,
            stop_loss,
            take_profit_1,
            take_profit_2,
            opened_at,
            updated_at
        FROM positions
        WHERE status IN ('OPEN', 'PARTIAL')
        ORDER BY opened_at ASC
        """
    ).fetchall()
    return [dict(row) for row in rows]


def get_latest_position_for_signal(conn: sqlite3.Connection, signal_id: str) -> dict | None:
    row = conn.execute(
        """
        SELECT position_id, opened_at, symbol, direction, entry_price, size
        FROM positions
        WHERE signal_id = ?
        ORDER BY opened_at DESC
        LIMIT 1
        """,
        (signal_id,),
    ).fetchone()
    return dict(row) if row else None


def insert_position(
    conn: sqlite3.Connection,
    *,
    position_id: str,
    signal_id: str,
    symbol: str,
    direction: str,
    status: str,
    entry_price: float,
    size: float,
    leverage: int,
    stop_loss: float,
    take_profit_1: float,
    take_profit_2: float,
    opened_at: datetime,
    updated_at: datetime,
) -> None:
    conn.execute(
        """
        INSERT INTO positions (
            position_id, signal_id, symbol, direction, status, entry_price, size, leverage,
            stop_loss, take_profit_1, take_profit_2, opened_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            position_id,
            signal_id,
            symbol,
            direction,
            status,
            entry_price,
            size,
            leverage,
            stop_loss,
            take_profit_1,
            take_profit_2,
            opened_at.isoformat(),
            updated_at.isoformat(),
        ),
    )


def insert_execution_fill_event(
    conn: sqlite3.Connection,
    *,
    position_id: str,
    order_type: str,
    fill_event: FillEvent,
) -> None:
    conn.execute(
        """
        INSERT INTO executions (
            execution_id, position_id, order_type, side, requested_price, filled_price,
            qty, fees, slippage_bps, executed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            fill_event.execution_id,
            position_id,
            order_type,
            fill_event.side,
            fill_event.requested_price,
            fill_event.filled_price,
            fill_event.qty,
            fill_event.fees,
            fill_event.slippage_bps,
            fill_event.executed_at.isoformat(),
        ),
    )


def fetch_open_trade_positions(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """
        SELECT
            p.position_id,
            p.signal_id,
            p.symbol,
            p.direction,
            p.status,
            p.entry_price,
            p.size,
            p.leverage,
            p.stop_loss,
            p.take_profit_1,
            p.take_profit_2,
            p.opened_at,
            p.updated_at,
            t.trade_id
        FROM positions p
        JOIN trade_log t ON t.position_id = p.position_id
        WHERE p.status IN ('OPEN', 'PARTIAL')
          AND t.closed_at IS NULL
        ORDER BY p.opened_at ASC
        """
    ).fetchall()
    return [dict(row) for row in rows]


def insert_trade_log_open(
    conn: sqlite3.Connection,
    *,
    trade_id: str,
    signal_id: str,
    position_id: str,
    opened_at: datetime,
    direction: str,
    regime: str,
    confluence_score: float,
    entry_price: float,
    size: float,
    features_at_entry_json: dict[str, Any],
    schema_version: str,
    config_hash: str,
) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO trade_log (
            trade_id, signal_id, position_id, opened_at, closed_at, direction, regime,
            confluence_score, entry_price, exit_price, size, fees_total, slippage_bps_avg,
            pnl_abs, pnl_r, mae, mfe, exit_reason, features_at_entry_json, schema_version, config_hash
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            trade_id,
            signal_id,
            position_id,
            opened_at.isoformat(),
            None,
            direction,
            regime,
            confluence_score,
            entry_price,
            None,
            size,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            None,
            json.dumps(features_at_entry_json),
            schema_version,
            config_hash,
        ),
    )


def close_position(conn: sqlite3.Connection, *, position_id: str, closed_at: datetime) -> None:
    conn.execute(
        """
        UPDATE positions
        SET status = 'CLOSED',
            updated_at = ?
        WHERE position_id = ?
        """,
        (closed_at.isoformat(), position_id),
    )


def update_trade_log_close(
    conn: sqlite3.Connection,
    *,
    trade_id: str,
    closed_at: datetime,
    exit_price: float,
    pnl_abs: float,
    pnl_r: float,
    mae: float,
    mfe: float,
    exit_reason: str,
) -> None:
    conn.execute(
        """
        UPDATE trade_log
        SET closed_at = ?,
            exit_price = ?,
            pnl_abs = ?,
            pnl_r = ?,
            mae = ?,
            mfe = ?,
            exit_reason = ?
        WHERE trade_id = ?
          AND closed_at IS NULL
        """,
        (
            closed_at.isoformat(),
            exit_price,
            pnl_abs,
            pnl_r,
            mae,
            mfe,
            exit_reason,
            trade_id,
        ),
    )


def get_daily_metrics(conn: sqlite3.Connection, day: date) -> dict | None:
    row = conn.execute("SELECT * FROM daily_metrics WHERE date = ?", (day.isoformat(),)).fetchone()
    return dict(row) if row else None


def upsert_daily_metrics(
    conn: sqlite3.Connection,
    *,
    day: date,
    trades_count: int,
    wins: int,
    losses: int,
    pnl_abs: float,
    pnl_r_sum: float,
    daily_dd_pct: float,
    expectancy_r: float,
) -> None:
    conn.execute(
        """
        INSERT INTO daily_metrics (
            date, trades_count, wins, losses, pnl_abs, pnl_r_sum, daily_dd_pct, expectancy_r
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(date) DO UPDATE SET
            trades_count = excluded.trades_count,
            wins = excluded.wins,
            losses = excluded.losses,
            pnl_abs = excluded.pnl_abs,
            pnl_r_sum = excluded.pnl_r_sum,
            daily_dd_pct = excluded.daily_dd_pct,
            expectancy_r = excluded.expectancy_r
        """,
        (
            day.isoformat(),
            trades_count,
            wins,
            losses,
            pnl_abs,
            pnl_r_sum,
            daily_dd_pct,
            expectancy_r,
        ),
    )


def fetch_trade_log_rows_for_day(conn: sqlite3.Connection, day: date) -> list[dict]:
    rows = conn.execute(
        """
        SELECT *
        FROM trade_log
        WHERE DATE(opened_at) = ?
        ORDER BY opened_at ASC
        """,
        (day.isoformat(),),
    ).fetchall()
    return [dict(row) for row in rows]


def fetch_recent_closed_trade_outcomes(conn: sqlite3.Connection, limit: int = 100) -> list[dict]:
    rows = conn.execute(
        """
        SELECT closed_at, pnl_abs
        FROM trade_log
        WHERE closed_at IS NOT NULL
        ORDER BY closed_at DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [dict(row) for row in rows]


def sum_closed_pnl_abs_between(conn: sqlite3.Connection, start_ts: datetime, end_ts: datetime) -> float:
    row = conn.execute(
        """
        SELECT COALESCE(SUM(pnl_abs), 0.0) AS pnl_abs_sum
        FROM trade_log
        WHERE closed_at IS NOT NULL
          AND closed_at >= ?
          AND closed_at < ?
        """,
        (start_ts.isoformat(), end_ts.isoformat()),
    ).fetchone()
    if not row:
        return 0.0
    return float(row["pnl_abs_sum"] or 0.0)


def sum_closed_pnl_abs_before(conn: sqlite3.Connection, before_ts: datetime) -> float:
    row = conn.execute(
        """
        SELECT COALESCE(SUM(pnl_abs), 0.0) AS pnl_abs_sum
        FROM trade_log
        WHERE closed_at IS NOT NULL
          AND closed_at < ?
        """,
        (before_ts.isoformat(),),
    ).fetchone()
    if not row:
        return 0.0
    return float(row["pnl_abs_sum"] or 0.0)


def fetch_closed_trade_pnl_series_between(
    conn: sqlite3.Connection,
    start_ts: datetime,
    end_ts: datetime,
) -> list[dict]:
    rows = conn.execute(
        """
        SELECT closed_at, pnl_abs
        FROM trade_log
        WHERE closed_at IS NOT NULL
          AND closed_at >= ?
          AND closed_at < ?
        ORDER BY closed_at ASC
        """,
        (start_ts.isoformat(), end_ts.isoformat()),
    ).fetchall()
    return [dict(row) for row in rows]


def get_open_trade_log_for_position(conn: sqlite3.Connection, position_id: str) -> dict | None:
    row = conn.execute(
        """
        SELECT *
        FROM trade_log
        WHERE position_id = ?
          AND closed_at IS NULL
        ORDER BY opened_at DESC
        LIMIT 1
        """,
        (position_id,),
    ).fetchone()
    return dict(row) if row else None


def get_last_closed_loss_at(conn: sqlite3.Connection) -> datetime | None:
    row = conn.execute(
        """
        SELECT closed_at
        FROM trade_log
        WHERE closed_at IS NOT NULL AND pnl_abs < 0
        ORDER BY closed_at DESC
        LIMIT 1
        """
    ).fetchone()
    if not row or not row["closed_at"]:
        return None
    return datetime.fromisoformat(row["closed_at"])


def _normalize_runtime_metric_value(value: Any) -> Any:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc).isoformat()
        return value.astimezone(timezone.utc).isoformat()
    return value
