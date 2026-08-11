"""AI 出图质量评估模块

对 Lovart / DALL-E 生成的广告图片进行多维度 AI 评分：
  - visual_quality   : 整体视觉质量、清晰度、构图
  - brand_alignment  : 是否匹配项目美术风格（色调、元素、氛围）
  - hook_clarity     : hook 概念是否清晰传达
  - ad_suitability   : 是否适合手游广告素材（CTA空间、可读性）
  - originality      : 原创性和创意度

评分结果用于闭环自动筛选：低分淘汰、高分入库。
"""

from __future__ import annotations

import base64
import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

# Try to import OpenAI for vision scoring
try:
    from openai import OpenAI
    _HAS_OPENAI = True
except ImportError:
    _HAS_OPENAI = False

import requests as _requests

from market_ops.creative_prompt_forge import GAME_VISUAL_CONTEXT, FALLBACK_VISUAL


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------
@dataclass(slots=True)
class ImageScore:
    """Quality score for a single generated image."""

    image_id: str
    file_path: str
    prompt_used: str
    model: str

    # Individual dimension scores (1-10)
    visual_quality: float = 0.0
    brand_alignment: float = 0.0
    hook_clarity: float = 0.0
    ad_suitability: float = 0.0
    originality: float = 0.0

    # Composite
    overall: float = 0.0
    passed: bool = False
    reject_reason: str = ""

    # AI feedback
    strengths: list[str] = field(default_factory=list)
    improvements: list[str] = field(default_factory=list)
    raw_feedback: str = ""


@dataclass(slots=True)
class ScoreBatch:
    """Batch scoring result."""

    total_scored: int
    total_passed: int
    total_rejected: int
    avg_overall: float
    threshold: float
    scores: list[ImageScore]


# ---------------------------------------------------------------------------
# Scoring prompt
# ---------------------------------------------------------------------------
_SCORING_SYSTEM = """You are an expert mobile game ad creative reviewer.
You evaluate AI-generated ad images for quality and effectiveness.
Always respond in valid JSON with this exact schema:
{
  "visual_quality": <1-10>,
  "brand_alignment": <1-10>,
  "hook_clarity": <1-10>,
  "ad_suitability": <1-10>,
  "originality": <1-10>,
  "strengths": ["..."],
  "improvements": ["..."],
  "summary": "..."
}
Be strict but fair. Score 7+ means production-ready, 5-6 needs improvement, below 5 is rejected."""

_SCORING_USER_TEMPLATE = """Evaluate this AI-generated mobile game ad creative.

**Project**: {project}
**Project Visual Style**:
- Genre: {genre}
- Color Palette: {palette}
- Key Elements: {key_elements}
- UI Style: {ui_style}
- Mood: {mood}

**Intended Hook Type**: {hook_type}
**Generation Prompt**: {prompt}
**Model Used**: {model}

Score each dimension 1-10 and provide feedback."""


