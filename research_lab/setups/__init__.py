"""Research-only setup implementations.

These modules are intentionally outside the live decision path.
"""

from research_lab.setups.absorption_continuation import (
    AbsorptionContinuationConfig,
    AbsorptionContinuationLong,
)
from research_lab.setups.base_setup import BaseSetup, SetupEvaluation
from research_lab.setups.compression_breakout import (
    CompressionBreakoutConfig,
    CompressionBreakoutLong,
)

__all__ = [
    "AbsorptionContinuationConfig",
    "AbsorptionContinuationLong",
    "BaseSetup",
    "CompressionBreakoutConfig",
    "CompressionBreakoutLong",
    "SetupEvaluation",
]
