from __future__ import annotations

from datetime import datetime, timedelta, timezone

from core.feature_engine import FeatureEngine, FeatureEngineConfig
from core.models import MarketSnapshot
from settings import DataQualityConfig


def test_funding_quality_thresholds_are_config_driven_and_ordered() -> None:
    data_quality = DataQualityConfig()
    engine_config = FeatureEngineConfig()

    assert data_quality.funding_coverage_ready == engine_config.funding_coverage_ready
    assert data_quality.funding_coverage_degraded == engine_config.funding_coverage_degraded
    assert 0.0 <= data_quality.funding_coverage_degraded < data_quality.funding_coverage_ready <= 1.0


def test_funding_window_reports_degraded_or_unavailable_when_history_is_clipped() -> None:
    now = datetime(2026, 1, 2, tzinfo=timezone.utc)
    engine = FeatureEngine(FeatureEngineConfig(funding_window_days=1))
    snapshot = MarketSnapshot(
        symbol="BTCUSDT",
        timestamp=now,
        price=100.0,
        bid=99.5,
        ask=100.5,
        funding_history=[
            {"funding_time": now - timedelta(hours=8), "funding_rate": 0.0001},
        ],
    )

    features = engine.compute(snapshot, "v1.0", "hash")

    assert features.quality["funding_window"].status == "unavailable"
    assert features.quality["funding_window"].metadata["loaded_samples"] == 1
    assert features.quality["funding_window"].metadata["required_samples"] == 3
