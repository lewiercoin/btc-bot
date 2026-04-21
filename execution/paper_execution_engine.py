from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from core.execution_types import ExecutionStatus, FillEvent
from core.models import ExecutableSignal
from execution.execution_engine import ExecutionEngine, PositionPersister


class PaperExecutionEngine(ExecutionEngine):
    def __init__(self, *, position_persister: PositionPersister, symbol: str = "BTCUSDT") -> None:
        self.position_persister = position_persister
        self.symbol = symbol.upper()

    def execute_signal(
        self,
        signal: ExecutableSignal,
        size: float,
        leverage: int,
        *,
        snapshot_price: float | None = None,
    ) -> None:
        if snapshot_price is None:
            raise ValueError("PaperExecutionEngine requires snapshot_price for fill simulation.")
        filled_price = float(snapshot_price)
        if filled_price <= 0:
            raise ValueError(f"PaperExecutionEngine received invalid snapshot_price={snapshot_price!r}.")

        position_id = f"paper-{uuid4().hex}"
        timestamp = datetime.now(timezone.utc)
        requested_price = float(signal.entry_price)
        slippage_bps = 0.0
        if requested_price > 0:
            slippage_bps = abs(filled_price - requested_price) / requested_price * 10_000.0

        self.position_persister.insert_position(
            position_id=position_id,
            signal_id=signal.signal_id,
            symbol=self.symbol,
            direction=signal.direction,
            status="OPEN",
            entry_price=filled_price,
            size=size,
            leverage=leverage,
            stop_loss=signal.stop_loss,
            take_profit_1=signal.take_profit_1,
            take_profit_2=signal.take_profit_2,
            opened_at=timestamp,
            updated_at=timestamp,
        )
        self.position_persister.insert_execution_fill_event(
            position_id=position_id,
            order_type="MARKET",
            fill_event=FillEvent(
                execution_id=f"exe-{uuid4().hex}",
                client_order_id=f"paper-{signal.signal_id[:16]}-{uuid4().hex[:8]}",
                status=ExecutionStatus.FILLED,
                side="BUY" if signal.direction == "LONG" else "SELL",
                requested_price=requested_price,
                filled_price=filled_price,
                qty=float(size),
                fees=0.0,
                slippage_bps=slippage_bps,
                executed_at=timestamp,
            ),
        )
        self.position_persister.commit()
