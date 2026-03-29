from __future__ import annotations

import sqlite3
import time
from datetime import datetime, timezone
from uuid import uuid4

from core.execution_types import ExecutionStatus, FillEvent, OrderRequest
from core.models import ExecutableSignal
from data.rest_client import BinanceRequestError, BinanceFuturesRestClient, RestClientError
from execution.execution_engine import ExecutionEngine
from execution.order_manager import OrderManager, OrderManagerError
from monitoring.audit_logger import AuditLogger
from storage.repositories import insert_execution_fill_event, insert_position


class LiveExecutionError(RuntimeError):
    pass


class LiveExecutionEngine(ExecutionEngine):
    def __init__(
        self,
        *,
        connection: sqlite3.Connection,
        rest_client: BinanceFuturesRestClient,
        order_manager: OrderManager,
        audit_logger: AuditLogger,
        symbol: str = "BTCUSDT",
        entry_order_type: str = "LIMIT",
        entry_timeout_seconds: int = 90,
        poll_interval_seconds: float = 1.0,
    ) -> None:
        self.connection = connection
        self.rest_client = rest_client
        self.order_manager = order_manager
        self.audit_logger = audit_logger
        self.symbol = symbol.upper()
        self.entry_order_type = entry_order_type.upper()
        self.entry_timeout_seconds = max(int(entry_timeout_seconds), 1)
        self.poll_interval_seconds = max(float(poll_interval_seconds), 0.0)

    def execute_signal(self, signal: ExecutableSignal, size: float, leverage: int) -> None:
        try:
            self._set_leverage(leverage)
            entry_side = "BUY" if signal.direction == "LONG" else "SELL"
            entry_request = self._build_entry_order(signal=signal, size=size, side=entry_side)
            entry_client_order_id = self.order_manager.submit(entry_request)
            fill_result = self._wait_for_entry_fill(
                client_order_id=entry_client_order_id,
                request=entry_request,
            )
        except (OrderManagerError, RestClientError, BinanceRequestError) as exc:
            self.audit_logger.log_error(
                "live_execution",
                "Entry execution failed.",
                payload={"signal_id": signal.signal_id, "error": str(exc)},
            )
            raise LiveExecutionError(f"entry_execution_failed:{exc}") from exc

        if fill_result.filled_qty <= 0:
            raise LiveExecutionError("entry_execution_failed:zero_fill_qty")

        position_id = f"live-{uuid4().hex}"
        position_status = "OPEN" if fill_result.fully_filled else "PARTIAL"
        opened_at = fill_result.executed_at
        insert_position(
            self.connection,
            position_id=position_id,
            signal_id=signal.signal_id,
            symbol=self.symbol,
            direction=signal.direction,
            status=position_status,
            entry_price=fill_result.avg_fill_price,
            size=fill_result.filled_qty,
            leverage=int(leverage),
            stop_loss=signal.stop_loss,
            take_profit_1=signal.take_profit_1,
            take_profit_2=signal.take_profit_2,
            opened_at=opened_at,
            updated_at=opened_at,
        )
        for event in fill_result.events:
            insert_execution_fill_event(
                self.connection,
                position_id=position_id,
                order_type=entry_request.order_type,
                fill_event=event,
            )
        self.connection.commit()

        try:
            exit_side = "SELL" if signal.direction == "LONG" else "BUY"
            stop_order = OrderRequest(
                client_order_id=f"sl-{signal.signal_id[:16]}-{uuid4().hex[:8]}",
                symbol=self.symbol,
                side=exit_side,
                order_type="STOP_MARKET",
                qty=fill_result.filled_qty,
                stop_price=signal.stop_loss,
            )
            tp_order = OrderRequest(
                client_order_id=f"tp-{signal.signal_id[:16]}-{uuid4().hex[:8]}",
                symbol=self.symbol,
                side=exit_side,
                order_type="TAKE_PROFIT_MARKET",
                qty=fill_result.filled_qty,
                stop_price=signal.take_profit_1,
            )
            stop_id = self.order_manager.submit(stop_order)
            tp_id = self.order_manager.submit(tp_order)

            stop_event = self._snapshot_order_event(
                client_order_id=stop_id,
                requested_price=stop_order.stop_price,
                fallback_side=stop_order.side,
            )
            tp_event = self._snapshot_order_event(
                client_order_id=tp_id,
                requested_price=tp_order.stop_price,
                fallback_side=tp_order.side,
            )
            insert_execution_fill_event(
                self.connection,
                position_id=position_id,
                order_type=stop_order.order_type,
                fill_event=stop_event,
            )
            insert_execution_fill_event(
                self.connection,
                position_id=position_id,
                order_type=tp_order.order_type,
                fill_event=tp_event,
            )
            self.connection.commit()
            self.audit_logger.log_info(
                "live_execution",
                "Live execution completed.",
                payload={
                    "signal_id": signal.signal_id,
                    "position_id": position_id,
                    "entry_order_id": entry_client_order_id,
                    "stop_order_id": stop_id,
                    "tp_order_id": tp_id,
                    "filled_qty": fill_result.filled_qty,
                    "fully_filled": fill_result.fully_filled,
                },
            )
        except (OrderManagerError, RestClientError, BinanceRequestError) as exc:
            self.audit_logger.log_error(
                "live_execution",
                "Protective order placement failed after entry fill.",
                payload={
                    "signal_id": signal.signal_id,
                    "position_id": position_id,
                    "error": str(exc),
                },
            )
            raise LiveExecutionError(f"protective_order_failed:{exc}") from exc

    def _set_leverage(self, leverage: int) -> None:
        self.rest_client.signed_request(
            "/fapi/v1/leverage",
            params={"symbol": self.symbol, "leverage": int(leverage)},
            method="POST",
        )

    def _build_entry_order(self, *, signal: ExecutableSignal, size: float, side: str) -> OrderRequest:
        client_order_id = f"entry-{signal.signal_id[:16]}-{uuid4().hex[:8]}"
        if self.entry_order_type == "MARKET":
            return OrderRequest(
                client_order_id=client_order_id,
                symbol=self.symbol,
                side=side,
                order_type="MARKET",
                qty=float(size),
            )
        return OrderRequest(
            client_order_id=client_order_id,
            symbol=self.symbol,
            side=side,
            order_type="LIMIT",
            qty=float(size),
            price=float(signal.entry_price),
            time_in_force="GTC",
        )

    def _wait_for_entry_fill(self, *, client_order_id: str, request: OrderRequest) -> "_EntryFillResult":
        deadline = time.monotonic() + self.entry_timeout_seconds
        seen: set[tuple[str, float, float | None]] = set()
        events: list[FillEvent] = []
        last_payload: dict | None = None

        while True:
            payload = self._fetch_order(client_order_id)
            last_payload = payload
            event = self._payload_to_fill_event(
                payload=payload,
                client_order_id=client_order_id,
                requested_price=request.price,
                fallback_side=request.side,
            )
            key = (event.status.value, round(event.qty, 10), event.filled_price)
            if key not in seen:
                events.append(event)
                seen.add(key)

            if event.status == ExecutionStatus.FILLED:
                return _EntryFillResult(
                    filled_qty=event.qty,
                    avg_fill_price=event.filled_price or request.price or 0.0,
                    events=events,
                    fully_filled=True,
                    executed_at=event.executed_at,
                )

            if event.status == ExecutionStatus.REJECTED:
                raise LiveExecutionError(f"entry_order_rejected:{client_order_id}")

            if time.monotonic() >= deadline:
                filled_qty = self._to_float(payload.get("executedQty"), 0.0)
                avg_price = self._to_float(payload.get("avgPrice"), 0.0)
                if filled_qty > 0:
                    try:
                        self.order_manager.cancel(client_order_id)
                    except OrderManagerError:
                        pass
                    return _EntryFillResult(
                        filled_qty=filled_qty,
                        avg_fill_price=avg_price if avg_price > 0 else (request.price or 0.0),
                        events=events,
                        fully_filled=False,
                        executed_at=event.executed_at,
                    )

                try:
                    self.order_manager.cancel(client_order_id)
                except OrderManagerError:
                    pass
                raise LiveExecutionError(f"entry_order_timeout_unfilled:{client_order_id}")

            if event.status == ExecutionStatus.CANCELED:
                filled_qty = self._to_float(payload.get("executedQty"), 0.0)
                if filled_qty > 0:
                    avg_price = self._to_float(payload.get("avgPrice"), 0.0)
                    return _EntryFillResult(
                        filled_qty=filled_qty,
                        avg_fill_price=avg_price if avg_price > 0 else (request.price or 0.0),
                        events=events,
                        fully_filled=False,
                        executed_at=event.executed_at,
                    )
                raise LiveExecutionError(f"entry_order_canceled:{client_order_id}")

            if self.poll_interval_seconds > 0:
                time.sleep(self.poll_interval_seconds)

            # Defensive guard if exchange repeatedly returns malformed payload.
            if last_payload is None:
                raise LiveExecutionError(f"entry_order_state_unavailable:{client_order_id}")

    def _fetch_order(self, client_order_id: str) -> dict:
        payload = self.rest_client.signed_request(
            "/fapi/v1/order",
            params={
                "symbol": self.symbol,
                "origClientOrderId": client_order_id,
            },
            method="GET",
        )
        if not isinstance(payload, dict):
            raise LiveExecutionError(f"invalid_order_snapshot_payload:{client_order_id}")
        return payload

    def _snapshot_order_event(
        self,
        *,
        client_order_id: str,
        requested_price: float | None,
        fallback_side: str,
    ) -> FillEvent:
        payload = self._fetch_order(client_order_id)
        return self._payload_to_fill_event(
            payload=payload,
            client_order_id=client_order_id,
            requested_price=requested_price,
            fallback_side=fallback_side,
        )

    def _payload_to_fill_event(
        self,
        *,
        payload: dict,
        client_order_id: str,
        requested_price: float | None,
        fallback_side: str,
    ) -> FillEvent:
        raw_status = str(payload.get("status", "NEW")).upper()
        status = self._map_status(raw_status)
        executed_qty = self._to_float(payload.get("executedQty"), 0.0)
        orig_qty = self._to_float(payload.get("origQty"), 0.0)
        avg_price = self._to_float(payload.get("avgPrice"), 0.0)

        if status in {ExecutionStatus.PARTIALLY_FILLED, ExecutionStatus.FILLED}:
            event_qty = executed_qty
            filled_price = avg_price if avg_price > 0 else requested_price
        else:
            event_qty = orig_qty if orig_qty > 0 else executed_qty
            filled_price = avg_price if avg_price > 0 else None

        event_ts = self._payload_time(payload)
        slippage_bps = 0.0
        if requested_price and requested_price > 0 and filled_price and filled_price > 0:
            slippage_bps = abs(filled_price - requested_price) / requested_price * 10_000.0

        return FillEvent(
            execution_id=f"exe-{uuid4().hex}",
            client_order_id=str(payload.get("clientOrderId") or client_order_id),
            status=status,
            side=str(payload.get("side") or fallback_side).upper(),
            requested_price=requested_price,
            filled_price=filled_price if filled_price and filled_price > 0 else None,
            qty=event_qty,
            fees=0.0,
            slippage_bps=slippage_bps,
            executed_at=event_ts,
        )

    @staticmethod
    def _map_status(raw_status: str) -> ExecutionStatus:
        mapping = {
            "NEW": ExecutionStatus.NEW,
            "PARTIALLY_FILLED": ExecutionStatus.PARTIALLY_FILLED,
            "FILLED": ExecutionStatus.FILLED,
            "CANCELED": ExecutionStatus.CANCELED,
            "EXPIRED": ExecutionStatus.CANCELED,
            "REJECTED": ExecutionStatus.REJECTED,
        }
        return mapping.get(raw_status.upper(), ExecutionStatus.REJECTED)

    @staticmethod
    def _payload_time(payload: dict) -> datetime:
        raw_ms = payload.get("updateTime") or payload.get("transactTime") or payload.get("time")
        if raw_ms is None:
            return datetime.now(timezone.utc)
        try:
            return datetime.fromtimestamp(int(raw_ms) / 1000, tz=timezone.utc)
        except (TypeError, ValueError):
            return datetime.now(timezone.utc)

    @staticmethod
    def _to_float(value: object, default: float = 0.0) -> float:
        if value in (None, ""):
            return default
        return float(value)


class _EntryFillResult:
    def __init__(
        self,
        *,
        filled_qty: float,
        avg_fill_price: float,
        events: list[FillEvent],
        fully_filled: bool,
        executed_at: datetime,
    ) -> None:
        self.filled_qty = filled_qty
        self.avg_fill_price = avg_fill_price
        self.events = events
        self.fully_filled = fully_filled
        self.executed_at = executed_at
