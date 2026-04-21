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
        limit_reached=False,
    )
    quality = assembler._quality_from_flow_metadata(metadata)

    assert quality.status == "unavailable"
    assert quality.reason == "flow_window_insufficient"
    assert quality.metadata["coverage_ratio"] < assembler.config.flow_coverage_degraded
