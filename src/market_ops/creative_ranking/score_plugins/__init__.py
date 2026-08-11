"""Creative Ranking Scorer Plugins

Scorer Plugin 架构:
- BaseScorer: 所有评分器的基类
- RuleScorer: 基于规则的评分（当前实现）
- LLMScorer: 基于大模型的评分（预留）
- VisionScorer: 基于视觉模型的评分（预留）
- HistoryScorer: 基于历史投放数据的评分（预留）

每个 Scorer 返回:
    score: float (0-100)
    breakdown: dict 评分明细
    recommendations: list[str] 推荐理由
    risks: list[str] 风险分析
"""
from .base_scorer import BaseScorer, ScoreResult
from .similarity_scorer import SimilarityScorer
from .hook_scorer import HookScorer
from .readability_scorer import ReadabilityScorer
from .novelty_scorer import NoveltyScorer
from .fatigue_scorer import FatigueScorer
from .brand_scorer import BrandScorer
from .ai_risk_scorer import AIRiskScorer
from .gameplay_scorer import GameplayScorer
from .policy_scorer import PolicyScorer

__all__ = [
    "BaseScorer",
    "ScoreResult",
    "SimilarityScorer",
    "HookScorer",
    "ReadabilityScorer",
    "NoveltyScorer",
    "FatigueScorer",
    "BrandScorer",
    "AIRiskScorer",
    "GameplayScorer",
    "PolicyScorer",
]
