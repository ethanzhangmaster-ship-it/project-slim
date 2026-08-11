"""V3.8 Frame Feature Extractor — 关键帧特征重建。

从 Eagle 缓存的 5 帧关键帧中提取：
  - Hook: first_frame_contrast, subject_presence_score, center_focus_score
  - Comprehension: motion_change_0_3s, text_density_0_3s, visual_entropy_delta
  - Reward: reward_visual_surge, brightness_spike, contrast_jump

所有特征以帧为单位，可复现。
不使用 archetype/pattern 标签。
"""
from __future__ import annotations
from pathlib import Path
from typing import List, Optional, Dict
import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
V35 = ROOT / "output" / "video_intelligence" / "p04" / "v3_5"
EAGLE_CACHE = V35 / "cache" / "eagle_frames"


def _load_frame(path: Path) -> Optional[Image.Image]:
    if path.exists() and path.stat().st_size > 1024:
        try:
            return Image.open(path)
        except Exception:
            pass
    return None


def extract_frame_features(eagle_name: str) -> Optional[Dict]:
    """提取 9 维帧级特征，基于 5 帧关键帧。

    帧位置:
      p0 = 5%  (Hook)
      p1 = 25% (Comprehension start)
      p2 = 50% (Comprehension mid)
      p3 = 75% (Reward)
      p4 = 95% (Reward end)
    """
    frame_paths = []
    for pct in ["05", "25", "50", "75", "95"]:
        frame_paths.append(EAGLE_CACHE / f"kf_{eagle_name}_{pct}.jpg")

    imgs = [_load_frame(p) for p in frame_paths]
    valid = [i for i in imgs if i is not None]

    if len(valid) < 2:
        return None

    # 所有帧分析
    analyzed = [_analyze_single_frame(img) for img in valid]

    # ── Hook (0-1s proxy: frame 0) ──
    p0 = analyzed[0]
    first_frame_contrast = p0["contrast"]
    subject_presence_score = p0["center_contrast"] * 0.6 + p0["edge_density"] * 0.4
    center_focus_score = p0["center_contrast"] / max(p0["contrast"], 1e-6)

    # ── Comprehension (frame 0→1, 0→2 motion + text) ──
    p1 = analyzed[1] if len(analyzed) > 1 else p0
    motion_change_0_3s = abs(p0["contrast"] - p1["contrast"]) + abs(p0["brightness"] - p1["brightness"])
    text_density_0_3s = max(p0["text_density_proxy"], p1["text_density_proxy"])
    visual_entropy_delta = p0["color_entropy"] - p1["color_entropy"] if len(analyzed) > 1 else 0

    # ── Reward (frame 3→4 surge) ──
    if len(analyzed) >= 5:
        p3 = analyzed[3]
        p4 = analyzed[4]
        reward_visual_surge = max(0, p4["saturation"] - p3["saturation"]) + max(0, p4["brightness"] - p3["brightness"])
        brightness_spike = max(0, p4["brightness"] - p3["brightness"])
        contrast_jump = max(0, p4["contrast"] - p3["contrast"])
    elif len(analyzed) >= 2:
        p_last = analyzed[-1]
        reward_visual_surge = p_last["saturation"] * 0.5
        brightness_spike = p_last["brightness"] * 0.3
        contrast_jump = p_last["contrast"] * 0.2
    else:
        reward_visual_surge = 0
        brightness_spike = 0
        contrast_jump = 0

    return {
        # Hook
        "first_frame_contrast": round(first_frame_contrast, 4),
        "subject_presence_score": round(subject_presence_score, 4),
        "center_focus_score": round(center_focus_score, 4),
        # Comprehension
        "motion_change_0_3s": round(motion_change_0_3s, 4),
        "text_density_0_3s": round(text_density_0_3s, 4),
        "visual_entropy_delta": round(visual_entropy_delta, 4),
        # Reward
        "reward_visual_surge": round(reward_visual_surge, 4),
        "brightness_spike": round(brightness_spike, 4),
        "contrast_jump": round(contrast_jump, 4),
    }


def _analyze_single_frame(img: Image.Image) -> Dict:
    """提取单帧 8 维特征, 用于上层计算。"""
    arr = np.array(img.convert("RGB"))
    gray = np.array(img.convert("L"))
    h, w = arr.shape[:2]

    brightness = float(gray.mean()) / 255.0
    contrast = float(gray.std()) / 255.0

    edges = img.convert("L").filter(ImageFilter.FIND_EDGES)
    edge_density = float((np.array(edges) > 30).sum()) / (h * w)

    horiz = np.abs(np.diff(gray.astype(np.float32), axis=1))
    text_density = float((horiz > 40).sum()) / ((h * (w - 1)))

    bins = 16
    rb = np.clip(arr[:, :, 0] // 16, 0, bins - 1).astype(int)
    gb = np.clip(arr[:, :, 1] // 16, 0, bins - 1).astype(int)
    bb = np.clip(arr[:, :, 2] // 16, 0, bins - 1).astype(int)
    idx = rb * bins * bins + gb * bins + bb
    hist = np.bincount(idx.ravel(), minlength=bins ** 3).astype(np.float32)
    hist = hist / hist.sum()
    nonzero = hist[hist > 0]
    entropy = float(-(nonzero * np.log2(nonzero)).sum())

    r, g, b = arr[:, :, 0].astype(np.float32), arr[:, :, 1].astype(np.float32), arr[:, :, 2].astype(np.float32)
    mx = np.maximum(np.maximum(r, g), b)
    mn = np.minimum(np.minimum(r, g), b)
    denom = np.where(mx > 0, mx, 1.0)
    saturation = float(((mx - mn) / denom).mean())

    ch, cw = int(h * 0.3), int(w * 0.3)
    center = gray[ch:h - ch, cw:w - cw]
    center_contrast = float(center.std()) / 255.0

    return {
        "brightness": brightness,
        "contrast": contrast,
        "edge_density": edge_density,
        "text_density_proxy": text_density,
        "color_entropy": entropy,
        "saturation": saturation,
        "center_contrast": center_contrast,
    }


def build_dataset(eagle_names: List[str]) -> List[Dict]:
    """构建所有可用视频的统一数据结构。"""
    samples = []
    for name in eagle_names:
        feats = extract_frame_features(name)
        if feats is None:
            continue
        samples.append({
            "video_id": name,
            "roas": 0.0,
            "frame_features": feats,
            "meta": {"archetype": "", "cluster_id": ""},
        })
    return samples
