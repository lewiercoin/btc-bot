from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from core.models import ExecutableSignal
from execution.execution_engine import ExecutionEngine, PositionPersister


class PaperExecutionEngine(ExecutionEngine):
    def __init__(self, *, position_persister: PositionPersister, symbol: str = "BTCUSDT") -> None:
        self.position_persister = position_persister
        self.symbol = symbol.upper()

    def execute_signal(self, signal: ExecutableSignal, size: float, leverage: int) -> None:
        position_id = f"paper-{uuid4().hex}"
        timestamp = datetime.now(timezone.utc)

        self.position_persister.insert_position(
            position_id=position_id,
            signal_id=signal.signal_id,
            symbol=self.symbol,
            direction=signal.direction,
            status="OPEN",
            entry_price=signal.entry_price,
            size=size,
            leverage=leverage,
            stop_loss=signal.stop_loss,
            take_profit_1=signal.take_profit_1,
            take_profit_2=signal.take_profit_2,
            opened_at=timestamp,
            updated_at=timestamp,
        )
        self.position_persister.commit()