# ---------------------------------------------------------------------------
# Image Scorer
# ---------------------------------------------------------------------------
class CreativeImageScorer:
    """AI-powered quality scorer for generated ad creatives.

    Supports (priority order):
    - Lovart self-evaluation — uses Lovart AI to score images (no extra API key needed)
    - OpenAI Vision (gpt-4o) — real scoring with image analysis
    - Mock mode — heuristic scoring based on file size and metadata
    """

    # Weights for composite score
    WEIGHTS = {
        "visual_quality": 0.25,
        "brand_alignment": 0.25,
        "hook_clarity": 0.20,
        "ad_suitability": 0.20,
        "originality": 0.10,
    }

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gpt-4o",
        threshold: float = 6.0,
        base_url: str | None = None,
        use_lovart: bool = True,
    ) -> None:
        self._api_key = api_key or os.getenv("OPENAI_API_KEY")
        self._model = model
        self._threshold = threshold
        self._base_url = base_url or os.getenv("OPENAI_BASE_URL")
        self._client: Any = None
        self._lovart: Any = None

        # Try Lovart first (no extra API key needed)
        if use_lovart:
            try:
                from market_ops.clients.lovart import LovartClient
                self._lovart = LovartClient()
            except (ImportError, ValueError):
                self._lovart = None

        # Fallback to OpenAI Vision
        if self._api_key and _HAS_OPENAI:
            kwargs: dict[str, Any] = {"api_key": self._api_key}
            if self._base_url:
                kwargs["base_url"] = self._base_url
            self._client = OpenAI(**kwargs)

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
            return "openai-vision"
        return "mock"

    @property
    def threshold(self) -> float:
        return self._threshold

    # ----- Public API -----

    def score_image(
        self,
        image_path: str | Path,
        prompt: str = "",
        project: str = "P04 Witch",
        hook_type: str = "unknown",
        model: str = "unknown",
        image_id: str = "",
        image_url: str = "",
    ) -> ImageScore:
        """Score a single generated image.

        Tries in order: Lovart self-eval → OpenAI Vision → Mock.

        Args:
            image_path: Local file path of the image.
            prompt: The generation prompt used.
            project: Project name for brand alignment check.
            hook_type: Intended hook type (crisis/reward/etc).
            model: Model that generated the image.
            image_id: Unique image identifier.
            image_url: If image is from URL (Lovart), use this instead of file.

        Returns:
            ImageScore with all dimensions filled.
        """
        visual_ctx = GAME_VISUAL_CONTEXT.get(project, FALLBACK_VISUAL)

        # Try Lovart self-evaluation first (no extra API key needed)
        if self.is_lovart:
            try:
                score = self._score_with_lovart(
                    image_path=image_path,
                    prompt=prompt,
                    project=project,
                    hook_type=hook_type,
                    model=model,
                    image_id=image_id,
                )
                print(f"[Scorer] Lovart score: {score.overall:.1f}, "
                      f"passed: {score.passed}")
                return score
            except Exception as exc:
                print(f"[Scorer] Lovart eval failed: {exc}")

        # Fallback to OpenAI Vision
        if self._client:
            try:
                return self._score_with_vision(
                    image_path=image_path,
                    image_url=image_url,
                    prompt=prompt,
                    project=project,
                    hook_type=hook_type,
                    model=model,
                    image_id=image_id,
                    visual_ctx=visual_ctx,
                )
            except Exception as exc:
                print(f"[Scorer] Vision API failed: {exc}")

        # Final fallback: mock scoring
        return self._score_mock(
            image_path=image_path,
            prompt=prompt,
            project=project,
            hook_type=hook_type,
            model=model,
            image_id=image_id,
        )

    def score_batch(
        self,
        images: list[dict[str, Any]],
        project: str = "P04 Witch",
    ) -> ScoreBatch:
        """Score a batch of generated images.

        Args:
            images: List of dicts with keys: file_path, prompt_used, model,
                    image_id, hook_type, image_url (optional).
            project: Project name.

        Returns:
            ScoreBatch with pass/fail classification.
        """
        scores: list[ImageScore] = []
        for img in images:
            score = self.score_image(
                image_path=img.get("file_path", ""),
                prompt=img.get("prompt_used", ""),
                project=project,
                hook_type=img.get("hook_type", "unknown"),
                model=img.get("model", "unknown"),
                image_id=img.get("image_id", ""),
                image_url=img.get("image_url", ""),
            )
            scores.append(score)

        passed = [s for s in scores if s.passed]
        rejected = [s for s in scores if not s.passed]
        avg = sum(s.overall for s in scores) / len(scores) if scores else 0.0

        return ScoreBatch(
            total_scored=len(scores),
            total_passed=len(passed),
            total_rejected=len(rejected),
            avg_overall=round(avg, 2),
            threshold=self._threshold,
            scores=scores,
        )

    def get_rejected_prompts(self, score_batch: ScoreBatch) -> list[dict[str, Any]]:
        """Extract prompt info from rejected images for regeneration."""
        return [
            {
                "image_id": s.image_id,
                "prompt": s.prompt_used,
                "model": s.model,
                "score": s.overall,
                "reason": s.reject_reason,
                "improvements": s.improvements,
            }
            for s in score_batch.scores
            if not s.passed
        ]

    # ----- Lovart self-evaluation -----

    def _score_with_lovart(
        self,
        *,
        image_path: str | Path,
        prompt: str,
        project: str,
        hook_type: str,
        model: str,
        image_id: str,
    ) -> ImageScore:
        """Score using Lovart AI self-evaluation (no extra API key needed)."""
        if not Path(image_path).exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        result = self._lovart.evaluate_image(
            image_path=image_path,
            prompt=prompt,
            project=project,
            hook_type=hook_type,
        )

        if "error" in result:
            raise RuntimeError(result["error"])

        return self._build_score(image_id, str(image_path), prompt, model, result)

    # ----- Vision scoring -----

    def _score_with_vision(
        self,
        *,
        image_path: str | Path,
        image_url: str,
        prompt: str,
        project: str,
        hook_type: str,
        model: str,
        image_id: str,
        visual_ctx: dict[str, Any],
    ) -> ImageScore:
        """Score using OpenAI Vision API."""
        # Prepare image content
        image_content: list[dict[str, Any]] = []

        if image_url:
            image_content.append({
                "type": "image_url",
                "image_url": {"url": image_url, "detail": "high"},
            })
        elif image_path and Path(image_path).exists():
            img_data = Path(image_path).read_bytes()
            b64 = base64.b64encode(img_data).decode("utf-8")
            suffix = Path(image_path).suffix.lstrip(".") or "png"
            mime = f"image/{suffix}" if suffix != "jpg" else "image/jpeg"
            image_content.append({
                "type": "image_url",
                "image_url": {"url": f"data:{mime};base64,{b64}", "detail": "high"},
            })
        else:
            # No image available, return low score
            return ImageScore(
                image_id=image_id,
                file_path=str(image_path),
                prompt_used=prompt,
                model=model,
                reject_reason="Image file not found or URL empty",
                passed=False,
            )

        user_text = _SCORING_USER_TEMPLATE.format(
            project=project,
            genre=visual_ctx.get("genre", ""),
            palette=visual_ctx.get("palette", ""),
            key_elements=", ".join(visual_ctx.get("key_elements", [])),
            ui_style=visual_ctx.get("ui_style", ""),
            mood=visual_ctx.get("mood", ""),
            hook_type=hook_type,
            prompt=prompt,
            model=model,
        )

        try:
            response = self._client.chat.completions.create(
                model=self._model,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": _SCORING_SYSTEM},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": user_text},
                            *image_content,
                        ],
                    },
                ],
                max_tokens=1000,
            )
            content = response.choices[0].message.content or "{}"
            result = json.loads(content)
            return self._build_score(image_id, str(image_path), prompt, model, result)
        except Exception as exc:
            print(f"[Scorer] Vision API error for {image_id}: {exc}")
            raise  # Let caller handle fallback

    def _build_score(
        self,
        image_id: str,
        file_path: str,
        prompt: str,
        model: str,
        result: dict[str, Any],
    ) -> ImageScore:
        """Build ImageScore from AI response dict."""
        vq = float(result.get("visual_quality", 0))
        ba = float(result.get("brand_alignment", 0))
        hc = float(result.get("hook_clarity", 0))
        ads = float(result.get("ad_suitability", 0))
        orig = float(result.get("originality", 0))

        overall = (
            vq * self.WEIGHTS["visual_quality"]
            + ba * self.WEIGHTS["brand_alignment"]
            + hc * self.WEIGHTS["hook_clarity"]
            + ads * self.WEIGHTS["ad_suitability"]
            + orig * self.WEIGHTS["originality"]
        )

        passed = overall >= self._threshold
        reject_reason = ""
        if not passed:
            weak = []
            if vq < self._threshold:
                weak.append(f"visual_quality={vq:.1f}")
            if ba < self._threshold:
                weak.append(f"brand_alignment={ba:.1f}")
            if hc < self._threshold:
                weak.append(f"hook_clarity={hc:.1f}")
            if ads < self._threshold:
                weak.append(f"ad_suitability={ads:.1f}")
            reject_reason = f"Below threshold ({overall:.1f}<{self._threshold}): {', '.join(weak)}"

        return ImageScore(
            image_id=image_id,
            file_path=file_path,
            prompt_used=prompt,
            model=model,
            visual_quality=vq,
            brand_alignment=ba,
            hook_clarity=hc,
            ad_suitability=ads,
            originality=orig,
            overall=round(overall, 2),
            passed=passed,
            reject_reason=reject_reason,
            strengths=result.get("strengths", []),
            improvements=result.get("improvements", []),
            raw_feedback=result.get("summary", ""),
        )

    # ----- Mock scoring -----

    def _score_mock(
        self,
        *,
        image_path: str | Path,
        prompt: str,
        project: str,
        hook_type: str,
        model: str,
        image_id: str,
    ) -> ImageScore:
        """Heuristic mock scoring based on file properties and prompt analysis."""
        import hashlib

        # Deterministic pseudo-random based on prompt hash
        seed = int(hashlib.md5(prompt.encode()).hexdigest()[:8], 16)

        def _mock_score(offset: int, lo: float = 5.0, hi: float = 9.5) -> float:
            val = lo + ((seed + offset * 37) % 100) / 100 * (hi - lo)
            return round(val, 1)

        vq = _mock_score(1)
        ba = _mock_score(2)
        hc = _mock_score(3)
        ads = _mock_score(4)
        orig = _mock_score(5)

        # Boost scores for prompts with good keywords
        prompt_lower = prompt.lower()
        if any(w in prompt_lower for w in ("1:1 square", "1080x1080", "mobile", "ad creative")):
            ads = min(10, ads + 0.5)
        if any(w in prompt_lower for w in ("dark", "gothic", "purple", "magic")):
            if "witch" in project.lower():
                ba = min(10, ba + 0.5)
        if any(w in prompt_lower for w in ("dramatic", "bold", "intense")):
            hc = min(10, hc + 0.3)

        # Check file exists and has reasonable size
        fp = Path(image_path)
        if fp.exists():
            size_kb = fp.stat().st_size / 1024
            if size_kb < 50:
                vq = max(1, vq - 2.0)  # Too small = low quality
        elif not image_id.startswith("mock"):
            vq = max(1, vq - 1.0)  # File missing

        result = {
            "visual_quality": vq,
            "brand_alignment": ba,
            "hook_clarity": hc,
            "ad_suitability": ads,
            "originality": orig,
            "strengths": [f"File size OK ({fp.stat().st_size // 1024}KB)" if fp.exists() else "Placeholder"],
            "improvements": ["Mock mode — enable OpenAI Vision for real scoring"],
            "summary": f"Mock score: overall={vq*0.25+ba*0.25+hc*0.2+ads*0.2+orig*0.1:.1f}",
        }
        return self._build_score(image_id, str(image_path), prompt, model, result)


