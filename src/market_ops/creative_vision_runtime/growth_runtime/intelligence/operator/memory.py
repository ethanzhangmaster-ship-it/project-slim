"""E15.3.1 Operator Memory Bridge — 记忆桥接.

连接 E15.1.5 Memory Feedback，将 Operator 经验写入 Pattern Memory。

方向:
  OperatorCycleResult → OperatorExperience → Experience Store → Pattern Memory
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .models import CycleOutcome, OperatorCycleResult, OperatorExperience, OperatorGoal


# ═══════════════════════════════════════════════════════════════
# Memory Bridge
# ═══════════════════════════════════════════════════════════════


class OperatorMemoryBridge:
    """E15.3.1 记忆桥接.

    将 Operator 运行周期结果转换为经验，存入记忆系统。

    用法:
        bridge = OperatorMemoryBridge()
        experience = bridge.record(cycle_result, goal)
        bridge.get_experiences()
    """

    def __init__(self):
        self._experiences: list[OperatorExperience] = []

    def record(
        self,
        cycle_result: OperatorCycleResult,
        goal: OperatorGoal | None = None,
    ) -> OperatorExperience:
        """记录一条经验.

        Args:
            cycle_result: 运行周期结果
            goal:         相关目标

        Returns:
            OperatorExperience
        """
        # 计算 reward
        reward = self._calculate_reward(cycle_result, goal)

        # 提取教训
        lesson = self._extract_lesson(cycle_result, goal)

        experience = OperatorExperience(
            goal=goal.name if goal else "",
            action=cycle_result.action,
            result=cycle_result.result,
            outcome=cycle_result.outcome.value,
            reward=reward,
            lesson=lesson,
            context={
                "cycle_number": cycle_result.cycle_number,
                "triggered_by": cycle_result.triggered_by,
                "decision": cycle_result.decision,
                "error": cycle_result.error,
            },
        )

        self._experiences.append(experience)
        return experience

    def record_direct(
        self,
        goal: str,
        action: dict[str, Any],
        result: dict[str, Any],
        outcome: str,
        reward: float = 0.0,
        lesson: str = "",
    ) -> OperatorExperience:
        """直接记录经验 (无需 CycleResult).

        Args:
            goal:    目标名称
            action:  执行动作
            result:  执行结果
            outcome: 结果
            reward:  奖励值
            lesson:  经验教训

        Returns:
            OperatorExperience
        """
        experience = OperatorExperience(
            goal=goal,
            action=action,
            result=result,
            outcome=outcome,
            reward=reward,
            lesson=lesson,
        )
        self._experiences.append(experience)
        return experience

    def get_experiences(self) -> list[OperatorExperience]:
        """获取所有经验."""
        return list(self._experiences)

    def get_recent(self, count: int = 10) -> list[OperatorExperience]:
        """获取最近经验."""
        return self._experiences[-count:]

    def get_by_outcome(self, outcome: str) -> list[OperatorExperience]:
        """按结果获取经验."""
        return [e for e in self._experiences if e.outcome == outcome]

    def get_successful(self) -> list[OperatorExperience]:
        """获取成功经验."""
        return [e for e in self._experiences if e.outcome == CycleOutcome.SUCCESS.value]

    def get_failed(self) -> list[OperatorExperience]:
        """获取失败经验."""
        return [e for e in self._experiences if e.outcome == CycleOutcome.FAILURE.value]

    def get_summary(self) -> dict[str, Any]:
        """获取经验摘要."""
        total = len(self._experiences)
        if total == 0:
            return {"total": 0, "success_rate": 0.0, "avg_reward": 0.0}

        successes = len(self.get_successful())
        failures = len(self.get_failed())
        rewards = [e.reward for e in self._experiences]

        return {
            "total": total,
            "successes": successes,
            "failures": failures,
            "success_rate": round(successes / total, 4),
            "avg_reward": round(sum(rewards) / len(rewards), 4),
            "max_reward": max(rewards) if rewards else 0,
        }

    def clear(self) -> None:
        """清空经验."""
        self._experiences.clear()

    # ── Internal ────────────────────────────────────────────────

    def _calculate_reward(
        self,
        cycle_result: OperatorCycleResult,
        goal: OperatorGoal | None,
    ) -> float:
        """计算奖励值.

        规则:
          - SUCCESS: 0.8 + goal_progress × 0.2
          - FAILURE: 0.0
          - NO_ACTION: 0.3
          - ERROR: 0.0
        """
        if cycle_result.outcome == CycleOutcome.SUCCESS:
            progress = goal.progress if goal else 0.5
            return round(0.8 + progress * 0.2, 4)
        elif cycle_result.outcome == CycleOutcome.FAILURE:
            return 0.0
        elif cycle_result.outcome == CycleOutcome.NO_ACTION:
            return 0.3
        else:
            return 0.0

    def _extract_lesson(
        self,
        cycle_result: OperatorCycleResult,
        goal: OperatorGoal | None,
    ) -> str:
        """提取经验教训."""
        if cycle_result.outcome == CycleOutcome.SUCCESS:
            action_type = cycle_result.action.get("action_type", "unknown")
            return (
                f"Action '{action_type}' succeeded for goal "
                f"'{goal.name if goal else 'unknown'}'"
            )
        elif cycle_result.outcome == CycleOutcome.FAILURE:
            reason = cycle_result.error or "unknown reason"
            return f"Cycle failed: {reason}"
        elif cycle_result.outcome == CycleOutcome.NO_ACTION:
            return "No action required — conditions not met"
        else:
            return f"Error: {cycle_result.error or 'unknown'}"


__all__ = ["OperatorMemoryBridge"]