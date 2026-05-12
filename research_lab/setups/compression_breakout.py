from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from core.models import Features, MarketSnapshot, RegimeState, SignalCandidate
from research_lab.setups.base_setup import BaseSetup, SetupEvaluation
from settings import StrategyConfig


@dataclass(slots=True, frozen=True)
class CompressionBreakoutConfig:
    atr_percentile_threshold: float = 0.20
    atr_history_min_samples: int = 80
    compression_lookback_15m: int = 96
    breakout_lookback_15m: int = 48
    range_width_atr_max: float = 8.0
    min_breakout_atr: float = 0.10
    breakout_offset_atr: float = 0.05
    min_compression_duration_bars: int = 12
    tfi_breakout_threshold: float = 0.35
    oi_participation_min_delta_pct: float = 0.0
    funding_extreme: float = 0.0008
    oi_extreme_zscore: float = 2.5
    volatility_panic_atr_norm: float = 0.02885372
    liquidation_rate_threshold: float = 1.0
    invalidation_offset_atr: float = 0.20
    rr_ratio: float = 2.5
    min_rr: float = 2.0
    min_confluence_score: float = 5.0


class CompressionBreakoutLong(BaseSetup):
    """Research-only volatility compression to upside expansion setup.

    Regime usage:
    - Primary setup activation comes from internal compression detection:
      ATR percentile, range width, compression duration, and breakout trigger.
    - Regime is a veto/context layer: block trend/crowded/liquidation regimes,
      accept normal/compression states, and do not rely on RegimeEngine as the
      sole compression detector.
    """

    def __init__(self, setup_config: CompressionBreakoutConfig | None = None) -> None:
        self.setup_config = setup_config or CompressionBreakoutConfig()

    def get_setup_type(self) -> str:
        return "compression_breakout_long"

    def check_regime_allowed(self, regime: RegimeState | str) -> bool:
        blocked_regimes = {
            RegimeState.UPTREND.value,
            RegimeState.DOWNTREND.value,
            RegimeState.CROWDED_LEVERAGE.value,
            RegimeState.POST_LIQUIDATION.value,
        }
        return _regime_value(regime) not in blocked_regimes

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
        entry = price
        invalidation = float(metrics["recent_low"]) - (self.setup_config.invalidation_offset_atr * atr_15m)
        rr_ratio = _rr_long(entry=entry, stop=invalidation, target=entry + self.setup_config.rr_ratio * (entry - invalidation))
        if rr_ratio < self.setup_config.min_rr:
            return None
        tp1 = entry + (entry - invalidation) * self.setup_config.rr_ratio
        tp2 = entry + (entry - invalidation) * (self.setup_config.rr_ratio + 1.0)

        confluence_score = self._confluence_score(features=features, metrics=metrics, rr_ratio=rr_ratio)
        if confluence_score < self.setup_config.min_confluence_score:
            return None

        reasons = [
            f"setup_type={self.get_setup_type()}",
            f"regime={_regime_value(regime)}",
            "regime_veto=allowed",
            f"internal_compression_detected={metrics['internal_compression_detected']}",
            f"atr_percentile={metrics['atr_percentile']:.3f}",
            f"range_width_atr={metrics['range_width_atr']:.3f}",
            f"compression_duration_bars={metrics['compression_duration_bars']}",
            f"breakout_size_atr={metrics['breakout_size_atr']:.3f}",
            f"recent_high={metrics['recent_high']:.2f}",
            f"recent_low={metrics['recent_low']:.2f}",
            f"price={price:.2f}",
            f"tfi_60s={features.tfi_60s:.4f}",
            f"oi_delta_pct={features.oi_delta_pct:.6f}",
            f"funding_8h={features.funding_8h:.6f}",
            f"oi_zscore_60d={features.oi_zscore_60d:.3f}",
            f"atr_4h_norm={features.atr_4h_norm:.6f}",
            f"volatility_panic_threshold={self.setup_config.volatility_panic_atr_norm:.6f}",
            f"volatility_panic={features.atr_4h_norm > self.setup_config.volatility_panic_atr_norm}",
            f"rr_ratio={rr_ratio:.2f}",
            f"confluence_score={confluence_score:.2f}",
            "entry_timing=breakout_confirmation_before_retail_extension",
            "counterparty=range_faders_late_breakout_chasers",
        ]

        return SignalCandidate(
            signal_id=f"research-compression-{uuid4().hex}",
            timestamp=_to_utc(features.timestamp),
            direction="LONG",
            setup_type=self.get_setup_type(),
            entry_reference=entry,
            invalidation_level=invalidation,
            tp_reference_1=tp1,
            tp_reference_2=tp2,
            confluence_score=confluence_score,
            regime=_as_regime(regime),
            reasons=reasons,
            features_json={
                "atr_15m": features.atr_15m,
                "atr_4h": features.atr_4h,
                "atr_4h_norm": features.atr_4h_norm,
                "atr_percentile": metrics["atr_percentile"],
                "range_width_atr": metrics["range_width_atr"],
                "compression_duration_bars": metrics["compression_duration_bars"],
                "breakout_size_atr": metrics["breakout_size_atr"],
                "recent_high": metrics["recent_high"],
                "recent_low": metrics["recent_low"],
                "funding_8h": features.funding_8h,
                "funding_pct_60d": features.funding_pct_60d,
                "oi_zscore_60d": features.oi_zscore_60d,
                "oi_delta_pct": features.oi_delta_pct,
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
        if metrics["atr_history_samples"] < self.setup_config.atr_history_min_samples:
            reasons.append("atr_history_insufficient")
        if metrics["atr_percentile"] > self.setup_config.atr_percentile_threshold:
            reasons.append("atr_not_compressed")
        if metrics["range_width_atr"] > self.setup_config.range_width_atr_max:
            reasons.append("range_width_not_compressed")
        if metrics["compression_duration_bars"] < self.setup_config.min_compression_duration_bars:
            reasons.append("compression_duration_too_short")
        if not metrics["breakout_detected"]:
            reasons.append("no_breakout_detected")
        if metrics["breakout_size_atr"] < self.setup_config.min_breakout_atr:
            reasons.append("breakout_too_small")
        if float(features.tfi_60s) < self.setup_config.tfi_breakout_threshold:
            reasons.append("tfi_below_breakout_threshold")
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

        rr_ratio = _rr_long(
            entry=float(snapshot.price),
            stop=metrics["recent_low"] - self.setup_config.invalidation_offset_atr * max(float(features.atr_15m), 1e-8),
            target=float(snapshot.price) + self.setup_config.rr_ratio * (
                float(snapshot.price)
                - (metrics["recent_low"] - self.setup_config.invalidation_offset_atr * max(float(features.atr_15m), 1e-8))
            ),
        )
        if rr_ratio < self.setup_config.min_rr:
            reasons.append("rr_below_minimum")

        score = self._confluence_score(features=features, metrics=metrics, rr_ratio=rr_ratio)
        if score < self.setup_config.min_confluence_score:
            reasons.append("confluence_too_low")

        return {
            "accepted": not reasons,
            "reasons": reasons,
            "metrics": metrics | {"rr_ratio": rr_ratio, "confluence_score": score},
        }

    def _structure_metrics(self, *, features: Features, snapshot: MarketSnapshot) -> dict[str, Any]:
        price = float(snapshot.price)
        atr_15m = max(float(features.atr_15m), 1e-8)
        candles_15m = list(snapshot.candles_15m or [])
        prior_candles = candles_15m[:-1] if len(candles_15m) > 1 else candles_15m
        range_candles = prior_candles[-self.setup_config.compression_lookback_15m :]
        breakout_candles = prior_candles[-self.setup_config.breakout_lookback_15m :]
        recent_high = _recent_high(breakout_candles, default=price)
        recent_low = _recent_low(breakout_candles, default=price)
        range_high = _recent_high(range_candles, default=recent_high)
        range_low = _recent_low(range_candles, default=recent_low)
        range_width_atr = (range_high - range_low) / atr_15m
        breakout_level = recent_high + (self.setup_config.breakout_offset_atr * atr_15m)
        breakout_size_atr = (price - recent_high) / atr_15m
        atr_history = _float_history(snapshot.source_meta.get("research_atr_4h_norm_history"))
        atr_percentile = _percentile_rank(atr_history, float(features.atr_4h_norm))
        return {
            "atr_history_samples": len(atr_history),
            "atr_percentile": atr_percentile,
            "recent_high": recent_high,
            "recent_low": recent_low,
            "range_high": range_high,
            "range_low": range_low,
            "range_width_atr": range_width_atr,
            "breakout_level": breakout_level,
            "breakout_size_atr": breakout_size_atr,
            "breakout_detected": price > breakout_level,
            "compression_duration_bars": _compression_duration(
                atr_history=atr_history,
                current_atr_norm=float(features.atr_4h_norm),
                percentile_threshold=self.setup_config.atr_percentile_threshold,
            ),
            "internal_compression_detected": (
                atr_percentile <= self.setup_config.atr_percentile_threshold
                and range_width_atr <= self.setup_config.range_width_atr_max
            ),
        }

    def _confluence_score(self, *, features: Features, metrics: dict[str, Any], rr_ratio: float) -> float:
        score = 0.0
        score += 2.0
        if metrics["atr_percentile"] <= 0.10:
            score += 1.5
        elif metrics["atr_percentile"] <= self.setup_config.atr_percentile_threshold:
            score += 1.0
        if metrics["breakout_size_atr"] >= 1.0:
            score += 1.0
        elif metrics["breakout_size_atr"] >= self.setup_config.min_breakout_atr:
            score += 0.5
        if float(features.tfi_60s) >= 0.50:
            score += 1.0
        elif float(features.tfi_60s) >= self.setup_config.tfi_breakout_threshold:
            score += 0.5
        if float(features.oi_delta_pct) > 0.001:
            score += 0.5
        if metrics["compression_duration_bars"] >= 24:
            score += 0.5
        if rr_ratio >= 2.5:
            score += 1.0
        return round(score, 6)


def _regime_value(regime: RegimeState | str) -> str:
    return regime.value if isinstance(regime, RegimeState) else str(regime)


def _as_regime(regime: RegimeState | str) -> RegimeState:
    if isinstance(regime, RegimeState):
        return regime
    return RegimeState(str(regime))


def _recent_high(candles: list[dict[str, Any]], *, default: float) -> float:
    highs = [float(candle.get("high", default)) for candle in candles if candle.get("high") is not None]
    return max(highs) if highs else float(default)


def _recent_low(candles: list[dict[str, Any]], *, default: float) -> float:
    lows = [float(candle.get("low", default)) for candle in candles if candle.get("low") is not None]
    return min(lows) if lows else float(default)


def _float_history(raw: Any) -> list[float]:
    if not isinstance(raw, list):
        return []
    values: list[float] = []
    for item in raw:
        try:
            values.append(float(item))
        except (TypeError, ValueError):
            continue
    return values


def _percentile_rank(history: list[float], value: float) -> float:
    if not history:
        return 1.0
    ordered = sorted(history)
    below_or_equal = sum(1 for item in ordered if item <= value)
    return below_or_equal / len(ordered)


def _compression_duration(
    *,
    atr_history: list[float],
    current_atr_norm: float,
    percentile_threshold: float,
) -> int:
    if not atr_history:
        return 0
    threshold_index = max(0, min(len(atr_history) - 1, int(len(atr_history) * percentile_threshold)))
    threshold = sorted(atr_history)[threshold_index]
    duration = 0
    for value in reversed([*atr_history, current_atr_norm]):
        if value <= threshold:
            duration += 1
            continue
        break
    return duration


def _rr_long(*, entry: float, stop: float, target: float) -> float:
    risk = entry - stop
    if risk <= 0:
        return 0.0
    return max(0.0, target - entry) / risk


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
