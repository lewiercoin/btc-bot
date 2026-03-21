from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class PerformanceReport:
    trades_count: int
    expectancy_r: float
    pnl_abs: float
    pnl_r_sum: float
    max_drawdown_pct: float


def summarize() -> PerformanceReport:
    raise NotImplementedError
