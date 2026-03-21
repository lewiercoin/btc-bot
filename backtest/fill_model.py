from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class FillResult:
    filled_price: float
    slippage_bps: float
    fee_paid: float


class FillModel:
    def simulate(self, requested_price: float, qty: float) -> FillResult:
        raise NotImplementedError
