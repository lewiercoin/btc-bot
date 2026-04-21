from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import sqlite3
from pathlib import Path

from core.models import FeatureQuality, Features
from dashboard.db_reader import read_feature_quality_from_conn
from storage.db import init_db
from storage.repositories import upsert_runtime_metrics


def test_features_accept_structured_quality_states_without_required_callsite_changes() -> None:
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    features = Features(
        schema_version="v1.0",
        config_hash="hash",
        timestamp=now,
        atr_15m=1.0,
        atr_4h=4.0,
        atr_4h_norm=0.01,
        ema50_4h=100.0,
        ema200_4h=99.0,
    )

    assert features.quality == {}


def test_feature_quality_serializes_as_plain_diagnostic_payload() -> None:
    quality = FeatureQuality.unavailable(
        reason="cold_start",
        metadata={"required_samples": 30, "loaded_samples": 0},
        provenance="bootstrapped-from-db",
    )

    assert asdict(quality) == {
        "status": "unavailable",
        "reason": "cold_start",
        "metadata": {"required_samples": 30, "loaded_samples": 0},
        "provenance": "bootstrapped-from-db",
    }


def test_feature_quality_visibility_reads_latest_runtime_payload() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn, Path("storage/schema.sql"))
    upsert_runtime_metrics(
        conn,
        config_hash="hash",
        feature_quality_json='{"oi_baseline": {"status": "ready"}}',
    )

    payload = read_feature_quality_from_conn(conn)

    assert payload["config_hash"] == "hash"
    assert payload["quality"]["oi_baseline"]["status"] == "ready"
