"""E13.7.7.5 Learning Execution Models — 策略执行协议.

Day 7.7.5:
  定义 LearningPolicyDecision → Execution 的协议层，
  使 Adaptive Optimization Layer 从 "建议系统" 变成 "可驱动执行系统"。

核心模型:
  1. LearningExecutionAction  — 可执行的动作类型
  2. LearningExecutionResult  — 执行结果 (可追踪、可回滚)
  3. LearningExecutionContext — 执行上下文 (执行时需要的依赖)

设计原则:
  - 纯数据模型，不包含执行逻辑
  - 所有执行结果包含 previous_state / new_state 用于回滚
  - 可序列化 (to_dict)，支持审计
  - 不修改已有模块 (DecisionEngine, PatternPredictor, MemoryConsolidator, LearningStrategyOptimizer)

用法:
  from growth_runtime.intelligence.learning.models.learning_execution_models import (
      LearningExecutionAction,
      LearningExecutionResult,
      LearningExecutionContext,
  )
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


# ═══════════════════════════════════════════════════════════════
# 1. LearningExecutionAction
# ═══════════════════════════════════════════════════════════════


class LearningExecutionAction(str, Enum):
    """策略执行动作 — Adapter 将 PolicyDecision 映射为此动作.

    | 动作               | 含义                          | 触发条件                  |
    |-------------------|------------------------------|--------------------------|
    | EXECUTE_LEARNING   | 执行学习循环                    | should_learn=True        |
    | BLOCK_LEARNING     | 阻止学习循环                    | should_learn=False       |
    | REFRESH_MEMORY     | 刷新记忆系统                    | should_update_memory=True |
    | UPDATE_STRATEGY    | 更新学习策略参数                 | strategy_mode 变化        |
    | NO_ACTION          | 无操作                        | MAINTAIN 决策             |
    """
    EXECUTE_LEARNING = "execute_learning"
    BLOCK_LEARNING = "block_learning"
    REFRESH_MEMORY = "refresh_memory"
    UPDATE_STRATEGY = "update_strategy"
    NO_ACTION = "no_action"


# ═══════════════════════════════════════════════════════════════
# 2. LearningExecutionContext
# ═══════════════════════════════════════════════════════════════


@dataclass
class LearningExecutionContext:
    """学习执行上下文 — 执行时需要的依赖注入.

    Attributes:
        context: 当前业务上下文 (game, country, creative, spend, ...)
        experiences: 学习经验列表 (可选)
        rewards: 奖励列表 (可选)
        decision_memory: DecisionMemory 实例
        experience_store: ExperienceStore 实例
        pattern_store: PatternStore 实例
        memory_consolidator: MemoryConsolidator 实例 (可选)
        loop_controller: LearningLoopController 实例 (可选)
        strategy_optimizer: LearningStrategyOptimizer 实例 (可选)
        metadata: 扩展元数据
    """
    context: dict[str, Any] = field(default_factory=dict)
    experiences: list[Any] = field(default_factory=list)
    rewards: list[Any] = field(default_factory=list)
    decision_memory: Any = None
    experience_store: Any = None
    pattern_store: Any = None
    memory_consolidator: Any = None
    loop_controller: Any = None
    strategy_optimizer: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "context_keys": list(self.context.keys()),
            "experience_count": len(self.experiences),
            "reward_count": len(self.rewards),
            "has_decision_memory": self.decision_memory is not None,
            "has_experience_store": self.experience_store is not None,
            "has_pattern_store": self.pattern_store is not None,
            "has_memory_consolidator": self.memory_consolidator is not None,
            "has_loop_controller": self.loop_controller is not None,
            "has_strategy_optimizer": self.strategy_optimizer is not None,
            "metadata": self.metadata,
        }


# ═══════════════════════════════════════════════════════════════
# 3. LearningExecutionResult
# ═══════════════════════════════════════════════════════════════


@dataclass
class LearningExecutionResult:
    """学习策略执行结果 — 一次 Policy → Execution 的完整输出.

    Day 7.7.5:
      任何策略执行都必须可追踪、可回滚。

    Attributes:
        success: 执行是否成功
        action: 执行的动作类型
        executed: 是否实际执行了操作 (BLOCK_LEARNING 时 executed=False)
        policy_decision_type: 触发执行的 PolicyDecisionType
        previous_state: 执行前的 LearningStrategyState 快照
        new_state: 执行后的 LearningStrategyState 快照
        memory_updated: MemoryConsolidator 是否被触发
        memory_result: MemoryConsolidator 的结果 (可选)
        strategy_updated: LearningStrategyState 是否被修改
        strategy_adjustments: 策略调整列表 (可选)
        learning_cycle: LearningCycleResult 是否被触发
        rollback_available: 是否可回滚
        reasons: 执行原因 / 决策说明
        error: 错误信息 (失败时)
        executed_at: 执行时间
        metadata: 扩展元数据
    """
    success: bool = False
    action: str = LearningExecutionAction.NO_ACTION.value
    executed: bool = False
    policy_decision_type: str = ""
    previous_state: dict[str, Any] | None = None
    new_state: dict[str, Any] | None = None
    memory_updated: bool = False
    memory_result: dict[str, Any] | None = None
    strategy_updated: bool = False
    strategy_adjustments: list[dict[str, Any]] = field(default_factory=list)
    learning_cycle: dict[str, Any] | None = None
    rollback_available: bool = False
    reasons: list[str] = field(default_factory=list)
    error: str | None = None
    executed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    # ── Properties ──────────────────────────────────────────────

    @property
    def is_successful(self) -> bool:
        """执行是否成功."""
        return self.success and self.error is None

    @property
    def action_executed(self) -> bool:
        """是否实际执行了操作."""
        return self.executed and self.action != LearningExecutionAction.NO_ACTION.value

    @property
    def has_state_change(self) -> bool:
        """状态是否发生了变化."""
        if self.previous_state is None or self.new_state is None:
            return False
        return self.previous_state != self.new_state

    @property
    def can_rollback(self) -> bool:
        """是否可回滚 (需要 previous_state 且 rollback_available)."""
        return self.rollback_available and self.previous_state is not None

    # ── Factory Methods ────────────────────────────────────────

    @classmethod
    def success_result(
        cls,
        action: LearningExecutionAction,
        policy_decision_type: str,
        previous_state: dict[str, Any] | None = None,
        new_state: dict[str, Any] | None = None,
        reasons: list[str] | None = None,
        **kwargs: Any,
    ) -> LearningExecutionResult:
        """创建成功执行结果."""
        return cls(
            success=True,
            action=action.value,
            executed=True,
            policy_decision_type=policy_decision_type,
            previous_state=previous_state,
            new_state=new_state or (dict(previous_state) if previous_state else None),
            rollback_available=previous_state is not None,
            reasons=reasons or [],
            **kwargs,
        )

    @classmethod
    def blocked_result(
        cls,
        policy_decision_type: str,
        reasons: list[str] | None = None,
        previous_state: dict[str, Any] | None = None,
    ) -> LearningExecutionResult:
        """创建 BLOCK 执行结果."""
        return cls(
            success=True,  # BLOCK 本身是成功的决策
            action=LearningExecutionAction.BLOCK_LEARNING.value,
            executed=False,
            policy_decision_type=policy_decision_type,
            previous_state=previous_state,
            new_state=dict(previous_state) if previous_state else None,
            rollback_available=False,
            reasons=reasons or [],
        )

    @classmethod
    def no_action_result(
        cls,
        policy_decision_type: str,
        reasons: list[str] | None = None,
        previous_state: dict[str, Any] | None = None,
    ) -> LearningExecutionResult:
        """创建 NO_ACTION 执行结果."""
        return cls(
            success=True,
            action=LearningExecutionAction.NO_ACTION.value,
            executed=False,
            policy_decision_type=policy_decision_type,
            previous_state=previous_state,
            new_state=dict(previous_state) if previous_state else None,
            rollback_available=False,
            reasons=reasons or [],
        )

    @classmethod
    def error_result(
        cls,
        action: LearningExecutionAction,
        error: str,
        policy_decision_type: str = "",
        previous_state: dict[str, Any] | None = None,
        reasons: list[str] | None = None,
    ) -> LearningExecutionResult:
        """创建错误执行结果."""
        return cls(
            success=False,
            action=action.value,
            executed=True,
            policy_decision_type=policy_decision_type,
            previous_state=previous_state,
            new_state=None,
            rollback_available=previous_state is not None,
            reasons=reasons or [],
            error=error,
        )

    # ── Serialization ──────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "action": self.action,
            "executed": self.executed,
            "policy_decision_type": self.policy_decision_type,
            "previous_state": self.previous_state,
            "new_state": self.new_state,
            "memory_updated": self.memory_updated,
            "memory_result": self.memory_result,
            "strategy_updated": self.strategy_updated,
            "strategy_adjustments": self.strategy_adjustments,
            "learning_cycle": self.learning_cycle,
            "rollback_available": self.rollback_available,
            "reasons": self.reasons,
            "error": self.error,
            "executed_at": self.executed_at,
            "metadata": self.metadata,
        }


# ═══════════════════════════════════════════════════════════════
# __all__
# ═══════════════════════════════════════════════════════════════

__all__ = [
    "LearningExecutionAction",
    "LearningExecutionContext",
    "LearningExecutionResult",
]