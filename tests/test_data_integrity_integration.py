from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone

from core.models import FeatureQuality, Features, MarketSnapshot
from settings import DataQualityConfig


def test_history_dependent_quality_keys_can_live_on_snapshot_and_features() -> None:
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    quality = {
        "oi_baseline": FeatureQuality.ready(
            reason="baseline_loaded",
            metadata={"loaded_days": 60, "required_days": 60},
            provenance="bootstrapped-from-db",
        ),
        "cvd_divergence": FeatureQuality.degraded(
            reason="insufficient_bars",
            metadata={"loaded_bars": 12, "required_bars": 30},
            provenance="mixed",
        ),
        "flow_15m": FeatureQuality.unavailable(
            reason="missing_aggtrades_window",
            metadata={"coverage_ratio": 0.0},
            provenance="rest",
        ),
        "funding_window": FeatureQuality.ready(
            reason="window_complete",
            metadata={"coverage_ratio": 1.0},
            provenance="rest",
        ),
    }

    snapshot = MarketSnapshot(
        symbol="BTCUSDT",
        timestamp=now,
        price=100.0,
        bid=99.5,
        ask=100.5,
        quality=quality,
    )
    features = Features(
        schema_version="v1.0",
        config_hash="hash",
        timestamp=now,
        atr_15m=1.0,
        atr_4h=4.0,
        atr_4h_norm=0.01,
        ema50_4h=100.0,
        ema200_4h=99.0,
        quality=snapshot.quality,
    )

    assert set(features.quality) == {
        "oi_baseline",
        "cvd_divergence",
        "flow_15m",
        "funding_window",
    }
    assert asdict(features.quality["flow_15m"])["metadata"]["coverage_ratio"] == 0.0


def test_data_integrity_threshold_names_match_milestone_contract() -> None:
    data_quality = DataQualityConfig()

    assert data_quality.oi_baseline_days == 60
    assert data_quality.cvd_divergence_bars == 30
    assert data_quality.flow_coverage_ready == 0.90
    assert data_quality.flow_coverage_degraded == 0.70
