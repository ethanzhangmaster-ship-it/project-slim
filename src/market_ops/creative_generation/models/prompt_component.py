"""Phase 3.0: PromptComponent — a single dimension of a prompt plan.

Each component represents one creative dimension (character, camera, lighting, etc.)
with its value, human-readable label, and weight in the final prompt.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PromptComponent:
    """A single creative dimension value in a prompt plan. Immutable."""
    dimension: str       # "character", "camera", "lighting", "composition", etc.
    value: str           # "cute_witch", "45_degree", "warm_golden", etc.
    label: str           # Human-readable: "Cute Witch", "45° Overhead", etc.
    weight: float = 1.0  # Importance weight in final prompt (0.0-1.0)

    def to_dict(self) -> dict:
        return {
            "dimension": self.dimension,
            "value": self.value,
            "label": self.label,
            "weight": self.weight,
        }