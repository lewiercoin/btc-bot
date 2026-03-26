from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

OrderType = Literal["LIMIT", "MARKET"]
OrderSide = Literal["BUY", "SELL"]

@dataclass(slots=True)
class FillResult:
    filled_price: float
    slippage_bps: float
    fee_paid: float


class FillModel:
    def simulate(
        self,
        requested_price: float,
        qty: float,
        *,
        order_type: OrderType = "MARKET",
        side: OrderSide = "BUY",
    ) -> FillResult:
        raise NotImplementedError


@dataclass(slots=True)
class FillModelConfig:
    slippage_bps_limit: float = 1.0
    slippage_bps_market: float = 3.0
    fee_rate_maker: float = 0.0004
    fee_rate_taker: float = 0.0004


class SimpleFillModel(FillModel):
    """Deterministic fill model with static slippage and fee rates."""

    def __init__(self, config: FillModelConfig | None = None) -> None:
        self.config = config or FillModelConfig()

    def simulate(
        self,
        requested_price: float,
        qty: float,
        *,
        order_type: OrderType = "MARKET",
        side: OrderSide = "BUY",
    ) -> FillResult:
        if requested_price <= 0:
            raise ValueError(f"requested_price must be positive, got {requested_price!r}")
        if qty <= 0:
            raise ValueError(f"qty must be positive, got {qty!r}")

        normalized_type = order_type.upper()
        normalized_side = side.upper()
        if normalized_type not in ("LIMIT", "MARKET"):
            raise ValueError(f"Unsupported order_type={order_type!r}; expected LIMIT or MARKET.")
        if normalized_side not in ("BUY", "SELL"):
            raise ValueError(f"Unsupported side={side!r}; expected BUY or SELL.")

        if normalized_type == "LIMIT":
            slippage_bps = float(self.config.slippage_bps_limit)
            fee_rate = float(self.config.fee_rate_maker)
        else:
            slippage_bps = float(self.config.slippage_bps_market)
            fee_rate = float(self.config.fee_rate_taker)

        direction_sign = 1.0 if normalized_side == "BUY" else -1.0
        filled_price = float(requested_price) * (1.0 + direction_sign * slippage_bps / 10_000.0)
        fee_paid = filled_price * float(qty) * fee_rate
        return FillResult(
            filled_price=filled_price,
            slippage_bps=slippage_bps,
            fee_paid=fee_paid,
        )
