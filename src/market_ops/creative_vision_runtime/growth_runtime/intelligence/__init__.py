"""E13.5 Growth Intelligence Layer — 决策智能层.

在 Growth Memory Kernel 之上构建自主决策能力，将 Reality Data + Memory Knowledge
融合为可执行的自主决策。

模块:
  E13.5.1 Intelligence Models: 决策智能数据模型
  E13.5.2 Opportunity Intelligence Engine: 现实洞察 → 增长机会
  E13.5.3 Strategy Selector: 连接 Strategy Memory 进行策略匹配
  E13.5.4 Risk Controller: 连接 Failure Memory 进行风险控制
  E13.5.5 Decision Engine: 机会 → 策略 → 风险 → 决策
  E13.5.6 Autonomous Runtime: 自主运行循环
"""

from .intelligence_models import (
    # Enums
    DecisionPriority,
    DecisionStatus,
    OpportunitySource,
    OpportunityType,
    RiskLevel,
    # Models
    CurrentMetrics,
    DecisionAction,
    DecisionContext,
    DecisionRecord,
    DecisionResult,
    ExpectedImpact,
    GrowthDecision,
    GrowthOpportunity,
    MemoryContext,
    SignalSummary,
    StrategyCandidate,
    StrategySelection,
)
from .opportunity_intelligence import OpportunityIntelligenceEngine
from .opportunity_ranker import OpportunityRanker
from .opportunity_rules import (
    AudienceExpansionRule,
    BudgetOptimizationRule,
    CreativeFatigueRule,
    ExperimentLaunchRule,
    MonetizationOptimizationRule,
    OpportunityRule,
    RiskMitigationRule,
    RuleEngine,
    ScalingOpportunityRule,
)
from .risk_controller import RiskCalculator, RiskController
from .risk_models import (
    RiskAssessment,
    RiskContext,
    RiskDecision,
    RiskLevel as E1354RiskLevel,
    RiskPolicy,
)
from .risk_rules import (
    BaseRiskRule,
    BudgetAggressionRule,
    HighImpactRule,
    HistoricalFailureCheckRule,
    LowConfidenceRule,
    NewProductRule,
    RiskRuleEngine,
    RiskRuleResult,
)
from .strategy_matcher import StrategyMatcher
from .strategy_ranker import StrategyRanker
from .strategy_selector import StrategySelector

# E13.5.5 Decision Engine
from .decision import (
    DecisionEngine,
    DecisionExplainer,
    DecisionExperience,
    DecisionInput,
    DecisionMemory,
    DecisionOutput,
    DecisionPlan,
    DecisionScore,
    DecisionScorer,
    DecisionType,
)

__all__ = [
    # E13.5.1 Enums
    "OpportunityType",
    "OpportunitySource",
    "DecisionStatus",
    "RiskLevel",
    "DecisionPriority",
    # E13.5.1 Models
    "CurrentMetrics",
    "SignalSummary",
    "MemoryContext",
    "DecisionContext",
    "ExpectedImpact",
    "GrowthOpportunity",
    "DecisionAction",
    "GrowthDecision",
    "DecisionResult",
    "DecisionRecord",
    # E13.5.2 Rules
    "OpportunityRule",
    "CreativeFatigueRule",
    "ScalingOpportunityRule",
    "BudgetOptimizationRule",
    "MonetizationOptimizationRule",
    "AudienceExpansionRule",
    "RiskMitigationRule",
    "ExperimentLaunchRule",
    "RuleEngine",
    # E13.5.2 Ranker
    "OpportunityRanker",
    # E13.5.2 Engine
    "OpportunityIntelligenceEngine",
    # E13.5.3 Models
    "StrategyCandidate",
    "StrategySelection",
    # E13.5.3 Core
    "StrategyMatcher",
    "StrategyRanker",
    "StrategySelector",
    # E13.5.4 Risk Models
    "E1354RiskLevel",
    "RiskDecision",
    "RiskAssessment",
    "RiskPolicy",
    "RiskContext",
    # E13.5.4 Risk Rules
    "RiskRuleResult",
    "BaseRiskRule",
    "BudgetAggressionRule",
    "HistoricalFailureCheckRule",
    "LowConfidenceRule",
    "NewProductRule",
    "HighImpactRule",
    "RiskRuleEngine",
    # E13.5.4 Risk Controller
    "RiskCalculator",
    "RiskController",
    # E13.5.5 Decision Engine
    "DecisionType",
    "DecisionScore",
    "DecisionPlan",
    "DecisionOutput",
    "DecisionInput",
    "DecisionScorer",
    "DecisionExplainer",
    "DecisionEngine",
    "DecisionExperience",
    "DecisionMemory",
]