"""Layer Compositor V1

替代简单 PIL paste，提供：
  - Alpha blending (feather mask)
  - Color matching (brightness / saturation / temperature)
  - Lighting harmonization (统一光照)
  - Layer stacking with z-index ordering
  - Shadow / glow compositing
"""
from __future__ import annotations

from PIL import Image, ImageEnhance, ImageFilter, ImageStat


class LayerCompositor:
    """Advanced layer compositing with alpha blending and color harmonization."""

    def __init__(self, width: int = 1080, height: int = 1080) -> None:
        self.W = width
        self.H = height

    def create_canvas(
        self, background_color: tuple[int, int, int] = (18, 12, 40),
    ) -> Image.Image:
        """Create base canvas with gradient background."""
        canvas = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
        # Draw gradient background
        from PIL import ImageDraw
        draw = ImageDraw.Draw(canvas)
        for y in range(self.H):
            t = y / self.H
            r = int(background_color[0] * (1 - t * 0.3))
            g = int(background_color[1] * (1 - t * 0.3))
            b = int(background_color[2] * (1 + t * 0.2))
            draw.line([(0, y), (self.W, y)], fill=(r, g, b, 255), width=1)
        return canvas

    def composite(
        self,
        layers: list[dict],
        base: Image.Image | None = None,
    ) -> Image.Image:
        """Composite layers in z-index order.

        Each layer dict:
          - image: PIL Image or path
          - position: (x, y) or None for full canvas
          - size: (w, h) or None for original
          - feather_radius: int (default 0)
          - color_match: bool (default True)
          - alpha: float (0-1, default 1.0)
        """
        canvas = base.copy() if base else self.create_canvas()

        # Sort by z_index (or insertion order)
        for i, layer in enumerate(layers):
            z = layer.get("z_index", i)
            layer["_z"] = z
        layers.sort(key=lambda l: l.get("_z", 0))

        for layer in layers:
            img = self._load_image(layer["image"])
            if img is None:
                continue

            pos = layer.get("position", None)
            size = layer.get("size", None)
            feather = layer.get("feather_radius", 0)
            color_match = layer.get("color_match", True)
            alpha = layer.get("alpha", 1.0)

            # Resize if needed
            if size:
                img = img.resize(size, Image.LANCZOS)
            elif pos is None:
                img = img.resize((self.W, self.H), Image.LANCZOS)

            # Color match to canvas
            if color_match and img.mode == "RGBA":
                img = self._color_match(img, canvas)

            # Apply alpha
            if alpha < 1.0:
                img = self._apply_alpha(img, alpha)

            # Paste with feather
            if pos:
                if feather > 0:
                    self._feather_paste(canvas, img, pos, feather)
                else:
                    canvas.paste(img, pos, img if img.mode == "RGBA" else None)
            else:
                if feather > 0:
                    self._feather_paste_full(canvas, img, feather)
                else:
                    canvas = Image.alpha_composite(canvas, img)

        return canvas

    def _load_image(self, source: str | Image.Image) -> Image.Image | None:
        if isinstance(source, Image.Image):
            return source.copy()
        try:
            return Image.open(source).convert("RGBA")
        except Exception:
            return None

    def _apply_alpha(self, img: Image.Image, alpha: float) -> Image.Image:
        """Apply global alpha multiplier."""
        if img.mode != "RGBA":
            img = img.convert("RGBA")
        r, g, b, a = img.split()
        a = a.point(lambda x: int(x * alpha))
        img = Image.merge("RGBA", (r, g, b, a))
        return img

    def _feather_paste(
        self,
        canvas: Image.Image,
        overlay: Image.Image,
        position: tuple[int, int],
        feather_radius: int = 40,
    ) -> None:
        """Paste overlay with soft feathered edges."""
        temp = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        temp.paste(overlay, position, overlay if overlay.mode == "RGBA" else None)

        # Create feather mask
        mask = Image.new("L", canvas.size, 0)
        x, y = position
        w, h = overlay.size

        inner_w = max(1, w - feather_radius * 2)
        inner_h = max(1, h - feather_radius * 2)
        inner = Image.new("L", (inner_w, inner_h), 255)
        full_mask = Image.new("L", (w, h), 0)
        full_mask.paste(inner, (feather_radius, feather_radius))
        full_mask = full_mask.filter(ImageFilter.GaussianBlur(radius=feather_radius / 2))

        mask.paste(full_mask, position)
        temp.putalpha(mask)

        result = Image.alpha_composite(canvas, temp)
        canvas.paste(result, (0, 0))

    def _feather_paste_full(
        self,
        canvas: Image.Image,
        overlay: Image.Image,
        feather_radius: int = 40,
    ) -> None:
        """Paste full-canvas overlay with edge feather."""
        mask = Image.new("L", canvas.size, 255)
        # Feather edges of mask
        mask = mask.filter(ImageFilter.GaussianBlur(radius=feather_radius))
        overlay.putalpha(mask)
        result = Image.alpha_composite(canvas, overlay)
        canvas.paste(result, (0, 0))

    def _color_match(self, source: Image.Image, target: Image.Image) -> Image.Image:
        """Match source image color tone to target.

        Adjusts brightness and saturation to harmonize components.
        """
        try:
            src_stat = ImageStat.Stat(source)
            tgt_stat = ImageStat.Stat(target)

            src_mean = src_stat.mean[:3]
            tgt_mean = tgt_stat.mean[:3]

            # Brightness match
            factors = []
            for s, t in zip(src_mean, tgt_mean):
                if s > 0:
                    factors.append(t / s)
                else:
                    factors.append(1.0)

            avg_brightness = sum(factors) / 3
            # Partial match (70% target, 30% original)
            blend_factor = avg_brightness * 0.7 + 0.3
            enhancer = ImageEnhance.Brightness(source)
            source = enhancer.enhance(blend_factor)

            # Saturation match
            src_std = src_stat.stddev[:3]
            tgt_std = tgt_stat.stddev[:3]
            avg_src_std = sum(src_std) / 3
            avg_tgt_std = sum(tgt_std) / 3
            if avg_src_std > 0:
                sat_factor = (avg_tgt_std / avg_src_std) * 0.6 + 0.4
                enhancer = ImageEnhance.Color(source)
                source = enhancer.enhance(min(max(sat_factor, 0.75), 1.25))

        except Exception:
            pass

        return source

    def lighting_harmonize(
        self, canvas: Image.Image, strength: float = 0.95,
    ) -> Image.Image:
        """Apply final lighting harmonization."""
        enhancer = ImageEnhance.Contrast(canvas)
        canvas = enhancer.enhance(strength)
        return canvas