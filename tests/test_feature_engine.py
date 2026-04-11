from __future__ import annotations

from datetime import datetime, timedelta, timezone

from core.feature_engine import FeatureEngine, FeatureEngineConfig
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
        _candle(ts - timedelta(minutes=105), 101.0, 103.0, 100.0, 102.0),
        _candle(ts - timedelta(minutes=90),  102.0, 104.0, 101.5, 103.0),
        _candle(ts - timedelta(minutes=75),  103.0, 104.0, 100.0, 103.5),
        _candle(ts - timedelta(minutes=60),  103.5, 104.5, 101.0, 103.5),
        _candle(ts - timedelta(minutes=45),  103.0, 104.0, 101.5, 103.0),
        _candle(ts - timedelta(minutes=30),  103.0, 104.0, 100.0, 103.5),
        _candle(ts - timedelta(minutes=15),  103.0, 103.5, 101.5, 103.0),
        _candle(ts,                          101.0, 103.5,  97.0, 101.5),
    ]


def _high_sweep_candles(ts: datetime) -> list[dict[str, float | datetime]]:
    return [
        _candle(ts - timedelta(minutes=105), 101.0, 104.0, 100.0, 102.0),
        _candle(ts - timedelta(minutes=90),  102.0, 103.0, 101.0, 102.5),
        _candle(ts - timedelta(minutes=75),  102.5, 104.0, 101.5, 103.0),
        _candle(ts - timedelta(minutes=60),  103.0, 103.5, 101.5, 103.0),
        _candle(ts - timedelta(minutes=45),  103.0, 103.5, 101.0, 103.0),
        _candle(ts - timedelta(minutes=30),  103.0, 104.0, 101.5, 103.5),
        _candle(ts - timedelta(minutes=15),  103.5, 103.5, 101.5, 103.0),
        _candle(ts,                          103.0, 107.0, 102.5, 102.0),
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


def test_level_min_age_bars_filters_short_span_cluster() -> None:
    from core.feature_engine import detect_equal_levels

    levels_short = [(0, 100.0), (1, 100.0), (2, 100.0), (3, 100.0)]
    result = detect_equal_levels(levels_short, tolerance=1.0, min_hits=3, min_age_bars=5)
    assert result == []

    levels_ok = [(0, 100.0), (1, 100.0), (2, 100.0), (3, 100.0), (4, 100.0), (5, 100.0)]
    result2 = detect_equal_levels(levels_ok, tolerance=1.0, min_hits=3, min_age_bars=5)
    assert result2 == [100.0]


def test_param_registry_contains_new_sweep_params() -> None:
    from research_lab.param_registry import build_param_registry, get_active_params, get_frozen_params

    build_param_registry.cache_clear()
    active = get_active_params()
    frozen = get_frozen_params()

    assert "level_min_age_bars" in active
    assert active["level_min_age_bars"].low == 2
    assert active["level_min_age_bars"].high == 20
    assert active["level_min_age_bars"].step == 1

    assert "min_hits" in active
    assert active["min_hits"].low == 2
    assert active["min_hits"].high == 5
    assert active["min_hits"].step == 1

    assert "weight_sweep_detected" in frozen
    assert "weight_reclaim_confirmed" in frozen
    assert "always-true intercept" in (frozen["weight_sweep_detected"].reason or "")
    assert "always-true intercept" in (frozen["weight_reclaim_confirmed"].reason or "")

    assert active["confluence_min"].low == 0.20
    assert active["confluence_min"].high == 0.75
    assert active["confluence_min"].step == 0.05


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
