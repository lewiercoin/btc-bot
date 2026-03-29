from __future__ import annotations

import sqlite3
from datetime import datetime

from core.execution_types import FillEvent
from execution.execution_engine import PositionPersister
from storage.repositories import insert_execution_fill_event, insert_position


class SqlitePositionPersister(PositionPersister):
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def insert_position(
        self,
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
        insert_position(
            self._connection,
            position_id=position_id,
            signal_id=signal_id,
            symbol=symbol,
            direction=direction,
            status=status,
            entry_price=entry_price,
            size=size,
            leverage=leverage,
            stop_loss=stop_loss,
            take_profit_1=take_profit_1,
            take_profit_2=take_profit_2,
            opened_at=opened_at,
            updated_at=updated_at,
        )

    def insert_execution_fill_event(
        self,
        *,
        position_id: str,
        order_type: str,
        fill_event: FillEvent,
    ) -> None:
        insert_execution_fill_event(
            self._connection,
            position_id=position_id,
            order_type=order_type,
            fill_event=fill_event,
        )

    def commit(self) -> None:
        self._connection.commit()
