from __future__ import annotations

from datetime import datetime, timedelta, timezone

from core.models import Features, MarketSnapshot, RegimeState
from research_lab.evaluate_post_cascade_gates import evaluate_post_cascade_gates
from research_lab.setups.post_cascade_momentum import (
    PostCascadeMomentumLong,
    PostCascadeMomentumShort,
    detect_cascade_direction,
)
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
        funding_8h=0.0,
        funding_sma3=0.0,
        funding_sma9=0.0,
        funding_pct_60d=50.0,
        oi_value=1.0,
        oi_zscore_60d=0.0,
        oi_delta_pct=0.0,
        cvd_15m=0.0,
        cvd_bullish_divergence=False,
        cvd_bearish_divergence=False,
        tfi_60s=0.12,
        force_order_rate_60s=0.0,
        force_order_spike=False,
        force_order_decreasing=True,
    )
    values.update(overrides)
    return Features(**values)


def _snapshot(*, price: float = 100_000.0, force_orders: list[dict] | None = None) -> MarketSnapshot:
    ts = datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc)
    candles_15m = []
    base = ts - timedelta(minutes=15 * 12)
    for index in range(12):
        close = price - 120.0 + index * 15.0
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
    snapshot = MarketSnapshot(
        symbol="BTCUSDT",
        timestamp=ts,
        price=price,
        bid=price - 5.0,
        ask=price + 5.0,
        candles_15m=candles_15m,
        candles_4h=[],
    )
    snapshot.source_meta["research_force_orders_lookback"] = force_orders or _up_force_orders()
    return snapshot


def _up_force_orders() -> list[dict]:
    return [{"side": "BUY"} for _ in range(8)] + [{"side": "SELL"} for _ in range(2)]


def _down_force_orders() -> list[dict]:
    return [{"side": "SELL"} for _ in range(8)] + [{"side": "BUY"} for _ in range(2)]


def test_detect_cascade_direction_identifies_up_and_down() -> None:
    assert detect_cascade_direction(_up_force_orders(), threshold=0.7)[0] == "up"
    assert detect_cascade_direction(_down_force_orders(), threshold=0.7)[0] == "down"
    assert detect_cascade_direction([{"side": "BUY"}, {"side": "SELL"}], threshold=0.7)[0] is None


def test_post_cascade_long_generates_after_upward_cascade() -> None:
    candidate = PostCascadeMomentumLong().generate_signal_candidate(
        features=_features(tfi_60s=0.12),
        snapshot=_snapshot(force_orders=_up_force_orders()),
        regime=RegimeState.POST_LIQUIDATION,
        config=StrategyConfig(),
    )

    assert candidate is not None
    assert candidate.setup_type == "post_cascade_momentum_long"
    assert candidate.direction == "LONG"
    assert candidate.regime is RegimeState.POST_LIQUIDATION
    assert candidate.invalidation_level < candidate.entry_reference < candidate.tp_reference_1
    assert "entry_timing=post_liquidation_aftermath_state" in candidate.reasons
    assert "not_late_crowded_unwind=True" in candidate.reasons


def test_post_cascade_short_generates_after_downward_cascade() -> None:
    candidate = PostCascadeMomentumShort().generate_signal_candidate(
        features=_features(tfi_60s=-0.12),
        snapshot=_snapshot(force_orders=_down_force_orders()),
        regime=RegimeState.POST_LIQUIDATION,
        config=StrategyConfig(),
    )

    assert candidate is not None
    assert candidate.setup_type == "post_cascade_momentum_short"
    assert candidate.direction == "SHORT"
    assert candidate.tp_reference_1 < candidate.entry_reference < candidate.invalidation_level


def test_post_cascade_requires_post_liquidation_regime() -> None:
    evaluation = PostCascadeMomentumLong().evaluate_structure(
        features=_features(tfi_60s=0.12),
        snapshot=_snapshot(force_orders=_up_force_orders()),
        regime=RegimeState.CROWDED_LEVERAGE,
        config=StrategyConfig(),
    )

    assert not evaluation.accepted
    assert "regime_blocked:crowded_leverage" in evaluation.reasons


def test_post_cascade_rejects_mixed_cascade_direction() -> None:
    evaluation = PostCascadeMomentumLong().evaluate_structure(
        features=_features(tfi_60s=0.12),
        snapshot=_snapshot(force_orders=[{"side": "BUY"}, {"side": "SELL"}]),
        regime=RegimeState.POST_LIQUIDATION,
        config=StrategyConfig(),
    )

    assert not evaluation.accepted
    assert "cascade_direction_unclear" in evaluation.reasons


def test_post_cascade_rejects_wrong_momentum() -> None:
    evaluation = PostCascadeMomentumLong().evaluate_structure(
        features=_features(tfi_60s=-0.12),
        snapshot=_snapshot(force_orders=_up_force_orders()),
        regime=RegimeState.POST_LIQUIDATION,
        config=StrategyConfig(),
    )

    assert not evaluation.accepted
    assert "momentum_not_confirmed" in evaluation.reasons


def test_post_cascade_gate_evaluator_rejects_hard_stop() -> None:
    report = {
        "performance": {"trades_count": 12},
        "per_regime": {"post_liquidation": {"expectancy_r": 0.2, "trades_count": 12}},
        "decision_summary": {"cascade_continuation_rate": 0.35},
        "signals": [{"candidate_reasons": ["setup_type=post_cascade_momentum_long"]}],
    }

    result = evaluate_post_cascade_gates(report)

    assert result["verdict"] == "REJECT"
    flags = {flag["flag"] for flag in result["red_flags"]}
    assert "post_liquidation_er_below_hard_stop" in flags
    assert "cascade_continuation_not_predictive" in flags


def test_post_cascade_gate_evaluator_detects_wrong_regime_bug() -> None:
    report = {
        "performance": {"trades_count": 12},
        "per_regime": {"normal": {"expectancy_r": 2.0, "trades_count": 12}},
        "decision_summary": {"cascade_continuation_rate": 0.8},
        "signals": [{"candidate_reasons": ["setup_type=post_cascade_momentum_long"]}],
    }

    result = evaluate_post_cascade_gates(report)

    assert result["verdict"] == "IMPLEMENTATION_BUG"
    assert result["red_flags"][0]["flag"] == "wrong_regime_trades"
