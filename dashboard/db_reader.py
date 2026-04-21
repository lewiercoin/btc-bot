from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from storage.db import connect_readonly
from storage.repositories import (
    fetch_decision_outcome_counts,
    fetch_open_positions,
    get_bot_state,
    get_config_snapshot,
    get_runtime_metrics,
)


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


def _parse_json_list(value: Any) -> list:
    if value is None:
        return []
    try:
        result = json.loads(value)
        return result if isinstance(result, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def _parse_json_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    try:
        result = json.loads(value)
        return result if isinstance(result, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def _age_seconds(value: Any, *, now: datetime) -> float | None:
    parsed = _parse_datetime(value)
    if parsed is None:
        return None
    return max((now - parsed).total_seconds(), 0.0)


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return bool(row)


def _runtime_freshness_unavailable() -> dict[str, Any]:
    return {
        "runtime_available": False,
        "updated_at": None,
        "config_hash": None,
        "last_health_check_at": None,
        "last_runtime_warning": None,
        "decision_cycle": {
            "status": "unavailable",
            "last_started_at": None,
            "last_finished_at": None,
            "last_outcome": None,
            "last_snapshot_age_seconds": None,
        },
        "rest_snapshot": {
            "built_at": None,
            "symbol": None,
            "timeframes": {
                "15m": {"last_candle_open_at": None, "age_seconds": None},
                "1h": {"last_candle_open_at": None, "age_seconds": None},
                "4h": {"last_candle_open_at": None, "age_seconds": None},
            },
        },
        "websocket": {
            "last_message_at": None,
            "message_age_seconds": None,
            "healthy": None,
        },
        "collector": None,
    }


def _get_current_config_hash(conn: sqlite3.Connection) -> str | None:
    """Read the current config_hash from the most recent trade_log entry (or signal_candidates as fallback)."""
    # Try to get from most recent trade first
    row = conn.execute(
        "SELECT config_hash FROM trade_log WHERE config_hash IS NOT NULL ORDER BY closed_at DESC LIMIT 1"
    ).fetchone()
    if row:
        return row["config_hash"]
    
    # Fallback to most recent signal
    row = conn.execute(
        "SELECT config_hash FROM signal_candidates WHERE config_hash IS NOT NULL ORDER BY timestamp DESC LIMIT 1"
    ).fetchone()
    return row["config_hash"] if row else None


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
            "signal_entry_reference": (
                None if row.get("signal_entry_reference") is None else float(row["signal_entry_reference"])
            ),
            "has_execution_record": bool(row.get("has_execution_record", 0)),
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


def read_trades_from_conn(conn: sqlite3.Connection, *, limit: int = 50, config_hash: str | None = None) -> dict[str, Any]:
    current_config = config_hash or _get_current_config_hash(conn)
    query = """
        SELECT
            t.trade_id,
            t.direction,
            t.entry_price,
            t.exit_price,
            t.pnl_abs,
            t.pnl_r,
            t.closed_at,
            t.regime,
            t.confluence_score,
            t.exit_reason,
            t.fees_total,
            t.mae,
            t.mfe,
            t.config_hash,
            es.entry_price AS signal_entry_reference,
            EXISTS (
                SELECT 1 FROM executions e WHERE e.position_id = t.position_id
            ) AS has_execution_record
        FROM trade_log t
        LEFT JOIN executable_signals es ON es.signal_id = t.signal_id
        WHERE t.closed_at IS NOT NULL
    """
    params = []
    if current_config:
        query += " AND t.config_hash = ?"
        params.append(current_config)
    query += " ORDER BY t.closed_at DESC LIMIT ?"
    params.append(int(limit))
    rows = conn.execute(query, tuple(params)).fetchall()

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
                "regime": str(row["regime"]) if row["regime"] else None,
                "confluence_score": None if row["confluence_score"] is None else float(row["confluence_score"]),
                "exit_reason": str(row["exit_reason"]) if row["exit_reason"] else None,
                "fees_total": float(row["fees_total"]) if row["fees_total"] is not None else 0.0,
                "mae": float(row["mae"]) if row["mae"] is not None else 0.0,
                "mfe": float(row["mfe"]) if row["mfe"] is not None else 0.0,
                "config_hash": str(row["config_hash"]) if "config_hash" in row.keys() else None,
                "signal_entry_reference": (
                    None if row["signal_entry_reference"] is None else float(row["signal_entry_reference"])
                ),
                "has_execution_record": bool(row["has_execution_record"]),
            }
            for row in rows
        ]
    }


