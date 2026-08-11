"""E15.3.3 Goal Store — 目标存储层.

管理目标的持久化存储和检索。

用法:
    store = GoalStore()
    store.save(goal)
    goals = store.get_active_goals()
"""

from __future__ import annotations

from typing import Any

from .models import Goal, GoalStatus, GoalPriority, SubGoal


# ═══════════════════════════════════════════════════════════════
# Goal Store
# ═══════════════════════════════════════════════════════════════


class GoalStore:
    """E15.3.3 目标存储 — 内存存储层.

    管理 Goal 和 SubGoal 的 CRUD 操作。
    后续可替换为 PostgreSQL/Redis 持久化存储。

    用法:
        store = GoalStore()
        store.save_goal(goal)
        active = store.get_active_goals()
    """

    def __init__(self):
        self._goals: dict[str, Goal] = {}
        self._subgoals: dict[str, list[SubGoal]] = {}  # goal_id → subgoals
        self._goal_history: dict[str, list[dict[str, Any]]] = {}

    # ── Goal CRUD ───────────────────────────────────────────────

    def save_goal(self, goal: Goal) -> Goal:
        """保存目标."""
        self._goals[goal.goal_id] = goal
        return goal

    def get_goal(self, goal_id: str) -> Goal | None:
        """获取目标."""
        return self._goals.get(goal_id)

    def get_all_goals(self) -> list[Goal]:
        """获取所有目标."""
        return list(self._goals.values())

    def get_active_goals(self) -> list[Goal]:
        """获取活跃目标."""
        return [g for g in self._goals.values() if g.status == GoalStatus.ACTIVE]

    def get_goals_by_type(self, goal_type: str) -> list[Goal]:
        """按类型获取目标."""
        return [g for g in self._goals.values() if g.type.value == goal_type]

    def get_goals_by_priority(self, min_priority: int = 3) -> list[Goal]:
        """按优先级获取目标 (数值越小优先级越高)."""
        return [
            g for g in self._goals.values()
            if g.status == GoalStatus.ACTIVE and g.priority.value <= min_priority
        ]

    def get_goals_by_tag(self, tag: str) -> list[Goal]:
        """按标签获取目标."""
        return [g for g in self._goals.values() if tag in g.tags]

    def update_goal(self, goal_id: str, **kwargs: Any) -> Goal | None:
        """更新目标字段."""
        goal = self._goals.get(goal_id)
        if goal is None:
            return None
        for key, value in kwargs.items():
            if hasattr(goal, key):
                setattr(goal, key, value)
        return goal

    def delete_goal(self, goal_id: str) -> bool:
        """删除目标."""
        if goal_id in self._goals:
            del self._goals[goal_id]
            self._subgoals.pop(goal_id, None)
            return True
        return False

    def exists(self, goal_id: str) -> bool:
        """检查目标是否存在."""
        return goal_id in self._goals

    def count(self) -> int:
        """获取目标总数."""
        return len(self._goals)

    def count_active(self) -> int:
        """获取活跃目标数."""
        return len(self.get_active_goals())

    # ── SubGoal CRUD ────────────────────────────────────────────

    def save_subgoal(self, subgoal: SubGoal) -> SubGoal:
        """保存子目标."""
        if subgoal.parent_goal_id not in self._subgoals:
            self._subgoals[subgoal.parent_goal_id] = []
        # 替换或追加
        for i, sg in enumerate(self._subgoals[subgoal.parent_goal_id]):
            if sg.subgoal_id == subgoal.subgoal_id:
                self._subgoals[subgoal.parent_goal_id][i] = subgoal
                return subgoal
        self._subgoals[subgoal.parent_goal_id].append(subgoal)
        return subgoal

    def get_subgoals(self, goal_id: str) -> list[SubGoal]:
        """获取目标的子目标列表."""
        return self._subgoals.get(goal_id, [])

    def get_active_subgoals(self, goal_id: str) -> list[SubGoal]:
        """获取目标的活跃子目标."""
        return [
            sg for sg in self.get_subgoals(goal_id)
            if sg.status == GoalStatus.ACTIVE
        ]

    def get_subgoal(self, subgoal_id: str) -> SubGoal | None:
        """获取单个子目标."""
        for subgoals in self._subgoals.values():
            for sg in subgoals:
                if sg.subgoal_id == subgoal_id:
                    return sg
        return None

    def update_subgoal(self, subgoal_id: str, **kwargs: Any) -> SubGoal | None:
        """更新子目标字段."""
        sg = self.get_subgoal(subgoal_id)
        if sg is None:
            return None
        for key, value in kwargs.items():
            if hasattr(sg, key):
                setattr(sg, key, value)
        return sg

    def delete_subgoal(self, subgoal_id: str) -> bool:
        """删除子目标."""
        for goal_id, subgoals in self._subgoals.items():
            for i, sg in enumerate(subgoals):
                if sg.subgoal_id == subgoal_id:
                    self._subgoals[goal_id].pop(i)
                    return True
        return False

    def count_subgoals(self, goal_id: str) -> int:
        """获取某目标的子目标数."""
        return len(self.get_subgoals(goal_id))

    def get_all_subgoals(self) -> list[SubGoal]:
        """获取所有子目标."""
        all_sg: list[SubGoal] = []
        for subgoals in self._subgoals.values():
            all_sg.extend(subgoals)
        return all_sg

    # ── History ─────────────────────────────────────────────────

    def record_history(self, goal_id: str, event: dict[str, Any]) -> None:
        """记录目标历史事件."""
        if goal_id not in self._goal_history:
            self._goal_history[goal_id] = []
        self._goal_history[goal_id].append(event)

    def get_history(self, goal_id: str) -> list[dict[str, Any]]:
        """获取目标历史."""
        return self._goal_history.get(goal_id, [])

    # ── Query ───────────────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        """获取存储统计."""
        goals = self.get_all_goals()
        status_counts: dict[str, int] = {}
        for g in goals:
            s = g.status.value
            status_counts[s] = status_counts.get(s, 0) + 1

        return {
            "total_goals": len(goals),
            "active_goals": self.count_active(),
            "total_subgoals": len(self.get_all_subgoals()),
            "status_counts": status_counts,
        }

    def clear(self) -> None:
        """清空存储."""
        self._goals.clear()
        self._subgoals.clear()
        self._goal_history.clear()


__all__ = ["GoalStore"]