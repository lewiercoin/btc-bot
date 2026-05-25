from __future__ import annotations

from datetime import datetime, timedelta, timezone

from research_lab.analysis_sweep_acceptance_retest_continuation import RetestConfig, maybe_signal
from research_lab.analysis_sweep_acceptance_continuation import Candle


def _candle(idx: int, *, open_: float, high: float, low: float, close: float) -> Candle:
    return Candle(
        open_time=datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=15 * idx),
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=1.0,
    )


def _base_candles() -> list[Candle]:
    candles: list[Candle] = []
    for idx in range(20):
        high = 100.0 if idx in {0, 5, 12} else 98.9
        candles.append(_candle(idx, open_=99.5, high=high, low=98.8, close=99.4))
    return candles


def test_acceptance_retest_hold_second_impulse_generates_long() -> None:
    candles = _base_candles()
    candles.append(_candle(20, open_=99.8, high=101.4, low=99.7, close=101.0))
    candles.append(_candle(21, open_=101.0, high=101.1, low=100.05, close=100.45))
    candles.append(_candle(22, open_=100.45, high=101.55, low=100.4, close=101.4))
    candles.append(_candle(23, open_=101.45, high=101.8, low=101.3, close=101.7))
    cfg = RetestConfig(
        config_id="test",
        equal_level_lookback=20,
        atr_period=5,
        min_sweep_depth_pct=0.001,
        proximity_atr=1.0,
        retest_window_bars=4,
        impulse_buf_atr=0.0,
        wick_min_atr=0.0,
    )

    signal, reason = maybe_signal(candles, {c.open_time: 0.2 for c in candles}, 20, symbol="BTCUSDT", config=cfg)

    assert reason == "candidate"
    assert signal is not None
    assert signal.direction == "LONG"
    assert signal.retest_idx == 21
    assert signal.impulse_idx == 22
    assert signal.entry_idx == 23


def test_acceptance_without_retest_impulse_is_rejected() -> None:
    candles = _base_candles()
    candles.append(_candle(20, open_=99.8, high=101.4, low=99.7, close=101.0))
    candles.append(_candle(21, open_=101.0, high=101.1, low=100.7, close=100.9))
    candles.append(_candle(22, open_=100.9, high=101.0, low=100.6, close=100.8))
    candles.append(_candle(23, open_=100.8, high=101.0, low=100.5, close=100.7))
    cfg = RetestConfig(
        config_id="test",
        equal_level_lookback=20,
        atr_period=5,
        min_sweep_depth_pct=0.001,
        proximity_atr=1.0,
        retest_window_bars=3,
        impulse_buf_atr=0.0,
    )

    signal, reason = maybe_signal(candles, {c.open_time: 0.2 for c in candles}, 20, symbol="BTCUSDT", config=cfg)

    assert signal is None
    assert reason == "no_retest_impulse"
