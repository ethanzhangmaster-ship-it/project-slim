"""E13.6.5 Feedback Models — 反馈闭环数据模型.

定义 ExecutionFeedback、RewardSignal、FeedbackResult 等核心模型，
连接 ExecutionResult → Reward → DecisionMemory → MemoryEvolution。

核心设计:
  - ExecutionFeedback: 连接执行结果与决策上下文
  - RewardSignal: 对执行结果的量化评估 (execution/efficiency/safety/outcome)
  - FeedbackResult: 反馈处理结果 (含 Memory 写入状态)
  - FeedbackConfig: 反馈计算参数配置

连接:
  E13.6.3 ExecutionEngine → E13.6.5 FeedbackLoop → E13.5.5 DecisionMemory → E13.4 MemoryEvolution
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


# ═══════════════════════════════════════════════════════════════
# Execution Feedback
# ═══════════════════════════════════════════════════════════════


@dataclass
class ExecutionFeedback:
    """执行反馈 — 连接执行结果与决策上下文.

    Attributes:
        feedback_id: 反馈唯一标识
        decision_id: 关联的决策 ID
        task_id: 关联的任务 ID
        plan_id: 关联的计划 ID
        opportunity_id: 关联的机会 ID
        strategy_id: 关联的策略 ID
        execution_summary: 执行结果摘要 (EngineResult.stats)
        audit_entries: 审计日志条目列表
        safety_evaluation: 安全评估结果 (SafetyEvaluation dict)
        context: 执行上下文 (ExecutionContext dict)
        action_type: 主要动作类型
        total_nodes: 总节点数
        success_nodes: 成功节点数
        failure_nodes: 失败节点数
        skipped_nodes: 跳过节点数
        rollback_nodes: 回滚节点数
        execution_duration_ms: 执行耗时 (毫秒)
        created_at: 创建时间
        metadata: 扩展元数据
    """
    feedback_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    decision_id: str = ""
    task_id: str = ""
    plan_id: str = ""
    opportunity_id: str = ""
    strategy_id: str = ""
    execution_summary: dict[str, Any] = field(default_factory=dict)
    audit_entries: list[dict[str, Any]] = field(default_factory=list)
    safety_evaluation: dict[str, Any] | None = None
    context: dict[str, Any] = field(default_factory=dict)
    action_type: str = ""
    total_nodes: int = 0
    success_nodes: int = 0
    failure_nodes: int = 0
    skipped_nodes: int = 0
    rollback_nodes: int = 0
    execution_duration_ms: float = 0.0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def success_rate(self) -> float:
        """执行成功率."""
        if self.total_nodes == 0:
            return 1.0
        return self.success_nodes / self.total_nodes

    @property
    def has_failures(self) -> bool:
        """是否有失败."""
        return self.failure_nodes > 0

    @property
    def has_rollbacks(self) -> bool:
        """是否有回滚."""
        return self.rollback_nodes > 0

    @property
    def was_blocked(self) -> bool:
        """是否被安全层拦截."""
        if self.safety_evaluation:
            return self.safety_evaluation.get("is_blocked", False)
        return False

    @property
    def needed_approval(self) -> bool:
        """是否需要审批."""
        if self.safety_evaluation:
            return self.safety_evaluation.get("requires_approval", False)
        return False

    def to_dict(self) -> dict[str, Any]:
        return {
            "feedback_id": self.feedback_id,
            "decision_id": self.decision_id,
            "task_id": self.task_id,
            "plan_id": self.plan_id,
            "opportunity_id": self.opportunity_id,
            "strategy_id": self.strategy_id,
            "execution_summary": self.execution_summary,
            "audit_entries": self.audit_entries,
            "safety_evaluation": self.safety_evaluation,
            "context": self.context,
            "action_type": self.action_type,
            "total_nodes": self.total_nodes,
            "success_nodes": self.success_nodes,
            "failure_nodes": self.failure_nodes,
            "skipped_nodes": self.skipped_nodes,
            "rollback_nodes": self.rollback_nodes,
            "execution_duration_ms": self.execution_duration_ms,
            "success_rate": round(self.success_rate, 4),
            "has_failures": self.has_failures,
            "has_rollbacks": self.has_rollbacks,
            "was_blocked": self.was_blocked,
            "needed_approval": self.needed_approval,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }


# ═══════════════════════════════════════════════════════════════
# Reward Signal
# ═══════════════════════════════════════════════════════════════


@dataclass
class RewardSignal:
    """Reward 信号 — 对执行结果的量化评估.

    四维 reward 分解:
      - execution_reward: 执行质量 (成功率、节点完成度)
      - efficiency_reward: 效率 (速度、资源利用)
      - safety_reward: 安全性 (无拦截、无警告)
      - outcome_reward: 业务结果 (ROAS 变化等)

    Attributes:
        reward_id: Reward 唯一标识
        decision_id: 关联的决策 ID
        total_reward: 总 reward [-1, 1]
        execution_reward: 执行奖励
        efficiency_reward: 效率奖励
        safety_reward: 安全奖励
        outcome_reward: 业务结果奖励
        confidence: Reward 置信度
        components: 各维度详细分解
        reward_level: 奖励等级 (positive/neutral/negative)
        created_at: 创建时间
        metadata: 扩展元数据
    """
    reward_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    decision_id: str = ""
    total_reward: float = 0.0
    execution_reward: float = 0.0
    efficiency_reward: float = 0.0
    safety_reward: float = 0.0
    outcome_reward: float = 0.0
    confidence: float = 1.0
    components: dict[str, float] = field(default_factory=dict)
    reward_level: str = "neutral"  # positive / neutral / negative
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_positive(self) -> bool:
        """是否为正 reward."""
        return self.total_reward > 0.1

    @property
    def is_negative(self) -> bool:
        """是否为负 reward."""
        return self.total_reward < -0.1

    @property
    def is_neutral(self) -> bool:
        """是否为中性 reward."""
        return -0.1 <= self.total_reward <= 0.1

    def to_dict(self) -> dict[str, Any]:
        return {
            "reward_id": self.reward_id,
            "decision_id": self.decision_id,
            "total_reward": round(self.total_reward, 4),
            "execution_reward": round(self.execution_reward, 4),
            "efficiency_reward": round(self.efficiency_reward, 4),
            "safety_reward": round(self.safety_reward, 4),
            "outcome_reward": round(self.outcome_reward, 4),
            "confidence": round(self.confidence, 4),
            "components": {k: round(v, 4) for k, v in self.components.items()},
            "reward_level": self.reward_level,
            "is_positive": self.is_positive,
            "is_negative": self.is_negative,
            "is_neutral": self.is_neutral,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }


# ═══════════════════════════════════════════════════════════════
# Feedback Result
# ═══════════════════════════════════════════════════════════════


@dataclass
class FeedbackResult:
    """反馈处理结果 — Feedback Loop 的最终输出.

    Attributes:
        feedback_id: 反馈 ID
        decision_id: 决策 ID
        feedback: 执行反馈
        reward: Reward 信号
        memory_updated: 是否更新 DecisionMemory
        experience_stored: 是否写入 ExperienceStore
        evolution_triggered: 是否触发 MemoryEvolution
        lessons: 经验教训
        recommendations: 改进建议
        next_action: 建议的后续动作
        created_at: 创建时间
        metadata: 扩展元数据
    """
    feedback_id: str = ""
    decision_id: str = ""
    feedback: ExecutionFeedback | None = None
    reward: RewardSignal | None = None
    memory_updated: bool = False
    experience_stored: bool = False
    evolution_triggered: bool = False
    lessons: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    next_action: str = ""  # reinforce / adjust / abandon / observe
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_successful_loop(self) -> bool:
        """反馈闭环是否成功."""
        return self.memory_updated and self.reward is not None

    @property
    def should_reinforce(self) -> bool:
        """是否应该强化该策略."""
        return self.next_action == "reinforce"

    @property
    def should_adjust(self) -> bool:
        """是否应该调整策略."""
        return self.next_action == "adjust"

    @property
    def should_abandon(self) -> bool:
        """是否应该放弃策略."""
        return self.next_action == "abandon"

    def to_dict(self) -> dict[str, Any]:
        return {
            "feedback_id": self.feedback_id,
            "decision_id": self.decision_id,
            "feedback": self.feedback.to_dict() if self.feedback else None,
            "reward": self.reward.to_dict() if self.reward else None,
            "memory_updated": self.memory_updated,
            "experience_stored": self.experience_stored,
            "evolution_triggered": self.evolution_triggered,
            "lessons": self.lessons,
            "recommendations": self.recommendations,
            "next_action": self.next_action,
            "is_successful_loop": self.is_successful_loop,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }


# ═══════════════════════════════════════════════════════════════
# Feedback Config
# ═══════════════════════════════════════════════════════════════


@dataclass
class FeedbackConfig:
    """反馈计算参数配置.

    Attributes:
        execution_weight: 执行质量权重 (默认 0.30)
        efficiency_weight: 效率权重 (默认 0.15)
        safety_weight: 安全权重 (默认 0.25)
        outcome_weight: 业务结果权重 (默认 0.30)
        positive_threshold: 正向 reward 阈值 (默认 0.1)
        negative_threshold: 负向 reward 阈值 (默认 -0.1)
        min_confidence: 最低置信度 (默认 0.3)
        evolution_trigger_threshold: 触发进化所需的经验数 (默认 10)
        max_lessons: 最多提取的经验教训数 (默认 5)
        max_recommendations: 最多改进建议数 (默认 3)
    """
    execution_weight: float = 0.30
    efficiency_weight: float = 0.15
    safety_weight: float = 0.25
    outcome_weight: float = 0.30
    positive_threshold: float = 0.1
    negative_threshold: float = -0.1
    min_confidence: float = 0.3
    evolution_trigger_threshold: int = 10
    max_lessons: int = 5
    max_recommendations: int = 3

    def validate(self) -> bool:
        """验证权重和为 1.0."""
        total = (
            self.execution_weight
            + self.efficiency_weight
            + self.safety_weight
            + self.outcome_weight
        )
        return abs(total - 1.0) < 0.001

    def to_dict(self) -> dict[str, Any]:
        return {
            "execution_weight": self.execution_weight,
            "efficiency_weight": self.efficiency_weight,
            "safety_weight": self.safety_weight,
            "outcome_weight": self.outcome_weight,
            "positive_threshold": self.positive_threshold,
            "negative_threshold": self.negative_threshold,
            "min_confidence": self.min_confidence,
            "evolution_trigger_threshold": self.evolution_trigger_threshold,
            "max_lessons": self.max_lessons,
            "max_recommendations": self.max_recommendations,
        }


# ═══════════════════════════════════════════════════════════════
# Factory
# ═══════════════════════════════════════════════════════════════


def create_default_config() -> FeedbackConfig:
    """创建默认反馈配置."""
    return FeedbackConfig()


def create_exploration_config() -> FeedbackConfig:
    """创建探索型配置 (更重视业务结果，降低安全权重)."""
    return FeedbackConfig(
        execution_weight=0.25,
        efficiency_weight=0.15,
        safety_weight=0.15,
        outcome_weight=0.45,
        positive_threshold=0.05,
        negative_threshold=-0.05,
    )


def create_conservative_config() -> FeedbackConfig:
    """创建保守型配置 (更重视安全，降低业务结果权重)."""
    return FeedbackConfig(
        execution_weight=0.25,
        efficiency_weight=0.10,
        safety_weight=0.45,
        outcome_weight=0.20,
        positive_threshold=0.15,
        negative_threshold=-0.15,
        min_confidence=0.5,
    )