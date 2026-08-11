"""Progression Renderer V1

生成视觉升级反馈层：
  - 升级箭头 (glowing merge arrows)
  - Level Badge (Lv.1 → Lv.2 → Legendary)
  - Evolution Burst (glow/sparkle effects)

作为透明 PNG overlay 叠加到最终 creative 上，强化 Hook clarity。
"""
from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont, ImageFilter
import math


class ProgressionRenderer:
    """Renders progression indicators (arrows, badges, glow) as transparent overlay."""

    def __init__(self) -> None:
        pass

    def render(
        self,
        width: int = 1024,
        height: int = 1024,
        output_path: str = "progression.png",
    ) -> str:
        """Render a full-size transparent progression overlay.

        Layout (for before_after_merge):
          - Arrow: center, pointing left→right
          - Lv.1 badge: left side
          - Lv.2 badge: right side
          - Glow burst: center
        """
        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        cx, cy = width // 2, height // 2

        # 1. Draw glowing merge arrow (center, horizontal)
        self._draw_glowing_arrow(draw, cx, int(height * 0.42), width * 0.25, color=(255, 215, 0))

        # 2. Draw level badges
        self._draw_level_badge(draw, int(width * 0.22), int(height * 0.38), "Lv.1", color=(200, 180, 255))
        self._draw_level_badge(draw, int(width * 0.78), int(height * 0.38), "Lv.2", color=(255, 215, 0))

        # 3. Draw evolution burst glow at center
        self._draw_evolution_burst(img, cx, int(height * 0.42), radius=80)

        # 4. Draw small sparkle particles
        self._draw_sparkles(draw, width, height)

        img.save(output_path)
        return output_path

    def _draw_glowing_arrow(
        self,
        draw: ImageDraw.Draw,
        cx: int,
        cy: int,
        length: float,
        color: tuple[int, int, int] = (255, 215, 0),
    ) -> None:
        """Draw a horizontal glowing arrow with gradient effect."""
        half_len = length / 2
        x1, y1 = int(cx - half_len), cy
        x2, y2 = int(cx + half_len), cy

        # Draw multiple lines for glow effect
        for offset in range(8, 0, -1):
            alpha = int(80 - offset * 8)
            glow_color = color + (alpha,)
            draw.line(
                [(x1, y1 - offset), (x2, y2 - offset)],
                fill=glow_color,
                width=4 + offset,
            )
            draw.line(
                [(x1, y1 + offset), (x2, y2 + offset)],
                fill=glow_color,
                width=4 + offset,
            )

        # Main arrow line
        draw.line([(x1, y1), (x2, y2)], fill=color + (255,), width=4)

        # Arrowhead
        head_size = 20
        draw.polygon(
            [
                (x2, y2),
                (x2 - head_size, y2 - head_size // 2),
                (x2 - head_size, y2 + head_size // 2),
            ],
            fill=color + (255,),
        )

        # Arrowhead glow
        for offset in range(4, 0, -1):
            alpha = int(60 - offset * 12)
            draw.polygon(
                [
                    (x2, y2),
                    (x2 - head_size - offset * 2, y2 - head_size // 2 - offset),
                    (x2 - head_size - offset * 2, y2 + head_size // 2 + offset),
                ],
                fill=color + (alpha,),
            )

    def _draw_level_badge(
        self,
        draw: ImageDraw.Draw,
        x: int,
        y: int,
        text: str,
        color: tuple[int, int, int] = (255, 215, 0),
    ) -> None:
        """Draw a circular level badge with text."""
        radius = 28

        # Glow ring
        for r in range(radius + 12, radius, -2):
            alpha = int(40 - (r - radius) * 4)
            draw.ellipse(
                [x - r, y - r, x + r, y + r],
                outline=color + (alpha,),
                width=2,
            )

        # Main circle
        draw.ellipse(
            [x - radius, y - radius, x + radius, y + radius],
            fill=(30, 15, 50, 230),
            outline=color + (255,),
            width=3,
        )

        # Text
        font = self._load_font(22)
        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        tx = x - tw // 2
        ty = y - th // 2

        # Text shadow
        draw.text((tx + 1, ty + 1), text, font=font, fill=(0, 0, 0, 180))
        draw.text((tx, ty), text, font=font, fill=color + (255,))

    def _draw_evolution_burst(self, img: Image.Image, cx: int, cy: int, radius: int = 80) -> None:
        """Draw a radial glow burst at center."""
        burst = Image.new("RGBA", img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(burst)

        for r in range(radius, 0, -4):
            alpha = int(30 * (r / radius))
            draw.ellipse(
                [cx - r, cy - r, cx + r, cy + r],
                fill=(255, 215, 0, alpha),
            )

        # Blur for soft glow
        burst = burst.filter(ImageFilter.GaussianBlur(radius=15))
        img.paste(burst, (0, 0), burst)

    def _draw_sparkles(self, draw: ImageDraw.Draw, W: int, H: int) -> None:
        """Draw random sparkle particles."""
        import random
        random.seed(42)

        sparkle_positions = [
            (int(W * 0.15), int(H * 0.30)),
            (int(W * 0.85), int(H * 0.25)),
            (int(W * 0.50), int(H * 0.18)),
            (int(W * 0.35), int(H * 0.48)),
            (int(W * 0.65), int(H * 0.50)),
        ]

        for sx, sy in sparkle_positions:
            size = random.randint(4, 10)
            # Cross sparkle
            draw.line([(sx - size, sy), (sx + size, sy)], fill=(255, 255, 255, 200), width=2)
            draw.line([(sx, sy - size), (sx, sy + size)], fill=(255, 255, 255, 200), width=2)
            # Center dot
            draw.ellipse([sx - 2, sy - 2, sx + 2, sy + 2], fill=(255, 215, 0, 255))

    def _load_font(self, size: int):
        from PIL import ImageFont
        import os

        font_paths = [
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/segoeuib.ttf",
        ]

        for fp in font_paths:
            if os.path.exists(fp):
                try:
                    return ImageFont.truetype(fp, size)
                except Exception:
                    continue

        return ImageFont.load_default()
