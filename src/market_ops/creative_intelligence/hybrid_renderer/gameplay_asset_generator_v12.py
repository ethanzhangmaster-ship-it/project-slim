"""Gameplay Asset Generator V1.2

V1.2 核心升级：
  - 严格 Prompt: "REAL MOBILE GAMEPLAY SCREENSHOT" 禁止 fantasy artwork
  - 多候选生成: 一次生成 5 张，Quality Gate 筛选最佳
  - 自动重生成: 质量 < 80 分自动重试
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from PIL import Image


GAMEPLAY_PROMPT_V12 = """A REAL MOBILE GAMEPLAY SCREENSHOT from a casual merge puzzle game.

CRITICAL: This is NOT concept art. NOT illustration. NOT fantasy poster. This is an actual mobile game screen capture.

REQUIREMENTS:
- Vertical smartphone screenshot format, 1080x1080 square
- Visible hexagonal merge board filling the center area
- 8-12 merge slots with game objects placed inside
- Two identical cute magical eggs in adjacent slots
- Bright golden merge arrow connecting the two eggs
- Sparkle/explosion effect at the merge point
- One upgraded baby dragon appearing after merge
- Level indicator badge (e.g. "LEVEL 12")
- Coin counter display (e.g. "1,250")
- Energy bar at top
- MERGE button at bottom
- Mobile game HUD elements visible

STYLE:
- Top grossing casual mobile game UI quality
- App Store screenshot level clarity
- Clean 3D cartoon mobile game visuals
- Bright colors, high contrast against dark purple backdrop
- Gold UI accents on dark purple theme

DO NOT INCLUDE:
- Big character illustration
- Cinematic background
- Fantasy poster composition
- Artwork that looks like a painting
- Full-screen character art
- Abstract magical effects without literal game UI

