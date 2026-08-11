"""E14.3 UA Growth Agent — 用户获取增长 Agent.

UA Agent 是多 Agent 组织中的专业 Agent，负责 UA 领域的全链路决策:

核心组件 (E14.3):
  1. analyzer: UA 指标分析 (异常检测、健康评分、趋势)
  2. diagnosis: 根因诊断引擎 (规则驱动、可解释)
  3. strategy: 增长策略生成 (诊断→策略映射)
  4. action_selector: 动作选择与执行 (优先级、风险、回滚)
  5. memory: UA 记忆系统 (决策历史、经验学习)
  6. ua_agent: UA Agent 核心 (整合所有模块)

反馈闭环 (E14.3.1):
  7. feedback: 动作结果采集 (before/after delta)
  8. evaluation: 奖励函数 + 结果评估
  9. learning: 学习引擎 + 完整反馈闭环

典型用法:
    from ua_agent import (
        UAGrowthAgent, UAMetrics, UAAnalysisResult,
        UADiagnosis, DiagnosisType, UAStrategy,
        UAActionSelector, UAMemory, GrowthRecommendation,
        create_ua_agent,
    )

    agent = create_ua_agent()
    rec = agent.analyze_metrics({
        "spend": 10000, "revenue": 13000, "roas": 1.3,
        "cpi": 2.1, "ctr": 0.8, "fatigue": 0.72,
    })
    print(rec.summary)

    # E14.3.1 反馈闭环
    result = agent.evaluate_outcome(
        action_id="act_001",
        action_type="generate_variants",
        before_metrics={"roas": 1.3, "ltv": 4.5},
        after_metrics={"roas": 1.6, "ltv": 5.2},
    )
    print(f"Reward: {result.evaluation.reward}, Improved: {result.improved}")
"""

from .analyzer import (
    UAMetrics,
    MetricAnomaly,
    MetricStatus,
    UAAnalysisResult,
    UAAnalyzer,
    DEFAULT_THRESHOLDS,
)

from .diagnosis import (
    UADiagnosis,
    DiagnosisType,
    DiagnosisSeverity,
    UADiagnosisEngine,
    DiagnosisRule,
)

from .strategy import (
    UAStrategy,
    StrategyType,
    StrategyAction,
    UAStrategyEngine,
    DIAGNOSIS_TO_STRATEGY,
)

from .action_selector import (
    UAActionSelector,
    SelectedAction,
    ActionPlan,
    ActionStatus,
    ActionRisk,
    ACTION_RISK_MAP,
    ROLLBACK_MAP,
)

from .memory import (
    UAMemory,
    UADecisionRecord,
    DecisionOutcome,
    ExperienceEntry,
)

# E14.3.1 Feedback Loop
from .feedback import (
    UAActionOutcome,
    FeedbackBatch,
    FeedbackCollector,
    create_feedback_collector,
)

from .evaluation import (
    EvaluationResult,
    EvaluationBatch,
    RewardCalculator,
    OutcomeEvaluator,
    RewardConfig,
    DEFAULT_REWARD_CONFIG,
    create_reward_calculator,
    create_outcome_evaluator,
)

from .learning import (
    LearningResult,
    FeedbackLoopResult,
    FeedbackLoopBatch,
    LearningEngine,
    FeedbackLoop,
    create_feedback_loop,
)

from .ua_agent import (
    UAGrowthAgent,
    UAAgentState,
    GrowthRecommendation,
    create_ua_agent,
)

__all__ = [
    # analyzer
    "UAMetrics",
    "MetricAnomaly",
    "MetricStatus",
    "UAAnalysisResult",
    "UAAnalyzer",
    "DEFAULT_THRESHOLDS",
    # diagnosis
    "UADiagnosis",
    "DiagnosisType",
    "DiagnosisSeverity",
    "UADiagnosisEngine",
    "DiagnosisRule",
    # strategy
    "UAStrategy",
    "StrategyType",
    "StrategyAction",
    "UAStrategyEngine",
    "DIAGNOSIS_TO_STRATEGY",
    # action_selector
    "UAActionSelector",
    "SelectedAction",
    "ActionPlan",
    "ActionStatus",
    "ActionRisk",
    "ACTION_RISK_MAP",
    "ROLLBACK_MAP",
    # memory
    "UAMemory",
    "UADecisionRecord",
    "DecisionOutcome",
    "ExperienceEntry",
    # E14.3.1 feedback
    "UAActionOutcome",
    "FeedbackBatch",
    "FeedbackCollector",
    "create_feedback_collector",
    # E14.3.1 evaluation
    "EvaluationResult",
    "EvaluationBatch",
    "RewardCalculator",
    "OutcomeEvaluator",
    "RewardConfig",
    "DEFAULT_REWARD_CONFIG",
    "create_reward_calculator",
    "create_outcome_evaluator",
    # E14.3.1 learning
    "LearningResult",
    "FeedbackLoopResult",
    "FeedbackLoopBatch",
    "LearningEngine",
    "FeedbackLoop",
    "create_feedback_loop",
    # ua_agent
    "UAGrowthAgent",
    "UAAgentState",
    "GrowthRecommendation",
    "create_ua_agent",
]