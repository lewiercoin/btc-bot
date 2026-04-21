from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta, timezone
import sqlite3
from pathlib import Path

from core.feature_engine import FeatureEngine, FeatureEngineConfig
from core.models import FeatureQuality, Features, MarketSnapshot
from data.market_data import MarketDataAssembler
from storage.db import init_db
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


def test_cold_start_marks_history_dependent_features_unavailable() -> None:
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    engine = FeatureEngine(FeatureEngineConfig(cvd_divergence_bars=3))

    features = engine.compute(
        MarketSnapshot(
            symbol="BTCUSDT",
            timestamp=now,
            price=100.0,
            bid=99.5,
            ask=100.5,
            open_interest=100.0,
            aggtrades_bucket_15m={"cvd": 1.0},
        ),
        "v1.0",
        "hash",
    )

    assert features.quality["oi_baseline"].status == "unavailable"
    assert features.quality["cvd_divergence"].status == "unavailable"


def test_restart_bootstrap_restores_mature_oi_and_cvd_quality() -> None:
    now = datetime(2026, 3, 1, tzinfo=timezone.utc)
    engine = FeatureEngine(FeatureEngineConfig(oi_baseline_days=60, oi_z_window_days=60, cvd_divergence_bars=3))
    engine.bootstrap_oi_history(
        [
            {"timestamp": now - timedelta(days=60), "oi_value": 100.0},
            {"timestamp": now - timedelta(days=30), "oi_value": 110.0},
        ]
    )
    engine.bootstrap_cvd_price_history(
        [
            {"bar_time": now - timedelta(minutes=30), "price_close": 100.0, "cvd": 1.0},
            {"bar_time": now - timedelta(minutes=15), "price_close": 101.0, "cvd": 2.0},
        ]
    )

    features = engine.compute(
        MarketSnapshot(
            symbol="BTCUSDT",
            timestamp=now,
            price=102.0,
            bid=101.5,
            ask=102.5,
            open_interest=120.0,
            aggtrades_bucket_15m={"cvd": 3.0},
        ),
        "v1.0",
        "hash",
    )

    assert features.quality["oi_baseline"].status == "ready"
    assert features.quality["cvd_divergence"].status == "ready"


class FakeRestClient:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def fetch_book_ticker(self, symbol: str) -> dict:
        return {"symbol": symbol, "bid": 99.0, "ask": 101.0}

    def fetch_klines(self, symbol: str, interval: str, limit: int = 500) -> list[dict]:
        _ = symbol
        _ = interval
        _ = limit
        return []

    def fetch_funding_history(self, symbol: str, limit: int = 200) -> list[dict]:
        _ = symbol
        _ = limit
        return []

    def fetch_open_interest(self, symbol: str) -> dict:
        return {"symbol": symbol, "timestamp": self.now, "oi_value": 123.0}

    def fetch_agg_trades_window(
        self,
        *,
        symbol: str,
        start_time: datetime,
        end_time: datetime,
        limit: int = 1000,
    ) -> list[dict]:
        _ = symbol
        _ = start_time
        _ = limit
        return [
            {"event_time": end_time - timedelta(minutes=14, seconds=50), "qty": 1.0, "is_buyer_maker": False},
            {"event_time": end_time - timedelta(seconds=5), "qty": 0.5, "is_buyer_maker": True},
        ]


def test_market_data_snapshot_persists_oi_and_cvd_history() -> None:
    now = datetime(2026, 1, 1, 0, 15, tzinfo=timezone.utc)
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn, Path("storage/schema.sql"))
    assembler = MarketDataAssembler(
        rest_client=FakeRestClient(now),  # type: ignore[arg-type]
        websocket_client=None,
        db_connection=conn,
    )

    snapshot = assembler.build_snapshot("BTCUSDT", now)

    assert snapshot.quality["flow_15m"].status == "ready"
    oi_count = conn.execute("SELECT COUNT(*) AS count FROM oi_samples").fetchone()["count"]
    cvd_count = conn.execute("SELECT COUNT(*) AS count FROM cvd_price_history").fetchone()["count"]
    assert oi_count == 1
    assert cvd_count == 1
