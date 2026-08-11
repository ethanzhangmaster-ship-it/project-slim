"""Creative Image Generator — Winner DNA → Prompt Planner → Lovart API.

Phase A of Creative Factory Loop v1.1:
  CreativePerformance (winners)
        │
        ▼
  build_dna_from_winner()
        │
        ▼
  CreativePromptPlanner.generate(dna, count=n)
        │
        ▼
  Prompt.positive_prompt
        │
        ▼
  LovartClient.generate_image(prompt)
        │
        ▼
  download_image(url, dest)
        │
        ▼
  GenerationResult

Usage:
    generator = CreativeImageGenerator(output_dir=Path("output/creative_factory/images"))
    results = generator.generate_from_winners(winners, per_winner=10)
    # → 12 winners × 10 = 120 images, filtered to top 50 by prompt score
"""

from __future__ import annotations

import json
import hashlib
import time
from dataclasses import dataclass, field, asdict
from datetime import date
from pathlib import Path
from typing import Any, Optional

from .creative_performance_builder import CreativePerformance
from .creative_generation.planner.prompt_planner import CreativePromptPlanner
from .creative_generation.models.prompt import Prompt
from .clients.lovart import LovartClient, LovartResult, download_image


# ── Default Merge Witches DNA (used when winner has no analyzed DNA) ──
MERGE_WITCHES_DEFAULT_DNA: dict[str, str] = {
    "character": "witch",
    "camera": "close-up",
    "lighting": "magical glow",
    "composition": "centered hero shot",
    "palette": "purple and gold magical",
    "gameplay": "merge puzzle",
    "reward": "dragon egg hatch",
    "emotion": "surprise",
    "hook": "merge",
    "style": "cartoon",
}

# Platform-specific DNA overrides
PLATFORM_DNA_OVERRIDES: dict[str, dict[str, str]] = {
    "ios": {"style": "cartoon polished", "palette": "purple gold premium"},
    "android": {"style": "cartoon vibrant", "palette": "purple gold bright"},
}


@dataclass
class GeneratedImage:
    """A single generated image result."""
    filename: str = ""
    local_path: str = ""
    source_url: str = ""
    prompt_text: str = ""
    prompt_id: str = ""
    prompt_score: float = 0.0
    model: str = ""
    winner_id: str = ""
    platform: str = ""
    generated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class GenerationResult:
    """Result from a batch image generation run."""
    date: str = ""
    total_prompts: int = 0
    total_generated: int = 0
    total_downloaded: int = 0
    total_failed: int = 0
    images: list[GeneratedImage] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    elapsed_sec: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["images"] = [img.to_dict() for img in self.images]
        d["success_rate"] = self.success_rate
        return d

    @property
    def success_rate(self) -> float:
        if self.total_generated == 0:
            return 0.0
        return round(self.total_downloaded / self.total_generated, 4)


