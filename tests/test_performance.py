from __future__ import annotations

from datetime import datetime, timedelta, timezone
from math import isclose, sqrt

from backtest.performance import _daily_sharpe_ratio, _max_drawdown_pct, summarize
from core.models import TradeLog


def _trade(
    *,
    trade_id: str,
    opened_at: datetime,
    closed_at: datetime | None,
    pnl_abs: float,
    pnl_r: float,
    fees: float = 0.0,
) -> TradeLog:
    return TradeLog(
        trade_id=trade_id,
        signal_id=f"sig-{trade_id}",
        opened_at=opened_at,
        closed_at=closed_at,
        direction="LONG",
        regime="normal",
        confluence_score=3.0,
        entry_price=100.0,
        exit_price=101.0 if closed_at else None,
        size=1.0,
        fees=fees,
        slippage_bps=0.0,
        pnl_abs=pnl_abs,
        pnl_r=pnl_r,
        mae=0.0,
        mfe=0.0,
        exit_reason="TP" if closed_at else None,
        features_at_entry_json={},
    )


def test_max_drawdown_pct_peak_to_trough() -> None:
    pnl_values = [100.0, -50.0, -200.0, 50.0]
    drawdown = _max_drawdown_pct(pnl_values=pnl_values, initial_equity=1_000.0)

    expected = 250.0 / 1_100.0
    assert isclose(drawdown, expected, rel_tol=1e-12, abs_tol=1e-12)


def test_daily_sharpe_ratio_uses_sample_variance() -> None:
    start = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    trades = [
        _trade(
            trade_id="t1",
            opened_at=start,
            closed_at=start + timedelta(hours=1),
            pnl_abs=100.0,
            pnl_r=1.0,
        ),
        _trade(
            trade_id="t2",
            opened_at=start + timedelta(days=1),
            closed_at=start + timedelta(days=1, hours=1),
            pnl_abs=-50.0,
            pnl_r=-0.5,
        ),
        _trade(
            trade_id="t3",
            opened_at=start + timedelta(days=2),
            closed_at=start + timedelta(days=2, hours=1),
            pnl_abs=150.0,
            pnl_r=1.5,
        ),
    ]

    sharpe = _daily_sharpe_ratio(trades, initial_equity=1_000.0)

    returns = [0.1, -50.0 / 1_100.0, 150.0 / 1_050.0]
    avg = sum(returns) / len(returns)
    sample_variance = sum((value - avg) ** 2 for value in returns) / (len(returns) - 1)
    expected = (avg / (sample_variance**0.5)) * sqrt(365.0)

    assert isclose(sharpe, expected, rel_tol=1e-12, abs_tol=1e-12)


def test_summarize_closed_trade_metrics_ignore_open_positions() -> None:
    start = datetime(2026, 2, 1, 0, 0, tzinfo=timezone.utc)
    trades = [
        _trade(
            trade_id="c1",
            opened_at=start,
            closed_at=start + timedelta(hours=1),
            pnl_abs=100.0,
            pnl_r=1.0,
            fees=1.0,
        ),
        _trade(
            trade_id="c2",
            opened_at=start + timedelta(hours=2),
            closed_at=start + timedelta(hours=3),
            pnl_abs=-40.0,
            pnl_r=-0.4,
            fees=2.0,
        ),
        _trade(
            trade_id="c3",
            opened_at=start + timedelta(hours=4),
            closed_at=start + timedelta(hours=5),
            pnl_abs=0.0,
            pnl_r=0.0,
            fees=0.5,
        ),
        _trade(
            trade_id="open",
            opened_at=start + timedelta(hours=6),
            closed_at=None,
            pnl_abs=999.0,
            pnl_r=9.99,
            fees=9.0,
        ),
    ]

    report = summarize(trades, initial_equity=1_000.0)

    assert report.trades_count == 3
    assert isclose(report.pnl_abs, 60.0)
    assert isclose(report.pnl_r_sum, 0.6)
    assert isclose(report.expectancy_r, 0.2)
    assert isclose(report.win_rate, 1.0 / 3.0)
    assert isclose(report.profit_factor, 2.5)
    assert isclose(report.total_fees, 3.5)
