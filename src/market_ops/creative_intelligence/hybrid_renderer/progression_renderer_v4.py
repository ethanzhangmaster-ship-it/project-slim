"""Progression Renderer V4

V4 升级：
  - 视觉化进化箭头: 🥚 + 🥚 → 💥 → 🐉 → 🔥 Legendary
  - 大箭头 + Glow + Explosion + Level badge
  - 水平排列，从左到右
"""
from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont


class ProgressionRendererV4:
    """V4: Visual evolution timeline with arrows, glow, and level badges."""

    def __init__(self) -> None:
        pass

    def render(
        self,
        width: int = 1080,
        height: int = 1080,
        output_path: str = "progression.png",
        mode: str = "egg_to_dragon",
    ) -> str:
        """Render progression timeline with visual arrows.

        Layout (horizontal):
          [EGG Lv.1] → [MERGE] → [DRAGON Lv.2] → [LEGENDARY Lv.3]
        """
        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Load font
        font = self._load_font(36)
        font_small = self._load_font(24)
        if not font:
            font = ImageFont.load_default()
            font_small = font

        # Define stages
        stages = [
            {"label": "EGG", "level": "Lv.1", "icon": "🥚", "color": (180, 180, 200)},
            {"label": "MERGE", "level": "", "icon": "💥", "color": (255, 215, 0)},
            {"label": "DRAGON", "level": "Lv.2", "icon": "🐉", "color": (255, 180, 50)},
            {"label": "LEGENDARY", "level": "Lv.3", "icon": "🔥", "color": (255, 100, 50)},
        ]

        num_stages = len(stages)
        stage_w = width // num_stages
        center_y = height // 2

        # Draw gradient background bar
        bar_y = center_y - 40
        bar_h = 80
        for i in range(bar_h):
            t = i / bar_h
            alpha = int(40 * (1 - abs(t - 0.5) * 2))
            r = int(80 + 40 * t)
            g = int(30 + 20 * t)
            b = int(120 + 40 * t)
            draw.line([(0, bar_y + i), (width, bar_y + i)], fill=(r, g, b, alpha), width=1)

        # Draw each stage
        for i, stage in enumerate(stages):
            cx = i * stage_w + stage_w // 2

            # Stage circle
            circle_r = 30
            draw.ellipse(
                [cx - circle_r, center_y - circle_r, cx + circle_r, center_y + circle_r],
                outline=stage["color"], width=3,
            )

            # Stage glow
            glow_r = circle_r + 8
            for g in range(8, 0, -2):
                alpha = int(15 - g)
                draw.ellipse(
                    [cx - glow_r + g, center_y - glow_r + g,
                     cx + glow_r - g, center_y + glow_r - g],
                    outline=stage["color"] + (alpha,), width=2,
                )

            # Stage label
            label_bbox = draw.textbbox((0, 0), stage["label"], font=font)
            lw = label_bbox[2] - label_bbox[0]
            draw.text((cx - lw // 2, center_y - circle_r - 50), stage["label"],
                      fill=stage["color"] + (255,), font=font)

            # Level badge
            if stage["level"]:
                lvl_bbox = draw.textbbox((0, 0), stage["level"], font=font_small)
                llw = lvl_bbox[2] - lvl_bbox[0]
                draw.text((cx - llw // 2, center_y + circle_r + 10), stage["level"],
                          fill=stage["color"] + (200,), font=font_small)

            # Draw arrow between stages
            if i < num_stages - 1:
                arrow_start_x = cx + circle_r + 5
                arrow_end_x = (i + 1) * stage_w + stage_w // 2 - circle_r - 5
                arrow_y = center_y

                # Arrow line
                draw.line(
                    [(arrow_start_x, arrow_y), (arrow_end_x, arrow_y)],
                    fill=(255, 215, 0, 200), width=4,
                )

                # Arrow glow
                draw.line(
                    [(arrow_start_x, arrow_y), (arrow_end_x, arrow_y)],
                    fill=(255, 215, 0, 80), width=12,
                )

                # Arrow head
                head_size = 10
                draw.polygon([
                    (arrow_end_x, arrow_y),
                    (arrow_end_x - head_size, arrow_y - head_size),
                    (arrow_end_x - head_size, arrow_y + head_size),
                ], fill=(255, 215, 0, 220))

                # Explosion particles at arrow
                for px in range(arrow_start_x + 10, arrow_end_x, 30):
                    particle_alpha = 80
                    draw.ellipse(
                        [px - 3, arrow_y - 3, px + 3, arrow_y + 3],
                        fill=(255, 255, 200, particle_alpha),
                    )

        img.save(output_path)
        return output_path

    def _load_font(self, size: int) -> ImageFont.FreeTypeFont | None:
        import os
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