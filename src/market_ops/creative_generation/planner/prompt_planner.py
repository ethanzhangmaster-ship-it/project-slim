"""Phase 3.0: Creative Prompt Planner — the main orchestrator.

Pipeline:
  Winner DNA
      │
      ▼
  Variation Engine (expand each dimension)
      │
      ▼
  Component Planners (composition, camera, lighting, etc.)
      │
      ▼
  Prompt Plans (collection of components)
      │
      ▼
  Prompt Renderer (model-specific rendering)
      │
      ▼
  Prompt Scorer (quality evaluation)
      │
      ▼
  Top-N Prompts

Usage:
    planner = CreativePromptPlanner(strategy="aggressive", model="lovart")
    prompts = planner.generate(dna, count=50)
    top20 = planner.top_n(prompts, n=20)
"""

from __future__ import annotations

import random
from typing import Any

from .variation_engine import VariationEngine
from .prompt_strategy import PromptStrategy, GrowthMode
from .composition_planner import CompositionPlanner
from .camera_planner import CameraPlanner
from .lighting_planner import LightingPlanner
from .color_planner import ColorPlanner
from .gameplay_planner import GameplayPlanner
from .reward_planner import RewardPlanner
from .typography_planner import TypographyPlanner
from .negative_prompt import NegativePromptPlanner
from .prompt_renderer import PromptRenderer
from .prompt_scorer import PromptScorer

from ..models.prompt_component import PromptComponent
from ..models.prompt_plan import PromptPlan
from ..models.prompt import Prompt, PromptScore


# DNA dimension → planner mapping
DNA_PLANNERS = {
    "composition": CompositionPlanner,
    "camera": CameraPlanner,
    "lighting": LightingPlanner,
    "palette": ColorPlanner,
    "gameplay": GameplayPlanner,
    "reward": RewardPlanner,
}


class CreativePromptPlanner:
    """Main orchestrator for the Creative Prompt Planner pipeline.

    Takes Winner DNA as input and produces scored, model-ready Prompts.
    """

    def __init__(
        self,
        strategy: str = "balanced",
        model: str = "lovart",
        aspect_ratio: str = "9:16",
        seed: int | None = None,
    ) -> None:
        self._strategy = PromptStrategy(strategy)
        self._model = model.lower()
        self._aspect_ratio = aspect_ratio
        self._rng = random.Random(seed) if seed is not None else random.Random()

        # Engines
        self._variation = VariationEngine(seed=seed)
        self._renderer = PromptRenderer()
        self._scorer = PromptScorer()
        self._negative = NegativePromptPlanner()

        # Planners (instantiated on demand)
        self._planners: dict[str, Any] = {}

    # ── Main API ──

    def generate(
        self,
        dna: dict[str, Any],
        count: int | None = None,
    ) -> list[Prompt]:
        """Generate prompts from a Winner DNA.

        Args:
            dna: Winner DNA dict with dimensions like character, camera, etc.
            count: Target number of prompts (None = strategy default).

        Returns:
            List of scored Prompt objects.
        """
        if count is None:
            count = self._strategy.total_prompts_target

        # Step 1: Generate variations for each dimension
        all_variants = self._variation.vary_all(dna, self._strategy.mode.value)

        # Step 2: Build PromptPlans from variation combinations
        plans = self._build_plans(dna, all_variants, count)

        # Step 3: Render each plan to a Prompt
        prompts = [self._renderer.render(plan) for plan in plans]

        # Step 4: Attach negative prompts
        neg_text = self._negative.generate(self._model)
        for p in prompts:
            p.negative_prompt = neg_text

        # Step 5: Score and filter
        prompts = self._scorer.score_batch(prompts)

        return prompts

    def generate_plan(self, dna: dict[str, Any]) -> PromptPlan:
        """Generate a single PromptPlan from DNA (without variations)."""
        return self._build_single_plan(dna)

    def top_n(self, prompts: list[Prompt], n: int = 20) -> list[Prompt]:
        """Return top N prompts by score."""
        return self._scorer.top_n(prompts, n)

    def render(self, plan: PromptPlan) -> Prompt:
        """Render a single PromptPlan to a Prompt."""
        prompt = self._renderer.render(plan)
        prompt.negative_prompt = self._negative.generate(self._model)
        return prompt

    # ── Internal: Plan Building ──

    def _build_plans(
        self, dna: dict[str, Any], all_variants: dict, count: int,
    ) -> list[PromptPlan]:
        """Build PromptPlans from variation combinations."""
        plans: list[PromptPlan] = []

        # Always include the original DNA as a plan
        if self._strategy.keep_original:
            plans.append(self._build_single_plan(dna))

        # Build plans from variation combinations
        dims = list(all_variants.keys())
        if not dims:
            return plans

        attempts = 0
        max_attempts = count * 3

        while len(plans) < count and attempts < max_attempts:
            attempts += 1

            # Pick one variation per dimension
            components = []
            for dim in dims:
                variants = all_variants[dim]
                if not variants:
                    continue
                variant = self._rng.choice(variants)
                components.append(PromptComponent(
                    dimension=dim,
                    value=variant.variant,
                    label=variant.label,
                    weight=1.0,
                ))

            # Add components from DNA that don't have variations
            for dim, value in dna.items():
                if dim not in dims and dim in DNA_PLANNERS:
                    planner = self._get_planner(dim)
                    components.append(planner.plan(str(value)))

            if components:
                plan = PromptPlan(
                    components=components,
                    strategy=self._strategy.mode.value,
                    seed=self._rng.randint(0, 999999),
                    aspect_ratio=self._aspect_ratio,
                    model=self._model,
                    source_dna=dna,
                )
                plans.append(plan)

        return plans[:count]

    def _build_single_plan(self, dna: dict[str, Any]) -> PromptPlan:
        """Build a single PromptPlan from DNA (no variations)."""
        components: list[PromptComponent] = []

        for dim, planner_cls in DNA_PLANNERS.items():
            if dim in dna:
                planner = self._get_planner(dim)
                components.append(planner.plan(str(dna[dim])))

        # Character
        character = dna.get("character", "witch")
        components.append(PromptComponent(
            dimension="character",
            value=str(character),
            label=str(character).replace("_", " ").title(),
            weight=1.0,
        ))

        # Emotion
        emotion = dna.get("emotion", "surprise")
        components.append(PromptComponent(
            dimension="emotion",
            value=str(emotion),
            label=str(emotion).replace("_", " ").title(),
            weight=0.7,
        ))

        # Style
        style = dna.get("style", "cartoon")
        components.append(PromptComponent(
            dimension="style",
            value=str(style),
            label=str(style).replace("_", " ").title(),
            weight=0.6,
        ))

        # Typography
        hook = dna.get("hook", "merge")
        typo_planner = TypographyPlanner()
        components.append(typo_planner.plan(str(hook)))

        return PromptPlan(
            components=components,
            strategy=self._strategy.mode.value,
            seed=self._rng.randint(0, 999999),
            aspect_ratio=self._aspect_ratio,
            model=self._model,
            source_dna=dna,
        )

    def _get_planner(self, dim: str) -> Any:
        if dim not in self._planners:
            planner_cls = DNA_PLANNERS.get(dim)
            if planner_cls:
                self._planners[dim] = planner_cls()
        return self._planners.get(dim)

    # ── Properties ──

    @property
    def strategy(self) -> PromptStrategy:
        return self._strategy

    @property
    def model(self) -> str:
        return self._model