def read_signals_from_conn(conn: sqlite3.Connection, *, limit: int = 20, config_hash: str | None = None) -> dict[str, Any]:
    current_config = config_hash or _get_current_config_hash(conn)
    query = """
        SELECT
            sc.signal_id,
            sc.timestamp,
            sc.direction,
            sc.setup_type,
            sc.confluence_score,
            sc.regime,
            sc.reasons_json,
            sc.config_hash,
            es.entry_price,
            es.stop_loss,
            es.take_profit_1,
            es.rr_ratio,
            es.governance_notes_json
        FROM signal_candidates sc
        LEFT JOIN executable_signals es ON sc.signal_id = es.signal_id
    """
    params = []
    if current_config:
        query += " WHERE sc.config_hash = ?"
        params.append(current_config)
    query += " ORDER BY sc.timestamp DESC LIMIT ?"
    params.append(int(limit))
    rows = conn.execute(query, tuple(params)).fetchall()

    return {
        "signals": [
            {
                "signal_id": str(row["signal_id"]),
                "timestamp": _to_iso(row["timestamp"]),
                "direction": str(row["direction"]),
                "setup_type": str(row["setup_type"]),
                "confluence_score": float(row["confluence_score"]),
                "regime": str(row["regime"]),
                "reasons": _parse_json_list(row["reasons_json"]),
                "config_hash": str(row["config_hash"]),
                "entry_price": None if row["entry_price"] is None else float(row["entry_price"]),
                "signal_entry_reference": None if row["entry_price"] is None else float(row["entry_price"]),
                "stop_loss": None if row["stop_loss"] is None else float(row["stop_loss"]),
                "take_profit_1": None if row["take_profit_1"] is None else float(row["take_profit_1"]),
                "rr_ratio": None if row["rr_ratio"] is None else float(row["rr_ratio"]),
                "governance_notes": _parse_json_list(row["governance_notes_json"]),
                "promoted": row["entry_price"] is not None,
            }
            for row in rows
        ]
    }


def read_daily_metrics_from_conn(conn: sqlite3.Connection, *, days: int = 14) -> dict[str, Any]:
    # Filter to last 7 days for paper trading dashboard (metrics table has no config_hash)
    cutoff_date = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
    rows = conn.execute(
        """
        SELECT date, trades_count, wins, losses, pnl_abs, pnl_r_sum, daily_dd_pct, expectancy_r
        FROM daily_metrics
        WHERE date >= ?
        ORDER BY date DESC
        LIMIT ?
        """,
        (cutoff_date, int(days)),
    ).fetchall()

    return {
        "metrics": [
            {
                "date": str(row["date"]),
                "trades_count": int(row["trades_count"]),
                "wins": int(row["wins"]),
                "losses": int(row["losses"]),
                "pnl_abs": float(row["pnl_abs"]),
                "pnl_r_sum": float(row["pnl_r_sum"]),
                "daily_dd_pct": float(row["daily_dd_pct"]),
                "expectancy_r": float(row["expectancy_r"]),
            }
            for row in rows
        ]
    }


def read_alerts_from_conn(conn: sqlite3.Connection, *, limit: int = 20) -> dict[str, Any]:
    # Filter to last 24 hours for paper trading dashboard (alerts table has no config_hash)
    cutoff_timestamp = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    rows = conn.execute(
        """
        SELECT id, timestamp, type, severity, component, message
        FROM alerts_errors
        WHERE timestamp >= ?
        ORDER BY timestamp DESC
        LIMIT ?
        """,
        (cutoff_timestamp, int(limit)),
    ).fetchall()

    return {
        "alerts": [
            {
                "id": int(row["id"]),
                "timestamp": _to_iso(row["timestamp"]),
                "type": str(row["type"]),
                "severity": str(row["severity"]),
                "component": str(row["component"]),
                "message": str(row["message"]),
            }
            for row in rows
        ]
    }


