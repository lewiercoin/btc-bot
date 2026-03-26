from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from dataclasses import dataclass

from data.rest_client import BinanceFuturesRestClient
from data.websocket_client import BinanceFuturesWebsocketClient


@dataclass(slots=True)
class HealthStatus:
    websocket_alive: bool
    db_writable: bool
    exchange_reachable: bool

    @property
    def healthy(self) -> bool:
        return self.websocket_alive and self.db_writable and self.exchange_reachable


class HealthMonitor:
    def __init__(
        self,
        *,
        websocket_client: BinanceFuturesWebsocketClient | None,
        connection: sqlite3.Connection,
        rest_client: BinanceFuturesRestClient,
    ) -> None:
        self.websocket_client = websocket_client
        self.connection = connection
        self.rest_client = rest_client

    def check(self) -> HealthStatus:
        return HealthStatus(
            websocket_alive=self._check_websocket_alive(),
            db_writable=self._check_db_writable(),
            exchange_reachable=self._check_exchange_reachable(),
        )

    def _check_websocket_alive(self) -> bool:
        if self.websocket_client is None:
            return False
        thread = getattr(self.websocket_client, "_thread", None)
        if thread is None or not thread.is_alive():
            return False

        last_message_at = self.websocket_client.last_message_at
        if last_message_at is None:
            return True
        heartbeat_seconds = int(getattr(self.websocket_client.config, "heartbeat_seconds", 30))
        max_delay = max(heartbeat_seconds * 3, 5)
        age = (datetime.now(timezone.utc) - last_message_at.astimezone(timezone.utc)).total_seconds()
        return age <= max_delay

    def _check_db_writable(self) -> bool:
        try:
            ts = datetime.now(timezone.utc).isoformat()
            self.connection.execute(
                """
                CREATE TEMP TABLE IF NOT EXISTS health_probe (
                    id INTEGER PRIMARY KEY,
                    ts TEXT NOT NULL
                )
                """
            )
            self.connection.execute(
                "INSERT OR REPLACE INTO health_probe (id, ts) VALUES (1, ?)",
                (ts,),
            )
            row = self.connection.execute("SELECT ts FROM health_probe WHERE id = 1").fetchone()
            return bool(row and row["ts"] == ts)
        except Exception:
            return False

    def _check_exchange_reachable(self) -> bool:
        try:
            return bool(self.rest_client.ping())
        except Exception:
            return False
