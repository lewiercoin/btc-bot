"""Trend Sweep Specialist — Variant 2 of sweep_reclaim family expansion.

Hypothesis: Liquidity sweeps in trending regimes (downtrend, uptrend) have
higher mean-reversion probability due to:
- Exhaustion dynamic (trend overextends → sweep → no follow-through → snap-back)
- Asymmetric positioning (trend attracts crowded positions → flush → reversion)
- Directional bias clarity (counter-trend sweep = failed continuation)

Direction logic (counter-trend reversion):
- Downtrend + sweep LOW → LONG (bears flush longs, failed continuation, snap-back)
- Uptrend + sweep HIGH → SHORT (bulls flush shorts, failed continuation, snap-back)

Independence from trial-00095:
- trial-00095 default whitelist: uptrend=() (no trades), downtrend=("LONG","SHORT")
- Trend Sweep: uptrend=("SHORT",), downtrend=("LONG",)
- ALL uptrend SHORT trades are fully independent (trial-00095 blocks uptrend entirely)
- Downtrend LONG trades partially overlap with trial-00095
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class TrendSweepConfig:
    # --- Regime filter ---
    allowed_regimes: tuple[str, ...] = ("downtrend", "uptrend")

    # --- Direction whitelist (counter-trend reversion) ---
    # Downtrend: only LONG (counter-trend snap-back after bear flush)
    # Uptrend: only SHORT (counter-trend snap-back after bull flush)
    downtrend_directions: tuple[str, ...] = ("LONG",)
    uptrend_directions: tuple[str, ...] = ("SHORT",)

    # --- Optional trend strength filter ---
    # Minimum consecutive cycles in current regime before trading
    # 0 = disabled (trade on first cycle of regime)
    min_trend_cycles: int = 0

    # --- Optional volatility filter (reused from V1) ---
    volatility_filter_enabled: bool = False
    volatility_atr_norm_min: float = 0.006  # minimum volatility (trending = higher vol)


def is_regime_trending(regime: str, config: TrendSweepConfig) -> tuple[bool, str]:
    """Check if regime is in allowed trending set."""
    if regime in config.allowed_regimes:
        return True, f"regime_accepted|{regime}"
    return False, f"regime_rejected|{regime}"


def get_trend_directions(regime: str, config: TrendSweepConfig) -> tuple[str, ...]:
    """Get allowed directions for a trending regime (counter-trend only)."""
    if regime == "downtrend":
        return config.downtrend_directions
    if regime == "uptrend":
        return config.uptrend_directions
    return ()


def is_volatility_sufficient(
    atr_4h_norm: float,
    config: TrendSweepConfig,
) -> tuple[bool, str]:
    """Check if volatility is sufficient for trending regime (not compressed)."""
    if not config.volatility_filter_enabled:
        return True, "volatility_filter_disabled"

    if atr_4h_norm < config.volatility_atr_norm_min:
        return False, f"volatility_too_low|atr_4h_norm={atr_4h_norm:.6f}"

    return True, "volatility_sufficient"
