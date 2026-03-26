from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from core.models import Features, RegimeState, SignalCandidate


@dataclass(slots=True)
class SignalConfig:
    confluence_min: float = 3.0
    min_sweep_depth_pct: float = 0.0001
    entry_offset_atr: float = 0.05
    invalidation_offset_atr: float = 0.25
    tp1_atr_mult: float = 2.0
    tp2_atr_mult: float = 3.5
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


class SignalEngine:
    def __init__(self, config: SignalConfig | None = None) -> None:
        self.config = config or SignalConfig()

    def generate(self, features: Features, regime: RegimeState) -> SignalCandidate | None:
        if not features.sweep_detected:
            return None
        if not features.reclaim_detected:
            return None
        if features.sweep_level is None:
            return None
        if features.sweep_depth_pct is not None and features.sweep_depth_pct < self.config.min_sweep_depth_pct:
            return None

        direction = self._infer_direction(features)
        if direction is None:
            return None

        confluence_score, reasons = self._confluence_score(features, regime, direction)
        if confluence_score < self.config.confluence_min:
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
            reasons=reasons,
            features_json={
                "atr_15m": features.atr_15m,
                "sweep_depth_pct": features.sweep_depth_pct,
                "funding_pct_60d": features.funding_pct_60d,
                "oi_zscore_60d": features.oi_zscore_60d,
                "cvd_15m": features.cvd_15m,
                "tfi_60s": features.tfi_60s,
                "force_order_rate_60s": features.force_order_rate_60s,
                "force_order_spike": features.force_order_spike,
            },
        )

    def _infer_direction(self, features: Features) -> str | None:
        if features.cvd_bullish_divergence and not features.cvd_bearish_divergence:
            return "LONG"
        if features.cvd_bearish_divergence and not features.cvd_bullish_divergence:
            return "SHORT"
        if features.tfi_60s > self.config.direction_tfi_threshold:
            return "LONG"
        if features.tfi_60s < self.config.direction_tfi_threshold_inverse:
            return "SHORT"
        return None

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

        if abs(features.tfi_60s) >= self.config.tfi_impulse_threshold:
            score += self.config.weight_tfi_impulse
            reasons.append("tfi_impulse")
        if features.force_order_spike:
            score += self.config.weight_force_order_spike
            reasons.append("force_order_spike")
        if regime in (RegimeState.POST_LIQUIDATION, RegimeState.CROWDED_LEVERAGE):
            score += self.config.weight_regime_special
            reasons.append(f"regime_{regime.value}")

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

    def _build_levels(self, features: Features, direction: str) -> tuple[float, float, float, float]:
        atr = max(features.atr_15m, 1e-8)
        base = float(features.sweep_level or 0.0)
        if base == 0:
            base = max(features.ema50_4h, 1.0)

        if direction == "LONG":
            entry = base + (atr * self.config.entry_offset_atr)
            invalidation = base - (atr * self.config.invalidation_offset_atr)
            tp1 = entry + atr * self.config.tp1_atr_mult
            tp2 = entry + atr * self.config.tp2_atr_mult
        else:
            entry = base - (atr * self.config.entry_offset_atr)
            invalidation = base + (atr * self.config.invalidation_offset_atr)
            tp1 = entry - atr * self.config.tp1_atr_mult
            tp2 = entry - atr * self.config.tp2_atr_mult

        return entry, invalidation, tp1, tp2

    def _make_signal_id(self, timestamp: datetime) -> str:
        ts = timestamp.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%S")
        return f"sig-{ts}-{uuid4().hex[:10]}"
