"""Text Overlay Engine V2

自动在广告素材上添加高质量的 Hook 文案。

V2 升级：
  - 更强的描边和阴影
  - 支持 TTF 字体自动发现
  - 更丰富的 Hook 模板
  - 更好的文字间距处理
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------
@dataclass(slots=True)
class TextOverlayConfig:
    text: str
    position: str = "top"
    font_size: int = 72
    font_color: tuple[int, int, int] = (255, 215, 0)
    stroke_color: tuple[int, int, int] = (40, 10, 60)
    stroke_width: int = 5
    shadow_color: tuple[int, int, int] = (20, 10, 40)
    shadow_offset: tuple[int, int] = (4, 4)
    max_width_ratio: float = 0.9


# ---------------------------------------------------------------------------
# Hook Library V2
# ---------------------------------------------------------------------------
HOOK_LIBRARY = {
    "collection": [
        "MERGE & WATCH THE MAGIC",
        "MERGE TO EVOLVE",
        "COMBINE & COLLECT",
        "BUILD YOUR MAGIC WORLD",
    ],
    "crisis": [
        "CAN YOU FIX THIS?",
        "URGENT: MERGE NOW",
        "THEY NEED YOUR HELP",
        "ONLY 1% CAN SOLVE THIS",
    ],
    "reward": [
        "UNLOCK THE LEGENDARY DRAGON",
        "BEST MERGE EVER!",
        "GET YOUR REWARD",
        "CLAIM YOUR LEGENDARY",
    ],
    "twist": [
        "DON'T MAKE THIS MISTAKE!",
        "WRONG MERGE = DISASTER",
        "99% FAIL THIS",
        "AVOID THIS TRAP",
    ],
    "comparison": [
        "LEVEL 1 → LEVEL 10",
        "COMMON → LEGENDARY",
        "BEFORE vs AFTER",
        "WEAK → POWERFUL",
    ],
    "curiosity": [
        "WHAT HAPPENS WHEN YOU MERGE?",
        "SECRET MERGE COMBO",
        "YOU WON'T BELIEVE #7",
        "DISCOVER THE HIDDEN DRAGON",
    ],
    "challenge": [
        "CAN YOU CREATE THE ULTIMATE?",
        "MERGE TO THE MAX",
        "HOW FAR CAN YOU GO?",
        "BEAT MY HIGH SCORE",
    ],
}


# ---------------------------------------------------------------------------
# Text Overlay Engine V2
# ---------------------------------------------------------------------------
class TextOverlayEngine:
    """Renders high-quality advertising text onto creative images."""

    def __init__(self, project: str = "P04 Witch") -> None:
        self._project = project
        self._font_cache: dict[int, Any] = {}

    def overlay_v2(
        self,
        image_path: str,
        hook_type: str = "collection",
        custom_text: str = "",
        output_path: str | None = None,
        config: TextOverlayConfig | None = None,
    ) -> str:
        """V2 overlay with enhanced stroke, shadow, and spacing."""
        from PIL import Image, ImageDraw, ImageFont

        img = Image.open(image_path).convert("RGBA")
        W, H = img.size

        text = custom_text or self._select_hook_text(hook_type)
        if not text:
            text = "MERGE & WATCH THE MAGIC"

        if config is None:
            config = self._auto_config_v2(text, W, H, hook_type)

        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        font = self._load_font_v2(config.font_size)

        # Calculate text size
        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]

        # Scale down if too wide
        max_w = int(W * config.max_width_ratio)
        if tw > max_w:
            scale = max_w / tw
            new_size = int(config.font_size * scale)
            font = self._load_font_v2(new_size)
            bbox = draw.textbbox((0, 0), text, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]

        # Position
        if config.position == "top":
            x = (W - tw) // 2
            y = int(H * 0.04)
        elif config.position == "center":
            x = (W - tw) // 2
            y = (H - th) // 2
        else:
            x = (W - tw) // 2
            y = int(H * 0.88) - th

        # V2: Enhanced shadow (multiple layers for depth)
        sx, sy = config.shadow_offset
        for layer in range(3, 0, -1):
            alpha = int(100 - layer * 25)
            for dx in range(-1, 2):
                for dy in range(-1, 2):
                    draw.text(
                        (x + sx * layer + dx, y + sy * layer + dy),
                        text,
                        font=font,
                        fill=config.shadow_color + (alpha,),
                    )

        # V2: Enhanced stroke (thicker, with inner glow)
        stroke_w = config.stroke_width
        for dx in range(-stroke_w, stroke_w + 1):
            for dy in range(-stroke_w, stroke_w + 1):
                dist = dx * dx + dy * dy
                if dist <= stroke_w * stroke_w:
                    # Outer ring = darker, inner = brighter
                    if dist > (stroke_w - 1) * (stroke_w - 1):
                        color = config.stroke_color + (255,)
                    else:
                        # Slightly lighter inner stroke
                        lighter = tuple(min(255, c + 20) for c in config.stroke_color)
                        color = lighter + (200,)
                    draw.text((x + dx, y + dy), text, font=font, fill=color)

        # Main text with slight gradient effect (draw twice for boldness)
        draw.text((x, y), text, font=font, fill=config.font_color + (255,))
        draw.text((x, y - 1), text, font=font, fill=tuple(min(255, c + 30) for c in config.font_color) + (180,))

        result = Image.alpha_composite(img, overlay)
        result = result.convert("RGB")

        if output_path is None:
            base = Path(image_path)
            output_path = str(base.parent / f"{base.stem}_with_text{base.suffix}")

        result.save(output_path, quality=95)
        return output_path

    def overlay(
        self,
        image_path: str,
        hook_type: str = "collection",
        custom_text: str = "",
        output_path: str | None = None,
        config: TextOverlayConfig | None = None,
    ) -> str:
        """V1 compatibility — delegates to V2."""
        return self.overlay_v2(image_path, hook_type, custom_text, output_path, config)

    def overlay_multiple(
        self,
        image_path: str,
        texts: list[dict[str, Any]],
        output_path: str | None = None,
    ) -> str:
        from PIL import Image, ImageDraw, ImageFont

        img = Image.open(image_path).convert("RGBA")
        W, H = img.size
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        for t in texts:
            text = t.get("text", "")
            if not text:
                continue
            pos = t.get("position", "top")
            size = t.get("font_size", 64)
            color = t.get("font_color", (255, 215, 0))
            stroke = t.get("stroke_color", (40, 10, 60))
            stroke_w = t.get("stroke_width", 4)

            font = self._load_font_v2(size)
            bbox = draw.textbbox((0, 0), text, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]

            max_w = int(W * 0.9)
            if tw > max_w:
                scale = max_w / tw
                new_size = int(size * scale)
                font = self._load_font_v2(new_size)
                bbox = draw.textbbox((0, 0), text, font=font)
                tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]

            if pos == "top":
                x, y = (W - tw) // 2, int(H * 0.04)
            elif pos == "center":
                x, y = (W - tw) // 2, (H - th) // 2
            elif pos == "bottom":
                x, y = (W - tw) // 2, int(H * 0.88) - th
            elif pos == "top_left":
                x, y = int(W * 0.05), int(H * 0.04)
            elif pos == "top_right":
                x, y = int(W * 0.95) - tw, int(H * 0.04)
            else:
                x, y = (W - tw) // 2, int(H * 0.04)

            # Enhanced stroke
            for dx in range(-stroke_w, stroke_w + 1):
                for dy in range(-stroke_w, stroke_w + 1):
                    if dx * dx + dy * dy <= stroke_w * stroke_w:
                        draw.text((x + dx, y + dy), text, font=font, fill=stroke + (255,))
            # Shadow
            draw.text((x + 3, y + 3), text, font=font, fill=(20, 10, 40, 150))
            # Text
            draw.text((x, y), text, font=font, fill=color + (255,))

        result = Image.alpha_composite(img, overlay).convert("RGB")

        if output_path is None:
            base = Path(image_path)
            output_path = str(base.parent / f"{base.stem}_with_texts{base.suffix}")

        result.save(output_path, quality=95)
        return output_path

    def _select_hook_text(self, hook_type: str) -> str:
        import random
        texts = HOOK_LIBRARY.get(hook_type, HOOK_LIBRARY["collection"])
        return random.choice(texts)

    def _auto_config_v2(self, text: str, W: int, H: int, hook_type: str) -> TextOverlayConfig:
        return TextOverlayConfig(
            text=text,
            position="top",
            font_size=min(84, max(52, H // 13)),
            font_color=(255, 220, 80),  # brighter gold
            stroke_color=(30, 5, 50),   # deeper purple
            stroke_width=max(4, H // 220),
            shadow_color=(15, 5, 30),
            shadow_offset=(4, 4),
        )

    def _load_font_v2(self, size: int):
        from PIL import ImageFont

        if size in self._font_cache:
            return self._font_cache[size]

        # Try to find a bold/truetype font
        font_paths = [
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/segoeuib.ttf",
            "C:/Windows/Fonts/tahomabd.ttf",
            "C:/Windows/Fonts/verdanab.ttf",
            "C:/Windows/Fonts/calibrib.ttf",
        ]

        for fp in font_paths:
            if os.path.exists(fp):
                try:
                    font = ImageFont.truetype(fp, size)
                    self._font_cache[size] = font
                    return font
                except Exception:
                    continue

        font = ImageFont.load_default()
        self._font_cache[size] = font
        return font
