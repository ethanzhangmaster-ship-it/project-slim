"""截图自动渲染器 — 将 ScreenshotSpec 一步渲染为像素图片.

设计目标:
  - 整合 Spec 生成与 PIL 像素渲染为单一闭环
  - 支持多设备尺寸 (iPhone 6.7"/6.5"/5.5"/iPad/Google Play)
  - 支持多种布局 (top_text_bottom_image / center_text / full_image_overlay)
  - 支持多种配色方案 (vibrant / dark / light / gaming / pastel)
  - 文字渲染 + 背景 + CTA 按钮 + 可选背景图叠加
  - 不依赖外部 API，仅使用 PIL (Pillow)

输出: PNG 图片 + sidecar JSON 清单 (用于 list_rendered / get_stats 回放)
"""
from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

# 项目根目录 (src/market_ops/workspace/screenshot_renderer.py → parents[3] = 项目根)
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_OUTPUT_DIR = str(_PROJECT_ROOT / "data" / "screenshots")

# Windows 字体候选 (按优先级)，找不到则回退到 PIL 默认位图字体
_FONT_CANDIDATES = (
    "C:/Windows/Fonts/segoeuib.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
)

# 共享的测量用 draw (textbbox 仅做度量，不依赖画布尺寸)
_MEASURE_DRAW = ImageDraw.Draw(Image.new("RGB", (16, 16)))


@dataclass
class ScreenshotSpec:
    """截图规格 — 描述一张商店截图的全部创意参数."""

    game_id: str
    device_type: str  # "iphone_6.7" | "iphone_6.5" | "iphone_5.5" | "ipad" | "google_play"
    headline: str
    subheadline: str = ""
    layout: str = "top_text_bottom_image"  # 布局类型
    palette: str = "vibrant"  # 配色方案名称
    cta: str = ""
    background_color: str = "#1a1a2e"
    text_color: str = "#ffffff"
    accent_color: str = "#e94560"
    image_path: str = ""  # 可选的背景/素材图路径
    dimensions: tuple[int, int] = (1290, 2796)  # iPhone 6.7"

    def to_dict(self) -> dict:
        return {
            "game_id": self.game_id,
            "device_type": self.device_type,
            "headline": self.headline,
            "subheadline": self.subheadline,
            "layout": self.layout,
            "palette": self.palette,
            "cta": self.cta,
            "background_color": self.background_color,
            "text_color": self.text_color,
            "accent_color": self.accent_color,
            "image_path": self.image_path,
            "dimensions": list(self.dimensions),
        }


@dataclass
class RenderedScreenshot:
    """渲染后的截图 — 包含原规格与产物元信息."""

    spec: ScreenshotSpec
    image_path: str  # 保存的 PNG 文件路径
    width: int
    height: int
    file_size: int
    rendered_at: str

    def to_dict(self) -> dict:
        return {
            "spec": self.spec.to_dict(),
            "image_path": self.image_path,
            "width": self.width,
            "height": self.height,
            "file_size": self.file_size,
            "rendered_at": self.rendered_at,
        }


