"""Range Sweep Specialist — Variant 1 of sweep_reclaim family expansion.

Hypothesis: Liquidity sweeps in range-bound markets (normal regime, horizontal
structure context) have highest mean-reversion probability due to tighter
structure boundaries and no directional bias.

Independence from trial-00095:
- Regime filter: normal only (trial-00095 is regime-agnostic)
- Direction: LONG and SHORT in normal (trial-00095 default: LONG only in normal)
- Structure slope filter: horizontal only (trial-00095 has no structure filter)
- Optional volatility cap: filters out high-volatility normal regimes
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class RangeSweepConfig:
    # --- Regime filter ---
    allowed_regime: str = "normal"

    # --- Structure slope filter ---
    structure_slope_window: int = 96  # cycles (24h at 15m)
    structure_slope_min_candles: int = 48  # minimum candles required (12h)
    structure_slope_atr_max: float = 0.3  # abs(slope_per_cycle / atr) threshold

    # --- Volatility filter ---
    volatility_filter_enabled: bool = True
    volatility_atr_norm_max: float = 0.015  # upper cap on atr_4h_norm

    # --- Direction whitelist override for NORMAL regime ---
    # Both LONG and SHORT allowed in range-bound markets (bidirectional reversion)
    normal_directions: tuple[str, ...] = ("LONG", "SHORT")


def compute_structure_slope(
    candles: list[dict[str, Any]],
    window: int,
    min_candles: int,
) -> float | None:
    """Compute ATR-normalized structure slope over a rolling window.

    Uses linear regression of candle midpoints: (high + low) / 2.
    Returns slope_per_cycle (not normalized). Caller normalizes by ATR.
    Returns None if insufficient data.
    """
    prior = candles[:-1] if len(candles) > 1 else candles
    tail = prior[-window:]
    if len(tail) < min_candles:
        return None

    n = len(tail)
    midpoints = [(float(c["high"]) + float(c["low"])) / 2.0 for c in tail]

    # Manual least-squares linear regression (no numpy dependency)
    # slope = (n * sum(x*y) - sum(x)*sum(y)) / (n * sum(x^2) - sum(x)^2)
    sum_x = 0.0
    sum_y = 0.0
    sum_xy = 0.0
    sum_x2 = 0.0
    for i, y in enumerate(midpoints):
        x = float(i)
        sum_x += x
        sum_y += y
        sum_xy += x * y
        sum_x2 += x * x

    denom = n * sum_x2 - sum_x * sum_x
    if abs(denom) < 1e-12:
        return 0.0

    slope = (n * sum_xy - sum_x * sum_y) / denom
    return slope


def is_structure_horizontal(
    candles: list[dict[str, Any]],
    atr_15m: float,
    config: RangeSweepConfig,
) -> tuple[bool, float | None, str]:
    """Check if structure is horizontal (low slope relative to ATR).

    Returns (is_horizontal, slope_atr_normalized, reason).
    """
    slope = compute_structure_slope(
        candles,
        window=config.structure_slope_window,
        min_candles=config.structure_slope_min_candles,
    )
    if slope is None:
        return False, None, "insufficient_structure_data"

    atr = max(atr_15m, 1e-8)
    slope_atr = slope / atr

    if abs(slope_atr) >= config.structure_slope_atr_max:
        return False, slope_atr, f"structure_slope_too_steep|slope_atr={slope_atr:.4f}"

    return True, slope_atr, "structure_horizontal"


def is_volatility_acceptable(
    atr_4h_norm: float,
    config: RangeSweepConfig,
) -> tuple[bool, str]:
    """Check if volatility is within acceptable range for range-bound trading."""
    if not config.volatility_filter_enabled:
        return True, "volatility_filter_disabled"

    if atr_4h_norm > config.volatility_atr_norm_max:
        return False, f"volatility_too_high|atr_4h_norm={atr_4h_norm:.6f}"

    return True, "volatility_acceptable"
