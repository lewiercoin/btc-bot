from __future__ import annotations

from datetime import datetime, timedelta, timezone

from core.models import Features, MarketSnapshot, RegimeState
from research_lab.evaluate_regime_gates import evaluate_gates
from research_lab.setups.regime_reversal import (
    RegimeReversalConfig,
    RegimeReversalLong,
    RegimeReversalShort,
    detect_regime_transition,
)


def test_detect_regime_transition_long_after_downtrend_exhaustion() -> None:
    result = detect_regime_transition(
        [RegimeState.DOWNTREND, RegimeState.DOWNTREND, RegimeState.NORMAL, RegimeState.NORMAL],
        max_entry_delay_cycles=12,
        min_persistence_cycles=2,
    )

    assert result["transition_active"] is True
    assert result["direction"] == "LONG"
    assert result["cycles_since_transition"] == 1


def test_detect_regime_transition_short_after_uptrend_exhaustion() -> None:
    result = detect_regime_transition(
        [RegimeState.UPTREND, RegimeState.UPTREND, RegimeState.DOWNTREND, RegimeState.DOWNTREND],
        max_entry_delay_cycles=12,
        min_persistence_cycles=2,
    )

    assert result["transition_active"] is True
    assert result["direction"] == "SHORT"
    assert result["reason"] == "uptrend_exhaustion_confirmed"


def test_detect_regime_transition_rejects_one_cycle_flip() -> None:
    result = detect_regime_transition(
        [RegimeState.UPTREND, RegimeState.UPTREND, RegimeState.DOWNTREND],
        max_entry_delay_cycles=12,
        min_persistence_cycles=2,
    )

    assert result["transition_active"] is False
    assert result["reason"] == "current_regime_not_persistent"


def test_detect_regime_transition_rejects_stale_transition() -> None:
    result = detect_regime_transition(
        [RegimeState.DOWNTREND] * 4 + [RegimeState.NORMAL] * 14,
        max_entry_delay_cycles=12,
        min_persistence_cycles=2,
    )

    assert result["transition_active"] is False
    assert result["reason"] == "transition_window_closed"


def test_long_candidate_after_confirmed_downtrend_to_normal_shift() -> None:
    setup = RegimeReversalLong(RegimeReversalConfig())
    snapshot = _snapshot(
        price=103.0,
        regime_history=[RegimeState.DOWNTREND, RegimeState.DOWNTREND, RegimeState.NORMAL, RegimeState.NORMAL],
    )
    features = _features(price=103.0, tfi=0.12, ema50=100.0)

    candidate = setup.generate_signal_candidate(snapshot=snapshot, features=features, regime=RegimeState.NORMAL)

    assert candidate is not None
    assert candidate.direction == "LONG"
    assert candidate.setup_type == "regime_reversal_long"
    assert candidate.features_json["cycles_since_transition"] == 1
    assert any("not_top_bottom_anticipation=True" in reason for reason in candidate.reasons)


def test_short_candidate_after_confirmed_uptrend_to_downtrend_shift() -> None:
    setup = RegimeReversalShort(RegimeReversalConfig())
    snapshot = _snapshot(
        price=97.0,
        regime_history=[RegimeState.UPTREND, RegimeState.UPTREND, RegimeState.DOWNTREND, RegimeState.DOWNTREND],
    )
    features = _features(price=97.0, tfi=-0.12, ema50=100.0)

    candidate = setup.generate_signal_candidate(snapshot=snapshot, features=features, regime=RegimeState.DOWNTREND)

    assert candidate is not None
    assert candidate.direction == "SHORT"
    assert candidate.setup_type == "regime_reversal_short"


def test_setup_rejects_blocked_regime() -> None:
    setup = RegimeReversalLong(RegimeReversalConfig())
    snapshot = _snapshot(
        price=103.0,
        regime_history=[RegimeState.DOWNTREND, RegimeState.DOWNTREND, RegimeState.COMPRESSION, RegimeState.COMPRESSION],
    )
    features = _features(price=103.0, tfi=0.12, ema50=100.0)

    evaluation = setup.evaluate_structure(snapshot=snapshot, features=features, regime=RegimeState.COMPRESSION)

    assert evaluation.accepted is False
    assert "regime_blocked:compression" in evaluation.reasons


def test_gate_evaluator_flags_entry_delay_timing_violation() -> None:
    report = {
        "performance": {"trades_count": 25, "expectancy_r": 1.2},
        "decision_summary": {
            "false_reversal_rate": 0.20,
            "whipsaw_rate": 0.10,
            "avg_entry_delay_cycles": 7.2,
            "transition_entry_rate": 0.90,
        },
        "closed_trades": [{"reasons": ["a"]} for _ in range(25)],
    }

    result = evaluate_gates(report)

    assert result["verdict"] == "TIMING_VIOLATION_15M_LATENCY"


def test_gate_evaluator_candidate_ready_when_all_pass() -> None:
    report = {
        "performance": {"trades_count": 25, "expectancy_r": 1.8},
        "decision_summary": {
            "false_reversal_rate": 0.20,
            "whipsaw_rate": 0.10,
            "avg_entry_delay_cycles": 2.0,
            "transition_entry_rate": 0.90,
        },
        "closed_trades": [{"reasons": ["a"]} for _ in range(25)],
    }

    result = evaluate_gates(report)

    assert result["verdict"] == "CANDIDATE_READY"


def _snapshot(*, price: float, regime_history: list[RegimeState]) -> MarketSnapshot:
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
    return MarketSnapshot(
        symbol="BTCUSDT",
        timestamp=now,
        price=price,
        bid=price,
        ask=price,
        candles_15m=candles,
        source_meta={"research_regime_history": [regime.value for regime in regime_history]},
    )


def _features(*, price: float, tfi: float, ema50: float) -> Features:
    del price
    return Features(
        schema_version="test",
        config_hash="test",
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        atr_15m=2.0,
        atr_4h=20.0,
        atr_4h_norm=0.01,
        ema50_4h=ema50,
        ema200_4h=ema50 * 0.99,
        tfi_60s=tfi,
    )
