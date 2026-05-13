from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Any

from core.models import Direction, Features, MarketSnapshot, RegimeState, SignalCandidate
from research_lab.setups.base_setup import BaseSetup, SetupEvaluation


@dataclass(slots=True, frozen=True)
class VolatilityBreakoutConfig:
    atr_slope_lookback_bars: int = 6
    min_atr_slope_pct: float = 0.10
    min_atr_history_samples: int = 12
    range_lookback_15m: int = 12
    min_breakout_atr: float = 0.50
    tfi_threshold: float = 0.05
    volatility_panic_atr_norm: float = 0.029
    invalidation_offset_atr: float = 0.35
    rr_ratio_1: float = 2.5
    rr_ratio_2: float = 3.5
    min_rr: float = 2.0
    min_confluence_score: float = 4.0
    max_ema_extension_atr: float = 8.0


def detect_expansion_state(
    atr_history: list[float],
    *,
    lookback_bars: int = 6,
    min_slope_pct: float = 0.10,
    min_samples: int = 12,
) -> dict[str, Any]:
    """Detect rising ATR state using slope, not absolute low ATR level."""

    cleaned = [float(value) for value in atr_history if value is not None and float(value) > 0]
    samples = len(cleaned)
    if samples < max(min_samples, lookback_bars + 1):
        return {
            "samples": samples,
            "atr_current": cleaned[-1] if cleaned else 0.0,
            "atr_reference": 0.0,
            "atr_slope_pct": 0.0,
            "recent_avg": 0.0,
            "older_avg": 0.0,
            "recent_vs_older_pct": 0.0,
            "expansion_state": False,
            "reason": "insufficient_atr_history",
        }

    current = cleaned[-1]
    reference = cleaned[-(lookback_bars + 1)]
    atr_slope_pct = (current - reference) / max(reference, 1e-12)
    recent_window = cleaned[-lookback_bars:]
    older_window = cleaned[-(lookback_bars * 2) : -lookback_bars]
    recent_avg = mean(recent_window) if recent_window else current
    older_avg = mean(older_window) if older_window else reference
    recent_vs_older_pct = (recent_avg - older_avg) / max(older_avg, 1e-12)
    expansion_state = atr_slope_pct >= min_slope_pct and recent_avg > older_avg
    return {
        "samples": samples,
        "atr_current": current,
        "atr_reference": reference,
        "atr_slope_pct": atr_slope_pct,
        "recent_avg": recent_avg,
        "older_avg": older_avg,
        "recent_vs_older_pct": recent_vs_older_pct,
        "expansion_state": expansion_state,
        "reason": "expansion_state" if expansion_state else "atr_not_rising",
    }


