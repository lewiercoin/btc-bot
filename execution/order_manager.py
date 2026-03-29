from __future__ import annotations

from dataclasses import replace
from typing import Any

from core.execution_types import OrderRequest
from data.rest_client import BinanceFuturesRestClient, BinanceRequestError, RestClientError
from monitoring.audit_logger import AuditLogger


class OrderManagerError(RuntimeError):
    def __init__(self, message: str, *, code: int | None = None, reason: str = "unknown") -> None:
        self.code = code
        self.reason = reason
        super().__init__(message)


def _format_float(value: float) -> str:
    text = f"{value:.12f}".rstrip("0").rstrip(".")
    return text or "0"


class OrderManager:
    _INSUFFICIENT_MARGIN_CODES = {-2019, -2027, -2028}
    _INVALID_PRICE_CODES = {-1013, -1111, -4001, -4003, -4014}
    _UNKNOWN_ORDER_CODES = {-2011}

    def __init__(self, rest_client: BinanceFuturesRestClient, audit_logger: AuditLogger, symbol: str = "BTCUSDT") -> None:
        self.rest_client = rest_client
        self.audit_logger = audit_logger
        self.symbol = symbol.upper()
        self._submitted_orders: dict[str, OrderRequest] = {}

    def submit(self, request: OrderRequest) -> str:
        normalized = self._normalize_request(request)
        params = self._build_submit_params(normalized)
        try:
            response = self.rest_client.signed_request(
                "/fapi/v1/order",
                params=params,
                method="POST",
            )
        except Exception as exc:
            self.audit_logger.log_error(
                "order_manager",
                "Order submit failed.",
                payload={
                    "client_order_id": normalized.client_order_id,
                    "symbol": normalized.symbol,
                    "side": normalized.side,
                    "type": normalized.order_type,
                },
            )
            raise self._to_order_error("submit", exc) from exc

        client_order_id = str(response.get("clientOrderId") or normalized.client_order_id)
        self._submitted_orders[client_order_id] = replace(normalized, client_order_id=client_order_id)
        self.audit_logger.log_info(
            "order_manager",
            "Order submitted.",
            payload={
                "client_order_id": client_order_id,
                "symbol": normalized.symbol,
                "side": normalized.side,
                "type": normalized.order_type,
                "qty": normalized.qty,
                "price": normalized.price,
                "stop_price": normalized.stop_price,
                "status": response.get("status"),
            },
        )
        return client_order_id

    def cancel(self, client_order_id: str) -> None:
        normalized_id = str(client_order_id)
        try:
            response = self.rest_client.signed_request(
                "/fapi/v1/order",
                params={
                    "symbol": self.symbol,
                    "origClientOrderId": normalized_id,
                },
                method="DELETE",
            )
        except Exception as exc:
            self.audit_logger.log_error(
                "order_manager",
                "Order cancel failed.",
                payload={"client_order_id": normalized_id, "symbol": self.symbol},
            )
            raise self._to_order_error("cancel", exc) from exc

        self._submitted_orders.pop(normalized_id, None)
        self.audit_logger.log_info(
            "order_manager",
            "Order canceled.",
            payload={
                "client_order_id": normalized_id,
                "symbol": self.symbol,
                "status": response.get("status"),
            },
        )

    def amend(self, client_order_id: str, qty: float | None = None, price: float | None = None) -> None:
        existing = self._submitted_orders.get(client_order_id)
        if existing is None:
            raise OrderManagerError(
                f"amend_failed:unknown_client_order_id:{client_order_id}",
                reason="unknown_order",
            )
        if qty is None and price is None:
            self.audit_logger.log_info(
                "order_manager",
                "Order amend skipped (no changes).",
                payload={"client_order_id": client_order_id},
            )
            return

        amended = replace(
            existing,
            qty=float(qty) if qty is not None else existing.qty,
            price=float(price) if price is not None else existing.price,
        )
        if amended.qty <= 0:
            raise OrderManagerError("amend_failed:invalid_qty", reason="invalid_qty")
        if amended.order_type == "LIMIT" and (amended.price is None or amended.price <= 0):
            raise OrderManagerError("amend_failed:invalid_price", reason="invalid_price")

        self.audit_logger.log_info(
            "order_manager",
            "Order amend requested (cancel + new).",
            payload={
                "client_order_id": client_order_id,
                "new_qty": amended.qty,
                "new_price": amended.price,
            },
        )
        self.cancel(client_order_id)
        self.submit(amended)
        self.audit_logger.log_info(
            "order_manager",
            "Order amend completed.",
            payload={
                "client_order_id": amended.client_order_id,
                "qty": amended.qty,
                "price": amended.price,
            },
        )

    def _normalize_request(self, request: OrderRequest) -> OrderRequest:
        normalized = replace(
            request,
            client_order_id=str(request.client_order_id),
            symbol=str(request.symbol).upper(),
            side=str(request.side).upper(),
            order_type=str(request.order_type).upper(),
            qty=float(request.qty),
            price=float(request.price) if request.price is not None else None,
            stop_price=float(request.stop_price) if request.stop_price is not None else None,
            time_in_force=str(request.time_in_force).upper(),
        )
        if normalized.symbol != self.symbol:
            raise OrderManagerError(
                f"submit_failed:symbol_mismatch:{normalized.symbol}",
                reason="symbol_mismatch",
            )
        if normalized.qty <= 0:
            raise OrderManagerError("submit_failed:invalid_qty", reason="invalid_qty")
        if normalized.order_type == "LIMIT" and (normalized.price is None or normalized.price <= 0):
            raise OrderManagerError("submit_failed:invalid_price", reason="invalid_price")
        if normalized.order_type in {"STOP_MARKET", "TAKE_PROFIT_MARKET"} and (
            normalized.stop_price is None or normalized.stop_price <= 0
        ):
            raise OrderManagerError("submit_failed:invalid_stop_price", reason="invalid_stop_price")
        return normalized

    def _build_submit_params(self, request: OrderRequest) -> dict[str, Any]:
        params: dict[str, Any] = {
            "symbol": request.symbol,
            "side": request.side,
            "type": request.order_type,
            "quantity": _format_float(request.qty),
            "newClientOrderId": request.client_order_id,
        }
        if request.order_type == "LIMIT":
            assert request.price is not None
            params["price"] = _format_float(request.price)
            params["timeInForce"] = request.time_in_force
        if request.order_type in {"STOP_MARKET", "TAKE_PROFIT_MARKET"}:
            assert request.stop_price is not None
            params["stopPrice"] = _format_float(request.stop_price)
            params["reduceOnly"] = "true"
        return params

    def _to_order_error(self, action: str, exc: Exception) -> OrderManagerError:
        if isinstance(exc, OrderManagerError):
            return exc
        if isinstance(exc, BinanceRequestError):
            code = exc.code
            message = exc.message
            if code in self._INSUFFICIENT_MARGIN_CODES:
                return OrderManagerError(f"{action}_failed:insufficient_margin:{message}", code=code, reason="insufficient_margin")
            if code in self._INVALID_PRICE_CODES:
                return OrderManagerError(f"{action}_failed:invalid_price:{message}", code=code, reason="invalid_price")
            if code in self._UNKNOWN_ORDER_CODES:
                return OrderManagerError(f"{action}_failed:unknown_order:{message}", code=code, reason="unknown_order")
            return OrderManagerError(f"{action}_failed:exchange_rejected:{message}", code=code, reason="exchange_rejected")
        if isinstance(exc, RestClientError):
            return OrderManagerError(f"{action}_failed:transport_error:{exc}", reason="transport_error")
        return OrderManagerError(f"{action}_failed:unexpected_error:{exc}", reason="unexpected_error")
