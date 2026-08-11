"""CTA Renderer V3

V3 升级：
  - 固定: "PLAY NOW"
  - 位置: bottom-right
  - 尺寸: 300x100
  - 效果: shadow + glow + pulse
"""
from __future__ import annotations

import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter


class CTARendererV3:
    """V3: Fixed CTA button with glow and pulse effects."""

    def render(
        self,
        width: int = 1080,
        height: int = 1080,
        output_path: str = "cta.png",
        cta_text: str = "PLAY NOW",
        position: str = "bottom_right",
    ) -> str:
        """Render CTA button with glow/pulse effect.

        Args:
            width, height: Canvas size
            output_path: Output path
            cta_text: CTA text (default "PLAY NOW")
            position: "bottom_right" (fixed)
        """
        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Button dimensions
        btn_w = 300
        btn_h = 100
        btn_x = width - btn_w - 30
        btn_y = height - btn_h - 20

        # Load font
        font = self._load_font(42)
        if not font:
            font = ImageFont.load_default()

        # Outer glow (pulse effect)
        for g in range(15, 0, -3):
            alpha = int(10 - g * 0.5)
            gx = btn_x - g
            gy = btn_y - g
            gw = btn_w + g * 2
            gh = btn_h + g * 2
            draw.rounded_rectangle(
                [gx, gy, gx + gw, gy + gh],
                radius=20, fill=(255, 180, 50, max(0, alpha)),
            )

        # Button shadow
        draw.rounded_rectangle(
            [btn_x + 4, btn_y + 4, btn_x + btn_w + 4, btn_y + btn_h + 4],
            radius=15, fill=(0, 0, 0, 180),
        )

        # Button background (gradient-like via two layers)
        draw.rounded_rectangle(
            [btn_x, btn_y, btn_x + btn_w, btn_y + btn_h],
            radius=15, fill=(255, 160, 30, 255),
        )
        # Inner highlight
        draw.rounded_rectangle(
            [btn_x + 4, btn_y + 4, btn_x + btn_w - 4, btn_y + btn_h // 2],
            radius=12, fill=(255, 200, 80, 100),
        )

        # Button border
        draw.rounded_rectangle(
            [btn_x, btn_y, btn_x + btn_w, btn_y + btn_h],
            radius=15, outline=(255, 215, 0, 255), width=3,
        )

        # Text
        bbox = draw.textbbox((0, 0), cta_text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        tx = btn_x + (btn_w - tw) // 2
        ty = btn_y + (btn_h - th) // 2 - 2

        # Text shadow
        draw.text((tx + 2, ty + 2), cta_text, font=font, fill=(0, 0, 0, 180))
        # Text outline
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            draw.text((tx + dx, ty + dy), cta_text, font=font, fill=(0, 0, 0, 200))
        # Text fill
        draw.text((tx, ty), cta_text, font=font, fill=(255, 255, 255, 255))

        # Play triangle icon
        icon_size = 20
        icon_x = tx - icon_size - 10
        icon_y = ty + th // 2 - icon_size // 2
        draw.polygon([
            (icon_x, icon_y),
            (icon_x, icon_y + icon_size),
            (icon_x + icon_size, icon_y + icon_size // 2),
        ], fill=(255, 255, 255, 255))

        img.save(output_path)
        return output_path

    def _load_font(self, size: int) -> ImageFont.FreeTypeFont | None:
        paths = [
            "C:/Windows/Fonts/impact.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/segoeuib.ttf",
        ]
        for fp in paths:
            if os.path.exists(fp):
                try:
                    return ImageFont.truetype(fp, size)
                except Exception:
                    continue
        return None