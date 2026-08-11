"""Frame Analyzer — 帧级视觉特征提取引擎。

从视频关键帧中提取结构信号：
  - 视觉复杂度 (edge density / color entropy)
  - 文字密度 proxy (edge layout analysis)
  - 亮度 / 对比度
  - 帧间变化率 (motion proxy)
  - 色彩分布

所有特征基于 PIL + numpy，零外部依赖。
"""
from __future__ import annotations
from pathlib import Path
from typing import List, Optional
import numpy as np
from PIL import Image, ImageFilter, ImageOps


class FrameAnalyzer:
    """Analyze a single video frame for structural features."""

    def analyze(self, img: Image.Image) -> dict:
        """Extract all visual features from one frame.

        Returns:
            dict with: complexity, edge_density, brightness, contrast,
                       text_density_proxy, saturation, entropy, color_dominance
        """
        arr = np.array(img.convert("RGB"))
        gray = np.array(img.convert("L"))
        h, w = arr.shape[:2]

        # ── 1. Brightness ──
        brightness = float(gray.mean()) / 255.0

        # ── 2. Contrast (std of grayscale) ──
        contrast = float(gray.std()) / 255.0

        # ── 3. Edge density ──
        edges = img.convert("L").filter(ImageFilter.FIND_EDGES)
        edge_arr = np.array(edges)
        edge_density = float((edge_arr > 30).sum()) / (h * w)

        # ── 4. Text density proxy ──
        # High-frequency horizontal edges often indicate text
        # Apply Sobel-like horizontal edge detection
        horiz_edges = np.abs(np.diff(gray.astype(np.float32), axis=1))
        text_density = float((horiz_edges > 40).sum()) / ((h * (w - 1)))

        # ── 5. Color entropy (complexity of color distribution) ──
        # Bin RGB into 16^3 = 4096 cubes
        bins = 16
        r_bins = np.clip(arr[:, :, 0] // (256 // bins), 0, bins - 1).astype(int)
        g_bins = np.clip(arr[:, :, 1] // (256 // bins), 0, bins - 1).astype(int)
        b_bins = np.clip(arr[:, :, 2] // (256 // bins), 0, bins - 1).astype(int)
        bin_idx = r_bins * bins * bins + g_bins * bins + b_bins
        hist = np.bincount(bin_idx.ravel(), minlength=bins ** 3).astype(np.float32)
        hist = hist / hist.sum()
        nonzero = hist[hist > 0]
        entropy = float(-(nonzero * np.log2(nonzero)).sum())

        # ── 6. Saturation ──
        r, g, b = arr[:, :, 0].astype(np.float32), arr[:, :, 1].astype(np.float32), arr[:, :, 2].astype(np.float32)
        max_rgb = np.maximum(np.maximum(r, g), b)
        min_rgb = np.minimum(np.minimum(r, g), b)
        denom = np.where(max_rgb > 0, max_rgb, 1.0)
        sat = (max_rgb - min_rgb) / denom
        saturation = float(sat.mean())

        # ── 7. Color dominance (largest single color cluster %) ──
        top_color_ratio = float(hist.max())

        # ── 8. Center-weighted character presence proxy ──
        # Assume character is in center 40% of frame
        ch = int(h * 0.3)
        cw = int(w * 0.3)
        center = gray[ch:h - ch, cw:w - cw]
        center_brightness = float(center.mean()) / 255.0
        center_contrast = float(center.std()) / 255.0

        return {
            "brightness": round(brightness, 4),
            "contrast": round(contrast, 4),
            "edge_density": round(edge_density, 4),
            "text_density_proxy": round(text_density, 4),
            "color_entropy": round(entropy, 4),
            "saturation": round(saturation, 4),
            "top_color_ratio": round(top_color_ratio, 4),
            "center_brightness": round(center_brightness, 4),
            "center_contrast": round(center_contrast, 4),
        }


def analyze_video_frames(frame_paths: List[Path]) -> List[dict]:
    """Analyze all keyframes of a video.

    Args:
        frame_paths: [frame_05.jpg, frame_25.jpg, frame_50.jpg, frame_75.jpg, frame_95.jpg]

    Returns:
        List of frame feature dicts, one per frame in order.
    """
    analyzer = FrameAnalyzer()
    results = []
    for fp in frame_paths:
        if fp.exists() and fp.stat().st_size > 1024:
            try:
                img = Image.open(fp)
                features = analyzer.analyze(img)
                features["frame"] = fp.stem
                results.append(features)
            except Exception:
                results.append(None)
        else:
            results.append(None)
    return results


def compute_video_scores(frames: List[dict]) -> dict:
    """Aggregate frame-level features into video-level structural scores.

    3 个核心分数:
      - Hook_Score: 第一帧视觉冲击力 (基于 edge_density, contrast, center_contrast)
      - Comprehension_Score: 中段信息清晰度 (基于 text_density, entropy, saturation)
      - Reward_Score: 后段视觉回报度 (基于 brightness, saturation, entropy)
    """
    if not frames or not any(frames):
        return {"hook_score": 0, "comprehension_score": 0, "reward_score": 0, "confidence": "low"}

    valid = [f for f in frames if f is not None]

    # Hook: first frame (position 0) — 冲击力
    first = valid[0] if len(valid) >= 1 else valid[-1]
    hook_score = (
        first.get("edge_density", 0) * 0.3
        + first.get("contrast", 0) * 0.3
        + first.get("center_contrast", 0) * 0.2
        + first.get("saturation", 0) * 0.2
    )

    # Comprehension: mid frames (positions 1-2, ~25-50%) — 信息清晰度
    mid = [valid[i] for i in [1, 2] if i < len(valid)]
    if mid:
        comp_score = (
            np.mean([m.get("color_entropy", 0) for m in mid]) * 0.3
            - np.mean([m.get("text_density_proxy", 0) for m in mid]) * 0.2   # too much text = bad
            + np.mean([m.get("brightness", 0) for m in mid]) * 0.25
            + np.mean([m.get("saturation", 0) for m in mid]) * 0.25
        )
    else:
        comp_score = 0.2

    # Reward: later frames (positions 3-4, ~75-95%) — 视觉回报
    late = [valid[i] for i in [3, 4] if i < len(valid)]
    if late:
        reward_score = (
            np.mean([l.get("brightness", 0) for l in late]) * 0.3
            + np.mean([l.get("saturation", 0) for l in late]) * 0.3
            + np.mean([l.get("color_entropy", 0) for l in late]) * 0.2
            + np.mean([l.get("edge_density", 0) for l in late]) * 0.2
        )
    else:
        reward_score = 0.2

    # Normalize to 0-1 range
    hook_score = min(max(hook_score * 2.0, 0), 1)
    comp_score = min(max(comp_score * 1.5, 0), 1)
    reward_score = min(max(reward_score * 1.5, 0), 1)

    return {
        "hook_score": round(hook_score, 4),
        "comprehension_score": round(comp_score, 4),
        "reward_score": round(reward_score, 4),
        "confidence": "medium",
    }