def read_runtime_freshness_from_conn(
    conn: sqlite3.Connection,
    *,
    heartbeat_seconds: int = 30,
    now: datetime | None = None,
) -> dict[str, Any]:
    if not _table_exists(conn, "runtime_metrics"):
        return _runtime_freshness_unavailable()

    row = get_runtime_metrics(conn)
    if row is None:
        return _runtime_freshness_unavailable()

    reference_now = _to_utc(now or datetime.now(timezone.utc))
    ws_age_seconds = _age_seconds(row.get("last_ws_message_at"), now=reference_now)
    max_delay = max(int(heartbeat_seconds) * 3, 5)
    websocket_healthy = None if ws_age_seconds is None else ws_age_seconds <= max_delay

    return {
        "runtime_available": True,
        "updated_at": _to_iso(row.get("updated_at")),
        "config_hash": row.get("config_hash"),
        "last_health_check_at": _to_iso(row.get("last_health_check_at")),
        "last_runtime_warning": row.get("last_runtime_warning"),
        "decision_cycle": {
            "status": row.get("decision_cycle_status") or "idle",
            "last_started_at": _to_iso(row.get("last_decision_cycle_started_at")),
            "last_finished_at": _to_iso(row.get("last_decision_cycle_finished_at")),
            "last_outcome": row.get("last_decision_outcome"),
            "last_snapshot_age_seconds": _age_seconds(row.get("last_snapshot_built_at"), now=reference_now),
        },
        "rest_snapshot": {
            "built_at": _to_iso(row.get("last_snapshot_built_at")),
            "symbol": row.get("last_snapshot_symbol"),
            "timeframes": {
                "15m": {
                    "last_candle_open_at": _to_iso(row.get("last_15m_candle_open_at")),
                    "age_seconds": _age_seconds(row.get("last_15m_candle_open_at"), now=reference_now),
                },
                "1h": {
                    "last_candle_open_at": _to_iso(row.get("last_1h_candle_open_at")),
                    "age_seconds": _age_seconds(row.get("last_1h_candle_open_at"), now=reference_now),
                },
                "4h": {
                    "last_candle_open_at": _to_iso(row.get("last_4h_candle_open_at")),
                    "age_seconds": _age_seconds(row.get("last_4h_candle_open_at"), now=reference_now),
                },
            },
        },
        "websocket": {
            "last_message_at": _to_iso(row.get("last_ws_message_at")),
            "message_age_seconds": ws_age_seconds,
            "healthy": websocket_healthy,
        },
        "collector": None,
    }


def _empty_decision_window(start_at: datetime) -> dict[str, Any]:
    return {
        "start_at": start_at.isoformat(),
        "total": 0,
        "by_outcome": {},
        "by_reason": {},
    }


