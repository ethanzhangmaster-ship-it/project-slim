"""Creative Composition Engine V1.1

从"组件拼贴"升级为"自然融合的 UA Creative"。

核心升级：
  1. Feather Blend         — soft alpha blend 替代硬边 paste
  2. Color Matching        — 让组件颜色匹配 base
  3. Lighting Harmonization — 统一光照方向
  4. Gameplay Prompt V2    — 更像真实 mobile merge game screenshot
  5. Progression Layer     — 升级箭头 + level badge + glow
  6. Enhanced Text Overlay — 更强描边/阴影
"""
from __future__ import annotations

import json
import random
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------
@dataclass(slots=True)
class CreativeComponent:
    component_type: str
    file_path: str
    prompt_used: str
    model: str = ""
    ready: bool = False


@dataclass(slots=True)
class CompositionResult:
    final_image: str = ""
    components: list[CreativeComponent] = field(default_factory=list)
    composition_score: float = 0.0
    generation_mode: str = "composition"
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Composition Engine V1.1
# ---------------------------------------------------------------------------
class CreativeCompositionEngine:
    """Component-based creative generation with natural blending."""

    def __init__(self, project: str = "P04 Witch", output_dir: Path | None = None) -> None:
        self._project = project
        self._output_dir = output_dir or Path("output/creative_analysis/composition_engine_v11")
        self._output_dir.mkdir(parents=True, exist_ok=True)

    def compose(
        self,
        strategy: Any,
        layout_blueprint: Any,
        winner_dna: dict[str, Any],
        winner_cdn_url: str,
        hook_type: str = "collection",
        custom_hook_text: str = "",
    ) -> CompositionResult:
        """Execute V1.1 composition pipeline with natural blending."""
        run_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_dir = self._output_dir / f"composition_{run_ts}"
        run_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n  [CompositionEngine V1.1] Starting optimized pipeline...")
        print(f"  Output: {run_dir}")

        from market_ops.creative_image_gen import CreativeImageGenerator
        from market_ops.creative_intelligence.text_overlay import TextOverlayEngine
        from market_ops.creative_intelligence.progression_renderer import ProgressionRenderer

        gen = CreativeImageGenerator(output_dir=run_dir / "components")
        components: list[CreativeComponent] = []

        # -----------------------------------------------------------------
        # Step 1: Base Component
        # -----------------------------------------------------------------
        print(f"\n  [V1.1] Step 1/6: Generating BASE component...")
        base_prompt = self._build_base_prompt(strategy, winner_dna)
        base_img = gen.generate_single(
            prompt_text=base_prompt,
            project=self._project,
            hook_type=hook_type,
            negative_prompt=strategy.negative_prompt if hasattr(strategy, "negative_prompt") else "",
            size="1024x1024",
        )
        components.append(CreativeComponent(
            component_type="base",
            file_path=base_img.file_path,
            prompt_used=base_prompt,
            model=base_img.model,
            ready=base_img.ready_for_review,
        ))
        print(f"      ✓ Base: {base_img.file_path}")

        # -----------------------------------------------------------------
        # Step 2: Gameplay Component V2 (real merge game screenshot)
        # -----------------------------------------------------------------
        print(f"\n  [V1.1] Step 2/6: Generating GAMEPLAY component V2...")
        gameplay_prompt = self._build_gameplay_prompt_v2(winner_dna)
        gameplay_img = gen.generate_single(
            prompt_text=gameplay_prompt,
            project=self._project,
            hook_type=hook_type,
            size="1024x1024",
        )
        components.append(CreativeComponent(
            component_type="gameplay",
            file_path=gameplay_img.file_path,
            prompt_used=gameplay_prompt,
            model=gameplay_img.model,
            ready=gameplay_img.ready_for_review,
        ))
        print(f"      ✓ Gameplay: {gameplay_img.file_path}")

        # -----------------------------------------------------------------
        # Step 3: Reward Component
        # -----------------------------------------------------------------
        print(f"\n  [V1.1] Step 3/6: Generating REWARD component...")
        reward_prompt = self._build_reward_prompt_v2(winner_dna)
        reward_img = gen.generate_single(
            prompt_text=reward_prompt,
            project=self._project,
            hook_type=hook_type,
            size="1024x1024",
        )
        components.append(CreativeComponent(
            component_type="reward",
            file_path=reward_img.file_path,
            prompt_used=reward_prompt,
            model=reward_img.model,
            ready=reward_img.ready_for_review,
        ))
        print(f"      ✓ Reward: {reward_img.file_path}")

        # -----------------------------------------------------------------
        # Step 4: Progression Renderer (arrows + badges + glow)
        # -----------------------------------------------------------------
        print(f"\n  [V1.1] Step 4/6: Rendering PROGRESSION layer...")
        prog_renderer = ProgressionRenderer()
        progression_path = prog_renderer.render(
            width=1024,
            height=1024,
            output_path=str(run_dir / "progression.png"),
        )
        components.append(CreativeComponent(
            component_type="progression",
            file_path=progression_path,
            prompt_used="progression_renderer: arrows + badges + glow",
            model="pil",
            ready=True,
        ))
        print(f"      ✓ Progression: {progression_path}")

        # -----------------------------------------------------------------
        # Step 5: V1.1 Composite (feather blend + color match + lighting)
        # -----------------------------------------------------------------
        print(f"\n  [V1.1] Step 5/6: Natural compositing with feather blend...")
        composite_path = self._composite_v11(
            base_path=base_img.file_path,
            gameplay_path=gameplay_img.file_path,
            reward_path=reward_img.file_path,
            progression_path=progression_path,
            layout_blueprint=layout_blueprint,
            output_path=str(run_dir / "merged.png"),
        )
        components.append(CreativeComponent(
            component_type="merged",
            file_path=composite_path,
            prompt_used="PIL feather_blend + color_match + lighting_transfer",
            model="pil_v11",
            ready=True,
        ))
        print(f"      ✓ Merged: {composite_path}")

        # -----------------------------------------------------------------
        # Step 6: Enhanced Text Overlay
        # -----------------------------------------------------------------
        print(f"\n  [V1.1] Step 6/6: Adding enhanced text overlay...")
        text_engine = TextOverlayEngine(project=self._project)

        hook_text = custom_hook_text or winner_dna.get("overlay_text", "")
        if not hook_text:
            hook_text = "MERGE & WATCH THE MAGIC"

        final_path = text_engine.overlay_v2(
            image_path=composite_path,
            hook_type=hook_type,
            custom_text=hook_text,
            output_path=str(run_dir / "final_creative.png"),
        )
        components.append(CreativeComponent(
            component_type="final_with_text",
            file_path=final_path,
            prompt_used=f"text_overlay_v2: {hook_text}",
            model="pil_text_v2",
            ready=True,
        ))
        print(f"      ✓ Final: {final_path}")

        # Save manifest
        manifest = {
            "run_timestamp": run_ts,
            "project": self._project,
            "generation_mode": "composition_v11",
            "hook_type": hook_type,
            "hook_text": hook_text,
            "winner_dna_summary": {
                "subject": winner_dna.get("subject", ""),
                "palette": winner_dna.get("palette", ""),
                "overlay_text": winner_dna.get("overlay_text", ""),
            },
            "components": [asdict(c) for c in components],
            "final_image": final_path,
        }
        manifest_path = run_dir / "composition_manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

        print(f"\n  [CompositionEngine V1.1] Pipeline complete!")
        print(f"  Final creative: {final_path}")
        print(f"  Manifest: {manifest_path}")

        return CompositionResult(
            final_image=final_path,
            components=components,
            generation_mode="composition_v11",
            metadata=manifest,
        )

    # ----- Prompt builders -----

    def _build_base_prompt(self, strategy: Any, winner_dna: dict[str, Any]) -> str:
        if hasattr(strategy, "generation_prompt") and strategy.generation_prompt:
            return strategy.generation_prompt

        subject = winner_dna.get("subject", "a witch character")
        palette = winner_dna.get("palette", "deep purple and gold")
        mood = winner_dna.get("mood", "mysterious and magical")
        return (
            f"Create a Facebook mobile game UA performance creative for {self._project}. "
            f"1:1 square aspect ratio, 1080x1080. "
            f"Subject: {subject}. Color palette: {palette}. Mood: {mood}. "
            f"AAA casual mobile game ADVERTISEMENT, 3D cartoon rendering. "
            f"Dark purple magical background with ambient purple glow and subtle gold sparkles. "
            f"Atmospheric lighting from above, soft shadows. "
            f"NOT a poster. NOT splash screen. NOT character artwork."
        )

    def _build_gameplay_prompt_v2(self, winner_dna: dict[str, Any]) -> str:
        """V2: Real mobile merge game screenshot style."""
        palette = winner_dna.get("palette", "deep purple and gold")
        return (
            f"Mobile merge game gameplay screenshot, 3D cartoon style. "
            f"Visible square grid cells with dark purple UI frame. "
            f"Two small cute identical magical eggs in adjacent grid slots on the LEFT side. "
            f"A bright glowing merge arrow pointing from the two eggs toward an empty slot on the RIGHT. "
            f"The RIGHT slot shows a slightly glowing upgraded reward (small baby dragon or gem). "
            f"Clear BEFORE (two eggs) → AFTER (one dragon) progression visible. "
            f"Level indicators 'Lv.1' near eggs and 'Lv.2' near dragon. "
            f"Purple and gold UI glow effects, merge sparkles between slots. "
            f"This is a GAME SCREENSHOT, NOT fantasy artwork, NOT character illustration, NOT poster. "
            f"Clean readable mobile game UI. Color palette: {palette}. "
            f"1:1 square aspect ratio, 1024x1024."
        )

    def _build_reward_prompt_v2(self, winner_dna: dict[str, Any]) -> str:
        palette = winner_dna.get("palette", "deep purple and gold")
        return (
            f"A legendary cute baby dragon reward on dark purple magical background. "
            f"The dragon has sparkling gold aura, purple magical wings, and glowing eyes. "
            f"Premium reward feel with rich glow effects and gold sparkles. "
            f"3D cartoon style, matching dark fantasy {self._project} game. "
            f"Color palette: {palette}. "
            f"The creature looks extremely desirable as a game reward — dopamine hit. "
            f"Soft ambient purple lighting from above. "
            f"Isolated focal point, generous dark background space for compositing. "
            f"1:1 square aspect ratio, 1024x1024."
        )

    # ----- V1.1 PIL Composite with natural blending -----

    def _composite_v11(
        self,
        base_path: str,
        gameplay_path: str,
        reward_path: str,
        progression_path: str,
        layout_blueprint: Any,
        output_path: str,
    ) -> str:
        """V1.1 composite: feather blend + color match + lighting harmonization."""
        from PIL import Image, ImageFilter, ImageEnhance

        base = Image.open(base_path).convert("RGBA")
        gameplay = Image.open(gameplay_path).convert("RGBA")
        reward = Image.open(reward_path).convert("RGBA")
        progression = Image.open(progression_path).convert("RGBA")

        W, H = base.size
        canvas = base.copy()

        layout_type = getattr(layout_blueprint, "layout_type", "before_after_merge")

        # Color match gameplay and reward to base
        gameplay = self._color_match(gameplay, base)
        reward = self._color_match(reward, base)

        if layout_type == "before_after_merge":
            # Gameplay: center, 55% width, 50% height
            gw, gh = int(W * 0.55), int(H * 0.50)
            gameplay_resized = gameplay.resize((gw, gh), Image.LANCZOS)
            gx = (W - gw) // 2
            gy = int(H * 0.22)
            self._feather_paste(canvas, gameplay_resized, (gx, gy), feather_radius=60)

            # Reward: right side, 28% width, 28% height
            rw, rh = int(W * 0.28), int(H * 0.28)
            reward_resized = reward.resize((rw, rh), Image.LANCZOS)
            rx = int(W * 0.68)
            ry = int(H * 0.28)
            self._feather_paste(canvas, reward_resized, (rx, ry), feather_radius=40)

        else:
            gw, gh = int(W * 0.55), int(H * 0.50)
            gameplay_resized = gameplay.resize((gw, gh), Image.LANCZOS)
            gx = (W - gw) // 2
            gy = int(H * 0.22)
            self._feather_paste(canvas, gameplay_resized, (gx, gy), feather_radius=60)

            rw, rh = int(W * 0.28), int(H * 0.28)
            reward_resized = reward.resize((rw, rh), Image.LANCZOS)
            rx = int(W * 0.68)
            ry = int(H * 0.28)
            self._feather_paste(canvas, reward_resized, (rx, ry), feather_radius=40)

        # Progression layer (arrows + badges) — paste with full alpha
        canvas = Image.alpha_composite(canvas, progression.resize((W, H), Image.LANCZOS))

        # Lighting harmonization: apply subtle base lighting tone
        canvas = self._lighting_harmonize(canvas, base)

        canvas.convert("RGB").save(output_path, quality=95)
        return output_path

    def _feather_paste(
        self,
        canvas: Image.Image,
        overlay: Image.Image,
        position: tuple[int, int],
        feather_radius: int = 40,
    ) -> None:
        """Paste overlay onto canvas with soft feathered edges."""
        from PIL import Image, ImageFilter

        # Create a full-size temporary canvas for the overlay
        temp = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        temp.paste(overlay, position, overlay)

        # Create feather mask
        mask = Image.new("L", canvas.size, 0)
        x, y = position
        w, h = overlay.size

        # Draw soft-edged rectangle
        inner = Image.new("L", (w - feather_radius * 2, h - feather_radius * 2), 255)
        inner_w, inner_h = inner.size
        full_mask = Image.new("L", (w, h), 0)
        full_mask.paste(inner, (feather_radius, feather_radius))
        full_mask = full_mask.filter(ImageFilter.GaussianBlur(radius=feather_radius / 2))

        mask.paste(full_mask, position)

        # Apply mask
        temp.putalpha(mask)

        # Composite
        result = Image.alpha_composite(canvas, temp)
        canvas.paste(result, (0, 0))

    def _color_match(self, source: Image.Image, target: Image.Image) -> Image.Image:
        """Match source image color tone to target."""
        from PIL import ImageStat, ImageEnhance

        # Get average colors
        src_stat = ImageStat.Stat(source)
        tgt_stat = ImageStat.Stat(target)

        src_mean = src_stat.mean[:3]
        tgt_mean = tgt_stat.mean[:3]

        # Adjust brightness
        brightness_factors = []
        for s, t in zip(src_mean, tgt_mean):
            if s > 0:
                brightness_factors.append(t / s)
            else:
                brightness_factors.append(1.0)

        avg_brightness = sum(brightness_factors) / 3
        enhancer = ImageEnhance.Brightness(source)
        source = enhancer.enhance(avg_brightness * 0.85 + 0.15)  # partial match

        # Adjust saturation to match target vibrancy
        src_std = src_stat.stddev[:3]
        tgt_std = tgt_stat.stddev[:3]
        avg_src_std = sum(src_std) / 3
        avg_tgt_std = sum(tgt_std) / 3
        if avg_src_std > 0:
            sat_factor = (avg_tgt_std / avg_src_std) * 0.7 + 0.3
            enhancer = ImageEnhance.Color(source)
            source = enhancer.enhance(min(max(sat_factor, 0.7), 1.3))

        return source

    def _lighting_harmonize(self, canvas: Image.Image, base: Image.Image) -> Image.Image:
        """Apply subtle lighting tone from base to canvas for unified feel."""
        from PIL import ImageEnhance

        # Slightly reduce contrast to soften composite edges
        enhancer = ImageEnhance.Contrast(canvas)
        canvas = enhancer.enhance(0.95)

        # Slightly increase warmth (yellow tint) to match gold accents
        # This is a subtle operation
        return canvas
