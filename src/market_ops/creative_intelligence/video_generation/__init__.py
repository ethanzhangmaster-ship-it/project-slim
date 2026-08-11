"""Video Generation Validation Layer

将 Video Creative Director 与本地 ComfyUI 连接，实现从 Winner DNA 到可投放视频素材的完整管线。

Usage:
    from market_ops.creative_intelligence.video_generation import GenerationPipeline

    pipeline = GenerationPipeline()
    result = pipeline.run(winner_dna, game_info, ad_goal)
"""
from __future__ import annotations

from .generation_pipeline import GenerationPipeline
from .comfyui_client import ComfyUIClient
from .models import GenerationResult, VideoScore

__all__ = [
    "GenerationPipeline",
    "ComfyUIClient",
    "GenerationResult",
    "VideoScore",
]
