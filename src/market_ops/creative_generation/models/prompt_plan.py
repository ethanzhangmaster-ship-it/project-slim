"""Phase 3.0: PromptPlan — a complete plan for generating one image.

A PromptPlan is a collection of PromptComponents that together define
a complete creative direction. It is model-agnostic and can be rendered
by any PromptRenderer.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from .prompt_component import PromptComponent


@dataclass
class PromptPlan:
    """A complete creative plan ready for rendering to a model-specific prompt.

    Contains all components for one image generation, plus metadata
    about strategy, seed, and target model.
    """
    plan_id: str = field(default_factory=lambda: f"plan_{uuid.uuid4().hex[:12]}")
    components: list[PromptComponent] = field(default_factory=list)
    strategy: str = "balanced"       # conservative | balanced | aggressive | experimental
    seed: int = 0
    aspect_ratio: str = "9:16"
    model: str = "lovart"
    source_dna: dict | None = None   # reference to original Winner DNA

    def get_component(self, dimension: str) -> PromptComponent | None:
        for c in self.components:
            if c.dimension == dimension:
                return c
        return None

    def get_value(self, dimension: str, default: str = "") -> str:
        c = self.get_component(dimension)
        return c.value if c else default

    def get_label(self, dimension: str, default: str = "") -> str:
        c = self.get_component(dimension)
        return c.label if c else default

    def to_dict(self) -> dict:
        return {
            "plan_id": self.plan_id,
            "components": [c.to_dict() for c in self.components],
            "strategy": self.strategy,
            "seed": self.seed,
            "aspect_ratio": self.aspect_ratio,
            "model": self.model,
        }