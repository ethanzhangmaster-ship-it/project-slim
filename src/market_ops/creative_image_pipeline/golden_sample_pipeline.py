"""Phase 3.0A: Golden Sample Pipeline — main orchestrator.

Pipeline:
  Winner DNA (JSON)
      │
      ▼
  Creative Prompt Planner
      │
      ▼
  Top 20 Prompts
      │
      ▼
  Image Selector (Top 3 diverse)
      │
      ▼
  Image Generator (Lovart/Flux)
      │
      ▼
  Image Quality Gate
      │
      ▼
  Image Exporter (Golden Sample)
      │
      ▼
  Human Review

Usage:
    pipeline = GoldenSamplePipeline()
    result = pipeline.run("output/winner_dna/winner_001.json")
    print(result.summary())
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..creative_generation.planner import CreativePromptPlanner
from ..creative_generation.models.prompt import Prompt

from .image_selector import ImageSelector, SelectionResult
from .image_generator import ImageGenerator, GenerationResult, GenerationReport
from .image_quality_gate import ImageQualityGate, QualityResult
from .image_exporter import ImageExporter


@dataclass
class PipelineResult:
    """Complete result of a Golden Sample pipeline run."""
    winner_id: str = ""
    total_prompts: int = 0
    selected_count: int = 0
    generated_count: int = 0
    passed_quality: int = 0
    exported_files: dict[str, str] = field(default_factory=dict)
    top_prompt: Prompt | None = None
    generation_report: GenerationReport | None = None
    quality_results: list[QualityResult] = field(default_factory=list)
    elapsed_ms: int = 0
    error: str = ""

    def summary(self) -> str:
        lines = [
            "=" * 50,
            f"  Golden Sample Pipeline — {self.winner_id}",
            "=" * 50,
            f"  Prompts generated:  {self.total_prompts}",
            f"  Selected for gen:   {self.selected_count}",
            f"  Images generated:   {self.generated_count}",
            f"  Passed quality:     {self.passed_quality}",
            f"  Elapsed:            {self.elapsed_ms}ms",
            "=" * 50,
        ]
        if self.error:
            lines.append(f"  ERROR: {self.error}")
        if self.exported_files:
            lines.append("  Exported files:")
            for k, v in self.exported_files.items():
                lines.append(f"    {k}: {v}")
        return "\n".join(lines)


class GoldenSamplePipeline:
    """Phase 3.0A: Golden Sample Pipeline.

    End-to-end pipeline from Winner DNA to Golden Sample export.
    Proves: DNA → Prompt → Image is viable.
    """

    def __init__(
        self,
        strategy: str = "aggressive",
        model: str = "lovart",
        output_dir: Path | None = None,
        max_images: int = 3,
        lovart_access_key: str | None = None,
        lovart_secret_key: str | None = None,
    ) -> None:
        self._strategy = strategy
        self._model = model
        self._output_dir = output_dir or Path("output/golden_sample")
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._max_images = max_images

        # Pipeline components
        self._planner = CreativePromptPlanner(strategy=strategy, model=model)
        self._selector = ImageSelector(max_count=max_images, ensure_diversity=True)
        self._generator = ImageGenerator(
            output_dir=self._output_dir,
            lovart_access_key=lovart_access_key,
            lovart_secret_key=lovart_secret_key,
        )
        self._quality_gate = ImageQualityGate(strict=True)
        self._exporter = ImageExporter(output_dir=self._output_dir)

    # ── Main API ──

    def run(
        self,
        dna_path: str | Path,
        prompt_count: int = 20,
        review_scores: dict[str, int] | None = None,
    ) -> PipelineResult:
        """Run the full Golden Sample pipeline.

        Args:
            dna_path: Path to a Winner DNA JSON file.
            prompt_count: Number of prompts to generate (default 20).
            review_scores: Optional human review scores.

        Returns:
            PipelineResult with complete pipeline output.
        """
        t0 = time.time()

        try:
            # Step 1: Load Winner DNA
            dna_data = self._load_dna(dna_path)
            winner_id = dna_data.get("winner_id", Path(dna_path).stem)
            dna = dna_data.get("dna", dna_data)

            # Step 2: Generate prompts via Prompt Planner
            prompts = self._planner.generate(dna, count=prompt_count)
            top_prompts = self._planner.top_n(prompts, n=prompt_count)

            # Step 3: Select top prompts for image generation
            selection = self._selector.select(top_prompts)

            # Step 4: Generate images
            gen_report = self._generator.generate_batch(selection.selected)

            # Step 5: Quality gate
            quality_results = []
            passed_count = 0
            successful_results = [r for r in gen_report.results if r.success]

            for gen_result in successful_results:
                qr = self._quality_gate.validate(gen_result.image_path)
                quality_results.append(qr)
                if qr.passed:
                    passed_count += 1

            # Step 6: Export Golden Sample (use first successful + passed image)
            exported_files = {}
            top_prompt = selection.selected[0] if selection.selected else None

            for gen_result in successful_results:
                qr = self._quality_gate.validate(gen_result.image_path)
                if qr.passed:
                    exported_files = self._exporter.export(
                        prompt=top_prompt or Prompt(),
                        image_path=gen_result.image_path,
                        quality=qr,
                        review_scores=review_scores,
                        winner_id=winner_id,
                    )
                    break

            elapsed_ms = int((time.time() - t0) * 1000)

            return PipelineResult(
                winner_id=winner_id,
                total_prompts=len(prompts),
                selected_count=len(selection.selected),
                generated_count=gen_report.success,
                passed_quality=passed_count,
                exported_files=exported_files,
                top_prompt=top_prompt,
                generation_report=gen_report,
                quality_results=quality_results,
                elapsed_ms=elapsed_ms,
            )

        except Exception as e:
            elapsed_ms = int((time.time() - t0) * 1000)
            return PipelineResult(
                winner_id=Path(dna_path).stem,
                elapsed_ms=elapsed_ms,
                error=str(e),
            )

    def run_plan_only(self, dna_path: str | Path) -> list[Prompt]:
        """Generate prompts only (no image generation). For testing."""
        dna_data = self._load_dna(dna_path)
        dna = dna_data.get("dna", dna_data)
        prompts = self._planner.generate(dna, count=20)
        return self._planner.top_n(prompts, n=20)

    # ── API Check ──

    @property
    def api_available(self) -> bool:
        return self._generator.api_available

    # ── Helpers ──

    def _load_dna(self, path: str | Path) -> dict[str, Any]:
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Winner DNA file not found: {path}")

        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)