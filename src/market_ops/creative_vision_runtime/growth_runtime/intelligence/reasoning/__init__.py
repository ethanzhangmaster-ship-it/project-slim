"""E15.2.4 Execution Reasoning Layer — 执行推理层.

Autonomous Execution Intelligence 的最后一个认知层，提供:
  - 假设生成: 基于观测数据解释当前状态
  - 诊断分析: 分析执行结果成败原因
  - 推理引擎: 整合所有认知能力形成决策
  - 决策追踪: 记录完整推理链路
  - 可解释性: 生成人类可读解释

连接:
  - E15.2.1 Planner → 读取执行计划
  - E15.2.2 Risk → 读取风险评估
  - E15.2.3 Selection → 读取选中动作
  - E15.0.11 Observability → 输出追踪数据
  - E13.4 Pattern Memory → 输出推理经验
"""

from .decision_trace import DecisionTraceBuilder
from .diagnosis import DiagnosisEngine
from .explanation import ExecutionExplainer
from .hypothesis import (
    AUDIENCE_SATURATION_RULE,
    BUDGET_INSUFFICIENT_RULE,
    CREATIVE_FATIGUE_RULE,
    DEFAULT_RULES,
    MARKET_SHIFT_RULE,
    SCALING_OPPORTUNITY_RULE,
    UNDERPERFORMING_CREATIVE_RULE,
    HypothesisEngine,
)
from .models import (
    Constraint,
    ConstraintType,
    DiagnosisResult,
    DiagnosisStatus,
    ExecutionAttempt,
    Hypothesis,
    Observation,
    ObservationTrend,
    ReasoningContext,
    ReasoningDecision,
    ReasoningResult,
    ReasoningStep,
    ReasoningTrace,
)
from .reasoning_engine import ExecutionReasoningEngine

__all__ = [
    # Enums
    "DiagnosisStatus",
    "ReasoningDecision",
    "ObservationTrend",
    "ConstraintType",
    # Models
    "Observation",
    "Constraint",
    "ExecutionAttempt",
    "ReasoningContext",
    "Hypothesis",
    "DiagnosisResult",
    "ReasoningStep",
    "ReasoningTrace",
    "ReasoningResult",
    # Hypothesis
    "HypothesisEngine",
    "DEFAULT_RULES",
    "CREATIVE_FATIGUE_RULE",
    "AUDIENCE_SATURATION_RULE",
    "BUDGET_INSUFFICIENT_RULE",
    "UNDERPERFORMING_CREATIVE_RULE",
    "SCALING_OPPORTUNITY_RULE",
    "MARKET_SHIFT_RULE",
    # Diagnosis
    "DiagnosisEngine",
    # Decision Trace
    "DecisionTraceBuilder",
    # Reasoning Engine
    "ExecutionReasoningEngine",
    # Explanation
    "ExecutionExplainer",
]