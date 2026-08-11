"""Gameplay Asset Generator V1.1

升级 Prompt：
  - 强调 "actual mobile game UI screenshot" vs "concept art"
  - 引用 top puzzle games 的视觉风格
  - 增加 negative prompt 力度
  - 自动重生成：gameplay_score < 0.75 自动重试
"""
from __future__ import annotations

from pathlib import Path
from typing import Any


GAMEPLAY_PROMPT_V11 = """A real mobile game UI screenshot from a casual merge puzzle game.
1:1 square aspect ratio, 1080x1080 pixels.

This is an ACTUAL GAMEPLAY SCREEN, not a marketing image.

ESSENTIAL ELEMENTS:
- Visible hexagonal merge board filling the play area
- Multiple game objects placed on merge slots
- Two identical cute eggs in adjacent slots on the LEFT
- A bright merge arrow and explosion particles between the eggs
- One upgraded baby dragon appearing on the RIGHT slot
- Clear BEFORE (two eggs) → AFTER (baby dragon) progression
- Level indicators: 'Lv.1' near eggs, 'Lv.2' near dragon
- Mobile game UI overlay: level badge, energy bar, coin counter, upgrade button
- Clean 3D cartoon mobile game visuals, bright colors, high contrast

CRITICAL: This is a MOBILE GAME SCREENSHOT.
NOT artwork. NOT a poster. NOT character art. NOT a fantasy illustration.
The game board must be the dominant visual element, filling 60%+ of the frame.
Similar visual style to top-grossing mobile puzzle games: clean UI, vibrant colors, clear gameplay state.
Dark purple magical theme with gold UI accents."""


class GameplayAssetGeneratorV11:
    """V1.1: Enhanced gameplay asset generator with re-generation support."""

    def __init__(self, game_type: str = "merge_witches", progression: str = "egg_to_dragon",
                 style: str = "3d_mobile_game") -> None:
        self.game_type = game_type
        self.progression = progression
        self.style = style

    def build_prompt(self, winner_dna: dict[str, Any] | None = None,
                     template_config: dict | None = None) -> str:
        """Build enhanced gameplay prompt."""
        palette = "deep purple and gold"
        if winner_dna:
            palette = winner_dna.get("palette", palette)

        config = template_config or {}
        gt = config.get("game_type", self.game_type)
        prog = config.get("progression", self.progression)

        return (
            f"A real mobile game UI screenshot from a {gt} casual merge puzzle game. "
            f"1:1 square aspect ratio, 1080x1080 pixels. "
            f"This is an ACTUAL GAMEPLAY SCREEN, not a marketing image. "
            f"Visible hexagonal merge board filling the play area. "
            f"Two identical cute magical eggs in adjacent slots on the LEFT side of the board. "
            f"A bright golden merge arrow and explosion particles connecting the two eggs, "
            f"showing them merging into a baby dragon on the RIGHT slot. "
            f"Clear BEFORE (two eggs) → AFTER (baby dragon) {prog} progression. "
            f"Level indicators 'Lv.1' near eggs and 'Lv.2' near dragon. "
            f"Mobile game UI overlay: level badge 'LEVEL 12' top-left, "
            f"energy bar top-right, coin counter bottom-left, "
            f"UPGRADE button bottom-right. "
            f"Clean 3D cartoon mobile game visuals, bright colors, high contrast. "
            f"Color palette: {palette}. "
            f"Dark purple magical theme with gold UI accents. "
            f"CRITICAL: This is a MOBILE GAME SCREENSHOT. "
            f"The game board must be the dominant visual element, filling 60%+ of the frame. "
            f"NOT artwork. NOT a poster. NOT character art. NOT a fantasy illustration."
        )

    def generate(self, generator: Any, project: str, output_path: str,
                 winner_dna: dict[str, Any] | None = None,
                 template_config: dict | None = None,
                 max_retries: int = 2) -> str:
        """Generate gameplay asset with auto-retry on low quality.

        Args:
            generator: CreativeImageGenerator instance
            project: project name
            output_path: where to save
            winner_dna: winner DNA
            template_config: template config
            max_retries: max re-generation attempts (default 2)

        Returns:
            path to saved gameplay asset
        """
        from PIL import Image

        best_path = None
        best_score = 0.0

        for attempt in range(max_retries + 1):
            prompt = self.build_prompt(winner_dna, template_config)
            result = generator.generate_single(
                prompt_text=prompt,
                project=project,
                hook_type="gameplay",
                size="1080x1080",
                negative_prompt="poster, splash screen, character portrait, fantasy illustration, "
                                "concept art, artwork, UI mockup, flat design, digital painting, "
                                "game poster, marketing banner, promotional image",
            )

            img = Image.open(result.file_path).convert("RGB")
            img = img.resize((1080, 1080), Image.LANCZOS)

            # Validate
            try:
                from market_ops.creative_intelligence.hybrid_renderer.gameplay_validator import GameplayValidator
                validator = GameplayValidator()
                validation = validator.validate(result.file_path)
                score = validation.gameplay_score
            except Exception:
                score = 0.6  # fallback

            if score > best_score:
                best_score = score
                best_path = output_path
                img.save(output_path, quality=95)

            if score >= 0.75 or attempt == max_retries:
                if attempt > 0:
                    print(f"        Gameplay retry #{attempt}: score {score:.2f}")
                break
            else:
                print(f"        Gameplay score {score:.2f} < 0.75, retrying ({attempt + 1}/{max_retries})...")

        return best_path or output_path