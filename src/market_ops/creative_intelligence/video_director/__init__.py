"""Video Creative Director - AI 视频创意导演模块

将 Winner Creative DNA + 广告表现数据 + 游戏玩法信息
转换为可执行的视频广告脚本、分镜、ComfyUI Prompt。

Usage:
    from src.market_ops.creative_intelligence.video_director import VideoDirector

    director = VideoDirector()
    result = director.direct(
        winner_dna={...},
        game_info={...},
        ad_goal={...},
    )
    # result -> VideoCreativePlan (含 storyboard + comfyui prompt + workflow)
"""
from __future__ import annotations

from .director_agent import VideoDirector
from .models import (
    WinnerDNA,
    GameInfo,
    AdGoal,
    VideoCreativePlan,
    StoryboardScene,
    ComfyUIWorkflow,
)

__all__ = [
    "VideoDirector",
    "WinnerDNA",
    "GameInfo",
    "AdGoal",
    "VideoCreativePlan",
    "StoryboardScene",
    "ComfyUIWorkflow",
]