def read_decision_funnel_from_conn(
    conn: sqlite3.Connection,
    *,
    config_hash: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    reference_now = _to_utc(now or datetime.now(timezone.utc))
    windows = {
        "24h": reference_now - timedelta(hours=24),
        "7d": reference_now - timedelta(days=7),
    }
    payload = {
        "config_hash": config_hash,
        "windows": {
            key: _empty_decision_window(start_at)
            for key, start_at in windows.items()
        },
    }

    if not _table_exists(conn, "decision_outcomes"):
        return payload

    for key, start_at in windows.items():
        counts = fetch_decision_outcome_counts(
            conn,
            since_ts=start_at,
            config_hash=config_hash,
        )
        by_reason = counts["by_reason"]
        payload["windows"][key] = {
            "start_at": start_at.isoformat(),
            "total": sum(by_reason.values()),
            "by_outcome": counts["by_outcome"],
            "by_reason": by_reason,
        }

    return payload


def read_config_snapshot_from_conn(conn: sqlite3.Connection, *, config_hash: str) -> dict[str, Any]:
    if not _table_exists(conn, "config_snapshots"):
        return {
            "config_hash": config_hash,
            "captured_at": None,
            "strategy": None,
        }

    row = get_config_snapshot(conn, config_hash)
    if row is None:
        return {
            "config_hash": config_hash,
            "captured_at": None,
            "strategy": None,
        }

    strategy: dict[str, Any] | None = None
    raw_strategy = row.get("strategy_json")
    if isinstance(raw_strategy, str):
        try:
            parsed = json.loads(raw_strategy)
            strategy = parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            strategy = None

    return {
        "config_hash": str(row["config_hash"]),
        "captured_at": _to_iso(row["captured_at"]),
        "strategy": strategy,
    }


def read_feature_quality_from_conn(conn: sqlite3.Connection) -> dict[str, Any]:
    if not _table_exists(conn, "runtime_metrics"):
        return {
            "updated_at": None,
            "config_hash": None,
            "quality": {},
        }

    row = get_runtime_metrics(conn)
    if row is None:
        return {
            "updated_at": None,
            "config_hash": None,
            "quality": {},
        }

    return {
        "updated_at": _to_iso(row.get("updated_at")),
        "config_hash": row.get("config_hash"),
        "quality": _parse_json_dict(row.get("feature_quality_json")),
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

    def read_trades(
        self,
        *,
        limit: int = 50,
        config_hash: str | None = None,
    ) -> dict[str, Any]:
        try:
            conn = self._connect_fn(self.db_path)
        except sqlite3.OperationalError as exc:
            if _is_missing_db_error(exc):
                return {"trades": []}
            raise
        try:
            return read_trades_from_conn(conn, limit=limit, config_hash=config_hash)
        finally:
            conn.close()

    def read_signals(
        self,
        *,
        limit: int = 20,
        config_hash: str | None = None,
    ) -> dict[str, Any]:
        try:
            conn = self._connect_fn(self.db_path)
        except sqlite3.OperationalError as exc:
            if _is_missing_db_error(exc):
                return {"signals": []}
            raise
        try:
            return read_signals_from_conn(conn, limit=limit, config_hash=config_hash)
        finally:
            conn.close()

    def read_daily_metrics(self, *, days: int = 14) -> dict[str, Any]:
        try:
            conn = self._connect_fn(self.db_path)
        except sqlite3.OperationalError as exc:
            if _is_missing_db_error(exc):
                return {"metrics": []}
            raise
        try:
            return read_daily_metrics_from_conn(conn, days=days)
        finally:
            conn.close()

    def read_alerts(self, *, limit: int = 20) -> dict[str, Any]:
        try:
            conn = self._connect_fn(self.db_path)
        except sqlite3.OperationalError as exc:
            if _is_missing_db_error(exc):
                return {"alerts": []}
            raise
        try:
            return read_alerts_from_conn(conn, limit=limit)
        finally:
            conn.close()

    def read_runtime_freshness(self, *, heartbeat_seconds: int = 30) -> dict[str, Any]:
        try:
            conn = self._connect_fn(self.db_path)
        except sqlite3.OperationalError as exc:
            if _is_missing_db_error(exc):
                return _runtime_freshness_unavailable()
            raise
        try:
            return read_runtime_freshness_from_conn(conn, heartbeat_seconds=heartbeat_seconds)
        finally:
            conn.close()

    def read_decision_funnel(
        self,
        *,
        config_hash: str | None = None,
    ) -> dict[str, Any]:
        try:
            conn = self._connect_fn(self.db_path)
        except sqlite3.OperationalError as exc:
            if _is_missing_db_error(exc):
                reference_now = _to_utc(datetime.now(timezone.utc))
                return {
                    "config_hash": config_hash,
                    "windows": {
                        "24h": _empty_decision_window(reference_now - timedelta(hours=24)),
                        "7d": _empty_decision_window(reference_now - timedelta(days=7)),
                    },
                }
            raise
        try:
            return read_decision_funnel_from_conn(conn, config_hash=config_hash)
        finally:
            conn.close()

    def read_config_snapshot(self, *, config_hash: str) -> dict[str, Any]:
        try:
            conn = self._connect_fn(self.db_path)
        except sqlite3.OperationalError as exc:
            if _is_missing_db_error(exc):
                return {
                    "config_hash": config_hash,
                    "captured_at": None,
                    "strategy": None,
                }
            raise
        try:
            return read_config_snapshot_from_conn(conn, config_hash=config_hash)
        finally:
            conn.close()

    def read_feature_quality(self) -> dict[str, Any]:
        try:
            conn = self._connect_fn(self.db_path)
        except sqlite3.OperationalError as exc:
            if _is_missing_db_error(exc):
                return {
                    "updated_at": None,
                    "config_hash": None,
                    "quality": {},
                }
            raise
        try:
            return read_feature_quality_from_conn(conn)
        finally:
            conn.close()
