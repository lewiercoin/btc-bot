from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.models import Direction, Features, MarketSnapshot, RegimeState, SignalCandidate
from research_lab.setups.base_setup import BaseSetup, SetupEvaluation


@dataclass(slots=True, frozen=True)
class RegimeReversalConfig:
    max_entry_delay_cycles: int = 12
    min_persistence_cycles: int = 2
    tfi_threshold: float = 0.05
    structure_lookback_15m: int = 12
    invalidation_offset_atr: float = 0.35
    rr_ratio_1: float = 2.5
    rr_ratio_2: float = 3.5
    min_rr: float = 2.0
    min_confluence_score: float = 4.0
    max_ema_extension_atr: float = 8.0


def detect_regime_transition(
    regime_history: list[RegimeState | str],
    *,
    max_entry_delay_cycles: int = 12,
    min_persistence_cycles: int = 2,
) -> dict[str, Any]:
    """Detect confirmed directional regime exhaustion from RegimeEngine labels."""

    history = [_coerce_regime(value) for value in regime_history if value is not None]
    if len(history) < min_persistence_cycles + 1:
        return {
            "transition_active": False,
            "direction": None,
            "reason": "insufficient_regime_history",
            "prior_regime": None,
            "current_regime": history[-1].value if history else None,
            "cycles_since_transition": None,
            "current_persistence_cycles": len(history),
            "transition_id": None,
        }

    current = history[-1]
    run_start = len(history) - 1
    while run_start > 0 and history[run_start - 1] == current:
        run_start -= 1
    current_persistence = len(history) - run_start
    if run_start == 0:
        return {
            "transition_active": False,
            "direction": None,
            "reason": "no_prior_regime_transition",
            "prior_regime": None,
            "current_regime": current.value,
            "cycles_since_transition": None,
            "current_persistence_cycles": current_persistence,
            "transition_id": None,
        }

    prior = history[run_start - 1]
    cycles_since_transition = current_persistence - 1
    transition_id = f"{run_start}:{prior.value}->{current.value}"

    if current_persistence < min_persistence_cycles:
        return _transition_result(
            False,
            "current_regime_not_persistent",
            prior,
            current,
            cycles_since_transition,
            current_persistence,
            transition_id,
        )
    if cycles_since_transition > max_entry_delay_cycles:
        return _transition_result(
            False,
            "transition_window_closed",
            prior,
            current,
            cycles_since_transition,
            current_persistence,
            transition_id,
        )
    if prior == RegimeState.DOWNTREND and current in {RegimeState.UPTREND, RegimeState.NORMAL}:
        return _transition_result(
            True,
            "downtrend_exhaustion_confirmed",
            prior,
            current,
            cycles_since_transition,
            current_persistence,
            transition_id,
            direction="LONG",
        )
    if prior == RegimeState.UPTREND and current in {RegimeState.DOWNTREND, RegimeState.NORMAL}:
        return _transition_result(
            True,
            "uptrend_exhaustion_confirmed",
            prior,
            current,
            cycles_since_transition,
            current_persistence,
            transition_id,
            direction="SHORT",
        )
    return _transition_result(
        False,
        "not_directional_exhaustion_transition",
        prior,
        current,
        cycles_since_transition,
        current_persistence,
        transition_id,
    )


