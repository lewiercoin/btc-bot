from __future__ import annotations

from datetime import datetime, timedelta, timezone

from research_lab.analysis_breakout_momentum_chop import Candle, chop_bucket, compute_choppiness, cost_in_r


def _candle(idx: int, *, high: float, low: float, close: float) -> Candle:
    return Candle(
        open_time=datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=15 * idx),
        open=close,
        high=high,
        low=low,
        close=close,
        volume=1.0,
    )


def test_compute_choppiness_low_for_clean_trend() -> None:
    candles = [_candle(idx, high=100 + idx + 0.2, low=100 + idx - 0.2, close=100 + idx) for idx in range(20)]

    chop = compute_choppiness(candles, period=14)

    assert chop is not None
    assert chop < 38.2
    assert chop_bucket(chop) == "low_trend"


def test_compute_choppiness_high_for_back_and_forth_range() -> None:
    candles = []
    for idx in range(20):
        close = 100.0 + (0.5 if idx % 2 else -0.5)
        candles.append(_candle(idx, high=101.0, low=99.0, close=close))

    chop = compute_choppiness(candles, period=14)

    assert chop is not None
    assert chop > 61.8
    assert chop_bucket(chop) == "high_chop"


def test_cost_in_r_scales_with_stop_distance() -> None:
    wide_stop = cost_in_r(entry=100.0, exit_price=102.0, stop_distance=2.0)
    tight_stop = cost_in_r(entry=100.0, exit_price=102.0, stop_distance=1.0)

    assert round(tight_stop, 6) == round(wide_stop * 2, 6)
