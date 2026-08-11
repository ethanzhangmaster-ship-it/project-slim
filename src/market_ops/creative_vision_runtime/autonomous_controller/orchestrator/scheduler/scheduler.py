"""E11.7.1 — Evolution Runtime Scheduler。

核心调度器：管理 EvolutionTask 的生命周期。

职责：
  - 提交任务（submit / submit_policy / submit_policies / submit_population_decision）
  - 获取下一任务（next）
  - 完成任务（complete）
  - 失败处理（fail → 自动重试）
  - 取消任务（cancel）
  - 并发控制（max_parallel）
  - Tick 驱动（tick）
  - 回调机制（on_execute）
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from .models import EvolutionTask, TaskStatus, TaskFactory
from .priority_queue import EvolutionPriorityQueue
from ..budget.budget_manager import EvolutionBudgetManager
from ..budget.models import BudgetDecision
from ..population.models import PopulationDecision
from ..population.population_manager import PopulationEvolutionManager

logger = logging.getLogger(__name__)

# 回调类型
TaskCallback = Callable[[EvolutionTask], None]


class EvolutionScheduler:
    """Evolution Runtime Scheduler。

    管理进化任务的生命周期调度。

    Attributes:
        max_parallel:     最大并行任务数
        max_retries:      默认最大重试次数
        executor:         执行回调
        on_complete:      完成回调
        on_fail:          失败回调
        on_cancel:        取消回调
    """

    def __init__(
        self,
        max_parallel: int = 5,
        max_retries: int = 3,
        executor: TaskCallback | None = None,
        on_complete: TaskCallback | None = None,
        on_fail: TaskCallback | None = None,
        on_cancel: TaskCallback | None = None,
        budget_manager: EvolutionBudgetManager | None = None,
        population_manager: PopulationEvolutionManager | None = None,
    ) -> None:
        self._max_parallel = max_parallel
        self._max_retries = max_retries
        self._executor = executor
        self._on_complete = on_complete
        self._on_fail = on_fail
        self._on_cancel = on_cancel
        self._queue = EvolutionPriorityQueue()
        self._running: dict[str, EvolutionTask] = {}
        self._history: dict[str, EvolutionTask] = {}  # task_id → task
        self._submit_count: int = 0
        self._complete_count: int = 0
        self._fail_count: int = 0
        self._retry_count: int = 0
        self._budget_manager = budget_manager
        self._population_manager = population_manager

    # ── 提交 ──────────────────────────────────────────────

    def submit(self, task: EvolutionTask) -> str:
        """提交任务到队列。

        先检查预算（如果配置了 budget_manager），
        再检查优先级（确保不挤占已有任务）。

        Returns:
            task_id（如果被预算拒绝则返回空字符串）
        """
        # 预算检查
        if self._budget_manager is not None:
            if not self._budget_manager.can_execute():
                logger.warning(
                    f"Task {task.task_id} rejected by budget manager"
                )
                return ""

        task.status = TaskStatus.QUEUED
        self._queue.push(task)
        self._history[task.task_id] = task
        self._submit_count += 1

        # 记录预算消耗
        if self._budget_manager is not None:
            self._budget_manager.consume()

        return task.task_id

    def submit_policy(self, decision: Any) -> str:
        """从 PolicyDecision 创建并提交任务。

        Returns:
            task_id
        """
        task = TaskFactory.create(decision, max_retries=self._max_retries)
        return self.submit(task)

    def submit_policies(self, decisions: list[Any]) -> list[str]:
        """批量提交 PolicyDecision。"""
        task_ids: list[str] = []
        for decision in decisions:
            task_id = self.submit_policy(decision)
            task_ids.append(task_id)
        return task_ids

    def submit_population_decision(
        self,
        decision: PopulationDecision,
    ) -> dict[str, Any]:
        """将 PopulationDecision 转换为 N 个 EvolutionTask 并提交。

        转换规则：
          - elite → keep 任务（优先级 10）
          - mutate → mutate 任务（优先级 60）
          - explore → explore 任务（优先级 40）
          - retire → retire 任务（优先级 100）

        Args:
            decision: PopulationDecision

        Returns:
            {
                "elite_tasks": list[str],
                "mutate_tasks": list[str],
                "explore_tasks": list[str],
                "retire_tasks": list[str],
                "total_tasks": int,
                "rejected_count": int,
            }
        """
        result: dict[str, Any] = {
            "elite_tasks": [],
            "mutate_tasks": [],
            "explore_tasks": [],
            "retire_tasks": [],
            "total_tasks": 0,
            "rejected_count": 0,
        }

        def _submit_genome_task(
            genome_id: str, action: str, strategy: str, priority: int
        ) -> str | None:
            """提交单个 genome 任务。"""
            task = EvolutionTask(
                genome_id=genome_id,
                action=action,
                mutation_strategy=strategy,
                priority=priority,
                max_retries=self._max_retries,
                metadata={
                    "decision_id": decision.decision_id,
                    "generation": decision.generation,
                    "source": "population_decision",
                },
            )
            task_id = self.submit(task)
            if task_id:
                return task_id
            else:
                result["rejected_count"] += 1
                return None

        # Elite → keep
        for genome_id in decision.elite:
            tid = _submit_genome_task(genome_id, "keep", "elite_preserve", 10)
            if tid:
                result["elite_tasks"].append(tid)

        # Mutate → mutate
        for genome_id in decision.mutate:
            tid = _submit_genome_task(genome_id, "mutate", "adaptive", 60)
            if tid:
                result["mutate_tasks"].append(tid)

        # Explore → explore
        for genome_id in decision.explore:
            tid = _submit_genome_task(genome_id, "explore", "forced_exploration", 40)
            if tid:
                result["explore_tasks"].append(tid)

        # Retire → retire
        for genome_id in decision.retire:
            tid = _submit_genome_task(genome_id, "retire", "retire", 100)
            if tid:
                result["retire_tasks"].append(tid)

        result["total_tasks"] = (
            len(result["elite_tasks"])
            + len(result["mutate_tasks"])
            + len(result["explore_tasks"])
            + len(result["retire_tasks"])
        )

        return result

    # ── 调度 ──────────────────────────────────────────────

    def next(self) -> EvolutionTask | None:
        """获取下一个待执行任务。

        从队列中取出最高优先级任务，状态变为 RUNNING。

        Returns:
            EvolutionTask 或 None（无可用任务或已达并行上限）
        """
        if self.available_slots == 0:
            return None
        task = self._queue.pop()
        if task is None:
            return None
        task.mark_running()
        self._running[task.task_id] = task
        return task

    def complete(self, task_id: str) -> bool:
        """完成任务。

        Returns:
            True 如果成功，False 如果任务不在运行中。
        """
        task = self._running.pop(task_id, None)
        if task is None:
            return False
        task.mark_completed()
        self._complete_count += 1
        if self._budget_manager is not None:
            self._budget_manager.complete()
        if self._on_complete:
            self._on_complete(task)
        return True

    def fail(self, task_id: str, error: str = "") -> bool:
        """任务失败处理。

        自动重试逻辑：
          - 未达最大重试次数 → 重新入队
          - 已达最大重试次数 → 保持 FAILED 状态

        Returns:
            True 如果处理成功。
        """
        task = self._running.pop(task_id, None)
        if task is None:
            return False

        task.mark_failed(error)
        self._fail_count += 1

        if task.can_retry:
            # 降低优先级后重试
            task.priority = max(0, task.priority - 10)
            task.mark_retry()
            self._queue.push(task)
            self._retry_count += 1
            logger.info(
                f"Task {task_id} retrying (attempt {task.retry_count}/{task.max_retries})"
            )
        else:
            logger.warning(
                f"Task {task_id} exceeded max retries ({task.max_retries}), permanently failed"
            )

        if self._on_fail:
            self._on_fail(task)
        return True

    def cancel(self, task_id: str) -> bool:
        """取消任务。

        支持取消 Running 和 Queued 状态的任务。

        Returns:
            True 如果成功取消。
        """
        # 从 running 中移除
        task = self._running.pop(task_id, None)
        if task is not None:
            task.mark_cancelled()
            if self._on_cancel:
                self._on_cancel(task)
            return True

        # 从队列中查找
        task = self._get_task_by_id(task_id)
        if task is not None and task.is_queued:
            task.mark_cancelled()
            self._queue.remove_by_genome(task.genome_id)
            if self._on_cancel:
                self._on_cancel(task)
            return True

        return False

    # ── Tick ──────────────────────────────────────────────

    def tick(self) -> list[EvolutionTask]:
        """一次 tick：从队列中取出可执行的任务。

        一次至多取出 available_slots 个任务。

        Returns:
            新开始执行的任务列表。
        """
        started: list[EvolutionTask] = []
        for _ in range(self.available_slots):
            task = self.next()
            if task is None:
                break
            if self._executor:
                try:
                    self._executor(task)
                except Exception as e:
                    logger.error(f"Executor error for task {task.task_id}: {e}")
                    self.fail(task.task_id, str(e))
                    continue
            started.append(task)
        return started

    def tick_all(self) -> list[EvolutionTask]:
        """持续 tick 直到队列为空或达到并行上限。"""
        all_started: list[EvolutionTask] = []
        while True:
            batch = self.tick()
            if not batch:
                break
            all_started.extend(batch)
        return all_started

    # ── 查询 ──────────────────────────────────────────────

    def get_task(self, task_id: str) -> EvolutionTask | None:
        """获取任务（先查 running，再查 history）。"""
        task = self._running.get(task_id)
        if task is not None:
            return task
        return self._history.get(task_id)

    def get_running_tasks(self) -> list[EvolutionTask]:
        return list(self._running.values())

    def get_queue_size(self) -> int:
        return self._queue.size()

    def get_pending_count(self) -> int:
        """获取等待中的任务数（队列 + running）。"""
        return self._queue.size() + len(self._running)

    def get_tasks_by_genome(self, genome_id: str) -> list[EvolutionTask]:
        """按 genome_id 查找所有历史上的任务。"""
        return [
            t for t in self._history.values() if t.genome_id == genome_id
        ]

    def get_tasks_by_status(self, status: TaskStatus) -> list[EvolutionTask]:
        """按状态查找任务。"""
        return [
            t for t in self._history.values() if t.status == status
        ]

    # ── 属性 ──────────────────────────────────────────────

    @property
    def available_slots(self) -> int:
        return max(0, self._max_parallel - len(self._running))

    @property
    def running_count(self) -> int:
        return len(self._running)

    @property
    def submit_count(self) -> int:
        return self._submit_count

    @property
    def complete_count(self) -> int:
        return self._complete_count

    @property
    def fail_count(self) -> int:
        return self._fail_count

    @property
    def retry_count(self) -> int:
        return self._retry_count

    @property
    def budget_manager(self) -> EvolutionBudgetManager | None:
        return self._budget_manager

    @property
    def population_manager(self) -> PopulationEvolutionManager | None:
        return self._population_manager

    # ── 内部 ──────────────────────────────────────────────

    def _get_task_by_id(self, task_id: str) -> EvolutionTask | None:
        """从队列中按 task_id 查找。"""
        for item in self._queue._heap:
            if item[3].task_id == task_id:
                return item[3]
        return None

    # ── Stats ─────────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        return {
            "queue_size": self._queue.size(),
            "running_count": len(self._running),
            "available_slots": self.available_slots,
            "max_parallel": self._max_parallel,
            "submit_count": self._submit_count,
            "complete_count": self._complete_count,
            "fail_count": self._fail_count,
            "retry_count": self._retry_count,
            "history_size": len(self._history),
        }

    def reset(self) -> None:
        self._queue.clear()
        self._running.clear()
        self._history.clear()
        self._submit_count = 0
        self._complete_count = 0
        self._fail_count = 0
        self._retry_count = 0

    def __repr__(self) -> str:
        return (
            f"EvolutionScheduler(queue={self._queue.size()}, "
            f"running={len(self._running)}, "
            f"slots={self.available_slots}/{self._max_parallel})"
        )