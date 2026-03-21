from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.feature_engine import FeatureEngine
from core.governance import GovernanceLayer
from core.models import MarketSnapshot
from core.regime_engine import RegimeEngine
from core.risk_engine import RiskEngine
from core.signal_engine import SignalEngine


def _make_candles(start: datetime, step_minutes: int, count: int, base: float) -> list[dict]:
    candles: list[dict] = []
    price = base
    for i in range(count):
        ts = start + timedelta(minutes=i * step_minutes)
        open_price = price
        close_price = price + 8.0
        high_price = max(open_price, close_price) + 5.0
        low_price = min(open_price, close_price) - 5.0
        candles.append(
            {
                "open_time": ts,
                "open": open_price,
                "high": high_price,
                "low": low_price,
                "close": close_price,
                "volume": 100 + i,
            }
        )
        price = close_price
    return candles


def build_snapshot() -> MarketSnapshot:
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    candles_15m = _make_candles(now - timedelta(minutes=15 * 80), 15, 80, 80000.0)
    candles_1h = _make_candles(now - timedelta(hours=120), 60, 120, 79000.0)
    candles_4h = _make_candles(now - timedelta(hours=4 * 220), 240, 220, 76000.0)

    # Inject equal-lows sweep + reclaim pattern on the latest 15m candle.
    sweep_level = min(c["low"] for c in candles_15m[-20:-2])
    latest = candles_15m[-1]
    latest["open"] = sweep_level + 30
    latest["high"] = sweep_level + 70
    latest["low"] = sweep_level - 60
    latest["close"] = sweep_level + 45

    funding = []
    for i in range(90):
        funding.append(
            {
                "funding_time": now - timedelta(hours=8 * (90 - i)),
                "funding_rate": -0.0002 + (i / 1_000_000),
            }
        )

    return MarketSnapshot(
        symbol="BTCUSDT",
        timestamp=now,
        price=latest["close"],
        bid=latest["close"] - 1,
        ask=latest["close"] + 1,
        candles_15m=candles_15m,
        candles_1h=candles_1h,
        candles_4h=candles_4h,
        funding_history=funding,
        open_interest=2_100_000.0,
        aggtrades_bucket_60s={"tfi": 0.23, "cvd": 180.0},
        aggtrades_bucket_15m={"tfi": 0.15, "cvd": 620.0},
        force_order_events_60s=[{"event_time": now - timedelta(seconds=10)} for _ in range(6)],
        etf_bias_daily=0.1,
        dxy_daily=103.2,
    )


def main() -> None:
    snapshot = build_snapshot()
    feature_engine = FeatureEngine()
    regime_engine = RegimeEngine()
    signal_engine = SignalEngine()
    governance = GovernanceLayer()
    risk = RiskEngine()

    features = feature_engine.compute(snapshot=snapshot, schema_version="v1.0", config_hash="dev")
    regime = regime_engine.classify(features)
    candidate = signal_engine.generate(features, regime)

    print("features:", features)
    print("regime:", regime.value)
    print("candidate:", candidate)

    if candidate is None:
        print("No candidate produced.")
        return

    decision = governance.evaluate(candidate)
    print("governance_decision:", decision)
    if not decision.approved:
        print("Rejected by governance.")
        return

    executable = governance.to_executable(candidate, decision)
    risk_decision = risk.evaluate(executable, equity=10_000.0, open_positions=0)
    print("executable:", executable)
    print("risk_decision:", risk_decision)


if __name__ == "__main__":
    main()
