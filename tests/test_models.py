from __future__ import annotations

from datetime import datetime, timezone

from core.models import MarketSnapshot, RegimeState, SignalCandidate


def test_market_snapshot_defaults_are_independent() -> None:
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    a = MarketSnapshot(symbol="BTCUSDT", timestamp=now, price=100.0, bid=99.5, ask=100.5)
    b = MarketSnapshot(symbol="BTCUSDT", timestamp=now, price=100.0, bid=99.5, ask=100.5)

    a.candles_15m.append({"open_time": now, "open": 99.0, "high": 101.0, "low": 98.0, "close": 100.0, "volume": 1.0})

    assert len(a.candles_15m) == 1
    assert b.candles_15m == []


def test_signal_candidate_defaults_for_optional_fields() -> None:
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    candidate = SignalCandidate(
        signal_id="sig-1",
        timestamp=now,
        direction="LONG",
        setup_type="unit-test",
        entry_reference=100.0,
        invalidation_level=95.0,
        tp_reference_1=105.0,
        tp_reference_2=110.0,
        confluence_score=3.5,
        regime=RegimeState.NORMAL,
    )

    assert candidate.reasons == []
    assert candidate.features_json == {}
    assert candidate.regime is RegimeState.NORMAL


def test_regime_state_values_are_stable() -> None:
    assert RegimeState.NORMAL.value == "normal"
    assert RegimeState.UPTREND.value == "uptrend"
    assert RegimeState.DOWNTREND.value == "downtrend"
    assert RegimeState.COMPRESSION.value == "compression"
    assert RegimeState.CROWDED_LEVERAGE.value == "crowded_leverage"
    assert RegimeState.POST_LIQUIDATION.value == "post_liquidation"
