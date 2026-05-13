"""Session Sweep Specialist — Variant 4 of sweep_reclaim family expansion.

Hypothesis: Liquidity sweeps during low-liquidity sessions (Asia hours,
00:00-08:00 UTC) have higher mean-reversion probability due to:
- Thinner order books → sweeps overshoot more → stronger snap-back
- Lower participation → less follow-through after sweep → reversion favored
- Microstructure mechanism (liquidity depth), NOT market structure (regime)

Design based on V1-V3 learnings:
- LONG ONLY: SHORT fails universally (0/2 pattern across all regimes)
- No regime filter: regime-agnostic (V1-V3 proved regime filtering degrades ER)
- Session filter: Asia hours (00:00-08:00 UTC) only
- No structure/volatility filters (didn't help in V1/V2)

Independence from trial-00095:
- trial-00095 is time-agnostic (trades any hour)
- Session filter creates differentiated opportunity set
- Overlap = subset of trial-00095 trades that happen during Asia hours
- If Asia-hour ER >> overall ER: session timing concentrates edge
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(slots=True)
class SessionSweepConfig:
    # --- Session window (UTC hours, inclusive start, exclusive end) ---
    session_start_hour: int = 0   # 00:00 UTC
    session_end_hour: int = 8     # 08:00 UTC (exclusive)

    # --- Direction: LONG only (SHORT fails 0/2 across V1-V3) ---
    directions: tuple[str, ...] = ("LONG",)

    # --- Session label for reporting ---
    session_label: str = "asia"


def is_in_session(
    timestamp: datetime,
    config: SessionSweepConfig,
) -> tuple[bool, str]:
    """Check if timestamp falls within the configured session window (UTC)."""
    if timestamp.tzinfo is None:
        utc_hour = timestamp.hour
    else:
        utc_hour = timestamp.astimezone(timezone.utc).hour

    if config.session_start_hour < config.session_end_hour:
        # Normal range (e.g. 0-8)
        in_session = config.session_start_hour <= utc_hour < config.session_end_hour
    else:
        # Wrapping range (e.g. 22-6)
        in_session = utc_hour >= config.session_start_hour or utc_hour < config.session_end_hour

    if in_session:
        return True, f"session_accepted|{config.session_label}|hour={utc_hour}"
    return False, f"session_rejected|{config.session_label}|hour={utc_hour}"


def get_session_directions(config: SessionSweepConfig) -> tuple[str, ...]:
    """Get allowed directions for session trades (LONG only per V1-V3 evidence)."""
    return config.directions
