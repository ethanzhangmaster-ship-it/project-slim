"""Progression Renderer V2

升级 V1 版本，新增：
  - Evolution Timeline（进化时间线）
  - Before → After 视觉箭头
  - Evolution burst（升级爆发光效）
  - Level badge chain（等级链）
  - Sparkle particle system（粒子系统）

作为透明 PNG overlay 叠加到最终 creative 上。
"""
from __future__ import annotations

import math
import random
from PIL import Image, ImageDraw, ImageFont, ImageFilter


class ProgressionRendererV2:
    """V2: Evolution timeline + before/after progression indicators."""

    def __init__(self) -> None:
        random.seed(42)

    def render(
        self,
        width: int = 1080,
        height: int = 1080,
        output_path: str = "progression.png",
        mode: str = "merge_evolution",
    ) -> str:
        """Render progression overlay.

        Args:
            width, height: Canvas size
            output_path: Output path
            mode: "merge_evolution" | "before_after" | "reward_unlock"
        """
        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        if mode == "merge_evolution":
            self._render_merge_evolution(draw, img, width, height)
        elif mode == "before_after":
            self._render_before_after(draw, img, width, height)
        elif mode == "reward_unlock":
            self._render_reward_unlock(draw, img, width, height)
        else:
            self._render_merge_evolution(draw, img, width, height)

        img.save(output_path)
        return output_path

    # ── Merge Evolution ─────────────────────────────────────────────────

    def _render_merge_evolution(
        self, draw: ImageDraw.Draw, img: Image.Image, W: int, H: int
    ) -> None:
        """Standard merge evolution: Lv.1 → Lv.2 with arrow and glow."""
        cx = W // 2
        cy = int(H * 0.42)

        # Evolution timeline arrow
        self._draw_evolution_arrow(draw, int(W * 0.22), cy, int(W * 0.78), cy)

        # Level badges
        self._draw_level_badge(draw, int(W * 0.22), cy - 10, "Lv.1", (200, 180, 255))
        self._draw_level_badge_v2(draw, int(W * 0.78), cy - 10, "Lv.2", (255, 215, 0))

        # Evolution burst at center
        self._draw_evolution_burst(img, cx, cy, radius=100)

        # Sparkle particles
        self._draw_sparkles(draw, W, H)

    # ── Before After ────────────────────────────────────────────────────

    def _render_before_after(
        self, draw: ImageDraw.Draw, img: Image.Image, W: int, H: int
    ) -> None:
        """Split screen: BEFORE → AFTER with large arrow."""
        cy = int(H * 0.45)

        # Large golden arrow
        self._draw_large_arrow(draw, int(W * 0.45), cy, int(W * 0.55), cy, W)

        # Before label
        self._draw_section_label(draw, int(W * 0.24), int(H * 0.16), "BEFORE",
                                 (180, 180, 220), dim=True)
        # After label
        self._draw_section_label(draw, int(W * 0.76), int(H * 0.16), "AFTER",
                                 (255, 215, 0), dim=False)

        # Sparkles near arrow
        self._draw_sparkles_region(draw, int(W * 0.42), int(H * 0.30), int(W * 0.16), int(H * 0.30))

    # ── Reward Unlock ───────────────────────────────────────────────────

    def _render_reward_unlock(
        self, draw: ImageDraw.Draw, img: Image.Image, W: int, H: int
    ) -> None:
        """Reward unlock: radial burst + sparkles + rarity badge."""
        cx, cy = W // 2, int(H * 0.45)

        # Radial burst
        self._draw_radial_burst(img, cx, cy, radius=200)

        # Sparkle particles everywhere
        self._draw_sparkles(draw, W, H, count=30)

        # Rarity badge
        self._draw_rarity_badge(draw, cx, int(H * 0.76), "LEGENDARY", (255, 215, 0))

    # ── Drawing primitives ──────────────────────────────────────────────

    def _draw_evolution_arrow(
        self, draw: ImageDraw.Draw, x1: int, y: int, x2: int, y2: int,
        color: tuple[int, int, int] = (255, 215, 0),
    ) -> None:
        """Draw a horizontal evolution arrow with gradient glow."""
        length = x2 - x1
        head_size = 24

        # Glow
        for o in range(6, 0, -1):
            alpha = int(60 - o * 8)
            draw.line([(x1, y - o), (x2, y2 - o)], fill=color + (alpha,), width=4 + o)
            draw.line([(x1, y + o), (x2, y2 + o)], fill=color + (alpha,), width=4 + o)

        # Main line
        draw.line([(x1, y), (x2, y2)], fill=color + (255,), width=4)

        # Arrowhead
        draw.polygon([
            (x2, y2),
            (x2 - head_size, y2 - head_size // 2),
            (x2 - head_size, y2 + head_size // 2),
        ], fill=color + (255,))

        # Arrowhead glow
        for o in range(4, 0, -1):
            alpha = int(50 - o * 10)
            draw.polygon([
                (x2, y2),
                (x2 - head_size - o * 2, y2 - head_size // 2 - o),
                (x2 - head_size - o * 2, y2 + head_size // 2 + o),
            ], fill=color + (alpha,))

    def _draw_large_arrow(
        self, draw: ImageDraw.Draw, x1: int, y1: int, x2: int, y2: int, W: int,
    ) -> None:
        """Large before→after arrow."""
        mid_x = (x1 + x2) // 2
        head_size = 30

        # Thick arrow with glow
        for o in range(8, 0, -2):
            alpha = int(50 - o * 5)
            draw.line([(x1, y1 - o), (x2, y2 - o)], fill=(255, 215, 0, alpha), width=6 + o)
            draw.line([(x1, y1 + o), (x2, y2 + o)], fill=(255, 215, 0, alpha), width=6 + o)

        draw.line([(x1, y1), (x2, y2)], fill=(255, 215, 0, 255), width=5)

        # Arrowhead
        draw.polygon([
            (x2, y2),
            (x2 - head_size, y2 - head_size // 2),
            (x2 - head_size, y2 + head_size // 2),
        ], fill=(255, 215, 0, 255))

    def _draw_level_badge(
        self, draw: ImageDraw.Draw, x: int, y: int, text: str,
        color: tuple[int, int, int],
    ) -> None:
        """Draw a circular level badge."""
        radius = 32

        # Glow rings
        for r in range(radius + 14, radius, -2):
            alpha = int(40 - (r - radius) * 3)
            draw.ellipse(
                [x - r, y - r, x + r, y + r],
                outline=color + (alpha,), width=2,
            )

        # Main circle
        draw.ellipse(
            [x - radius, y - radius, x + radius, y + radius],
            fill=(30, 15, 50, 230),
            outline=color + (255,),
            width=3,
        )

        # Text
        font = self._load_font(24)
        if font:
            bbox = draw.textbbox((0, 0), text, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            tx = x - tw // 2
            ty = y - th // 2
            draw.text((tx + 1, ty + 1), text, font=font, fill=(0, 0, 0, 180))
            draw.text((tx, ty), text, font=font, fill=color + (255,))

    def _draw_level_badge_v2(
        self, draw: ImageDraw.Draw, x: int, y: int, text: str,
        color: tuple[int, int, int],
    ) -> None:
        """V2 badge with evolution burst effect."""
        self._draw_level_badge(draw, x, y, text, color)
        # Extra sparkle ring
        radius = 38
        for angle in range(0, 360, 45):
            rad = math.radians(angle)
            sx = x + int(radius * math.cos(rad))
            sy = y + int(radius * math.sin(rad))
            draw.ellipse([sx - 3, sy - 3, sx + 3, sy + 3], fill=color + (200,))

    def _draw_section_label(
        self, draw: ImageDraw.Draw, cx: int, y: int, text: str,
        color: tuple[int, int, int], dim: bool = False,
    ) -> None:
        """Draw BEFORE/AFTER section label."""
        font = self._load_font(28)
        if not font:
            return
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]

        alpha = 120 if dim else 255
        # Glow
        draw.text((cx - tw // 2 - 1, y - 1), text, font=font, fill=(0, 0, 0, 200))
        draw.text((cx - tw // 2 + 1, y + 1), text, font=font, fill=(0, 0, 0, 200))
        draw.text((cx - tw // 2, y), text, font=font, fill=color + (alpha,))

        if not dim:
            # Underline glow
            draw.line(
                [(cx - tw // 2 - 10, y + 34), (cx + tw // 2 + 10, y + 34)],
                fill=color + (100,), width=2,
            )

    def _draw_evolution_burst(
        self, img: Image.Image, cx: int, cy: int, radius: int = 80,
    ) -> None:
        """Draw a radial glow burst at center."""
        burst = Image.new("RGBA", img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(burst)

        for r in range(radius, 0, -4):
            alpha = int(25 * (r / radius))
            draw.ellipse(
                [cx - r, cy - r, cx + r, cy + r],
                fill=(255, 215, 0, alpha),
            )

        burst = burst.filter(ImageFilter.GaussianBlur(radius=20))
        img.paste(burst, (0, 0), burst)

    def _draw_radial_burst(
        self, img: Image.Image, cx: int, cy: int, radius: int = 200,
    ) -> None:
        """Large radial burst for reward unlock."""
        burst = Image.new("RGBA", img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(burst)

        for r in range(radius, 0, -8):
            alpha = int(20 * (r / radius))
            draw.ellipse(
                [cx - r, cy - r, cx + r, cy + r],
                fill=(255, 215, 0, alpha),
            )

        burst = burst.filter(ImageFilter.GaussianBlur(radius=30))
        img.paste(burst, (0, 0), burst)

    def _draw_rarity_badge(
        self, draw: ImageDraw.Draw, cx: int, y: int, text: str,
        color: tuple[int, int, int],
    ) -> None:
        """Draw rarity badge (e.g. LEGENDARY)."""
        font = self._load_font(22)
        if not font:
            return
        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        pad_x, pad_y = 24, 12

        # Badge background
        draw.rounded_rectangle(
            [cx - tw // 2 - pad_x, y - th // 2 - pad_y,
             cx + tw // 2 + pad_x, y + th // 2 + pad_y],
            radius=14,
            fill=(30, 15, 50, 230),
            outline=color + (255,),
            width=2,
        )
        # Glow border
        draw.rounded_rectangle(
            [cx - tw // 2 - pad_x - 4, y - th // 2 - pad_y - 4,
             cx + tw // 2 + pad_x + 4, y + th // 2 + pad_y + 4],
            radius=16,
            outline=color + (60,),
            width=2,
        )

        draw.text((cx - tw // 2, y - th // 2), text, font=font, fill=color + (255,))

    def _draw_sparkles(
        self, draw: ImageDraw.Draw, W: int, H: int, count: int = 20,
    ) -> None:
        """Draw random sparkle particles."""
        positions = [
            (int(W * random.uniform(0.05, 0.95)), int(H * random.uniform(0.10, 0.80)))
            for _ in range(count)
        ]

        for sx, sy in positions:
            size = random.randint(3, 10)
            draw.line([(sx - size, sy), (sx + size, sy)], fill=(255, 255, 255, 180), width=2)
            draw.line([(sx, sy - size), (sx, sy + size)], fill=(255, 255, 255, 180), width=2)
            draw.ellipse([sx - 2, sy - 2, sx + 2, sy + 2], fill=(255, 215, 0, 220))

    def _draw_sparkles_region(
        self, draw: ImageDraw.Draw, x: int, y: int, w: int, h: int,
    ) -> None:
        """Draw sparkles in a specific region."""
        for _ in range(15):
            sx = x + random.randint(0, w)
            sy = y + random.randint(0, h)
            size = random.randint(3, 8)
            draw.line([(sx - size, sy), (sx + size, sy)], fill=(255, 255, 255, 160), width=1)
            draw.line([(sx, sy - size), (sx, sy + size)], fill=(255, 255, 255, 160), width=1)
            draw.ellipse([sx - 1, sy - 1, sx + 1, sy + 1], fill=(255, 215, 0, 200))

    # ── Helpers ─────────────────────────────────────────────────────────

    def _load_font(self, size: int) -> ImageFont.FreeTypeFont | None:
        import os
        paths = [
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