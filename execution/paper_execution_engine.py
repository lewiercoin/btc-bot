from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from uuid import uuid4

from core.models import ExecutableSignal
from execution.execution_engine import ExecutionEngine


class PaperExecutionEngine(ExecutionEngine):
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def execute_signal(self, signal: ExecutableSignal, size: float, leverage: int) -> None:
        position_id = f"paper-{uuid4().hex}"
        timestamp = datetime.now(timezone.utc).isoformat()

        self.connection.execute(
            """
            INSERT INTO positions (
                position_id, signal_id, symbol, direction, status, entry_price, size,
                leverage, stop_loss, take_profit_1, take_profit_2, opened_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                position_id,
                signal.signal_id,
                "BTCUSDT",
                signal.direction,
                "OPEN",
                signal.entry_price,
                size,
                leverage,
                signal.stop_loss,
                signal.take_profit_1,
                signal.take_profit_2,
                timestamp,
                timestamp,
            ),
        )
        self.connection.commit()
