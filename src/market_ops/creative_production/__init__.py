"""Facebook Creative Production Engine (V4.3.1)

把 Decision Variant 自动转换成完整的 Facebook 广告生产方案。
AI 视频模型只是执行器之一，同时支持 Eagle 素材复用、Unity 录屏、历史 Winner 复用、人工剪辑。

核心模块:
- CreativeDirector: 创意总监（决定为什么拍、怎么拍、拍给谁）
- CreativeScript: 广告脚本
- StoryboardEngine: 跨平台分镜
- ShotGenerator: 镜头拆解
- AssetPlanner: 素材来源规划（AI/Eagle/Unity/历史Winner/人工）
- AssetConsistency: 素材一致性（Character/UI/Theme/Color）
- CameraLanguage: 运镜语言
- MotionEngine: 动作引擎
- EditorTimeline: 剪辑时间线（Premiere/DaVinci/CapCut）
- VideoModelAdapter: 视频模型适配
- WorkflowBuilder: 统一生产工作流
- ProductionMemory: DuckDB 存储
- ProductionPipeline: 统一流程
- ProductionAPI: 统一入口
- Dashboard: 制作概览

版本: 4.3.1
"""
from __future__ import annotations

from .creative_director import CreativeDirector
from .creative_script import CreativeScriptEngine
from .storyboard_engine import StoryboardEngine
from .shot_generator import ShotGenerator
from .asset_planner import AssetPlanner
from .asset_consistency import AssetConsistency
from .camera_language import CameraLanguageEngine
from .motion_engine import MotionEngine
from .editor_timeline import EditorTimeline
from .video_model_adapter import VideoModelAdapter
from .workflow_builder import WorkflowBuilder
from .production_memory import ProductionMemory
from .production_pipeline import ProductionPipeline
from .production_api import CreativeProductionAPI, get_production_api
from .dashboard import ProductionDashboard

__all__ = [
    "CreativeDirector",
    "CreativeScriptEngine",
    "StoryboardEngine",
    "ShotGenerator",
    "AssetPlanner",
    "AssetConsistency",
    "CameraLanguageEngine",
    "MotionEngine",
    "EditorTimeline",
    "VideoModelAdapter",
    "WorkflowBuilder",
    "ProductionMemory",
    "ProductionPipeline",
    "CreativeProductionAPI",
    "get_production_api",
    "ProductionDashboard",
]
__version__ = "4.3.1"