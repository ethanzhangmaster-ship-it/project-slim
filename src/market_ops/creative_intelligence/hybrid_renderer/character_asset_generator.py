"""Character Asset Generator V1

用 AI 生成角色素材（透明背景或独立角色）。

要求：
  - 透明背景（或暗色背景便于合成）
  - 全身角色
  - 动态姿势，指向 gameplay 区域
  - 目光朝向 merge area
"""
from __future__ import annotations

from typing import Any


class CharacterAssetGenerator:
    """Generate character asset for UA creative compositing."""

    def __init__(self, character_type: str = "witch", pose: str = "dynamic_casting",
                 direction: str = "right_toward_gameplay") -> None:
        self.character_type = character_type
        self.pose = pose
        self.direction = direction

    def build_prompt(self, winner_dna: dict[str, Any] | None = None,
                     template_config: dict | None = None) -> str:
        """Build character generation prompt."""
        palette = "deep purple and gold"
        subject = "witch character"
        if winner_dna:
            palette = winner_dna.get("palette", palette)
            subject = winner_dna.get("subject", subject)

        config = template_config or {}
        ct = config.get("character_type", self.character_type)
        cp = config.get("pose", self.pose)

        return (
            f"A cute {ct} character from a merge mobile game. "
            f"Full body, {cp} pose, hands extended forward casting magic toward a merge board. "
            f"Looking toward the right side of the frame with an excited expression. "
            f"3D cartoon style, premium mobile game character art. "
            f"Dark purple magical background with ambient glow — "
            f"the background should be dark and simple for compositing. "
            f"Color palette: {palette}. "
            f"Character should be well-lit with rim lighting. "
            f"1:1 square aspect ratio, 1080x1080. "
            f"NOT a poster. NOT a standalone illustration. "
            f"The character should be positioned on the left side of the frame, "
            f"looking and pointing RIGHT toward the center."
        )

    def generate(self, generator: Any, project: str, output_path: str,
                 winner_dna: dict[str, Any] | None = None,
                 template_config: dict | None = None) -> str:
        """Generate character asset."""
        from PIL import Image

        prompt = self.build_prompt(winner_dna, template_config)
        result = generator.generate_single(
            prompt_text=prompt,
            project=project,
            hook_type="character",
            size="1080x1080",
            negative_prompt="poster, splash screen, text overlay, UI elements, merge board, gameplay screenshot",
        )

        img = Image.open(result.file_path).convert("RGBA")
        img = img.resize((1080, 1080), Image.LANCZOS)
        img.save(output_path, quality=95)
        return output_path