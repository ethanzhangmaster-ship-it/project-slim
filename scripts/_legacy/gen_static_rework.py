"""Phase 2.1.7 静态图重做 — 验证版（4 张）。

核心变更（相对失败管线）：
  1. AI 只生成「干净场景素材」（扁平渐变背景、上下 22% 留白、中部 before→arrow→after）。
  2. 广告结构由代码(PIL)强行合成：顶部安全区(标题)、中部合并箭头、底部 CTA 按钮、FREE 徽章。
     —— 版式 100% 可控，不靠模型「自觉」。
  3. 真·视觉合规过滤（非 CLIP）：符文/文字连通域、假 UI 横条行均值、安全区拥挤度。

用法: python scripts/gen_static_rework.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from scipy import ndimage as ndi

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from market_ops.clients.lovart import LovartClient, download_image

OUT = ROOT / "output" / "creative_rework"
RAW = OUT / "raw"
MOCK = OUT / "mock"
for d in (RAW, MOCK):
    d.mkdir(parents=True, exist_ok=True)

WINNER = ROOT / "output" / "phase2_1_5" / "real_validation" / "winner_reference" / "winner_001.png"

FONT_CANDIDATES = {
    "regular": [r"C:/Windows/Fonts/arial.ttf", r"C:/Windows/Fonts/ARIAL.TTF"],
    "bold": [r"C:/Windows/Fonts/arialbd.ttf", r"C:/Windows/Fonts/ARIALBD.TTF"],
}


def load_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    for c in FONT_CANDIDATES["bold" if bold else "regular"]:
        if Path(c).exists():
            try:
                return ImageFont.truetype(c, size)
            except Exception:
                pass
    return ImageFont.load_default()


# ---- 4 个验证概念（取之前相对最干净的 004/003/002 + 修符文的 001）----
CONCEPTS = [
    {
        "id": "R1",
        "theme": "Dragon Egg Merge",
        "before": "two identical small dragon eggs",
        "after": "one cute baby dragon",
        "headline": "Merge eggs. Hatch your dragon!",
    },
    {
        "id": "R2",
        "theme": "Castle Merge",
        "before": "two small stone castles",
        "after": "one grand royal castle",
        "headline": "Merge castles. Build a kingdom!",
    },
    {
        "id": "R3",
        "theme": "Flower to Magic Tree",
        "before": "two glowing magic flowers",
        "after": "one blooming magic tree",
        "headline": "Merge flowers. Grow magic!",
    },
    {
        "id": "R4",
        "theme": "Dragon Merge",
        "before": "two small dragons",
        "after": "one majestic adult dragon",
        "headline": "Merge dragons. Unleash power!",
    },
]


def build_prompt(c: dict) -> str:
    return (
        "Square 1:1 mobile game advertisement render. "
        "FLAT solid purple-to-blue gradient background, NO scenery, NO landscape, "
        "NO floating islands, NO ruins, NO characters with faces. "
        "TOP 22% and BOTTOM 22% of the canvas must be EMPTY flat background with NO objects and NO text. "
        f"In the CENTER horizontal band only: on the LEFT, {c['before']} side by side; "
        "in the CENTER, a bright glowing golden vertical merge beam and arrow pointing right; "
        f"on the RIGHT, {c['after']}. "
        "NO humans, NO faces, NO large characters as focal point. "
        "NO text, NO logo, NO UI, NO buttons, NO frames, NO panels, NO runes, NO glyphs, "
        "NO symbols, NO watermark. "
        "Clean high-end 3D mobile game art style, Facebook UA creative."
    )


# ---------------- 真·视觉合规过滤（numpy + scipy，非 CLIP）----------------
def _glyph_in_zone(zone: np.ndarray) -> bool:
    med = np.median(zone)
    dark = zone < (med - 25)
    if dark.sum() < 50:
        return False
    lab, n = ndi.label(dark)
    if n == 0:
        return False
    sizes = np.bincount(lab.ravel())[1:]
    glyph_like = int(np.sum((sizes > 12) & (sizes < 1500)))
    return glyph_like > 10


def _ui_bar(gray: np.ndarray) -> bool:
    rowmean = gray.mean(axis=1)
    gm = rowmean.mean()
    low = rowmean < (gm - 35)
    lab, n = ndi.label(low)
    if n == 0:
        return False
    H = gray.shape[0]
    sizes = np.bincount(lab.ravel())[1:]
    for i, s in enumerate(sizes):
        if s > 0.35 * H:
            coords = np.where(lab == (i + 1))[0]
            pos = coords.mean() / H
            if pos < 0.14 or pos > 0.86:
                return True
    return False


def _busy(zone: np.ndarray) -> bool:
    return float(zone.std()) > 38.0


def visual_filter(path: Path) -> dict:
    img = Image.open(path).convert("L")
    arr = np.array(img)
    H, W = arr.shape
    top = arr[: int(0.22 * H)]
    bot = arr[int(0.78 * H):]
    glyph_top = _glyph_in_zone(top)
    glyph_bot = _glyph_in_zone(bot)
    ui_bar = _ui_bar(arr)
    busy_top = _busy(top)
    busy_bot = _busy(bot)
    raw_compliant = not (glyph_top or glyph_bot or ui_bar or busy_top or busy_bot)
    return {
        "glyph_in_top_safe_zone": glyph_top,
        "glyph_in_bottom_safe_zone": glyph_bot,
        "fake_ui_bar": ui_bar,
        "busy_top_safe_zone": busy_top,
        "busy_bottom_safe_zone": busy_bot,
        "raw_compliant": raw_compliant,
    }


# ---------------- 程序化广告合成（PIL 强行拼版式）----------------
def composite_ad_frame(raw_path: Path, out_path: Path, headline: str) -> None:
    W = H = 1080
    img = Image.open(raw_path).convert("RGB").resize((W, H))

    # 上下安全区深色叠层（保证文字可读）
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    overlay.paste(Image.new("RGBA", (W, int(0.22 * H)), (8, 6, 22, 150)), (0, 0))
    overlay.paste(Image.new("RGBA", (W, int(0.22 * H)), (8, 6, 22, 178)), (0, int(0.78 * H)))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(img)

    # 顶部标题
    draw.text((W / 2, int(0.11 * H)), headline, fill=(255, 255, 255),
              font=load_font(46, bold=True), anchor="mm")

    # 中部合并箭头（金，带辉光）
    ay = int(0.50 * H)
    x0, x1 = int(0.40 * W), int(0.60 * W)
    arrow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ad = ImageDraw.Draw(arrow)
    gold = (255, 200, 60, 255)
    ad.line([(x0, ay), (x1 - 22, ay)], fill=gold, width=14)
    ad.polygon([(x1, ay), (x1 - 32, ay - 24), (x1 - 32, ay + 24)], fill=gold)
    arrow = arrow.filter(ImageFilter.GaussianBlur(4))
    img = Image.alpha_composite(img.convert("RGBA"), arrow).convert("RGB")
    draw = ImageDraw.Draw(img)

    # 底部 CTA 按钮
    btn_w, btn_h = int(0.36 * W), int(0.075 * H)
    bx0 = int(0.5 * W - btn_w / 2)
    by0 = int(0.86 * H)
    draw.rounded_rectangle([bx0, by0, bx0 + btn_w, by0 + btn_h], radius=btn_h // 2, fill=(255, 160, 40))
    draw.text((0.5 * W, by0 + btn_h / 2), "PLAY FREE", fill=(255, 255, 255),
              font=load_font(40, bold=True), anchor="mm")

    # 右上 FREE 徽章
    badge = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bd = ImageDraw.Draw(badge)
    r = int(0.052 * H)
    cx, cy = int(0.88 * W), int(0.11 * H)
    bd.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 60, 90, 255))
    bd.text((cx, cy), "FREE", fill=(255, 255, 255), font=load_font(30, bold=True), anchor="mm")
    img = Image.alpha_composite(img.convert("RGBA"), badge).convert("RGB")

    img.save(out_path)


def main() -> int:
    client = LovartClient()
    if not client.is_configured:
        print("[!] Lovart AK/SK 未配置。")
        return 1

    winner_cdn = None
    if WINNER.exists():
        try:
            winner_cdn = client.upload_file(WINNER)
            print(f"  [winner] CDN ref ready")
        except Exception as exc:
            print(f"  [winner] upload failed ({exc}); 无参考生成。")

    report = []
    for c in CONCEPTS:
        cid = c["id"]
        raw_path = RAW / f"{cid}.png"
        mock_path = MOCK / f"{cid}.png"
        prompt = build_prompt(c)
        t0 = time.time()
        result = client.generate_image(prompt, attachments=[winner_cdn] if winner_cdn else None)
        if not result.image_urls and winner_cdn:
            print(f"  [retry] {cid} attachment failed, regen w/o ref")
            result = client.generate_image(prompt, attachments=None)
        if not result.image_urls:
            print(f"  [FAIL] {cid} ({result.status})")
            report.append({"id": cid, "theme": c["theme"], "generated": False})
            continue
        download_image(result.image_urls[0], raw_path)
        filt = visual_filter(raw_path)
        composite_ad_frame(raw_path, mock_path, c["headline"])
        report.append({
            "id": cid, "theme": c["theme"], "generated": True,
            "headline": c["headline"], "raw_compliant": filt["raw_compliant"],
            "filter": filt, "raw": str(raw_path), "mock": str(mock_path),
        })
        print(f"  [ok] {cid} {c['theme']} ({time.time() - t0:.0f}s) raw_compliant={filt['raw_compliant']}")

    (OUT / "rework_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n=== rework validation batch done: {sum(r.get('generated', False) for r in report)}/4 ===")
    print(f"  report -> {OUT / 'rework_report.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
