from __future__ import annotations

from datetime import datetime, timedelta, timezone

from core.models import Features, MarketSnapshot, RegimeState
from research_lab.evaluate_volatility_gates import evaluate_gates
from research_lab.setups.volatility_breakout import (
    VolatilityBreakoutConfig,
    VolatilityBreakoutLong,
    VolatilityBreakoutShort,
    detect_expansion_state,
)


def test_detect_expansion_state_uses_slope_not_low_atr_level() -> None:
    history = [0.010] * 6 + [0.0105, 0.011, 0.0115, 0.012, 0.0125, 0.013]

    result = detect_expansion_state(history, lookback_bars=6, min_slope_pct=0.10, min_samples=12)

    assert result["expansion_state"] is True
    assert result["atr_slope_pct"] > 0.10


def test_detect_expansion_state_rejects_flat_atr() -> None:
    history = [0.010] * 12

    result = detect_expansion_state(history, lookback_bars=6, min_slope_pct=0.10, min_samples=12)

    assert result["expansion_state"] is False
    assert result["reason"] == "atr_not_rising"


def test_long_candidate_requires_expansion_and_upward_breakout() -> None:
    setup = VolatilityBreakoutLong(VolatilityBreakoutConfig(min_atr_slope_pct=0.05))
    snapshot = _snapshot(price=104.0, tfi=0.12)
    features = _features(price=104.0, atr_15m=2.0, atr_4h_norm=0.013, tfi=0.12, ema50=100.0)

    candidate = setup.generate_signal_candidate(
        snapshot=snapshot,
        features=features,
        regime=RegimeState.NORMAL,
    )

    assert candidate is not None
    assert candidate.direction == "LONG"
    assert candidate.setup_type == "volatility_breakout_long"
    assert candidate.features_json["expansion_state"] is True
    assert candidate.features_json["compression_entry"] is False
    assert any("not_compression_breakout_2_0=True" in reason for reason in candidate.reasons)


def test_short_candidate_requires_expansion_and_downward_breakout() -> None:
    setup = VolatilityBreakoutShort(VolatilityBreakoutConfig(min_atr_slope_pct=0.05))
    snapshot = _snapshot(price=96.0, tfi=-0.12)
    features = _features(price=96.0, atr_15m=2.0, atr_4h_norm=0.013, tfi=-0.12, ema50=100.0)

    candidate = setup.generate_signal_candidate(
        snapshot=snapshot,
        features=features,
        regime=RegimeState.NORMAL,
    )

    assert candidate is not None
    assert candidate.direction == "SHORT"
    assert candidate.setup_type == "volatility_breakout_short"
    assert candidate.features_json["expansion_state"] is True


def test_compression_regime_is_blocked_even_if_breakout_exists() -> None:
    setup = VolatilityBreakoutLong(VolatilityBreakoutConfig(min_atr_slope_pct=0.05))
    snapshot = _snapshot(price=104.0, tfi=0.12)
    features = _features(price=104.0, atr_15m=2.0, atr_4h_norm=0.013, tfi=0.12, ema50=100.0)

    evaluation = setup.evaluate_structure(
        snapshot=snapshot,
        features=features,
        regime=RegimeState.COMPRESSION,
    )

    assert evaluation.accepted is False
    assert "regime_blocked:compression" in evaluation.reasons
    assert "compression_entry_timing_violation" in evaluation.reasons


def test_long_rejects_without_structure_breakout() -> None:
    setup = VolatilityBreakoutLong(VolatilityBreakoutConfig(min_atr_slope_pct=0.05))
    snapshot = _snapshot(price=101.0, tfi=0.12)
    features = _features(price=101.0, atr_15m=2.0, atr_4h_norm=0.013, tfi=0.12, ema50=100.0)

    evaluation = setup.evaluate_structure(
        snapshot=snapshot,
        features=features,
        regime=RegimeState.NORMAL,
    )

    assert evaluation.accepted is False
    assert "breakout_too_small" in evaluation.reasons


def test_long_rejects_opposing_tfi() -> None:
    setup = VolatilityBreakoutLong(VolatilityBreakoutConfig(min_atr_slope_pct=0.05))
    snapshot = _snapshot(price=104.0, tfi=-0.12)
    features = _features(price=104.0, atr_15m=2.0, atr_4h_norm=0.013, tfi=-0.12, ema50=100.0)

    evaluation = setup.evaluate_structure(
        snapshot=snapshot,
        features=features,
        regime=RegimeState.NORMAL,
    )

    assert evaluation.accepted is False
    assert "tfi_not_aligned" in evaluation.reasons


def test_gate_evaluator_flags_timing_violation() -> None:
    report = {
        "performance": {"trades_count": 25, "expectancy_r": 1.2},
        "decision_summary": {
            "expansion_continuation_rate": 0.55,
            "expansion_entry_rate": 0.40,
        },
        "closed_trades": [{"reasons": ["a"]} for _ in range(25)],
    }

    result = evaluate_gates(report)

    assert result["verdict"] == "TIMING_VIOLATION"


def test_gate_evaluator_accepts_all_hard_gates() -> None:
    report = {
        "performance": {"trades_count": 25, "expectancy_r": 1.6},
        "decision_summary": {
            "expansion_continuation_rate": 0.62,
            "expansion_entry_rate": 0.85,
        },
        "closed_trades": [{"reasons": ["a"]} for _ in range(25)],
    }

    result = evaluate_gates(report)

    assert result["verdict"] == "CANDIDATE_FOR_PHASE_2_5"


def _snapshot(*, price: float, tfi: float) -> MarketSnapshot:
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    candles = []
    for index in range(13):
        open_time = now - timedelta(minutes=15 * (13 - index))
        candles.append(
            {
                "open_time": open_time,
                "open": 100.0,
                "high": 102.0,
                "low": 98.0,
                "close": 100.0,
                "volume": 1.0,
            }
        )
    candles[-1]["close"] = price
    candles[-1]["high"] = max(price, candles[-1]["high"])
    candles[-1]["low"] = min(price, candles[-1]["low"])
    atr_history = [0.010] * 6 + [0.0105, 0.011, 0.0115, 0.012, 0.0125, 0.013]
    return MarketSnapshot(
        symbol="BTCUSDT",
        timestamp=now,
        price=price,
        bid=price,
        ask=price,
        candles_15m=candles,
        source_meta={"research_atr_4h_norm_history": atr_history},
        aggtrades_bucket_60s={"tfi": tfi},
    )


def _features(*, price: float, atr_15m: float, atr_4h_norm: float, tfi: float, ema50: float) -> Features:
    del price
    return Features(
        schema_version="test",
        config_hash="test",
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        atr_15m=atr_15m,
        atr_4h=atr_4h_norm * ema50,
        atr_4h_norm=atr_4h_norm,
        ema50_4h=ema50,
        ema200_4h=ema50 * 0.95,
        tfi_60s=tfi,
    )
