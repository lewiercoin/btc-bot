from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.feature_engine import FeatureEngine, FeatureEngineConfig
from core.models import MarketSnapshot


def main() -> None:
    now = datetime(2026, 1, 1, 0, 15, tzinfo=timezone.utc)
    engine = FeatureEngine(
        FeatureEngineConfig(
            oi_baseline_days=1,
            oi_z_window_days=1,
            cvd_divergence_bars=3,
            cvd_divergence_window_bars=3,
            funding_window_days=1,
        )
    )
    engine.bootstrap_oi_history(
        [
            {"timestamp": now - timedelta(days=1), "oi_value": 100.0},
            {"timestamp": now - timedelta(hours=12), "oi_value": 110.0},
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
            funding_history=[
                {"funding_time": now - timedelta(hours=16), "funding_rate": 0.0001},
                {"funding_time": now - timedelta(hours=8), "funding_rate": 0.0002},
                {"funding_time": now, "funding_rate": 0.0003},
            ],
        ),
        "v1.0",
        "smoke",
    )

    required = {"oi_baseline", "cvd_divergence", "funding_window", "flow_15m", "flow_60s"}
    missing = required - set(features.quality)
    if missing:
        raise RuntimeError(f"Missing feature quality keys: {sorted(missing)}")
    unavailable = {
        key: value.reason
        for key, value in features.quality.items()
        if value.status == "unavailable" and key in {"oi_baseline", "cvd_divergence", "funding_window"}
    }
    if unavailable:
        raise RuntimeError(f"Unexpected unavailable quality states: {unavailable}")
    print("feature engine smoke: OK")


if __name__ == "__main__":
    main()
