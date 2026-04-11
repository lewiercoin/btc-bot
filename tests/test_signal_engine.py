from __future__ import annotations

from datetime import datetime, timezone

import pytest

from core.models import Features, RegimeState
from core.signal_engine import SignalConfig, SignalEngine


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


def test_infer_direction_short_on_low_sweep() -> None:
    """LOW sweep → SHORT. Direction derived from sweep_side, CVD/TFI irrelevant."""
    engine = SignalEngine()
    features = _features(sweep_side="LOW")

    assert engine._infer_direction(features) == "SHORT"


def test_infer_direction_long_on_high_sweep() -> None:
    """HIGH sweep → LONG. Direction derived from sweep_side, CVD/TFI irrelevant."""
    engine = SignalEngine()
    features = _features(sweep_side="HIGH")

    assert engine._infer_direction(features) == "LONG"


def test_infer_direction_none_when_no_sweep_side() -> None:
    """No sweep_side → None. No direction can be inferred."""
    engine = SignalEngine()
    features = _features(sweep_side=None)

    assert engine._infer_direction(features) is None


def test_infer_direction_ignores_cvd_tfi() -> None:
    """Direction is purely from sweep_side. Bullish CVD on LOW sweep still → SHORT."""
    engine = SignalEngine()
    features = _features(sweep_side="LOW", bullish_divergence=True, tfi_60s=0.5)

    assert engine._infer_direction(features) == "SHORT"


def test_regime_special_bonus_changes_short_confluence_score() -> None:
    engine = SignalEngine()
    features = _features(
        sweep_side="LOW",
        bearish_divergence=True,
        tfi_60s=-0.2,
        funding_8h=0.0001,
        ema50_4h=95.0,
        ema200_4h=100.0,
    )

    normal_score, normal_reasons = engine._confluence_score(features, RegimeState.NORMAL, "SHORT")
    downtrend_score, downtrend_reasons = engine._confluence_score(features, RegimeState.DOWNTREND, "SHORT")

    assert downtrend_score == pytest.approx(normal_score + engine.config.weight_regime_special)
    assert "regime_special" not in normal_reasons
    assert "regime_special" in downtrend_reasons


def test_short_tfi_impulse_requires_negative_flow() -> None:
    engine = SignalEngine()
    positive_tfi = _features(
        sweep_side="LOW",
        bearish_divergence=True,
        tfi_60s=0.2,
        funding_8h=-0.0001,
    )
    negative_tfi = _features(
        sweep_side="LOW",
        bearish_divergence=True,
        tfi_60s=-0.2,
        funding_8h=-0.0001,
    )

    positive_score, positive_reasons = engine._confluence_score(positive_tfi, RegimeState.NORMAL, "SHORT")
    negative_score, negative_reasons = engine._confluence_score(negative_tfi, RegimeState.NORMAL, "SHORT")

    assert negative_score == positive_score + engine.config.weight_tfi_impulse
    assert "tfi_impulse" not in positive_reasons
    assert "tfi_impulse" in negative_reasons


def test_direction_whitelist_blocks_long_in_uptrend_by_default() -> None:
    engine = SignalEngine()

    assert engine._is_direction_allowed_for_regime(direction="LONG", regime=RegimeState.UPTREND) is False


def test_direction_whitelist_can_allow_long_in_uptrend_via_config() -> None:
    engine = SignalEngine(
        SignalConfig(
            regime_direction_whitelist={
                RegimeState.UPTREND.value: ("LONG",),
            }
        )
    )

    assert engine._is_direction_allowed_for_regime(direction="LONG", regime=RegimeState.UPTREND) is True


def test_default_whitelist_allows_short_in_normal() -> None:
    """With inversion, SHORT must be allowed in NORMAL regime."""
    engine = SignalEngine()
    assert engine._is_direction_allowed_for_regime(direction="SHORT", regime=RegimeState.NORMAL) is True


def test_generate_short_on_low_sweep_end_to_end() -> None:
    """Full pipeline: LOW sweep + bearish divergence + sufficient confluence → SHORT signal."""
    engine = SignalEngine(
        SignalConfig(
            confluence_min=0.5,
            weight_cvd_divergence=0.75,
            weight_tfi_impulse=0.50,
        )
    )
    features = _features(
        sweep_side="LOW",
        bearish_divergence=True,
        tfi_60s=-0.2,
        funding_8h=0.0001,
        ema50_4h=95.0,
        ema200_4h=100.0,
    )
    candidate = engine.generate(features, RegimeState.NORMAL)
    assert candidate is not None
    assert candidate.direction == "SHORT"
    assert candidate.entry_reference < features.sweep_level
    assert candidate.invalidation_level > candidate.entry_reference
    assert candidate.tp_reference_1 < candidate.entry_reference


def test_generate_long_on_high_sweep_end_to_end() -> None:
    """Full pipeline: HIGH sweep + bullish divergence + sufficient confluence → LONG signal."""
    engine = SignalEngine(
        SignalConfig(
            confluence_min=0.5,
            weight_cvd_divergence=0.75,
            weight_tfi_impulse=0.50,
        )
    )
    features = _features(
        sweep_side="HIGH",
        bullish_divergence=True,
        tfi_60s=0.2,
        funding_8h=-0.0001,
        ema50_4h=105.0,
        ema200_4h=100.0,
    )
    candidate = engine.generate(features, RegimeState.NORMAL)
    assert candidate is not None
    assert candidate.direction == "LONG"
    assert candidate.entry_reference > features.sweep_level
    assert candidate.invalidation_level < candidate.entry_reference
    assert candidate.tp_reference_1 > candidate.entry_reference


def test_generate_rejects_none_sweep_side_end_to_end() -> None:
    """Full pipeline: no sweep_side → no direction → rejected."""
    engine = SignalEngine(SignalConfig(confluence_min=0.0))
    features = _features(sweep_side=None, bullish_divergence=True, tfi_60s=0.2)
    assert engine.generate(features, RegimeState.NORMAL) is None


def test_generate_low_sweep_always_short_regardless_of_cvd() -> None:
    """Full pipeline: LOW sweep + bullish CVD → still SHORT (CVD only affects confluence)."""
    engine = SignalEngine(SignalConfig(confluence_min=0.0))
    features = _features(
        sweep_side="LOW",
        bullish_divergence=True,
        tfi_60s=0.2,
    )
    candidate = engine.generate(features, RegimeState.NORMAL)
    assert candidate is not None
    assert candidate.direction == "SHORT"


def test_inversion_deterministic_same_input_same_output() -> None:
    """Direction flip is deterministic: same input always produces same direction."""
    engine = SignalEngine(
        SignalConfig(
            confluence_min=0.5,
            weight_cvd_divergence=0.75,
            weight_tfi_impulse=0.50,
        )
    )
    features = _features(
        sweep_side="LOW",
        bearish_divergence=True,
        tfi_60s=-0.2,
        funding_8h=0.0001,
        ema50_4h=95.0,
        ema200_4h=100.0,
    )
    results = [engine.generate(features, RegimeState.NORMAL) for _ in range(10)]
    directions = [r.direction for r in results if r is not None]
    assert len(directions) == 10
    assert all(d == "SHORT" for d in directions)
