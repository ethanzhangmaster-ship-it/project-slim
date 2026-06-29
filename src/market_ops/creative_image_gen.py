from __future__ import annotations

import base64
import json
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

# Optional DALL-E support (legacy)
try:
    from openai import OpenAI
    _HAS_OPENAI = True
except ImportError:
    _HAS_OPENAI = False

# Lovart client
try:
    from market_ops.clients.lovart import LovartClient, download_image as _lovart_download
    _HAS_LOVART = True
except ImportError:
    _HAS_LOVART = False


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------
@dataclass(slots=True)
class GeneratedImage:
    """A single generated image with tracking metadata."""

    image_id: str
    prompt_id: str
    project: str
    hook_type: str
    file_path: str  # where the image is saved
    prompt_used: str
    negative_prompt: str = ""
    model: str = "mock"
    generation_ms: int = 0
    width: int = 0
    height: int = 0
    format: str = "png"
    seed: int = 0
    source_prompt_id: str = ""
    ready_for_review: bool = False


@dataclass(slots=True)
class GenerationBatch:
    """A batch of generated images."""

    batch_id: str
    project: str
    generated_at: str
    total_images: int
    model: str
    images: list[GeneratedImage]
    manifest_path: str = ""


# ---------------------------------------------------------------------------
# Image Generator
# ---------------------------------------------------------------------------
class CreativeImageGenerator:
    """Generates ad creatives from prompts using AI image models.

    Supports:
    - Lovart OpenClaw (nano banana + gpt-2) — primary
    - OpenAI DALL-E 3 (legacy, when api_key is set)
    - Mock mode (placeholder images + prompt saving for manual use)
    """

    def __init__(
        self,
        output_dir: Path | None = None,
        api_key: str | None = None,
        model: str = "dall-e-3",
        use_lovart: bool | None = None,
        lovart_access_key: str | None = None,
        lovart_secret_key: str | None = None,
    ) -> None:
        self._output_dir = output_dir or Path("output/generated_images")
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._api_key = api_key
        self._model = model
        self._client: Any = None
        self._lovart: Any = None

        # Lovart takes priority if available
        if use_lovart is None:
            use_lovart = _HAS_LOVART and bool(
                lovart_access_key
                or __import__("os").getenv("LOVART_ACCESS_KEY")
            )

        if use_lovart and _HAS_LOVART:
            try:
                self._lovart = LovartClient(
                    access_key=lovart_access_key,
                    secret_key=lovart_secret_key,
                )
            except ValueError:
                self._lovart = None

        if not self._lovart and api_key and _HAS_OPENAI:
            self._client = OpenAI(api_key=api_key)

    @property
    def is_live(self) -> bool:
        return self._lovart is not None or self._client is not None

    @property
    def is_lovart(self) -> bool:
        return self._lovart is not None

    @property
    def active_backend(self) -> str:
        if self._lovart:
            return "lovart"
        if self._client:
            return "dall-e"
        return "mock"

    # ----- public API -----

    def generate(
        self,
        prompts: list[dict[str, Any]],
        project: str = "",
        size: str = "1024x1792",  # portrait 9:16
        quality: str = "standard",
        all_models: bool = False,
    ) -> GenerationBatch:
        """Generate images from a list of prompt dicts (from PromptForge output).

        Args:
            prompts: List of prompt dicts with prompt_text, hook_type, etc.
            project: Project name for file organization.
            size: Image size string (used for DALL-E, ignored by Lovart).
            quality: Quality setting (used for DALL-E, ignored by Lovart).
            all_models: If True and using Lovart, generate each prompt with ALL
                        configured models (nano banana + gpt-2).
        """
        if self._lovart:
            return self._generate_lovart(prompts, project, all_models)
        if self._client:
            return self._generate_live(prompts, project, size, quality)
        return self._generate_mock(prompts, project, size)

    def generate_single(
        self,
        prompt_text: str,
        project: str = "",
        hook_type: str = "unknown",
        negative_prompt: str = "",
        size: str = "1024x1792",
    ) -> GeneratedImage:
        """Generate a single image from one prompt string."""
        prompt_dict = {
            "prompt_id": "single_001",
            "prompt_text": prompt_text,
            "negative_prompt": negative_prompt,
            "hook_type": hook_type,
            "project": project,
        }
        return self.generate([prompt_dict], project, size).images[0]

    # ----- Lovart generation -----

    def _generate_lovart(
        self,
        prompts: list[dict[str, Any]],
        project: str,
        all_models: bool = False,
    ) -> GenerationBatch:
        """Generate images via Lovart OpenClaw (nano banana + gpt-2)."""
        images: list[GeneratedImage] = []
        batch_id = f"lovart_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        idx = 0

        for p in prompts:
            prompt_text = str(p.get("prompt_text") or "")
            prompt_id = str(p.get("prompt_id") or f"p{idx:03d}")
            hook = str(p.get("hook_type") or "unknown")
            negative = str(p.get("negative_prompt") or "")

            if all_models:
                # Generate with all configured models
                results = self._lovart.generate_image_all_models(prompt_text)
            else:
                # Generate with first (default) model only
                # Pass reference_image_url as attachment for img2img variation
                ref_url = str(p.get("reference_image_url") or "").strip()
                attachments = [ref_url] if ref_url else None
                results = [self._lovart.generate_image(prompt_text, attachments=attachments)]

            for result in results:
                model_used = result.raw.get("_model_used", "lovart")
                t_ms = int(result.elapsed_sec * 1000)

                if result.status == "done" and result.image_urls:
                    # Download each image
                    for url_idx, img_url in enumerate(result.image_urls):
                        img_id = f"{batch_id}_{idx:03d}"
                        suffix = f"_{url_idx}" if len(result.image_urls) > 1 else ""
                        fmt = "png" if ".png" in img_url else "jpg"
                        dest = self._output_dir / batch_id / f"{img_id}{suffix}.{fmt}"
                        try:
                            _lovart_download(img_url, dest)
                            img = GeneratedImage(
                                image_id=img_id + suffix,
                                prompt_id=prompt_id,
                                project=project,
                                hook_type=hook,
                                file_path=str(dest),
                                prompt_used=prompt_text,
                                negative_prompt=negative,
                                model=model_used,
                                generation_ms=t_ms,
                                width=0,
                                height=0,
                                format=fmt,
                                seed=0,
                                source_prompt_id=prompt_id,
                                ready_for_review=True,
                            )
                        except Exception as dl_exc:
                            print(f"[ImageGen] Download failed: {dl_exc}")
                            img = GeneratedImage(
                                image_id=img_id + suffix,
                                prompt_id=prompt_id,
                                project=project,
                                hook_type=hook,
                                file_path="",
                                prompt_used=prompt_text,
                                negative_prompt=negative,
                                model=f"{model_used}(dl_error)",
                                generation_ms=t_ms,
                                ready_for_review=False,
                            )
                        images.append(img)
                        idx += 1
                else:
                    # No images returned
                    print(f"[ImageGen] Lovart status={result.status} for {prompt_id}: {result.assistant_text}")
                    img = GeneratedImage(
                        image_id=f"{batch_id}_{idx:03d}_error",
                        prompt_id=prompt_id,
                        project=project,
                        hook_type=hook,
                        file_path="",
                        prompt_used=prompt_text,
                        negative_prompt=negative,
                        model=f"{model_used}({result.status})",
                        generation_ms=t_ms,
                        ready_for_review=False,
                    )
                    images.append(img)
                    idx += 1

        model_label = "lovart(" + ",".join(self._lovart._models) + ")"
        manifest = self._write_manifest(batch_id, project, images, model_label)
        return GenerationBatch(
            batch_id=batch_id,
            project=project,
            generated_at=datetime.now().isoformat(),
            total_images=len(images),
            model=model_label,
            images=images,
            manifest_path=str(manifest),
        )

    # ----- DALL-E generation (legacy) -----

    def _generate_live(
        self,
        prompts: list[dict[str, Any]],
        project: str,
        size: str,
        quality: str,
    ) -> GenerationBatch:
        """Real DALL-E generation."""
        images: list[GeneratedImage] = []
        batch_id = f"live_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        for i, p in enumerate(prompts):
            prompt_text = str(p.get("prompt_text") or "")
            prompt_id = str(p.get("prompt_id") or f"p{i:03d}")
            hook = str(p.get("hook_type") or "unknown")
            negative = str(p.get("negative_prompt") or "")

            t0 = time.time()
            try:
                resp = self._client.images.generate(
                    model=self._model,
                    prompt=prompt_text,
                    n=1,
                    size=size,
                    quality=quality,
                    response_format="b64_json",
                )
                elapsed_ms = int((time.time() - t0) * 1000)

                b64_data = resp.data[0].b64_json
                image_bytes = base64.b64decode(b64_data)
                revised_prompt = resp.data[0].revised_prompt or prompt_text

                # Parse size
                w, h = 1024, 1792
                if "x" in size:
                    parts = size.split("x")
                    w = int(parts[0])
                    h = int(parts[1])

                img = self._save_image(
                    image_bytes=image_bytes,
                    batch_id=batch_id,
                    index=i,
                    prompt_id=prompt_id,
                    project=project,
                    hook_type=hook,
                    prompt_text=prompt_text,
                    revised_prompt=revised_prompt,
                    negative_prompt=negative,
                    model=self._model,
                    generation_ms=elapsed_ms,
                    width=w,
                    height=h,
                    fmt="png",
                )
                images.append(img)

            except Exception as exc:
                # On failure, create a placeholder with error info
                print(f"[ImageGen] DALL-E failed for {prompt_id}: {exc}")
                img = GeneratedImage(
                    image_id=f"{batch_id}_{i:03d}_error",
                    prompt_id=prompt_id,
                    project=project,
                    hook_type=hook,
                    file_path="",
                    prompt_used=prompt_text,
                    negative_prompt=negative,
                    model=f"{self._model}(error)",
                    generation_ms=0,
                    ready_for_review=False,
                )
                images.append(img)

        manifest = self._write_manifest(batch_id, project, images, self._model)
        return GenerationBatch(
            batch_id=batch_id,
            project=project,
            generated_at=datetime.now().isoformat(),
            total_images=len(images),
            model=self._model,
            images=images,
            manifest_path=str(manifest),
        )

    def _generate_mock(
        self,
        prompts: list[dict[str, Any]],
        project: str,
        size: str,
    ) -> GenerationBatch:
        """Mock generation: produces tiny placeholder images + saves prompts."""
        images: list[GeneratedImage] = []
        batch_id = f"mock_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Use tiny placeholder to avoid slow PNG compression
        w, h = 16, 28
        if "x" in size:
            parts = size.split("x")
            w = min(int(parts[0]), 16)
            h = min(int(parts[1]), 28)

        for i, p in enumerate(prompts):
            prompt_text = str(p.get("prompt_text") or "")
            prompt_id = str(p.get("prompt_id") or f"p{i:03d}")
            hook = str(p.get("hook_type") or "unknown")
            negative = str(p.get("negative_prompt") or "")

            # Generate a simple placeholder image
            image_bytes = _make_placeholder(w, h, prompt_id, hook, project)
            img = self._save_image(
                image_bytes=image_bytes,
                batch_id=batch_id,
                index=i,
                prompt_id=prompt_id,
                project=project,
                hook_type=hook,
                prompt_text=prompt_text,
                negative_prompt=negative,
                model="mock",
                generation_ms=1,
                width=w,
                height=h,
                fmt="png",
            )
            images.append(img)

        manifest = self._write_manifest(batch_id, project, images, "mock")
        return GenerationBatch(
            batch_id=batch_id,
            project=project,
            generated_at=datetime.now().isoformat(),
            total_images=len(images),
            model="mock",
            images=images,
            manifest_path=str(manifest),
        )

    def _save_image(
        self,
        *,
        image_bytes: bytes,
        batch_id: str,
        index: int,
        prompt_id: str,
        project: str,
        hook_type: str,
        prompt_text: str,
        negative_prompt: str = "",
        revised_prompt: str = "",
        model: str = "mock",
        generation_ms: int = 0,
        width: int = 1024,
        height: int = 1792,
        fmt: str = "png",
    ) -> GeneratedImage:
        """Save image to disk and return metadata."""
        batch_dir = self._output_dir / batch_id
        batch_dir.mkdir(parents=True, exist_ok=True)

        image_id = f"{batch_id}_{index:03d}"
        filename = f"{image_id}.{fmt}"
        file_path = batch_dir / filename
        file_path.write_bytes(image_bytes)

        return GeneratedImage(
            image_id=image_id,
            prompt_id=prompt_id,
            project=project,
            hook_type=hook_type,
            file_path=str(file_path),
            prompt_used=revised_prompt or prompt_text,
            negative_prompt=negative_prompt,
            model=model,
            generation_ms=generation_ms,
            width=width,
            height=height,
            format=fmt,
            seed=hash(prompt_text) & 0xFFFFFFFF,
            source_prompt_id=prompt_id,
            ready_for_review=True,
        )

    def _write_manifest(
        self,
        batch_id: str,
        project: str,
        images: list[GeneratedImage],
        model: str,
    ) -> Path:
        """Write a manifest JSON for the generation batch."""
        manifest_path = self._output_dir / batch_id / "manifest.json"
        data = {
            "batch_id": batch_id,
            "project": project,
            "generated_at": datetime.now().isoformat(),
            "model": model,
            "total_images": len(images),
            "images": [asdict(img) for img in images],
        }
        manifest_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return manifest_path


