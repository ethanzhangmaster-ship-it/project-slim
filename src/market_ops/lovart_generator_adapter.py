"""Phase 2: Lovart Generator Adapter.

Wraps the existing CreativeImageGenerator + LovartClient to provide
a simpler interface for CreativeGenerationSpec-based generation.

Also handles:
- Generation history tracking
- Image saving with metadata
- Batch generation with progress
"""

from __future__ import annotations

import json
import os
import signal
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from .creative_blueprint_validator import CreativeGenerationSpec
from .creative_prompt_builder import CreativePromptBuilder, LovartPrompt


# ═══════════════════════════════════════════════════════════
# 1. Generated Creative
# ═══════════════════════════════════════════════════════════

@dataclass
class GeneratedCreative:
    """A single AI-generated creative with full lineage tracking."""
    creative_id: str = ""
    prompt: LovartPrompt = field(default_factory=LovartPrompt)
    image_path: str = ""
    source_blueprint: str = ""
    generation_time: str = ""
    model: str = "lovart"
    width: int = 1080
    height: int = 1080
    generation_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "creative_id": self.creative_id,
            "prompt": self.prompt.to_dict(),
            "image_path": self.image_path,
            "source_blueprint": self.source_blueprint,
            "generation_time": self.generation_time,
            "model": self.model,
            "width": self.width,
            "height": self.height,
            "generation_ms": self.generation_ms,
        }


@dataclass
class GenerationBatch:
    """A batch of generated creatives."""
    batch_id: str = ""
    generated_at: str = ""
    total: int = 0
    creatives: list[GeneratedCreative] = field(default_factory=list)
    manifest_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "generated_at": self.generated_at,
            "total": self.total,
            "creatives": [c.to_dict() for c in self.creatives],
            "manifest_path": self.manifest_path,
        }


# ═══════════════════════════════════════════════════════════
# 2. Lovart Generator Adapter
# ═══════════════════════════════════════════════════════════

class LovartGeneratorAdapter:
    """Simplified adapter for Lovart-based creative generation.

    Wraps CreativeImageGenerator and provides:
    - Spec → Prompt → Image pipeline
    - Batch generation with progress tracking
    - Generation history recording
    - Mock mode for testing without API keys
    """

    def __init__(
        self,
        output_dir: Path | None = None,
        lovart_access_key: str | None = None,
        lovart_secret_key: str | None = None,
    ) -> None:
        self._output_dir = output_dir or Path("output/creative_analysis/generated_creatives")
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._history_dir = self._output_dir / "history"
        self._history_dir.mkdir(parents=True, exist_ok=True)

        self._prompt_builder = CreativePromptBuilder()

        # Try to initialize Lovart
        self._generator = None
        self._is_live = False
        try:
            from market_ops.creative_image_gen import CreativeImageGenerator
            self._generator = CreativeImageGenerator(
                output_dir=self._output_dir,
                use_lovart=True,
                lovart_access_key=lovart_access_key,
                lovart_secret_key=lovart_secret_key,
            )
            self._is_live = self._generator.is_live
        except Exception:
            self._generator = None

    @property
    def is_live(self) -> bool:
        return self._is_live

    @property
    def active_backend(self) -> str:
        if self._generator:
            return self._generator.active_backend
        return "mock"

    # ── Main API ──

    def generate_from_specs(
        self,
        specs: list[CreativeGenerationSpec],
        variations_per_spec: int = 5,
        project: str = "merge_witches",
    ) -> GenerationBatch:
        """Generate creatives from a list of GenerationSpecs.

        Args:
            specs: Validated GenerationSpecs.
            variations_per_spec: Number of variations per spec.
            project: Project name for organization.
        """
        batch_id = f"gen_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        creatives: list[GeneratedCreative] = []

        for spec in specs:
            prompts = self._prompt_builder.build_variations(spec, variations_per_spec)
            for prompt in prompts:
                creative = self._generate_single(prompt, batch_id, project)
                creatives.append(creative)
                time.sleep(0.1)  # Rate limiting

        # Save batch manifest
        batch = GenerationBatch(
            batch_id=batch_id,
            generated_at=datetime.now().isoformat(),
            total=len(creatives),
            creatives=creatives,
        )
        self._save_manifest(batch)
        self._save_history(creatives)

        return batch

    def _generate_single(
        self, prompt: LovartPrompt, batch_id: str, project: str
    ) -> GeneratedCreative:
        """Generate a single creative from a prompt."""
        creative_id = f"{batch_id}_{prompt.prompt_id}"
        now = datetime.now().isoformat()
        t0 = time.time()

        if self._generator and self._is_live:
            # Live generation via Lovart with timeout
            try:
                import threading
                result_container = []
                error_container = []

                def _do_generate():
                    try:
                        r = self._generator.generate_single(
                            prompt_text=prompt.prompt_text,
                            project=project,
                            hook_type=prompt.hook_type,
                            negative_prompt=prompt.negative_prompt,
                        )
                        result_container.append(r)
                    except Exception as e:
                        error_container.append(e)

                thread = threading.Thread(target=_do_generate, daemon=True)
                thread.start()
                thread.join(timeout=30)  # 30s timeout per image

                if result_container:
                    result = result_container[0]
                    image_path = result.file_path
                    model = result.model
                elif error_container:
                    raise error_container[0]
                else:
                    raise TimeoutError("Lovart API call timed out after 30s")
            except Exception as e:
                print(f"  [WARN] Lovart failed for {creative_id}: {e}")
                image_path = self._mock_save(prompt, creative_id)
                model = "mock_fallback"
        else:
            # Mock mode: save prompt, create placeholder
            image_path = self._mock_save(prompt, creative_id)
            model = "mock"

        elapsed_ms = int((time.time() - t0) * 1000)

        return GeneratedCreative(
            creative_id=creative_id,
            prompt=prompt,
            image_path=image_path,
            source_blueprint=prompt.source_blueprint,
            generation_time=now,
            model=model,
            generation_ms=elapsed_ms,
        )

    def _mock_save(self, prompt: LovartPrompt, creative_id: str) -> str:
        """Save prompt as text file for manual use. NO fake images."""
        prompt_dir = self._output_dir / "prompts"
        prompt_dir.mkdir(parents=True, exist_ok=True)

        txt_path = prompt_dir / f"{creative_id}.txt"
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(f"# {creative_id}\n")
            f.write(f"# Source: {prompt.source_blueprint}\n")
            f.write(f"# Confidence: {prompt.confidence}\n")
            f.write(f"# Hook: {prompt.hook_type}\n\n")
            f.write(f"{prompt.prompt_text}\n\n")
            f.write(f"# Negative:\n{prompt.negative_prompt}\n")

        # No image generated — Lovart API unavailable
        return ""

    # ── History ──

    def _save_manifest(self, batch: GenerationBatch) -> None:
        path = self._output_dir / f"manifest_{batch.batch_id}.json"
        batch.manifest_path = str(path)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(batch.to_dict(), f, ensure_ascii=False, indent=2)

    def _save_history(self, creatives: list[GeneratedCreative]) -> None:
        """Append to generation history."""
        history_path = self._history_dir / "generation_history.json"
        existing = []
        if history_path.exists():
            with open(history_path, "r", encoding="utf-8") as f:
                existing = json.load(f)

        for c in creatives:
            existing.append({
                "id": c.creative_id,
                "blueprint": c.source_blueprint,
                "prompt": c.prompt.prompt_text[:200],
                "image": c.image_path,
                "created_time": c.generation_time,
                "model": c.model,
            })

        with open(history_path, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)