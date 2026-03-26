from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from math import sqrt

from core.models import TradeLog


@dataclass(slots=True)
class PerformanceReport:
    trades_count: int
    expectancy_r: float
    pnl_abs: float
    pnl_r_sum: float
    max_drawdown_pct: float
    win_rate: float
    avg_winner_r: float
    avg_loser_r: float
    profit_factor: float
    max_consecutive_losses: int
    sharpe_ratio: float
    total_fees: float


def summarize(trades: list[TradeLog], *, initial_equity: float = 10_000.0) -> PerformanceReport:
    if not trades:
        return PerformanceReport(
            trades_count=0,
            expectancy_r=0.0,
            pnl_abs=0.0,
            pnl_r_sum=0.0,
            max_drawdown_pct=0.0,
            win_rate=0.0,
            avg_winner_r=0.0,
            avg_loser_r=0.0,
            profit_factor=0.0,
            max_consecutive_losses=0,
            sharpe_ratio=0.0,
            total_fees=0.0,
        )

    closed_trades = [trade for trade in trades if trade.closed_at is not None]
    if not closed_trades:
        return PerformanceReport(
            trades_count=0,
            expectancy_r=0.0,
            pnl_abs=0.0,
            pnl_r_sum=0.0,
            max_drawdown_pct=0.0,
            win_rate=0.0,
            avg_winner_r=0.0,
            avg_loser_r=0.0,
            profit_factor=0.0,
            max_consecutive_losses=0,
            sharpe_ratio=0.0,
            total_fees=0.0,
        )

    ordered = sorted(closed_trades, key=lambda trade: trade.closed_at or trade.opened_at)
    pnl_values = [float(trade.pnl_abs) for trade in ordered]
    pnl_r_values = [float(trade.pnl_r) for trade in ordered]
    wins = [trade for trade in ordered if float(trade.pnl_abs) > 0]
    losses = [trade for trade in ordered if float(trade.pnl_abs) < 0]
    winning_r = [float(trade.pnl_r) for trade in wins if float(trade.pnl_r) > 0]
    losing_r = [float(trade.pnl_r) for trade in losses if float(trade.pnl_r) < 0]

    pnl_abs_sum = float(sum(pnl_values))
    pnl_r_sum = float(sum(pnl_r_values))
    trades_count = len(ordered)
    expectancy_r = pnl_r_sum / trades_count if trades_count else 0.0
    win_rate = len(wins) / trades_count if trades_count else 0.0
    avg_winner_r = sum(winning_r) / len(winning_r) if winning_r else 0.0
    avg_loser_r = sum(losing_r) / len(losing_r) if losing_r else 0.0

    gross_profit = sum(float(trade.pnl_abs) for trade in wins)
    gross_loss_abs = abs(sum(float(trade.pnl_abs) for trade in losses))
    if gross_loss_abs == 0:
        profit_factor = float("inf") if gross_profit > 0 else 0.0
    else:
        profit_factor = gross_profit / gross_loss_abs

    max_consecutive_losses = _max_consecutive_losses(ordered)
    max_drawdown_pct = _max_drawdown_pct(pnl_values=pnl_values, initial_equity=max(initial_equity, 1e-8))
    sharpe_ratio = _daily_sharpe_ratio(ordered, initial_equity=max(initial_equity, 1e-8))
    total_fees = float(sum(float(trade.fees) for trade in ordered))

    return PerformanceReport(
        trades_count=trades_count,
        expectancy_r=expectancy_r,
        pnl_abs=pnl_abs_sum,
        pnl_r_sum=pnl_r_sum,
        max_drawdown_pct=max_drawdown_pct,
        win_rate=win_rate,
        avg_winner_r=avg_winner_r,
        avg_loser_r=avg_loser_r,
        profit_factor=profit_factor,
        max_consecutive_losses=max_consecutive_losses,
        sharpe_ratio=sharpe_ratio,
        total_fees=total_fees,
    )


def _max_consecutive_losses(trades: list[TradeLog]) -> int:
    max_losses = 0
    current = 0
    for trade in trades:
        if float(trade.pnl_abs) < 0:
            current += 1
            if current > max_losses:
                max_losses = current
        elif float(trade.pnl_abs) > 0:
            current = 0
    return max_losses


def _max_drawdown_pct(*, pnl_values: list[float], initial_equity: float) -> float:
    peak = initial_equity
    equity = initial_equity
    max_dd = 0.0
    for pnl in pnl_values:
        equity += float(pnl)
        if equity > peak:
            peak = equity
        drawdown = (peak - equity) / max(peak, 1e-8)
        if drawdown > max_dd:
            max_dd = drawdown
    return min(max(max_dd, 0.0), 1.0)


def _daily_sharpe_ratio(trades: list[TradeLog], *, initial_equity: float) -> float:
    daily_pnl: dict[date, float] = {}
    for trade in trades:
        if trade.closed_at is None:
            continue
        key = trade.closed_at.date()
        daily_pnl[key] = daily_pnl.get(key, 0.0) + float(trade.pnl_abs)

    if len(daily_pnl) < 2:
        return 0.0

    equity = initial_equity
    daily_returns: list[float] = []
    for day in sorted(daily_pnl):
        pnl = daily_pnl[day]
        ret = pnl / max(equity, 1e-8)
        daily_returns.append(ret)
        equity += pnl

    if len(daily_returns) < 2:
        return 0.0

    avg = sum(daily_returns) / len(daily_returns)
    variance = sum((value - avg) ** 2 for value in daily_returns) / len(daily_returns)
    stdev = variance**0.5
    if stdev == 0:
        return 0.0
    return (avg / stdev) * sqrt(365.0)
