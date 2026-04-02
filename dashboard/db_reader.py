from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from storage.db import connect_readonly
from storage.repositories import fetch_open_positions, get_bot_state


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return _to_utc(value)
    return _to_utc(datetime.fromisoformat(str(value)))


def _to_iso(value: Any) -> str | None:
    parsed = _parse_datetime(value)
    if parsed is None:
        return None
    return parsed.isoformat()


def _trade_outcome(pnl_abs: Any) -> str | None:
    if pnl_abs is None:
        return None
    pnl = float(pnl_abs)
    if pnl > 0:
        return "WIN"
    if pnl < 0:
        return "LOSS"
    return "BREAKEVEN"


def _is_missing_db_error(exc: sqlite3.OperationalError) -> bool:
    return "unable to open" in str(exc).lower()


def read_status_from_conn(conn: sqlite3.Connection) -> dict[str, Any]:
    raw = get_bot_state(conn)
    if raw is None:
        return {
            "bot_state": None,
            "uptime_seconds": None,
            "dashboard_version": "m1",
        }

    return {
        "bot_state": {
            "mode": str(raw["mode"]),
            "healthy": bool(raw["healthy"]),
            "safe_mode": bool(raw["safe_mode"]),
            "safe_mode_reason": raw["last_error"],
            "open_positions_count": int(raw["open_positions_count"]),
            "consecutive_losses": int(raw["consecutive_losses"]),
            "daily_dd_pct": float(raw["daily_dd_pct"]),
            "weekly_dd_pct": float(raw["weekly_dd_pct"]),
            "last_trade_at": _to_iso(raw["last_trade_at"]),
            "state_timestamp": _to_iso(raw["timestamp"]),
        },
        "uptime_seconds": None,
        "dashboard_version": "m1",
    }


def read_positions_from_conn(conn: sqlite3.Connection, *, now: datetime | None = None) -> dict[str, Any]:
    rows = fetch_open_positions(conn)
    positions = [
        {
            "position_id": str(row["position_id"]),
            "direction": str(row["direction"]),
            "entry_price": float(row["entry_price"]),
            "size": float(row["size"]),
            "stop_loss": None if row["stop_loss"] is None else float(row["stop_loss"]),
            "take_profit_1": None if row["take_profit_1"] is None else float(row["take_profit_1"]),
            "status": str(row["status"]),
            "opened_at": _to_iso(row["opened_at"]),
        }
        for row in rows
    ]

    latest_opened_at = max((_parse_datetime(row["opened_at"]) for row in rows), default=None)
    reference_now = _to_utc(now or datetime.now(timezone.utc))
    data_age_seconds = None
    if latest_opened_at is not None:
        data_age_seconds = max((reference_now - latest_opened_at).total_seconds(), 0.0)

    return {
        "positions": positions,
        "data_age_seconds": data_age_seconds,
    }


def read_trades_from_conn(conn: sqlite3.Connection, *, limit: int = 50) -> dict[str, Any]:
    rows = conn.execute(
        """
        SELECT trade_id, direction, entry_price, exit_price, pnl_abs, pnl_r, closed_at
        FROM trade_log
        WHERE closed_at IS NOT NULL
        ORDER BY closed_at DESC
        LIMIT ?
        """,
        (int(limit),),
    ).fetchall()

    return {
        "trades": [
            {
                "trade_id": str(row["trade_id"]),
                "direction": str(row["direction"]),
                "entry_price": float(row["entry_price"]),
                "exit_price": None if row["exit_price"] is None else float(row["exit_price"]),
                "pnl_abs": None if row["pnl_abs"] is None else float(row["pnl_abs"]),
                "pnl_r": None if row["pnl_r"] is None else float(row["pnl_r"]),
                "outcome": _trade_outcome(row["pnl_abs"]),
                "closed_at": _to_iso(row["closed_at"]),
            }
            for row in rows
        ]
    }


class DashboardReader:
    def __init__(
        self,
        db_path: Path,
        *,
        connect_fn: Callable[[Path], sqlite3.Connection] = connect_readonly,
    ) -> None:
        self.db_path = db_path
        self._connect_fn = connect_fn

    def read_status(self) -> dict[str, Any]:
        try:
            conn = self._connect_fn(self.db_path)
        except sqlite3.OperationalError as exc:
            if _is_missing_db_error(exc):
                return {
                    "bot_state": None,
                    "uptime_seconds": None,
                    "dashboard_version": "m3",
                }
            raise
        try:
            return read_status_from_conn(conn)
        finally:
            conn.close()

    def read_positions(self) -> dict[str, Any]:
        try:
            conn = self._connect_fn(self.db_path)
        except sqlite3.OperationalError as exc:
            if _is_missing_db_error(exc):
                return {
                    "positions": [],
                    "data_age_seconds": None,
                }
            raise
        try:
            return read_positions_from_conn(conn)
        finally:
            conn.close()

    def read_trades(self, *, limit: int = 50) -> dict[str, Any]:
        try:
            conn = self._connect_fn(self.db_path)
        except sqlite3.OperationalError as exc:
            if _is_missing_db_error(exc):
                return {"trades": []}
            raise
        try:
            return read_trades_from_conn(conn, limit=limit)
        finally:
            conn.close()
