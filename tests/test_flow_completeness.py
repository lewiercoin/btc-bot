from __future__ import annotations

from datetime import datetime, timedelta, timezone

from core.feature_engine import FeatureEngineConfig
from data.market_data import MarketDataAssembler
from settings import DataQualityConfig


class DummyRestClient:
    pass


def test_flow_quality_thresholds_are_config_driven_and_ordered() -> None:
    data_quality = DataQualityConfig()
    engine_config = FeatureEngineConfig()

    assert data_quality.flow_coverage_ready == engine_config.flow_coverage_ready
    assert data_quality.flow_coverage_degraded == engine_config.flow_coverage_degraded
    assert 0.0 <= data_quality.flow_coverage_degraded < data_quality.flow_coverage_ready <= 1.0


def test_partial_flow_window_is_not_labeled_ready() -> None:
    now = datetime(2026, 1, 1, 0, 15, tzinfo=timezone.utc)
    assembler = MarketDataAssembler(rest_client=DummyRestClient())  # type: ignore[arg-type]
    trades = [
        {"event_time": now - timedelta(minutes=3), "qty": 1.0, "is_buyer_maker": False},
        {"event_time": now - timedelta(minutes=1), "qty": 1.0, "is_buyer_maker": True},
    ]

    metadata = assembler._flow_window_metadata(
        trades,
        now=now,
        window_seconds=15 * 60,
        source="rest",
    )
    quality = assembler._quality_from_flow_metadata(metadata)

    assert quality.status == "unavailable"
    assert quality.reason == "flow_window_insufficient"
    assert quality.metadata["coverage_ratio"] < assembler.config.flow_coverage_degraded

def test_flow_60s_ready_despite_high_volume_15m() -> None:
    """
    Regression test for shared limit_reached bug (FLOW-WINDOW-FIX-V1).
    
    Scenario: REST fetch returns >=1000 trades (high volume / pagination).
    60s window has full coverage (trades span full 60 seconds).
    15m window may be partial (trades don't span full 15 minutes).
    
    Expected: 60s → READY (not false positive DEGRADED)
    Expected: 15m → degraded/unavailable based on actual coverage
    """
    now = datetime(2026, 4, 27, 12, 0, tzinfo=timezone.utc)
    assembler = MarketDataAssembler(rest_client=DummyRestClient())  # type: ignore[arg-type]
    
    # Simulate high-volume scenario: trades densely packed in last 90 seconds
    # (mimics pagination fetch returning many trades for recent period)
    trades = []
    for i in range(100):  # Dense trades
        offset_seconds = 90 - i * 0.9  # Spread over 90 seconds
        trades.append({
            "event_time": now - timedelta(seconds=offset_seconds),
            "qty": 1.0,
            "is_buyer_maker": (i % 2 == 0),
        })
    
    # 60s window metadata
    metadata_60s = assembler._flow_window_metadata(
        trades,
        now=now,
        window_seconds=60,
        source="rest",
    )
    quality_60s = assembler._quality_from_flow_metadata(metadata_60s)
    
    # 60s window should be READY (full coverage of last 60 seconds)
    # First trade at now-90s, last trade at now-0.9s
    # Coverage for 60s window: (now-0.9s) - max(now-90s, now-60s) = 59.1s / 60s ≈ 0.985
    assert quality_60s.status == "ready", f"60s should be READY, got {quality_60s.status} ({quality_60s.reason})"
    assert quality_60s.reason == "flow_window_complete"
    assert metadata_60s["coverage_ratio"] >= assembler.config.flow_coverage_ready
    
    # 15m window metadata (same trades)
    metadata_15m = assembler._flow_window_metadata(
        trades,
        now=now,
        window_seconds=15 * 60,
        source="rest",
    )
    quality_15m = assembler._quality_from_flow_metadata(metadata_15m)
    
    # 15m window should be degraded/unavailable (only covers last ~90 seconds of 900 seconds)
    # Coverage for 15m window: 90s / 900s = 0.1
    assert quality_15m.status in ("degraded", "unavailable"), \
        f"15m should be degraded/unavailable, got {quality_15m.status}"
    assert metadata_15m["coverage_ratio"] < assembler.config.flow_coverage_ready
    
    # Key assertion: NO shared state - 60s READY despite 15m degraded
    # (Before fix: both would be DEGRADED due to shared limit_reached flag)
    assert quality_60s.status == "ready" and quality_15m.status != "ready", \
        "60s and 15m should have independent quality assessment"
