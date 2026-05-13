"""Research-only setup implementations.

These modules are intentionally outside the live decision path.
"""

from research_lab.setups.base_setup import BaseSetup, SetupEvaluation
from research_lab.setups.crowded_unwind import (
    CrowdedUnwindConfig,
    CrowdedUnwindLong,
    CrowdedUnwindShort,
)

__all__ = [
    "BaseSetup",
    "CrowdedUnwindConfig",
    "CrowdedUnwindLong",
    "CrowdedUnwindShort",
    "SetupEvaluation",
]
