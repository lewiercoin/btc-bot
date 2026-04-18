from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

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
    close_vs_reclaim_buffer_atr: float | None = None,
    wick_vs_min_atr: float | None = None,
    sweep_vs_buffer_atr: float | None = None,
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
        close_vs_reclaim_buffer_atr=close_vs_reclaim_buffer_atr,
        wick_vs_min_atr=wick_vs_min_atr,
        sweep_vs_buffer_atr=sweep_vs_buffer_atr,
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


def test_diagnose_reports_regime_whitelist_block_for_long_uptrend() -> None:
    engine = SignalEngine()
    features = _features(sweep_side="LOW", bullish_divergence=True, tfi_60s=0.2)

    diagnostics = engine.diagnose(features, RegimeState.UPTREND)

    assert diagnostics.blocked_by == "regime_direction_whitelist"
    assert diagnostics.direction_inferred == "LONG"
    assert diagnostics.direction_allowed is False
    assert diagnostics.reclaim_detected is True


def test_uptrend_continuation_infers_long_without_reclaim() -> None:
    engine = SignalEngine(
        SignalConfig(
            confluence_min=0.0,
            ema_trend_gap_pct=0.02,
            regime_direction_whitelist={
                RegimeState.UPTREND.value: ("LONG",),
            },
        )
    )
    features = replace(
        _features(sweep_side="HIGH", bullish_divergence=True, tfi_60s=0.2, ema50_4h=105.0, ema200_4h=100.0),
        reclaim_detected=False,
    )

    diagnostics = engine.diagnose(features, RegimeState.UPTREND)

    assert diagnostics.blocked_by is None
    assert diagnostics.direction_inferred == "LONG"
    assert diagnostics.direction_allowed is True
    assert diagnostics.reclaim_detected is False


def test_uptrend_continuation_blocked_on_low_sweep() -> None:
    engine = SignalEngine(
        SignalConfig(
            ema_trend_gap_pct=0.02,
            regime_direction_whitelist={
                RegimeState.UPTREND.value: ("LONG",),
            },
        )
    )
    features = replace(
        _features(sweep_side="LOW", bullish_divergence=True, tfi_60s=0.2, ema50_4h=105.0, ema200_4h=100.0),
        reclaim_detected=False,
    )

    diagnostics = engine.diagnose(features, RegimeState.UPTREND)

    assert diagnostics.blocked_by == "uptrend_continuation_weak"
    assert diagnostics.direction_inferred is None
    assert diagnostics.direction_allowed is None


def test_uptrend_continuation_blocked_weak_trend() -> None:
    engine = SignalEngine(
        SignalConfig(
            ema_trend_gap_pct=0.01,
            regime_direction_whitelist={
                RegimeState.UPTREND.value: ("LONG",),
            },
        )
    )
    features = replace(
        _features(sweep_side="HIGH", bullish_divergence=True, tfi_60s=0.2, ema50_4h=100.4, ema200_4h=100.0),
        reclaim_detected=False,
    )

    diagnostics = engine.diagnose(features, RegimeState.UPTREND)

    assert diagnostics.blocked_by == "uptrend_continuation_weak"
    assert diagnostics.direction_inferred is None
    assert diagnostics.direction_allowed is None


def test_uptrend_continuation_fallback_to_reclaim() -> None:
    engine = SignalEngine(
        SignalConfig(
            confluence_min=0.0,
            regime_direction_whitelist={
                RegimeState.UPTREND.value: ("SHORT",),
            },
        )
    )
    features = _features(sweep_side="HIGH", bearish_divergence=True, tfi_60s=-0.2, ema50_4h=105.0, ema200_4h=100.0)

    diagnostics = engine.diagnose(features, RegimeState.UPTREND)

    assert diagnostics.blocked_by is None
    assert diagnostics.direction_inferred == "SHORT"
    assert diagnostics.direction_allowed is True
    assert diagnostics.reclaim_detected is True


def test_diagnose_non_uptrend_preserves_gate_order_and_stops_at_no_reclaim() -> None:
    engine = SignalEngine()
    features = replace(
        _features(sweep_side="LOW", bullish_divergence=True, tfi_60s=0.2),
        reclaim_detected=False,
    )

    diagnostics = engine.diagnose(features, RegimeState.NORMAL)

    assert diagnostics.blocked_by == "no_reclaim"
    assert diagnostics.direction_inferred is None
    assert diagnostics.direction_allowed is None
    assert diagnostics.confluence_preview is None


def test_diagnose_propagates_reclaim_diagnostic_fields() -> None:
    engine = SignalEngine()
    features = replace(
        _features(
            sweep_side="LOW",
            bullish_divergence=True,
            tfi_60s=0.2,
            close_vs_reclaim_buffer_atr=-0.25,
            wick_vs_min_atr=0.5,
            sweep_vs_buffer_atr=0.75,
        ),
        reclaim_detected=False,
    )

    diagnostics = engine.diagnose(features, RegimeState.NORMAL)

    assert diagnostics.close_vs_reclaim_buffer_atr == -0.25
    assert diagnostics.wick_vs_min_atr == 0.5
    assert diagnostics.sweep_vs_buffer_atr == 0.75


def test_generate_accepts_precomputed_diagnostics_without_changing_candidate() -> None:
    engine = SignalEngine(
        SignalConfig(
            regime_direction_whitelist={
                RegimeState.UPTREND.value: ("LONG",),
            }
        )
    )
    features = _features(sweep_side="LOW", bullish_divergence=True, tfi_60s=0.2)
    diagnostics = engine.diagnose(features, RegimeState.UPTREND)

    direct = engine.generate(features, RegimeState.UPTREND)
    precomputed = engine.generate(features, RegimeState.UPTREND, diagnostics=diagnostics)

    assert diagnostics.blocked_by is None
    assert direct is not None
    assert precomputed is not None
    assert precomputed.direction == direct.direction
    assert precomputed.confluence_score == direct.confluence_score
    assert precomputed.reasons == direct.reasons
    assert precomputed.entry_reference == direct.entry_reference
