"""Special Regime Sweep Specialist — Variant 3 of sweep_reclaim family expansion.

Hypothesis: Liquidity sweeps in forced positioning regimes (crowded_leverage,
post_liquidation) have higher mean-reversion probability due to:
- Asymmetric pressure (funding extremes / liquidation cascades create forced
  positioning, not voluntary trend-following)
- Flush + snap-back: crowded leverage gets flushed out → rapid reversion
- Post-liquidation vacuum: forced sellers exhausted → buying pressure dominates

Design based on V1 + V2 learnings:
- LONG ONLY: SHORT fails in all regimes tested (0/2 pattern)
- No structure/volatility filters: didn't help in V1/V2
- Special regimes only: crowded_leverage + post_liquidation

Independence from trial-00095:
- trial-00095 whitelist: crowded_leverage=("LONG",), post_liquidation=("LONG","SHORT")
- Overlap expected: crowded_leverage LONG fully overlaps trial-00095
- post_liquidation LONG also overlaps trial-00095
- This variant tests whether special regimes CONCENTRATE the edge, not whether
  they provide independent trades. If ER >> trial-00095 overall, it suggests
  parameter refinement for these specific contexts could yield a variant.

NOTE: post_liquidation historically had 0 cycles in prior research. V3 may
effectively be crowded_leverage LONG only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class SpecialRegimeSweepConfig:
    # --- Regime filter ---
    allowed_regimes: tuple[str, ...] = ("crowded_leverage", "post_liquidation")

    # --- Direction: LONG only (SHORT fails 0/2 across V1+V2) ---
    directions: tuple[str, ...] = ("LONG",)

    # --- Optional: min cycles in current regime before trading ---
    # 0 = disabled (trade on first cycle of regime)
    min_regime_cycles: int = 0


def is_regime_special(regime: str, config: SpecialRegimeSweepConfig) -> tuple[bool, str]:
    """Check if regime is in allowed special set."""
    if regime in config.allowed_regimes:
        return True, f"regime_accepted|{regime}"
    return False, f"regime_rejected|{regime}"


def get_special_directions(config: SpecialRegimeSweepConfig) -> tuple[str, ...]:
    """Get allowed directions for special regimes (LONG only per V1+V2 evidence)."""
    return config.directions
