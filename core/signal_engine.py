from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

from core.models import Features, RegimeState, SignalCandidate, SignalDiagnostics


def _default_regime_direction_whitelist() -> dict[str, tuple[str, ...]]:
    return {
        RegimeState.NORMAL.value: ("LONG",),
        RegimeState.COMPRESSION.value: ("LONG",),
        RegimeState.DOWNTREND.value: ("LONG", "SHORT"),
        RegimeState.UPTREND.value: (),
        RegimeState.CROWDED_LEVERAGE.value: ("SHORT",),
        RegimeState.POST_LIQUIDATION.value: ("LONG",),
    }


@dataclass(slots=True)
class SignalConfig:
    confluence_min: float = 3.0
    min_sweep_depth_pct: float = 0.0001
    ema_trend_gap_pct: float = 0.0063
    entry_offset_atr: float = 0.05
    invalidation_offset_atr: float = 0.75
    min_stop_distance_pct: float = 0.0015
    tp1_atr_mult: float = 2.5
    tp2_atr_mult: float = 4.0
    weight_sweep_detected: float = 1.25
    weight_reclaim_confirmed: float = 1.25
    weight_cvd_divergence: float = 0.75
    weight_tfi_impulse: float = 0.50
    weight_force_order_spike: float = 0.40
    weight_regime_special: float = 0.35
    weight_ema_trend_alignment: float = 0.25
    weight_funding_supportive: float = 0.20
    direction_tfi_threshold: float = 0.05
    direction_tfi_threshold_inverse: float = -0.05
    tfi_impulse_threshold: float = 0.10
    regime_direction_whitelist: dict[str, tuple[str, ...]] = field(default_factory=_default_regime_direction_whitelist)


