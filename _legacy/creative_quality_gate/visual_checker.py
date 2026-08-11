"""Phase 2.1.6 — 视觉基础检查（无模型依赖，纯 PIL/numpy）。

负责 Hard Reject 中可量化的部分：
- 长宽比（必须匹配 winner ±5%）
- 奖励面积占比（reward 中央突出度 proxy）
- AI 文字伪影启发式（高频水平边缘密度 → 文字密集区）
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))


def aspect_ratio(path: str | Path) -> float:
    """返回 width/height。"""
    w, h = Image.open(path).size
    return w / h


def aspect_matches(path: str | Path, ref_ratio: float, tol: float = 0.05) -> tuple[bool, float]:
    """长宽比是否落在 winner 基准 ±tol 内。"""
    r = aspect_ratio(path)
    ok = abs(r - ref_ratio) <= tol
    return ok, round(r, 3)


def reward_area_ratio(path: str | Path) -> float:
    """奖励在中央区域突出的 proxy。

    做法：取图像中央 50% 框，计算该区域的「高饱和 + 高亮度对比」像素占比，
    作为「奖励主体是否占据画面核心」的近似。不是精确分割，仅用于趋势判断。
    """
    img = Image.open(path).convert("RGB").resize((256, 256))
    arr = np.asarray(img, dtype=np.float32) / 255.0
    h, w, _ = arr.shape
    cy, cx = h // 2, w // 2
    m = h // 4
    center = arr[cy - m : cy + m, cx - m : cx + m]  # 中央 50%
    # 饱和度
    mx = center.max(axis=2)
    mn = center.min(axis=2)
    sat = mx - mn
    # 亮度对比（与局部均值的偏离）
    lum = center.mean(axis=2)
    contrast = np.abs(lum - lum.mean())
    salient = (sat > 0.35) & (contrast > 0.12)
    return round(float(salient.mean()), 3)


def ai_text_density(path: str | Path) -> float:
    """AI 文字伪影检测（0-1，越高越疑似大面积乱码文字）。

    用连通域分析统计「字符状小笔画」密度：乱码文字图由大量极小面积的
    笔画连通域（字符间缝隙被切割成的小暗块）组成；正常游戏图主体是少量
    大连通域（阴影/主体连续），小连通域数量少一个数量级。

    实现：灰度图按中位数二值化取暗像素，scipy 标注连通域，统计面积<40
    的小连通域数量。实测：满屏乱码图 ~3000+，正常游戏图 ~150-400。
    这是真正的视觉文字检测，不依赖 CLIP（CLIP 对「文字 vs 乱码」方向会
    反转，不可靠）。
    """
    from scipy import ndimage

    img = Image.open(path).convert("L").resize((320, 320))
    a = np.asarray(img, dtype=np.float32)
    med = float(np.median(a))
    binary = (a < med).astype(np.uint8)  # 暗像素（笔画/字符/阴影）
    labeled, n = ndimage.label(binary)
    if n == 0:
        return 0.0
    sizes = ndimage.sum(np.ones_like(binary), labeled, index=range(1, n + 1))
    sizes = np.asarray(sizes, dtype=np.float32)
    small_count = int(np.sum(sizes < 40))
    # 实测标定：游戏图 ~150-400，满屏乱码 ~3000+
    score = small_count / 1000.0
    return round(float(min(1.0, max(0.0, score))), 3)


def gameplay_area_ratio(path: str | Path) -> float:
    """玩法主体占画面比例（Composition Validator 用）。

    取中央 gameplay 带（去掉上下各 18% 安全区），统计显著前景像素占比，
    作为「玩法主体是否占据画面主导」的近似几何量。

    阈值（PRD §8）：>= 0.45 视为主体够大。
    """
    img = Image.open(path).convert("RGB").resize((256, 256))
    arr = np.asarray(img, dtype=np.float32) / 255.0
    h, w, _ = arr.shape
    top = int(h * 0.18)
    bot = int(h * 0.82)
    band = arr[top:bot, :, :]
    mx = band.max(axis=2)
    mn = band.min(axis=2)
    sat = mx - mn
    lum = band.mean(axis=2)
    contrast_band = np.abs(lum - lum.mean())
    foreground = (sat > 0.30) & (contrast_band > 0.10)
    return round(float(foreground.mean()), 3)


def contrast(path: str | Path) -> float:
    """整图对比度（灰度 std），用于 visual quality 辅助。"""
    img = Image.open(path).convert("L").resize((128, 128))
    a = np.asarray(img, dtype=np.float32)
    return round(float(a.std() / 255.0), 3)
