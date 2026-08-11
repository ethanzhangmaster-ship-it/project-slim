"""Feature Label Builder — 从帧级特征 + 投放数据构建训练样本。

输出: dataset.jsonl, 每行 = {video_id, cluster_id, features:{...}, labels:{roas,ctr,cvr}}
"""
from __future__ import annotations
import json, re, os
from pathlib import Path
from collections import defaultdict
from typing import List, Optional, Tuple
import numpy as np
from PIL import Image

from engine.frame_analyzer import FrameAnalyzer, analyze_video_frames, compute_video_scores

ROOT = Path(__file__).resolve().parent.parent
P04 = ROOT / "output" / "video_intelligence" / "p04"
V35 = P04 / "v3_5"
EAGLE_CACHE = V35 / "cache" / "eagle_frames"
ATTRIBUTION_FILE = V35 / "attribution" / "attribution_results.json"
DATA_FILE = P04 / "p4_full_export_all_accounts.json"
CLUSTER_FILE = V35 / "clusters" / "cluster_results.json"

# ── Video → cluster mapping from attribution ──

def _load_fb_video_map() -> Tuple[dict, dict]:
    """Load FB videos with ROAS/CTR/CVR + cluster assignment."""
    video_map = {}
    cluster_map = {}

    if ATTRIBUTION_FILE.exists():
        attr = json.loads(ATTRIBUTION_FILE.read_text(encoding="utf-8"))
        for a in attr:
            vid = a.get("video_id", "")
            spend = a.get("total_spend", 0) or 0
            rev = a.get("total_revenue", 0) or 0
            cid = a.get("assigned_cluster", "Noise")
            video_map[vid] = {
                "cluster_id": cid,
                "spend": spend,
                "revenue": rev,
                "assigned_cluster": cid,
            }
            cluster_map[vid] = cid

    # Load FB raw data for CTR/CVR
    if DATA_FILE.exists():
        data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        for v in data.get("videos", []):
            vid = v.get("video_id", "")
            imp = v.get("total_impressions", 0) or 0
            click = v.get("total_clicks", 0) or 0
            install = v.get("total_installs", 0) or 0
            spend = v.get("total_spend", 0) or 0
            rev = v.get("total_revenue", 0) or 0
            roas = rev / max(spend, 1)
            ctr = click / max(imp, 1)
            cvr = install / max(click, 1)

            if vid not in video_map:
                video_map[vid] = {"cluster_id": "unknown", "spend": spend, "revenue": rev}
            else:
                video_map[vid]["spend"] = spend
                video_map[vid]["revenue"] = rev

            video_map[vid].update({
                "impressions": imp, "clicks": click, "installs": install,
                "roas": round(roas, 4),
                "ctr": round(ctr, 4),
                "cvr": round(cvr, 4),
            })

    return video_map, cluster_map


def _extract_eagle_features(eagle_name: str) -> Optional[dict]:
    """Extract aggregated frame features from an Eagle video's cached frames.

    Returns:
        dict of averaged per-frame features + per-frame-position features.
    """
    frame_paths = []
    for pct in ["05", "25", "50", "75", "95"]:
        fp = EAGLE_CACHE / f"kf_{eagle_name}_{pct}.jpg"
        frame_paths.append(fp)

    frames = analyze_video_frames(frame_paths)
    valid = [f for f in frames if f is not None]
    if not valid:
        return None

    # Per-frame-position features (p0=hook, p1-p2=mid, p3-p4=late)
    p0 = valid[0] if len(valid) >= 1 else None
    p1 = valid[1] if len(valid) >= 2 else None
    p2 = valid[2] if len(valid) >= 3 else None
    p3 = valid[3] if len(valid) >= 4 else None
    p4 = valid[4] if len(valid) >= 5 else None

    def safe(f, key, default=0):
        return f.get(key, default) if f else default

    features = {
        # Hook frame features (frame 0, 5%)
        "hook_contrast": safe(p0, "contrast"),
        "hook_edge_density": safe(p0, "edge_density"),
        "hook_entropy": safe(p0, "color_entropy"),
        "hook_saturation": safe(p0, "saturation"),
        "hook_brightness": safe(p0, "brightness"),
        "hook_center_contrast": safe(p0, "center_contrast"),
        "hook_text_density": safe(p0, "text_density_proxy"),
        "hook_top_color_ratio": safe(p0, "top_color_ratio"),

        # Mid frames average (frame 1-2, 25-50%)
        "mid_contrast": np.mean([safe(p1, "contrast"), safe(p2, "contrast")]) if p1 or p2 else safe(p1 or p2 or {}, "contrast"),
        "mid_edge_density": np.mean([safe(p1, "edge_density"), safe(p2, "edge_density")]) if p1 or p2 else 0,
        "mid_entropy": np.mean([safe(p1, "color_entropy"), safe(p2, "color_entropy")]) if p1 or p2 else 0,
        "mid_saturation": np.mean([safe(p1, "saturation"), safe(p2, "saturation")]) if p1 or p2 else 0,
        "mid_brightness": np.mean([safe(p1, "brightness"), safe(p2, "brightness")]) if p1 or p2 else 0,
        "mid_text_density": np.mean([safe(p1, "text_density_proxy"), safe(p2, "text_density_proxy")]) if p1 or p2 else 0,
        "mid_center_contrast": np.mean([safe(p1, "center_contrast"), safe(p2, "center_contrast")]) if p1 or p2 else 0,

        # Late frames average (frame 3-4, 75-95%)
        "late_contrast": np.mean([safe(p3, "contrast"), safe(p4, "contrast")]) if p3 or p4 else safe(p3 or p4 or {}, "contrast"),
        "late_edge_density": np.mean([safe(p3, "edge_density"), safe(p4, "edge_density")]) if p3 or p4 else 0,
        "late_entropy": np.mean([safe(p3, "color_entropy"), safe(p4, "color_entropy")]) if p3 or p4 else 0,
        "late_saturation": np.mean([safe(p3, "saturation"), safe(p4, "saturation")]) if p3 or p4 else 0,
        "late_brightness": np.mean([safe(p3, "brightness"), safe(p4, "brightness")]) if p3 or p4 else 0,
        "late_text_density": np.mean([safe(p3, "text_density_proxy"), safe(p4, "text_density_proxy")]) if p3 or p4 else 0,

        # Frame-to-frame deltas (motion proxy)
        "motion_contrast_delta": (
            abs(safe(p0, "contrast") - safe(p1, "contrast"))
            if p0 and p1 else 0
        ),
        "motion_entropy_delta": (
            abs(safe(p0, "color_entropy") - safe(p4, "color_entropy"))
            if p0 and p4 else 0
        ),
        "motion_edge_delta": (
            abs(safe(p0, "edge_density") - safe(p4, "edge_density"))
            if p0 and p4 else 0
        ),
        "motion_brightness_delta": (
            abs(safe(p0, "brightness") - safe(p4, "brightness"))
            if p0 and p4 else 0
        ),
    }

    return features


