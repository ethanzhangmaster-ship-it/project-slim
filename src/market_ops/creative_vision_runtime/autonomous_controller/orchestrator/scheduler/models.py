"""E11.7.1 — Runtime Scheduler Models。

EvolutionTask:  调度最小单元
TaskStatus:     任务状态机
TaskFactory:    将 EvolutionPolicyDecision 转换为 EvolutionTask
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class TaskStatus(str, Enum):
    """任务状态机。

    PENDING → QUEUED → RUNNING → COMPLETED
                              → FAILED → RETRY → QUEUED
                              → CANCELLED
    """
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# 合法状态转换
VALID_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.PENDING: {TaskStatus.QUEUED, TaskStatus.CANCELLED},
    TaskStatus.QUEUED: {TaskStatus.RUNNING, TaskStatus.CANCELLED},
    TaskStatus.RUNNING: {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED},
    TaskStatus.FAILED: {TaskStatus.QUEUED},  # RETRY → 重新入队
    TaskStatus.COMPLETED: set(),  # 终态
    TaskStatus.CANCELLED: set(),  # 终态
}


@dataclass
class EvolutionTask:
    """调度最小单元。

    Attributes:
        task_id:              任务 ID
        genome_id:            Genome ID
        action:               进化动作（来自 Policy）
        mutation_strategy:    突变策略（来自 Policy）
        priority:             优先级（越高越优先）
        status:               任务状态
        created_at:           创建时间
        started_at:           开始时间
        completed_at:         完成时间
        retry_count:          重试次数
        max_retries:          最大重试次数
        error:                错误信息
        metadata:             附加元数据
    """

    task_id: str = ""
    genome_id: str = ""
    action: str = ""
    mutation_strategy: str = ""
    priority: int = 0
    status: TaskStatus = TaskStatus.PENDING
    created_at: str = ""
    started_at: str | None = None
    completed_at: str | None = None
    retry_count: int = 0
    max_retries: int = 3
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.task_id:
            self.task_id = f"et_{uuid.uuid4().hex[:12]}"
        if not self.created_at:
            self.created_at = _now()

    # ── 属性 ──────────────────────────────────────────

    @property
    def is_terminal(self) -> bool:
        """是否处于终态（COMPLETED / CANCELLED）。"""
        return self.status in (TaskStatus.COMPLETED, TaskStatus.CANCELLED)

    @property
    def is_running(self) -> bool:
        return self.status == TaskStatus.RUNNING

    @property
    def is_queued(self) -> bool:
        return self.status == TaskStatus.QUEUED

    @property
    def can_retry(self) -> bool:
        return self.retry_count < self.max_retries

    @property
    def duration(self) -> float | None:
        """运行时长（秒）。"""
        if self.started_at and self.completed_at:
            start = datetime.fromisoformat(self.started_at)
            end = datetime.fromisoformat(self.completed_at)
            return (end - start).total_seconds()
        return None

    # ── 状态转换方法 ──────────────────────────────────

    def transition_to(self, new_status: TaskStatus) -> bool:
        """尝试状态转换，返回是否成功。"""
        if new_status not in VALID_TRANSITIONS.get(self.status, set()):
            return False
        self.status = new_status
        if new_status == TaskStatus.RUNNING and self.started_at is None:
            self.started_at = _now()
        if new_status in (TaskStatus.COMPLETED, TaskStatus.CANCELLED):
            self.completed_at = _now()
        return True

    def mark_running(self) -> bool:
        return self.transition_to(TaskStatus.RUNNING)

    def mark_completed(self) -> bool:
        return self.transition_to(TaskStatus.COMPLETED)

    def mark_failed(self, error: str = "") -> bool:
        self.error = error
        return self.transition_to(TaskStatus.FAILED)

    def mark_cancelled(self) -> bool:
        return self.transition_to(TaskStatus.CANCELLED)

    def mark_retry(self) -> bool:
        """从 FAILED 重试（重新入队）。"""
        if not self.can_retry:
            return False
        self.retry_count += 1
        self.error = None
        return self.transition_to(TaskStatus.QUEUED)

    # ── 序列化 ────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "genome_id": self.genome_id,
            "action": self.action,
            "mutation_strategy": self.mutation_strategy,
            "priority": self.priority,
            "status": self.status.value,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "error": self.error,
            "metadata": self.metadata,
        }

    def __repr__(self) -> str:
        return (
            f"EvolutionTask({self.task_id}, "
            f"genome={self.genome_id}, "
            f"action={self.action}, "
            f"status={self.status.value}, "
            f"priority={self.priority})"
        )


class TaskFactory:
    """将 EvolutionPolicyDecision 转换为 EvolutionTask。"""

    # action → priority 基础映射
    ACTION_PRIORITY_MAP: dict[str, int] = {
        "retire": 100,
        "exploit": 80,
        "mutate": 60,
        "explore": 40,
        "keep": 10,
        "crossover": 70,
    }

    @staticmethod
    def create(
        decision: Any,  # EvolutionPolicyDecision
        priority: int | None = None,
        max_retries: int = 3,
        metadata: dict[str, Any] | None = None,
    ) -> EvolutionTask:
        """从 PolicyDecision 创建 EvolutionTask。

        Args:
            decision:    EvolutionPolicyDecision
            priority:    显式优先级（可选，默认从 action 推导）
            max_retries: 最大重试次数
            metadata:    附加元数据

        Returns:
            EvolutionTask
        """
        if priority is None:
            priority = TaskFactory.ACTION_PRIORITY_MAP.get(
                decision.action.value if hasattr(decision.action, 'value') else str(decision.action),
                50,
            )

        return EvolutionTask(
            genome_id=decision.genome_id,
            action=decision.action.value if hasattr(decision.action, 'value') else str(decision.action),
            mutation_strategy=(
                decision.mutation_strategy.value
                if hasattr(decision.mutation_strategy, 'value')
                else str(decision.mutation_strategy)
            ),
            priority=priority,
            max_retries=max_retries,
            metadata=metadata or {
                "decision_id": getattr(decision, "decision_id", ""),
                "confidence": getattr(decision, "confidence", 0.0),
                "mutation_rate": getattr(decision, "mutation_rate", 0.0),
                "target_genes": getattr(decision, "target_genes", []),
            },
        )

    @staticmethod
    def create_batch(
        decisions: list[Any],
        priorities: dict[str, int] | None = None,
        max_retries: int = 3,
    ) -> list[EvolutionTask]:
        """批量创建任务。"""
        prio_map = priorities or {}
        return [
            TaskFactory.create(
                d,
                priority=prio_map.get(d.genome_id),
                max_retries=max_retries,
            )
            for d in decisions
        ]