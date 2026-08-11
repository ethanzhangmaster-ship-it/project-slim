"""E11.3.2 — Frame Extraction Layer。

VisionAsset.video_path → FrameSequence (6 帧 + 视频级评分)。
"""
from .models import VisionFrame, FrameSequence
from .extractor import VideoFrameExtractor

__all__ = [
    "VisionFrame",
    "FrameSequence",
    "VideoFrameExtractor",
]