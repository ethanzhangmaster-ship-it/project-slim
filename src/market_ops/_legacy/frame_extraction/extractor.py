"""E11.3.2 — Video Frame Extractor。

将 VisionAsset 转换为 FrameSequence：
  VisionAsset.video_path
    → FrameSampler (6 帧采样)
    → FrameAnalyzer (帧级视觉特征)
    → compute_video_scores (视频级评分)
    → FrameSequence

复用已有基础设施：
  - creative_remix_engine/visual_intelligence/frame_sampler.py  FrameSampler
  - engine/frame_analyzer.py  FrameAnalyzer, analyze_video_frames(), compute_video_scores

不做 AI 分析（CLIP/OCR/目标检测），只做结构级视觉特征提取。

Usage:
    extractor = VideoFrameExtractor(cache_dir="data/frames")
    sequence = extractor.extract(vision_asset)
    # → FrameSequence with 6 frames + video scores
"""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path
from typing import Any

from creative_remix_engine.visual_intelligence.frame_sampler import FrameSampler
from engine.frame_analyzer import (
    FrameAnalyzer,
    analyze_video_frames,
    compute_video_scores,
)

from ..vision_asset.models import VisionAsset, VisionAssetStatus
from .models import VisionFrame, FrameSequence

logger = logging.getLogger(__name__)


