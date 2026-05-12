from __future__ import annotations

from datetime import datetime, timedelta, timezone

from core.models import Features, MarketSnapshot, RegimeState
from research_lab.evaluate_compression_gates import evaluate_compression_gates
from research_lab.setups.compression_breakout import CompressionBreakoutConfig, CompressionBreakoutLong
from settings import StrategyConfig


def _features(**overrides) -> Features:
    values = dict(
        schema_version="v1.0",
        config_hash="hash",
        timestamp=datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc),
        atr_15m=100.0,
        atr_4h=400.0,
        atr_4h_norm=0.002,
        ema50_4h=100_000.0,
        ema200_4h=98_000.0,
        equal_lows=[],
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
        oi_delta_pct=0.0015,
        cvd_15m=0.0,
        cvd_bullish_divergence=False,
        cvd_bearish_divergence=False,
        tfi_60s=0.55,
        force_order_rate_60s=0.0,
        force_order_spike=False,
        force_order_decreasing=False,
    )
    values.update(overrides)
    return Features(**values)


def _snapshot(*, price: float = 100_260.0) -> MarketSnapshot:
    ts = datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc)
    candles_15m = []
    base = ts - timedelta(minutes=15 * 96)
    for index in range(96):
        center = 99_900.0 + (index % 6) * 8.0
        candles_15m.append(
            {
                "open_time": base + timedelta(minutes=15 * index),
                "open": center - 10.0,
                "high": min(100_100.0, center + 90.0),
                "low": max(99_700.0, center - 90.0),
                "close": center,
                "volume": 10.0,
            }
        )
    candles_15m.append(
        {
            "open_time": ts,
            "open": 100_090.0,
            "high": price + 20.0,
            "low": 100_050.0,
            "close": price,
            "volume": 35.0,
        }
    )
    snapshot = MarketSnapshot(
        symbol="BTCUSDT",
        timestamp=ts,
        price=price,
        bid=price - 5.0,
        ask=price + 5.0,
        candles_15m=candles_15m,
        candles_4h=[],
    )
    snapshot.source_meta["research_atr_4h_norm_history"] = [0.012] * 100 + [0.002] * 15
    return snapshot


def test_compression_breakout_generates_explained_long_candidate() -> None:
    setup = CompressionBreakoutLong()
    features = _features()
    snapshot = _snapshot()

    candidate = setup.generate_signal_candidate(
        features=features,
        snapshot=snapshot,
        regime=RegimeState.COMPRESSION,
        config=StrategyConfig(),
    )

    assert candidate is not None
    assert candidate.setup_type == "compression_breakout_long"
    assert candidate.direction == "LONG"
    assert candidate.regime is RegimeState.COMPRESSION
    assert candidate.invalidation_level < candidate.entry_reference < candidate.tp_reference_1
    assert "setup_type=compression_breakout_long" in candidate.reasons
    assert "regime_veto=allowed" in candidate.reasons
    assert "internal_compression_detected=True" in candidate.reasons
    assert any(reason.startswith("atr_percentile=") for reason in candidate.reasons)
    assert any(reason.startswith("breakout_size_atr=") for reason in candidate.reasons)
    assert "entry_timing=breakout_confirmation_before_retail_extension" in candidate.reasons


def test_compression_breakout_blocks_wrong_regime_and_absorption_retry() -> None:
    setup = CompressionBreakoutLong()

    evaluation = setup.evaluate_structure(
        features=_features(),
        snapshot=_snapshot(),
        regime=RegimeState.UPTREND,
        config=StrategyConfig(),
    )

    assert not evaluation.accepted
    assert "regime_blocked:uptrend" in evaluation.reasons


def test_compression_breakout_accepts_normal_when_internally_compressed() -> None:
    setup = CompressionBreakoutLong()

    candidate = setup.generate_signal_candidate(
        features=_features(),
        snapshot=_snapshot(),
        regime=RegimeState.NORMAL,
        config=StrategyConfig(),
    )

    assert candidate is not None
    assert candidate.regime is RegimeState.NORMAL
    assert "internal_compression_detected=True" in candidate.reasons


def test_compression_breakout_requires_objective_compression_history() -> None:
    setup = CompressionBreakoutLong()
    snapshot = _snapshot()
    snapshot.source_meta["research_atr_4h_norm_history"] = [0.010] * 20

    evaluation = setup.evaluate_structure(
        features=_features(),
        snapshot=snapshot,
        regime=RegimeState.COMPRESSION,
        config=StrategyConfig(),
    )

    assert not evaluation.accepted
    assert "atr_history_insufficient" in evaluation.reasons


def test_compression_breakout_rejects_no_breakout() -> None:
    setup = CompressionBreakoutLong()

    evaluation = setup.evaluate_structure(
        features=_features(),
        snapshot=_snapshot(price=100_020.0),
        regime=RegimeState.COMPRESSION,
        config=StrategyConfig(),
    )

    assert not evaluation.accepted
    assert "no_breakout_detected" in evaluation.reasons


def test_compression_breakout_blocks_crowded_or_panic_context() -> None:
    setup = CompressionBreakoutLong(
        CompressionBreakoutConfig(liquidation_rate_threshold=0.5)
    )
    features = _features(
        funding_8h=0.0012,
        oi_zscore_60d=3.0,
        atr_4h_norm=0.04,
        force_order_spike=True,
        force_order_rate_60s=0.8,
    )

    evaluation = setup.evaluate_structure(
        features=features,
        snapshot=_snapshot(),
        regime=RegimeState.COMPRESSION,
        config=StrategyConfig(),
    )

    assert not evaluation.accepted
    assert "funding_crowded_long" in evaluation.reasons
    assert "oi_crowded" in evaluation.reasons
    assert "volatility_panic" in evaluation.reasons
    assert "liquidation_cascade_active" in evaluation.reasons


def test_compression_gate_evaluator_blocks_missing_validation_evidence() -> None:
    report = {
        "performance": {"trades_count": 0, "profit_factor": None, "win_rate": None},
        "per_regime": {},
        "decision_summary": {"breakout_followthrough_rate": None, "internal_compression_closed_trades": 0},
        "signals": [],
    }

    result = evaluate_compression_gates(report)

    assert result["verdict"] == "ITERATE"
    failed = {gate["name"] for gate in result["gates"] if not gate["passed"]}
    assert "internal_compression_er" in failed
    assert "breakout_followthrough" in failed
    assert "overlap_control" in failed
    assert "walkforward" in failed
    assert result["red_flags"][0]["flag"] == "no_trades"


def test_compression_gate_evaluator_rejects_failed_breakout_thesis() -> None:
    report = {
        "performance": {"trades_count": 25, "expectancy_r": 0.4, "profit_factor": 0.8, "win_rate": 0.32},
        "per_regime": {"compression": {"expectancy_r": 0.4, "trades_count": 18}},
        "decision_summary": {"breakout_followthrough_rate": 0.25, "internal_compression_closed_trades": 25},
        "signals": [{"candidate_reasons": ["setup_type=compression_breakout_long"]}],
    }

    result = evaluate_compression_gates(
        report,
        overlap_rate=0.1,
        walkforward_passed_windows=2,
    )

    assert result["verdict"] == "REJECT"
    flags = {flag["flag"] for flag in result["red_flags"]}
    assert "compression_er_below_edge_threshold" in flags
    assert "breakout_followthrough_not_predictive" in flags
