from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from core.models import Features, MarketSnapshot, RegimeState, SignalCandidate


@dataclass(slots=True)
class SetupEvaluation:
    accepted: bool
    reasons: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)


class BaseSetup(ABC):
    """Research-only setup contract shared by portfolio setup experiments."""

    @abstractmethod
    def get_setup_type(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def check_regime_allowed(self, regime: RegimeState) -> bool:
        raise NotImplementedError

    @abstractmethod
    def evaluate_structure(
        self,
        *,
        snapshot: MarketSnapshot,
        features: Features,
        regime: RegimeState,
    ) -> SetupEvaluation:
        raise NotImplementedError

    @abstractmethod
    def generate_signal_candidate(
        self,
        *,
        snapshot: MarketSnapshot,
        features: Features,
        regime: RegimeState,
    ) -> SignalCandidate | None:
        raise NotImplementedError
