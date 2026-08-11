"""E15.3.2 Learner — 连接 Decision Loop 与 E15.1.5 Memory Feedback.

将决策周期的执行结果转换为经验，通过 MemoryFeedbackBridge 存入记忆系统。

流程:
  DecisionCycle + ExecutionResult
      ↓
  Learner.learn(cycle, result)
      ↓
  build Experience
      ↓
  E15.1.5 MemoryFeedbackBridge
      ↓
  Pattern Memory Update
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from .models import (
    CycleOutcome,
    CycleResult,
    DecisionCycle,
)


# ═══════════════════════════════════════════════════════════════
# Learner
# ═══════════════════════════════════════════════════════════════


class Learner:
    """E15.3.2 学习器 — 连接 Decision Loop 与 Memory Feedback.

    将每个决策周期的执行结果转化为经验，存入记忆系统。

    用法:
        learner = Learner(memory_bridge)
        experience = learner.learn(cycle, cycle_result)
    """

    def __init__(self, memory_bridge: Any = None):
        """初始化.

        Args:
            memory_bridge: E15.1.5 MemoryFeedbackBridge 实例 (可选)
        """
        self._memory_bridge = memory_bridge
        self._learn_count: int = 0
        self._experience_count: int = 0
        self._experiences: list[dict[str, Any]] = []

    # ── Properties ──────────────────────────────────────────────

    @property
    def learn_count(self) -> int:
        return self._learn_count

    @property
    def experience_count(self) -> int:
        return self._experience_count

    # ── Core: Learn ─────────────────────────────────────────────

    def learn(
        self,
        cycle: DecisionCycle,
        cycle_result: CycleResult,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """从决策周期中学习.

        Args:
            cycle:        决策周期
            cycle_result: 周期结果
            context:      额外上下文

        Returns:
            dict: 学习经验
        """
        self._learn_count += 1

        # 构建经验
        experience = self._build_experience(cycle, cycle_result, context)

        # 存储经验
        self._experience_count += 1
        self._experiences.append(experience)

        # 如果有 MemoryBridge，通过它存储
        if self._memory_bridge is not None:
            try:
                self._store_via_bridge(cycle, cycle_result, experience)
            except Exception:
                pass  # Bridge 存储失败不阻塞

        return experience

    def learn_batch(
        self,
        results: list[tuple[DecisionCycle, CycleResult]],
        context: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """批量学习.

        Args:
            results: (cycle, cycle_result) 列表
            context: 额外上下文

        Returns:
            list[dict]: 学习经验列表
        """
        return [self.learn(cycle, result, context) for cycle, result in results]

    # ── Experience Building ─────────────────────────────────────

    def _build_experience(
        self,
        cycle: DecisionCycle,
        cycle_result: CycleResult,
        context: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """构建经验记录."""
        # 提取关键指标变化
        metrics_delta = {}
        for key in set(cycle_result.metrics_before) | set(cycle_result.metrics_after):
            before = cycle_result.metrics_before.get(key, 0)
            after = cycle_result.metrics_after.get(key, 0)
            metrics_delta[key] = after - before

        # 生成经验教训
        lesson = self._generate_lesson(cycle_result)

        return {
            "experience_id": str(uuid.uuid4()),
            "cycle_id": cycle.cycle_id,
            "cycle_number": cycle.cycle_number,
            "operator_id": cycle.operator_id,
            "action_type": cycle_result.action_taken,
            "action": cycle.selected_action,
            "outcome": cycle_result.outcome.value,
            "reward": cycle_result.reward,
            "metrics_before": cycle_result.metrics_before,
            "metrics_after": cycle_result.metrics_after,
            "metrics_delta": metrics_delta,
            "lesson": lesson,
            "lessons": cycle_result.lessons,
            "context": context or {},
            "duration_seconds": cycle_result.duration_seconds,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _generate_lesson(self, cycle_result: CycleResult) -> str:
        """生成经验教训."""
        if cycle_result.outcome == CycleOutcome.SUCCESS:
            return (
                f"Action '{cycle_result.action_taken}' succeeded "
                f"with reward {cycle_result.reward:.2f}"
            )
        if cycle_result.outcome == CycleOutcome.PARTIAL:
            return (
                f"Action '{cycle_result.action_taken}' partially succeeded "
                f"(reward={cycle_result.reward:.2f})"
            )
        if cycle_result.outcome == CycleOutcome.FAILURE:
            return (
                f"Action '{cycle_result.action_taken}' failed "
                f"(reward={cycle_result.reward:.2f})"
            )
        if cycle_result.outcome == CycleOutcome.ERROR:
            return f"Action '{cycle_result.action_taken}' encountered error"
        return f"No action taken (cycle #{cycle_result.cycle_number})"

    def _store_via_bridge(
        self,
        cycle: DecisionCycle,
        cycle_result: CycleResult,
        experience: dict[str, Any],
    ) -> None:
        """通过 MemoryFeedbackBridge 存储经验."""
        # 尝试构建 ExecutionResult 并存储
        if hasattr(self._memory_bridge, "process_execution_result"):
            from ...workflow.memory_bridge import ExecutionResult, ExecutionStatus

            status = ExecutionStatus.SUCCESS
            if cycle_result.outcome == CycleOutcome.FAILURE:
                status = ExecutionStatus.FAILED
            elif cycle_result.outcome == CycleOutcome.PARTIAL:
                status = ExecutionStatus.PARTIAL

            exec_result = ExecutionResult(
                result_id=experience["experience_id"],
                workflow_id=cycle.cycle_id,
                workflow_name=f"decision_cycle_{cycle.cycle_number}",
                action_type=cycle_result.action_taken,
                status=status,
                context=experience.get("context", {}),
                metrics_before=cycle_result.metrics_before,
                metrics_after=cycle_result.metrics_after,
                duration_ms=cycle_result.duration_seconds * 1000,
                error=cycle.error or "",
            )
            self._memory_bridge.process_execution_result(exec_result)

    # ── Query ───────────────────────────────────────────────────

    def get_experiences(self, limit: int = 50) -> list[dict[str, Any]]:
        """获取最近的经验."""
        return self._experiences[-limit:]

    def get_stats(self) -> dict[str, Any]:
        """获取学习统计."""
        if not self._experiences:
            return {
                "learn_count": self._learn_count,
                "experience_count": self._experience_count,
                "avg_reward": 0.0,
                "success_rate": 0.0,
            }
        rewards = [e["reward"] for e in self._experiences]
        success_count = sum(
            1 for e in self._experiences if e["outcome"] == "success"
        )
        return {
            "learn_count": self._learn_count,
            "experience_count": self._experience_count,
            "avg_reward": round(sum(rewards) / len(rewards), 4),
            "success_rate": round(success_count / len(self._experiences), 4),
            "has_memory_bridge": self._memory_bridge is not None,
        }

    def get_top_lessons(self, n: int = 5) -> list[str]:
        """获取 Top N 经验教训."""
        lessons = [e["lesson"] for e in self._experiences if e["lesson"]]
        return lessons[-n:]

    def reset(self) -> None:
        """重置学习器."""
        self._learn_count = 0
        self._experience_count = 0
        self._experiences = []


__all__ = ["Learner"]