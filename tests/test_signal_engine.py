from __future__ import annotations

from datetime import datetime, timezone

from core.models import Features, RegimeState
from core.signal_engine import SignalEngine


def _features(
    *,
    sweep_side: str | None,
    bullish_divergence: bool = False,
    bearish_divergence: bool = False,
    tfi_60s: float = 0.0,
    funding_8h: float = 0.0,
    ema50_4h: float = 100.0,
    ema200_4h: float = 100.0,
) -> Features:
    return Features(
        schema_version="v1.0",
        config_hash="hash",
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        atr_15m=10.0,
        atr_4h=50.0,
        atr_4h_norm=0.01,
        ema50_4h=ema50_4h,
        ema200_4h=ema200_4h,
        sweep_detected=True,
        reclaim_detected=True,
        sweep_level=100.0,
        sweep_depth_pct=0.001,
        sweep_side=sweep_side,
        funding_8h=funding_8h,
        funding_sma3=0.0,
        funding_sma9=0.0,
        funding_pct_60d=50.0,
        oi_value=1.0,
        oi_zscore_60d=0.0,
        oi_delta_pct=0.0,
        cvd_15m=0.0,
        cvd_bullish_divergence=bullish_divergence,
        cvd_bearish_divergence=bearish_divergence,
        tfi_60s=tfi_60s,
        force_order_rate_60s=0.0,
        force_order_spike=False,
        force_order_decreasing=False,
    )


def test_infer_direction_rejects_short_when_sweep_side_is_low() -> None:
    engine = SignalEngine()
    features = _features(sweep_side="LOW", bearish_divergence=True, tfi_60s=-0.2)

    assert engine._infer_direction(features) is None


def test_infer_direction_rejects_long_when_sweep_side_is_high() -> None:
    engine = SignalEngine()
    features = _features(sweep_side="HIGH", bullish_divergence=True, tfi_60s=0.2)

    assert engine._infer_direction(features) is None


def test_regime_special_bonus_changes_short_confluence_score() -> None:
    engine = SignalEngine()
    features = _features(
        sweep_side="HIGH",
        bearish_divergence=True,
        tfi_60s=-0.2,
        funding_8h=0.0001,
        ema50_4h=95.0,
        ema200_4h=100.0,
    )

    normal_score, normal_reasons = engine._confluence_score(features, RegimeState.NORMAL, "SHORT")
    downtrend_score, downtrend_reasons = engine._confluence_score(features, RegimeState.DOWNTREND, "SHORT")

    assert downtrend_score == normal_score + engine.config.weight_regime_special
    assert "regime_special" not in normal_reasons
    assert "regime_special" in downtrend_reasons


def test_short_tfi_impulse_requires_negative_flow() -> None:
    engine = SignalEngine()
    positive_tfi = _features(
        sweep_side="HIGH",
        bearish_divergence=True,
        tfi_60s=0.2,
        funding_8h=0.0001,
    )
    negative_tfi = _features(
        sweep_side="HIGH",
        bearish_divergence=True,
        tfi_60s=-0.2,
        funding_8h=0.0001,
    )

    positive_score, positive_reasons = engine._confluence_score(positive_tfi, RegimeState.NORMAL, "SHORT")
    negative_score, negative_reasons = engine._confluence_score(negative_tfi, RegimeState.NORMAL, "SHORT")

    assert negative_score == positive_score + engine.config.weight_tfi_impulse
    assert "tfi_impulse" not in positive_reasons
    assert "tfi_impulse" in negative_reasons
