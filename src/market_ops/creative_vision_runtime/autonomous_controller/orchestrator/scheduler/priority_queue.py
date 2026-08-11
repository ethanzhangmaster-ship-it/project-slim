"""E11.7.1 — Evolution Priority Queue。

基于 heapq 的优先级队列，按 priority 降序排列。

优先级规则：
  - priority 越高越优先
  - 同 priority 时按创建时间 FIFO
"""

from __future__ import annotations

import heapq
import logging
from typing import Any

from .models import EvolutionTask

logger = logging.getLogger(__name__)


class EvolutionPriorityQueue:
    """进化任务优先级队列。

    使用 heapq 最小堆 + 负 priority 实现最大堆语义。

    Attributes:
        push_count: 入队次数
        pop_count:  出队次数
    """

    def __init__(self) -> None:
        self._heap: list[tuple[int, int, int, EvolutionTask]] = []
        self._counter: int = 0  # 全局递增计数器保证 FIFO
        self._push_count: int = 0
        self._pop_count: int = 0

    # ── 核心操作 ──────────────────────────────────────────

    def push(self, task: EvolutionTask) -> None:
        """入队。

        内部使用 (-priority, counter, id_counter, task) 保证：
          - priority 越高越先出
          - 同 priority 先入先出
        """
        # 负号：高 priority → 小 heap value → 先 pop
        heapq.heappush(
            self._heap,
            (-task.priority, self._counter, self._counter, task),
        )
        self._counter += 1
        self._push_count += 1

    def pop(self) -> EvolutionTask | None:
        """出队：返回最高优先级的任务，无任务时返回 None。"""
        if not self._heap:
            return None
        _, _, _, task = heapq.heappop(self._heap)
        self._pop_count += 1
        return task

    def peek(self) -> EvolutionTask | None:
        """查看最高优先级任务但不移除。"""
        if not self._heap:
            return None
        return self._heap[0][3]

    # ── 批量操作 ──────────────────────────────────────────

    def push_batch(self, tasks: list[EvolutionTask]) -> None:
        """批量入队。"""
        for task in tasks:
            self.push(task)

    def pop_batch(self, n: int) -> list[EvolutionTask]:
        """批量出队最多 n 个。"""
        results: list[EvolutionTask] = []
        for _ in range(n):
            task = self.pop()
            if task is None:
                break
            results.append(task)
        return results

    def pop_all(self) -> list[EvolutionTask]:
        """出队全部任务。"""
        results: list[EvolutionTask] = []
        while self._heap:
            task = self.pop()
            if task:
                results.append(task)
        return results

    # ── 查询操作 ──────────────────────────────────────────

    def size(self) -> int:
        return len(self._heap)

    def is_empty(self) -> bool:
        return len(self._heap) == 0

    def clear(self) -> None:
        self._heap.clear()
        self._counter = 0

    def get_all(self) -> list[EvolutionTask]:
        """获取所有任务（按优先级降序，不移除）。"""
        return sorted(
            [item[3] for item in self._heap],
            key=lambda t: (-t.priority, t.created_at),
        )

    def get_by_genome(self, genome_id: str) -> list[EvolutionTask]:
        """按 genome_id 查找队列中的任务。"""
        return [item[3] for item in self._heap if item[3].genome_id == genome_id]

    def remove_by_genome(self, genome_id: str) -> int:
        """按 genome_id 移除队列中的任务，返回移除数量。"""
        original_size = len(self._heap)
        self._heap = [
            item for item in self._heap if item[3].genome_id != genome_id
        ]
        heapq.heapify(self._heap)
        return original_size - len(self._heap)

    def has_genome(self, genome_id: str) -> bool:
        """检查队列中是否有指定 genome 的任务。"""
        return any(item[3].genome_id == genome_id for item in self._heap)

    # ── Stats ─────────────────────────────────────────────

    @property
    def push_count(self) -> int:
        return self._push_count

    @property
    def pop_count(self) -> int:
        return self._pop_count

    def get_stats(self) -> dict[str, Any]:
        return {
            "size": self.size(),
            "push_count": self._push_count,
            "pop_count": self._pop_count,
        }

    def reset_stats(self) -> None:
        self._push_count = 0
        self._pop_count = 0

    def __repr__(self) -> str:
        return (
            f"EvolutionPriorityQueue(size={self.size()}, "
            f"push={self._push_count}, pop={self._pop_count})"
        )

    def __len__(self) -> int:
        return self.size()