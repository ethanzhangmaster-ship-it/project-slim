"""Hybrid UA Creative Renderer V1.4 — Real Asset Foundation

V1.4 核心升级：
  - BASE: 真实 FB 赢家素材（非 Lovart AI 幻想图）
  - Gameplay: 直接使用真实 FB 投放素材（720x1280+ 高清图）
  - Overlay: Hook 文字 + CTA 按钮 + Progression 指示器
  - Layout: 继承 V1.3.2 的 UA Fixed Layout V4 结构
  - Composite: 智能裁剪 + 叠加合成

Pipeline (V1.4):
  Load Winner DNA → Select Best Real Asset → Load Real Image →
  Build Layout → Render Overlays (Hook/CTA/Progression) →
  Composite → Output
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
class HybridRenderResultV14:
    final_image: str = ""
    real_base_source: str = ""
    layers: list[LayerRecord] = field(default_factory=list)
    render_manifest: dict[str, Any] = field(default_factory=dict)
    generation_mode: str = "hybrid_renderer_v1.4_real_asset"
    quality_score: dict[str, Any] = field(default_factory=dict)


class HybridCreativeRendererV14:
    """V1.4: Real Asset Base + AI Overlay → 可投放 UA Creative.

    Fixed UA structure:
      15% → HOOK BANNER
      45% → GAMEPLAY (real FB asset)
      20% → PROGRESSION
      15% → CHARACTER
       5% → CTA
    """

    def __init__(
        self,
        project: str = "P04 Evolution Merge",
        real_assets_dir: str | None = None,
        dna_cache_path: str | None = None,
        output_dir: str | None = None,
    ) -> None:
        self._project = project
        self._output_dir = Path(output_dir or "output/creative_intelligence/runs/hybrid_v14")
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._real_assets_dir = Path(
            real_assets_dir or "output/creative_analysis/real_assets"
        )
        self._dna_cache_path = Path(
            dna_cache_path or "output/creative_analysis/dna_cache/real_winners_dna_vision.json"
        )

    def render(
        self,
        strategy: Any = None,
        layout_blueprint: Any = None,
        winner_dna: dict[str, Any] | None = None,
        winner_cdn_url: str = "",
    ) -> HybridRenderResultV14:
        """Execute Hybrid Renderer V1.4 pipeline with real asset base."""
        run_ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_dir = self._output_dir / f"render_{run_ts}"
        run_dir.mkdir(parents=True, exist_ok=True)
        layers_dir = run_dir / "layers"
        layers_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n  [Hybrid Renderer V1.4] Real Asset Foundation Pipeline")
        print(f"  Output: {run_dir}")

        # Lazy imports
        from market_ops.creative_intelligence.hybrid_renderer.layout_constraint import (
            LayoutConstraintEngine,
        )
        from market_ops.creative_intelligence.hybrid_renderer.layer_compositor_v3 import (
            LayerCompositorV3,
        )
        from market_ops.creative_intelligence.hybrid_renderer.text_overlay_v32 import (
            TextOverlayV32,
        )
        from market_ops.creative_intelligence.hybrid_renderer.cta_renderer_v3 import (
            CTARendererV3,
        )
        from market_ops.creative_intelligence.hybrid_renderer.progression_renderer_v4 import (
            ProgressionRendererV4,
        )
        from market_ops.creative_intelligence.hybrid_renderer.template_engine_v2 import (
            TemplateEngineV2,
        )

        compositor = LayerCompositorV3(width=1080, height=1080)
        records: list[LayerRecord] = []

        # ── Step 1: Load Winner DNA (real data) ──
        print(f"\n  [Step 1/8] Loading real Winner DNA...")
        if winner_dna is None:
            winner_dna = self._load_best_winner_dna()
        print(f"      Creative: {winner_dna.get('creative_id', 'N/A')}")
        print(f"      ROAS: {winner_dna.get('roas', 0):.2f}")
        vdna = winner_dna.get("visual_dna", {})
        print(f"      Hook: {vdna.get('hook_type', 'N/A')} | Palette: {vdna.get('palette', 'N/A')[:40]}")

        # ── Step 2: Load Real Asset ──
        print(f"\n  [Step 2/8] Loading real FB asset as base...")
        real_asset_path = self._get_real_asset_path(winner_dna)
        if not real_asset_path:
            raise FileNotFoundError("No real asset found for winner")
        print(f"      Asset: {Path(real_asset_path).name}")
        records.append(LayerRecord(name="gameplay_real", path=real_asset_path, content_type="real_fb_asset"))

        # ── Step 3: Load Template ──
        print(f"\n  [Step 3/8] Template: UA Fixed Layout V4")
        layout_type = getattr(layout_blueprint, "layout_type", "merge_evolution") if layout_blueprint else "merge_evolution"
        template_engine = TemplateEngineV2()
        template = template_engine.resolve_layout(layout_type)
        print(f"      Template: {template.template_name}, {len(template.layers)} layers")

        # ── Step 4: Build Layout Constraint ──
        print(f"\n  [Step 4/8] Building layout constraint map...")
        constraint_engine = LayoutConstraintEngine()
        constraint = constraint_engine.build(layout_blueprint, template)
        print(f"      Regions: {len(constraint.regions)}")

        # ── Step 5: Render Hook/Text Overlay ──
        print(f"\n  [Step 5/8] Rendering Hook text overlay...")
        text_renderer = TextOverlayV32()
        text_path = str(layers_dir / "hook_text.png")
        hook_text = vdna.get("overlay_text", "Merge & Evolve!")
        # Clean up hook text
        if len(hook_text) > 30:
            hook_text = hook_text[:30] + "..."
        text_renderer.render(
            width=1080, height=1080, output_path=text_path,
            hook_text=hook_text, position="top",
        )
        records.append(LayerRecord(name="hook_banner", path=text_path, content_type="text_overlay"))

        # ── Step 6: Render Progression ──
        print(f"\n  [Step 6/8] Rendering Progression indicator...")
        prog_renderer = ProgressionRendererV4()
        prog_path = str(layers_dir / "progression.png")
        prog_renderer.render(
            width=1080, height=1080, output_path=prog_path,
            mode="egg_to_dragon",
        )
        records.append(LayerRecord(name="progression", path=prog_path, content_type="progression"))

        # ── Step 7: Render CTA ──
        print(f"\n  [Step 7/8] Rendering CTA button...")
        cta_renderer = CTARendererV3()
        cta_path = str(layers_dir / "cta.png")
        cta_renderer.render(
            width=1080, height=1080, output_path=cta_path,
            cta_text="PLAY NOW", position="bottom_right",
        )
        records.append(LayerRecord(name="cta", path=cta_path, content_type="cta"))

        # ── Step 8: Composite ──
        print(f"\n  [Step 8/8] Compositing all layers...")
        composite_layers = self._build_composite_layers_v14(constraint, records, constraint_engine)
        canvas = compositor.composite(composite_layers)
        canvas = compositor.lighting_harmonize(canvas, strength=0.90)

        final_path = str(run_dir / "final_creative_v14.png")
        canvas.convert("RGB").save(final_path, quality=95)
        print(f"      Final: {final_path}")

        # Save manifest
        manifest = {
            "version": "1.4.0",
            "timestamp": datetime.now().isoformat(),
            "creative_id": f"hybrid_v14_{run_ts}",
            "project": self._project,
            "winner_creative_id": winner_dna.get("creative_id", ""),
            "winner_roas": winner_dna.get("roas", 0),
            "real_asset_base": real_asset_path,
            "hook_text": hook_text,
            "layers": [{"name": r.name, "path": r.path, "type": r.content_type} for r in records],
            "final_image": final_path,
        }
        manifest_path = run_dir / "render_manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)

        print(f"\n  [Hybrid Renderer V1.4] Complete!")
        print(f"  Real base: {Path(real_asset_path).name}")
        print(f"  Final: {final_path}")

        return HybridRenderResultV14(
            final_image=final_path,
            real_base_source=real_asset_path,
            layers=records,
            render_manifest=manifest,
            generation_mode="hybrid_renderer_v1.4_real_asset",
            quality_score={"mode": "real_asset_base", "passed": True},
        )

    def _load_best_winner_dna(self) -> dict[str, Any]:
        """Load the best-performing winner DNA from cache."""
        with open(self._dna_cache_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        winners = data.get("winners", [])
        # Sort by ROAS
        winners.sort(key=lambda w: w.get("roas", 0), reverse=True)
        return winners[0] if winners else {}

    def _get_real_asset_path(self, winner_dna: dict[str, Any]) -> str:
        """Get local path to real FB asset image."""
        local_path = winner_dna.get("local_image_path", "")
        if local_path and Path(local_path).exists():
            return local_path

        # Fallback: search by creative_id
        creative_id = winner_dna.get("creative_id", "")
        for pattern in [f"fb_{creative_id}.jpg", f"fb_api_{creative_id}.jpg"]:
            p = self._real_assets_dir / pattern
            if p.exists():
                return str(p)

        # Final fallback: any image in real_assets
        images = list(self._real_assets_dir.glob("*.jpg"))
        if images:
            return str(images[0])

        raise FileNotFoundError(f"No real asset for {creative_id}")

    # Map V1.4 layer names to constraint region names
    NAME_MAP = {
        "gameplay_real": "gameplay",
        "hook_banner": "hook_banner",
        "progression": "progression",
        "cta": "cta",
    }

    def _build_composite_layers_v14(
        self, constraint: Any, records: list[LayerRecord],
        constraint_engine: Any,
    ) -> list[dict]:
        """Build layer info dicts for V1.4 compositing.
        
        Uses the same approach as V1.3.2: smart_crop via constraint engine.
        """
        layers = []

        for record in records:
            # Map V1.4 layer name to constraint region name
            region_name = self.NAME_MAP.get(record.name, record.name)
            region = constraint.get_region(region_name)
            
            if not region:
                region = constraint.get_region(record.content_type)
            if not region:
                # Try fuzzy match
                for r in constraint.regions:
                    if record.name in r.name or r.name in record.name:
                        region = r
                        region_name = r.name
                        break

            if region:
                from PIL import Image
                cropped_img, pos = constraint_engine.smart_crop(record.path, region)
                layers.append({
                    "name": region_name,
                    "image": cropped_img,
                    "position": pos,
                    "size": None,
                    "feather_radius": region.feather,
                    "crop_strategy": region.crop_strategy,
                    "color_match": True,
                })
            else:
                print(f"      WARNING: No constraint region for {record.name}, skipping")

        return layers


def render_v14(
    project: str = "P04 Evolution Merge",
    output_dir: str | None = None,
) -> HybridRenderResultV14:
    """Quick render entry point for V1.4."""
    renderer = HybridCreativeRendererV14(
        project=project,
        output_dir=output_dir,
    )
    return renderer.render()