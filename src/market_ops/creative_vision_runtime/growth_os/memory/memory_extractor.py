"""E12.7.5 Memory Extractor — 执行结果 → 增长经验."""

from __future__ import annotations

from typing import Any

from ..execution.models import (
    ExecutionPlan,
    ExecutionResult,
    ExecutionTask,
    TaskStatus,
    TaskType,
)

from .models import (
    ExperienceContext,
    ExperienceMetrics,
    GrowthExperience,
    MemoryType,
    Outcome,
)


class MemoryExtractor:
    """记忆提取器 — 将 ExecutionResult 提炼为 GrowthExperience.

    输入: ExecutionPlan / ExecutionTask / ExecutionResult
    输出: GrowthExperience
    """

    def __init__(self):
        self._extraction_count: int = 0

    @property
    def extraction_count(self) -> int:
        return self._extraction_count

    # ── Extract from Plan ─────────────────────────────────────

    def extract_from_plan(self, plan: ExecutionPlan) -> list[GrowthExperience]:
        """从 ExecutionPlan 中提取所有经验."""
        experiences: list[GrowthExperience] = []
        for task in plan.tasks:
            exp = self.extract_from_task(task, plan)
            if exp is not None:
                experiences.append(exp)
        return experiences

    def extract_from_task(
        self, task: ExecutionTask, plan: ExecutionPlan | None = None,
    ) -> GrowthExperience | None:
        """从单个 ExecutionTask 中提取经验."""
        self._extraction_count += 1

        outcome = self._map_status(task.status)
        memory_type = self._map_task_type(task.task_type)
        learning_value = self._compute_learning_value(task, outcome)

        context = ExperienceContext(
            product_id=task.product_id,
            market=task.parameters.get("market", ""),
            channel=task.parameters.get("channel", ""),
            lifecycle=task.parameters.get("lifecycle", ""),
            creative_state=task.parameters.get("creative_state", ""),
        )

        metrics = self._extract_metrics(task)

        tags = self._generate_tags(task, outcome)

        summary = self._generate_summary(task, outcome)

        return GrowthExperience(
            product_id=task.product_id,
            strategy_id=task.strategy_id,
            execution_id=plan.plan_id if plan else "",
            memory_type=memory_type,
            context=context,
            action=self._extract_action(task),
            result=outcome,
            metrics=metrics,
            learning_value=learning_value,
            confidence=self._compute_confidence(task, outcome),
            tags=tags,
            summary=summary,
        )

    # ── Mapping helpers ───────────────────────────────────────

    def _map_status(self, status: TaskStatus) -> Outcome:
        if status == TaskStatus.SUCCESS:
            return Outcome.SUCCESS
        if status in {TaskStatus.FAILED, TaskStatus.CANCELLED}:
            return Outcome.FAILURE
        return Outcome.PARTIAL

    def _map_task_type(self, task_type: TaskType) -> MemoryType:
        creative_types = {
            TaskType.CREATIVE_GENERATION, TaskType.CREATIVE_MUTATION,
            TaskType.CREATE_CREATIVE, TaskType.REFRESH_CREATIVE,
        }
        experiment_types = {
            TaskType.EXPERIMENT_START, TaskType.EXPERIMENT_EVALUATE,
            TaskType.LAUNCH_EXPERIMENT, TaskType.EVALUATE_EXPERIMENT,
        }
        budget_types = {
            TaskType.BUDGET_INCREASE, TaskType.BUDGET_DECREASE,
            TaskType.BUDGET_REALLOCATE, TaskType.INCREASE_BUDGET,
            TaskType.DECREASE_BUDGET, TaskType.REALLOCATE_BUDGET,
        }
        if task_type in creative_types:
            return MemoryType.CREATIVE_MEMORY
        if task_type in experiment_types:
            return MemoryType.EXPERIMENT_MEMORY
        if task_type in budget_types:
            return MemoryType.STRATEGY_MEMORY
        return MemoryType.STRATEGY_MEMORY

    def _compute_learning_value(self, task: ExecutionTask, outcome: Outcome) -> float:
        """计算学习价值.

        成功=高价值, 失败也能学到东西, 未完成=低价值.
        """
        base = 0.5
        if outcome == Outcome.SUCCESS:
            result = task.result
            if result and result.metrics:
                roas = result.metrics.get("roas", 0.0)
                if roas > 1.0:
                    base += min(0.3, (roas - 1.0) * 0.15)
            base += 0.2  # success bonus
        elif outcome == Outcome.FAILURE:
            base += 0.1  # failure still has learning value
        else:
            base -= 0.2  # partial is less valuable

        return max(0.0, min(1.0, base))

    def _compute_confidence(self, task: ExecutionTask, outcome: Outcome) -> float:
        """计算经验置信度."""
        if outcome == Outcome.SUCCESS:
            confidence = 0.7
            if task.result and task.result.metrics:
                roas = task.result.metrics.get("roas", 0.0)
                if roas > 1.0:
                    confidence = min(0.95, 0.7 + (roas - 1.0) * 0.1)
            return confidence
        if outcome == Outcome.FAILURE:
            return 0.6
        return 0.3

    def _extract_metrics(self, task: ExecutionTask) -> ExperienceMetrics:
        """从任务结果中提取指标."""
        result = task.result
        if result is None:
            return ExperienceMetrics()

        return ExperienceMetrics(
            spend=result.metrics.get("spend", 0.0),
            revenue=result.metrics.get("revenue", 0.0),
            roas=result.metrics.get("roas", 0.0),
            ctr=result.metrics.get("ctr", 0.0),
            cvr=result.metrics.get("cvr", 0.0),
            retention=result.metrics.get("retention", 0.0),
            impressions=result.metrics.get("impressions", 0),
            installs=result.metrics.get("installs", 0),
        )

    def _extract_action(self, task: ExecutionTask) -> dict[str, Any]:
        """提取动作描述."""
        action: dict[str, Any] = {
            "task_type": task.task_type.value,
            "target_module": task.target_module.value,
            "priority": task.priority,
        }
        action.update(task.parameters)
        return action

    def _generate_tags(self, task: ExecutionTask, outcome: Outcome) -> list[str]:
        """生成标签."""
        tags = [task.task_type.value, task.target_module.value]
        if outcome == Outcome.SUCCESS:
            tags.append("success")
        elif outcome == Outcome.FAILURE:
            tags.append("failure")
        if task.is_high_priority:
            tags.append("high_priority")
        if task.parameters.get("market"):
            tags.append(f"market:{task.parameters['market']}")
        if task.parameters.get("channel"):
            tags.append(f"channel:{task.parameters['channel']}")
        return tags

    def _generate_summary(self, task: ExecutionTask, outcome: Outcome) -> str:
        """生成经验摘要."""
        status_text = "成功" if outcome == Outcome.SUCCESS else (
            "失败" if outcome == Outcome.FAILURE else "部分完成"
        )
        return f"[{task.task_type.value}] {status_text} — {task.product_id} — {task.strategy_id}"