# ---------------------------------------------------------------------------
# Report helpers
# ---------------------------------------------------------------------------
def print_score_report(batch: ScoreBatch) -> None:
    """Print a formatted scoring report to console."""
    print(f"\n  Quality Score Report")
    print(f"  {'─'*50}")
    print(f"  Scored: {batch.total_scored} | Passed: {batch.total_passed} | "
          f"Rejected: {batch.total_rejected}")
    print(f"  Avg Score: {batch.avg_overall:.1f} | Threshold: {batch.threshold:.1f}")
    print(f"  {'─'*50}")

    for s in batch.scores:
        status = "✓" if s.passed else "✗"
        print(f"  {status} [{s.image_id}] {s.model} → {s.overall:.1f}")
        print(f"    VQ={s.visual_quality:.1f} BA={s.brand_alignment:.1f} "
              f"HC={s.hook_clarity:.1f} AS={s.ad_suitability:.1f} "
              f"OR={s.originality:.1f}")
        if s.strengths:
            print(f"    + {', '.join(s.strengths[:2])}")
        if not s.passed:
            print(f"    ! {s.reject_reason}")
    print()


def save_score_report(batch: ScoreBatch, output_path: str | Path) -> Path:
    """Save scoring report as JSON."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "total_scored": batch.total_scored,
        "total_passed": batch.total_passed,
        "total_rejected": batch.total_rejected,
        "avg_overall": batch.avg_overall,
        "threshold": batch.threshold,
        "scores": [asdict(s) for s in batch.scores],
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
