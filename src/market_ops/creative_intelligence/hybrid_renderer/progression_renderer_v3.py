"""Progression Renderer V3

Evolution Timeline 渲染器。

从「简单箭头」升级为「Evolution Timeline」：

          MERGE
    Egg Lv1 → Egg Lv2 → Baby Dragon → Legendary Dragon

组件：
  - 垂直/水平进化箭头链
  - 等级徽章链
  - 粒子爆发
  - 光晕效果
"""
from __future__ import annotations

import math
import random
from PIL import Image, ImageDraw, ImageFont, ImageFilter


class ProgressionRendererV3:
    """V3: Evolution Timeline renderer."""

    def __init__(self) -> None:
        random.seed(42)

    def render(
        self,
        width: int = 1080,
        height: int = 1080,
        output_path: str = "progression.png",
        mode: str = "merge_evolution",
        stages: list[str] | None = None,
    ) -> str:
        """Render evolution timeline overlay.

        Args:
            width, height: Canvas size
            output_path: Output path
            mode: "merge_evolution" | "before_after" | "reward_unlock"
            stages: Custom stage labels, e.g. ["Egg Lv1", "Egg Lv2", "Baby Dragon", "Legendary"]
        """
        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        if stages is None:
            stages = ["Egg Lv1", "Merge", "Baby Dragon", "Legendary"]

        if mode == "merge_evolution":
            self._render_evolution_timeline(draw, img, width, height, stages)
        elif mode == "before_after":
            self._render_before_after(draw, img, width, height)
        elif mode == "reward_unlock":
            self._render_reward_unlock(draw, img, width, height)
        else:
            self._render_evolution_timeline(draw, img, width, height, stages)

        img.save(output_path)
        return output_path

    # ── Evolution Timeline ──────────────────────────────────────────────

    def _render_evolution_timeline(
        self, draw: ImageDraw.Draw, img: Image.Image,
        W: int, H: int, stages: list[str],
    ) -> None:
        """Draw vertical evolution timeline: stage1 → stage2 → stage3 → stage4."""
        start_y = int(H * 0.28)
        end_y = int(H * 0.72)
        cx = W // 2
        total_h = end_y - start_y
        gap = total_h // (len(stages) - 1) if len(stages) > 1 else total_h

        # Draw vertical glow line connecting all stages
        self._draw_glow_line(draw, cx, start_y, cx, end_y, color=(255, 215, 0))

        # Draw each stage
        for i, stage in enumerate(stages):
            cy = start_y + i * gap
            if i < len(stages) - 1:
                # Arrow between stages
                self._draw_vertical_arrow(draw, cx, cy + 20, cx, cy + gap - 20, (255, 215, 0))

            # Stage badge
            self._draw_stage_badge_v3(draw, cx, cy, stage, is_final=(i == len(stages) - 1))

        # Evolution burst at center
        mid_y = start_y + total_h // 2
        self._draw_evolution_burst(img, cx, mid_y, radius=60)

        # Sparkles along the timeline
        self._draw_sparkles(draw, W, H, count=15)

    # ── Before After ────────────────────────────────────────────────────

    def _render_before_after(
        self, draw: ImageDraw.Draw, img: Image.Image, W: int, H: int,
    ) -> None:
        """Split screen: BEFORE → AFTER with large arrow."""
        cy = int(H * 0.42)
        self._draw_large_arrow(draw, int(W * 0.42), cy, int(W * 0.58), cy)
        self._draw_section_label(draw, int(W * 0.22), int(H * 0.16), "BEFORE", (180, 180, 220), dim=True)
        self._draw_section_label(draw, int(W * 0.78), int(H * 0.16), "AFTER", (255, 215, 0), dim=False)
        self._draw_sparkles_region(draw, int(W * 0.40), int(H * 0.28), int(W * 0.20), int(H * 0.30))

    # ── Reward Unlock ───────────────────────────────────────────────────

    def _render_reward_unlock(
        self, draw: ImageDraw.Draw, img: Image.Image, W: int, H: int,
    ) -> None:
        """Reward unlock: radial burst + sparkles + rarity badge."""
        cx, cy = W // 2, int(H * 0.42)
        self._draw_radial_burst(img, cx, cy, radius=220)
        self._draw_sparkles(draw, W, H, count=30)
        self._draw_rarity_badge(draw, cx, int(H * 0.76), "LEGENDARY", (255, 215, 0))

    # ── Drawing primitives ──────────────────────────────────────────────

    def _draw_glow_line(
        self, draw: ImageDraw.Draw, x1: int, y1: int, x2: int, y2: int,
        color: tuple[int, int, int] = (255, 215, 0),
    ) -> None:
        """Draw a vertical glow line."""
        for o in range(6, 0, -1):
            alpha = int(40 - o * 5)
            draw.line([(x1 - o, y1), (x2 - o, y2)], fill=color + (alpha,), width=3)
            draw.line([(x1 + o, y1), (x2 + o, y2)], fill=color + (alpha,), width=3)
        draw.line([(x1, y1), (x2, y2)], fill=color + (200,), width=2)

    def _draw_vertical_arrow(
        self, draw: ImageDraw.Draw, x1: int, y1: int, x2: int, y2: int,
        color: tuple[int, int, int] = (255, 215, 0),
    ) -> None:
        """Draw a small downward arrow."""
        head_size = 12
        draw.line([(x1, y1), (x2, y2 - head_size)], fill=color + (180,), width=2)
        draw.polygon([
            (x2, y2),
            (x2 - head_size // 2, y2 - head_size),
            (x2 + head_size // 2, y2 - head_size),
        ], fill=color + (200,))

    def _draw_stage_badge_v3(
        self, draw: ImageDraw.Draw, x: int, y: int, text: str,
        is_final: bool = False,
    ) -> None:
        """Draw a stage badge with glow."""
        radius = 24
        color = (255, 215, 0) if is_final else (180, 160, 220)

        # Glow ring
        for r in range(radius + 10, radius, -2):
            alpha = int(30 - (r - radius) * 3)
            draw.ellipse([x - r, y - r, x + r, y + r], outline=color + (alpha,), width=2)

        # Main circle
        draw.ellipse(
            [x - radius, y - radius, x + radius, y + radius],
            fill=(30, 15, 50, 230) if not is_final else (40, 25, 20, 230),
            outline=color + (255,),
            width=2,
        )

        # Text
        font = self._load_font(16)
        if font:
            bbox = draw.textbbox((0, 0), text, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            draw.text((x - tw // 2, y - th // 2 - 1), text, font=font, fill=(0, 0, 0, 180))
            draw.text((x - tw // 2 - 1, y - th // 2), text, font=font, fill=color + (255,))

    def _draw_large_arrow(
        self, draw: ImageDraw.Draw, x1: int, y1: int, x2: int, y2: int,
    ) -> None:
        """Large before→after arrow."""
        head_size = 28
        for o in range(8, 0, -2):
            alpha = int(50 - o * 5)
            draw.line([(x1, y1 - o), (x2, y2 - o)], fill=(255, 215, 0, alpha), width=5 + o)
            draw.line([(x1, y1 + o), (x2, y2 + o)], fill=(255, 215, 0, alpha), width=5 + o)
        draw.line([(x1, y1), (x2, y2)], fill=(255, 215, 0, 255), width=4)
        draw.polygon([
            (x2, y2), (x2 - head_size, y2 - head_size // 2), (x2 - head_size, y2 + head_size // 2),
        ], fill=(255, 215, 0, 255))

    def _draw_section_label(
        self, draw: ImageDraw.Draw, cx: int, y: int, text: str,
        color: tuple[int, int, int], dim: bool = False,
    ) -> None:
        font = self._load_font(26)
        if not font:
            return
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        alpha = 120 if dim else 255
        draw.text((cx - tw // 2 - 1, y - 1), text, font=font, fill=(0, 0, 0, 200))
        draw.text((cx - tw // 2 + 1, y + 1), text, font=font, fill=(0, 0, 0, 200))
        draw.text((cx - tw // 2, y), text, font=font, fill=color + (alpha,))
        if not dim:
            draw.line([(cx - tw // 2 - 10, y + 30), (cx + tw // 2 + 10, y + 30)], fill=color + (100,), width=2)

    def _draw_evolution_burst(self, img: Image.Image, cx: int, cy: int, radius: int = 80) -> None:
        burst = Image.new("RGBA", img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(burst)
        for r in range(radius, 0, -4):
            alpha = int(20 * (r / radius))
            draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 215, 0, alpha))
        burst = burst.filter(ImageFilter.GaussianBlur(radius=18))
        img.paste(burst, (0, 0), burst)

    def _draw_radial_burst(self, img: Image.Image, cx: int, cy: int, radius: int = 200) -> None:
        burst = Image.new("RGBA", img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(burst)
        for r in range(radius, 0, -8):
            alpha = int(18 * (r / radius))
            draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 215, 0, alpha))
        burst = burst.filter(ImageFilter.GaussianBlur(radius=30))
        img.paste(burst, (0, 0), burst)

    def _draw_rarity_badge(
        self, draw: ImageDraw.Draw, cx: int, y: int, text: str,
        color: tuple[int, int, int],
    ) -> None:
        font = self._load_font(22)
        if not font:
            return
        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        pad_x, pad_y = 24, 12
        draw.rounded_rectangle(
            [cx - tw // 2 - pad_x, y - th // 2 - pad_y, cx + tw // 2 + pad_x, y + th // 2 + pad_y],
            radius=14, fill=(30, 15, 50, 230), outline=color + (255,), width=2,
        )
        draw.text((cx - tw // 2, y - th // 2), text, font=font, fill=color + (255,))

    def _draw_sparkles(self, draw: ImageDraw.Draw, W: int, H: int, count: int = 20) -> None:
        for _ in range(count):
            sx = int(W * random.uniform(0.05, 0.95))
            sy = int(H * random.uniform(0.10, 0.80))
            size = random.randint(3, 10)
            draw.line([(sx - size, sy), (sx + size, sy)], fill=(255, 255, 255, 160), width=2)
            draw.line([(sx, sy - size), (sx, sy + size)], fill=(255, 255, 255, 160), width=2)
            draw.ellipse([sx - 2, sy - 2, sx + 2, sy + 2], fill=(255, 215, 0, 220))

    def _draw_sparkles_region(self, draw: ImageDraw.Draw, x: int, y: int, w: int, h: int) -> None:
        for _ in range(15):
            sx = x + random.randint(0, w)
            sy = y + random.randint(0, h)
            size = random.randint(3, 8)
            draw.line([(sx - size, sy), (sx + size, sy)], fill=(255, 255, 255, 140), width=1)
            draw.line([(sx, sy - size), (sx, sy + size)], fill=(255, 255, 255, 140), width=1)
            draw.ellipse([sx - 1, sy - 1, sx + 1, sy + 1], fill=(255, 215, 0, 200))

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