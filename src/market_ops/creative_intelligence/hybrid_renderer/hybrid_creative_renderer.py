"""Hybrid UA Creative Renderer V1.3.1

Creative Composition Engine V1.3.1 — Optimized Pipeline.

核心修复:
  1. Hook 文案不再丢失 — resolve_hook_text() 优先级链
  2. AI Asset 不用 resize 缩放 — smart_crop strategy 保持质量
  3. Layout Constraint Engine 确保最终结构与 Blueprint 一致

Pipeline:
  Layout → Director → Generate Assets → Gameplay Validator
  → Layout Constraint → Smart Crop → Progression Layer
  → Text Layer (w/ resolve_hook_text) → CTA → Composite → Evaluation
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class LayerRecord:
    name: str
    path: str
    content_type: str


@dataclass(slots=True)
class HybridRenderResult:
    final_image: str = ""
    layers: list[LayerRecord] = field(default_factory=list)
    render_manifest: dict[str, Any] = field(default_factory=dict)
    generation_mode: str = "hybrid_renderer_v1.1"


class HybridCreativeRenderer:
    """V1.3.1: AI生成真实手游素材 + 布局约束 + 智能裁剪 + 广告渲染引擎"""

    def __init__(self, project: str = "P04 Witch", output_dir: Path | None = None) -> None:
        self._project = project
        self._output_dir = output_dir or Path("output/creative_analysis/hybrid_renderer")
        self._output_dir.mkdir(parents=True, exist_ok=True)

    def render(
        self,
        strategy: Any,
        layout_blueprint: Any,
        winner_dna: dict[str, Any],
        winner_cdn_url: str,
        hook_type: str = "collection",
        custom_hook_text: str = "",
    ) -> HybridRenderResult:
        """Execute Hybrid Renderer V1.3.1 pipeline."""
        run_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_dir = self._output_dir / f"render_{run_ts}"
        run_dir.mkdir(parents=True, exist_ok=True)
        layers_dir = run_dir / "layers"
        layers_dir.mkdir(parents=True, exist_ok=True)
        validation_dir = run_dir / "validation"
        validation_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n  [Hybrid Renderer V1.3.1] Starting optimized pipeline...")
        print(f"  Output: {run_dir}")

        # ── Lazy imports ──
        from market_ops.creative_image_gen import CreativeImageGenerator
        from market_ops.creative_intelligence.hybrid_renderer.template_engine_v2 import TemplateEngineV2
        from market_ops.creative_intelligence.hybrid_renderer.gameplay_asset_generator import GameplayAssetGeneratorV11
        from market_ops.creative_intelligence.hybrid_renderer.character_asset_generator import CharacterAssetGenerator
        from market_ops.creative_intelligence.hybrid_renderer.reward_asset_generator import RewardAssetGenerator
        from market_ops.creative_intelligence.hybrid_renderer.gameplay_validator import GameplayValidator
        from market_ops.creative_intelligence.hybrid_renderer.layout_constraint import LayoutConstraintEngine
        from market_ops.creative_intelligence.hybrid_renderer.progression_renderer_v3 import ProgressionRendererV3
        from market_ops.creative_intelligence.hybrid_renderer.text_overlay_v3 import TextOverlayV3
        from market_ops.creative_intelligence.hybrid_renderer.cta_renderer_v2 import CTARendererV2
        from market_ops.creative_intelligence.hybrid_renderer.layer_compositor_v2 import LayerCompositorV2
        from market_ops.creative_intelligence.hybrid_renderer.render_manifest import ManifestBuilder

        gen = CreativeImageGenerator(output_dir=layers_dir / "ai_components")
        template_engine = TemplateEngineV2()
        constraint_engine = LayoutConstraintEngine()
        compositor = LayerCompositorV2(width=1080, height=1080)
        manifest_builder = ManifestBuilder()
        records: list[LayerRecord] = []

        # ── Step 1: Load V3 Template ──
        layout_type = getattr(layout_blueprint, "layout_type", "merge_evolution")
        template = template_engine.resolve_layout(layout_type)
        manifest_builder.set_template(template.template_id, template.template_name)
        print(f"  [Step 1/10] Template: {template.template_name}")

        # ── Step 2: Build Layout Constraint ──
        print(f"  [Step 2/10] Building layout constraint map...")
        constraint = constraint_engine.build(layout_blueprint, template)
        print(f"      Regions: {len(constraint.regions)} (smart crop configured)")

        # ── Step 3: Generate AI Gameplay Asset (V1.1 with auto-retry) ──
        print(f"\n  [Step 3/10] Generating AI Gameplay Asset (V1.1, auto-retry)...")
        gameplay_gen = GameplayAssetGeneratorV11()
        gameplay_path = str(layers_dir / "gameplay.png")
        gameplay_config = template.config.get("gameplay_config", {})
        gameplay_gen.generate(
            generator=gen, project=self._project, output_path=gameplay_path,
            winner_dna=winner_dna, template_config=gameplay_config, max_retries=2,
        )
        records.append(LayerRecord(name="gameplay", path=gameplay_path, content_type="gameplay"))
        print(f"      ✓ Gameplay: {gameplay_path}")

        # ── Step 4: Generate AI Character Asset ──
        print(f"\n  [Step 4/10] Generating AI Character Asset...")
        char_gen = CharacterAssetGenerator()
        char_path = str(layers_dir / "character.png")
        char_config = template.config.get("character_config", {})
        char_gen.generate(
            generator=gen, project=self._project, output_path=char_path,
            winner_dna=winner_dna, template_config=char_config,
        )
        records.append(LayerRecord(name="character", path=char_path, content_type="character"))
        print(f"      ✓ Character: {char_path}")

        # ── Step 5: Generate AI Reward Asset ──
        print(f"\n  [Step 5/10] Generating AI Reward Asset...")
        reward_gen = RewardAssetGenerator()
        reward_path = str(layers_dir / "reward.png")
        reward_config = template.config.get("reward_config", {})
        reward_gen.generate(
            generator=gen, project=self._project, output_path=reward_path,
            winner_dna=winner_dna, template_config=reward_config,
        )
        records.append(LayerRecord(name="reward", path=reward_path, content_type="reward"))
        print(f"      ✓ Reward: {reward_path}")

        # ── Step 6: Validate Gameplay ──
        print(f"\n  [Step 6/10] Validating Gameplay Asset...")
        validator = GameplayValidator()
        validation = validator.validate(gameplay_path)
        validation_path = validation_dir / "gameplay_score.json"
        validator.save_report(validation, str(validation_path))
        manifest_builder.set_validation(
            validation.gameplay_score, validation.board_visible,
            validation.merge_action_visible, validation.progression_visible,
        )
        print(f"      ✓ Gameplay Score: {validation.gameplay_score:.2f}")
        print(f"        Board: {validation.board_visible}, Merge: {validation.merge_action_visible}")

        # ── Step 7: Render Progression V3 ──
        print(f"\n  [Step 7/10] Rendering Progression V3 (Evolution Timeline)...")
        prog_renderer = ProgressionRendererV3()
        prog_path = str(layers_dir / "progression.png")
        prog_renderer.render(width=1080, height=1080, output_path=prog_path, mode="merge_evolution")
        records.append(LayerRecord(name="progression", path=prog_path, content_type="progression"))
        print(f"      ✓ Progression: {prog_path}")

        # ── Step 8: Render Text Overlay V3.1 (with resolve_hook_text) ──
        print(f"\n  [Step 8/10] Rendering Text Overlay V3.1 (resolve_hook_text)...")
        text_renderer = TextOverlayV3()
        text_path = str(layers_dir / "text.png")
        text_renderer.render(
            width=1080, height=1080, output_path=text_path,
            hook_type=hook_type, custom_text=custom_hook_text, position="top",
            winner_dna=winner_dna, layout_blueprint=layout_blueprint,
            prompt_strategy=strategy,
        )
        records.append(LayerRecord(name="text", path=text_path, content_type="text"))
        print(f"      ✓ Text: {text_path}")

        # ── Step 9: Render CTA V2.1 (auto-select) ──
        print(f"\n  [Step 9/10] Rendering CTA V2.1 (auto-select)...")
        cta_renderer = CTARendererV2()
        cta_path = str(layers_dir / "cta.png")
        cta_renderer.render(
            width=1080, height=1080, output_path=cta_path,
            cta_type="auto", position="bottom",
            winner_dna=winner_dna, hook_type=hook_type,
        )
        records.append(LayerRecord(name="cta", path=cta_path, content_type="cta"))
        print(f"      ✓ CTA: {cta_path}")

        # ── Step 10: Composite All Layers (with smart_crop + constraint) ──
        print(f"\n  [Step 10/10] Compositing all layers (smart crop + constraint)...")
        composite_layers = self._build_composite_layers_v2(
            constraint, records, constraint_engine,
        )
        canvas = compositor.composite(composite_layers)
        canvas = compositor.lighting_harmonize(canvas, strength=0.95)

        final_path = str(run_dir / "final_creative.png")
        canvas.convert("RGB").save(final_path, quality=95)
        print(f"      ✓ Final: {final_path}")

        # ── Build Manifest ──
        manifest_builder.set_creative_id(f"hybrid_v131_{run_ts}")
        manifest_builder.set_project(self._project)
        manifest_builder.set_final_image(final_path)
        manifest_builder.set_winner_dna(winner_dna)
        manifest_builder.set_metadata("hook_type", hook_type)
        manifest_builder.set_metadata("hook_text", custom_hook_text or winner_dna.get("overlay_text", ""))
        manifest_builder.set_metadata("renderer_version", "v1.3.1")
        for r in records:
            manifest_builder.add_layer(name=r.name, path=r.path, generator=r.content_type)

        manifest_path = run_dir / "render_manifest.json"
        manifest_builder.save(str(manifest_path))

        print(f"\n  [Hybrid Renderer V1.3.1] Optimized pipeline complete!")
        print(f"  Final creative: {final_path}")
        print(f"  Manifest: {manifest_path}")

        return HybridRenderResult(
            final_image=final_path,
            layers=records,
            render_manifest=json.loads(manifest_path.read_text(encoding="utf-8")),
            generation_mode="hybrid_renderer_v1.1",
        )

    # ── Layer compositing with smart_crop ──────────────────────────────

    def _build_composite_layers_v2(
        self, constraint: Any, records: list[LayerRecord],
        constraint_engine: Any,
    ) -> list[dict]:
        """Build layer info dicts using smart_crop from constraint engine."""
        layers = []

        for record in records:
            region = constraint.get_region(record.content_type)
            if not region:
                # Try matching by name
                region = constraint.get_region(record.name)

            if region:
                # Apply smart_crop
                cropped_img, pos = constraint_engine.smart_crop(record.path, region)
                layers.append({
                    "name": record.content_type,
                    "image": cropped_img,
                    "position": pos,
                    "size": None,  # Already cropped/resized
                    "feather_radius": region.feather,
                    "color_match": True,
                })
            else:
                # No constraint region — paste full image
                layers.append({
                    "name": record.content_type,
                    "image": record.path,
                    "position": None,
                    "size": None,
                    "feather_radius": 0,
                    "color_match": True,
                })

        return layers