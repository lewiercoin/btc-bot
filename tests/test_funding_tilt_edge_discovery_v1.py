from __future__ import annotations

from datetime import datetime, timezone

from backtest.fill_model import FillModelConfig
from core.funding import FundingRateSample
from research_lab.diagnostics.funding_tilt_edge_discovery_v1 import (
    Candle,
    calculate_trade_return,
)


def _candle(ts: datetime, price: float) -> Candle:
    return Candle(
        index=0,
        open_time=ts,
        open=price,
        high=price,
        low=price,
        close=price,
        volume=1.0,
    )


def test_funding_tilt_pnl_sign_credits_short_on_positive_funding() -> None:
    opened = datetime(2026, 6, 1, 0, 15, tzinfo=timezone.utc)
    closed = datetime(2026, 6, 1, 8, 15, tzinfo=timezone.utc)
    funding_samples = [
        FundingRateSample(
            funding_time=datetime(2026, 6, 1, 8, 0, tzinfo=timezone.utc),
            funding_rate=0.002,
        )
    ]

    trade = calculate_trade_return(
        cohort="unit",
        fold="fold_unit",
        cell_key="W30_Z2_H3",
        direction="SHORT",
        signal_index=0,
        exit_index=1,
        entry_candle=_candle(opened, 100.0),
        exit_candle=_candle(closed, 100.0),
        funding_samples=funding_samples,
        exit_reason="UNIT",
        fill_config=FillModelConfig(
            slippage_bps_market=3.0,
            fee_rate_taker=0.0004,
        ),
    )

    entry_fill = 100.0 * (1.0 - 0.0003)
    exit_fill = 100.0 * (1.0 + 0.0003)
    gross = entry_fill - exit_fill
    fees = entry_fill * 0.0004 + exit_fill * 0.0004
    funding_paid = -entry_fill * 0.002
    expected_net = gross - fees - funding_paid
    expected_return = expected_net / entry_fill

    assert trade.funding_paid_pct < 0.0
    assert trade.funding_credit_pct > 0.0
    assert trade.net_return_pct == expected_return
    assert trade.net_return_pct > 0.0


def test_funding_tilt_pnl_sign_credits_long_on_negative_funding() -> None:
    opened = datetime(2026, 6, 1, 0, 15, tzinfo=timezone.utc)
    closed = datetime(2026, 6, 1, 8, 15, tzinfo=timezone.utc)
    funding_samples = [
        FundingRateSample(
            funding_time=datetime(2026, 6, 1, 8, 0, tzinfo=timezone.utc),
            funding_rate=-0.002,
        )
    ]

    trade = calculate_trade_return(
        cohort="unit",
        fold="fold_unit",
        cell_key="W30_Z2_H3",
        direction="LONG",
        signal_index=0,
        exit_index=1,
        entry_candle=_candle(opened, 100.0),
        exit_candle=_candle(closed, 100.0),
        funding_samples=funding_samples,
        exit_reason="UNIT",
        fill_config=FillModelConfig(
            slippage_bps_market=3.0,
            fee_rate_taker=0.0004,
        ),
    )

    entry_fill = 100.0 * (1.0 + 0.0003)
    exit_fill = 100.0 * (1.0 - 0.0003)
    gross = exit_fill - entry_fill
    fees = entry_fill * 0.0004 + exit_fill * 0.0004
    funding_paid = entry_fill * -0.002
    expected_net = gross - fees - funding_paid
    expected_return = expected_net / entry_fill

    assert trade.funding_paid_pct < 0.0
    assert trade.funding_credit_pct > 0.0
    assert trade.net_return_pct == expected_return
    assert trade.net_return_pct > 0.0
