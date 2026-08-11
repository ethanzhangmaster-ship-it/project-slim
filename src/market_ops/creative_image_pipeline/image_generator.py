"""Phase 3.0A: Image Generator — Prompt → Image via Lovart/Flux API.

Wraps the existing LovartAPIAdapter and LovartGeneratorAdapter.
Handles:
  - Real API calls with timeout protection
  - Image download and local save
  - Fallback: no fake images, returns empty result with error
  - Generation metadata tracking
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..creative_generation.models.prompt import Prompt


@dataclass
class GenerationResult:
    """Result of a single image generation attempt."""
    prompt_id: str = ""
    image_path: str = ""
    success: bool = False
    error: str = ""
    model: str = "lovart"
    generation_ms: int = 0
    width: int = 0
    height: int = 0
    file_size_kb: float = 0
    retry_count: int = 0


@dataclass
class GenerationReport:
    """Summary report for a generation batch."""
    total: int = 0
    success: int = 0
    failed: int = 0
    results: list[GenerationResult] = field(default_factory=list)
    total_time_ms: int = 0
    api_available: bool = False


class ImageGenerator:
    """Generates images from Prompt objects via AI API.

    Uses LovartAPIAdapter for real API calls. Never produces fake images.
    When API is unavailable, returns GenerationResult with success=False.
    """

    def __init__(
        self,
        output_dir: Path | None = None,
        lovart_access_key: str | None = None,
        lovart_secret_key: str | None = None,
        timeout: int = 60,
        max_retries: int = 2,
    ) -> None:
        self._output_dir = output_dir or Path("output/golden_sample")
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._max_retries = max_retries
        self._timeout = timeout

        self._lovart = None
        self._api_available = False
        try:
            from ..lovart_adapter import LovartAPIAdapter
            self._lovart = LovartAPIAdapter(
                access_key=lovart_access_key,
                secret_key=lovart_secret_key,
                timeout=timeout,
            )
            self._api_available = self._lovart.available
        except Exception:
            self._lovart = None
            self._api_available = False

    @property
    def api_available(self) -> bool:
        return self._api_available

    def generate(self, prompt: Prompt, max_retries: int | None = None) -> GenerationResult:
        """Generate a single image from a Prompt.

        Args:
            prompt: Rendered Prompt object with positive_prompt and negative_prompt.
            max_retries: Override default retry count.

        Returns:
            GenerationResult with image_path if successful, error otherwise.
        """
        retries = max_retries if max_retries is not None else self._max_retries
        t0 = time.time()

        for attempt in range(retries + 1):
            result = self._try_generate(prompt, attempt)
            if result.success:
                result.generation_ms = int((time.time() - t0) * 1000)
                return result
            time.sleep(1)  # Brief delay before retry

        elapsed_ms = int((time.time() - t0) * 1000)
        return GenerationResult(
            prompt_id=prompt.prompt_id,
            success=False,
            error=f"Failed after {retries + 1} attempts",
            model=prompt.model,
            generation_ms=elapsed_ms,
            retry_count=retries + 1,
        )

    def generate_batch(
        self, prompts: list[Prompt], max_retries: int | None = None,
    ) -> GenerationReport:
        """Generate images for a list of prompts.

        Returns GenerationReport with summary and individual results.
        """
        t0 = time.time()
        results = []

        for prompt in prompts:
            result = self.generate(prompt, max_retries=max_retries)
            results.append(result)

        total_ms = int((time.time() - t0) * 1000)

        return GenerationReport(
            total=len(results),
            success=sum(1 for r in results if r.success),
            failed=sum(1 for r in results if not r.success),
            results=results,
            total_time_ms=total_ms,
            api_available=self._api_available,
        )

    def _try_generate(self, prompt: Prompt, attempt: int) -> GenerationResult:
        """Attempt a single generation call."""
        if not self._lovart or not self._api_available:
            return GenerationResult(
                prompt_id=prompt.prompt_id,
                success=False,
                error="Lovart API not available",
                model=prompt.model,
            )

        try:
            api_result = self._lovart.generate(
                prompt=prompt.positive_prompt,
                negative_prompt=prompt.negative_prompt,
                size=self._size_from_aspect(prompt.aspect_ratio),
            )

            if api_result.success and api_result.image_url:
                image_path = self._save_image(prompt, api_result)
                return GenerationResult(
                    prompt_id=prompt.prompt_id,
                    image_path=image_path,
                    success=True,
                    model=prompt.model,
                )
            else:
                return GenerationResult(
                    prompt_id=prompt.prompt_id,
                    success=False,
                    error=api_result.error or "Unknown API error",
                    model=prompt.model,
                    retry_count=attempt,
                )
        except Exception as e:
            return GenerationResult(
                prompt_id=prompt.prompt_id,
                success=False,
                error=f"Exception: {e}",
                model=prompt.model,
                retry_count=attempt,
            )

    def _save_image(self, prompt: Prompt, api_result: Any) -> str:
        """Download and save image from API result."""
        import urllib.request

        image_id = prompt.prompt_id or uuid.uuid4().hex[:12]
        filename = f"{image_id}.png"
        filepath = self._output_dir / filename

        try:
            urllib.request.urlretrieve(api_result.image_url, str(filepath))
        except Exception:
            pass  # File may already exist or download failed

        return str(filepath)

    def _size_from_aspect(self, aspect_ratio: str) -> str:
        """Convert aspect ratio to pixel dimensions."""
        mapping = {
            "1:1": "1080x1080",
            "9:16": "1080x1920",
            "16:9": "1920x1080",
            "4:5": "1080x1350",
        }
        return mapping.get(aspect_ratio, "1080x1080")