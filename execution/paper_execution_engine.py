from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from core.execution_types import ExecutionStatus, FillEvent
from core.models import ExecutableSignal
from execution.execution_engine import ExecutionEngine, PositionPersister


class PaperExecutionEngine(ExecutionEngine):
    def __init__(
        self,
        *,
        position_persister: PositionPersister,
        symbol: str = "BTCUSDT",
        allowed_symbols: tuple[str, ...] | None = None,
    ) -> None:
        self.position_persister = position_persister
        self.symbol = symbol.upper()
        self.allowed_symbols = tuple(s.upper() for s in (allowed_symbols or (self.symbol,)))

    def execute_signal(
        self,
        signal: ExecutableSignal,
        size: float,
        leverage: int,
        *,
        snapshot_price: float | None = None,
        bid_price: float | None = None,
        ask_price: float | None = None,
        snapshot_id: str | None = None,
    ) -> None:
        if self.symbol not in self.allowed_symbols:
            allowed = ",".join(self.allowed_symbols)
            raise ValueError(f"paper_execution_symbol_not_allowed:symbol={self.symbol}:allowed={allowed}")
        if snapshot_price is None:
            raise ValueError("PaperExecutionEngine requires snapshot_price for fill simulation.")

        # Use bid/ask spread for realistic fill pricing (REMEDIATION-A2)
        # BUY (LONG): fill at ask (buy from asks), SELL (SHORT): fill at bid (sell to bids)
        side = "BUY" if signal.direction == "LONG" else "SELL"
        if side == "BUY" and ask_price is not None and ask_price > 0:
            filled_price = float(ask_price)
        elif side == "SELL" and bid_price is not None and bid_price > 0:
            filled_price = float(bid_price)
        else:
            # Fallback to snapshot price if bid/ask not available
            filled_price = float(snapshot_price)

        if filled_price <= 0:
            raise ValueError(f"PaperExecutionEngine received invalid fill price={filled_price!r}.")
        self._validate_bracket_after_fill(signal=signal, filled_price=filled_price)

        # Calculate fees: 0.04% taker rate (match backtest SimpleFillModel)
        fee_rate = 0.0004  # 0.04% = 4 basis points
        notional = filled_price * float(size)
        fees = notional * fee_rate

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
                side=side,
                requested_price=requested_price,
                filled_price=filled_price,
                qty=float(size),
                fees=fees,
                slippage_bps=slippage_bps,
                executed_at=timestamp,
                snapshot_id=snapshot_id,
            ),
        )
        self.position_persister.commit()

    @staticmethod
    def _validate_bracket_after_fill(*, signal: ExecutableSignal, filled_price: float) -> None:
        stop_loss = float(signal.stop_loss)
        take_profit_1 = float(signal.take_profit_1)
        take_profit_2 = float(signal.take_profit_2)
        if signal.direction == "LONG":
            valid = stop_loss < filled_price < take_profit_1 <= take_profit_2
        else:
            valid = take_profit_2 <= take_profit_1 < filled_price < stop_loss
        if valid:
            return

        raise ValueError(
            "paper_fill_invalid_bracket:"
            f"direction={signal.direction}:"
            f"filled_price={filled_price:.8f}:"
            f"stop_loss={stop_loss:.8f}:"
            f"take_profit_1={take_profit_1:.8f}:"
            f"take_profit_2={take_profit_2:.8f}"
        )
