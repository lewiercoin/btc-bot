from __future__ import annotations

from datetime import datetime, timedelta, timezone

from core.models import Features, MarketSnapshot, RegimeState
from research_lab.evaluate_crowded_gates import evaluate_crowded_gates
from research_lab.setups.crowded_unwind import CrowdedUnwindConfig, CrowdedUnwindLong, CrowdedUnwindShort
from settings import StrategyConfig


def _features(**overrides) -> Features:
    values = dict(
        schema_version="v1.0",
        config_hash="hash",
        timestamp=datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc),
        atr_15m=100.0,
        atr_4h=400.0,
        atr_4h_norm=0.012,
        ema50_4h=100_000.0,
        ema200_4h=99_000.0,
        equal_lows=[],
        equal_highs=[],
        sweep_detected=False,
        reclaim_detected=False,
        sweep_level=None,
        sweep_depth_pct=None,
        sweep_side=None,
        funding_8h=-0.00035,
        funding_sma3=-0.00030,
        funding_sma9=-0.00025,
        funding_pct_60d=4.0,
        oi_value=1.0,
        oi_zscore_60d=2.2,
        oi_delta_pct=-0.002,
        cvd_15m=0.0,
        cvd_bullish_divergence=False,
        cvd_bearish_divergence=False,
        tfi_60s=0.25,
        force_order_rate_60s=0.05,
        force_order_spike=True,
        force_order_decreasing=False,
    )
    values.update(overrides)
    return Features(**values)


def _snapshot(*, price: float = 100_000.0) -> MarketSnapshot:
    ts = datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc)
    candles_15m = []
    base = ts - timedelta(minutes=15 * 12)
    for index in range(12):
        close = price - 80.0 + index * 10.0
        candles_15m.append(
            {
                "open_time": base + timedelta(minutes=15 * index),
                "open": close - 10.0,
                "high": close + 80.0,
                "low": close - 90.0,
                "close": close,
                "volume": 10.0,
            }
        )
    return MarketSnapshot(
        symbol="BTCUSDT",
        timestamp=ts,
        price=price,
        bid=price - 5.0,
        ask=price + 5.0,
        candles_15m=candles_15m,
        candles_4h=[],
    )


def test_crowded_unwind_long_generates_explained_candidate() -> None:
    candidate = CrowdedUnwindLong().generate_signal_candidate(
        features=_features(),
        snapshot=_snapshot(),
        regime=RegimeState.CROWDED_LEVERAGE,
        config=StrategyConfig(),
    )

    assert candidate is not None
    assert candidate.setup_type == "crowded_unwind_long"
    assert candidate.direction == "LONG"
    assert candidate.invalidation_level < candidate.entry_reference < candidate.tp_reference_1
    assert "setup_type=crowded_unwind_long" in candidate.reasons
    assert "crowded_side=shorts" in candidate.reasons
    assert "entry_timing=force_spike_unwind_starting_now" in candidate.reasons
    assert any(reason.startswith("force_order_rate_60s=") for reason in candidate.reasons)


def test_crowded_unwind_short_generates_explained_candidate() -> None:
    features = _features(
        funding_8h=0.00035,
        funding_sma3=0.00030,
        funding_sma9=0.00025,
        funding_pct_60d=96.0,
        tfi_60s=-0.25,
    )

    candidate = CrowdedUnwindShort().generate_signal_candidate(
        features=features,
        snapshot=_snapshot(),
        regime=RegimeState.CROWDED_LEVERAGE,
        config=StrategyConfig(),
    )

    assert candidate is not None
    assert candidate.setup_type == "crowded_unwind_short"
    assert candidate.direction == "SHORT"
    assert candidate.tp_reference_1 < candidate.entry_reference < candidate.invalidation_level
    assert "crowded_side=longs" in candidate.reasons


def test_crowded_unwind_blocks_wrong_regime() -> None:
    evaluation = CrowdedUnwindLong().evaluate_structure(
        features=_features(),
        snapshot=_snapshot(),
        regime=RegimeState.UPTREND,
        config=StrategyConfig(),
    )

    assert not evaluation.accepted
    assert "regime_blocked:uptrend" in evaluation.reasons


