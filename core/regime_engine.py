from __future__ import annotations

from dataclasses import dataclass

from core.models import Features, RegimeState


@dataclass(slots=True)
class RegimeConfig:
    ema_trend_gap_pct: float = 0.0025
    compression_atr_norm_max: float = 0.0055
    crowded_funding_extreme_pct: float = 85.0
    crowded_oi_zscore_min: float = 1.5
    post_liq_tfi_abs_min: float = 0.2


class RegimeEngine:
    def __init__(self, config: RegimeConfig | None = None) -> None:
        self.config = config or RegimeConfig()

    def classify(self, features: Features) -> RegimeState:
        if self._is_post_liquidation(features):
            return RegimeState.POST_LIQUIDATION
        if self._is_crowded_leverage(features):
            return RegimeState.CROWDED_LEVERAGE
        if self._is_compression(features):
            return RegimeState.COMPRESSION
        if self._is_uptrend(features):
            return RegimeState.UPTREND
        if self._is_downtrend(features):
            return RegimeState.DOWNTREND
        return RegimeState.NORMAL

    def _is_uptrend(self, features: Features) -> bool:
        if features.ema200_4h == 0:
            return False
        gap = (features.ema50_4h - features.ema200_4h) / features.ema200_4h
        return gap >= self.config.ema_trend_gap_pct and features.atr_4h_norm > self.config.compression_atr_norm_max

    def _is_downtrend(self, features: Features) -> bool:
        if features.ema200_4h == 0:
            return False
        gap = (features.ema200_4h - features.ema50_4h) / features.ema200_4h
        return gap >= self.config.ema_trend_gap_pct and features.atr_4h_norm > self.config.compression_atr_norm_max

    def _is_compression(self, features: Features) -> bool:
        return 0 < features.atr_4h_norm <= self.config.compression_atr_norm_max

    def _is_crowded_leverage(self, features: Features) -> bool:
        funding_extreme = (
            features.funding_pct_60d >= self.config.crowded_funding_extreme_pct
            or features.funding_pct_60d <= (100 - self.config.crowded_funding_extreme_pct)
        )
        return funding_extreme and abs(features.oi_zscore_60d) >= self.config.crowded_oi_zscore_min

    def _is_post_liquidation(self, features: Features) -> bool:
        if not features.force_order_spike:
            return False
        if abs(features.tfi_60s) < self.config.post_liq_tfi_abs_min:
            return False
        return features.force_order_decreasing
