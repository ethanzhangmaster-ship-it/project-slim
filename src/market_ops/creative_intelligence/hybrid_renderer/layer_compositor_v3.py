"""Layer Compositor V3

V3 升级：
  - 禁止 resize full image，改为 crop → smart fit → compose
  - Gameplay: 保持 UI 比例，不做扭曲缩放
  - Character: 保持透明边缘，不做硬切
  - Reward: 保持高亮，不做色彩压暗
  - 固定 UA 层顺序
"""
from __future__ import annotations

from PIL import Image, ImageEnhance, ImageFilter, ImageStat


class LayerCompositorV3:
    """V3: Crop-based compositing for UA ad structure."""

    # Fixed UA layer order
    LAYER_ORDER = ["background", "gameplay", "progression", "character", "hook_banner", "cta"]

    def __init__(self, width: int = 1080, height: int = 1080) -> None:
        self.W = width
        self.H = height

    def create_canvas(self) -> Image.Image:
        """Create dark purple gradient canvas."""
        from PIL import ImageDraw
        canvas = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
        draw = ImageDraw.Draw(canvas)
        for y in range(self.H):
            t = y / self.H
            r = int(18 * (1 - t * 0.3))
            g = int(12 * (1 - t * 0.3))
            b = int(40 * (1 + t * 0.2))
            draw.line([(0, y), (self.W, y)], fill=(r, g, b, 255), width=1)
        return canvas

    def composite(self, layers: list[dict], base: Image.Image | None = None) -> Image.Image:
        """Composite layers in fixed UA order.

        Each layer dict:
          - image: PIL Image or file path
          - name: layer name for ordering
          - position: (x, y) or None
          - size: (w, h) or None
          - feather_radius: int
          - crop_strategy: "fit_center" | "crop_bottom" | "crop_center" | None
          - alpha: float (0-1)
        """
        canvas = base.copy() if base else self.create_canvas()

        def _order_key(layer: dict) -> int:
            name = layer.get("name", "")
            try:
                return self.LAYER_ORDER.index(name)
            except ValueError:
                return 99
        layers.sort(key=_order_key)

        for layer in layers:
            img = self._load_image(layer.get("image"))
            if img is None:
                continue

            pos = layer.get("position", None)
            size = layer.get("size", None)
            feather = layer.get("feather_radius", 0)
            alpha = layer.get("alpha", 1.0)
            crop_strategy = layer.get("crop_strategy", None)
            name = layer.get("name", "")

            # V3: Smart crop + fit — never just resize full image
            if size and crop_strategy:
                img = self._smart_crop_fit(img, size, crop_strategy)
            elif size:
                img = self._contain_fit(img, size)
            elif pos is None:
                img = img.resize((self.W, self.H), Image.LANCZOS)

            # Alpha
            if alpha < 1.0:
                img = self._apply_alpha(img, alpha)

            # Paste
            if pos:
                if feather > 0:
                    self._feather_paste(canvas, img, pos, feather)
                else:
                    canvas.paste(img, pos, img if img.mode == "RGBA" else None)
            else:
                canvas = Image.alpha_composite(canvas, img)

        return canvas

    def lighting_harmonize(self, canvas: Image.Image, strength: float = 0.95) -> Image.Image:
        enhancer = ImageEnhance.Contrast(canvas)
        return enhancer.enhance(strength)

    # ── Smart Crop + Fit ──────────────────────────────────────────────

    def _smart_crop_fit(self, img: Image.Image, target_size: tuple[int, int],
                        strategy: str) -> Image.Image:
        """Smart crop then fit into target region.

        Strategies:
          - fit_center: scale to fit, letterbox, center crop
          - crop_bottom: crop from bottom, keep top
          - crop_center: crop center of source
        """
        tw, th = target_size
        sw, sh = img.size

        if strategy == "crop_bottom":
            # Crop from bottom — keep the lower portion (for character feet)
            target_ratio = tw / th
            crop_h = int(sw / target_ratio)
            crop_h = min(crop_h, sh)
            top = max(0, sh - crop_h)
            img = img.crop((0, top, sw, sh))
        elif strategy == "crop_center":
            # Crop center portion
            target_ratio = tw / th
            src_ratio = sw / sh
            if src_ratio > target_ratio:
                new_w = int(sh * target_ratio)
                left = (sw - new_w) // 2
                img = img.crop((left, 0, left + new_w, sh))
            else:
                new_h = int(sw / target_ratio)
                top = (sh - new_h) // 2
                img = img.crop((0, top, sw, top + new_h))
        else:
            # fit_center: default — contain within bounds
            img = self._contain_fit(img, target_size)

        # Final resize to exact target
        img = img.resize((tw, th), Image.LANCZOS)
        return img

    def _contain_fit(self, img: Image.Image, target_size: tuple[int, int]) -> Image.Image:
        """Scale image to fit within target_size, maintaining aspect ratio."""
        tw, th = target_size
        sw, sh = img.size
        scale = min(tw / sw, th / sh)
        new_w = int(sw * scale)
        new_h = int(sh * scale)
        return img.resize((new_w, new_h), Image.LANCZOS)

    # ── Internal helpers ────────────────────────────────────────────────

    def _load_image(self, source: str | Image.Image | None) -> Image.Image | None:
        if source is None:
            return None
        if isinstance(source, Image.Image):
            return source.copy()
        try:
            return Image.open(source).convert("RGBA")
        except Exception:
            return None

    def _apply_alpha(self, img: Image.Image, alpha: float) -> Image.Image:
        if img.mode != "RGBA":
            img = img.convert("RGBA")
        r, g, b, a = img.split()
        a = a.point(lambda x: int(x * alpha))
        return Image.merge("RGBA", (r, g, b, a))

    def _feather_paste(self, canvas: Image.Image, overlay: Image.Image,
                       position: tuple[int, int], feather_radius: int = 40) -> None:
        temp = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        temp.paste(overlay, position, overlay if overlay.mode == "RGBA" else None)
        x, y = position
        w, h = overlay.size
        inner_w = max(1, w - feather_radius * 2)
        inner_h = max(1, h - feather_radius * 2)
        inner = Image.new("L", (inner_w, inner_h), 255)
        full_mask = Image.new("L", (w, h), 0)
        full_mask.paste(inner, (feather_radius, feather_radius))
        full_mask = full_mask.filter(ImageFilter.GaussianBlur(radius=feather_radius / 2))
        mask = Image.new("L", canvas.size, 0)
        mask.paste(full_mask, position)
        temp.putalpha(mask)
        result = Image.alpha_composite(canvas, temp)
        canvas.paste(result, (0, 0))