# ---------------------------------------------------------------------------
# Placeholder image generator (for mock mode)
# ---------------------------------------------------------------------------
def _make_placeholder(width: int, height: int, label: str, hook: str, project: str) -> bytes:
    """Generate a simple colored placeholder PNG with text overlay.

    Uses only stdlib - creates a minimal valid PNG with colored background.
    For real use, replace with PIL/Pillow rendering.
    """
    import struct
    import zlib

    # Map hook types to colors
    colors = {
        "crisis": (180, 40, 40),
        "reward": (40, 160, 40),
        "twist": (160, 80, 40),
        "comparison": (60, 60, 180),
        "curiosity": (120, 40, 160),
        "collection": (40, 120, 160),
    }
    r, g, b = colors.get(hook, (80, 80, 80))

    # Build minimal PNG with solid color
    def make_png(w: int, h: int, red: int, green: int, blue: int) -> bytes:
        # For simplicity, use a tiny placeholder and scale info
        # Actual placeholder just stores metadata; image is a colored 1x1

        # PNG signature
        sig = b"\x89PNG\r\n\x1a\n"

        # IHDR chunk
        ihdr_data = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)  # 8-bit RGB
        ihdr_crc = zlib.crc32(b"IHDR" + ihdr_data) & 0xFFFFFFFF
        ihdr = _png_chunk(b"IHDR", ihdr_data)

        # IDAT chunk - raw pixel data
        raw = b""
        for y in range(h):
            raw += b"\x00"  # filter byte
            for x in range(w):
                # Add some variation based on position
                rr = min(255, max(0, red + (x * 3) % 20 - 10))
                gg = min(255, max(0, green + (y * 3) % 20 - 10))
                bb = min(255, max(0, blue + (x + y) % 10 - 5))
                raw += struct.pack("BBB", rr, gg, bb)

        compressed = zlib.compress(raw)
        idat = _png_chunk(b"IDAT", compressed)

        # IEND chunk
        iend = _png_chunk(b"IEND", b"")

        return sig + ihdr + idat + iend

    return make_png(width, height, r, g, b)


def _png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    import struct
    import zlib

    chunk = chunk_type + data
    crc = zlib.crc32(chunk) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + chunk + struct.pack(">I", crc)
