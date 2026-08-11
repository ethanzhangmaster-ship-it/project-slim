"""Hybrid UA Creative Renderer V1.3.2

V1.3.2 升级：
  - Gameplay Asset Generator V1.2 (严格 prompt, 真实截图)
  - 5 候选生成 + Quality Gate V2 筛选最佳
  - UA Fixed Layout V4 (固定垂直分段结构)
  - Layer Compositor V3 (crop 替代 resize, 保持比例)
  - Character Renderer V2 (右下角限制, 非主视觉)
  - Progression Renderer V4 (箭头视觉化进化: 🥚→💥→🐉)
  - Text Overlay V3.2 (简化文字, Impact字体, 顶部固定)
  - CTA Renderer V3 (固定 PLAY NOW, 右下角发光按钮)

Pipeline:
Load Template → Build UA Layout → Generate 3 Gameplay → Quality Gate → Select Best →
Generate Character → Render Progression → Render Hook → Render CTA →
Compose → Quality Score → Output
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
class HybridRenderResultV132:
    final_image: str = ""
    layers: list[LayerRecord] = field(default_factory=list)
    render_manifest: dict[str, Any] = field(default_factory=dict)
    generation_mode: str = "hybrid_renderer_v1.3.2"
    quality_score: dict[str, Any] = field(default_factory=dict)


class HybridCreativeRendererV132:
    """V1.3.2: UA Structure Controller + AI素材 + 质量检测 → 可投放Creative.

    Fixed UA structure:
      15% → HOOK
      45% → GAMEPLAY
      20% → PROGRESSION
      15% → CHARACTER
       5% → CTA
    """

    def __init__(self, project: str = "P04 Witch", output_dir: Path | None = None) -> None:
        self._project = project
        self._output_dir = output_dir or Path("output/creative_intelligence/runs/hybrid_v132")
        self._output_dir.mkdir(parents=True, exist_ok=True)

    def render(
        self,
        strategy: Any,
        layout_blueprint: Any,
        winner_dna: dict[str, Any],
        winner_cdn_url: str,
    ) -> HybridRenderResultV132:
        """Execute Hybrid Renderer V1.3.2 optimized pipeline."""
        run_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_dir = self._output_dir / f"render_{run_ts}"
        run_dir.mkdir(parents=True, exist_ok=True)
        layers_dir = run_dir / "layers"
        layers_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n  [Hybrid Renderer V1.3.2] Starting optimized UA pipeline...")
        print(f"  Output: {run_dir}")

        # Lazy imports
        from market_ops.creative_image_gen import CreativeImageGenerator
        from market_ops.creative_intelligence.hybrid_renderer.template_engine_v2 import TemplateEngineV2
        from market_ops.creative_intelligence.hybrid_renderer.gameplay_asset_generator_v12 import GameplayAssetGeneratorV12
        from market_ops.creative_intelligence.hybrid_renderer.character_asset_generator_v2 import CharacterAssetGeneratorV2
        from market_ops.creative_intelligence.hybrid_renderer.gameplay_quality_gate import GameplayQualityGate
        from market_ops.creative_intelligence.hybrid_renderer.layer_compositor_v3 import LayerCompositorV3
        from market_ops.creative_intelligence.hybrid_renderer.progression_renderer_v4 import ProgressionRendererV4
        from market_ops.creative_intelligence.hybrid_renderer.text_overlay_v32 import TextOverlayV32
        from market_ops.creative_intelligence.hybrid_renderer.cta_renderer_v3 import CTARendererV3
        from market_ops.creative_intelligence.hybrid_renderer.render_manifest import ManifestBuilder

        gen = CreativeImageGenerator(output_dir=layers_dir / "ai_components")
        template_engine = TemplateEngineV2()
        compositor = LayerCompositorV3(width=1080, height=1080)
        manifest_builder = ManifestBuilder()
        records: list[LayerRecord] = []

        # ── Step 1: Load V4 Template ──
        print(f"\n  [Step 1/11] Template: Load UA Fixed Layout V4")
        layout_type = getattr(layout_blueprint, "layout_type", "merge_evolution")
        template = template_engine.resolve_layout(layout_type)
        manifest_builder.set_template(template.template_id, template.template_name)
        print(f"      Template: {template.template_name}, {len(template.layers)} layers")

        # ── Step 2: Build UA Layout Constraint ──
        print(f"\n  [Step 2/11] Building UA constrained layout map...")
        from market_ops.creative_intelligence.hybrid_renderer.layout_constraint import LayoutConstraintEngine
        constraint_engine = LayoutConstraintEngine()
        constraint = constraint_engine.build(layout_blueprint, template)
        print(f"      Regions: {len(constraint.regions)} (all with smart crop)")

        # ── Step 3: Generate 5 Gameplay Candidates ──
        print(f"\n  [Step 3/11] Generating 3 gameplay candidates (V1.2)...")
        gameplay_gen = GameplayAssetGeneratorV12()
        gameplay_config = template.config.get("gameplay_config", {})
        candidate_result = gameplay_gen.generate_candidates(
            generator=gen, project=self._project, output_dir=str(run_dir),
            winner_dna=winner_dna, template_config=gameplay_config, num_candidates=3,
        )
        gameplay_path = candidate_result["selected_path"]
        records.append(LayerRecord(name="gameplay", path=gameplay_path, content_type="gameplay"))
        print(f"      Best candidate: score={candidate_result['best_score']:.0f}/100")

        # ── Step 4: Gameplay Quality Gate ──
        print(f"\n  [Step 4/11] Gameplay Quality Gate evaluation...")
        gate = GameplayQualityGate()
        quality_result = gate.evaluate(gameplay_path)
        quality_path = str(run_dir / "gameplay_quality.json")
        gate.save_report(quality_result, quality_path)
        print(f"      Quality: {quality_result.total_score:.0f}/100 "
              f"(board={quality_result.board_score:.0f} ui={quality_result.ui_score:.0f} "
              f"merge={quality_result.merge_score:.0f} auth={quality_result.auth_score:.0f})")
        print(f"      Passed: {quality_result.passed}")

        # ── Step 5: Generate Character V2 ──
        print(f"\n  [Step 5/10] Generating Character (V2, small support)...")
        char_gen = CharacterAssetGeneratorV2()
        char_path = str(layers_dir / "character.png")
        char_config = template.config.get("character_config", {})
        char_gen.generate(
            generator=gen, project=self._project, output_path=char_path,
            winner_dna=winner_dna, template_config=char_config,
        )
        records.append(LayerRecord(name="character", path=char_path, content_type="character"))
        print(f"      ✓ Character: {char_path}")

        # ── Step 6: Render Progression V4 ──
        print(f"\n  [Step 6/10] Rendering Progression V4 (visual arrows)...")
        prog_renderer = ProgressionRendererV4()
        prog_path = str(layers_dir / "progression.png")
        prog_renderer.render(width=1080, height=1080, output_path=prog_path, mode="egg_to_dragon")
        records.append(LayerRecord(name="progression", path=prog_path, content_type="progression"))
        print(f"      ✓ Progression: {prog_path}")

        # ── Step 7: Render Text Overlay V3.2 ──
        print(f"\n  [Step 7/10] Rendering Text Overlay V3.2 (simplified hook)...")
        text_renderer = TextOverlayV32()
        text_path = str(layers_dir / "text.png")
        raw_hook_text = winner_dna.get("overlay_text", "Merge & Watch the Magic")
        text_renderer.render(
            width=1080, height=1080, output_path=text_path,
            hook_text=raw_hook_text, position="top",
        )
        records.append(LayerRecord(name="hook_banner", path=text_path, content_type="text"))
        print(f"      ✓ Text: {text_path}")

        # ── Step 8: Render CTA V3 ──
        print(f"\n  [Step 8/10] Rendering CTA V3 (PLAY NOW)...")
        cta_renderer = CTARendererV3()
        cta_path = str(layers_dir / "cta.png")
        cta_renderer.render(
            width=1080, height=1080, output_path=cta_path,
            cta_text="PLAY NOW", position="bottom_right",
        )
        records.append(LayerRecord(name="cta", path=cta_path, content_type="cta"))
        print(f"      ✓ CTA: {cta_path}")

        # ── Step 9: Composite All Layers (V3 with smart crop) ──
        print(f"\n  [Step 9/10] Compositing all layers (smart crop + constraint)...")
        composite_layers = self._build_composite_layers_v3(
            constraint, records, constraint_engine,
        )
        canvas = compositor.composite(composite_layers)
        canvas = compositor.lighting_harmonize(canvas, strength=0.95)

        final_path = str(run_dir / "final_creative.png")
        canvas.convert("RGB").save(final_path, quality=95)
        print(f"      ✓ Final: {final_path}")

        # ── Step 10: Build Manifest ──
        manifest_builder.set_creative_id(f"hybrid_v132_{run_ts}")
        manifest_builder.set_project(self._project)
        manifest_builder.set_final_image(final_path)
        manifest_builder.set_winner_dna(winner_dna)
        manifest_builder.set_metadata("hook_text", winner_dna.get("overlay_text", ""))
        manifest_builder.set_metadata("renderer_version", "v1.3.2")
        manifest_builder.set_metadata("gameplay_quality", quality_result.total_score)
        for r in records:
            manifest_builder.add_layer(name=r.name, path=r.path, generator=r.content_type)

        manifest_path = run_dir / "render_manifest.json"
        manifest_builder.save(str(manifest_path))

        print(f"\n  [Hybrid Renderer V1.3.2] Optimized pipeline complete!")
        print(f"  Final creative: {final_path}")
        print(f"  Manifest: {manifest_path}")
        print(f"  Gameplay quality: {quality_result.total_score:.0f}/100")

        return HybridRenderResultV132(
            final_image=final_path,
            layers=records,
            render_manifest=json.loads(manifest_path.read_text(encoding="utf-8")),
            generation_mode="hybrid_renderer_v1.3.2",
            quality_score={
                "total": quality_result.total_score,
                "board": quality_result.board_score,
                "ui": quality_result.ui_score,
                "merge": quality_result.merge_score,
                "auth": quality_result.auth_score,
                "passed": quality_result.passed,
            },
        )

    # ── Build composite layers with smart crop from constraint ─────────────

    def _build_composite_layers_v3(
        self, constraint: Any, records: list[LayerRecord],
        constraint_engine: Any,
    ) -> list[dict]:
        """Build layer info dicts using smart_crop from constraint engine."""
        layers = []

        for record in records:
            region = constraint.get_region(record.content_type)
            if not region:
                region = constraint.get_region(record.name)

            if region:
                from PIL import Image
                cropped_img, pos = constraint_engine.smart_crop(record.path, region)
                layers.append({
                    "name": record.content_type,
                    "image": cropped_img,
                    "position": pos,
                    "size": None,
                    "feather_radius": region.feather,
                    "crop_strategy": region.crop_strategy,
                    "color_match": True,
                })
            else:
                # No constraint region — skip this layer (don't paste full-size)
                print(f"      ⚠ Skipping layer '{record.name}' (no constraint region)")

        return layers