class _RegimeReversalBase(BaseSetup):
    direction: Direction

    def __init__(self, config: RegimeReversalConfig | None = None) -> None:
        self.config = config or RegimeReversalConfig()

    def get_setup_type(self) -> str:
        suffix = "long" if self.direction == "LONG" else "short"
        return f"regime_reversal_{suffix}"

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
            return SetupEvaluation(False, reasons, metrics)

        transition = metrics["transition"]
        if not bool(transition["transition_active"]):
            reasons.append(str(transition["reason"]))
            return SetupEvaluation(False, reasons, metrics)
        if transition["direction"] != self.direction:
            reasons.append("transition_direction_mismatch")
            return SetupEvaluation(False, reasons, metrics)

        structure = self._structure_metrics(snapshot=snapshot)
        metrics.update(structure)
        if not structure["structure_ready"]:
            reasons.append("insufficient_structure_history")
            return SetupEvaluation(False, reasons, metrics)

        price = float(snapshot.price)
        atr_15m = max(float(features.atr_15m), 1e-8)
        if self.direction == "LONG":
            momentum_ok = float(features.tfi_60s) > self.config.tfi_threshold
            ema_ok = float(features.ema50_4h) <= 0.0 or price > float(features.ema50_4h)
            extension_atr = (price - float(features.ema50_4h)) / atr_15m if float(features.ema50_4h) > 0 else 0.0
            structure_ok = price > float(structure["structure_mid"])
        else:
            momentum_ok = float(features.tfi_60s) < -self.config.tfi_threshold
            ema_ok = float(features.ema50_4h) <= 0.0 or price < float(features.ema50_4h)
            extension_atr = (float(features.ema50_4h) - price) / atr_15m if float(features.ema50_4h) > 0 else 0.0
            structure_ok = price < float(structure["structure_mid"])

        metrics["momentum_aligned"] = momentum_ok
        metrics["ema_alignment"] = ema_ok
        metrics["structure_alignment"] = structure_ok
        metrics["ema_extension_atr"] = extension_atr

        if not momentum_ok:
            reasons.append("tfi_not_aligned_with_new_regime")
        if not ema_ok:
            reasons.append("ema_alignment_failed")
        if not structure_ok:
            reasons.append("structure_not_confirmed")
        if extension_atr > self.config.max_ema_extension_atr:
            reasons.append("price_overextended_vs_ema")

        accepted = not reasons
        if accepted:
            reasons.extend(
                [
                    "regime_transition_confirmed",
                    "entry_after_shift_confirmation",
                    "not_top_bottom_anticipation=True",
                    f"cycles_since_transition={transition['cycles_since_transition']}",
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
        if self.direction == "LONG":
            stop = float(evaluation.metrics["structure_low"]) - (self.config.invalidation_offset_atr * atr_15m)
            risk = price - stop
            target_1 = price + (risk * self.config.rr_ratio_1)
            target_2 = price + (risk * self.config.rr_ratio_2)
        else:
            stop = float(evaluation.metrics["structure_high"]) + (self.config.invalidation_offset_atr * atr_15m)
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

        transition = evaluation.metrics["transition"]
        features_json = self._features_json(
            snapshot=snapshot,
            features=features,
            regime=regime,
            evaluation=evaluation,
            rr_ratio=rr_ratio,
        )
        reasons = [
            f"setup_type={self.get_setup_type()}",
            f"prior_regime={transition['prior_regime']}",
            f"current_regime={transition['current_regime']}",
            f"cycles_since_transition={transition['cycles_since_transition']}",
            f"transition_id={transition['transition_id']}",
            f"tfi_60s={float(features.tfi_60s):.6f}",
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

    def _base_metrics(self, *, snapshot: MarketSnapshot, features: Features, regime: RegimeState) -> dict[str, Any]:
        regime_history = list(snapshot.source_meta.get("research_regime_history") or [])
        if not regime_history or regime_history[-1] != regime.value:
            regime_history.append(regime.value)
        transition = detect_regime_transition(
            regime_history,
            max_entry_delay_cycles=self.config.max_entry_delay_cycles,
            min_persistence_cycles=self.config.min_persistence_cycles,
        )
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
            "transition": transition,
        }

    def _structure_metrics(self, *, snapshot: MarketSnapshot) -> dict[str, Any]:
        candles = list(snapshot.candles_15m or [])
        prior = candles[:-1] if len(candles) > 1 else candles
        window = prior[-self.config.structure_lookback_15m :]
        if len(window) < self.config.structure_lookback_15m:
            return {
                "structure_ready": False,
                "structure_high": 0.0,
                "structure_low": 0.0,
                "structure_mid": 0.0,
            }
        highs = [float(candle["high"]) for candle in window]
        lows = [float(candle["low"]) for candle in window]
        high = max(highs)
        low = min(lows)
        return {
            "structure_ready": True,
            "structure_high": high,
            "structure_low": low,
            "structure_mid": (high + low) / 2.0,
        }

    def _confluence_score(self, metrics: dict[str, Any]) -> float:
        score = 0.0
        if bool(metrics["transition"]["transition_active"]):
            score += 1.5
        if bool(metrics.get("momentum_aligned", False)):
            score += 1.0
        if bool(metrics.get("ema_alignment", False)):
            score += 1.0
        if bool(metrics.get("structure_alignment", False)):
            score += 1.0
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
        transition = dict(evaluation.metrics["transition"])
        return {
            "setup_type": self.get_setup_type(),
            "direction": self.direction,
            "price": float(snapshot.price),
            "regime": regime.value,
            "prior_regime": transition["prior_regime"],
            "current_regime": transition["current_regime"],
            "transition_id": transition["transition_id"],
            "cycles_since_transition": transition["cycles_since_transition"],
            "current_persistence_cycles": transition["current_persistence_cycles"],
            "atr_15m": float(features.atr_15m),
            "atr_4h_norm": float(features.atr_4h_norm),
            "tfi_60s": float(features.tfi_60s),
            "ema50_4h": float(features.ema50_4h),
            "ema200_4h": float(features.ema200_4h),
            "ema_extension_atr": float(evaluation.metrics["ema_extension_atr"]),
            "structure_high": float(evaluation.metrics["structure_high"]),
            "structure_low": float(evaluation.metrics["structure_low"]),
            "structure_mid": float(evaluation.metrics["structure_mid"]),
            "rr_ratio": float(rr_ratio),
            "entry_timing": "after_regime_shift_confirmation",
        }


class RegimeReversalLong(_RegimeReversalBase):
    direction: Direction = "LONG"


class RegimeReversalShort(_RegimeReversalBase):
    direction: Direction = "SHORT"


def _transition_result(
    active: bool,
    reason: str,
    prior: RegimeState,
    current: RegimeState,
    cycles_since_transition: int,
    current_persistence: int,
    transition_id: str,
    *,
    direction: Direction | None = None,
) -> dict[str, Any]:
    return {
        "transition_active": active,
        "direction": direction,
        "reason": reason,
        "prior_regime": prior.value,
        "current_regime": current.value,
        "cycles_since_transition": cycles_since_transition,
        "current_persistence_cycles": current_persistence,
        "transition_id": transition_id,
    }


def _coerce_regime(value: RegimeState | str) -> RegimeState:
    if isinstance(value, RegimeState):
        return value
    return RegimeState(str(value))
