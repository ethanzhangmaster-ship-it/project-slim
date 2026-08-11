"""Video Intelligence Analyzer - AI 视频理解与评估模块

对 ComfyUI 生成的视频进行自动分析，判断是否具有买量价值。

Usage:
    from market_ops.creative_intelligence.video_analysis import AnalysisPipeline

    pipeline = AnalysisPipeline()
    report = pipeline.analyze("video.mp4", game_type="merge")
"""
from __future__ import annotations

from .analysis_pipeline import AnalysisPipeline
from .models import VideoAnalysisReport

__all__ = [
    "AnalysisPipeline",
    "VideoAnalysisReport",
]
