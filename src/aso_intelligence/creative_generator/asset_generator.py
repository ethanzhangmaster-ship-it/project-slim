"""
E16.6.8 — ASO Asset Generator.

Transforms creative briefs into generated store assets via prompt builder
and Lovart pipeline (dry-run in tests).

Pipeline:
    Creative Brief + Genome → PromptBuilder → Lovart/DryRun → CreativeCandidate[]
"""

from __future__ import annotations

from typing import List, Optional
from uuid import uuid4

from src.aso_intelligence.creative_generator.models import (
    ASOCreativeBrief,
    ASOCreativeGenome,
    CreativeCandidate,
    CreativeScore,
    StoreAssetType,
)


class PromptBuilder:
    """Build structured generation prompts from brief + genome."""

    def build(
        self,
        brief: ASOCreativeBrief,
        genome: ASOCreativeGenome,
        variant_index: int = 0,
    ) -> str:
        """Build a generation prompt for an image/Lovart pipeline.

        Structure:
          [asset type] for [game],
          objective: [objective],
          subject: [genome hook_character], reward: [genome hook_reward],
          composition: [genome comp_focus], [comp_hierarchy],
          emotion: curiosity [score], achievement [score],
          direction: [brief visual_direction],
          message: [brief key_message]
        """
        parts = [
            f"Generate a {brief.asset_type.value.lower()} for a mobile game.",
            f"Objective: {brief.objective.value.replace('_', ' ').lower()}.",
        ]

        if genome.hook_character and genome.hook_character != "none":
            parts.append(
                f"Subject: prominent {genome.hook_character.replace('_', ' ')}."
            )
        if genome.hook_reward and genome.hook_reward != "none":
            parts.append(f"Reward: show {genome.hook_reward}.")
        if genome.hook_transformation and genome.hook_transformation != "none":
            parts.append(
                f"Transformation: {genome.hook_transformation.replace('_', ' ')}."
            )

        parts.append(
            f"Composition: {genome.comp_focus} with {genome.comp_hierarchy} hierarchy."
        )
        if genome.emotion_curiosity > 0.5:
            parts.append("Create curiosity and intrigue.")
        if genome.emotion_achievement > 0.5:
            parts.append("Show achievement and satisfaction.")

        if brief.visual_direction:
            parts.append(f"Direction: {brief.visual_direction}")
        if brief.key_message:
            parts.append(f"Message: {brief.key_message}")

        return " ".join(parts)


class ASOAssetGenerator:
    """Generate store asset candidates from creative briefs.

    Uses ``PromptBuilder`` to create prompts, then passes them to a generator
    pipeline (Lovart in production, DryRun in tests/offline).
    """

    def __init__(self, prompt_builder: Optional[PromptBuilder] = None):
        self.prompt_builder = prompt_builder or PromptBuilder()

    # ------------------------------------------------------------------ #
    def generate_variants(
        self,
        brief: ASOCreativeBrief,
        genome: ASOCreativeGenome,
        count: int = 5,
        *,
        dry_run: bool = True,
    ) -> List[CreativeCandidate]:
        """Generate ``count`` creative variants from a brief + genome.

        In dry-run mode (default), each variant gets a generated prompt but
        no actual image — only structured metadata for testing/scoring.
        """
        candidates: List[CreativeCandidate] = []
        for i in range(count):
            prompt = self.prompt_builder.build(brief, genome, variant_index=i)

            # Slight prompt variation per variant
            variant_prompt = self._variate(prompt, i, count)

            candidate = CreativeCandidate(
                candidate_id=str(uuid4()),
                game_id=brief.game_id,
                asset_type=brief.asset_type,
                variant_label=f"Variant #{i + 1}",
                prompt_used=variant_prompt,
                genome=genome,
                source="dryrun" if dry_run else "lovart",
            )
            candidates.append(candidate)

        return candidates

    # ------------------------------------------------------------------ #
    def _variate(self, prompt: str, index: int, total: int) -> str:
        """Add slight variation to prompts for diversity.

        Each variant gets a different emphasis so candidates explore
        different visual approaches.
        """
        variations = [
            "",
            "Emphasise character emotions and facial expressions.",
            "Focus on reward visualisation and progress indicators.",
            "Show the merge action in the center of the frame.",
            "Highlight the transformation before and after.",
            "Make the scene feel magical and enchanting.",
            "Show multiple characters interacting.",
            "Focus on the collection aspect with visible inventory.",
            "Emphasise the upgrade path with clear level indicators.",
            "Create a sense of discovery and surprise.",
            "Show the most satisfying gameplay moment.",
            "Focus on reward screens with coins and gems.",
            "Emphasise the social aspect of sharing progress.",
            "Show a split-screen before/after merge comparison.",
            "Make the character the hero of the scene.",
            "Show the game world from a top-down perspective.",
            "Focus on puzzle-solving with visible challenge.",
            "Show the game's variety of characters and items.",
            "Emphasise quick gameplay loop in a single frame.",
            "Show end-game content to inspire long-term play.",
        ]
        # Select variation based on index
        if index < len(variations) and variations[index]:
            return f"{prompt} {variations[index]}"
        return prompt


__all__ = ["PromptBuilder", "ASOAssetGenerator"]
