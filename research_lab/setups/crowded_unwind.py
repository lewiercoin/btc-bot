from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from core.models import Features, MarketSnapshot, RegimeState, SignalCandidate
from research_lab.setups.base_setup import BaseSetup, SetupEvaluation
from settings import StrategyConfig


@dataclass(slots=True, frozen=True)
class CrowdedUnwindConfig:
    funding_long_crowding_pct: float = 85.0
    funding_short_crowding_pct: float = 15.0
    funding_long_crowding_min: float = 0.0002
    funding_short_crowding_max: float = -0.0002
    oi_elevated_zscore: float = 1.5
    oi_extreme_zscore: float = 2.5
    oi_unwind_max_delta_pct: float = 0.0
    force_rate_min: float = 1.0 / 60.0
    tfi_flip_threshold: float = 0.10
    volatility_panic_atr_norm: float = 0.02885372
    invalidation_offset_atr: float = 0.35
    recent_low_lookback_15m: int = 12
    recent_high_lookback_15m: int = 12
    rr_ratio: float = 2.5
    min_rr: float = 2.0
    min_confluence_score: float = 5.0


class CrowdedUnwindBase(BaseSetup):
    direction: str
    crowded_side: str

    def __init__(self, setup_config: CrowdedUnwindConfig | None = None) -> None:
        self.setup_config = setup_config or CrowdedUnwindConfig()

    def check_regime_allowed(self, regime: RegimeState | str) -> bool:
        blocked = {
            RegimeState.UPTREND.value,
            RegimeState.DOWNTREND.value,
            RegimeState.COMPRESSION.value,
            RegimeState.POST_LIQUIDATION.value,
        }
        return _regime_value(regime) not in blocked

    def evaluate_structure(
        self,
        *,
        features: Features,
        snapshot: MarketSnapshot,
        regime: RegimeState | str,
        config: StrategyConfig,
    ) -> SetupEvaluation:
        checks = self._evaluate(features=features, snapshot=snapshot, regime=regime)
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
        checks = self._evaluate(features=features, snapshot=snapshot, regime=regime)
        if not checks["accepted"]:
            return None
        metrics = checks["metrics"]
        price = float(snapshot.price)
        atr_15m = max(float(features.atr_15m), 1e-8)
        if self.direction == "LONG":
            stop = float(metrics["recent_low"]) - self.setup_config.invalidation_offset_atr * atr_15m
            target_1 = price + self.setup_config.rr_ratio * (price - stop)
            target_2 = price + (self.setup_config.rr_ratio + 1.0) * (price - stop)
            rr_ratio = _rr_long(entry=price, stop=stop, target=target_1)
        else:
            stop = float(metrics["recent_high"]) + self.setup_config.invalidation_offset_atr * atr_15m
            target_1 = price - self.setup_config.rr_ratio * (stop - price)
            target_2 = price - (self.setup_config.rr_ratio + 1.0) * (stop - price)
            rr_ratio = _rr_short(entry=price, stop=stop, target=target_1)
        if rr_ratio < self.setup_config.min_rr:
            return None
        confluence = self._confluence_score(features=features, metrics=metrics, rr_ratio=rr_ratio)
        if confluence < self.setup_config.min_confluence_score:
            return None

        reasons = [
            f"setup_type={self.get_setup_type()}",
            f"regime={_regime_value(regime)}",
            "regime_veto=allowed",
            f"crowded_side={self.crowded_side}",
            f"funding_8h={features.funding_8h:.6f}",
            f"funding_percentile={features.funding_pct_60d:.3f}",
            f"funding_sma3={features.funding_sma3:.6f}",
            f"funding_sma9={features.funding_sma9:.6f}",
            f"oi_zscore_60d={features.oi_zscore_60d:.3f}",
            f"oi_delta_pct={features.oi_delta_pct:.6f}",
            f"oi_unwind_detected={metrics['oi_unwind_detected']}",
            f"force_order_spike={features.force_order_spike}",
            f"force_order_rate_60s={features.force_order_rate_60s:.4f}",
            f"force_rate_threshold={self.setup_config.force_rate_min:.4f}",
            f"tfi_60s={features.tfi_60s:.4f}",
            f"tfi_flip_detected={metrics['tfi_flip_detected']}",
            f"price={price:.2f}",
            f"atr_4h_norm={features.atr_4h_norm:.6f}",
            f"rr_ratio={rr_ratio:.2f}",
            f"confluence_score={confluence:.2f}",
            "entry_timing=force_spike_unwind_starting_now",
            "counterparty=overleveraged_traders_forced_to_exit",
        ]
        return SignalCandidate(
            signal_id=f"research-crowded-{uuid4().hex}",
            timestamp=_to_utc(features.timestamp),
            direction=self.direction,
            setup_type=self.get_setup_type(),
            entry_reference=price,
            invalidation_level=stop,
            tp_reference_1=target_1,
            tp_reference_2=target_2,
            confluence_score=confluence,
            regime=_as_regime(regime),
            reasons=reasons,
            features_json={
                "atr_15m": features.atr_15m,
                "atr_4h": features.atr_4h,
                "atr_4h_norm": features.atr_4h_norm,
                "funding_8h": features.funding_8h,
                "funding_sma3": features.funding_sma3,
                "funding_sma9": features.funding_sma9,
                "funding_pct_60d": features.funding_pct_60d,
                "oi_zscore_60d": features.oi_zscore_60d,
                "oi_delta_pct": features.oi_delta_pct,
                "force_order_rate_60s": features.force_order_rate_60s,
                "force_order_spike": features.force_order_spike,
                "tfi_60s": features.tfi_60s,
                "tfi_flip_detected": metrics["tfi_flip_detected"],
                "oi_unwind_detected": metrics["oi_unwind_detected"],
                "crowded_side": self.crowded_side,
                "rr_ratio": rr_ratio,
            },
        )

    def _evaluate(self, *, features: Features, snapshot: MarketSnapshot, regime: RegimeState | str) -> dict[str, Any]:
        reasons: list[str] = []
        metrics = self._structure_metrics(features=features, snapshot=snapshot)
        if not self.check_regime_allowed(regime):
            reasons.append(f"regime_blocked:{_regime_value(regime)}")
        if float(snapshot.price) <= 0:
            reasons.append("invalid_price")
        if not self._funding_extreme(features):
            reasons.append("funding_not_extreme")
        if abs(float(features.oi_zscore_60d)) < self.setup_config.oi_elevated_zscore:
            reasons.append("oi_not_elevated")
        if not bool(features.force_order_spike):
            reasons.append("no_force_spike")
        if float(features.force_order_rate_60s) < self.setup_config.force_rate_min:
            reasons.append("force_rate_below_threshold")
        if not (metrics["tfi_flip_detected"] or metrics["oi_unwind_detected"]):
            reasons.append("unwind_confirmation_missing")
        if self._funding_normalized(features):
            reasons.append("funding_already_normalized")
        if float(features.atr_4h_norm) > self.setup_config.volatility_panic_atr_norm:
            reasons.append("volatility_panic")

        rr_ratio = self._rr_for_metrics(features=features, snapshot=snapshot, metrics=metrics)
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
        candles = list(snapshot.candles_15m or [])
        recent_low = _recent_low(candles, default=price, lookback=self.setup_config.recent_low_lookback_15m)
        recent_high = _recent_high(candles, default=price, lookback=self.setup_config.recent_high_lookback_15m)
        tfi = float(features.tfi_60s)
        if self.direction == "LONG":
            tfi_flip = tfi >= self.setup_config.tfi_flip_threshold
        else:
            tfi_flip = tfi <= -self.setup_config.tfi_flip_threshold
        oi_unwind = float(features.oi_delta_pct) <= self.setup_config.oi_unwind_max_delta_pct
        return {
            "recent_low": recent_low,
            "recent_high": recent_high,
            "tfi_flip_detected": tfi_flip,
            "oi_unwind_detected": oi_unwind,
        }

    def _rr_for_metrics(self, *, features: Features, snapshot: MarketSnapshot, metrics: dict[str, Any]) -> float:
        price = float(snapshot.price)
        atr_15m = max(float(features.atr_15m), 1e-8)
        if self.direction == "LONG":
            stop = float(metrics["recent_low"]) - self.setup_config.invalidation_offset_atr * atr_15m
            return _rr_long(entry=price, stop=stop, target=price + self.setup_config.rr_ratio * (price - stop))
        stop = float(metrics["recent_high"]) + self.setup_config.invalidation_offset_atr * atr_15m
        return _rr_short(entry=price, stop=stop, target=price - self.setup_config.rr_ratio * (stop - price))

    def _confluence_score(self, *, features: Features, metrics: dict[str, Any], rr_ratio: float) -> float:
        score = 2.0
        if self._funding_very_extreme(features):
            score += 1.5
        elif self._funding_extreme(features):
            score += 1.0
        if float(features.force_order_rate_60s) >= self.setup_config.force_rate_min * 2.0:
            score += 1.0
        elif bool(features.force_order_spike):
            score += 0.5
        if abs(float(features.oi_zscore_60d)) >= self.setup_config.oi_extreme_zscore:
            score += 1.0
        elif abs(float(features.oi_zscore_60d)) >= self.setup_config.oi_elevated_zscore:
            score += 0.5
        if metrics["tfi_flip_detected"]:
            score += 1.0
        if metrics["oi_unwind_detected"]:
            score += 0.5
        if rr_ratio >= 2.5:
            score += 1.0
        return round(score, 6)

    def _funding_extreme(self, features: Features) -> bool:
        raise NotImplementedError

    def _funding_very_extreme(self, features: Features) -> bool:
        raise NotImplementedError

    def _funding_normalized(self, features: Features) -> bool:
        return 15.0 < float(features.funding_pct_60d) < 85.0


