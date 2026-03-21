from __future__ import annotations

from core.execution_types import OrderRequest


class OrderManager:
    def submit(self, request: OrderRequest) -> str:
        raise NotImplementedError

    def cancel(self, client_order_id: str) -> None:
        raise NotImplementedError

    def amend(self, client_order_id: str, qty: float | None = None, price: float | None = None) -> None:
        raise NotImplementedError
