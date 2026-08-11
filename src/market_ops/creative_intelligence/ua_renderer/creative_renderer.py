"""UA Native Creative Renderer V1

Creative Composition Engine V1.2 核心编排器。

流程：
  Winner DNA → Template Engine → Layer Renderer Pipeline → Layer Composer → Final Creative

Pipeline:
  1. Template Engine   — 根据 layout_type 加载 UA 模板
  2. AI Image Gen      — 生成 base + character + reward 组件
  3. Gameplay Renderer — 渲染 merge game UI 层
  4. Progression V2    — 渲染进化时间线 + 箭头 + 光效
  5. CTA Renderer      — 渲染点击诱因层
  6. Text Overlay      — 文字叠加层
  7. Layer Compositor  — 高级合成（alpha blending + color match + lighting）
  8. Render Manifest   — 输出 manifest + layers 目录
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image


# ── Data Models ────────────────────────────────────────────────────────

@dataclass(slots=True)
class RenderLayer:
    name: str
    file_path: str
    content_type: str
    position: tuple[int, int] | None = None
    size: tuple[int, int] | None = None
    z_index: int = 0


@dataclass(slots=True)
class RenderResult:
    final_image: str = ""
    layers: list[RenderLayer] = field(default_factory=list)
    render_manifest: dict[str, Any] = field(default_factory=dict)
    generation_mode: str = "ua_renderer_v1"


# ── Creative Renderer ──────────────────────────────────────────────────

class UACreativeRenderer:
    """V1.2 UA Native Creative Renderer — AI素材 + 广告渲染引擎"""

    def __init__(self, project: str = "P04 Witch", output_dir: Path | None = None) -> None:
        self._project = project
        self._output_dir = output_dir or Path("output/creative_analysis/ua_renderer")
        self._output_dir.mkdir(parents=True, exist_ok=True)

    def render(
        self,
        strategy: Any,
        layout_blueprint: Any,
        winner_dna: dict[str, Any],
        winner_cdn_url: str,
        hook_type: str = "collection",
        custom_hook_text: str = "",
    ) -> RenderResult:
        """Execute UA Renderer V1 pipeline.

        Args:
            strategy: CreativePromptDirector 输出的 strategy
            layout_blueprint: CreativeLayoutPlanner 输出的 blueprint
            winner_dna: 赢家视觉 DNA
            winner_cdn_url: 赢家 CDN 参考图
            hook_type: hook 类型
            custom_hook_text: 自定义 hook 文字
        """
        run_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_dir = self._output_dir / f"render_{run_ts}"
        run_dir.mkdir(parents=True, exist_ok=True)
        layers_dir = run_dir / "layers"
        layers_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n  [UA Renderer V1] Starting pipeline...")
        print(f"  Output: {run_dir}")

        # ── Lazy imports ──
        from market_ops.creative_image_gen import CreativeImageGenerator
        from market_ops.creative_intelligence.ua_renderer.template_engine import TemplateEngine
        from market_ops.creative_intelligence.ua_renderer.gameplay_renderer import GameplayRenderer
        from market_ops.creative_intelligence.ua_renderer.progression_renderer import ProgressionRendererV2
        from market_ops.creative_intelligence.ua_renderer.cta_renderer import CTARenderer
        from market_ops.creative_intelligence.ua_renderer.layer_compositor import LayerCompositor
        from market_ops.creative_intelligence.text_overlay import TextOverlayEngine

        gen = CreativeImageGenerator(output_dir=run_dir / "components")
        template_engine = TemplateEngine()
        compositor = LayerCompositor(width=1080, height=1080)
        render_layers: list[RenderLayer] = []

        # ── Step 1: Load Template ──
        layout_type = getattr(layout_blueprint, "layout_type", "before_after_merge")
        template = template_engine.resolve_layout(layout_type)
        print(f"  [Step 1/7] Template: {template.template_name}")

        # ── Step 2: AI Components (base + reward) ──
        print(f"\n  [Step 2/7] Generating AI components...")

        # Base background
        base_prompt = self._build_base_prompt(strategy, winner_dna)
        base_img = gen.generate_single(
            prompt_text=base_prompt,
            project=self._project,
            hook_type=hook_type,
            negative_prompt=getattr(strategy, "negative_prompt", ""),
            size="1080x1080",
        )
        base_path = str(layers_dir / "base.png")
        Image.open(base_img.file_path).convert("RGB").resize((1080, 1080)).save(base_path)
        render_layers.append(RenderLayer(
            name="base", file_path=base_path, content_type="base", z_index=0,
        ))
        print(f"      ✓ Base: {base_path}")

        # Reward character
        reward_prompt = self._build_reward_prompt(winner_dna)
        reward_img = gen.generate_single(
            prompt_text=reward_prompt,
            project=self._project,
            hook_type=hook_type,
            size="1080x1080",
        )
        reward_path = str(layers_dir / "reward.png")
        Image.open(reward_img.file_path).convert("RGBA").resize((1080, 1080)).save(reward_path)
        render_layers.append(RenderLayer(
            name="reward", file_path=reward_path, content_type="reward", z_index=15,
        ))
        print(f"      ✓ Reward: {reward_path}")

        # ── Step 3: Gameplay Layer ──
        print(f"\n  [Step 3/7] Rendering Gameplay layer...")
        gameplay_renderer = GameplayRenderer(width=1080, height=1080)
        gameplay_path = str(layers_dir / "gameplay.png")

        merge_config = template.config.get("merge_config", {})
        ui_config = template.config.get("ui_elements", {})
        gameplay_renderer.render(
            output_path=gameplay_path,
            before_items=merge_config.get("before_items", ["egg_lv1", "egg_lv1"]),
            after_item=merge_config.get("after_item", "dragon"),
            show_ui=True,
            ui_config=ui_config,
        )
        render_layers.append(RenderLayer(
            name="gameplay", file_path=gameplay_path, content_type="gameplay", z_index=20,
        ))
        print(f"      ✓ Gameplay: {gameplay_path}")

        # ── Step 4: Progression V2 ──
        print(f"\n  [Step 4/7] Rendering Progression V2 layer...")
        prog_renderer = ProgressionRendererV2()
        prog_path = str(layers_dir / "progression.png")
        prog_renderer.render(
            width=1080, height=1080, output_path=prog_path,
            mode="merge_evolution",
        )
        render_layers.append(RenderLayer(
            name="progression", file_path=prog_path, content_type="progression", z_index=25,
        ))
        print(f"      ✓ Progression: {prog_path}")

        # ── Step 5: CTA Layer ──
        print(f"\n  [Step 5/7] Rendering CTA layer...")
        cta_renderer = CTARenderer()
        cta_path = str(layers_dir / "cta.png")
        cta_renderer.render(
            width=1080, height=1080, output_path=cta_path,
            cta_type="merge",
            position="bottom",
        )
        render_layers.append(RenderLayer(
            name="cta", file_path=cta_path, content_type="cta", z_index=30,
        ))
        print(f"      ✓ CTA: {cta_path}")

        # ── Step 6: Layer Compositing ──
        print(f"\n  [Step 6/7] Compositing all layers...")
        composite_layers = []
        for layer in render_layers:
            layer_info = self._build_layer_info(layer, template, compositor)
            composite_layers.append(layer_info)

        canvas = compositor.composite(composite_layers)
        merged_path = str(layers_dir / "merged.png")
        canvas = compositor.lighting_harmonize(canvas, strength=0.95)
        canvas.convert("RGB").save(merged_path, quality=95)
        print(f"      ✓ Merged: {merged_path}")

        # ── Step 7: Text Overlay ──
        print(f"\n  [Step 7/7] Adding text overlay...")
        text_engine = TextOverlayEngine(project=self._project)
        hook_text = custom_hook_text or winner_dna.get("overlay_text", "")
        if not hook_text:
            hook_text = "MERGE & EVOLVE"

        final_path = str(run_dir / "final_creative.png")
        text_engine.overlay_v2(
            image_path=merged_path,
            hook_type=hook_type,
            custom_text=hook_text,
            output_path=final_path,
        )
        print(f"      ✓ Final: {final_path}")

        # ── Manifest ──
        manifest = {
            "run_timestamp": run_ts,
            "project": self._project,
            "generation_mode": "ua_renderer_v1",
            "template": template.template_id,
            "template_name": template.template_name,
            "hook_type": hook_type,
            "hook_text": hook_text,
            "winner_dna_summary": {
                "subject": winner_dna.get("subject", ""),
                "palette": winner_dna.get("palette", ""),
                "overlay_text": winner_dna.get("overlay_text", ""),
            },
            "layers": [
                {"name": l.name, "path": l.file_path, "content_type": l.content_type, "z_index": l.z_index}
                for l in render_layers
            ],
            "final_image": final_path,
        }
        manifest_path = run_dir / "render_manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

        print(f"\n  [UA Renderer V1] Pipeline complete!")
        print(f"  Final creative: {final_path}")
        print(f"  Manifest: {manifest_path}")

        return RenderResult(
            final_image=final_path,
            layers=render_layers,
            render_manifest=manifest,
            generation_mode="ua_renderer_v1",
        )

    # ── Layer info builder ──────────────────────────────────────────────

    def _build_layer_info(
        self, layer: RenderLayer, template: Any, compositor: LayerCompositor,
    ) -> dict:
        """Build layer info dict for compositor, mapping template layout to positions."""
        W, H = compositor.W, compositor.H

        # Find matching template layer
        tmpl = None
        for tl in template.layers:
            if layer.content_type == "base" and "background" in tl.content.lower():
                tmpl = tl
                break
            elif layer.content_type in tl.content.lower() or layer.content_type in tl.name.lower():
                tmpl = tl
                break
            elif layer.content_type == "reward" and "character" in tl.content.lower():
                tmpl = tl
                break

        if tmpl:
            px = int(tmpl.x * W)
            py = int(tmpl.y * H)
            pw = int(tmpl.width * W)
            ph = int(tmpl.height * H)
            return {
                "image": layer.file_path,
                "position": (px, py),
                "size": (pw, ph),
                "feather_radius": 40 if layer.content_type in ("reward", "character") else 0,
                "color_match": layer.content_type != "base",
                "z_index": tmpl.z_index,
            }

        # Default: full canvas
        return {
            "image": layer.file_path,
            "position": None,
            "size": None,
            "feather_radius": 0,
            "color_match": True,
            "z_index": layer.z_index,
        }

    # ── Prompt builders ─────────────────────────────────────────────────

    def _build_base_prompt(self, strategy: Any, winner_dna: dict[str, Any]) -> str:
        if hasattr(strategy, "generation_prompt") and strategy.generation_prompt:
            return strategy.generation_prompt

        subject = winner_dna.get("subject", "a witch character")
        palette = winner_dna.get("palette", "deep purple and gold")
        mood = winner_dna.get("mood", "mysterious and magical")
        return (
            f"Facebook mobile game UA performance creative background for {self._project}. "
            f"1:1 square, 1080x1080. "
            f"Dark purple magical background with ambient purple glow and subtle gold sparkles. "
            f"Atmospheric lighting from above, soft shadows. "
            f"Dark gradient edges for UA text overlay space. "
            f"NOT a poster. NOT splash screen. NOT character artwork. "
            f"Color palette: {palette}. Mood: {mood}."
        )

    def _build_reward_prompt(self, winner_dna: dict[str, Any]) -> str:
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
            f"1:1 square aspect ratio, 1080x1080."
        )