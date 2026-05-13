from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from core.models import Features, MarketSnapshot, RegimeState, SignalCandidate
from settings import StrategyConfig


@dataclass(slots=True)
class SetupEvaluation:
    accepted: bool
    reasons: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)


class BaseSetup(ABC):
    """Research-only setup contract for offline hypothesis validation."""

    @abstractmethod
    def get_setup_type(self) -> str:
        """Return the setup identifier."""

    @abstractmethod
    def check_regime_allowed(self, regime: RegimeState | str) -> bool:
        """Return True when this setup is allowed to evaluate in the regime."""

    @abstractmethod
    def evaluate_structure(
        self,
        *,
        features: Features,
        snapshot: MarketSnapshot,
        regime: RegimeState | str,
        config: StrategyConfig,
    ) -> SetupEvaluation:
        """Evaluate setup-specific market structure without producing a signal."""

    @abstractmethod
    def generate_signal_candidate(
        self,
        *,
        features: Features,
        snapshot: MarketSnapshot,
        regime: RegimeState | str,
        config: StrategyConfig,
    ) -> SignalCandidate | None:
        """Generate a fully explained research candidate or return None."""

    def get_metrics_tags(self) -> dict[str, str]:
        return {"setup_type": self.get_setup_type()}