class _VolatilityBreakoutBase(BaseSetup):
    direction: Direction

    def __init__(self, config: VolatilityBreakoutConfig | None = None) -> None:
        self.config = config or VolatilityBreakoutConfig()

    def get_setup_type(self) -> str:
        suffix = "long" if self.direction == "LONG" else "short"
        return f"volatility_breakout_{suffix}"

    def check_regime_allowed(self, regime: RegimeState) -> bool:
        return regime not in {
            RegimeState.COMPRESSION,
            RegimeState.CROWDED_LEVERAGE,
            RegimeState.POST_LIQUIDATION,
        }

    def evaluate_structure(
        self,
        *,
        snapshot: MarketSnapshot,
        features: Features,
        regime: RegimeState,
    ) -> SetupEvaluation:
        reasons: list[str] = []
        metrics = self._base_metrics(snapshot=snapshot, features=features, regime=regime)

        if not self.check_regime_allowed(regime):
            reasons.append(f"regime_blocked:{regime.value}")
            if regime == RegimeState.COMPRESSION:
                reasons.append("compression_entry_timing_violation")
            return SetupEvaluation(False, reasons, metrics)

        if float(features.atr_4h_norm) >= self.config.volatility_panic_atr_norm:
            reasons.append("atr_overheated_panic_threshold")
            return SetupEvaluation(False, reasons, metrics)

        expansion = metrics["expansion"]
        if not bool(expansion["expansion_state"]):
            reasons.append(str(expansion["reason"]))
            return SetupEvaluation(False, reasons, metrics)

        range_metrics = self._range_metrics(snapshot)
        metrics.update(range_metrics)
        if not range_metrics["range_ready"]:
            reasons.append("insufficient_range_history")
            return SetupEvaluation(False, reasons, metrics)

        price = float(snapshot.price)
        atr_15m = max(float(features.atr_15m), 1e-8)
        if self.direction == "LONG":
            breakout_size_atr = (price - float(range_metrics["range_high"])) / atr_15m
            ema_ok = float(features.ema50_4h) <= 0.0 or price > float(features.ema50_4h)
            momentum_ok = float(features.tfi_60s) > self.config.tfi_threshold
            extension_atr = (price - float(features.ema50_4h)) / atr_15m if float(features.ema50_4h) > 0 else 0.0
        else:
            breakout_size_atr = (float(range_metrics["range_low"]) - price) / atr_15m
            ema_ok = float(features.ema50_4h) <= 0.0 or price < float(features.ema50_4h)
            momentum_ok = float(features.tfi_60s) < -self.config.tfi_threshold
            extension_atr = (float(features.ema50_4h) - price) / atr_15m if float(features.ema50_4h) > 0 else 0.0

        metrics["breakout_size_atr"] = breakout_size_atr
        metrics["ema_alignment"] = ema_ok
        metrics["momentum_aligned"] = momentum_ok
        metrics["ema_extension_atr"] = extension_atr

        if breakout_size_atr < self.config.min_breakout_atr:
            reasons.append("breakout_too_small")
        if not ema_ok:
            reasons.append("ema_alignment_failed")
        if not momentum_ok:
            reasons.append("tfi_not_aligned")
        if extension_atr > self.config.max_ema_extension_atr:
            reasons.append("price_overextended_vs_ema")

        accepted = not reasons
        if accepted:
            reasons.extend(
                [
                    "expansion_state_active",
                    "structure_breaking_now",
                    "momentum_aligned",
                    "entry_timing=atr_expansion_state_not_compression",
                    "not_compression_breakout_2_0=True",
                ]
            )
        return SetupEvaluation(accepted, reasons, metrics)

    def generate_signal_candidate(
        self,
        *,
        snapshot: MarketSnapshot,
        features: Features,
        regime: RegimeState,
    ) -> SignalCandidate | None:
        evaluation = self.evaluate_structure(snapshot=snapshot, features=features, regime=regime)
        if not evaluation.accepted:
            return None

        price = float(snapshot.price)
        atr_15m = max(float(features.atr_15m), 1e-8)
        range_high = float(evaluation.metrics["range_high"])
        range_low = float(evaluation.metrics["range_low"])
        if self.direction == "LONG":
            stop = range_low - (self.config.invalidation_offset_atr * atr_15m)
            risk = price - stop
            target_1 = price + (risk * self.config.rr_ratio_1)
            target_2 = price + (risk * self.config.rr_ratio_2)
        else:
            stop = range_high + (self.config.invalidation_offset_atr * atr_15m)
            risk = stop - price
            target_1 = price - (risk * self.config.rr_ratio_1)
            target_2 = price - (risk * self.config.rr_ratio_2)

        if risk <= 0:
            return None

        rr_ratio = abs(target_1 - price) / max(risk, 1e-8)
        if rr_ratio < self.config.min_rr:
            return None

        confluence_score = self._confluence_score(evaluation.metrics)
        if confluence_score < self.config.min_confluence_score:
            return None

        features_json = self._features_json(
            snapshot=snapshot,
            features=features,
            regime=regime,
            evaluation=evaluation,
            rr_ratio=rr_ratio,
        )
        reasons = [
            f"setup_type={self.get_setup_type()}",
            f"regime={regime.value}",
            f"atr_slope_pct={evaluation.metrics['expansion']['atr_slope_pct']:.6f}",
            f"breakout_size_atr={evaluation.metrics['breakout_size_atr']:.6f}",
            f"tfi_60s={float(features.tfi_60s):.6f}",
            f"atr_4h_norm={float(features.atr_4h_norm):.8f}",
            f"rr_ratio={rr_ratio:.2f}",
            f"confluence_score={confluence_score:.2f}",
            *evaluation.reasons,
        ]
        return SignalCandidate(
            signal_id="",
            timestamp=snapshot.timestamp,
            direction=self.direction,
            setup_type=self.get_setup_type(),
            entry_reference=price,
            invalidation_level=stop,
            tp_reference_1=target_1,
            tp_reference_2=target_2,
            confluence_score=confluence_score,
            regime=regime,
            reasons=reasons,
            features_json=features_json,
        )

    def _base_metrics(
        self,
        *,
        snapshot: MarketSnapshot,
        features: Features,
        regime: RegimeState,
    ) -> dict[str, Any]:
        atr_history = list(snapshot.source_meta.get("research_atr_4h_norm_history") or [])
        if not atr_history or float(atr_history[-1]) != float(features.atr_4h_norm):
            atr_history.append(float(features.atr_4h_norm))
        expansion = detect_expansion_state(
            atr_history,
            lookback_bars=self.config.atr_slope_lookback_bars,
            min_slope_pct=self.config.min_atr_slope_pct,
            min_samples=self.config.min_atr_history_samples,
        )
        compression_entry = regime == RegimeState.COMPRESSION
        return {
            "timestamp": snapshot.timestamp.isoformat(),
            "direction": self.direction,
            "regime": regime.value,
            "price": float(snapshot.price),
            "atr_15m": float(features.atr_15m),
            "atr_4h_norm": float(features.atr_4h_norm),
            "tfi_60s": float(features.tfi_60s),
            "ema50_4h": float(features.ema50_4h),
            "ema200_4h": float(features.ema200_4h),
            "compression_entry": compression_entry,
            "expansion": expansion,
        }

    def _range_metrics(self, snapshot: MarketSnapshot) -> dict[str, Any]:
        candles = list(snapshot.candles_15m or [])
        prior = candles[:-1] if len(candles) > 1 else candles
        window = prior[-self.config.range_lookback_15m :]
        if len(window) < self.config.range_lookback_15m:
            return {
                "range_ready": False,
                "range_high": 0.0,
                "range_low": 0.0,
                "range_lookback_15m": self.config.range_lookback_15m,
            }
        highs = [float(candle["high"]) for candle in window]
        lows = [float(candle["low"]) for candle in window]
        return {
            "range_ready": True,
            "range_high": max(highs),
            "range_low": min(lows),
            "range_width": max(highs) - min(lows),
            "range_lookback_15m": self.config.range_lookback_15m,
        }

    def _confluence_score(self, metrics: dict[str, Any]) -> float:
        score = 0.0
        expansion = metrics["expansion"]
        if bool(expansion["expansion_state"]):
            score += 1.5
        if float(metrics.get("breakout_size_atr", 0.0)) >= self.config.min_breakout_atr:
            score += 1.2
        if bool(metrics.get("momentum_aligned", False)):
            score += 1.0
        if bool(metrics.get("ema_alignment", False)):
            score += 0.8
        if float(metrics.get("ema_extension_atr", 0.0)) <= self.config.max_ema_extension_atr:
            score += 0.5
        return score

    def _features_json(
        self,
        *,
        snapshot: MarketSnapshot,
        features: Features,
        regime: RegimeState,
        evaluation: SetupEvaluation,
        rr_ratio: float,
    ) -> dict[str, Any]:
        expansion = dict(evaluation.metrics["expansion"])
        return {
            "setup_type": self.get_setup_type(),
            "direction": self.direction,
            "price": float(snapshot.price),
            "regime": regime.value,
            "atr_15m": float(features.atr_15m),
            "atr_4h_norm": float(features.atr_4h_norm),
            "atr_slope_pct": float(expansion["atr_slope_pct"]),
            "recent_vs_older_pct": float(expansion["recent_vs_older_pct"]),
            "expansion_state": bool(expansion["expansion_state"]),
            "compression_entry": bool(evaluation.metrics["compression_entry"]),
            "range_high": float(evaluation.metrics["range_high"]),
            "range_low": float(evaluation.metrics["range_low"]),
            "breakout_size_atr": float(evaluation.metrics["breakout_size_atr"]),
            "tfi_60s": float(features.tfi_60s),
            "ema50_4h": float(features.ema50_4h),
            "ema200_4h": float(features.ema200_4h),
            "ema_extension_atr": float(evaluation.metrics["ema_extension_atr"]),
            "rr_ratio": float(rr_ratio),
            "entry_timing": "atr_expansion_state_not_compression",
        }


class VolatilityBreakoutLong(_VolatilityBreakoutBase):
    direction: Direction = "LONG"


class VolatilityBreakoutShort(_VolatilityBreakoutBase):
    direction: Direction = "SHORT"
