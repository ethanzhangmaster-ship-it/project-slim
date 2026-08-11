"""E15.3.1 Goal Manager — 目标管理器.

管理 Operator 的长期目标:
  - 创建/更新/删除目标
  - 基于观察更新进度
  - 判断达成/失败/过期
  - 目标优先级排序
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .models import GoalStatus, OperatorGoal, OperatorObservation


# ═══════════════════════════════════════════════════════════════
# Goal Manager
# ═══════════════════════════════════════════════════════════════


class GoalManager:
    """E15.3.1 目标管理器.

    管理多个 Operator 目标，基于观察数据更新进度。

    用法:
        mgr = GoalManager()
        mgr.add_goal(goal)
        mgr.update_from_observation(observation)
        achieved = mgr.get_achieved()
    """

    def __init__(self):
        self._goals: dict[str, OperatorGoal] = {}

    # ── CRUD ────────────────────────────────────────────────────

    def add_goal(self, goal: OperatorGoal) -> None:
        """添加目标."""
        self._goals[goal.goal_id] = goal

    def remove_goal(self, goal_id: str) -> bool:
        """删除目标."""
        if goal_id in self._goals:
            del self._goals[goal_id]
            return True
        return False

    def get_goal(self, goal_id: str) -> OperatorGoal | None:
        """获取目标."""
        return self._goals.get(goal_id)

    def get_all_goals(self) -> list[OperatorGoal]:
        """获取所有目标."""
        return list(self._goals.values())

    def get_active_goals(self) -> list[OperatorGoal]:
        """获取活跃目标 (按优先级排序)."""
        active = [g for g in self._goals.values() if g.status == GoalStatus.ACTIVE]
        priority_order = {"high": 0, "medium": 1, "low": 2}
        active.sort(key=lambda g: priority_order.get(g.priority, 2))
        return active

    def get_goals_by_metric(self, metric: str) -> list[OperatorGoal]:
        """按指标获取目标."""
        return [g for g in self._goals.values() if g.metric == metric]

    # ── Progress Update ─────────────────────────────────────────

    def update_from_observation(self, observation: OperatorObservation) -> list[OperatorGoal]:
        """基于观察更新所有相关目标进度.

        Args:
            observation: 环境观察

        Returns:
            list[OperatorGoal]: 进度发生变化的目标
        """
        updated: list[OperatorGoal] = []

        for metric_name, value in observation.metrics.items():
            for goal in self._goals.values():
                if goal.metric != metric_name:
                    continue
                if goal.status != GoalStatus.ACTIVE:
                    continue

                old_progress = goal.progress
                goal.update_progress(value)

                if goal.progress != old_progress:
                    updated.append(goal)

                # 检查是否达成
                if goal.is_achieved():
                    goal.status = GoalStatus.ACHIEVED

        return updated

    def update_goal(self, goal_id: str, current_value: float) -> OperatorGoal | None:
        """手动更新单个目标.

        Args:
            goal_id:       目标 ID
            current_value: 当前值

        Returns:
            OperatorGoal | None
        """
        goal = self._goals.get(goal_id)
        if goal is None:
            return None
        if goal.status != GoalStatus.ACTIVE:
            return goal

        goal.update_progress(current_value)

        if goal.is_achieved():
            goal.status = GoalStatus.ACHIEVED

        return goal

    # ── Status Evaluation ───────────────────────────────────────

    def evaluate_all(self) -> dict[str, list[OperatorGoal]]:
        """评估所有目标状态.

        Returns:
            {"achieved": [...], "failed": [...], "active": [...], "expired": [...]}
        """
        self._check_expired()

        result: dict[str, list[OperatorGoal]] = {
            "achieved": [],
            "failed": [],
            "active": [],
            "expired": [],
        }

        for goal in self._goals.values():
            if goal.status == GoalStatus.ACHIEVED:
                result["achieved"].append(goal)
            elif goal.status == GoalStatus.FAILED:
                result["failed"].append(goal)
            elif goal.status == GoalStatus.EXPIRED:
                result["expired"].append(goal)
            else:
                result["active"].append(goal)

        return result

    def get_achieved(self) -> list[OperatorGoal]:
        """获取已达成目标."""
        return [g for g in self._goals.values() if g.status == GoalStatus.ACHIEVED]

    def get_failed(self) -> list[OperatorGoal]:
        """获取已失败目标."""
        return [g for g in self._goals.values() if g.status == GoalStatus.FAILED]

    def mark_failed(self, goal_id: str, reason: str = "") -> OperatorGoal | None:
        """标记目标为失败."""
        goal = self._goals.get(goal_id)
        if goal is None:
            return None
        goal.status = GoalStatus.FAILED
        if reason:
            goal.metadata["failure_reason"] = reason
        return goal

    def pause_goal(self, goal_id: str) -> OperatorGoal | None:
        """暂停目标."""
        goal = self._goals.get(goal_id)
        if goal is None:
            return None
        if goal.status == GoalStatus.ACTIVE:
            goal.status = GoalStatus.PAUSED
        return goal

    def resume_goal(self, goal_id: str) -> OperatorGoal | None:
        """恢复目标."""
        goal = self._goals.get(goal_id)
        if goal is None:
            return None
        if goal.status == GoalStatus.PAUSED:
            goal.status = GoalStatus.ACTIVE
        return goal

    def get_goal_count(self) -> int:
        """获取目标总数."""
        return len(self._goals)

    def get_progress_summary(self) -> dict[str, Any]:
        """获取进度摘要."""
        evaluation = self.evaluate_all()
        return {
            "total": len(self._goals),
            "active": len(evaluation["active"]),
            "achieved": len(evaluation["achieved"]),
            "failed": len(evaluation["failed"]),
            "expired": len(evaluation["expired"]),
            "overall_progress": self._overall_progress(),
        }

    # ── Internal ────────────────────────────────────────────────

    def _check_expired(self) -> None:
        """检查过期目标."""
        now = datetime.now(timezone.utc)
        for goal in self._goals.values():
            if goal.status != GoalStatus.ACTIVE:
                continue
            if not goal.deadline:
                continue
            try:
                deadline = datetime.fromisoformat(goal.deadline)
                if now > deadline:
                    goal.status = GoalStatus.EXPIRED
            except ValueError:
                pass

    def _overall_progress(self) -> float:
        """整体进度."""
        active = self.get_active_goals()
        if not active:
            achieved = self.get_achieved()
            total = len(self._goals)
            if total == 0:
                return 0.0
            return round(len(achieved) / total, 4)
        return round(sum(g.progress for g in active) / len(active), 4)


__all__ = ["GoalManager"]