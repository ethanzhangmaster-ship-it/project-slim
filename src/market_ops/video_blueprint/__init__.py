"""Video Creative Blueprint Intelligence (V4.4)

把 V4.2.2 Decision Variant 转换成完整的视频创意设计蓝图(Video Blueprint)。
不绑定任何 AI 视频模型，输出可供人工或任意 AI 视频模型使用的制作规范。

核心模块:
- VideoDNAEngine: Video DNA 中央引擎
- BlueprintEngine: 视频蓝图核心引擎
- StoryPatternEngine: 动态故事模式引擎
- StoryboardEngine: 视频分镜生成
- ShotlistEngine: 镜头拆解
- AssetMappingEngine: 素材映射引擎
- CameraEngine: 相机规范引擎（Lens/Move Speed/Shake/Focus/Depth/Zoom）
- PacingEngine: 节奏控制
- TransitionEngine: 转场引擎
- SubtitleEngine: 字幕引擎
- MusicEngine: 音乐引擎
- EditingEngine: 剪辑规范
- PromptPackageEngine: Prompt 包引擎
- CreativeReviewEngine: 创意评审引擎
- QualityChecker: 质量检查
- BlueprintMemory: 蓝图记忆存储 (DuckDB)
- BlueprintAPI: 统一接口
- Dashboard: 生产概览

版本: 4.4.1
"""
from __future__ import annotations

from .video_dna_engine import VideoDNA, VideoDNAEngine
from .blueprint_engine import BlueprintEngine, VideoBlueprint
from .story_pattern_engine import StoryPatternEngine, StoryPattern
from .storyboard_engine import StoryboardEngine, Storyboard
from .shotlist_engine import ShotlistEngine, Shotlist
from .asset_mapping_engine import AssetMappingEngine, AssetMap
from .camera_engine import CameraEngine, CameraProfile, CameraSpec, CameraMove
from .pacing_engine import PacingEngine, PacingProfile
from .transition_engine import TransitionEngine, TransitionProfile
from .subtitle_engine import SubtitleEngine, SubtitleProfile
from .music_engine import MusicEngine, MusicProfile
from .editing_engine import EditingEngine, EditingGuide
from .prompt_package_engine import PromptPackageEngine, PromptPackageCollection
from .creative_review import CreativeReviewEngine, CreativeReview
from .quality_checker import QualityChecker, QualityReport
from .blueprint_memory import BlueprintMemory
from .blueprint_api import BlueprintAPI, get_blueprint_api, BlueprintOutput
from .dashboard import BlueprintDashboard

__all__ = [
    # DNA
    "VideoDNA",
    "VideoDNAEngine",
    # Blueprint
    "BlueprintEngine",
    "VideoBlueprint",
    # Story Pattern
    "StoryPatternEngine",
    "StoryPattern",
    # Storyboard
    "StoryboardEngine",
    "Storyboard",
    # Shotlist
    "ShotlistEngine",
    "Shotlist",
    # Asset Mapping
    "AssetMappingEngine",
    "AssetMap",
    # Camera
    "CameraEngine",
    "CameraProfile",
    "CameraSpec",
    "CameraMove",
    # Pacing
    "PacingEngine",
    "PacingProfile",
    # Transition
    "TransitionEngine",
    "TransitionProfile",
    # Subtitle
    "SubtitleEngine",
    "SubtitleProfile",
    # Music
    "MusicEngine",
    "MusicProfile",
    # Editing
    "EditingEngine",
    "EditingGuide",
    # Prompt
    "PromptPackageEngine",
    "PromptPackageCollection",
    # Review
    "CreativeReviewEngine",
    "CreativeReview",
    # Quality
    "QualityChecker",
    "QualityReport",
    # Memory
    "BlueprintMemory",
    # API
    "BlueprintAPI",
    "BlueprintOutput",
    "get_blueprint_api",
    # Dashboard
    "BlueprintDashboard",
]
__version__ = "4.4.1"
