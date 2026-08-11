"""E14.4.3.1 Creative Executor — 创意执行层.

将 Creative Plan 转化为可执行的 Creative Action:

  输入: CreativePlan (策略 + 种群规模 + 变异配置)
  输出: CreativeExecutionAction (action_type, target, parameters, status)

核心能力:
  - Plan→Action: 将执行计划转化为具体动作
  - 动作类型: GENERATE_VARIANTS, MUTATE_DNA, CLONE_WINNER, REFRESH, STOP, PROMOTE
  - 状态管理: PENDING → EXECUTING → COMPLETED/FAILED
  - 优先级排序: 确保高优先级动作优先执行
  - 批量调度: 支持多计划批量执行

设计原则:
  - 确定性动作生成，不依赖 AI
  - 与 E11 Evolution Engine 兼容
  - 所有动作可追溯、可回滚
  - 与 UA Agent 执行层对齐
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from .planner import CreativePlan, PlanStatus, MutationConfig
from .strategy import CreativeStrategyType, GeneMutationAction
from .opportunity import OpportunityPriority


# ═══════════════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════════════


class ExecutionActionType(str, Enum):
    """执行动作类型."""
    GENERATE_VARIANTS = "generate_variants"      # 生成变体
    MUTATE_DNA = "mutate_dna"                    # 变异 DNA
    CLONE_WINNER = "clone_winner"                # 克隆赢家
    REFRESH_CREATIVE = "refresh_creative"        # 刷新素材
    STOP_CREATIVE = "stop_creative"              # 停止素材
    PROMOTE_CREATIVE = "promote_creative"        # 推广素材
    SCALE_CREATIVE = "scale_creative"            # 扩大投放
    TEST_CREATIVE = "test_creative"              # 测试素材
    UNKNOWN = "unknown"


class ExecutionStatus(str, Enum):
    """执行状态."""
    PENDING = "pending"          # 等待执行
    QUEUED = "queued"            # 已排队
    EXECUTING = "executing"      # 执行中
    COMPLETED = "completed"      # 完成
    FAILED = "failed"            # 失败
    CANCELLED = "cancelled"      # 取消
    ROLLED_BACK = "rolled_back"  # 已回滚


# ═══════════════════════════════════════════════════════════════
# Strategy → Action Mapping
# ═══════════════════════════════════════════════════════════════

STRATEGY_TO_ACTION: dict[CreativeStrategyType, ExecutionActionType] = {
    CreativeStrategyType.REFRESH_HOOK: ExecutionActionType.GENERATE_VARIANTS,
    CreativeStrategyType.CHANGE_VISUAL_STYLE: ExecutionActionType.GENERATE_VARIANTS,
    CreativeStrategyType.CHANGE_GAMEPLAY_SHOWCASE: ExecutionActionType.GENERATE_VARIANTS,
    CreativeStrategyType.CHANGE_EMOTION: ExecutionActionType.GENERATE_VARIANTS,
    CreativeStrategyType.COPY_WINNER_DNA: ExecutionActionType.CLONE_WINNER,
    CreativeStrategyType.EXPLORE_NEW_DNA: ExecutionActionType.MUTATE_DNA,
    CreativeStrategyType.OPTIMIZE_OPENING: ExecutionActionType.GENERATE_VARIANTS,
    CreativeStrategyType.SCALE_WINNER: ExecutionActionType.SCALE_CREATIVE,
    CreativeStrategyType.EXPLORE_NEW_AUDIENCE: ExecutionActionType.TEST_CREATIVE,
    CreativeStrategyType.TEST_NEW_CONCEPT: ExecutionActionType.TEST_CREATIVE,
    CreativeStrategyType.REFRESH_CREATIVE: ExecutionActionType.REFRESH_CREATIVE,
}


# ═══════════════════════════════════════════════════════════════
# Models
# ═══════════════════════════════════════════════════════════════


@dataclass
class ExecutionParameters:
    """执行参数.

    Attributes:
        generator: 生成器名称 (e11_evolution/clip/lovart)
        count: 生成数量
        mutation_configs: 变异配置
        experiment_config: 实验配置
        generation: 代际数
        keep_original: 是否保留原始
        max_budget: 最大预算
        priority: 优先级
        metadata: 扩展参数
    """
    generator: str = "e11_evolution"
    count: int = 5
    mutation_configs: list[dict[str, Any]] = field(default_factory=list)
    experiment_config: dict[str, Any] | None = None
    generation: int = 1
    keep_original: bool = True
    max_budget: float = 0.0
    priority: str = "medium"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "generator": self.generator,
            "count": self.count,
            "mutation_configs": self.mutation_configs,
            "experiment_config": self.experiment_config,
            "generation": self.generation,
            "keep_original": self.keep_original,
            "max_budget": self.max_budget,
            "priority": self.priority,
            "metadata": self.metadata,
        }


@dataclass
class CreativeExecutionAction:
    """创意执行动作 — Plan → Action.

    Attributes:
        action_id: 动作 ID
        plan_id: 关联计划 ID
        strategy_id: 关联策略 ID
        creative_id: 目标创意 ID
        action_type: 动作类型
        status: 执行状态
        priority: 优先级
        parameters: 执行参数
        result: 执行结果
        error: 错误信息
        created_at: 创建时间
        started_at: 开始时间
        completed_at: 完成时间
        metadata: 扩展元数据
    """
    action_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    plan_id: str = ""
    strategy_id: str = ""
    creative_id: str = ""
    action_type: ExecutionActionType = ExecutionActionType.UNKNOWN
    status: ExecutionStatus = ExecutionStatus.PENDING
    priority: OpportunityPriority = OpportunityPriority.MEDIUM
    parameters: ExecutionParameters | None = None
    result: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    started_at: str = ""
    completed_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "plan_id": self.plan_id,
            "strategy_id": self.strategy_id,
            "creative_id": self.creative_id,
            "action_type": self.action_type.value,
            "status": self.status.value,
            "priority": self.priority.value,
            "parameters": self.parameters.to_dict() if self.parameters else None,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "metadata": self.metadata,
        }

    @property
    def is_pending(self) -> bool:
        return self.status == ExecutionStatus.PENDING

    @property
    def is_completed(self) -> bool:
        return self.status == ExecutionStatus.COMPLETED

    @property
    def is_failed(self) -> bool:
        return self.status == ExecutionStatus.FAILED

    @property
    def is_terminal(self) -> bool:
        return self.status in (
            ExecutionStatus.COMPLETED,
            ExecutionStatus.FAILED,
            ExecutionStatus.CANCELLED,
            ExecutionStatus.ROLLED_BACK,
        )

    @property
    def summary(self) -> str:
        parts = [
            f"[{self.priority.value.upper()}] {self.action_type.value}",
            f"creative={self.creative_id}",
            f"status={self.status.value}",
        ]
        if self.parameters:
            parts.append(f"count={self.parameters.count}")
        return " ".join(parts)


@dataclass
class ExecutionBatch:
    """批量执行结果.

    Attributes:
        batch_id: 批次 ID
        actions: 动作列表
        total_actions: 总动作数
        completed: 完成数
        failed: 失败数
        pending: 等待数
        summary: 批次摘要
        created_at: 创建时间
    """
    batch_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    actions: list[CreativeExecutionAction] = field(default_factory=list)
    total_actions: int = 0
    completed: int = 0
    failed: int = 0
    pending: int = 0
    summary: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "actions": [a.to_dict() for a in self.actions],
            "total_actions": self.total_actions,
            "completed": self.completed,
            "failed": self.failed,
            "pending": self.pending,
            "summary": self.summary,
            "created_at": self.created_at,
        }

    @property
    def action_count(self) -> int:
        return len(self.actions)


# ═══════════════════════════════════════════════════════════════
# Creative Executor
# ═══════════════════════════════════════════════════════════════


class CreativeExecutor:
    """创意执行器 — Plan → Action.

    职责:
      1. 计划→动作: 将执行计划转化为具体动作
      2. 动作调度: 按优先级调度动作执行
      3. 状态管理: 跟踪动作执行生命周期
      4. 回滚支持: 支持动作回滚

    用法:
        executor = CreativeExecutor()
        action = executor.create_action(plan)
        executor.execute(action)
    """

    def __init__(self):
        self._actions: dict[str, CreativeExecutionAction] = {}
        self._history: list[CreativeExecutionAction] = []

    # ── 核心方法 ──────────────────────────────────────────────

    def create_action(self, plan: CreativePlan) -> CreativeExecutionAction:
        """从计划创建执行动作.

        Args:
            plan: 创意执行计划

        Returns:
            CreativeExecutionAction: 执行动作
        """
        action_type = STRATEGY_TO_ACTION.get(
            plan.strategy_type,
            ExecutionActionType.UNKNOWN,
        )

        parameters = self._build_parameters(plan)

        action = CreativeExecutionAction(
            plan_id=plan.plan_id,
            strategy_id=plan.strategy_id,
            creative_id=plan.creative_id,
            action_type=action_type,
            priority=plan.priority,
            parameters=parameters,
        )

        self._actions[action.action_id] = action
        self._history.append(action)
        return action

    def create_actions_from_batch(
        self,
        plans: list[CreativePlan],
    ) -> ExecutionBatch:
        """从批量计划创建批量动作.

        Args:
            plans: 计划列表

        Returns:
            ExecutionBatch: 批量执行结果
        """
        actions = []
        for plan in plans:
            if plan.status == PlanStatus.READY:
                action = self.create_action(plan)
                actions.append(action)

        # 按优先级排序
        priority_order = {
            OpportunityPriority.CRITICAL: 0,
            OpportunityPriority.HIGH: 1,
            OpportunityPriority.MEDIUM: 2,
            OpportunityPriority.LOW: 3,
        }
        actions.sort(key=lambda a: priority_order.get(a.priority, 99))

        batch = ExecutionBatch(
            actions=actions,
            total_actions=len(actions),
            pending=len(actions),
            summary=f"共 {len(actions)} 个执行动作",
        )

        return batch

    def execute(self, action: CreativeExecutionAction) -> bool:
        """执行动作 (标记为执行中).

        Args:
            action: 执行动作

        Returns:
            bool: 是否成功开始执行
        """
        if action.status != ExecutionStatus.PENDING:
            return False
        action.status = ExecutionStatus.EXECUTING
        action.started_at = datetime.now(timezone.utc).isoformat()
        return True

    def complete(
        self,
        action: CreativeExecutionAction,
        result: dict[str, Any] | None = None,
    ) -> bool:
        """标记动作完成.

        Args:
            action: 执行动作
            result: 执行结果

        Returns:
            bool: 是否成功
        """
        if action.status != ExecutionStatus.EXECUTING:
            return False
        action.status = ExecutionStatus.COMPLETED
        action.completed_at = datetime.now(timezone.utc).isoformat()
        if result:
            action.result = result
        return True

    def fail(
        self,
        action: CreativeExecutionAction,
        error: str = "",
    ) -> bool:
        """标记动作失败.

        Args:
            action: 执行动作
            error: 错误信息

        Returns:
            bool: 是否成功
        """
        if action.status not in (ExecutionStatus.PENDING, ExecutionStatus.EXECUTING):
            return False
        action.status = ExecutionStatus.FAILED
        action.completed_at = datetime.now(timezone.utc).isoformat()
        action.error = error
        return True

    def rollback(self, action: CreativeExecutionAction) -> bool:
        """回滚动作.

        Args:
            action: 执行动作

        Returns:
            bool: 是否成功回滚
        """
        if action.status != ExecutionStatus.COMPLETED:
            return False
        action.status = ExecutionStatus.ROLLED_BACK
        action.completed_at = datetime.now(timezone.utc).isoformat()
        return True

    def cancel(self, action: CreativeExecutionAction) -> bool:
        """取消动作.

        Args:
            action: 执行动作

        Returns:
            bool: 是否成功取消
        """
        if action.is_terminal:
            return False
        action.status = ExecutionStatus.CANCELLED
        action.completed_at = datetime.now(timezone.utc).isoformat()
        return True

    # ── 内部方法 ──────────────────────────────────────────────

    def _build_parameters(self, plan: CreativePlan) -> ExecutionParameters:
        """从计划构建执行参数."""
        mutation_configs = []
        if plan.mutation_configs:
            mutation_configs = [m.to_dict() for m in plan.mutation_configs]

        experiment_config = None
        if plan.experiment_config:
            experiment_config = plan.experiment_config.to_dict()

        return ExecutionParameters(
            generator="e11_evolution",
            count=plan.population_size,
            mutation_configs=mutation_configs,
            experiment_config=experiment_config,
            generation=plan.generation_count,
            keep_original=plan.keep_original,
            max_budget=plan.experiment_config.max_budget if plan.experiment_config else 0.0,
            priority=plan.priority.value,
        )

    # ── 查询 ──────────────────────────────────────────────────

    def get_action(self, action_id: str) -> CreativeExecutionAction | None:
        return self._actions.get(action_id)

    def get_actions_by_plan(self, plan_id: str) -> list[CreativeExecutionAction]:
        return [a for a in self._actions.values() if a.plan_id == plan_id]

    def get_actions_by_creative(self, creative_id: str) -> list[CreativeExecutionAction]:
        return [a for a in self._actions.values() if a.creative_id == creative_id]

    def get_pending_actions(self) -> list[CreativeExecutionAction]:
        return [a for a in self._actions.values() if a.is_pending]

    def get_executing_actions(self) -> list[CreativeExecutionAction]:
        return [a for a in self._actions.values() if a.status == ExecutionStatus.EXECUTING]

    def get_completed_actions(self) -> list[CreativeExecutionAction]:
        return [a for a in self._actions.values() if a.is_completed]

    def get_failed_actions(self) -> list[CreativeExecutionAction]:
        return [a for a in self._actions.values() if a.is_failed]

    def get_history(self, n: int = 50) -> list[CreativeExecutionAction]:
        return self._history[-n:]

    def stats(self) -> dict[str, Any]:
        total = len(self._actions)
        if total == 0:
            return {"total": 0}
        status_counts: dict[str, int] = {}
        for a in self._actions.values():
            s = a.status.value
            status_counts[s] = status_counts.get(s, 0) + 1
        type_counts: dict[str, int] = {}
        for a in self._actions.values():
            t = a.action_type.value
            type_counts[t] = type_counts.get(t, 0) + 1
        return {
            "total": total,
            "by_status": status_counts,
            "by_type": type_counts,
            "pending": len(self.get_pending_actions()),
            "executing": len(self.get_executing_actions()),
            "completed": len(self.get_completed_actions()),
            "failed": len(self.get_failed_actions()),
        }

    def reset(self) -> None:
        self._actions.clear()
        self._history.clear()


# ═══════════════════════════════════════════════════════════════
# Factory
# ═══════════════════════════════════════════════════════════════


def create_executor() -> CreativeExecutor:
    """创建默认执行器."""
    return CreativeExecutor()