from __future__ import annotations

from datetime import datetime, timedelta, timezone

from core.feature_engine import FeatureEngine
from core.models import MarketSnapshot


def _snapshot(
    ts: datetime,
    *,
    price: float,
    open_interest: float,
    cvd_15m: float,
    tfi_60s: float,
    force_orders_count: int,
) -> MarketSnapshot:
    candles_15m = [
        {"open_time": ts - timedelta(minutes=45), "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0, "volume": 1.0},
        {"open_time": ts - timedelta(minutes=30), "open": 100.0, "high": 102.0, "low": 99.0, "close": 101.0, "volume": 1.0},
        {"open_time": ts - timedelta(minutes=15), "open": 101.0, "high": 103.0, "low": 100.0, "close": 102.0, "volume": 1.0},
    ]
    candles_1h = [
        {"open_time": ts - timedelta(hours=3), "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0, "volume": 1.0},
        {"open_time": ts - timedelta(hours=2), "open": 100.0, "high": 101.0, "low": 99.0, "close": 101.0, "volume": 1.0},
        {"open_time": ts - timedelta(hours=1), "open": 101.0, "high": 102.0, "low": 100.0, "close": 102.0, "volume": 1.0},
    ]
    candles_4h = [
        {"open_time": ts - timedelta(hours=12), "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0, "volume": 1.0},
        {"open_time": ts - timedelta(hours=8), "open": 100.0, "high": 101.0, "low": 99.0, "close": 101.0, "volume": 1.0},
        {"open_time": ts - timedelta(hours=4), "open": 101.0, "high": 102.0, "low": 100.0, "close": 102.0, "volume": 1.0},
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
