from __future__ import annotations

from datetime import datetime, timedelta, timezone

from core.models import Features, MarketSnapshot, RegimeState
from research_lab.setups.absorption_continuation import (
    AbsorptionContinuationConfig,
    AbsorptionContinuationLong,
)
from research_lab.analyze_setup_overlap import calculate_overlap
from research_lab.analyze_trend_day_capture import calculate_trend_day_capture
from research_lab.evaluate_absorption_gates import evaluate_absorption_gates
from settings import StrategyConfig


def _features(**overrides) -> Features:
    values = dict(
        schema_version="v1.0",
        config_hash="hash",
        timestamp=datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc),
        atr_15m=100.0,
        atr_4h=400.0,
        atr_4h_norm=0.003,
        ema50_4h=100_100.0,
        ema200_4h=97_000.0,
        equal_lows=[100_050.0],
        equal_highs=[],
        sweep_detected=False,
        reclaim_detected=False,
        sweep_level=None,
        sweep_depth_pct=None,
        sweep_side=None,
        funding_8h=0.0001,
        funding_sma3=0.0001,
        funding_sma9=0.0001,
        funding_pct_60d=55.0,
        oi_value=1.0,
        oi_zscore_60d=0.5,
        oi_delta_pct=0.001,
        cvd_15m=25.0,
        cvd_bullish_divergence=True,
        cvd_bearish_divergence=False,
        tfi_60s=0.42,
        force_order_rate_60s=0.0,
        force_order_spike=False,
        force_order_decreasing=False,
    )
    values.update(overrides)
    return Features(**values)


def _snapshot(*, price: float = 100_200.0) -> MarketSnapshot:
    ts = datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc)
    candles_15m = []
    base = ts - timedelta(minutes=15 * 31)
    for index in range(32):
        high = 101_400.0 - max(index - 8, 0) * 35.0
        low = 100_050.0 + min(index, 12) * 8.0
        close = price if index == 31 else max(low + 80.0, high - 220.0)
        candles_15m.append(
            {
                "open_time": base + timedelta(minutes=15 * index),
                "open": close - 20.0,
                "high": high,
                "low": low,
                "close": close,
                "volume": 10.0,
            }
        )
    candles_4h = [
        {"open_time": ts - timedelta(hours=12), "open": 96_200.0, "high": 97_000.0, "low": 96_000.0, "close": 96_600.0},
        {"open_time": ts - timedelta(hours=8), "open": 96_600.0, "high": 97_400.0, "low": 96_500.0, "close": 97_100.0},
        {"open_time": ts - timedelta(hours=4), "open": 97_100.0, "high": 98_000.0, "low": 97_000.0, "close": 97_800.0},
        {"open_time": ts, "open": 97_800.0, "high": 100_300.0, "low": 97_600.0, "close": price},
    ]
    return MarketSnapshot(
        symbol="BTCUSDT",
        timestamp=ts,
        price=price,
        bid=price - 5.0,
        ask=price + 5.0,
        candles_15m=candles_15m,
        candles_4h=candles_4h,
    )


def test_absorption_continuation_generates_explained_long_candidate() -> None:
    setup = AbsorptionContinuationLong()
    features = _features()
    snapshot = _snapshot()

    candidate = setup.generate_signal_candidate(
        features=features,
        snapshot=snapshot,
        regime=RegimeState.UPTREND,
        config=StrategyConfig(),
    )

    assert candidate is not None
    assert candidate.setup_type == "absorption_continuation_long"
    assert candidate.direction == "LONG"
    assert candidate.regime is RegimeState.UPTREND
    assert candidate.invalidation_level < candidate.entry_reference < candidate.tp_reference_1
    assert "setup_type=absorption_continuation_long" in candidate.reasons
    assert any(reason.startswith("pullback_depth_pct=") for reason in candidate.reasons)
    assert any(reason.startswith("rr_ratio=") for reason in candidate.reasons)
    assert any(reason.startswith("cvd_slope_pullback_window=") for reason in candidate.reasons)
    assert any(reason.startswith("volatility_panic_threshold=") for reason in candidate.reasons)
    assert "entry_timing=pullback_absorption_before_breakout_confirmation" in candidate.reasons


def test_absorption_continuation_blocks_retail_ema_pullback_without_absorption() -> None:
    setup = AbsorptionContinuationLong()
    features = _features(cvd_15m=-10.0, cvd_bullish_divergence=False, tfi_60s=0.05)

    evaluation = setup.evaluate_structure(
        features=features,
        snapshot=_snapshot(),
        regime=RegimeState.UPTREND,
        config=StrategyConfig(),
    )

    assert not evaluation.accepted
    assert "absorption_not_confirmed" in evaluation.reasons
    assert "tfi_below_absorption_threshold" in evaluation.reasons


