"""
AWS Fleet Scout - Scout the best AWS regions for spot or capacity block deployments.

This package provides tools for finding optimal AWS regions for EC2 compute
deployments, with advanced placement recommendations and composite utility scoring.
"""

from .commands.fleet.recommend import PlacementConstraints, PlacementOption, recommend_placement
from .commands.fleet.utility import (
    CompositeUtility,
    LatencyConfig,
    UtilityWeights,
    calculate_composite_utility,
)

__all__ = [
    "recommend_placement",
    "PlacementConstraints",
    "PlacementOption",
    "calculate_composite_utility",
    "UtilityWeights",
    "LatencyConfig",
    "CompositeUtility",
]

__version__ = "1.0.1"
