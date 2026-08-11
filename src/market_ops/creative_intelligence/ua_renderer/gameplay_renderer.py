"""Gameplay Renderer V1

生成真正的 mobile merge game 截图风格的 UI 层。

包含：
  - Hex merge board (六边形网格)
  - Merge slots with items (物品槽位)
  - UI elements (level badge, energy bar, coins, upgrade button)
  - Merge arrows (合成箭头)
  - Before/after 对比

输出：透明 PNG gameplay layer
"""
from __future__ import annotations

import math
from PIL import Image, ImageDraw, ImageFont, ImageFilter


# ── colour palette ──────────────────────────────────────────────────────
PURPLE_DARK = (18, 12, 40, 255)
PURPLE_MID = (40, 25, 80, 255)
PURPLE_UI = (60, 40, 120, 255)
PURPLE_LIGHT = (100, 70, 180, 255)
GOLD = (255, 215, 0, 255)
GOLD_DIM = (200, 170, 0, 255)
WHITE = (255, 255, 255, 255)
GREEN = (80, 220, 120, 255)
RED = (220, 60, 60, 255)
EGG_COLOR = (200, 180, 255, 255)
DRAGON_COLOR = (255, 140, 60, 255)
SLOT_BG = (25, 18, 50, 220)
SLOT_BORDER = (80, 60, 140, 255)


