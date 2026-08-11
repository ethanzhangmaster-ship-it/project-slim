"""CTA Renderer V1

生成点击诱因层（Call-To-Action overlay）。

支持模板：
  - MERGE NOW     (merge action)
  - UNLOCK DRAGON (reward motivation)
  - COMPLETE COLLECTION (collection urgency)
  - PLAY NOW      (generic)

输出：透明 PNG CTA layer
"""
from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont, ImageFilter


CTA_TEMPLATES = {
    "merge": {
        "text": "MERGE NOW",
        "subtext": "Tap to Combine",
        "color": (80, 220, 120),
        "glow_color": (60, 200, 100),
    },
    "reward": {
        "text": "UNLOCK DRAGON",
        "subtext": "Collect Your Reward",
        "color": (255, 215, 0),
        "glow_color": (255, 180, 0),
    },
    "collection": {
        "text": "COMPLETE COLLECTION",
        "subtext": "3/5 Dragons Found",
        "color": (255, 160, 60),
        "glow_color": (255, 120, 30),
    },
    "play": {
        "text": "PLAY NOW",
        "subtext": "Free to Play",
        "color": (100, 180, 255),
        "glow_color": (60, 150, 240),
    },
}


class CTARenderer:
    """Render click-to-action button layer."""

    def __init__(self) -> None:
        pass

    def render(
        self,
        width: int = 1080,
        height: int = 1080,
        output_path: str = "cta.png",
        cta_type: str = "merge",
        custom_text: str = "",
        custom_subtext: str = "",
        position: str = "bottom",
        y_offset: int = 0,
    ) -> str:
        """Render CTA button layer.

        Args:
            width, height: Canvas size
            output_path: Output path
            cta_type: "merge" | "reward" | "collection" | "play"
            custom_text: Override default text
            custom_subtext: Override default subtext
            position: "bottom" | "center"
            y_offset: Vertical offset from position
        """
        template = CTA_TEMPLATES.get(cta_type, CTA_TEMPLATES["merge"])
        text = custom_text or template["text"]
        subtext = custom_subtext or template["subtext"]
        color = template["color"]
        glow_color = template["glow_color"]

        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        font_main = self._load_font(36)
        font_sub = self._load_font(18)

        if position == "bottom":
            cy = height - 80 + y_offset
        else:
            cy = height // 2 + y_offset

        # Subtext
        if font_sub and subtext:
            bbox = draw.textbbox((0, 0), subtext, font=font_sub)
            sw = bbox[2] - bbox[0]
            sx = (width - sw) // 2
            sy = cy - 55
            draw.text((sx + 1, sy + 1), subtext, font=font_sub, fill=(0, 0, 0, 150))
            draw.text((sx, sy), subtext, font=font_sub, fill=color + (255,))

        # Main CTA text
        if font_main:
            bbox = draw.textbbox((0, 0), text, font=font_main)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            tx = (width - tw) // 2
            ty = cy - 30

            # Glow shadow
            for o in range(5, 0, -1):
                alpha = int(40 - o * 6)
                draw.text((tx - o, ty), text, font=font_main, fill=glow_color + (alpha,))
                draw.text((tx + o, ty), text, font=font_main, fill=glow_color + (alpha,))
                draw.text((tx, ty - o), text, font=font_main, fill=glow_color + (alpha,))
                draw.text((tx, ty + o), text, font=font_main, fill=glow_color + (alpha,))

            # Dark shadow
            draw.text((tx + 2, ty + 2), text, font=font_main, fill=(0, 0, 0, 200))
            # Main text
            draw.text((tx, ty), text, font=font_main, fill=color + (255,))

            # Underline button effect
            ul_y = ty + th + 8
            ul_w = tw + 40
            ul_x = (width - ul_w) // 2

            # Glow bar
            for o in range(4, 0, -1):
                alpha = int(60 - o * 12)
                draw.rounded_rectangle(
                    [ul_x - o, ul_y - o, ul_x + ul_w + o, ul_y + 6 + o],
                    radius=6, fill=glow_color + (alpha,),
                )

            # Main bar
            draw.rounded_rectangle(
                [ul_x, ul_y, ul_x + ul_w, ul_y + 6],
                radius=4, fill=color + (255,),
            )

        # Bottom gradient overlay (dark fade for legibility)
        self._draw_bottom_gradient(draw, width, height, cy - 40)

        img.save(output_path)
        return output_path

    def _draw_bottom_gradient(
        self, draw: ImageDraw.Draw, W: int, H: int, start_y: int,
    ) -> None:
        """Draw a subtle dark gradient at bottom for text legibility."""
        for row in range(start_y, H):
            alpha = int(60 * (row - start_y) / (H - start_y))
            draw.line([(0, row), (W, row)], fill=(0, 0, 0, alpha), width=1)

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