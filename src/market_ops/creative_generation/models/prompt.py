"""Phase 3.0: Prompt + PromptScore — the final rendered output.

Prompt is the model-ready output with positive/negative prompt text,
plus all metadata. PromptScore evaluates quality across 8 dimensions.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field


@dataclass(frozen=True)
class PromptScore:
    """Quality score for a generated prompt across 8 dimensions."""
    gameplay: float = 0.0       # 0-100
    composition: float = 0.0    # 0-100
    hook: float = 0.0           # 0-100
    reward: float = 0.0         # 0-100
    brand: float = 0.0          # 0-100
    readability: float = 0.0    # 0-100
    novelty: float = 0.0        # 0-100
    diversity: float = 0.0      # 0-100

    @property
    def total(self) -> float:
        dims = [self.gameplay, self.composition, self.hook, self.reward,
                self.brand, self.readability, self.novelty, self.diversity]
        return round(sum(dims) / len(dims), 1)

    def to_dict(self) -> dict:
        return {
            "gameplay": self.gameplay,
            "composition": self.composition,
            "hook": self.hook,
            "reward": self.reward,
            "brand": self.brand,
            "readability": self.readability,
            "novelty": self.novelty,
            "diversity": self.diversity,
            "total": self.total,
        }


@dataclass
class Prompt:
    """A complete, rendered prompt ready for AI image generation.

    This is the final output of the Prompt Planner pipeline:
    DNA → Components → Plan → Renderer → Prompt
    """
    prompt_id: str = field(default_factory=lambda: f"prompt_{uuid.uuid4().hex[:12]}")
    positive_prompt: str = ""
    negative_prompt: str = ""
    camera: str = ""
    lighting: str = ""
    composition: str = ""
    seed: int = 0
    aspect_ratio: str = "9:16"
    model: str = "lovart"
    score: PromptScore | None = None
    plan_id: str = ""
    source_dna: dict | None = None

    def to_dict(self) -> dict:
        result = {
            "prompt_id": self.prompt_id,
            "positive_prompt": self.positive_prompt,
            "negative_prompt": self.negative_prompt,
            "camera": self.camera,
            "lighting": self.lighting,
            "composition": self.composition,
            "seed": self.seed,
            "aspect_ratio": self.aspect_ratio,
            "model": self.model,
            "plan_id": self.plan_id,
        }
        if self.score:
            result["score"] = self.score.to_dict()
        return result