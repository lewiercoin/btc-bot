from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from core.models import Features, MarketSnapshot, RegimeState, SignalCandidate
from research_lab.setups.base_setup import BaseSetup, SetupEvaluation
from settings import StrategyConfig


@dataclass(slots=True, frozen=True)
class AbsorptionContinuationConfig:
    pullback_min_pct: float = 0.005
    pullback_max_pct: float = 0.03
    ema_proximity_atr: float = 0.75
    equal_low_proximity_atr: float = 0.50
    min_ema200_slope_pct: float = 0.0001
    max_extension_pct: float = 0.05
    funding_extreme: float = 0.0008
    oi_extreme_zscore: float = 2.5
    oi_participation_min_delta_pct: float = -0.002
    tfi_threshold: float = 0.30
    volatility_panic_atr_norm: float = 0.008
    liquidation_rate_threshold: float = 1.0
    entry_offset_atr: float = 0.05
    invalidation_offset_atr: float = 0.30
    tp1_atr_mult: float = 2.5
    tp2_atr_mult: float = 4.0
    min_rr: float = 2.1
    recent_high_lookback_15m: int = 32
    swing_low_lookback_15m: int = 16
    ema_slope_lookback_4h: int = 3


class AbsorptionContinuationLong(BaseSetup):
    """Institutional-grade trend pullback absorption setup for research only."""

    def __init__(self, setup_config: AbsorptionContinuationConfig | None = None) -> None:
        self.setup_config = setup_config or AbsorptionContinuationConfig()

    def get_setup_type(self) -> str:
        return "absorption_continuation_long"

    def check_regime_allowed(self, regime: RegimeState | str) -> bool:
        return _regime_value(regime) == RegimeState.UPTREND.value

    def evaluate_structure(
        self,
        *,
        features: Features,
        snapshot: MarketSnapshot,
        regime: RegimeState | str,
        config: StrategyConfig,
    ) -> SetupEvaluation:
        checks = self._evaluate(features=features, snapshot=snapshot, regime=regime, config=config)
        return SetupEvaluation(
            accepted=checks["accepted"],
            reasons=list(checks["reasons"]),
            metrics=dict(checks["metrics"]),
        )

    def generate_signal_candidate(
        self,
        *,
        features: Features,
        snapshot: MarketSnapshot,
        regime: RegimeState | str,
        config: StrategyConfig,
    ) -> SignalCandidate | None:
        checks = self._evaluate(features=features, snapshot=snapshot, regime=regime, config=config)
        if not checks["accepted"]:
            return None

        metrics = checks["metrics"]
        price = float(snapshot.price)
        atr_15m = max(float(features.atr_15m), 1e-8)
        pullback_low = float(metrics["pullback_low"])
        prior_swing_low = float(metrics["prior_swing_low"])

        entry = price + (self.setup_config.entry_offset_atr * atr_15m)
        structural_stop = min(pullback_low, prior_swing_low)
        invalidation = structural_stop - (self.setup_config.invalidation_offset_atr * atr_15m)
        tp1 = entry + (self.setup_config.tp1_atr_mult * atr_15m)
        tp2 = entry + (self.setup_config.tp2_atr_mult * atr_15m)
        rr_ratio = _rr_long(entry=entry, stop=invalidation, target=tp1)
        if rr_ratio < self.setup_config.min_rr:
            return None

        reasons = [
            f"setup_type={self.get_setup_type()}",
            f"regime={_regime_value(regime)}",
            "trend_structure=uptrend_price_above_ema200_ema50_above_ema200",
            f"ema200_slope_pct={metrics['ema200_slope_pct']:.6f}",
            f"pullback_depth_pct={metrics['pullback_depth_pct']:.6f}",
            f"price_near_ema50_atr={metrics['price_near_ema50_atr']:.3f}",
            f"price_near_equal_low={metrics['price_near_equal_low']}",
            f"maintains_higher_lows={metrics['maintains_higher_lows']}",
            f"cvd_bullish_divergence={features.cvd_bullish_divergence}",
            f"cvd_15m_slope_proxy={metrics['cvd_slope_proxy']:.6f}",
            f"tfi_60s={features.tfi_60s:.3f}",
            f"oi_delta_pct={features.oi_delta_pct:.6f}",
            f"funding_8h={features.funding_8h:.6f}",
            f"oi_zscore_60d={features.oi_zscore_60d:.3f}",
            f"atr_4h_norm={features.atr_4h_norm:.6f}",
            f"rr_ratio={rr_ratio:.3f}",
            "entry_timing=pullback_absorption_before_breakout_confirmation",
            "counterparty=pullback_sellers_early_shorts_late_breakout_buyers",
        ]

        return SignalCandidate(
            signal_id=f"research-absorption-{uuid4().hex}",
            timestamp=_to_utc(features.timestamp),
            direction="LONG",
            setup_type=self.get_setup_type(),
            entry_reference=entry,
            invalidation_level=invalidation,
            tp_reference_1=tp1,
            tp_reference_2=tp2,
            confluence_score=self._confluence_score(features=features, metrics=metrics, rr_ratio=rr_ratio),
            regime=_as_regime(regime),
            reasons=reasons,
            features_json={
                "atr_15m": features.atr_15m,
                "atr_4h": features.atr_4h,
                "atr_4h_norm": features.atr_4h_norm,
                "ema50_4h": features.ema50_4h,
                "ema200_4h": features.ema200_4h,
                "ema200_slope_pct": metrics["ema200_slope_pct"],
                "pullback_depth_pct": metrics["pullback_depth_pct"],
                "price_near_ema50_atr": metrics["price_near_ema50_atr"],
                "price_near_equal_low": metrics["price_near_equal_low"],
                "prior_swing_low": prior_swing_low,
                "pullback_low": pullback_low,
                "funding_8h": features.funding_8h,
                "funding_pct_60d": features.funding_pct_60d,
                "oi_zscore_60d": features.oi_zscore_60d,
                "oi_delta_pct": features.oi_delta_pct,
                "cvd_15m": features.cvd_15m,
                "cvd_bullish_divergence": features.cvd_bullish_divergence,
                "tfi_60s": features.tfi_60s,
                "force_order_rate_60s": features.force_order_rate_60s,
                "force_order_spike": features.force_order_spike,
                "rr_ratio": rr_ratio,
            },
        )

    def _evaluate(
        self,
        *,
        features: Features,
        snapshot: MarketSnapshot,
        regime: RegimeState | str,
        config: StrategyConfig,
    ) -> dict[str, Any]:
        reasons: list[str] = []
        metrics = self._structure_metrics(features=features, snapshot=snapshot)

        if not self.check_regime_allowed(regime):
            reasons.append(f"regime_blocked:{_regime_value(regime)}")
        if float(snapshot.price) <= 0:
            reasons.append("invalid_price")
        if float(features.ema200_4h) <= 0 or float(features.ema50_4h) <= 0:
            reasons.append("missing_trend_emas")
        if float(snapshot.price) <= float(features.ema200_4h):
            reasons.append("price_not_above_ema200")
        if float(features.ema50_4h) <= float(features.ema200_4h):
            reasons.append("ema50_not_above_ema200")
        if metrics["ema200_slope_pct"] < self.setup_config.min_ema200_slope_pct:
            reasons.append("ema200_slope_too_weak")
        if metrics["extension_pct"] > self.setup_config.max_extension_pct:
            reasons.append("trend_overextended")

        if not (self.setup_config.pullback_min_pct <= metrics["pullback_depth_pct"] <= self.setup_config.pullback_max_pct):
            reasons.append("pullback_depth_out_of_range")
        if not (metrics["price_near_ema50"] or metrics["price_near_equal_low"]):
            reasons.append("pullback_not_near_liquidity_level")
        if not metrics["maintains_higher_lows"]:
            reasons.append("higher_low_structure_broken")

        absorption_ok = (
            bool(features.cvd_bullish_divergence)
            or metrics["cvd_slope_proxy"] > 0.0
        )
        if not absorption_ok:
            reasons.append("absorption_not_confirmed")
        if float(features.tfi_60s) < self.setup_config.tfi_threshold:
            reasons.append("tfi_below_absorption_threshold")
        if float(features.oi_delta_pct) < self.setup_config.oi_participation_min_delta_pct:
            reasons.append("oi_unwind_not_participation")

        if float(features.funding_8h) > self.setup_config.funding_extreme:
            reasons.append("funding_crowded_long")
        if float(features.oi_zscore_60d) > self.setup_config.oi_extreme_zscore:
            reasons.append("oi_crowded")
        if float(features.atr_4h_norm) > self.setup_config.volatility_panic_atr_norm:
            reasons.append("volatility_panic")
        if bool(features.force_order_spike) and float(features.force_order_rate_60s) > self.setup_config.liquidation_rate_threshold:
            reasons.append("liquidation_cascade_active")
        if bool(features.sweep_detected) and features.sweep_side == "LOW" and not bool(features.reclaim_detected):
            reasons.append("low_sweep_without_reclaim")

        return {
            "accepted": not reasons,
            "reasons": reasons,
            "metrics": metrics,
        }

    def _structure_metrics(self, *, features: Features, snapshot: MarketSnapshot) -> dict[str, Any]:
        price = float(snapshot.price)
        atr_4h = max(float(features.atr_4h), 1e-8)
        candles_15m = list(snapshot.candles_15m or [])
        candles_4h = list(snapshot.candles_4h or [])
        recent_high = _recent_high(candles_15m, default=price, lookback=self.setup_config.recent_high_lookback_15m)
        pullback_low = _recent_low(candles_15m, default=price, lookback=self.setup_config.swing_low_lookback_15m)
        prior_swing_low = _prior_swing_low(candles_15m, default=pullback_low)
        ema200_slope_pct = _ema200_slope_pct(
            candles_4h,
            current_ema200=float(features.ema200_4h),
            lookback=self.setup_config.ema_slope_lookback_4h,
        )
        pullback_depth_pct = (recent_high - price) / max(recent_high, 1e-8)
        price_near_ema50_atr = abs(price - float(features.ema50_4h)) / atr_4h
        price_near_equal_low = any(
            abs(price - float(level)) / atr_4h <= self.setup_config.equal_low_proximity_atr
            for level in features.equal_lows
        )
        return {
            "recent_high": recent_high,
            "pullback_low": pullback_low,
            "prior_swing_low": prior_swing_low,
            "pullback_depth_pct": pullback_depth_pct,
            "price_near_ema50_atr": price_near_ema50_atr,
            "price_near_ema50": price_near_ema50_atr <= self.setup_config.ema_proximity_atr,
            "price_near_equal_low": price_near_equal_low,
            "maintains_higher_lows": price > prior_swing_low,
            "ema200_slope_pct": ema200_slope_pct,
            "extension_pct": (price - float(features.ema200_4h)) / max(float(features.ema200_4h), 1e-8),
            "cvd_slope_proxy": float(features.cvd_15m),
        }

    @staticmethod
    def _confluence_score(*, features: Features, metrics: dict[str, Any], rr_ratio: float) -> float:
        score = 0.0
        score += 2.0  # setup identity and trend regime
        if metrics["price_near_ema50"]:
            score += 1.0
        if metrics["price_near_equal_low"]:
            score += 1.0
        if bool(features.cvd_bullish_divergence):
            score += 1.5
        if float(features.tfi_60s) >= 0.30:
            score += 1.0
        if float(features.oi_delta_pct) >= 0.0:
            score += 0.5
        if rr_ratio >= 2.5:
            score += 1.0
        return score


