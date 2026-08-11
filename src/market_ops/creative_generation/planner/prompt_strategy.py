"""Phase 3.0: Prompt Strategy — controls variation aggressiveness.

Strategy modes:
  - Conservative: minimal changes, stay close to proven DNA
  - Balanced: moderate exploration (default)
  - Aggressive: explore many directions
  - Experimental: radical changes, cross-category exploration
"""

from __future__ import annotations

from enum import Enum


class GrowthMode(str, Enum):
    """Variation strategy modes."""
    CONSERVATIVE = "conservative"
    BALANCED = "balanced"
    AGGRESSIVE = "aggressive"
    EXPERIMENTAL = "experimental"


STRATEGY_CONFIG = {
    GrowthMode.CONSERVATIVE: {
        "max_distance": 0.3,
        "min_variants_per_dim": 1,
        "max_variants_per_dim": 2,
        "total_prompts_target": 5,
        "keep_original": True,
        "crossover_enabled": False,
        "description": "Minimal changes, stay close to proven DNA. Best for scaling winners.",
    },
    GrowthMode.BALANCED: {
        "max_distance": 0.5,
        "min_variants_per_dim": 3,
        "max_variants_per_dim": 5,
        "total_prompts_target": 20,
        "keep_original": True,
        "crossover_enabled": True,
        "description": "Moderate exploration with controlled risk. Default mode.",
    },
    GrowthMode.AGGRESSIVE: {
        "max_distance": 0.7,
        "min_variants_per_dim": 5,
        "max_variants_per_dim": 8,
        "total_prompts_target": 50,
        "keep_original": True,
        "crossover_enabled": True,
        "description": "Explore many directions. Best for finding new winners.",
    },
    GrowthMode.EXPERIMENTAL: {
        "max_distance": 1.0,
        "min_variants_per_dim": 6,
        "max_variants_per_dim": 12,
        "total_prompts_target": 100,
        "keep_original": False,
        "crossover_enabled": True,
        "description": "Radical changes, cross-category exploration. Best for R&D.",
    },
}


class PromptStrategy:
    """Manages variation strategy for prompt generation.

    Controls how aggressively the Variation Engine explores
    creative space from a given Winner DNA.
    """

    def __init__(self, mode: GrowthMode | str = GrowthMode.BALANCED) -> None:
        if isinstance(mode, str):
            mode = GrowthMode(mode.lower())
        self._mode = mode
        self._config = STRATEGY_CONFIG[mode]

    @property
    def mode(self) -> GrowthMode:
        return self._mode

    @property
    def max_distance(self) -> float:
        return self._config["max_distance"]

    @property
    def max_variants_per_dim(self) -> int:
        return self._config["max_variants_per_dim"]

    @property
    def total_prompts_target(self) -> int:
        return self._config["total_prompts_target"]

    @property
    def keep_original(self) -> bool:
        return self._config["keep_original"]

    @property
    def crossover_enabled(self) -> bool:
        return self._config["crossover_enabled"]

    def to_dict(self) -> dict:
        return {"mode": self._mode.value, **self._config}