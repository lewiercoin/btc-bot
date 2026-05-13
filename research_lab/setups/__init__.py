"""Research-only setup implementations.

These modules are intentionally outside the live decision path.
"""

from research_lab.setups.base_setup import BaseSetup, SetupEvaluation
from research_lab.setups.post_cascade_momentum import (
    PostCascadeMomentumConfig,
    PostCascadeMomentumLong,
    PostCascadeMomentumShort,
    detect_cascade_direction,
)

__all__ = [
    "BaseSetup",
    "PostCascadeMomentumConfig",
    "PostCascadeMomentumLong",
    "PostCascadeMomentumShort",
    "SetupEvaluation",
    "detect_cascade_direction",
]
