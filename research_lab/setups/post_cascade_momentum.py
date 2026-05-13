from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from core.models import Features, MarketSnapshot, RegimeState, SignalCandidate
from research_lab.setups.base_setup import BaseSetup, SetupEvaluation
from settings import StrategyConfig


@dataclass(slots=True, frozen=True)
class PostCascadeMomentumConfig:
    force_lookback_minutes: int = 180
    min_force_orders: int = 5
    direction_threshold: float = 0.70
    tfi_threshold: float = 0.05
    invalidation_offset_atr: float = 0.35
    recent_low_lookback_15m: int = 12
    recent_high_lookback_15m: int = 12
    rr_ratio: float = 2.5
    min_rr: float = 2.0
    min_confluence_score: float = 4.0


class PostCascadeMomentumBase(BaseSetup):
    direction: str
    required_cascade_direction: str

    def __init__(self, setup_config: PostCascadeMomentumConfig | None = None) -> None:
        self.setup_config = setup_config or PostCascadeMomentumConfig()

    def check_regime_allowed(self, regime: RegimeState | str) -> bool:
        return _regime_value(regime) == RegimeState.POST_LIQUIDATION.value

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
            f"cascade_direction={metrics['cascade_direction']}",
            f"cascade_direction_ratio={metrics['cascade_direction_ratio']:.3f}",
            f"force_orders_lookback={metrics['force_orders_count']}",
            f"tfi_60s={features.tfi_60s:.4f}",
            f"momentum_confirmed={metrics['momentum_confirmed']}",
            f"price={price:.2f}",
            f"recent_low={metrics['recent_low']:.2f}",
            f"recent_high={metrics['recent_high']:.2f}",
            f"atr_15m={features.atr_15m:.4f}",
            f"rr_ratio={rr_ratio:.2f}",
            f"confluence_score={confluence:.2f}",
            "entry_timing=post_liquidation_aftermath_state",
            "not_late_crowded_unwind=True",
        ]
        return SignalCandidate(
            signal_id=f"research-post-cascade-{uuid4().hex}",
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
                "atr_4h_norm": features.atr_4h_norm,
                "tfi_60s": features.tfi_60s,
                "force_orders_lookback": metrics["force_orders_count"],
                "cascade_direction": metrics["cascade_direction"],
                "cascade_direction_ratio": metrics["cascade_direction_ratio"],
                "momentum_confirmed": metrics["momentum_confirmed"],
                "rr_ratio": rr_ratio,
            },
        )

    def _evaluate(self, *, features: Features, snapshot: MarketSnapshot, regime: RegimeState | str) -> dict[str, Any]:
        reasons: list[str] = []
        metrics = self._structure_metrics(features=features, snapshot=snapshot)
        if not self.check_regime_allowed(regime):
            reasons.append(f"regime_blocked:{_regime_value(regime)}")
        if metrics["force_orders_count"] < self.setup_config.min_force_orders:
            reasons.append("insufficient_force_order_history")
        if metrics["cascade_direction"] is None:
            reasons.append("cascade_direction_unclear")
        elif metrics["cascade_direction"] != self.required_cascade_direction:
            reasons.append(f"cascade_direction_mismatch:{metrics['cascade_direction']}")
        if not metrics["momentum_confirmed"]:
            reasons.append("momentum_not_confirmed")
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
        force_orders = list(snapshot.source_meta.get("research_force_orders_lookback", []) or [])
        cascade_direction, ratio, up_count, down_count = detect_cascade_direction(
            force_orders,
            threshold=self.setup_config.direction_threshold,
        )
        price = float(snapshot.price)
        candles = list(snapshot.candles_15m or [])
        recent_low = _recent_low(candles, default=price, lookback=self.setup_config.recent_low_lookback_15m)
        recent_high = _recent_high(candles, default=price, lookback=self.setup_config.recent_high_lookback_15m)
        tfi = float(features.tfi_60s)
        momentum = tfi >= self.setup_config.tfi_threshold if self.direction == "LONG" else tfi <= -self.setup_config.tfi_threshold
        return {
            "force_orders_count": len(force_orders),
            "up_force_orders": up_count,
            "down_force_orders": down_count,
            "cascade_direction": cascade_direction,
            "cascade_direction_ratio": ratio,
            "recent_low": recent_low,
            "recent_high": recent_high,
            "momentum_confirmed": momentum,
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
        score = 0.0
        if metrics["cascade_direction"] == self.required_cascade_direction:
            score += 2.0
        if metrics["cascade_direction_ratio"] >= 0.85:
            score += 1.0
        if metrics["momentum_confirmed"]:
            score += 1.0
        if metrics["force_orders_count"] >= self.setup_config.min_force_orders * 2:
            score += 0.5
        if rr_ratio >= 2.5:
            score += 1.0
        return round(score, 6)


class PostCascadeMomentumLong(PostCascadeMomentumBase):
    direction = "LONG"
    required_cascade_direction = "up"

    def get_setup_type(self) -> str:
        return "post_cascade_momentum_long"


class PostCascadeMomentumShort(PostCascadeMomentumBase):
    direction = "SHORT"
    required_cascade_direction = "down"

    def get_setup_type(self) -> str:
        return "post_cascade_momentum_short"


def detect_cascade_direction(
    force_orders: list[dict[str, Any]],
    *,
    threshold: float = 0.70,
) -> tuple[str | None, float, int, int]:
    up_count = 0
    down_count = 0
    for order in force_orders:
        side = str(order.get("side", "")).upper()
        if side in {"BUY", "SHORT"}:
            up_count += 1
        elif side in {"SELL", "LONG"}:
            down_count += 1
    total = up_count + down_count
    if total <= 0:
        return None, 0.0, up_count, down_count
    up_ratio = up_count / total
    down_ratio = down_count / total
    if up_ratio >= threshold:
        return "up", up_ratio, up_count, down_count
    if down_ratio >= threshold:
        return "down", down_ratio, up_count, down_count
    return None, max(up_ratio, down_ratio), up_count, down_count


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
