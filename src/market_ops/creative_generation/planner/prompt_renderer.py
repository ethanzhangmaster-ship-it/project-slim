"""Phase 3.0: Prompt Renderer — renders PromptPlan to model-specific prompt text.

Takes a PromptPlan (collection of components) and renders it to a natural
language prompt string optimized for the target AI model.

Each model has its own rendering style:
  - Lovart: structured, layered prompt
  - Flux: concise, keyword-dense
  - SDXL: tag-based, weighted
  - ComfyUI: workflow-compatible
"""

from __future__ import annotations

from ..models.prompt_plan import PromptPlan
from ..models.prompt import Prompt


class PromptRenderer:
    """Renders PromptPlan to model-specific Prompt text."""

    MODEL_RENDERERS = {
        "lovart": "_render_lovart",
        "flux": "_render_flux",
        "sdxl": "_render_sdxl",
        "comfyui": "_render_comfyui",
    }

    def render(self, plan: PromptPlan) -> Prompt:
        """Render a PromptPlan to a complete Prompt."""
        model = plan.model.lower()
        renderer = self.MODEL_RENDERERS.get(model, "_render_lovart")
        method = getattr(self, renderer)
        return method(plan)

    # ── Lovart Renderer ──

    def _render_lovart(self, plan: PromptPlan) -> Prompt:
        """Lovart: structured, layered prompt with clear sections."""
        character = plan.get_label("character", "cute witch")
        reward = plan.get_label("reward", "baby dragon")
        gameplay = plan.get_label("gameplay", "merge")
        camera = plan.get_label("camera", "45 degree overhead")
        lighting = plan.get_label("lighting", "warm golden")
        composition = plan.get_label("composition", "center")
        palette = plan.get_label("palette", "purple and gold")
        emotion = plan.get_label("emotion", "surprise")
        style = plan.get_label("style", "cartoon")

        positive = (
            f"High-converting Facebook mobile game advertisement for Merge Witches. "
            f"{character} character as the main focal point, {emotion} expression. "
            f"Holding a {reward}, magical reward moment. "
            f"{gameplay} gameplay visible with satisfying effects. "
            f"{composition} composition, {camera} camera angle. "
            f"{lighting} lighting, {palette} color palette. "
            f"{style} art style, mobile game aesthetic. "
            f"Ultra clean, clear visual hierarchy, strong call-to-action energy. "
            f"{plan.aspect_ratio} aspect ratio, high detail."
        )

        camera_str = plan.get_value("camera", "45_degree")
        lighting_str = plan.get_value("lighting", "warm")
        composition_str = plan.get_value("composition", "center")

        return Prompt(
            plan_id=plan.plan_id,
            positive_prompt=positive,
            negative_prompt="",
            camera=camera_str,
            lighting=lighting_str,
            composition=composition_str,
            seed=plan.seed,
            aspect_ratio=plan.aspect_ratio,
            model=plan.model,
            source_dna=plan.source_dna,
        )

    # ── Flux Renderer ──

    def _render_flux(self, plan: PromptPlan) -> Prompt:
        """Flux: concise, keyword-dense prompt."""
        character = plan.get_label("character", "cute witch")
        reward = plan.get_label("reward", "baby dragon")
        gameplay = plan.get_label("gameplay", "merge")
        camera = plan.get_label("camera", "medium shot")
        lighting = plan.get_label("lighting", "warm golden")
        palette = plan.get_label("palette", "purple gold")
        style = plan.get_label("style", "cartoon")

        positive = (
            f"Mobile game ad, {character}, holding {reward}, "
            f"{gameplay} gameplay, {camera}, {lighting}, "
            f"{palette} palette, {style}, "
            f"high quality, clean composition, {plan.aspect_ratio}"
        )

        return Prompt(
            plan_id=plan.plan_id,
            positive_prompt=positive,
            negative_prompt="",
            camera=plan.get_value("camera", "45_degree"),
            lighting=plan.get_value("lighting", "warm"),
            composition=plan.get_value("composition", "center"),
            seed=plan.seed,
            aspect_ratio=plan.aspect_ratio,
            model=plan.model,
            source_dna=plan.source_dna,
        )

    # ── SDXL Renderer ──

    def _render_sdxl(self, plan: PromptPlan) -> Prompt:
        """SDXL: tag-based, weighted prompt."""
        character = plan.get_value("character", "cute_witch")
        reward = plan.get_value("reward", "baby_dragon")
        gameplay = plan.get_value("gameplay", "merge")
        camera = plan.get_value("camera", "45_degree")
        lighting = plan.get_value("lighting", "warm")
        palette = plan.get_value("palette", "purple_gold")
        style = plan.get_value("style", "cartoon")

        positive = (
            f"(mobile game advertisement:1.2), "
            f"({character}:1.1), (holding {reward}:1.1), "
            f"({gameplay} gameplay:1.0), "
            f"({camera}:1.0), ({lighting} lighting:1.0), "
            f"({palette} color palette:1.0), "
            f"({style} style:1.0), "
            f"(high quality:1.2), (clean composition:1.1), "
            f"{plan.aspect_ratio}"
        )

        return Prompt(
            plan_id=plan.plan_id,
            positive_prompt=positive,
            negative_prompt="",
            camera=plan.get_value("camera", "45_degree"),
            lighting=plan.get_value("lighting", "warm"),
            composition=plan.get_value("composition", "center"),
            seed=plan.seed,
            aspect_ratio=plan.aspect_ratio,
            model=plan.model,
            source_dna=plan.source_dna,
        )

    # ── ComfyUI Renderer ──

    def _render_comfyui(self, plan: PromptPlan) -> Prompt:
        """ComfyUI: workflow-compatible, clean prompt."""
        character = plan.get_label("character", "cute witch")
        reward = plan.get_label("reward", "baby dragon")
        gameplay = plan.get_label("gameplay", "merge")
        camera = plan.get_label("camera", "medium shot")
        lighting = plan.get_label("lighting", "warm golden")
        palette = plan.get_label("palette", "purple and gold")
        style = plan.get_label("style", "cartoon")

        positive = (
            f"{character}, holding {reward}, {gameplay} gameplay, "
            f"{camera}, {lighting}, {palette} palette, "
            f"{style}, mobile game advertisement, "
            f"high quality, sharp focus, {plan.aspect_ratio}"
        )

        return Prompt(
            plan_id=plan.plan_id,
            positive_prompt=positive,
            negative_prompt="",
            camera=plan.get_value("camera", "45_degree"),
            lighting=plan.get_value("lighting", "warm"),
            composition=plan.get_value("composition", "center"),
            seed=plan.seed,
            aspect_ratio=plan.aspect_ratio,
            model=plan.model,
            source_dna=plan.source_dna,
        )