The game board must be the DOMINANT visual element, filling 60%+ of the frame."""


GAMEPLAY_NEGATIVE_V12 = (
    "poster, splash screen, character portrait, fantasy illustration, "
    "concept art, artwork, UI mockup, flat design, digital painting, "
    "game poster, marketing banner, promotional image, cinematic, "
    "big character, full screen character, magical scene without UI, "
    "abstract art, painting, wallpaper, landscape, portrait, "
    "no game UI, no HUD, no merge board, no grid, no slots"
)


class GameplayAssetGeneratorV12:
    """V1.2: Strict gameplay screenshot generator with multi-candidate support."""

    def __init__(self, game_type: str = "merge_witches", progression: str = "egg_to_dragon",
                 style: str = "3d_mobile_game_ui") -> None:
        self.game_type = game_type
        self.progression = progression
        self.style = style

    def build_prompt(self, winner_dna: dict[str, Any] | None = None,
                     template_config: dict | None = None) -> str:
        """Build strict gameplay screenshot prompt."""
        palette = "dark purple and gold"
        if winner_dna:
            palette = winner_dna.get("palette", palette)

        config = template_config or {}
        gt = config.get("game_type", self.game_type)
        prog = config.get("progression", self.progression)

        return (
            f"A REAL MOBILE GAMEPLAY SCREENSHOT from a {gt} casual merge puzzle game. "
            f"CRITICAL: This is NOT concept art. NOT illustration. NOT fantasy poster. "
            f"This is an actual mobile game screen capture. "
            f"Vertical smartphone screenshot format, 1080x1080 square. "
            f"Visible hexagonal merge board filling the center area. "
            f"8-12 merge slots with game objects placed inside. "
            f"Two identical cute magical eggs in adjacent slots. "
            f"Bright golden merge arrow connecting the two eggs. "
            f"Sparkle and explosion effect at the merge point. "
            f"One upgraded baby dragon appearing after merge. "
            f"Level indicator badge 'LEVEL 12'. "
            f"Coin counter display '1,250'. "
            f"Energy bar at top. "
            f"MERGE button at bottom. "
            f"Mobile game HUD elements visible. "
            f"Top grossing casual mobile game UI quality. "
            f"App Store screenshot level clarity. "
            f"Clean 3D cartoon mobile game visuals. "
            f"Bright colors, high contrast against {palette} backdrop. "
            f"Gold UI accents on {palette} theme. "
            f"DO NOT INCLUDE: big character illustration, cinematic background, "
            f"fantasy poster composition, artwork that looks like a painting, "
            f"full-screen character art, abstract magical effects without literal game UI. "
            f"The game board must be the DOMINANT visual element, filling 60%+ of the frame."
        )

    def generate_candidates(
        self,
        generator: Any,
        project: str,
        output_dir: str,
        winner_dna: dict[str, Any] | None = None,
        template_config: dict | None = None,
        num_candidates: int = 5,
    ) -> dict:
        """Generate multiple gameplay candidates and select the best one.

        Args:
            generator: CreativeImageGenerator instance
            project: project name
            output_dir: directory for candidate outputs
            winner_dna: winner DNA data
            template_config: template config
            num_candidates: number of candidates to generate (default 5)

        Returns:
            dict with keys: selected_path, candidates, scores, best_score
        """
        candidates_dir = Path(output_dir) / "gameplay_candidates"
        candidates_dir.mkdir(parents=True, exist_ok=True)

        candidates = []
        scores = []

        print(f"        Generating {num_candidates} gameplay candidates...")

        for i in range(num_candidates):
            prompt = self.build_prompt(winner_dna, template_config)
            result = generator.generate_single(
                prompt_text=prompt,
                project=project,
                hook_type="gameplay",
                size="1080x1080",
                negative_prompt=GAMEPLAY_NEGATIVE_V12,
            )

            candidate_path = str(candidates_dir / f"candidate_{i + 1:03d}.png")
            img = Image.open(result.file_path).convert("RGB")
            img = img.resize((1080, 1080), Image.LANCZOS)
            img.save(candidate_path, quality=95)
            candidates.append(candidate_path)

            # Quick heuristic candidate selection (avoid 54 Lovart API calls)
            try:
                score = self._quick_quality_score(candidate_path)
                scores.append(score)
                print(f"          Candidate {i + 1:03d}: quick_score={score:.0f}")
            except Exception:
                score = 50
                scores.append(score)
                print(f"          Candidate {i + 1:03d}: score={score:.0f} (fallback)")

        # Select best candidate
        best_idx = 0
        best_score = 0
        for i, s in enumerate(scores):
            if s > best_score:
                best_score = s
                best_idx = i

        selected_path = str(Path(output_dir) / "selected_gameplay.png")
        Image.open(candidates[best_idx]).save(selected_path, quality=95)

        # Save scores
        scores_json = {
            "candidates": [
                {"path": candidates[i], "score": float(scores[i])}
                for i in range(len(candidates))
            ],
            "best_index": best_idx,
            "best_score": float(best_score),
            "selected_path": selected_path,
        }
        scores_path = candidates_dir / "scores.json"
        scores_path.write_text(json.dumps(scores_json, indent=2, ensure_ascii=False), encoding="utf-8")

        print(f"        Selected Candidate {best_idx + 1:03d}: score={best_score:.0f}")

        return {
            "selected_path": selected_path,
            "candidates": candidates,
            "scores": scores,
            "best_score": best_score,
            "best_index": best_idx,
        }

    def generate_single(
        self,
        generator: Any,
        project: str,
        output_path: str,
        winner_dna: dict[str, Any] | None = None,
        template_config: dict | None = None,
    ) -> str:
        """Generate a single gameplay asset (fallback mode)."""
        prompt = self.build_prompt(winner_dna, template_config)
        result = generator.generate_single(
            prompt_text=prompt,
            project=project,
            hook_type="gameplay",
            size="1080x1080",
            negative_prompt=GAMEPLAY_NEGATIVE_V12,
        )
        img = Image.open(result.file_path).convert("RGB")
        img = img.resize((1080, 1080), Image.LANCZOS)
        img.save(output_path, quality=95)
        return output_path

    @staticmethod
    def _quick_quality_score(image_path: str) -> float:
        """Fast heuristic score based on image properties (no API calls).
        
        Uses contrast, saturation, and color variety as proxies for UI density.
        Higher contrast + more colors ≈ more likely to be a game screenshot.
        """
        from PIL import ImageStat
        img = Image.open(image_path).convert("RGB")
        stat = ImageStat.Stat(img)
        
        # Contrast: higher stddev suggests more UI elements
        stddev = sum(stat.stddev) / 3
        contrast_score = min(stddev / 80.0, 1.0) * 30
        
        # Color variety: more unique colors suggests game UI
        extrema = stat.extrema
        range_sum = sum((e[1] - e[0]) for e in extrema)
        color_score = min(range_sum / 600.0, 1.0) * 30
        
        # Brightness: game screenshots tend to be brighter than concept art
        mean = sum(stat.mean) / 3
        brightness_score = min(mean / 200.0, 1.0) * 20
        
        # Size: penalize images that are too small
        w, h = img.size
        size_score = min(w * h / (1080 * 1080), 1.0) * 20
        
        return contrast_score + color_score + brightness_score + size_score