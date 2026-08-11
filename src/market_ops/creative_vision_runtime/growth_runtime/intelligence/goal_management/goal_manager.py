"""E15.3.3 Goal Manager — 目标管理核心控制器.

整合目标创建、拆解、追踪、评估和调整的完整闭环。

完整流程:
  Create Goal
      ↓
  Decompose → SubGoals
      ↓
  Activate → Operator Loop
      ↓
  Track Progress
      ↓
  Evaluate
      ↓
  Adapt (if needed) → 回到 Decompose
      ↺

用法:
    manager = GoalManager()
    goal = manager.create_goal(name="Increase ROAS", metric="roas", target=0.65, baseline=0.45)
    manager.activate_goal(goal.goal_id)
    subgoals = manager.decompose_goal(goal.goal_id)
    progress = manager.update_progress(goal.goal_id, {"roas": 0.55})
    status = manager.evaluate_goal(goal.goal_id)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .evaluator import GoalEvaluator
from .goal_decomposer import GoalDecomposer
from .goal_store import GoalStore
from .models import (
    Goal,
    GoalAdaptation,
    GoalPriority,
    GoalProgress,
    GoalResult,
    GoalStatus,
    GoalType,
    SubGoal,
)
from .progress_tracker import ProgressTracker


# ═══════════════════════════════════════════════════════════════
# Goal Manager
# ═══════════════════════════════════════════════════════════════


class GoalManager:
    """E15.3.3 目标管理器 — 核心控制器.

    整合目标创建、拆解、追踪、评估和调整。

    用法:
        manager = GoalManager()
        goal = manager.create_goal(
            name="Increase ROAS",
            metric="roas",
            target_value=0.65,
            baseline_value=0.45,
        )
        manager.activate_goal(goal.goal_id)
        manager.decompose_goal(goal.goal_id)
        manager.update_progress(goal.goal_id, {"roas": 0.55})
    """

    def __init__(
        self,
        store: GoalStore | None = None,
        decomposer: GoalDecomposer | None = None,
        tracker: ProgressTracker | None = None,
        evaluator: GoalEvaluator | None = None,
    ):
        self._store = store or GoalStore()
        self._decomposer = decomposer or GoalDecomposer()
        self._tracker = tracker or ProgressTracker()
        self._evaluator = evaluator or GoalEvaluator()
        self._adaptations: list[GoalAdaptation] = []

    # ── Properties ──────────────────────────────────────────────

    @property
    def store(self) -> GoalStore:
        return self._store

    @property
    def decomposer(self) -> GoalDecomposer:
        return self._decomposer

    @property
    def tracker(self) -> ProgressTracker:
        return self._tracker

    @property
    def evaluator(self) -> GoalEvaluator:
        return self._evaluator

    # ── Create Goal ─────────────────────────────────────────────

    def create_goal(
        self,
        name: str,
        metric: str,
        target_value: float,
        baseline_value: float = 0.0,
        current_value: float | None = None,
        description: str = "",
        goal_type: GoalType = GoalType.OPTIMIZATION,
        direction: str = "above",
        priority: GoalPriority = GoalPriority.P3,
        deadline: str = "",
        tags: list[str] | None = None,
        parent_goal: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Goal:
        """创建目标.

        Args:
            name:           目标名称
            metric:         核心指标
            target_value:   目标值
            baseline_value: 基线值
            current_value:  当前值 (默认=baseline)
            description:    目标描述
            goal_type:      目标类型
            direction:      方向
            priority:       优先级
            deadline:       截止时间
            tags:           标签
            parent_goal:    父目标 ID
            metadata:       扩展元数据

        Returns:
            Goal: 创建的目标
        """
        goal = Goal(
            name=name,
            description=description or f"Goal: {name} ({metric}: {baseline_value} → {target_value})",
            type=goal_type,
            metric=metric,
            current_value=current_value if current_value is not None else baseline_value,
            target_value=target_value,
            baseline_value=baseline_value,
            direction=direction,
            priority=priority,
            status=GoalStatus.CREATED,
            deadline=deadline,
            tags=tags or [],
            parent_goal=parent_goal,
            metadata=metadata or {},
        )
        self._store.save_goal(goal)
        self._store.record_history(goal.goal_id, {
            "event": "created",
            "timestamp": goal.created_at,
        })
        return goal

    # ── Activate / Lifecycle ────────────────────────────────────

    def activate_goal(self, goal_id: str) -> bool:
        """激活目标."""
        goal = self._store.get_goal(goal_id)
        if goal is None:
            return False
        if goal.status != GoalStatus.CREATED:
            return False
        goal.status = GoalStatus.ACTIVE
        self._store.record_history(goal_id, {
            "event": "activated",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        return True

    def pause_goal(self, goal_id: str) -> bool:
        """暂停目标."""
        goal = self._store.get_goal(goal_id)
        if goal is None:
            return False
        if goal.status != GoalStatus.ACTIVE:
            return False
        goal.status = GoalStatus.PAUSED
        self._store.record_history(goal_id, {
            "event": "paused",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        return True

    def resume_goal(self, goal_id: str) -> bool:
        """恢复目标."""
        goal = self._store.get_goal(goal_id)
        if goal is None:
            return False
        if goal.status != GoalStatus.PAUSED:
            return False
        goal.status = GoalStatus.ACTIVE
        self._store.record_history(goal_id, {
            "event": "resumed",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        return True

    def cancel_goal(self, goal_id: str) -> bool:
        """取消目标."""
        goal = self._store.get_goal(goal_id)
        if goal is None:
            return False
        goal.status = GoalStatus.CANCELLED
        self._store.record_history(goal_id, {
            "event": "cancelled",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        return True

    # ── Decompose ───────────────────────────────────────────────

    def decompose_goal(self, goal_id: str) -> list[SubGoal]:
        """拆解目标为子目标.

        Args:
            goal_id: 目标 ID

        Returns:
            list[SubGoal]: 子目标列表
        """
        goal = self._store.get_goal(goal_id)
        if goal is None:
            return []

        subgoals = self._decomposer.decompose(goal)
        for sg in subgoals:
            sg.status = GoalStatus.ACTIVE
            self._store.save_subgoal(sg)

        self._store.record_history(goal_id, {
            "event": "decomposed",
            "subgoals_count": len(subgoals),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        return subgoals

    # ── Progress Tracking ───────────────────────────────────────

    def update_progress(
        self, goal_id: str, metrics: dict[str, float]
    ) -> GoalProgress | None:
        """更新目标进度.

        Args:
            goal_id: 目标 ID
            metrics: 当前指标

        Returns:
            GoalProgress | None
        """
        goal = self._store.get_goal(goal_id)
        if goal is None:
            return None

        # 更新目标进度
        progress = self._tracker.track_goal(goal, metrics)

        # 同步更新子目标进度
        subgoals = self._store.get_active_subgoals(goal_id)
        self._tracker.track_all_subgoals(subgoals, metrics)

        self._store.record_history(goal_id, {
            "event": "progress_updated",
            "progress": progress.progress,
            "current": progress.current_value,
            "timestamp": progress.updated_at,
        })
        return progress

    # ── Evaluate ────────────────────────────────────────────────

    def evaluate_goal(self, goal_id: str) -> GoalStatus | None:
        """评估目标状态.

        如果目标被评估为 ACHIEVED 或 FAILED，自动更新目标状态。

        Args:
            goal_id: 目标 ID

        Returns:
            GoalStatus | None
        """
        goal = self._store.get_goal(goal_id)
        if goal is None:
            return None

        progress = self._tracker.get_progress(goal_id)
        status = self._evaluator.evaluate(goal, progress)

        # 自动更新状态
        if status in (GoalStatus.ACHIEVED, GoalStatus.FAILED):
            goal.status = status
            self._store.record_history(goal_id, {
                "event": "evaluated",
                "status": status.value,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

        return status

    def evaluate_subgoals(self, goal_id: str) -> dict[str, GoalStatus] | None:
        """评估子目标状态."""
        subgoals = self._store.get_subgoals(goal_id)
        if not subgoals:
            return None

        results = self._evaluator.evaluate_subgoals(subgoals)

        # 更新子目标状态
        for sg in subgoals:
            status = results.get(sg.subgoal_id)
            if status in (GoalStatus.ACHIEVED, GoalStatus.FAILED):
                sg.status = status

        return results

    def build_result(self, goal_id: str) -> GoalResult | None:
        """构建目标结果."""
        goal = self._store.get_goal(goal_id)
        if goal is None:
            return None
        subgoals = self._store.get_subgoals(goal_id)
        return self._evaluator.build_result(goal, subgoals)

    # ── Adapt ───────────────────────────────────────────────────

    def check_adaptation_needed(self, goal_id: str) -> bool:
        """检查是否需要调整目标策略."""
        goal = self._store.get_goal(goal_id)
        if goal is None:
            return False
        progress = self._tracker.get_progress(goal_id)
        if progress is None:
            return False
        return self._evaluator.needs_adaptation(goal, progress)

    def adapt_goal(
        self,
        goal_id: str,
        reason: str,
        new_target: float | None = None,
        new_strategy: str | None = None,
    ) -> GoalAdaptation | None:
        """调整目标策略.

        当目标进度持续不佳时，调整目标值或重新拆解子目标。

        Args:
            goal_id:      目标 ID
            reason:       调整原因
            new_target:   新目标值 (None=不变)
            new_strategy: 新策略描述

        Returns:
            GoalAdaptation | None
        """
        goal = self._store.get_goal(goal_id)
        if goal is None:
            return None

        previous_target = goal.target_value
        previous_subgoals = [sg.subgoal_id for sg in self._store.get_subgoals(goal_id)]

        adaptation = GoalAdaptation(
            goal_id=goal_id,
            reason=reason,
            previous_target=previous_target,
            new_target=new_target if new_target is not None else previous_target,
            previous_strategy=goal.description,
            new_strategy=new_strategy or goal.description,
            previous_subgoals=previous_subgoals,
        )

        # 更新目标值
        if new_target is not None:
            goal.target_value = new_target

        # 重新拆解子目标
        if new_target is not None or new_strategy is not None:
            # 删除旧子目标
            for sg_id in previous_subgoals:
                self._store.delete_subgoal(sg_id)
            # 重新拆解
            new_subgoals = self._decomposer.decompose(goal)
            for sg in new_subgoals:
                sg.status = GoalStatus.ACTIVE
                self._store.save_subgoal(sg)
            adaptation.new_subgoals = [sg.subgoal_id for sg in new_subgoals]

        self._adaptations.append(adaptation)
        self._store.record_history(goal_id, {
            "event": "adapted",
            "reason": reason,
            "adaptation": adaptation.to_dict(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        return adaptation

    # ── Query ───────────────────────────────────────────────────

    def get_goal(self, goal_id: str) -> Goal | None:
        return self._store.get_goal(goal_id)

    def get_active_goals(self) -> list[Goal]:
        return self._store.get_active_goals()

    def get_all_goals(self) -> list[Goal]:
        return self._store.get_all_goals()

    def get_subgoals(self, goal_id: str) -> list[SubGoal]:
        return self._store.get_subgoals(goal_id)

    def get_progress(self, goal_id: str) -> GoalProgress | None:
        return self._tracker.get_progress(goal_id)

    def get_adaptations(self) -> list[GoalAdaptation]:
        return list(self._adaptations)

    def get_goal_summary(self, goal_id: str) -> dict[str, Any] | None:
        """获取目标完整摘要."""
        goal = self._store.get_goal(goal_id)
        if goal is None:
            return None
        progress = self._tracker.get_progress(goal_id)
        subgoals = self._store.get_subgoals(goal_id)

        return {
            "goal": goal.to_dict(),
            "progress": progress.to_dict() if progress else None,
            "subgoals": [sg.to_dict() for sg in subgoals],
            "subgoals_count": len(subgoals),
            "active_subgoals": len([sg for sg in subgoals if sg.status == GoalStatus.ACTIVE]),
            "completed_subgoals": len([sg for sg in subgoals if sg.status == GoalStatus.ACHIEVED]),
            "adaptations": len(self._adaptations),
            "history": self._store.get_history(goal_id),
        }

    def get_stats(self) -> dict[str, Any]:
        """获取管理器统计."""
        return {
            "store": self._store.get_stats(),
            "adaptations": len(self._adaptations),
            "tracker_count": self._tracker.track_count,
            "evaluator_count": self._evaluator.evaluation_count,
        }


__all__ = ["GoalManager"]