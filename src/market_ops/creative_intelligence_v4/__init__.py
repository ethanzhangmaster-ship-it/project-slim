"""V4.0 Creative Intelligence Platform.

Facebook + Adjust + Eagle + AI 的广告素材工业化流水线。

Modules:
  - creative_repository: 统一素材存储 + metadata
  - dna: Image DNA + Video DNA 系统
  - creative_intelligence: 统一生成编排
  - generation: 图片/视频生成器
  - quality: 质量门禁
  - review: 人工评审
  - learning: 学习引擎
  - pipeline: V4.0 主流水线
"""

from .creative_repository.repository import CreativeRepository
from .creative_repository.metadata import (
    CreativeMetadata, CreativeType, CreativeStatus,
    MonetizationType, OptimizationGoal,
)
from .dna.image_dna import ImageDNA
from .dna.video_dna import VideoDNA
from .dna.dna_extractor import DNAExtractor
from .creative_intelligence.intelligence import CreativeIntelligence
from .creative_intelligence.video_planner import VideoPlanner, VideoPlan, VideoSegment
from .generation.video_generator import VideoGenerator, VideoGenerationResult
from .quality.image_quality_gate import ImageQualityV4, ImageQualityResult
from .quality.video_quality_gate import VideoQualityGate, VideoQualityResult
from .review.human_review import HumanReview, ReviewResult
from .learning.learning_engine import LearningEngine, LearningReport, LearningInsight
from .pipeline.v40_pipeline import V40Pipeline, V40PipelineResult

__all__ = [
    # Repository
    "CreativeRepository",
    "CreativeMetadata",
    "CreativeType",
    "CreativeStatus",
    "MonetizationType",
    "OptimizationGoal",
    # DNA
    "ImageDNA",
    "VideoDNA",
    "DNAExtractor",
    # Intelligence
    "CreativeIntelligence",
    "VideoPlanner",
    "VideoPlan",
    "VideoSegment",
    # Generation
    "VideoGenerator",
    "VideoGenerationResult",
    # Quality
    "ImageQualityV4",
    "ImageQualityResult",
    "VideoQualityGate",
    "VideoQualityResult",
    # Review
    "HumanReview",
    "ReviewResult",
    # Learning
    "LearningEngine",
    "LearningReport",
    "LearningInsight",
    # Pipeline
    "V40Pipeline",
    "V40PipelineResult",
]