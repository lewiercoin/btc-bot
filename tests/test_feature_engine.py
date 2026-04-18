from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from core.feature_engine import FeatureEngine, FeatureEngineConfig, detect_sweep_reclaim
from core.models import MarketSnapshot


def _candle(open_time: datetime, open_: float, high: float, low: float, close: float) -> dict[str, float | datetime]:
    return {
        "open_time": open_time,
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": 1.0,
    }


def _snapshot(
    ts: datetime,
    *,
    price: float,
    open_interest: float,
    cvd_15m: float,
    tfi_60s: float,
    force_orders_count: int,
    candles_15m: list[dict[str, float | datetime]] | None = None,
) -> MarketSnapshot:
    candles_15m = candles_15m or [
        _candle(ts - timedelta(minutes=45), 100.0, 101.0, 99.0, 100.0),
        _candle(ts - timedelta(minutes=30), 100.0, 102.0, 99.0, 101.0),
        _candle(ts - timedelta(minutes=15), 101.0, 103.0, 100.0, 102.0),
    ]
    candles_1h = [
        _candle(ts - timedelta(hours=3), 100.0, 101.0, 99.0, 100.0),
        _candle(ts - timedelta(hours=2), 100.0, 101.0, 99.0, 101.0),
        _candle(ts - timedelta(hours=1), 101.0, 102.0, 100.0, 102.0),
    ]
    candles_4h = [
        _candle(ts - timedelta(hours=12), 100.0, 101.0, 99.0, 100.0),
        _candle(ts - timedelta(hours=8), 100.0, 101.0, 99.0, 101.0),
        _candle(ts - timedelta(hours=4), 101.0, 102.0, 100.0, 102.0),
    ]
    funding = [
        {"funding_time": ts - timedelta(hours=8), "funding_rate": 0.0001},
        {"funding_time": ts, "funding_rate": 0.0002},
    ]
    force_orders = [{"event_time": ts - timedelta(seconds=10)} for _ in range(force_orders_count)]
    return MarketSnapshot(
        symbol="BTCUSDT",
        timestamp=ts,
        price=price,
        bid=price - 0.1,
        ask=price + 0.1,
        candles_15m=candles_15m,
        candles_1h=candles_1h,
        candles_4h=candles_4h,
        funding_history=funding,
        open_interest=open_interest,
        aggtrades_bucket_60s={"tfi": tfi_60s},
        aggtrades_bucket_15m={"cvd": cvd_15m},
        force_order_events_60s=force_orders,
    )


def _low_sweep_candles(ts: datetime) -> list[dict[str, float | datetime]]:
    return [
        _candle(ts - timedelta(minutes=60), 101.0, 103.0, 100.0, 102.0),
        _candle(ts - timedelta(minutes=45), 102.0, 104.0, 100.0, 103.0),
        _candle(ts - timedelta(minutes=30), 103.0, 104.0, 101.0, 103.5),
        _candle(ts - timedelta(minutes=15), 102.5, 103.0, 98.0, 101.5),
    ]


def _high_sweep_candles(ts: datetime) -> list[dict[str, float | datetime]]:
    return [
        _candle(ts - timedelta(minutes=75), 100.0, 104.0, 99.0, 101.0),
        _candle(ts - timedelta(minutes=60), 101.0, 104.0, 100.0, 102.0),
        _candle(ts - timedelta(minutes=45), 101.5, 104.0, 100.5, 102.0),
        _candle(ts - timedelta(minutes=30), 102.0, 103.0, 101.0, 102.5),
        _candle(ts - timedelta(minutes=15), 102.5, 106.0, 101.5, 102.0),
    ]


def test_compute_features_is_idempotent() -> None:
    now = datetime(2026, 1, 1, 0, 15, tzinfo=timezone.utc)
    snapshot = _snapshot(
        now,
        price=102.0,
        open_interest=1_000.0,
        cvd_15m=5.0,
        tfi_60s=0.1,
        force_orders_count=2,
    )
    engine = FeatureEngine()

    first = engine.compute(snapshot, "v1.0", "hash")
    second = engine.compute(snapshot, "v1.0", "hash")
    third = engine.compute(snapshot, "v1.0", "hash")

    assert first == second == third


