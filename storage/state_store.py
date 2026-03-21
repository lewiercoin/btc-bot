from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from core.models import BotState
from storage.repositories import get_bot_state, upsert_bot_state


class StateStore:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

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