class ScreenshotRenderer:
    """截图渲染器 — 将 ScreenshotSpec 渲染为像素图片.

    支持:
    - 多种设备尺寸 (iPhone 6.7"/6.5"/5.5"/iPad/Google Play)
    - 多种布局 (top_text_bottom_image / center_text / full_image_overlay)
    - 多种配色方案
    - 文字渲染 + 背景 + CTA 按钮
    - 可选背景图叠加
    """

    # 设备尺寸预设 (宽, 高)
    DEVICE_DIMENSIONS = {
        "iphone_6.7": (1290, 2796),
        "iphone_6.5": (1242, 2688),
        "iphone_5.5": (1242, 2208),
        "ipad": (2048, 2732),
        "google_play": (1080, 1920),
    }

    # 配色方案预设
    PALETTES = {
        "vibrant": {"bg": "#1a1a2e", "text": "#ffffff", "accent": "#e94560"},
        "dark": {"bg": "#0f0f0f", "text": "#ffffff", "accent": "#3498db"},
        "light": {"bg": "#ffffff", "text": "#2c3e50", "accent": "#e74c3c"},
        "gaming": {"bg": "#16213e", "text": "#ffffff", "accent": "#fbb034"},
        "pastel": {"bg": "#fce4ec", "text": "#880e4f", "accent": "#ec407a"},
    }

    # 布局类型白名单
    LAYOUTS = ("top_text_bottom_image", "center_text", "full_image_overlay")

    def __init__(self, output_dir: str = ""):
        self.output_dir = output_dir or _DEFAULT_OUTPUT_DIR

    # ── 公开 API ───────────────────────────────────────────

    def render(self, spec: ScreenshotSpec) -> RenderedScreenshot:
        """渲染单张截图为 PNG 并落盘，返回产物元信息."""
        width, height = self._resolve_dimensions(spec)
        bg_rgb = self._hex_to_rgb(self._resolve(spec, "bg"))
        text_rgb = self._hex_to_rgb(self._resolve(spec, "text"))
        accent_rgb = self._hex_to_rgb(self._resolve(spec, "accent"))

        # 画布 (RGBA 便于叠加)
        canvas = Image.new("RGBA", (width, height), bg_rgb + (255,))
        draw = ImageDraw.Draw(canvas, "RGBA")

        bg_image = self._load_image(spec.image_path)

        layout = spec.layout or "top_text_bottom_image"
        if layout == "center_text":
            self._render_center_text(draw, canvas, spec, width, height,
                                     text_rgb, accent_rgb, bg_rgb, bg_image)
        elif layout == "full_image_overlay":
            self._render_full_image_overlay(draw, canvas, spec, width, height,
                                            text_rgb, accent_rgb, bg_rgb, bg_image)
        else:
            self._render_top_text_bottom_image(draw, canvas, spec, width, height,
                                               text_rgb, accent_rgb, bg_rgb, bg_image)

        # 落盘
        out_dir = Path(self.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        stem = f"{spec.game_id}_{spec.device_type}_{ts}_{uuid.uuid4().hex[:8]}"
        png_path = out_dir / f"{stem}.png"
        canvas.convert("RGB").save(png_path, format="PNG")
        file_size = png_path.stat().st_size
        rendered_at = datetime.now().isoformat(timespec="seconds")

        rendered = RenderedScreenshot(
            spec=spec,
            image_path=str(png_path),
            width=width,
            height=height,
            file_size=file_size,
            rendered_at=rendered_at,
        )
        # sidecar JSON 清单 — 供 list_rendered / get_stats 回放
        manifest_path = out_dir / f"{stem}.json"
        try:
            manifest_path.write_text(
                json.dumps(rendered.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError as exc:
            logger.warning("写入截图清单失败 %s: %s", manifest_path, exc)
        return rendered

    def render_batch(self, specs: list[ScreenshotSpec]) -> list[RenderedScreenshot]:
        """批量渲染截图，逐张落盘并返回产物列表."""
        results: list[RenderedScreenshot] = []
        for spec in specs:
            try:
                results.append(self.render(spec))
            except Exception as exc:  # 单张失败不影响整批
                logger.error("渲染截图失败 (game_id=%s): %s", spec.game_id, exc)
        return results

    def create_spec(
        self,
        game_id: str,
        device_type: str = "iphone_6.7",
        headline: str = "",
        subheadline: str = "",
        cta: str = "",
        palette: str = "vibrant",
        layout: str = "top_text_bottom_image",
    ) -> ScreenshotSpec:
        """创建截图规格 (辅助方法) — 由 palette 推导配色，由 device_type 推导尺寸."""
        if device_type not in self.DEVICE_DIMENSIONS:
            raise ValueError(
                f"未知 device_type: {device_type}，可选: {list(self.DEVICE_DIMENSIONS)}"
            )
        if palette not in self.PALETTES:
            raise ValueError(
                f"未知 palette: {palette}，可选: {list(self.PALETTES)}"
            )
        pal = self.PALETTES[palette]
        return ScreenshotSpec(
            game_id=game_id,
            device_type=device_type,
            headline=headline,
            subheadline=subheadline,
            cta=cta,
            layout=layout,
            palette=palette,
            background_color=pal["bg"],
            text_color=pal["text"],
            accent_color=pal["accent"],
            dimensions=self.DEVICE_DIMENSIONS[device_type],
        )

    def list_rendered(self, game_id: str | None = None) -> list[RenderedScreenshot]:
        """列出已渲染的截图，可按 game_id 过滤."""
        out_dir = Path(self.output_dir)
        if not out_dir.exists():
            return []
        results: list[RenderedScreenshot] = []
        for manifest in sorted(out_dir.glob("*.json")):
            try:
                data = json.loads(manifest.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            spec_dict = data.get("spec", {})
            if game_id and spec_dict.get("game_id") != game_id:
                continue
            results.append(self._from_dict(data))
        return results

    def get_stats(self) -> dict:
        """渲染统计信息."""
        rendered = self.list_rendered()
        by_game: dict[str, int] = {}
        by_device: dict[str, int] = {}
        by_palette: dict[str, int] = {}
        total_size = 0
        for item in rendered:
            by_game[item.spec.game_id] = by_game.get(item.spec.game_id, 0) + 1
            by_device[item.spec.device_type] = by_device.get(item.spec.device_type, 0) + 1
            by_palette[item.spec.palette] = by_palette.get(item.spec.palette, 0) + 1
            total_size += item.file_size
        return {
            "count": len(rendered),
            "total_size": total_size,
            "by_game": by_game,
            "by_device": by_device,
            "by_palette": by_palette,
            "output_dir": self.output_dir,
        }

    # ── 布局渲染 ───────────────────────────────────────────

    def _render_top_text_bottom_image(
        self, draw: ImageDraw.ImageDraw, canvas: Image.Image, spec: ScreenshotSpec,
        width: int, height: int, text_rgb, accent_rgb, bg_rgb, bg_image,
    ) -> None:
        """顶部文字 + 底部图片卡 (无图时绘制占位卡) + CTA."""
        margin = max(width // 24, 24)

        # 顶部 headline
        headline = spec.headline or spec.game_id
        h_font, _ = self._fit_font(headline, width - 2 * margin, width // 9)
        h_lines = self._wrap(headline, h_font, width - 2 * margin)
        line_h = self._text_height("Ag", h_font)
        y = height // 14
        for line in h_lines[:3]:
            self._draw_text_centered(draw, line, h_font, y, width, text_rgb + (255,))
            y += int(line_h * 1.15)

        # subheadline
        if spec.subheadline:
            s_font, _ = self._fit_font(spec.subheadline, width - 2 * margin, width // 16,
                                       min_size=max(width // 40, 20))
            s_lines = self._wrap(spec.subheadline, s_font, width - 2 * margin)
            s_line_h = self._text_height("Ag", s_font)
            for line in s_lines[:3]:
                self._draw_text_centered(draw, line, s_font, y, width, text_rgb + (220,))
                y += int(s_line_h * 1.1)

        # 底部图片卡
        card_x0 = margin
        card_x1 = width - margin
        card_y0 = int(height * 0.42)
        card_y1 = int(height * 0.86)
        radius = max(width // 40, 24)
        if bg_image is not None:
            self._paste_rounded(canvas, bg_image, (card_x0, card_y0, card_x1, card_y1),
                                radius, accent_rgb, border_width=max(width // 220, 4))
        else:
            draw.rounded_rectangle((card_x0, card_y0, card_x1, card_y1), radius=radius,
                                   fill=bg_rgb + (255,), outline=accent_rgb + (255,),
                                   width=max(width // 220, 4))
            ph_font, _ = self._fit_font("GAMEPLAY", (card_x1 - card_x0) // 2, width // 14)
            self._draw_text_centered(draw, "GAMEPLAY", ph_font,
                                     (card_y0 + card_y1) // 2, width, accent_rgb + (200,))

        # CTA
        if spec.cta:
            self._draw_cta(draw, spec.cta, width, height, accent_rgb, text_rgb)

    def _render_center_text(
        self, draw: ImageDraw.ImageDraw, canvas: Image.Image, spec: ScreenshotSpec,
        width: int, height: int, text_rgb, accent_rgb, bg_rgb, bg_image,
    ) -> None:
        """居中文字布局，可选淡化的背景图."""
        margin = max(width // 24, 24)

        # 可选: 淡化背景图
        if bg_image is not None:
            faded = self._cover(bg_image, (width, height)).convert("RGBA")
            overlay = Image.new("RGBA", (width, height), bg_rgb + (160,))
            canvas.paste(faded, (0, 0), faded)
            canvas.paste(overlay, (0, 0), overlay)
            draw = ImageDraw.Draw(canvas, "RGBA")

        headline = spec.headline or spec.game_id
        h_font, _ = self._fit_font(headline, width - 2 * margin, width // 8)
        h_lines = self._wrap(headline, h_font, width - 2 * margin)
        line_h = self._text_height("Ag", h_font)
        total_h = int(line_h * 1.15) * len(h_lines[:3])
        y = (height - total_h) // 2 - int(height * 0.08)
        for line in h_lines[:3]:
            self._draw_text_centered(draw, line, h_font, y, width, text_rgb + (255,))
            y += int(line_h * 1.15)

        if spec.subheadline:
            s_font, _ = self._fit_font(spec.subheadline, width - 2 * margin, width // 18,
                                       min_size=max(width // 44, 20))
            s_lines = self._wrap(spec.subheadline, s_font, width - 2 * margin)
            s_line_h = self._text_height("Ag", s_font)
            for line in s_lines[:3]:
                self._draw_text_centered(draw, line, s_font, y, width, text_rgb + (220,))
                y += int(s_line_h * 1.1)

        if spec.cta:
            self._draw_cta(draw, spec.cta, width, height, accent_rgb, text_rgb)

    def _render_full_image_overlay(
        self, draw: ImageDraw.ImageDraw, canvas: Image.Image, spec: ScreenshotSpec,
        width: int, height: int, text_rgb, accent_rgb, bg_rgb, bg_image,
    ) -> None:
        """整图背景 + 半透明遮罩 + 文字 + CTA."""
        if bg_image is not None:
            covered = self._cover(bg_image, (width, height)).convert("RGBA")
            canvas.paste(covered, (0, 0), covered)
            draw = ImageDraw.Draw(canvas, "RGBA")
        # 半透明遮罩，提升文字可读性
        draw.rectangle((0, 0, width, height), fill=bg_rgb + (110,))

        margin = max(width // 24, 24)
        headline = spec.headline or spec.game_id
        h_font, _ = self._fit_font(headline, width - 2 * margin, width // 8)
        h_lines = self._wrap(headline, h_font, width - 2 * margin)
        line_h = self._text_height("Ag", h_font)
        y = int(height * 0.18)
        for line in h_lines[:3]:
            self._draw_text_centered(draw, line, h_font, y, width, text_rgb + (255,))
            y += int(line_h * 1.15)

        if spec.subheadline:
            s_font, _ = self._fit_font(spec.subheadline, width - 2 * margin, width // 18,
                                       min_size=max(width // 44, 20))
            s_lines = self._wrap(spec.subheadline, s_font, width - 2 * margin)
            s_line_h = self._text_height("Ag", s_font)
            for line in s_lines[:3]:
                self._draw_text_centered(draw, line, s_font, y, width, text_rgb + (235,))
                y += int(s_line_h * 1.1)

        if spec.cta:
            self._draw_cta(draw, spec.cta, width, height, accent_rgb, text_rgb)

    # ── 绘图工具 ───────────────────────────────────────────

    def _draw_cta(self, draw: ImageDraw.ImageDraw, cta: str, width: int, height: int,
                  accent_rgb, text_rgb) -> None:
        """绘制 CTA 按钮 (圆角矩形 + 居中文字)."""
        max_btn_w = int(width * 0.7)
        font, _ = self._fit_font(cta, max_btn_w, width // 16, min_size=28)
        bbox = _MEASURE_DRAW.textbbox((0, 0), cta, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        pad_x = max(width // 24, 24)
        pad_y = max(height // 70, 16)
        btn_w = min(tw + 2 * pad_x, max_btn_w)
        btn_h = th + 2 * pad_y
        x = (width - btn_w) // 2
        y = height - int(height * 0.10) - btn_h
        draw.rounded_rectangle((x, y, x + btn_w, y + btn_h), radius=btn_h // 2,
                               fill=accent_rgb + (255,))
        tx = x + (btn_w - tw) // 2 - bbox[0]
        ty = y + (btn_h - th) // 2 - bbox[1]
        draw.text((tx, ty), cta, font=font, fill=text_rgb + (255,))

    def _draw_text_centered(self, draw: ImageDraw.ImageDraw, text: str, font,
                            y: int, width: int, fill) -> None:
        bbox = _MEASURE_DRAW.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        x = (width - tw) // 2 - bbox[0]
        draw.text((x, y), text, font=font, fill=fill)

    def _paste_rounded(self, canvas: Image.Image, image: Image.Image, box,
                       radius: int, border_rgb, border_width: int = 0) -> None:
        """把图片以 cover 方式裁剪并圆角粘贴到 box，可选描边."""
        x0, y0, x1, y1 = box
        w = x1 - x0
        h = y1 - y0
        if w <= 0 or h <= 0:
            return
        covered = self._cover(image.convert("RGBA"), (w, h))
        mask = Image.new("L", (w, h), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, w - 1, h - 1), radius=radius, fill=255)
        canvas.paste(covered, (x0, y0), mask)
        if border_width > 0:
            ImageDraw.Draw(canvas, "RGBA").rounded_rectangle(
                (x0, y0, x1 - 1, y1 - 1), radius=radius,
                outline=border_rgb + (255,), width=border_width,
            )

    @staticmethod
    def _cover(image: Image.Image, size: tuple[int, int]) -> Image.Image:
        """以 cover 方式缩放裁剪到指定尺寸 (居中)."""
        target_w, target_h = size
        ratio = max(target_w / image.width, target_h / image.height)
        resized = image.resize(
            (max(round(image.width * ratio), 1), max(round(image.height * ratio), 1)),
            Image.Resampling.LANCZOS,
        )
        left = (resized.width - target_w) // 2
        top = (resized.height - target_h) // 2
        return resized.crop((left, top, left + target_w, top + target_h))

    def _fit_font(self, text: str, max_width: int, start_size: int,
                  min_size: int = 28) -> tuple[Any, int]:
        """从 start_size 递减字号，直到文本宽度不超过 max_width."""
        size = start_size
        while size >= min_size:
            font = self._font(size)
            bbox = _MEASURE_DRAW.textbbox((0, 0), text, font=font)
            if bbox[2] - bbox[0] <= max_width:
                return font, size
            size -= 2
        return self._font(min_size), min_size

    def _wrap(self, text: str, font, max_width: int) -> list[str]:
        """按空格分词做简单换行; 中文按字符兜底."""
        text = text.strip()
        if not text:
            return []
        if self._text_width(text, font) <= max_width:
            return [text]
        lines: list[str] = []
        # 优先按空格分词
        if " " in text:
            current = ""
            for word in text.split():
                trial = f"{current} {word}".strip()
                if self._text_width(trial, font) <= max_width:
                    current = trial
                else:
                    if current:
                        lines.append(current)
                    current = word
            if current:
                lines.append(current)
        else:
            current = ""
            for ch in text:
                trial = current + ch
                if self._text_width(trial, font) <= max_width:
                    current = trial
                else:
                    if current:
                        lines.append(current)
                    current = ch
            if current:
                lines.append(current)
        return lines

    def _text_width(self, text: str, font) -> int:
        bbox = _MEASURE_DRAW.textbbox((0, 0), text, font=font)
        return bbox[2] - bbox[0]

    def _text_height(self, text: str, font) -> int:
        bbox = _MEASURE_DRAW.textbbox((0, 0), text, font=font)
        return bbox[3] - bbox[1]

    @staticmethod
    def _font(size: int):
        for candidate in _FONT_CANDIDATES:
            try:
                return ImageFont.truetype(candidate, size)
            except OSError:
                continue
        return ImageFont.load_default()

    @staticmethod
    def _load_image(image_path: str) -> Image.Image | None:
        if not image_path:
            return None
        path = Path(image_path)
        if not path.exists() or not path.is_file():
            return None
        try:
            return Image.open(path).convert("RGBA")
        except Exception as exc:
            logger.warning("加载背景图失败 %s: %s", image_path, exc)
            return None

    @staticmethod
    def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
        """解析 #RRGGBB / RRGGBB 颜色为 (r, g, b)."""
        color = hex_color.strip().lstrip("#")
        if len(color) == 3:
            color = "".join(c * 2 for c in color)
        if len(color) != 6:
            return (0, 0, 0)
        try:
            return (int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16))
        except ValueError:
            return (0, 0, 0)

    def _resolve(self, spec: ScreenshotSpec, key: str) -> str:
        """解析配色: 优先用 spec 显式颜色; 若显式颜色仍是 vibrant 默认值且 palette 非 vibrant，则用 palette."""
        pal = self.PALETTES.get(spec.palette, {})
        if key == "bg":
            val = spec.background_color
            default = "#1a1a2e"
        elif key == "text":
            val = spec.text_color
            default = "#ffffff"
        else:
            val = spec.accent_color
            default = "#e94560"
        if spec.palette != "vibrant" and pal and val == default:
            return pal.get(key, default)
        return val

    def _resolve_dimensions(self, spec: ScreenshotSpec) -> tuple[int, int]:
        """优先用 spec.dimensions，否则按 device_type 查表."""
        if spec.dimensions and spec.dimensions[0] > 0 and spec.dimensions[1] > 0:
            return spec.dimensions
        return self.DEVICE_DIMENSIONS.get(spec.device_type, self.DEVICE_DIMENSIONS["iphone_6.7"])

    @staticmethod
    def _from_dict(data: dict) -> RenderedScreenshot:
        spec_dict = data.get("spec", {})
        dims = spec_dict.get("dimensions") or [1290, 2796]
        spec = ScreenshotSpec(
            game_id=spec_dict.get("game_id", ""),
            device_type=spec_dict.get("device_type", "iphone_6.7"),
            headline=spec_dict.get("headline", ""),
            subheadline=spec_dict.get("subheadline", ""),
            layout=spec_dict.get("layout", "top_text_bottom_image"),
            palette=spec_dict.get("palette", "vibrant"),
            cta=spec_dict.get("cta", ""),
            background_color=spec_dict.get("background_color", "#1a1a2e"),
            text_color=spec_dict.get("text_color", "#ffffff"),
            accent_color=spec_dict.get("accent_color", "#e94560"),
            image_path=spec_dict.get("image_path", ""),
            dimensions=(int(dims[0]), int(dims[1])),
        )
        return RenderedScreenshot(
            spec=spec,
            image_path=data.get("image_path", ""),
            width=int(data.get("width", 0)),
            height=int(data.get("height", 0)),
            file_size=int(data.get("file_size", 0)),
            rendered_at=data.get("rendered_at", ""),
        )


__all__ = ["ScreenshotSpec", "RenderedScreenshot", "ScreenshotRenderer"]