class CreativeImageGenerator:
    """Generate Merge Witches ad images from Winner DNA via Lovart.

    Pipeline:
      1. Build DNA dict from CreativePerformance winners
      2. Generate prompts via CreativePromptPlanner
      3. Call Lovart API for each prompt
      4. Download images to local disk
    """

    def __init__(
        self,
        output_dir: Path | None = None,
        lovart_client: LovartClient | None = None,
        model: str = "nano_banana",
        aspect_ratio: str = "9:16",
        prompt_strategy: str = "balanced",
        seed: int | None = None,
    ) -> None:
        self.output_dir = Path(output_dir) if output_dir else Path("output/creative_factory/images")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self._lovart = lovart_client  # None = lazy init (needs AK/SK env vars)
        self._model = model
        self._aspect_ratio = aspect_ratio

        self._planner = CreativePromptPlanner(
            strategy=prompt_strategy,
            model="lovart",
            aspect_ratio=aspect_ratio,
            seed=seed,
        )

    @property
    def lovart(self) -> LovartClient:
        if self._lovart is None:
            self._lovart = LovartClient()
        return self._lovart

    # ── Public API ──

    def generate_from_winners(
        self,
        winners: list[CreativePerformance],
        per_winner: int = 10,
        max_total: int = 50,
        dry_run: bool = False,
    ) -> GenerationResult:
        """Generate images from a list of winner CreativePerformances.

        Args:
            winners: List of winner CreativePerformance objects.
            per_winner: Number of prompts per winner.
            max_total: Maximum total images to generate across all winners.
            dry_run: If True, only generate prompts, skip Lovart API calls.

        Returns:
            GenerationResult with all generated image metadata.
        """
        today = date.today().isoformat()
        result = GenerationResult(date=today)
        t0 = time.time()

        # Sort winners by ROAS (best first)
        sorted_winners = sorted(winners, key=lambda w: w.roas, reverse=True)

        for winner in sorted_winners:
            if result.total_generated >= max_total:
                break

            # Build DNA from winner
            dna = self._build_dna_from_winner(winner)

            # Calculate how many prompts for this winner
            remaining = max_total - result.total_generated
            count = min(per_winner, remaining)

            try:
                # Step 1: Generate prompts
                prompts = self._planner.generate(dna, count=count)
                result.total_prompts += len(prompts)

                # Step 2: Generate images (or skip in dry_run)
                for prompt in prompts:
                    if dry_run:
                        result.total_generated += 1
                        result.total_downloaded += 1
                        continue

                    try:
                        image = self._generate_one(prompt, winner)
                        if image:
                            result.images.append(image)
                            result.total_downloaded += 1
                        result.total_generated += 1
                    except Exception as e:
                        result.total_generated += 1
                        result.total_failed += 1
                        result.errors.append(f"[{winner.creative_id}] {e}")

            except Exception as e:
                result.errors.append(f"DNA→Prompt failed for {winner.creative_id}: {e}")

        result.elapsed_sec = round(time.time() - t0, 1)

        # Save manifest
        self._save_manifest(result)

        return result

    def generate_from_dna(
        self,
        dna: dict[str, Any],
        count: int = 10,
        label: str = "custom",
        dry_run: bool = False,
    ) -> GenerationResult:
        """Generate images from a raw DNA dict (no winner object needed).

        Args:
            dna: DNA dict with dimension keys.
            count: Number of images to generate.
            label: Label for tracking (e.g., "experiment_001").
            dry_run: If True, only generate prompts, skip Lovart API calls.

        Returns:
            GenerationResult with all generated image metadata.
        """
        today = date.today().isoformat()
        result = GenerationResult(date=today)
        t0 = time.time()

        try:
            prompts = self._planner.generate(dna, count=count)
            result.total_prompts = len(prompts)

            for prompt in prompts:
                if dry_run:
                    result.total_generated += 1
                    result.total_downloaded += 1
                    continue

                try:
                    # Build a minimal winner-like object for tracking
                    dummy_winner = CreativePerformance(
                        creative_id=f"dna_{label}",
                        creative_name=label,
                        platform="custom",
                        roas=1.0,
                    )
                    image = self._generate_one(prompt, dummy_winner)
                    if image:
                        result.images.append(image)
                        result.total_downloaded += 1
                    result.total_generated += 1
                except Exception as e:
                    result.total_generated += 1
                    result.total_failed += 1
                    result.errors.append(f"[{label}] {e}")

        except Exception as e:
            result.errors.append(f"DNA→Prompt failed: {e}")

        result.elapsed_sec = round(time.time() - t0, 1)
        self._save_manifest(result)
        return result

    def generate_prompts_only(
        self,
        winners: list[CreativePerformance],
        per_winner: int = 10,
    ) -> list[dict[str, Any]]:
        """Generate prompts without calling Lovart (for testing / dry-run).

        Returns list of prompt dicts with winner info attached.
        """
        all_prompts: list[dict[str, Any]] = []
        sorted_winners = sorted(winners, key=lambda w: w.roas, reverse=True)

        for winner in sorted_winners:
            dna = self._build_dna_from_winner(winner)
            prompts = self._planner.generate(dna, count=per_winner)
            for p in prompts:
                all_prompts.append({
                    "winner_id": winner.creative_id,
                    "winner_platform": winner.platform,
                    "winner_roas": winner.roas,
                    "prompt_id": p.prompt_id,
                    "positive_prompt": p.positive_prompt,
                    "negative_prompt": p.negative_prompt,
                    "score": p.score.total if p.score else 0.0,
                    "aspect_ratio": p.aspect_ratio,
                    "seed": p.seed,
                })

        return all_prompts

    # ── Internal ──

    def _build_dna_from_winner(self, winner: CreativePerformance) -> dict[str, str]:
        """Build a DNA dict from a CreativePerformance winner.

        Uses default Merge Witches DNA with platform-specific overrides.
        In the future, this will read from analyzed visual_dna.
        """
        dna = dict(MERGE_WITCHES_DEFAULT_DNA)

        # Apply platform-specific overrides
        platform_overrides = PLATFORM_DNA_OVERRIDES.get(winner.platform, {})
        dna.update(platform_overrides)

        # If winner has very high ROAS, add "winning" emphasis
        if winner.roas >= 2.0:
            dna["emotion"] = "excitement and surprise"
            dna["hook"] = "merge win moment"

        # If winner has high spend, it's been tested thoroughly
        if winner.spend >= 5000:
            dna["style"] = dna.get("style", "cartoon") + " proven winner"

        return dna

    def _generate_one(
        self,
        prompt: Prompt,
        winner: CreativePerformance,
    ) -> Optional[GeneratedImage]:
        """Generate a single image from a Prompt.

        Returns GeneratedImage on success, None if Lovart returned no images.
        """
        # Call Lovart
        lovart_result = self.lovart.generate_image(
            prompt=prompt.positive_prompt,
            model=None,  # Use default model (nano_banana)
        )

        if lovart_result.status != "done":
            raise RuntimeError(f"Lovart generation failed: {lovart_result.status}")

        if not lovart_result.image_urls:
            return None

        # Download the first image (Lovart may return multiple)
        image_url = lovart_result.image_urls[0]

        # Generate a deterministic filename
        filename = self._make_filename(winner.creative_id, prompt.prompt_id)
        dest_path = self.output_dir / filename

        try:
            local_path = download_image(image_url, dest_path)
        except Exception as e:
            raise RuntimeError(f"Download failed: {e}") from e

        return GeneratedImage(
            filename=filename,
            local_path=str(local_path),
            source_url=image_url,
            prompt_text=prompt.positive_prompt,
            prompt_id=prompt.prompt_id,
            prompt_score=prompt.score.total if prompt.score else 0.0,
            model=self._model,
            winner_id=winner.creative_id,
            platform=winner.platform,
            generated_at=date.today().isoformat(),
        )

    @staticmethod
    def _make_filename(winner_id: str, prompt_id: str) -> str:
        """Generate a deterministic filename for the generated image."""
        short_hash = hashlib.md5(f"{winner_id}_{prompt_id}".encode()).hexdigest()[:8]
        return f"gen_{winner_id}_{short_hash}.png"

    def _save_manifest(self, result: GenerationResult) -> Path:
        """Save generation manifest to JSON."""
        today = date.today().isoformat().replace("-", "")
        path = self.output_dir / f"generation_manifest_{today}.json"
        path.write_text(
            json.dumps(result.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return path


# ── Convenience function ──

def create_default_generator(
    output_dir: str | Path = "output/creative_factory/images",
    model: str = "nano_banana",
) -> CreativeImageGenerator:
    """Create a CreativeImageGenerator with sensible defaults for Merge Witches."""
    return CreativeImageGenerator(
        output_dir=Path(output_dir),
        model=model,
        aspect_ratio="9:16",
        prompt_strategy="balanced",
    )