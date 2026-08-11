"""Winner Intelligence Module V3.8 — Creative Performance Intelligence Layer

从"视觉质量"转向"买量价值"。

Modules:
- winner_database: Winner 数据库（真实买量数据存储）
- winner_dna_extractor: 从视频提取多维 Winner DNA
- creative_value_predictor: Buying Score 预测引擎
- dna_similarity: DNA 相似度计算引擎
- archetype_ranker: Performance Archetype 发现与分类
- performance_quality_gate: 基于买量价值的 S+/S/A/B/Reject 分级
- smart_mutation_engine: 基于 Winner DNA 指导的智能变异
- ua_feedback_loop: UA 数据反馈闭环
"""

from .winner_database import WinnerDatabase
from .winner_dna_extractor import WinnerDNAExtractor
from .creative_value_predictor import CreativeValuePredictor
from .dna_similarity import DNASimilarityEngine, SimilarityResult
from .archetype_ranker import ArchetypeDiscoveryEngine, PerformanceArchetype
from .performance_quality_gate import PerformanceQualityGate, PerformanceGrade
from .smart_mutation_engine import SmartMutationEngine, MutationSuggestion
from .ua_feedback_loop import UAFeedbackLoop, FeedbackResult

__all__ = [
    "WinnerDatabase",
    "WinnerDNAExtractor",
    "CreativeValuePredictor",
    "DNASimilarityEngine",
    "SimilarityResult",
    "ArchetypeDiscoveryEngine",
    "PerformanceArchetype",
    "PerformanceQualityGate",
    "PerformanceGrade",
    "SmartMutationEngine",
    "MutationSuggestion",
    "UAFeedbackLoop",
    "FeedbackResult",
]
