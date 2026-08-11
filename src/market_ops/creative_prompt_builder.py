"""Phase 2: Creative Prompt Builder.

Converts CreativeGenerationSpec → Lovart-optimized prompt text.

Transforms structured ad specifications into natural-language
prompts that produce high-converting mobile game advertisements,
not fantasy illustrations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .creative_blueprint_validator import CreativeGenerationSpec


# ═══════════════════════════════════════════════════════════
# 1. Prompt DNA Library (inline)
# ═══════════════════════════════════════════════════════════

HOOK_PHRASES: dict[str, str] = {
    "character_showcase": "A cute witch character as the main focal point, showcasing magical transformation",
    "merge_upgrade": "Visible merge board with items combining into more powerful objects",
    "evolution": "Dragon or witch evolution sequence showing dramatic transformation",
    "general_showcase": "Beautiful game world with magical creatures and items",
}

COMPOSITION_PHRASES: dict[str, str] = {
    "center": "Large central subject dominating the frame, strong focal point",
    "top": "Key action and reward visible in the upper portion",
    "balanced": "Evenly distributed elements across the frame",
    "bottom": "Merge board and interaction area at the bottom",
}

COLOR_PHRASES: dict[str, str] = {
    "purple": "Rich purple magical fantasy atmosphere with glowing effects",
    "blue_cool": "Cool mystical blue tones with ethereal lighting",
    "warm_golden": "Warm golden light suggesting achievement and reward",
    "green": "Enchanted forest green with natural magical elements",
    "warm_red": "Intense fire magic red with dramatic energy",
}

REWARD_PHRASES: dict[str, str] = {
    "evolution": "dramatic evolution transformation with magical particle effects",
    "transformation": "visible transformation sequence with before-and-after impact",
    "level_up": "level-up celebration with upgrade visual effects",
    "unlock": "unlocking animation revealing a powerful new character or item",
    "merge": "satisfying merge result showing the combined powerful outcome",
}

EMOTION_PHRASES: dict[str, str] = {
    "surprise": "strong surprise and wow moment",
    "excitement": "exciting achievement feeling",
    "satisfaction": "deep satisfaction of progress",
    "delight": "delightful and charming reveal",
    "awe": "awe-inspiring magical spectacle",
}

# Style guard — prevents Lovart from drifting into fantasy illustration
STYLE_GUARD = (
    "Mobile game advertisement creative style, "
    "not fantasy artwork, not illustration poster, "
    "not cinematic concept art. "
    "Clean game ad feeling, clear visual hierarchy, "
    "strong call-to-action energy."
)

# Negative prompt — what to avoid
NEGATIVE_PROMPT = (
    "illustration, painting, concept art, cinematic, "
    "movie poster, book cover, complex background, "
    "too much text, watermark, logo, blurry, low quality, "
    "realistic 3D, photorealistic, portrait photography"
)


# ═══════════════════════════════════════════════════════════
# 2. Creative Prompt Builder
# ═══════════════════════════════════════════════════════════

@dataclass
class LovartPrompt:
    """A complete prompt ready for Lovart generation."""
    prompt_id: str = ""
    prompt_text: str = ""
    negative_prompt: str = ""
    hook_type: str = ""
    source_blueprint: str = ""
    confidence: float = 0.0
    style: str = "mobile_game_ad"
    format: str = "1080x1080"

    def to_dict(self) -> dict[str, Any]:
        return {
            "prompt_id": self.prompt_id,
            "prompt_text": self.prompt_text,
            "negative_prompt": self.negative_prompt,
            "hook_type": self.hook_type,
            "source_blueprint": self.source_blueprint,
            "confidence": self.confidence,
            "style": self.style,
            "format": self.format,
        }


class CreativePromptBuilder:
    """Builds Lovart-optimized prompts from CreativeGenerationSpecs.

    The prompt is structured in layers:
      1. Game context (what game this is)
      2. Main hook (what grabs attention)
      3. Scene description (what the user sees)
      4. Gameplay moment (what's happening)
      5. Reward moment (the payoff)
      6. Visual style (colors, composition)
      7. Style guard (prevents fantasy drift)
    """

    def build(self, spec: CreativeGenerationSpec, prompt_id: str = "") -> LovartPrompt:
        """Build a single Lovart prompt from a GenerationSpec."""
        s = spec.hook_scene
        g = spec.gameplay_sequence
        r = spec.reward_moment
        v = spec.visual_constraints

        # Layer 1: Game context
        game_context = (
            "A high-converting Facebook mobile game advertisement for "
            "Merge Witches, a merge evolution puzzle game."
        )

        # Layer 2: Hook
        hook = HOOK_PHRASES.get(s.character, HOOK_PHRASES.get("character_showcase", ""))
        if s.attention_reason:
            hook += f", {s.attention_reason.replace('_', ' ')}"

        # Layer 3: Scene
        scene = (
            f"{s.character.replace('_', ' ')} placed in {s.position} position, "
            f"{s.action.replace('_', ' ')} pose"
        )

        # Layer 4: Gameplay
        gameplay = (
            f"Merge evolution gameplay visible: "
            f"{g.state_before.replace('_', ' ')} transforming into "
            f"{g.state_after.replace('_', ' ')} "
            f"through {g.interaction.replace('_', ' ')}. "
            f"{g.visual_change} visual transformation."
        )

        # Layer 5: Reward
        reward = (
            f"{r.reward_object} {r.reward_action.replace('_', ' ')} moment, "
            f"{EMOTION_PHRASES.get(r.reward_emotion, 'strong achievement feeling')}"
        )

        # Layer 6: Visual
        color = COLOR_PHRASES.get(v.color_palette, "fantasy color palette")
        composition = COMPOSITION_PHRASES.get(v.composition, "balanced composition")
        visual = f"{color}. {composition}."

        # Assemble
        prompt_text = (
            f"{game_context}\n\n"
            f"Main Hook: {hook}\n\n"
            f"Scene: {scene}\n\n"
            f"Gameplay: {gameplay}\n\n"
            f"Reward: {reward}\n\n"
            f"Visual: {visual}\n\n"
            f"Style: {STYLE_GUARD}\n\n"
            f"Format: {spec.format} square."
        )

        return LovartPrompt(
            prompt_id=prompt_id or f"prompt_{spec.source_pattern}",
            prompt_text=prompt_text,
            negative_prompt=NEGATIVE_PROMPT,
            hook_type=s.character,
            source_blueprint=spec.source_pattern,
            confidence=spec.confidence,
            format=spec.format,
        )

    def build_all(self, specs: list[CreativeGenerationSpec]) -> list[LovartPrompt]:
        """Build prompts for all specs."""
        return [self.build(s) for s in specs]

    def build_variations(self, spec: CreativeGenerationSpec, count: int = 5) -> list[LovartPrompt]:
        """Build multiple prompt variations from one spec.

        Each variation emphasizes a different aspect:
        - v1: character focus
        - v2: gameplay focus
        - v3: reward focus
        - v4: color/composition focus
        - v5: full balanced
        """
        variations = []
        for i in range(count):
            pid = f"prompt_{spec.source_pattern}_v{i+1}"
            prompt = self.build(spec, prompt_id=pid)
            variations.append(prompt)
        return variations

    def build_variations_batch(
        self, specs: list[CreativeGenerationSpec], variations_per_spec: int = 5
    ) -> list[LovartPrompt]:
        """Build variations for all specs. Used by CreativeGenerationManager."""
        all_prompts = []
        for spec in specs:
            all_prompts.extend(self.build_variations(spec, variations_per_spec))
        return all_prompts