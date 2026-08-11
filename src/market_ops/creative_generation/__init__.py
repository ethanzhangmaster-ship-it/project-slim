"""Facebook Creative Generation Engine (V4.3)

将 V4.2.2 Decision Portfolio 转换为可直接投放的 AI 创意。

核心模块:
- PromptEngine: 从 Decision Variant 生成 Master Prompt
- PromptTemplateLibrary: 多 Hook 类型模板库
- PromptOptimizer: 多版本 Prompt 优化 (A/B/C/D)
- NegativePromptEngine: 自动生成负面提示词
- ModelAdapter: 多 AI 模型适配
- StoryboardGenerator: 视频分镜生成
- ImageTaskBuilder: 构建可执行 AI 任务
- QualityValidator: 质量验证
- PromptMemory: Prompt 表现记忆
- GenerationPipeline: 统一生成流程
- GenerationAPI: 统一入口

版本: 4.3.0
"""
from __future__ import annotations

from .generation_api import GenerationAPI, get_generation_api
from .generation_pipeline import GenerationPipeline
from .image_task_builder import ImageTaskBuilder
from .model_adapter import ModelAdapter
from .negative_prompt import NegativePromptEngine
from .prompt_engine import PromptEngine
from .prompt_memory import PromptMemory
from .prompt_optimizer import PromptOptimizer
from .prompt_templates import PromptTemplateLibrary
from .quality_validator import QualityValidator
from .storyboard_generator import StoryboardGenerator

__all__ = [
    "PromptEngine",
    "PromptTemplateLibrary",
    "PromptOptimizer",
    "NegativePromptEngine",
    "ModelAdapter",
    "StoryboardGenerator",
    "ImageTaskBuilder",
    "QualityValidator",
    "PromptMemory",
    "GenerationPipeline",
    "GenerationAPI",
    "get_generation_api",
]
__version__ = "4.3.0"
