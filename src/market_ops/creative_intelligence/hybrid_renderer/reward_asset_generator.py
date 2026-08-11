"""Reward Asset Generator V1

用 AI 生成付费诱因素材。

内容：
  - legendary dragon / premium reward
  - treasure / magical chest
  - golden glow / rare collectible feeling
"""
from __future__ import annotations

from typing import Any


class RewardAssetGenerator:
    """Generate premium reward asset for UA creative."""

    def __init__(self, reward_type: str = "legendary_dragon", rarity: str = "legendary",
                 style: str = "premium_reward") -> None:
        self.reward_type = reward_type
        self.rarity = rarity
        self.style = style

    def build_prompt(self, winner_dna: dict[str, Any] | None = None,
                     template_config: dict | None = None) -> str:
        """Build reward generation prompt."""
        palette = "deep purple and gold"
        if winner_dna:
            palette = winner_dna.get("palette", palette)

        config = template_config or {}
        rt = config.get("reward_type", self.reward_type)
        rar = config.get("rarity", self.rarity)

        return (
            f"A premium {rar} reward reveal: a cute baby {rt} with golden magical aura. "
            f"The dragon has sparkling wings, glowing eyes, and a rich golden glow effect. "
            f"Premium collectible reward feel — extremely desirable, dopamine hit. "
            f"Golden sparkles and magical particles surrounding the creature. "
            f"3D cartoon style, matching dark fantasy merge game. "
            f"Color palette: {palette}. "
            f"The creature is the focal point, centered in frame. "
            f"Dark magical background with purple ambient glow for compositing. "
            f"Soft lighting from above, rim light on the creature. "
            f"1:1 square aspect ratio, 1080x1080. "
            f"NOT a poster. NOT a full scene. Isolated premium reward focus."
        )

    def generate(self, generator: Any, project: str, output_path: str,
                 winner_dna: dict[str, Any] | None = None,
                 template_config: dict | None = None) -> str:
        """Generate reward asset."""
        from PIL import Image

        prompt = self.build_prompt(winner_dna, template_config)
        result = generator.generate_single(
            prompt_text=prompt,
            project=project,
            hook_type="reward",
            size="1080x1080",
            negative_prompt="poster, splash screen, text overlay, UI elements, merge board, gameplay screenshot, character portrait",
        )

        img = Image.open(result.file_path).convert("RGBA")
        img = img.resize((1080, 1080), Image.LANCZOS)
        img.save(output_path, quality=95)
        return output_path