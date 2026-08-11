"""E13.5.5 Decision Models — 决策引擎数据模型.

将 Opportunity + Strategy + Risk Assessment 汇聚成最终 Autonomous Growth Decision。

核心模型:
  - DecisionType: 决策类型枚举 (EXECUTE/TEST/HOLD/BLOCK/ESCALATE)
  - DecisionScore: 策略评分 (reward × confidence × (1-risk))
  - DecisionPlan: 决策执行计划 (动作 + 预算 + 时间线)
  - DecisionOutput: 决策引擎最终输出 (Generic wrapper)
  - DecisionInput: 决策引擎输入上下文

连接:
  E13.5.2 Opportunity → E13.5.3 Strategy → E13.5.4 Risk → E13.5.5 Decision
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


# ═══════════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════════


class DecisionType(str, Enum):
    """决策类型 — 决定对该策略采取什么行动.

    | Type     | 说明         |
    |----------|-------------|
    | EXECUTE  | 直接执行      |
    | TEST     | 小预算实验     |
    | HOLD     | 保持观察      |
    | BLOCK    | 禁止执行      |
    | ESCALATE | 需要人工确认   |
    """
    EXECUTE = "execute"
    TEST = "test"
    HOLD = "hold"
    BLOCK = "block"
    ESCALATE = "escalate"


# ═══════════════════════════════════════════════════════════════
# Decision Score
# ═══════════════════════════════════════════════════════════════


@dataclass
class DecisionScore:
    """策略评分 — 综合策略价值、置信度与风险.

    公式:
      final_score = strategy_reward × confidence × (1 - risk_score)

    Attributes:
        strategy_id: 策略 ID
        strategy_name: 策略名称
        strategy_reward: 策略历史成功率 (expected reward) [0, 1]
        confidence: 策略置信度 [0, 1]
        risk_score: 风险评分 [0, 1]
        risk_adjusted_reward: 风险调整后收益
        final_score: 最终综合评分 [0, 1]
        rank: 排名 (1-based)
    """
    strategy_id: str = ""
    strategy_name: str = ""
    strategy_reward: float = 0.0
    confidence: float = 0.0
    risk_score: float = 0.0
    risk_adjusted_reward: float = 0.0
    final_score: float = 0.0
    rank: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "strategy_name": self.strategy_name,
            "strategy_reward": round(self.strategy_reward, 4),
            "confidence": round(self.confidence, 4),
            "risk_score": round(self.risk_score, 4),
            "risk_adjusted_reward": round(self.risk_adjusted_reward, 4),
            "final_score": round(self.final_score, 4),
            "rank": self.rank,
        }

    @property
    def is_viable(self) -> bool:
        """是否可行 (final_score >= 0.3)."""
        return self.final_score >= 0.3

    @property
    def is_strong(self) -> bool:
        """是否强推荐 (final_score >= 0.6)."""
        return self.final_score >= 0.6


# ═══════════════════════════════════════════════════════════════
# Decision Plan
# ═══════════════════════════════════════════════════════════════


@dataclass
class DecisionPlan:
    """决策执行计划 — 具体执行动作与预算.

    Attributes:
        plan_id: 计划唯一标识
        action_type: 动作类型
        target_entity: 目标实体 (campaign/adset/creative)
        target_entity_id: 目标实体 ID
        params: 动作参数
        test_budget: 实验预算 (TEST 模式)
        execute_budget: 执行预算 (EXECUTE 模式)
        max_budget: 最大预算上限
        duration_days: 执行天数
        expected_roas_impact: 预期 ROAS 影响
        rollout_steps: 分阶段执行步骤
    """
    plan_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    action_type: str = ""
    target_entity: str = "creative"
    target_entity_id: str = ""
    params: dict[str, Any] = field(default_factory=dict)
    test_budget: float = 0.0
    execute_budget: float = 0.0
    max_budget: float = 0.0
    duration_days: int = 7
    expected_roas_impact: float = 0.0
    rollout_steps: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "action_type": self.action_type,
            "target_entity": self.target_entity,
            "target_entity_id": self.target_entity_id,
            "params": self.params,
            "test_budget": self.test_budget,
            "execute_budget": self.execute_budget,
            "max_budget": self.max_budget,
            "duration_days": self.duration_days,
            "expected_roas_impact": round(self.expected_roas_impact, 4),
            "rollout_steps": self.rollout_steps,
        }

    @property
    def has_test_budget(self) -> bool:
        return self.test_budget > 0

    @property
    def has_execute_budget(self) -> bool:
        return self.execute_budget > 0


# ═══════════════════════════════════════════════════════════════
# Decision Output
# ═══════════════════════════════════════════════════════════════


@dataclass
class DecisionOutput:
    """决策引擎最终输出 — 对 Opportunity 的完整决策.

    与 E13.5.1 GrowthDecision 互补:
      - GrowthDecision: 生命周期状态管理
      - DecisionOutput: 决策引擎编排结果

    Attributes:
        decision_id: 决策唯一标识
        opportunity_id: 关联的机会 ID
        strategy_id: 选中的策略 ID
        strategy_name: 策略名称
        decision_type: 决策类型 (EXECUTE/TEST/HOLD/BLOCK/ESCALATE)
        confidence: 决策置信度 [0, 1]
        expected_reward: 预期收益
        risk_score: 综合风险评分 [0, 1]
        risk_level: 风险等级标签
        final_score: 最终评分
        action_plan: 执行计划
        alternatives: 备选方案
        explanation: 决策解释
        reasons: 决策理由列表
        warnings: 风险警告
        requires_approval: 是否需要人工审批
        created_at: 创建时间
        metadata: 扩展元数据
    """
    decision_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    opportunity_id: str = ""
    strategy_id: str = ""
    strategy_name: str = ""
    decision_type: DecisionType = DecisionType.HOLD
    confidence: float = 0.0
    expected_reward: float = 0.0
    risk_score: float = 0.0
    risk_level: str = "safe"
    final_score: float = 0.0
    action_plan: DecisionPlan | None = None
    alternatives: list[DecisionScore] = field(default_factory=list)
    explanation: str = ""
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    requires_approval: bool = False
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "opportunity_id": self.opportunity_id,
            "strategy_id": self.strategy_id,
            "strategy_name": self.strategy_name,
            "decision_type": self.decision_type.value,
            "confidence": round(self.confidence, 4),
            "expected_reward": round(self.expected_reward, 4),
            "risk_score": round(self.risk_score, 4),
            "risk_level": self.risk_level,
            "final_score": round(self.final_score, 4),
            "action_plan": self.action_plan.to_dict() if self.action_plan else None,
            "alternatives": [a.to_dict() for a in self.alternatives],
            "explanation": self.explanation,
            "reasons": self.reasons,
            "warnings": self.warnings,
            "requires_approval": self.requires_approval,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }

    @property
    def is_executable(self) -> bool:
        return self.decision_type == DecisionType.EXECUTE

    @property
    def is_testable(self) -> bool:
        return self.decision_type == DecisionType.TEST

    @property
    def is_blocked(self) -> bool:
        return self.decision_type == DecisionType.BLOCK

    @property
    def is_escalated(self) -> bool:
        return self.decision_type == DecisionType.ESCALATE

    @property
    def has_alternatives(self) -> bool:
        return len(self.alternatives) > 0

    @property
    def alternative_count(self) -> int:
        return len(self.alternatives)

    def get_top_alternative(self) -> DecisionScore | None:
        return self.alternatives[0] if self.alternatives else None


# ═══════════════════════════════════════════════════════════════
# Decision Input
# ═══════════════════════════════════════════════════════════════


@dataclass
class DecisionInput:
    """决策引擎输入 — 汇聚 Opportunity + Strategies + Risk.

    Attributes:
        opportunity: 增长机会
        strategies: 候选策略列表
        risks: 每个策略的风险评估 (keyed by strategy_id)
        context: 决策上下文 (产品、预算、样本等)
        metadata: 扩展元数据
    """
    opportunity: Any = None
    strategies: list[Any] = field(default_factory=list)
    risks: dict[str, Any] = field(default_factory=dict)
    context: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def has_opportunity(self) -> bool:
        return self.opportunity is not None

    @property
    def has_strategies(self) -> bool:
        return len(self.strategies) > 0

    @property
    def strategy_count(self) -> int:
        return len(self.strategies)