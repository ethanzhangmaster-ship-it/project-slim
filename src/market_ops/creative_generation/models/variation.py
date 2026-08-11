"""Phase 3.0: Variation — a single variant of one dimension.

Used by VariationEngine to track individual variations applied
to a dimension value.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Variation:
    """A single variation of a dimension value. Immutable."""
    dimension: str       # "character", "camera", etc.
    original: str        # original value from DNA
    variant: str         # varied value
    label: str           # human-readable label
    distance: float = 0.0  # how far from original (0.0 = same, 1.0 = radical)

    def to_dict(self) -> dict:
        return {
            "dimension": self.dimension,
            "original": self.original,
            "variant": self.variant,
            "label": self.label,
            "distance": self.distance,
        }