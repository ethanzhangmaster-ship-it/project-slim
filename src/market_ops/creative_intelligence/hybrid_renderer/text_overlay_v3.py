"""Text Overlay V3.1

SVG 风格的文字叠加层。

升级：
  - resolve_hook_text 优先级规则:
    1. winner_dna.overlay_text
    2. layout_blueprint.hook_text
    3. prompt_strategy.hook
    4. default template
  - 多行渲染更清晰（line spacing）
  - 加强 stroke/shadow/glow 梯度
  - fantasy gothic 风格支持
"""
from __future__ import annotations

import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter


HOOK_TEMPLATES_V3 = {
    "merge": [
        ["MERGE", "WATCH THE", "MAGIC"],
        ["COMBINE", "AND", "EVOLVE"],
        ["TAP TO", "COMBINE", "ITEMS"],
    ],
    "evolution": [
        ["FROM EGG", "TO", "DRAGON"],
        ["EVOLVE", "YOUR", "POWER"],
        ["WATCH THEM", "TRANS", "FORM"],
    ],
    "reward": [
        ["UNLOCK", "LEGEN", "DARY"],
        ["CLAIM", "YOUR", "REWARD"],
        ["GET THE", "GOLD", "DRAGON"],
    ],
    "collection": [
        ["MERGE AND", "WATCH THE", "MAGIC"],
        ["COLLECT", "ALL THE", "DRAGONS"],
        ["BUILD YOUR", "LEGEN", "DARY", "COLLEC", "TION"],
    ],
    "crisis": [
        ["CAN YOU", "MERGE", "IT?"],
        ["ONLY 1%", "CAN DO", "THIS"],
        ["WRONG MERGE", "TRY AGAIN"],
    ],
}


def resolve_hook_text(
    winner_dna: dict | None = None,
    layout_blueprint: Any | None = None,
    prompt_strategy: Any | None = None,
    hook_type: str = "merge",
    custom_text: str = "",
) -> str:
    """Resolve hook text with priority fallback.

    Priority:
    1. custom_text (directly passed)
    2. winner_dna.overlay_text
    3. layout_blueprint.hook_text
    4. prompt_strategy.hook_text
    5. hook_type template from HOOK_TEMPLATES_V3
    6. default fallback
    """
    # 1. custom_text
    if custom_text and custom_text.strip():
        return custom_text.strip()

    # 2. winner_dna.overlay_text
    if winner_dna:
        ot = winner_dna.get("overlay_text", "")
        if ot and ot.strip():
            return ot.strip()

    # 3. layout_blueprint.hook_text
    if layout_blueprint and hasattr(layout_blueprint, "hook_text"):
        lt = getattr(layout_blueprint, "hook_text", "")
        if lt and lt.strip():
            return lt.strip()

    # 4. prompt_strategy.hook
    if prompt_strategy and hasattr(prompt_strategy, "hook_strategy"):
        hs = getattr(prompt_strategy, "hook_strategy", "")
        if hs and hs.strip():
            return hs.strip()

    # 5. default template based on hook_type
    templates = HOOK_TEMPLATES_V3.get(hook_type, HOOK_TEMPLATES_V3["merge"])
    import random
    random.seed(42)
    selected = random.choice(templates)
    return "\n".join(selected)


class TextOverlayV3:
    """V3.1: SVG-style text overlay with gradient, glow, multi-line support."""

    def __init__(self) -> None:
        pass

    def render(
        self,
        width: int = 1080,
        height: int = 1080,
        output_path: str = "text.png",
        hook_type: str = "merge",
        custom_text: str = "",
        position: str = "top",
        winner_dna: dict | None = None,
        layout_blueprint: Any | None = None,
        prompt_strategy: Any | None = None,
    ) -> str:
        """Render text overlay layer.

        Args:
            width, height: Canvas size
            output_path: Output path
            hook_type: "merge" | "evolution" | "reward" | "collection" | "crisis"
            custom_text: Custom text (newline for multi-line)
            position: "top" | "center"
        """
        # Resolve text with fallback
        text = resolve_hook_text(winner_dna, layout_blueprint, prompt_strategy, hook_type, custom_text)

        # Split into lines for better spacing
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        if not lines:
            lines = ["MERGE", "WATCH THE", "MAGIC"]

        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Adaptive font sizing based on number of lines
        font_size_main = 64 if len(lines) <= 2 else 52
        font_main = self._load_font(font_size_main)
        if not font_main:
            font_main = ImageFont.load_default()

        # Calculate total height
        total_h = 0
        line_heights = []
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font_main)
            h = bbox[3] - bbox[1]
            line_heights.append(h + 12)  # line spacing
            total_h += h + 12

        if position == "top":
            start_y = int(height * 0.06)
        else:
            start_y = (height - total_h) // 2

        current_y = start_y

        # Draw each line with proper spacing
        for i, line in enumerate(lines):
            bbox = draw.textbbox((0, 0), line, font=font_main)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            tx = (width - tw) // 2

            # Outer glow (multiple layers)
            for o in range(8, 0, -2):
                alpha = int(25 - o * 2)
                for dx, dy in [(-o, 0), (o, 0), (0, -o), (0, o), (-o, -o), (o, -o), (-o, o), (o, o)]:
                    draw.text((tx + dx, current_y + dy), line, font=font_main, fill=(255, 215, 0, alpha))

            # Heavy dark shadow
            for dx, dy in [(-3, 0), (3, 0), (0, -3), (0, 3), (-2, -2), (2, -2), (-2, 2), (2, 2)]:
                draw.text((tx + dx, current_y + dy), line, font=font_main, fill=(10, 5, 20, 220))

            # Outer stroke (dark outline)
            draw.text((tx + 2, current_y + 2), line, font=font_main, fill=(0, 0, 0, 180))
            draw.text((tx - 2, current_y + 2), line, font=font_main, fill=(0, 0, 0, 180))
            draw.text((tx + 2, current_y - 2), line, font=font_main, fill=(0, 0, 0, 180))
            draw.text((tx - 2, current_y - 2), line, font=font_main, fill=(0, 0, 0, 180))

            # Main text (golden gradient effect)
            draw.text((tx + 1, current_y + 1), line, font=font_main, fill=(255, 215, 0, 255))
            # Top highlight
            draw.text((tx, current_y - 1), line, font=font_main, fill=(255, 240, 180, 100))

            current_y += line_heights[i]

        # Dark gradient banner fade behind text for legibility
        fade_start = start_y - 20
        fade_end = current_y + 20
        for row in range(int(fade_start), int(fade_end)):
            if row < 0 or row >= height:
                continue
            t = abs(((row - ((fade_start + fade_end) // 2)) / ((fade_end - fade_start) // 2)))
            alpha = int(100 * (1 - t))
            alpha = max(0, min(140, alpha))
            draw.line([(0, row), (width, row)], fill=(10, 5, 25, alpha), width=1)

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