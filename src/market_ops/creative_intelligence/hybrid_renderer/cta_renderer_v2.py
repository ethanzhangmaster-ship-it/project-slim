"""CTA Renderer V2.1

生成 CTA Button 层。

升级：
  - 自动选择 CTA 类型（基于 winner_dna 的 reward_score / hook_type / emotion）
  - Emoji 支持（✨ ▶ 🐉）
  - 更丰富的视觉层次
"""
from __future__ import annotations

from typing import Any
from PIL import Image, ImageDraw, ImageFont


CTA_TEMPLATES_V2 = {
    "merge": {
        "text": "MERGE NOW",
        "icon": "✨",
        "color": (80, 220, 120),
        "glow_color": (60, 200, 100),
        "bg_color": (20, 60, 30),
    },
    "reward": {
        "text": "UNLOCK DRAGON",
        "icon": "🐉",
        "color": (255, 215, 0),
        "glow_color": (255, 180, 0),
        "bg_color": (60, 40, 10),
    },
    "collection": {
        "text": "COLLECT ALL",
        "icon": "🎁",
        "color": (255, 160, 60),
        "glow_color": (255, 120, 30),
        "bg_color": (50, 25, 10),
    },
    "play": {
        "text": "PLAY NOW",
        "icon": "▶",
        "color": (100, 180, 255),
        "glow_color": (60, 150, 240),
        "bg_color": (15, 30, 60),
    },
    "evolution": {
        "text": "EVOLVE NOW",
        "icon": "⚡",
        "color": (200, 150, 255),
        "glow_color": (160, 100, 255),
        "bg_color": (30, 15, 50),
    },
}


def auto_select_cta_type(winner_dna: dict[str, Any] | None = None,
                         hook_type: str = "merge") -> str:
    """Auto-select CTA type based on winner DNA context.

    Heuristic:
      - reward_score > 0.8 → "reward"
      - hook_type == "collection" → "collection"
      - hook_type == "evolution" → "evolution"
      - hook_type == "crisis" → "play"
      - default → "merge"
    """
    if winner_dna:
        reward_score = winner_dna.get("reward_score", 0)
        if isinstance(reward_score, (int, float)) and reward_score > 0.8:
            return "reward"

    type_map = {
        "merge": "merge",
        "evolution": "evolution",
        "reward": "reward",
        "collection": "collection",
        "crisis": "play",
    }
    return type_map.get(hook_type, "merge")


class CTARendererV2:
    """V2.1: Enhanced CTA button with auto-selection and emoji support."""

    def __init__(self) -> None:
        pass

    def render(
        self,
        width: int = 1080,
        height: int = 1080,
        output_path: str = "cta.png",
        cta_type: str = "auto",
        custom_text: str = "",
        position: str = "bottom",
        winner_dna: dict[str, Any] | None = None,
        hook_type: str = "merge",
    ) -> str:
        """Render CTA button.

        Args:
            width, height: Canvas size
            output_path: Output path
            cta_type: "auto" | "merge" | "reward" | "collection" | "play" | "evolution"
            custom_text: Override text
            position: "bottom" | "center"
            winner_dna: Winner DNA for auto-selection
            hook_type: Hook type for auto-selection
        """
        if cta_type == "auto":
            cta_type = auto_select_cta_type(winner_dna, hook_type)

        template = CTA_TEMPLATES_V2.get(cta_type, CTA_TEMPLATES_V2["merge"])
        text = custom_text or template["text"]
        icon = template.get("icon", "")
        color = template["color"]
        glow_color = template["glow_color"]
        bg_color = template["bg_color"]

        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        font_main = self._load_font(38)
        if not font_main:
            return output_path

        display_text = f"{icon} {text} {icon}" if icon else text

        bbox = draw.textbbox((0, 0), display_text, font=font_main)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]

        # Button dimensions
        pad_x, pad_y = 36, 14
        btn_w = tw + pad_x * 2
        btn_h = th + pad_y * 2

        if position == "bottom":
            btn_y = height - 90 - btn_h // 2
        else:
            btn_y = height // 2 - btn_h // 2
        btn_x = (width - btn_w) // 2

        # Outer glow layers
        for o in range(10, 0, -2):
            alpha = int(25 - o * 2)
            draw.rounded_rectangle(
                [btn_x - o, btn_y - o, btn_x + btn_w + o, btn_y + btn_h + o],
                radius=22, fill=glow_color + (alpha,),
            )

        # Button BG
        draw.rounded_rectangle(
            [btn_x, btn_y, btn_x + btn_w, btn_y + btn_h],
            radius=18, fill=bg_color + (240,),
        )

        # Button border
        draw.rounded_rectangle(
            [btn_x, btn_y, btn_x + btn_w, btn_y + btn_h],
            radius=18, outline=color + (255,), width=2,
        )

        # Inner glow
        draw.rounded_rectangle(
            [btn_x + 4, btn_y + 4, btn_x + btn_w - 4, btn_y + btn_h - 4],
            radius=14, outline=color + (50,), width=1,
        )

        # Text shadow
        draw.text((btn_x + pad_x + 2, btn_y + pad_y + 2), display_text, font=font_main, fill=(0, 0, 0, 200))
        # Main text
        draw.text((btn_x + pad_x, btn_y + pad_y), display_text, font=font_main, fill=color + (255,))
        # Highlight
        draw.text((btn_x + pad_x + 1, btn_y + pad_y - 1), display_text, font=font_main, fill=(255, 255, 255, 60))

        # Bottom dark gradient for legibility
        fade_start = btn_y - 30
        for row in range(max(0, fade_start), height):
            alpha = int(90 * (row - fade_start) / (height - fade_start))
            draw.line([(0, row), (width, row)], fill=(0, 0, 0, min(alpha, 120)), width=1)

        img.save(output_path)
        return output_path

    def _load_font(self, size: int) -> ImageFont.FreeTypeFont | None:
        import os
        paths = [
            "C:/Windows/Fonts/segoeuisymbol.ttf",
            "C:/Windows/Fonts/seguisym.ttf",
            "C:/Windows/Fonts/seguiemj.ttf",
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