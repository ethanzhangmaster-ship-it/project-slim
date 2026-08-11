"""Text Overlay V3.2

V3.2 升级：
  - 简化 Hook: "Merge & Watch the Magic" → "MERGE" + "WATCH MAGIC"
  - 字体: Impact / Luckiest Guy / Burbank
  - 效果: white fill + black outline + gold shadow
  - 固定位置: Top 15%
  - 禁止: middle overlay
"""
from __future__ import annotations

import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter


def simplify_hook_text(raw_text: str) -> list[str]:
    """Simplify hook text to 2-3 word lines for maximum impact.

    "Merge & Watch the Magic" → ["MERGE", "WATCH MAGIC"]
    """
    text = raw_text.strip().upper()
    # Remove common filler words
    for word in ["THE", "AND", "&", "TO", "A", "AN"]:
        text = text.replace(f" {word} ", " ")
        if text.startswith(f"{word} "):
            text = text[len(word) + 1:]
        if text.endswith(f" {word}"):
            text = text[:-len(word) - 1]

    words = text.split()
    if len(words) <= 2:
        return [text]
    elif len(words) <= 4:
        mid = len(words) // 2
        return [" ".join(words[:mid]), " ".join(words[mid:])]
    else:
        return [" ".join(words[:3]), " ".join(words[3:])]


class TextOverlayV32:
    """V3.2: Simplified hook text overlay with Impact font and gold effects."""

    def render(
        self,
        width: int = 1080,
        height: int = 1080,
        output_path: str = "text.png",
        hook_text: str = "MERGE & WATCH THE MAGIC",
        position: str = "top",
    ) -> str:
        """Render simplified hook text overlay.

        Args:
            width, height: Canvas size
            output_path: Output path
            hook_text: Raw hook text from winner DNA
            position: "top" (fixed)
        """
        lines = simplify_hook_text(hook_text)

        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Font: Impact
        font_size = 72 if len(lines) <= 2 else 56
        font = self._load_font(font_size)
        if not font:
            font = ImageFont.load_default()

        # Calculate layout
        total_h = 0
        line_heights = []
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            h = bbox[3] - bbox[1]
            line_heights.append(h + 16)
            total_h += h + 16

        # Fixed top 15% region
        top_region_h = int(height * 0.15)
        start_y = (top_region_h - total_h) // 2
        if start_y < 10:
            start_y = 10

        # Calculate where text lines will end
        current_y = start_y
        for i in range(len(lines)):
            current_y += line_heights[i]

        # Dark gradient banner behind text for legibility (drawn FIRST)
        fade_start = max(0, start_y - 10)
        fade_end = min(height, current_y + 10)
        for row in range(fade_start, fade_end):
            dist = abs(row - ((fade_start + fade_end) // 2))
            half = (fade_end - fade_start) // 2
            t = dist / half if half > 0 else 1.0
            alpha = int(120 * (1 - t))
            alpha = max(0, min(140, alpha))
            draw.line([(0, row), (width, row)], fill=(10, 5, 25, alpha), width=1)

        current_y = start_y

        for i, line in enumerate(lines):
            bbox = draw.textbbox((0, 0), line, font=font)
            tw = bbox[2] - bbox[0]
            tx = (width - tw) // 2

            # Gold shadow (offset)
            for dx, dy in [(-3, 3), (3, 3), (-2, 2), (2, 2)]:
                draw.text((tx + dx, current_y + dy), line, font=font,
                          fill=(180, 140, 20, 160))

            # Black outline (thick stroke)
            for dx, dy in [(-3, 0), (3, 0), (0, -3), (0, 3),
                          (-2, -2), (2, -2), (-2, 2), (2, 2)]:
                draw.text((tx + dx, current_y + dy), line, font=font,
                          fill=(0, 0, 0, 220))

            # White fill
            draw.text((tx, current_y), line, font=font,
                      fill=(255, 255, 255, 255))

            # Top highlight (subtle)
            draw.text((tx, current_y - 1), line, font=font,
                      fill=(255, 255, 255, 80))

            current_y += line_heights[i]

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