class VideoFrameExtractor:
    """VisionAsset → FrameSequence 转换器。

    复用 FrameSampler + FrameAnalyzer，不做重复实现。

    Attributes:
        cache_dir:      帧缓存目录
        sample_points:  采样点比例（默认 6 帧: 0%, 20%, 40%, 60%, 80%, 100%）
    """

    SAMPLE_POINTS = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]

    def __init__(
        self,
        cache_dir: str = "data/frames",
        skip_if_cached: bool = True,
    ) -> None:
        self._cache_dir = Path(cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._sampler = FrameSampler(cache_dir=self._cache_dir)
        self._analyzer = FrameAnalyzer()
        self._skip_if_cached = skip_if_cached

        self._extracted_count: int = 0
        self._failed_count: int = 0

    # ── Public API ───────────────────────────────────────

    def extract(self, asset: VisionAsset, force: bool = False) -> FrameSequence | None:
        """从 VisionAsset 提取帧序列。

        Args:
            asset: VisionAsset 对象
            force: 是否强制重新提取（忽略缓存）

        Returns:
            FrameSequence 或 None（提取失败）
        """
        video_path = Path(asset.video_path)

        # 文件检查
        if not video_path.exists():
            logger.warning(f"VideoFrameExtractor: file not found: {video_path}")
            self._failed_count += 1
            return None

        # 获取视频时长
        duration = self._get_duration(video_path)
        if duration <= 0:
            logger.warning(f"VideoFrameExtractor: invalid duration: {video_path}")
            self._failed_count += 1
            return None

        # 提取帧
        try:
            frame_paths = self._sampler.sample(video_path, force=force)
        except Exception as e:
            logger.error(f"VideoFrameExtractor: frame sampling failed: {e}")
            self._failed_count += 1
            return None

        if not frame_paths:
            logger.warning(f"VideoFrameExtractor: no frames extracted: {video_path}")
            self._failed_count += 1
            return None

        # 分析帧特征
        frame_features = analyze_video_frames(frame_paths)

        # 构建 VisionFrame 列表
        frames: list[VisionFrame] = []
        for i, (fp, features) in enumerate(zip(frame_paths, frame_features)):
            ratio = self.SAMPLE_POINTS[i] if i < len(self.SAMPLE_POINTS) else 0.0
            ts = duration * ratio

            if features is not None:
                frame = VisionFrame(
                    frame_index=i,
                    frame_path=str(fp),
                    timestamp_sec=round(ts, 1),
                    ratio=ratio,
                    brightness=features.get("brightness", 0.0),
                    contrast=features.get("contrast", 0.0),
                    edge_density=features.get("edge_density", 0.0),
                    text_density=features.get("text_density_proxy", 0.0),
                    color_entropy=features.get("color_entropy", 0.0),
                    saturation=features.get("saturation", 0.0),
                    top_color_ratio=features.get("top_color_ratio", 0.0),
                    center_brightness=features.get("center_brightness", 0.0),
                    center_contrast=features.get("center_contrast", 0.0),
                )
            else:
                frame = VisionFrame(
                    frame_index=i,
                    frame_path=str(fp),
                    timestamp_sec=round(ts, 1),
                    ratio=ratio,
                )

            frames.append(frame)

        # 计算视频级评分
        scores = compute_video_scores(frame_features)

        # 获取分辨率
        resolution = self._get_resolution(frame_paths)

        # 构建 FrameSequence
        sequence = FrameSequence(
            creative_id=asset.creative_id,
            creative_asset_id=asset.creative_asset_id,
            video_path=str(video_path),
            eagle_filename=asset.eagle_filename,
            frames=frames,
            duration_sec=round(duration, 1),
            resolution=resolution,
            frame_count=len(frames),
            hook_score=scores.get("hook_score", 0.0),
            comprehension_score=scores.get("comprehension_score", 0.0),
            reward_score=scores.get("reward_score", 0.0),
            status="extracted",
        )

        self._extracted_count += 1
        logger.info(
            f"VideoFrameExtractor: {asset.creative_asset_id} "
            f"→ {len(frames)} frames, hook={sequence.hook_score:.2f}"
        )

        return sequence

    def extract_batch(
        self,
        assets: list[VisionAsset],
        force: bool = False,
    ) -> list[FrameSequence]:
        """批量提取帧序列。

        Args:
            assets: VisionAsset 列表
            force:  是否强制重新提取

        Returns:
            FrameSequence 列表（跳过失败的）
        """
        sequences: list[FrameSequence] = []
        for asset in assets:
            seq = self.extract(asset, force=force)
            if seq is not None:
                sequences.append(seq)

        logger.info(
            f"VideoFrameExtractor: batch done: "
            f"{len(sequences)}/{len(assets)} extracted"
        )
        return sequences

    def extract_winners(
        self,
        assets: list[VisionAsset],
        force: bool = False,
    ) -> list[FrameSequence]:
        """仅提取 WINNER 素材的帧序列。

        Args:
            assets: VisionAsset 列表
            force:  是否强制重新提取

        Returns:
            WINNER FrameSequence 列表
        """
        winners = [a for a in assets if a.is_winner]
        return self.extract_batch(winners, force=force)

    # ── Query ────────────────────────────────────────────

    def is_cached(self, video_path: str) -> bool:
        return self._sampler.is_cached(Path(video_path))

    def get_frame_dir(self, video_path: str) -> Path:
        return self._sampler.get_frame_dir(Path(video_path))

    @property
    def extracted_count(self) -> int:
        return self._extracted_count

    @property
    def failed_count(self) -> int:
        return self._failed_count

    # ── Internal ────────────────────────────────────────

    @staticmethod
    def _get_duration(video_path: Path) -> float:
        """获取视频时长（秒）。"""
        try:
            r = subprocess.run([
                "ffprobe", "-v", "error", "-select_streams", "v:0",
                "-show_entries", "stream=duration",
                "-of", "json", str(video_path)
            ], capture_output=True, text=True, timeout=10)
            s = json.loads(r.stdout).get("streams", [{}])[0]
            return float(s.get("duration", 0) or 0)
        except Exception:
            return 0.0

    @staticmethod
    def _get_resolution(frame_paths: list[Path]) -> tuple[int, int]:
        """获取视频分辨率。"""
        try:
            from PIL import Image
            for fp in frame_paths:
                if fp.exists() and fp.stat().st_size > 0:
                    img = Image.open(fp)
                    return img.size  # (width, height)
        except Exception:
            pass
        return (0, 0)

    def __repr__(self) -> str:
        return (
            f"VideoFrameExtractor(cache={self._cache_dir}, "
            f"extracted={self._extracted_count}, "
            f"failed={self._failed_count})"
        )