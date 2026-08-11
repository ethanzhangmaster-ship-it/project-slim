"""E15.3.5 Continuous Learning Loop — 持续学习循环.

Autonomous Operator 的长期进化层，实现从经验中持续积累知识的能力。

组件:
    - models:                 核心数据模型
    - experience_collector:   经验收集
    - experience_evaluator:   经验质量评估
    - knowledge_extractor:    知识提取
    - pattern_evolution:      模式生命周期管理
    - strategy_learner:       策略学习
    - learning_engine:        持续学习核心引擎

用法:
    from growth_runtime.intelligence.learning import ContinuousLearningEngine

    engine = ContinuousLearningEngine()
    engine.collect(action="creative_refresh", context={...}, result={...}, reward=0.74)
    result = engine.process()
    feedback = engine.generate_model_feedback()
"""

from .experience_collector import ExperienceCollector
from .experience_evaluator import ExperienceEvaluator
from .knowledge_extractor import KnowledgeExtractor
from .learning_engine import ContinuousLearningEngine, ModelImprovementFeedback
from .models import (
    ExperienceQuality,
    ExperienceQualityLevel,
    InsightType,
    LearnedPattern,
    LearningExperience,
    LearningInsight,
    LearningResult,
    PatternEvolution,
    PatternStatus,
    StrategyRecommendation,
)
from .pattern_evolution import PatternEvolutionEngine, VALID_TRANSITIONS
from .strategy_learner import StrategyLearner

__all__ = [
    # Engines
    "ContinuousLearningEngine",
    "ModelImprovementFeedback",
    # Components
    "ExperienceCollector",
    "ExperienceEvaluator",
    "KnowledgeExtractor",
    "PatternEvolutionEngine",
    "StrategyLearner",
    # Models
    "ExperienceQuality",
    "ExperienceQualityLevel",
    "InsightType",
    "LearnedPattern",
    "LearningExperience",
    "LearningInsight",
    "LearningResult",
    "PatternEvolution",
    "PatternStatus",
    "StrategyRecommendation",
    # Rules
    "VALID_TRANSITIONS",
]