"""Character Renderer V2

V2 升级：
  - 角色不能成为主视觉，限制 max 35% width, 45% height
  - 固定位置: bottom-right
  - 禁止: center character, full screen character
  - Prompt: "small supporting character, NOT main focus"
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image


CHARACTER_PROMPT_V2 = """A small supporting witch character for a mobile game ad.

IMPORTANT: This character is a SUPPORTING element, NOT the main focus.
The character should be small, positioned at the bottom-right corner of a larger ad.

Style:
- 3D cartoon witch character
- Dark purple magical robes with gold trim
- Magical staff or wand
- Subtle magical glow around hands
- Transparent or dark background
- Facing left (toward the gameplay area)

CRITICAL: The character should be SMALL and positioned at the BOTTOM-RIGHT.
NOT a full-body portrait. NOT the main visual. Just a guide character.
The character should occupy at most 35% of the frame width."""


CHARACTER_NEGATIVE_V2 = (
    "full body portrait, main character, center composition, "
    "full screen, hero pose, large character, dominant figure, "
    "cinematic, poster, splash art, close-up, face portrait"
)


class CharacterAssetGeneratorV2:
    """V2: Small supporting character, bottom-right, max 35% width."""

    def __init__(self) -> None:
        self.max_width_ratio = 0.35
        self.max_height_ratio = 0.45

    def build_prompt(self, winner_dna: dict[str, Any] | None = None) -> str:
        palette = "dark purple and gold"
        subject = "witch character"
        pose = "facing left with magical energy"
        if winner_dna:
            palette = winner_dna.get("palette", palette)
            subject = winner_dna.get("subject", subject)
            pose = winner_dna.get("character_pose", pose)

        return (
            f"A small supporting {subject} for a mobile game ad. "
            f"IMPORTANT: This character is a SUPPORTING element, NOT the main focus. "
            f"The character should be small, positioned at the bottom-right corner of a larger ad. "
            f"3D cartoon style, {palette} color palette. "
            f"{pose}. "
            f"Subtle magical glow around hands. "
            f"Transparent or dark background. "
            f"Facing left toward the gameplay area. "
            f"CRITICAL: The character should be SMALL and positioned at the BOTTOM-RIGHT. "
            f"NOT a full-body portrait. NOT the main visual. Just a guide character. "
            f"The character should occupy at most 35% of the frame width."
        )

    def generate(
        self,
        generator: Any,
        project: str,
        output_path: str,
        winner_dna: dict[str, Any] | None = None,
        template_config: dict | None = None,
    ) -> str:
        """Generate small supporting character."""
        prompt = self.build_prompt(winner_dna)
        result = generator.generate_single(
            prompt_text=prompt,
            project=project,
            hook_type="character",
            size="512x512",
            negative_prompt=CHARACTER_NEGATIVE_V2,
        )

        img = Image.open(result.file_path).convert("RGBA")
        img = img.resize((512, 512), Image.LANCZOS)
        img.save(output_path, quality=95)
        return output_path