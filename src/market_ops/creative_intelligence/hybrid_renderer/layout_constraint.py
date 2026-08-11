"""Layout Constraint Engine V1

Layout Blueprint → Render Position Map.

核心职责：确保最终广告结构与 Layout Blueprint 一致。
把模板的 float 坐标映射到实际的像素位置，并用 smart crop 策略避免缩放失真。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ConstraintRegion:
    """A single region in the render map."""
    name: str
    x: int = 0
    y: int = 0
    w: int = 0
    h: int = 0
    crop_strategy: str = "fit"  # fit | crop_center | crop_bottom | crop_top | none
    crop_scale: float = 1.0    # What fraction of source image to use (0.7 = center 70%)
    z_index: int = 0
    feather: int = 0


@dataclass(slots=True)
class LayoutConstraint:
    """Full render constraint map for a 1080x1080 canvas."""
    width: int = 1080
    height: int = 1080
    regions: list[ConstraintRegion] = field(default_factory=list)

    def get_region(self, name: str) -> ConstraintRegion | None:
        for r in self.regions:
            if r.name == name:
                return r
        return None


class LayoutConstraintEngine:
    """Convert Layout Blueprint + Template to precise pixel position map."""

    CANVAS_W = 1080
    CANVAS_H = 1080

    def build(self, layout_blueprint: Any, template: Any) -> LayoutConstraint:
        """Build constraint map from blueprint + template.

        Smart crop strategy per region:
          - gameplay: crop_center 70% (keep merge board, lose edges)
          - character: crop_bottom 75% (keep full body, anchor bottom)
          - reward: crop_center 80% (highlight reward, no edge distortion)
          - text: fit (overlay, no crop needed)
          - cta: fit (overlay, no crop needed)
          - progression: fit (overlay, no crop needed)
        """
        constraint = LayoutConstraint()

        # Map each template layer to a constraint region
        for tl in template.layers:
            region = self._build_region(tl)
            constraint.regions.append(region)

        return constraint

    def _build_region(self, tl: Any) -> ConstraintRegion:
        """Convert template layer to constraint region with smart crop."""
        x = int(tl.x * self.CANVAS_W)
        y = int(tl.y * self.CANVAS_H)
        w = int(tl.width * self.CANVAS_W)
        h = int(tl.height * self.CANVAS_H)
        name = tl.name
        content = tl.content if hasattr(tl, "content") else ""

        # Determine crop strategy
        crop_strategy = "fit"
        crop_scale = 1.0

        if "gameplay" in name.lower() or "gameplay" in content.lower():
            # Gameplay: crop center 70% — keep the merge board, drop edges
            crop_strategy = "crop_center"
            crop_scale = 0.70
        elif "character" in name.lower() or "character" in content.lower():
            # Character: crop bottom 75% — keep full body, anchor bottom
            crop_strategy = "crop_bottom"
            crop_scale = 0.75
        elif "reward" in name.lower() or "reward" in content.lower():
            # Reward: crop center 80% — highlight the dragon/reward
            crop_strategy = "crop_center"
            crop_scale = 0.80
        elif "before" in name.lower() or "after" in name.lower():
            crop_strategy = "crop_center"
            crop_scale = 0.75
        elif any(kw in name.lower() for kw in ("text", "hook", "cta", "progression", "banner")):
            # Overlay layers: crop exact region from full canvas (NOT resize)
            crop_strategy = "crop_region"
            crop_scale = 1.0

        feather = getattr(tl, "feather_radius", 0)
        z = getattr(tl, "z_index", 0)

        return ConstraintRegion(
            name=name, x=x, y=y, w=w, h=h,
            crop_strategy=crop_strategy,
            crop_scale=crop_scale,
            z_index=z,
            feather=feather,
        )

    def smart_crop(self, source: Any, region: ConstraintRegion) -> Any:
        """Apply smart crop to source image based on region strategy.

        Returns (cropped_img, paste_position) tuple.
        Instead of resizing 1080x1080 into a small region, we crop the
        source image to keep the important part at full resolution.
        """
        from PIL import Image
        if isinstance(source, str):
            img = Image.open(source).convert("RGBA")
        else:
            img = source

        src_w, src_h = img.size

        if region.crop_strategy == "crop_region":
            # Overlay layers: crop exact region from full canvas (no resize)
            cropped = img.crop((region.x, region.y, region.x + region.w, region.y + region.h))
            return cropped, (region.x, region.y)
        elif region.crop_strategy == "fit" or region.crop_scale >= 1.0:
            # Just resize to fit
            img = img.resize((region.w, region.h), Image.LANCZOS)
            return img, (region.x, region.y)

        # Crop the source image
        crop_w = int(src_w * region.crop_scale)
        crop_h = int(src_h * region.crop_scale)

        if region.crop_strategy == "crop_center":
            cx, cy = src_w // 2, src_h // 2
            left = max(0, cx - crop_w // 2)
            top = max(0, cy - crop_h // 2)
        elif region.crop_strategy == "crop_bottom":
            left = (src_w - crop_w) // 2
            top = src_h - crop_h
        elif region.crop_strategy == "crop_top":
            left = (src_w - crop_w) // 2
            top = 0
        else:
            # Default: center crop
            cx, cy = src_w // 2, src_h // 2
            left = max(0, cx - crop_w // 2)
            top = max(0, cy - crop_h // 2)

        right = min(src_w, left + crop_w)
        bottom = min(src_h, top + crop_h)
        cropped = img.crop((left, top, right, bottom))

        # Now resize the cropped image to fit the region
        cropped = cropped.resize((region.w, region.h), Image.LANCZOS)
        return cropped, (region.x, region.y)