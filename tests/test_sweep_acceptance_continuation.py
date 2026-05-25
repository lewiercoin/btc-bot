from __future__ import annotations

from datetime import datetime, timedelta, timezone

from research_lab.analysis_sweep_acceptance_continuation import (
    AcceptanceConfig,
    Candle,
    detect_equal_levels,
    maybe_signal,
)


def _candle(idx: int, *, open_: float, high: float, low: float, close: float) -> Candle:
    return Candle(
        open_time=datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=15 * idx),
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=1.0,
    )


def test_detect_equal_levels_requires_hits_and_age() -> None:
    levels = [(0, 100.0), (3, 100.1), (7, 99.9), (8, 104.0)]

    detected = detect_equal_levels(levels, tolerance=0.25, min_hits=3, min_age_bars=5)

    assert detected == [100.0]


def test_high_sweep_without_reclaim_acceptance_generates_long() -> None:
    candles: list[Candle] = []
    for idx in range(20):
        high = 100.0 if idx in {0, 5, 12} else 99.4
        candles.append(_candle(idx, open_=99.5, high=high, low=98.8, close=99.4))
    candles.append(_candle(20, open_=99.8, high=101.4, low=99.7, close=101.0))
    candles.append(_candle(21, open_=101.1, high=101.2, low=100.8, close=101.0))
    cfg = AcceptanceConfig(
        config_id="test",
        equal_level_lookback=20,
        atr_period=5,
        min_sweep_depth_pct=0.001,
        proximity_atr=1.0,
        entry_mode="next_open",
    )

    signal, reason = maybe_signal(candles, {candles[20].open_time: 0.25}, 20, symbol="BTCUSDT", config=cfg)

    assert reason == "candidate"
    assert signal is not None
    assert signal.direction == "LONG"
    assert signal.sweep_side == "HIGH"


def test_high_sweep_with_reclaim_is_rejected() -> None:
    candles: list[Candle] = []
    for idx in range(20):
        high = 100.0 if idx in {0, 5, 12} else 99.4
        candles.append(_candle(idx, open_=99.5, high=high, low=98.8, close=99.4))
    candles.append(_candle(20, open_=99.8, high=101.4, low=99.2, close=99.0))
    candles.append(_candle(21, open_=99.1, high=99.2, low=98.8, close=99.0))
    cfg = AcceptanceConfig(
        config_id="test",
        equal_level_lookback=20,
        atr_period=5,
        min_sweep_depth_pct=0.001,
        proximity_atr=1.0,
        entry_mode="next_open",
    )

    signal, reason = maybe_signal(candles, {candles[20].open_time: 0.25}, 20, symbol="BTCUSDT", config=cfg)

    assert signal is None
    assert reason == "no_sweep_acceptance"
