from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from core.models import Features, MarketContext, SessionBucket, VolatilityBucket
from settings import ContextConfig


@dataclass(slots=True)
class ContextEngine:
    config: ContextConfig

    def classify(self, features: Features) -> MarketContext:
        """Stateless deterministic context eligibility classifier.

        Same features + same config -> same MarketContext.
        Does not receive RegimeState.
        """
        session = self._classify_session(features.timestamp)
        volatility = self._classify_volatility(features.atr_4h_norm)

        if self.config.neutral_mode:
            return MarketContext(
                session_bucket=session,
                volatility_bucket=volatility,
                context_eligible=True,
                context_block_reason=None,
                context_policy_version=self.config.policy_version,
                neutral_mode_active=True,
            )

        allowed = self.config.session_volatility_whitelist.get(session, ())
        eligible = volatility in allowed
        reason = None if eligible else f"context_unfavorable:{session.value}:{volatility.value}"

        return MarketContext(
            session_bucket=session,
            volatility_bucket=volatility,
            context_eligible=eligible,
            context_block_reason=reason,
            context_policy_version=self.config.policy_version,
            neutral_mode_active=False,
        )

    def _classify_session(self, timestamp: datetime) -> SessionBucket:
        h = timestamp.hour  # UTC required
        if h >= 22 or h < 7:
            return SessionBucket.ASIA
        if 7 <= h < 14:
            return SessionBucket.EU
        if 14 <= h < 16:
            return SessionBucket.EU_US
        return SessionBucket.US

    def _classify_volatility(self, atr_norm: float) -> VolatilityBucket:
        if atr_norm < self.config.atr_low_threshold:
            return VolatilityBucket.LOW
        if atr_norm > self.config.atr_high_threshold:
            return VolatilityBucket.HIGH
        return VolatilityBucket.NORMAL