def test_absorption_continuation_uses_pullback_window_cvd_history() -> None:
    setup = AbsorptionContinuationLong()
    snapshot = _snapshot()
    snapshot.source_meta["research_cvd_price_history"] = [
        {"price": 101_000.0, "cvd": 120.0},
        {"price": 100_800.0, "cvd": 90.0},
        {"price": 100_500.0, "cvd": 60.0},
        {"price": 100_200.0, "cvd": 30.0},
    ]
    features = _features(cvd_15m=30.0, cvd_bullish_divergence=True)

    evaluation = setup.evaluate_structure(
        features=features,
        snapshot=snapshot,
        regime=RegimeState.UPTREND,
        config=StrategyConfig(),
    )

    assert not evaluation.accepted
    assert "absorption_not_confirmed" in evaluation.reasons
    assert evaluation.metrics["cvd_slope_pullback_window"] < 0


def test_absorption_continuation_blocks_wrong_regime_and_crowded_leverage() -> None:
    setup = AbsorptionContinuationLong()
    features = _features(funding_8h=0.0012, oi_zscore_60d=3.0)

    evaluation = setup.evaluate_structure(
        features=features,
        snapshot=_snapshot(),
        regime=RegimeState.CROWDED_LEVERAGE,
        config=StrategyConfig(),
    )

    assert not evaluation.accepted
    assert "regime_blocked:crowded_leverage" in evaluation.reasons
    assert "funding_crowded_long" in evaluation.reasons
    assert "oi_crowded" in evaluation.reasons


def test_absorption_continuation_rejects_broken_structure() -> None:
    setup = AbsorptionContinuationLong()
    snapshot = _snapshot(price=99_600.0)
    features = _features(ema50_4h=100_100.0, ema200_4h=97_000.0)

    evaluation = setup.evaluate_structure(
        features=features,
        snapshot=snapshot,
        regime=RegimeState.UPTREND,
        config=StrategyConfig(),
    )

    assert not evaluation.accepted
    assert "higher_low_structure_broken" in evaluation.reasons


def test_absorption_continuation_blocks_panic_liquidation_context() -> None:
    setup = AbsorptionContinuationLong(
        AbsorptionContinuationConfig(liquidation_rate_threshold=0.5)
    )
    features = _features(
        atr_4h_norm=0.012,
        force_order_spike=True,
        force_order_rate_60s=0.8,
    )

    evaluation = setup.evaluate_structure(
        features=features,
        snapshot=_snapshot(),
        regime=RegimeState.UPTREND,
        config=StrategyConfig(),
    )

    assert not evaluation.accepted
    assert "volatility_panic" in evaluation.reasons
    assert "liquidation_cascade_active" in evaluation.reasons


def test_overlap_analysis_uses_strict_portfolio_thresholds() -> None:
    absorption = [
        {"timestamp": "2026-05-11T10:00:00+00:00"},
        {"timestamp": "2026-05-11T11:00:00+00:00"},
        {"timestamp": "2026-05-11T12:00:00+00:00"},
    ]
    sweep = [
        {"timestamp": "2026-05-11T10:10:00+00:00"},
        {"timestamp": "2026-05-11T13:00:00+00:00"},
    ]

    result = calculate_overlap(absorption, sweep, tolerance_minutes=15)

    assert result["overlap_count"] == 1
    assert result["overlap_rate"] == 0.25
    assert result["verdict"] == "PASS_ACCEPTABLE_WITH_COMMENT"


def test_trend_day_capture_marks_low_capture_as_iteration_or_reject() -> None:
    signals = [{"timestamp": "2026-05-11T10:00:00+00:00"}]
    trend_days = ["2026-05-10", "2026-05-11", "2026-05-12"]

    result = calculate_trend_day_capture(signals, trend_days)

    assert result["trend_days_total"] == 3
    assert result["trend_days_captured"] == 1
    assert result["missed_days"] == ["2026-05-10", "2026-05-12"]
    assert result["verdict"] == "ITERATE_LOW_CAPTURE"


def test_gate_evaluator_blocks_missing_validation_evidence() -> None:
    report = {
        "performance": {"trades_count": 0},
        "per_regime": {},
        "decision_summary": {"absorption_confirmation_hit_rate": None},
        "signals": [],
    }

    result = evaluate_absorption_gates(report)

    assert result["verdict"] == "ITERATE"
    failed = {gate["name"] for gate in result["gates"] if not gate["passed"]}
    assert "uptrend_er" in failed
    assert "trend_day_capture" in failed
    assert "overlap_control" in failed
    assert "walkforward" in failed
    assert result["red_flags"][0]["flag"] == "no_trades"


def test_gate_evaluator_rejects_high_overlap_even_with_other_evidence() -> None:
    report = {
        "performance": {"trades_count": 25},
        "per_regime": {
            "uptrend": {"expectancy_r": 1.8, "trades_count": 25},
            "range": {"expectancy_r": -0.2, "trades_count": 3},
        },
        "decision_summary": {"absorption_confirmation_hit_rate": 0.57},
        "signals": [{"candidate_reasons": ["setup_type=absorption_continuation_long"]}],
    }

    result = evaluate_absorption_gates(
        report,
        sweep_uptrend_trades=0,
        overlap_rate=0.55,
        trend_day_capture_rate=0.60,
        walkforward_passed_windows=2,
    )

    assert result["verdict"] == "REJECT"
    assert any(flag["flag"] == "high_overlap_with_sweep_reclaim" for flag in result["red_flags"])
