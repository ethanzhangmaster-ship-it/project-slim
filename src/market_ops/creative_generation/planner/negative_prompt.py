"""Phase 3.0: Negative Prompt Planner — wraps NegativePromptEngine for model-specific negatives.

Automatically appends model-appropriate negative prompts.
"""

from __future__ import annotations

from ..negative_prompt import NegativePromptEngine
from ..models.prompt_component import PromptComponent


class NegativePromptPlanner:
    """Plans negative prompts for a specific AI model.

    Uses the existing NegativePromptEngine but exposes it through
    the Prompt Planner component interface.
    """

    def __init__(self) -> None:
        self._engine = NegativePromptEngine()

    def plan(self, model: str, extra_terms: list[str] | None = None) -> PromptComponent:
        text = self._engine.generate(model, extra_terms=extra_terms, include_policy=True)
        return PromptComponent(
            dimension="negative_prompt",
            value=model,
            label=text[:80] + "..." if len(text) > 80 else text,
            weight=0.3,
        )

    def generate(self, model: str, extra_terms: list[str] | None = None) -> str:
        return self._engine.generate(model, extra_terms=extra_terms, include_policy=True)

    def list_models(self) -> list[str]:
        return self._engine.list_models()