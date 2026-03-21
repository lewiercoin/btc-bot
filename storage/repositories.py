from __future__ import annotations

import json
import sqlite3
from datetime import datetime

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
    ts = (timestamp or datetime.utcnow()).isoformat()
    conn.execute(
        """
        INSERT INTO bot_state (
            id, timestamp, mode, healthy, safe_mode, open_positions_count, consecutive_losses,
            daily_dd_pct, weekly_dd_pct, last_trade_at, last_error
        ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            last_error = excluded.last_error
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
        ),
    )


def get_bot_state(conn: sqlite3.Connection) -> dict | None:
    row = conn.execute("SELECT * FROM bot_state WHERE id = 1").fetchone()
    if not row:
        return None
    return dict(row)