def _regime_value(regime: RegimeState | str) -> str:
    return regime.value if isinstance(regime, RegimeState) else str(regime)


def _as_regime(regime: RegimeState | str) -> RegimeState:
    if isinstance(regime, RegimeState):
        return regime
    return RegimeState(str(regime))


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _candle_float(candle: dict[str, Any], key: str, default: float) -> float:
    try:
        return float(candle.get(key, default))
    except (TypeError, ValueError):
        return default


def _recent_high(candles: list[dict[str, Any]], *, default: float, lookback: int) -> float:
    scoped = candles[-max(lookback, 1) :]
    if not scoped:
        return default
    return max(_candle_float(candle, "high", default) for candle in scoped)


def _recent_low(candles: list[dict[str, Any]], *, default: float, lookback: int) -> float:
    scoped = candles[-max(lookback, 1) :]
    if not scoped:
        return default
    return min(_candle_float(candle, "low", default) for candle in scoped)


def _prior_swing_low(candles: list[dict[str, Any]], *, default: float) -> float:
    if len(candles) < 4:
        return default
    scoped = candles[-16:-1]
    if not scoped:
        return default
    return min(_candle_float(candle, "low", default) for candle in scoped)


def _ema200_slope_pct(candles_4h: list[dict[str, Any]], *, current_ema200: float, lookback: int) -> float:
    if current_ema200 <= 0:
        return 0.0
    scoped = candles_4h[-max(lookback + 1, 2) :]
    if len(scoped) < 2:
        return 0.001
    earlier_close = _candle_float(scoped[0], "close", current_ema200)
    latest_close = _candle_float(scoped[-1], "close", current_ema200)
    if earlier_close <= 0:
        return 0.0
    return (latest_close - earlier_close) / earlier_close


def _rr_long(*, entry: float, stop: float, target: float) -> float:
    risk = entry - stop
    if risk <= 0:
        return 0.0
    return (target - entry) / risk