def test_compute_features_independent_of_prior_state() -> None:
    now = datetime(2026, 1, 1, 0, 15, tzinfo=timezone.utc)
    prior_snapshot = _snapshot(
        now - timedelta(minutes=15),
        price=103.0,
        open_interest=1_200.0,
        cvd_15m=1.0,
        tfi_60s=0.9,
        force_orders_count=50,
    )
    target_snapshot = _snapshot(
        now,
        price=102.0,
        open_interest=1_000.0,
        cvd_15m=5.0,
        tfi_60s=0.1,
        force_orders_count=2,
    )

    used_engine = FeatureEngine()
    _ = used_engine.compute(prior_snapshot, "v1.0", "hash")
    warm_result = used_engine.compute(target_snapshot, "v1.0", "hash")

    fresh_engine = FeatureEngine()
    fresh_result = fresh_engine.compute(target_snapshot, "v1.0", "hash")
    assert warm_result != fresh_result

    used_engine.reset()
    reset_result = used_engine.compute(target_snapshot, "v1.0", "hash")
    assert reset_result == fresh_result


def test_compute_features_marks_low_sweep_side() -> None:
    now = datetime(2026, 1, 1, 0, 15, tzinfo=timezone.utc)
    snapshot = _snapshot(
        now,
        price=101.5,
        open_interest=1_000.0,
        cvd_15m=5.0,
        tfi_60s=0.1,
        force_orders_count=2,
        candles_15m=_low_sweep_candles(now),
    )

    features = FeatureEngine().compute(snapshot, "v1.0", "hash")

    assert features.sweep_detected is True
    assert features.sweep_side == "LOW"
    assert features.close_vs_reclaim_buffer_atr is not None
    assert features.wick_vs_min_atr is not None
    assert features.sweep_vs_buffer_atr is not None


def test_compute_features_marks_high_sweep_side() -> None:
    now = datetime(2026, 1, 1, 0, 15, tzinfo=timezone.utc)
    snapshot = _snapshot(
        now,
        price=102.0,
        open_interest=1_000.0,
        cvd_15m=5.0,
        tfi_60s=-0.1,
        force_orders_count=2,
        candles_15m=_high_sweep_candles(now),
    )

    features = FeatureEngine().compute(snapshot, "v1.0", "hash")

    assert features.sweep_detected is True
    assert features.sweep_side == "HIGH"
    assert features.close_vs_reclaim_buffer_atr is not None
    assert features.wick_vs_min_atr is not None
    assert features.sweep_vs_buffer_atr is not None


def test_detect_sweep_reclaim_reports_low_sweep_diagnostic_margins() -> None:
    ts = datetime(2026, 1, 1, 0, 15, tzinfo=timezone.utc)
    candles = [
        _candle(ts - timedelta(minutes=15), 100.0, 101.0, 99.0, 100.0),
        _candle(ts, 101.0, 102.0, 98.0, 101.0),
    ]

    detected = detect_sweep_reclaim(
        candles,
        equal_lows=[100.0],
        equal_highs=[],
        atr_15m=10.0,
        config=FeatureEngineConfig(),
    )

    assert detected[0:5] == (True, False, 100.0, 0.02, "LOW")
    assert detected[5] == pytest.approx(0.05)
    assert detected[6] == pytest.approx(-0.1)
    assert detected[7] == pytest.approx(0.05)


def test_detect_sweep_reclaim_reports_high_sweep_diagnostic_margins() -> None:
    ts = datetime(2026, 1, 1, 0, 15, tzinfo=timezone.utc)
    candles = [
        _candle(ts - timedelta(minutes=15), 100.0, 101.0, 99.0, 100.0),
        _candle(ts, 99.0, 102.0, 98.0, 99.0),
    ]

    detected = detect_sweep_reclaim(
        candles,
        equal_lows=[],
        equal_highs=[100.0],
        atr_15m=10.0,
        config=FeatureEngineConfig(),
    )

    assert detected[0:5] == (True, False, 100.0, 0.02, "HIGH")
    assert detected[5] == pytest.approx(0.05)
    assert detected[6] == pytest.approx(-0.1)
    assert detected[7] == pytest.approx(0.05)


def test_cvd_divergence_uses_windowed_swing_reference_not_last_bar_only() -> None:
    engine = FeatureEngine(FeatureEngineConfig(cvd_divergence_window_bars=4))
    start = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    engine._cvd_price_history.extend(
        [
            (start, 100.0, 5.0),
            (start + timedelta(minutes=15), 102.0, 8.0),
            (start + timedelta(minutes=30), 101.0, -20.0),
            (start + timedelta(minutes=45), 103.0, 1.0),
        ]
    )

    bullish, bearish = engine._compute_cvd_divergence()

    assert bullish is False
    assert bearish is True
