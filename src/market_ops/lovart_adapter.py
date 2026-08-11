"""Phase 2.1: Lovart API Adapter — clean wrapper around the Lovart OpenClaw API.

Encapsulates all Lovart API calls with:
  - 60s timeout per request
  - Error classification
  - Cost estimation
  - No mock/placeholder generation
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class LovartAPIResult:
    """Result from a Lovart API generation call."""
    success: bool = False
    image_url: str = ""
    image_path: str = ""
    thread_id: str = ""
    model: str = ""
    generation_time: float = 0
    cost: float = 0
    error: str = ""
    raw: Any = None


class LovartAPIAdapter:
    """Production adapter for Lovart image generation API.

    Wraps the existing LovartClient with timeout, error handling,
    and cost tracking. Never generates placeholder images.
    """

    # Estimated cost per image (credits)
    ESTIMATED_COST_PER_IMAGE = 0.12

    def __init__(
        self,
        access_key: str | None = None,
        secret_key: str | None = None,
        timeout: int = 60,
    ) -> None:
        self._timeout = timeout
        self._client = None
        self._available = False

        try:
            from market_ops.clients.lovart import LovartClient
            self._client = LovartClient(
                access_key=access_key,
                secret_key=secret_key,
            )
            self._available = True
        except Exception as e:
            self._available = False
            self._init_error = str(e)

    @property
    def available(self) -> bool:
        return self._available

    def generate(
        self,
        prompt: str,
        negative_prompt: str = "",
        size: str = "1080x1080",
        model: str | None = None,
        project_id: str | None = None,
        attachments: list[str] | None = None,
    ) -> LovartAPIResult:
        """Generate an image via Lovart API with timeout protection.

        Returns LovartAPIResult with success flag and image_url or error.
        Never returns a placeholder/fake result.
        """
        if not self._client or not self._available:
            return LovartAPIResult(
                success=False,
                error=f"Lovart API unavailable: {getattr(self, '_init_error', 'not configured')}",
            )

        result_container: list[LovartAPIResult] = []
        error_container: list[Exception] = []

        def _call():
            try:
                t0 = time.time()
                compiled_prompt = prompt.strip()
                if negative_prompt.strip():
                    compiled_prompt += f"\n\nAVOID / NEGATIVE CONSTRAINTS:\n{negative_prompt.strip()}"
                if size.strip():
                    compiled_prompt += (
                        f"\n\nOUTPUT SPECIFICATION: compose for exact {size.strip()} pixels. "
                        "Keep all key subjects and copy inside placement-safe margins."
                    )
                api_result = self._client.generate_image(
                    prompt=compiled_prompt,
                    model=model,
                    project_id=project_id,
                    attachments=attachments,
                )
                elapsed = time.time() - t0

                if api_result.status == "done" and api_result.image_urls:
                    result_container.append(LovartAPIResult(
                        success=True,
                        image_url=api_result.image_urls[0],
                        thread_id=api_result.thread_id,
                        model=api_result.raw.get("_model_used", "lovart"),
                        generation_time=elapsed,
                        cost=self.ESTIMATED_COST_PER_IMAGE,
                        raw=api_result.raw,
                    ))
                else:
                    err_msg = api_result.assistant_text or api_result.status or "Unknown error"
                    result_container.append(LovartAPIResult(
                        success=False,
                        error=err_msg,
                        thread_id=api_result.thread_id,
                        generation_time=elapsed,
                        raw=api_result.raw,
                    ))
            except Exception as e:
                error_container.append(e)

        thread = threading.Thread(target=_call, daemon=True)
        thread.start()
        thread.join(timeout=self._timeout)

        if result_container:
            return result_container[0]

        if error_container:
            return LovartAPIResult(
                success=False,
                error=f"Lovart API error: {error_container[0]}",
            )

        return LovartAPIResult(
            success=False,
            error=f"Lovart API timeout after {self._timeout}s",
        )