class GameplayRenderer:
    """Render a merge-game UI layer with board, items, and game elements."""

    def __init__(self, width: int = 1080, height: int = 1080) -> None:
        self.W = width
        self.H = height

    def render(
        self,
        output_path: str,
        board_area: tuple[int, int, int, int] | None = None,
        before_items: list[str] | None = None,
        after_item: str = "dragon",
        show_ui: bool = True,
        ui_config: dict | None = None,
    ) -> str:
        """Render full gameplay layer.

        Args:
            output_path: 输出路径
            board_area: (x, y, w, h) 棋盘区域，None 则居中
            before_items: 合成前的物品列表, e.g. ["egg", "egg"]
            after_item: 合成后的物品名
            show_ui: 是否显示 UI 元素
            ui_config: UI 配置覆盖
        """
        img = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        if before_items is None:
            before_items = ["egg_lv1", "egg_lv1"]

        # Board area
        if board_area is None:
            bx, by = int(self.W * 0.05), int(self.H * 0.22)
            bw, bh = int(self.W * 0.55), int(self.H * 0.52)
        else:
            bx, by, bw, bh = board_area

        # ── 1. Hex grid background ──
        self._draw_hex_grid(draw, bx, by, bw, bh)

        # ── 2. Merge slots ──
        slot_w = bw // 3
        slot_h = bh // 2
        left_slot_center = (bx + slot_w, by + bh // 2)
        right_slot_center = (bx + 2 * slot_w, by + bh // 2)

        # Draw 3 slots: left, middle (arrow), right
        self._draw_slot(draw, left_slot_center[0] - slot_w // 2, left_slot_center[1],
                        slot_w, slot_h, slot_w - 40, slot_h - 40, "Lv.1")
        self._draw_slot(draw, right_slot_center[0] - slot_w // 2, right_slot_center[1],
                        slot_w, slot_h, slot_w - 40, slot_h - 40, "Lv.2")

        # ── 3. Draw items in slots ──
        self._draw_item(draw, left_slot_center[0], left_slot_center[1] - 10, "egg", repeat=2)
        self._draw_item(draw, right_slot_center[0], right_slot_center[1] - 10, after_item)

        # ── 4. Merge arrow between slots ──
        arrow_x = left_slot_center[0] + slot_w // 2 + 20
        self._draw_merge_arrow(draw, arrow_x, by + bh // 2)

        # ── 5. UI elements ──
        if show_ui:
            ui = ui_config or {}
            self._draw_ui_elements(draw, img, bx, by, bw, bh, ui)

        img.save(output_path)
        return output_path

    # ── Hex Grid ────────────────────────────────────────────────────────

    def _draw_hex_grid(self, draw: ImageDraw.Draw, x: int, y: int, w: int, h: int) -> None:
        """Draw a subtle hexagonal grid background."""
        hex_size = 36
        cols = w // (hex_size * 2) + 1
        rows = h // (hex_size * 2) + 1

        for row in range(rows):
            for col in range(cols):
                cx = x + col * hex_size * 2 + (hex_size if row % 2 else 0)
                cy = y + row * hex_size * 2
                if cx > x + w or cy > y + h:
                    continue
                pts = self._hex_points(cx, cy, hex_size - 2)
                draw.polygon(pts, outline=(60, 40, 120, 60), width=1)

    def _hex_points(self, cx: int, cy: int, size: int) -> list[tuple[int, int]]:
        pts = []
        for i in range(6):
            angle = math.pi / 3 * i - math.pi / 6
            pts.append((int(cx + size * math.cos(angle)), int(cy + size * math.sin(angle))))
        return pts

    # ── Slots ───────────────────────────────────────────────────────────

    def _draw_slot(
        self,
        draw: ImageDraw.Draw,
        x: int, y: int, area_w: int, area_h: int,
        slot_w: int, slot_h: int, label: str,
    ) -> None:
        """Draw a single merge slot with rounded rect background."""
        sx = x + (area_w - slot_w) // 2
        sy = y - slot_h // 2

        # Slot background
        draw.rounded_rectangle(
            [sx, sy, sx + slot_w, sy + slot_h],
            radius=16,
            fill=SLOT_BG,
            outline=SLOT_BORDER,
            width=2,
        )

        # Inner glow
        draw.rounded_rectangle(
            [sx + 4, sy + 4, sx + slot_w - 4, sy + slot_h - 4],
            radius=12,
            outline=(100, 80, 160, 40),
            width=1,
        )

        # Level label
        font = self._load_font(16)
        if font:
            bbox = draw.textbbox((0, 0), label, font=font)
            tw = bbox[2] - bbox[0]
            draw.text((sx + (slot_w - tw) // 2, sy + 6), label, font=font, fill=PURPLE_LIGHT)

    # ── Items ───────────────────────────────────────────────────────────

    def _draw_item(
        self, draw: ImageDraw.Draw, cx: int, cy: int, item_type: str, repeat: int = 1
    ) -> None:
        """Draw merge items (egg, dragon, etc.) in slot."""
        if item_type.startswith("egg"):
            self._draw_egg_item(draw, cx, cy, repeat)
        elif item_type.startswith("dragon"):
            self._draw_dragon_item(draw, cx, cy)

    def _draw_egg_item(self, draw: ImageDraw.Draw, cx: int, cy: int, count: int = 1) -> None:
        """Draw cute egg items."""
        if count == 2:
            # Two eggs side by side
            gap = 30
            for offset in (-gap, gap):
                self._draw_single_egg(draw, cx + offset, cy)
        else:
            self._draw_single_egg(draw, cx, cy)

    def _draw_single_egg(self, draw: ImageDraw.Draw, cx: int, cy: int) -> None:
        """Draw one egg."""
        ew, eh = 28, 36
        # Egg body (ellipse)
        draw.ellipse(
            [cx - ew // 2, cy - eh // 2, cx + ew // 2, cy + eh // 2],
            fill=EGG_COLOR,
            outline=(160, 140, 220, 255),
            width=2,
        )
        # Highlight
        draw.ellipse(
            [cx - 6, cy - 12, cx + 4, cy - 4],
            fill=(240, 230, 255, 180),
        )
        # Sparkle dots
        draw.ellipse([cx + 8, cy - 10, cx + 12, cy - 6], fill=GOLD)
        draw.ellipse([cx - 14, cy + 6, cx - 10, cy + 10], fill=GOLD)

    def _draw_dragon_item(self, draw: ImageDraw.Draw, cx: int, cy: int) -> None:
        """Draw a simple baby dragon icon."""
        dw, dh = 40, 36
        # Body
        draw.ellipse(
            [cx - dw // 2, cy - dh // 2, cx + dw // 2, cy + dh // 2],
            fill=DRAGON_COLOR,
            outline=(255, 100, 30, 255),
            width=2,
        )
        # Eyes
        draw.ellipse([cx - 8, cy - 8, cx - 2, cy - 2], fill=WHITE)
        draw.ellipse([cx + 2, cy - 8, cx + 8, cy - 2], fill=WHITE)
        draw.ellipse([cx - 5, cy - 7, cx - 3, cy - 3], fill=(40, 20, 0, 255))
        draw.ellipse([cx + 5, cy - 7, cx + 7, cy - 3], fill=(40, 20, 0, 255))
        # Wings
        draw.polygon([(cx - dw // 2 - 8, cy - 8), (cx - dw // 2, cy - 6), (cx - dw // 2 - 4, cy + 4)], fill=(255, 160, 80, 255))
        draw.polygon([(cx + dw // 2 + 8, cy - 8), (cx + dw // 2, cy - 6), (cx + dw // 2 + 4, cy + 4)], fill=(255, 160, 80, 255))
        # Glow aura
        glow = Image.new("RGBA", (dw + 24, dh + 24), (0, 0, 0, 0))
        gdraw = ImageDraw.Draw(glow)
        gdraw.ellipse([4, 4, dw + 20, dh + 20], fill=(255, 215, 0, 30))
        glow = glow.filter(ImageFilter.GaussianBlur(radius=8))

    # ── Merge Arrow ─────────────────────────────────────────────────────

    def _draw_merge_arrow(self, draw: ImageDraw.Draw, x: int, cy: int) -> None:
        """Draw a glowing merge arrow pointing right."""
        arrow_len = 50
        head_size = 16
        x1, y1 = x - arrow_len // 2, cy
        x2, y2 = x + arrow_len // 2, cy

        # Glow layers
        for o in range(6, 0, -1):
            alpha = int(40 - o * 5)
            draw.line([(x1, y1 - o), (x2, y2 - o)], fill=GOLD[:3] + (alpha,), width=4 + o)
            draw.line([(x1, y1 + o), (x2, y2 + o)], fill=GOLD[:3] + (alpha,), width=4 + o)

        # Main arrow
        draw.line([(x1, y1), (x2, y2)], fill=GOLD, width=3)

        # Arrowhead
        draw.polygon([
            (x2, y2),
            (x2 - head_size, y2 - head_size // 2),
            (x2 - head_size, y2 + head_size // 2),
        ], fill=GOLD)

        # Merge sparkles
        for sx, sy in [(x1 + 10, cy - 12), (x2 - 10, cy - 10), (x1 + 20, cy + 10)]:
            draw.line([(sx - 4, sy), (sx + 4, sy)], fill=GOLD, width=1)
            draw.line([(sx, sy - 4), (sx, sy + 4)], fill=GOLD, width=1)

    # ── UI Elements ─────────────────────────────────────────────────────

    def _draw_ui_elements(
        self, draw: ImageDraw.Draw, img: Image.Image,
        bx: int, by: int, bw: int, bh: int, config: dict,
    ) -> None:
        """Draw game UI overlay: level badge, energy bar, coins, upgrade button."""
        font_sm = self._load_font(14)
        font_md = self._load_font(18)
        font_lg = self._load_font(22)

        margin = 12
        bar_w = int(bw * 0.85)

        # ── Top bar: Level badge + Energy ──
        bar_y = by + 8
        bar_x = bx + (bw - bar_w) // 2

        # Level badge
        level_text = config.get("level_text", "LEVEL 12")
        if font_md:
            bbox = draw.textbbox((0, 0), level_text, font=font_md)
            tw = bbox[2] - bbox[0]
            draw.rounded_rectangle(
                [bar_x, bar_y, bar_x + tw + 24, bar_y + 30],
                radius=10, fill=PURPLE_UI, outline=PURPLE_LIGHT, width=2,
            )
            draw.text((bar_x + 12, bar_y + 5), level_text, font=font_md, fill=GOLD)

        # Energy bar
        if config.get("show_energy_bar", True):
            energy_pct = config.get("energy_pct", 0.72)
            e_x = bar_x + 120
            e_y = bar_y + 6
            e_w = bar_w - 130
            e_h = 18

            # BG
            draw.rounded_rectangle([e_x, e_y, e_x + e_w, e_y + e_h], radius=8, fill=(20, 15, 40, 220))
            # Fill
            fill_w = int(e_w * energy_pct)
            draw.rounded_rectangle([e_x, e_y, e_x + fill_w, e_y + e_h], radius=8, fill=(80, 200, 120, 220))
            # Label
            if font_sm:
                label = f"⚡ {int(energy_pct * 100)}%"
                draw.text((e_x + 6, e_y + 1), label, font=font_sm, fill=WHITE)

        # ── Bottom bar: Coins + Upgrade button ──
        bottom_y = by + bh - 44

        # Coins
        if config.get("show_coins", True):
            coin_text = f"🪙 {config.get('coin_count', '2,450')}"
            if font_md:
                bbox = draw.textbbox((0, 0), coin_text, font=font_md)
                tw = bbox[2] - bbox[0]
                draw.rounded_rectangle(
                    [bar_x, bottom_y, bar_x + tw + 20, bottom_y + 32],
                    radius=10, fill=(50, 35, 80, 220), outline=PURPLE_LIGHT, width=1,
                )
                draw.text((bar_x + 10, bottom_y + 5), coin_text, font=font_md, fill=GOLD)

        # Upgrade button
        if config.get("show_upgrade_button", True):
            btn_text = "UPGRADE"
            btn_w = 120
            btn_x = bar_x + bar_w - btn_w
            btn_y = bottom_y

            if font_lg:
                bbox = draw.textbbox((0, 0), btn_text, font=font_lg)
                tw = bbox[2] - bbox[0]
                draw.rounded_rectangle(
                    [btn_x, btn_y, btn_x + btn_w, btn_y + 32],
                    radius=12, fill=GREEN, outline=(60, 180, 90, 255), width=2,
                )
                draw.text((btn_x + (btn_w - tw) // 2, btn_y + 4), btn_text, font=font_lg, fill=WHITE)

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