class SignalEngine:
    def __init__(self, config: SignalConfig | None = None) -> None:
        self.config = config or SignalConfig()

    def diagnose(self, features: Features, regime: RegimeState) -> SignalDiagnostics:
        direction: str | None = None
        direction_allowed: bool | None = None
        confluence_preview: float | None = None
        candidate_reasons_preview: list[str] = []
        blocked_by: str | None = None

        if not features.sweep_detected:
            blocked_by = "no_sweep"
        elif features.sweep_level is None:
            blocked_by = "missing_sweep_level"
        elif features.sweep_depth_pct is not None and features.sweep_depth_pct < self.config.min_sweep_depth_pct:
            blocked_by = "sweep_too_shallow"
        else:
            continuation_blocked_by: str | None = None
            if regime is RegimeState.UPTREND and not features.reclaim_detected:
                direction, continuation_blocked_by = self._infer_uptrend_continuation_direction(features)

            if direction is None:
                if not features.reclaim_detected:
                    blocked_by = continuation_blocked_by or "no_reclaim"
                else:
                    direction = self._infer_direction(features)
                    if direction is None:
                        blocked_by = "direction_unresolved"

            if direction is not None:
                direction_allowed = self._is_direction_allowed_for_regime(direction=direction, regime=regime)
                if not direction_allowed:
                    blocked_by = "regime_direction_whitelist"
                else:
                    confluence_preview, candidate_reasons_preview = self._confluence_score(features, regime, direction)
                    if confluence_preview < self.config.confluence_min:
                        blocked_by = "confluence_below_min"

        return SignalDiagnostics(
            timestamp=features.timestamp,
            config_hash=features.config_hash,
            regime=regime,
            blocked_by=blocked_by,
            sweep_detected=features.sweep_detected,
            reclaim_detected=features.reclaim_detected,
            sweep_side=features.sweep_side,
            sweep_level=features.sweep_level,
            sweep_depth_pct=features.sweep_depth_pct,
            direction_inferred=direction,
            direction_allowed=direction_allowed,
            confluence_preview=confluence_preview,
            close_vs_reclaim_buffer_atr=features.close_vs_reclaim_buffer_atr,
            wick_vs_min_atr=features.wick_vs_min_atr,
            sweep_vs_buffer_atr=features.sweep_vs_buffer_atr,
            candidate_reasons_preview=candidate_reasons_preview,
        )

    def _infer_uptrend_continuation_direction(self, features: Features) -> tuple[str | None, str | None]:
        if features.sweep_side != "HIGH":
            return None, "uptrend_continuation_weak"

        ema_gap_pct = self._ema_gap_pct(features)
        ema_gap_ok = ema_gap_pct > self.config.ema_trend_gap_pct
        tfi_bullish = features.tfi_60s > self.config.direction_tfi_threshold

        if ema_gap_ok and tfi_bullish:
            return "LONG", None
        return None, "uptrend_continuation_weak"

    def generate(
        self,
        features: Features,
        regime: RegimeState,
        diagnostics: SignalDiagnostics | None = None,
    ) -> SignalCandidate | None:
        resolved_diagnostics = diagnostics or self.diagnose(features, regime)
        if resolved_diagnostics.blocked_by is not None:
            return None

        direction = resolved_diagnostics.direction_inferred
        confluence_score = resolved_diagnostics.confluence_preview
        if direction is None or confluence_score is None:
            return None

        entry, invalidation, tp1, tp2 = self._build_levels(features, direction)
        setup_type = f"liquidity_sweep_reclaim_{direction.lower()}"
        return SignalCandidate(
            signal_id=self._make_signal_id(features.timestamp),
            timestamp=features.timestamp,
            direction=direction,
            setup_type=setup_type,
            entry_reference=entry,
            invalidation_level=invalidation,
            tp_reference_1=tp1,
            tp_reference_2=tp2,
            confluence_score=confluence_score,
            regime=regime,
            reasons=list(resolved_diagnostics.candidate_reasons_preview),
            features_json={
                "atr_15m": features.atr_15m,
                "sweep_depth_pct": features.sweep_depth_pct,
                "sweep_side": features.sweep_side,
                "funding_pct_60d": features.funding_pct_60d,
                "oi_zscore_60d": features.oi_zscore_60d,
                "cvd_15m": features.cvd_15m,
                "tfi_60s": features.tfi_60s,
                "force_order_rate_60s": features.force_order_rate_60s,
                "force_order_spike": features.force_order_spike,
            },
        )

    def _infer_direction(self, features: Features) -> str | None:
        inferred_direction: str | None = None
        if features.cvd_bullish_divergence and not features.cvd_bearish_divergence:
            inferred_direction = "LONG"
        elif features.cvd_bearish_divergence and not features.cvd_bullish_divergence:
            inferred_direction = "SHORT"
        elif features.tfi_60s > self.config.direction_tfi_threshold:
            inferred_direction = "LONG"
        elif features.tfi_60s < self.config.direction_tfi_threshold_inverse:
            inferred_direction = "SHORT"

        if inferred_direction == "LONG" and features.sweep_side != "LOW":
            return None
        if inferred_direction == "SHORT" and features.sweep_side != "HIGH":
            return None
        return inferred_direction

    def _ema_gap_pct(self, features: Features) -> float:
        if features.ema200_4h == 0:
            return 0.0
        return (features.ema50_4h - features.ema200_4h) / features.ema200_4h

    def _confluence_score(self, features: Features, regime: RegimeState, direction: str) -> tuple[float, list[str]]:
        score = 0.0
        reasons: list[str] = []

        if features.sweep_detected:
            score += self.config.weight_sweep_detected
            reasons.append("liquidity_sweep_detected")
        if features.reclaim_detected:
            score += self.config.weight_reclaim_confirmed
            reasons.append("reclaim_confirmed")

        if direction == "LONG" and features.cvd_bullish_divergence:
            score += self.config.weight_cvd_divergence
            reasons.append("cvd_bullish_divergence")
        if direction == "SHORT" and features.cvd_bearish_divergence:
            score += self.config.weight_cvd_divergence
            reasons.append("cvd_bearish_divergence")

        if direction == "LONG" and features.tfi_60s >= self.config.tfi_impulse_threshold:
            score += self.config.weight_tfi_impulse
            reasons.append("tfi_impulse")
        if direction == "SHORT" and features.tfi_60s <= -self.config.tfi_impulse_threshold:
            score += self.config.weight_tfi_impulse
            reasons.append("tfi_impulse")
        if features.force_order_spike:
            score += self.config.weight_force_order_spike
            reasons.append("force_order_spike")
        if self._is_regime_special_supportive(direction=direction, regime=regime):
            score += self.config.weight_regime_special
            reasons.append("regime_special")

        if direction == "LONG" and features.ema50_4h >= features.ema200_4h:
            score += self.config.weight_ema_trend_alignment
            reasons.append("ema_trend_alignment")
        if direction == "SHORT" and features.ema50_4h <= features.ema200_4h:
            score += self.config.weight_ema_trend_alignment
            reasons.append("ema_trend_alignment")

        if direction == "LONG" and features.funding_8h <= 0:
            score += self.config.weight_funding_supportive
            reasons.append("funding_supportive")
        if direction == "SHORT" and features.funding_8h >= 0:
            score += self.config.weight_funding_supportive
            reasons.append("funding_supportive")

        return score, reasons

    def _is_regime_special_supportive(self, *, direction: str, regime: RegimeState) -> bool:
        # Award the special bonus only in structurally asymmetric regimes:
        # SHORTs in HTF downtrend / crowded leverage, LONGs after liquidation unwind.
        if direction == "SHORT":
            return regime in {RegimeState.DOWNTREND, RegimeState.CROWDED_LEVERAGE}
        if direction == "LONG":
            return regime is RegimeState.POST_LIQUIDATION
        return False

    def _build_levels(self, features: Features, direction: str) -> tuple[float, float, float, float]:
        atr = max(features.atr_15m, 1e-8)
        base = float(features.sweep_level or 0.0)
        if base == 0:
            base = max(features.ema50_4h, 1.0)
        min_stop_distance_pct = max(self.config.min_stop_distance_pct, 0.0)

        if direction == "LONG":
            entry = base + (atr * self.config.entry_offset_atr)
            raw_invalidation = base - (atr * self.config.invalidation_offset_atr)
            min_stop_distance = abs(entry) * min_stop_distance_pct
            actual_stop_distance = max(abs(entry - raw_invalidation), min_stop_distance)
            invalidation = entry - actual_stop_distance
            tp1 = entry + atr * self.config.tp1_atr_mult
            tp2 = entry + atr * self.config.tp2_atr_mult
        else:
            entry = base - (atr * self.config.entry_offset_atr)
            raw_invalidation = base + (atr * self.config.invalidation_offset_atr)
            min_stop_distance = abs(entry) * min_stop_distance_pct
            actual_stop_distance = max(abs(entry - raw_invalidation), min_stop_distance)
            invalidation = entry + actual_stop_distance
            tp1 = entry - atr * self.config.tp1_atr_mult
            tp2 = entry - atr * self.config.tp2_atr_mult

        return entry, invalidation, tp1, tp2

    def _is_direction_allowed_for_regime(self, *, direction: str, regime: RegimeState) -> bool:
        allowed = self.config.regime_direction_whitelist.get(regime.value)
        if allowed is None:
            return False
        return direction in allowed

    def _make_signal_id(self, timestamp: datetime) -> str:
        ts = timestamp.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%S")
        return f"sig-{ts}-{uuid4().hex[:10]}"
