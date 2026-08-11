"""E11.8.2 — Strategy Executor。

核心入口：Strategy → MutationPlan → EvolutionTask → Scheduler。

流程：
  EvolutionStrategy → ExecutionPlanner → MutationPlan → create tasks → Scheduler.submit()
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from ..models import EvolutionStrategy, StrategyType
from .models import (
    ExecutionResult,
    MutationOperation,
    MutationPlan,
    MutationParameter,
)
from .execution_planner import ExecutionPlanner

logger = logging.getLogger(__name__)

# 默认 task 元数据
DEFAULT_TASK_METADATA: dict[str, Any] = {}


class StrategyExecutor:
    """策略执行器。

    将 EvolutionStrategy 通过 Scheduler 调度执行。

    Attributes:
        planner:        执行计划器
        scheduler:      调度器
        task_metadata:  默认任务元数据
    """

    def __init__(
        self,
        planner: ExecutionPlanner | None = None,
        scheduler: Any = None,  # EvolutionScheduler
        task_metadata: dict[str, Any] | None = None,
    ) -> None:
        self._planner = planner or ExecutionPlanner()
        self._scheduler = scheduler
        self._task_metadata = task_metadata or DEFAULT_TASK_METADATA

    # ── 主入口 ──────────────────────────────────────────

    def execute(
        self,
        strategy: EvolutionStrategy,
    ) -> ExecutionResult:
        """执行一个 EvolutionStrategy。

        完整流程：
          1. ExecutionPlanner.create_plan() → MutationPlan
          2. 为每个 mutation 创建 EvolutionTask
          3. 提交到 Scheduler
          4. 返回 ExecutionResult

        Args:
            strategy: EvolutionStrategy

        Returns:
            ExecutionResult
        """
        # 1. 创建计划
        plan = self._planner.create_plan(strategy)

        # 2. 创建并提交任务
        task_ids = self._submit_plan(plan)

        # 3. 构建结果
        success = len(task_ids) > 0
        reason = (
            f"Created {len(task_ids)} tasks from {plan.mutation_count} mutations"
            if success
            else "No tasks created (budget exhausted or scheduler unavailable)"
        )

        result = ExecutionResult(
            plan_id=plan.plan_id,
            strategy_id=strategy.strategy_id,
            tasks_created=len(task_ids),
            task_ids=task_ids,
            success=success,
            reason=reason,
            metadata={
                "strategy_type": strategy.strategy_type.value,
                "mutation_focus": strategy.mutation_focus.value,
                "plan": plan.to_dict(),
            },
        )

        logger.info(
            f"Strategy executed: {result.tasks_created} tasks, "
            f"success={result.success}"
        )

        return result

    def execute_batch(
        self,
        strategies: list[EvolutionStrategy],
    ) -> list[ExecutionResult]:
        """批量执行策略。

        Returns:
            ExecutionResult 列表
        """
        return [self.execute(s) for s in strategies]

    # ── 内部方法 ─────────────────────────────────────────

    def _submit_plan(self, plan: MutationPlan) -> list[str]:
        """将 MutationPlan 转换为 EvolutionTask 并提交到 Scheduler。

        Returns:
            成功提交的 task_id 列表
        """
        if self._scheduler is None:
            logger.warning("No scheduler configured, cannot submit tasks")
            return []

        task_ids: list[str] = []

        for i, mutation in enumerate(plan.mutations):
            task = self._create_task(plan, mutation, i)
            if task is None:
                continue

            task_id = self._scheduler.submit(task)
            if task_id:
                task_ids.append(task_id)

        return task_ids

    def _create_task(
        self,
        plan: MutationPlan,
        mutation: MutationParameter,
        index: int,
    ) -> Any | None:
        """根据 MutationPlan 和 MutationParameter 创建 EvolutionTask。

        Args:
            plan:     MutationPlan
            mutation: MutationParameter
            index:    mutation 在列表中的序号

        Returns:
            EvolutionTask 或 None
        """
        # 动态导入避免循环依赖
        from ...orchestrator.scheduler.models import EvolutionTask, TaskStatus

        # 确定 genome_id
        genome_id = self._resolve_genome_id(plan, index)

        # 确定 action
        action = mutation.metadata.get("operation", "modify")

        # 确定 mutation_strategy
        mutation_strategy = mutation.metadata.get("strategy_type", "explore")

        # 优先级：plan priority + index offset（让同计划内任务有序）
        priority = plan.priority - index

        return EvolutionTask(
            genome_id=genome_id,
            action=action,
            mutation_strategy=mutation_strategy,
            priority=max(1, priority),
            metadata={
                "plan_id": plan.plan_id,
                "strategy_id": plan.strategy_id,
                "mutation_focus": mutation.focus,
                "target_gene": mutation.target_gene,
                "intensity": mutation.intensity,
                "description": mutation.description,
                "mutation_index": index,
                **(self._task_metadata),
            },
        )

    @staticmethod
    def _resolve_genome_id(plan: MutationPlan, index: int) -> str:
        """解析 genome_id。

        - 如果有 target_genomes，轮询使用
        - CREATE 操作生成新 genome_id
        - 兜底生成唯一 ID
        """
        if plan.genome_ids:
            return plan.genome_ids[index % len(plan.genome_ids)]

        if plan.is_create:
            return f"new_genome_{uuid.uuid4().hex[:8]}"

        return f"genome_{uuid.uuid4().hex[:8]}"

    # ── 属性 ────────────────────────────────────────────

    @property
    def planner(self) -> ExecutionPlanner:
        return self._planner

    @property
    def scheduler(self) -> Any:
        return self._scheduler

    def set_scheduler(self, scheduler: Any) -> None:
        """设置调度器。"""
        self._scheduler = scheduler

    def __repr__(self) -> str:
        has_scheduler = self._scheduler is not None
        return f"StrategyExecutor(planner={self._planner}, scheduler={has_scheduler})"