def test_crowded_unwind_requires_force_spike() -> None:
    evaluation = CrowdedUnwindLong().evaluate_structure(
        features=_features(force_order_spike=False, force_order_rate_60s=0.0),
        snapshot=_snapshot(),
        regime=RegimeState.CROWDED_LEVERAGE,
        config=StrategyConfig(),
    )

    assert not evaluation.accepted
    assert "no_force_spike" in evaluation.reasons
    assert "force_rate_below_threshold" in evaluation.reasons


def test_crowded_unwind_requires_extreme_funding() -> None:
    evaluation = CrowdedUnwindLong().evaluate_structure(
        features=_features(funding_8h=0.0, funding_pct_60d=50.0),
        snapshot=_snapshot(),
        regime=RegimeState.CROWDED_LEVERAGE,
        config=StrategyConfig(),
    )

    assert not evaluation.accepted
    assert "funding_not_extreme" in evaluation.reasons
    assert "funding_already_normalized" in evaluation.reasons


def test_crowded_unwind_requires_elevated_oi() -> None:
    evaluation = CrowdedUnwindShort().evaluate_structure(
        features=_features(funding_8h=0.00035, funding_pct_60d=96.0, tfi_60s=-0.25, oi_zscore_60d=0.2),
        snapshot=_snapshot(),
        regime=RegimeState.CROWDED_LEVERAGE,
        config=StrategyConfig(),
    )

    assert not evaluation.accepted
    assert "oi_not_elevated" in evaluation.reasons


def test_crowded_unwind_blocks_volatility_panic() -> None:
    setup = CrowdedUnwindLong(CrowdedUnwindConfig(volatility_panic_atr_norm=0.02))

    evaluation = setup.evaluate_structure(
        features=_features(atr_4h_norm=0.03),
        snapshot=_snapshot(),
        regime=RegimeState.CROWDED_LEVERAGE,
        config=StrategyConfig(),
    )

    assert not evaluation.accepted
    assert "volatility_panic" in evaluation.reasons


def test_crowded_unwind_not_absorption_or_compression_retry() -> None:
    candidate = CrowdedUnwindLong().generate_signal_candidate(
        features=_features(cvd_bullish_divergence=False, cvd_bearish_divergence=False),
        snapshot=_snapshot(),
        regime=RegimeState.CROWDED_LEVERAGE,
        config=StrategyConfig(),
    )

    assert candidate is not None
    joined_reasons = " ".join(candidate.reasons)
    assert "cvd" not in joined_reasons.lower()
    assert "compression" not in joined_reasons.lower()


def test_gate_evaluator_blocks_missing_crowded_validation() -> None:
    report = {
        "performance": {"trades_count": 0, "profit_factor": None, "expectancy_r": None, "win_rate": None},
        "per_regime": {},
        "decision_summary": {"liquidation_capture_rate": None},
        "signals": [],
    }

    result = evaluate_crowded_gates(report)

    assert result["verdict"] == "ITERATE"
    failed = {gate["name"] for gate in result["gates"] if not gate["passed"]}
    assert "crowded_leverage_er" in failed
    assert "liquidation_capture" in failed
    assert "overlap_control" in failed
    assert "walkforward" in failed
    assert result["red_flags"][0]["flag"] == "no_trades"


def test_gate_evaluator_rejects_failed_liquidation_capture() -> None:
    report = {
        "performance": {"trades_count": 25, "profit_factor": 0.8, "expectancy_r": 0.2, "win_rate": 0.32},
        "per_regime": {"crowded_leverage": {"expectancy_r": 0.2, "trades_count": 20}},
        "decision_summary": {"liquidation_capture_rate": 0.25},
        "signals": [{"candidate_reasons": ["setup_type=crowded_unwind_short"]}],
    }

    result = evaluate_crowded_gates(report, overlap_rate=0.1, walkforward_passed_windows=2)

    assert result["verdict"] == "REJECT"
    flags = {flag["flag"] for flag in result["red_flags"]}
    assert "crowded_leverage_er_below_edge_threshold" in flags
    assert "liquidation_capture_not_predictive" in flags
