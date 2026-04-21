from __future__ import annotations

from core.feature_engine import FeatureEngineConfig
from settings import DataQualityConfig


def test_funding_quality_thresholds_are_config_driven_and_ordered() -> None:
    data_quality = DataQualityConfig()
    engine_config = FeatureEngineConfig()

    assert data_quality.funding_coverage_ready == engine_config.funding_coverage_ready
    assert data_quality.funding_coverage_degraded == engine_config.funding_coverage_degraded
    assert 0.0 <= data_quality.funding_coverage_degraded < data_quality.funding_coverage_ready <= 1.0