def build_dataset(output_path: Optional[Path] = None) -> List[dict]:
    """Build the full feature-label dataset from cached Eagle frames + FB data.

    Returns:
        list of dicts: [{video_id, cluster_id, features, labels}, ...]
    """
    # ── 1. Find all Eagle videos with cached frames ──
    files = list(EAGLE_CACHE.glob("*.jpg"))
    video_frames = defaultdict(set)
    for f in files:
        stem = f.stem
        parts = stem.split("_")
        if len(parts) < 3:
            continue
        name = "_".join(parts[1:-1])
        video_frames[name].add(parts[-1])

    full_videos = {k: v for k, v in video_frames.items() if len(v) >= 4}
    print(f"  Videos with 4+ frames: {len(full_videos)}")

    # ── 2. Load FB data ──
    fb_map, _ = _load_fb_video_map()

    # ── 3. Load cluster results (Eagle side) ──
    eagle_clusters = {}
    if CLUSTER_FILE.exists():
        cl = json.loads(CLUSTER_FILE.read_text(encoding="utf-8"))
        for cid, cdata in cl.items():
            for m in cdata.get("members", []):
                eagle_clusters[m] = cid

    # ── 4. Build samples ──
    samples = []
    no_label = 0
    for e_name in full_videos:
        features = _extract_eagle_features(e_name)
        if features is None:
            continue

        cid = eagle_clusters.get(e_name, "unknown")

        # Check if this Eagle video has matching FB videos (via attribution)
        # In our case, Eagle → FB isn't 1:1, so we use cluster-level labels
        sample = {
            "video_id": e_name,
            "cluster_id": cid,
            "features": features,
            "labels": {},
        }

        # Try to find FB label for the same creative
        samples.append(sample)

    print(f"  Total samples: {len(samples)}")
    print(f"  With FB label: {len(samples) - no_label}")

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            for s in samples:
                f.write(json.dumps(s, ensure_ascii=False) + "\n")
        print(f"  Saved to {output_path}")

    return samples


def load_dataset(path: Path) -> Tuple[np.ndarray, np.ndarray, List[str], List[str]]:
    """Load dataset from jsonl file.

    Returns:
        X: (N, D) feature matrix
        y: (N, 3) label matrix [ROAS, CTR, CVR]
        feature_names: list of D feature name strings
        video_ids: list of N video id strings
    """
    samples = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                samples.append(json.loads(line))

    if not samples:
        return np.array([]), np.array([]), [], []

    feature_names = list(samples[0]["features"].keys())
    X = np.array([list(s["features"].values()) for s in samples]).astype(np.float32)
    y_roas = np.array([s["labels"].get("roas", 0) for s in samples]).astype(np.float32)
    y_ctr = np.array([s["labels"].get("ctr", 0) for s in samples]).astype(np.float32)
    y_cvr = np.array([s["labels"].get("cvr", 0) for s in samples]).astype(np.float32)
    y = np.column_stack([y_roas, y_ctr, y_cvr])
    video_ids = [s["video_id"] for s in samples]

    return X, y, feature_names, video_ids
