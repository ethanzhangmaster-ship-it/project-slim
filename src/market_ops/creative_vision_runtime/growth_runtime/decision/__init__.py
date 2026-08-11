"""E13.3 Growth Decision Engine — 增长决策引擎.

从数据洞察到决策执行的核心层，实现:
  - 数据 → 洞察 (GrowthIntelligence)
  - 洞察 → 机会 (OpportunityDetector)
  - 机会 → 排名 (CreativeRanker)
  - 机会 → 决策 (ActionMapper)
  - 决策 → 报告 (GrowthDecisionEngine)

模块:
  - models:                决策数据模型
  - intelligence:          E13.3.1 增长洞察分析
  - opportunity_detector:  E13.3.2 机会发现引擎
  - creative_ranker:       E13.3.3 统一评分排序
  - decision_engine:       E13.3.4 核心决策编排器
  - action_mapper:         E13.3.5 机会到决策映射
  - confidence:            E13.3.6 置信度与风险评估
  - pattern_retriever:     E13.5  模式检索器 (Pattern → Decision)
  - decision_enhancer:     E13.5  决策增强器 (Pattern → Decision Bridge)
"""

from .action_mapper import ActionMapper
from .confidence import ConfidenceCalculator, RiskAssessor
from .creative_ranker import CreativeRanker
from .decision_engine import GrowthDecisionEngine
from .intelligence import GrowthIntelligence
from .models import (
    ActionType,
    BudgetAction,
    CreativeRanking,
    DecisionAction,
    DecisionConfidence,
    DecisionReport,
    DecisionResult,
    GrowthInsight,
    GrowthOpportunity,
    InsightType,
    OpportunitySeverity,
)
from .opportunity_detector import OpportunityDetector
from .pattern_retriever import (
    PatternRecommendation,
    PatternRetriever,
    RetrievalContext,
    RetrievalResult,
)
from .decision_enhancer import DecisionEnhancer, EnhancementReport
from .decision_memory_retriever import (
    DecisionContext,
    DecisionHistoryResult,
    DecisionMemoryRetriever,
    DecisionRecord,
)

__all__ = [
    # Enums
    "InsightType",
    "ActionType",
    "DecisionConfidence",
    "OpportunitySeverity",
    # Models
    "GrowthInsight",
    "GrowthOpportunity",
    "CreativeRanking",
    "BudgetAction",
    "DecisionAction",
    "DecisionReport",
    "DecisionResult",
    # E13.3.1
    "GrowthIntelligence",
    # E13.3.2
    "OpportunityDetector",
    # E13.3.3
    "CreativeRanker",
    # E13.3.4
    "GrowthDecisionEngine",
    # E13.3.5
    "ActionMapper",
    # E13.3.6
    "ConfidenceCalculator",
    "RiskAssessor",
    # E13.5 Pattern Retrieval
    "PatternRetriever",
    "RetrievalContext",
    "RetrievalResult",
    "PatternRecommendation",
    "DecisionEnhancer",
    "EnhancementReport",
    # E13.6.5 Decision Memory Retrieval
    "DecisionMemoryRetriever",
    "DecisionContext",
    "DecisionRecord",
    "DecisionHistoryResult",
]