class CrowdedUnwindLong(CrowdedUnwindBase):
    direction = "LONG"
    crowded_side = "shorts"

    def get_setup_type(self) -> str:
        return "crowded_unwind_long"

    def _funding_extreme(self, features: Features) -> bool:
        return (
            float(features.funding_pct_60d) <= self.setup_config.funding_short_crowding_pct
            or float(features.funding_8h) <= self.setup_config.funding_short_crowding_max
        )

    def _funding_very_extreme(self, features: Features) -> bool:
        return float(features.funding_pct_60d) <= 5.0


class CrowdedUnwindShort(CrowdedUnwindBase):
    direction = "SHORT"
    crowded_side = "longs"

    def get_setup_type(self) -> str:
        return "crowded_unwind_short"

    def _funding_extreme(self, features: Features) -> bool:
        return (
            float(features.funding_pct_60d) >= self.setup_config.funding_long_crowding_pct
            or float(features.funding_8h) >= self.setup_config.funding_long_crowding_min
        )

    def _funding_very_extreme(self, features: Features) -> bool:
        return float(features.funding_pct_60d) >= 95.0


def _regime_value(regime: RegimeState | str) -> str:
    return regime.value if isinstance(regime, RegimeState) else str(regime)


def _as_regime(regime: RegimeState | str) -> RegimeState:
    if isinstance(regime, RegimeState):
        return regime
    return RegimeState(str(regime))


def _recent_low(candles: list[dict[str, Any]], *, default: float, lookback: int) -> float:
    rows = candles[-lookback:] if candles else []
    lows = [float(candle.get("low", default)) for candle in rows if candle.get("low") is not None]
    return min(lows) if lows else float(default)


def _recent_high(candles: list[dict[str, Any]], *, default: float, lookback: int) -> float:
    rows = candles[-lookback:] if candles else []
    highs = [float(candle.get("high", default)) for candle in rows if candle.get("high") is not None]
    return max(highs) if highs else float(default)


def _rr_long(*, entry: float, stop: float, target: float) -> float:
    risk = entry - stop
    if risk <= 0:
        return 0.0
    return max(0.0, target - entry) / risk


def _rr_short(*, entry: float, stop: float, target: float) -> float:
    risk = stop - entry
    if risk <= 0:
        return 0.0
    return max(0.0, entry - target) / risk


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
