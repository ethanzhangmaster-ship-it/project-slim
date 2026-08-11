"""E15.3.3 Progress Tracker — 进度追踪器.

连接 Reality Layer，持续追踪目标进度。

计算:
  progress = (current - baseline) / (target - baseline)

趋势分析:
  基于历史数据点判断 IMPROVING / STABLE / DECLINING

用法:
    tracker = ProgressTracker()
    progress = tracker.track(goal, current_value=0.55)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .models import (
    Goal,
    GoalProgress,
    GoalStatus,
    ProgressTrend,
    SubGoal,
)


# ═══════════════════════════════════════════════════════════════
# Progress Tracker
# ═══════════════════════════════════════════════════════════════


class ProgressTracker:
    """E15.3.3 进度追踪器 — 追踪目标进度和趋势.

    用法:
        tracker = ProgressTracker()
        progress = tracker.track_goal(goal, metrics={"roas": 0.55})
    """

    def __init__(self, max_trend_points: int = 10):
        self._max_trend_points = max_trend_points
        self._progress_cache: dict[str, GoalProgress] = {}
        self._track_count: int = 0

    # ── Properties ──────────────────────────────────────────────

    @property
    def track_count(self) -> int:
        return self._track_count

    # ── Core: Track Goal ────────────────────────────────────────

    def track_goal(
        self, goal: Goal, metrics: dict[str, float]
    ) -> GoalProgress:
        """追踪目标进度.

        Args:
            goal:    目标
            metrics: 当前指标快照

        Returns:
            GoalProgress: 进度对象
        """
        self._track_count += 1

        current = float(metrics.get(goal.metric, goal.current_value))

        # 更新目标当前值
        goal.current_value = current

        # 计算进度
        progress = goal.progress()

        # 计算剩余差距
        remaining_gap = goal.gap()

        # 更新趋势历史
        cached = self._progress_cache.get(goal.goal_id)
        if cached:
            cached.trend_data.append({
                "value": current,
                "progress": progress,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            if len(cached.trend_data) > self._max_trend_points:
                cached.trend_data = cached.trend_data[-self._max_trend_points:]
        else:
            cached = GoalProgress(
                goal_id=goal.goal_id,
                trend_data=[{
                    "value": current,
                    "progress": progress,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }],
            )

        # 计算趋势
        trend = self._calculate_trend(cached.trend_data)

        # 更新进度对象
        cached.progress = progress
        cached.current_value = current
        cached.target_value = goal.target_value
        cached.baseline_value = goal.baseline_value
        cached.remaining_gap = remaining_gap
        cached.trend = trend
        cached.updated_at = datetime.now(timezone.utc).isoformat()

        # 估算完成时间
        cached.estimated_completion = self._estimate_completion(
            cached.trend_data, goal
        )

        self._progress_cache[goal.goal_id] = cached
        return cached

    def track_subgoal(
        self, subgoal: SubGoal, metrics: dict[str, float]
    ) -> SubGoal:
        """追踪子目标进度.

        Args:
            subgoal: 子目标
            metrics: 当前指标快照

        Returns:
            SubGoal: 更新后的子目标
        """
        current = float(metrics.get(subgoal.metric, subgoal.current_value))
        subgoal.update_progress(current)
        return subgoal

    def track_all_subgoals(
        self, subgoals: list[SubGoal], metrics: dict[str, float]
    ) -> list[SubGoal]:
        """批量追踪子目标."""
        return [self.track_subgoal(sg, metrics) for sg in subgoals]

    # ── Trend Analysis ──────────────────────────────────────────

    def _calculate_trend(self, trend_data: list[dict[str, Any]]) -> ProgressTrend:
        """根据历史数据点计算趋势.

        Args:
            trend_data: 历史数据点

        Returns:
            ProgressTrend: 趋势
        """
        if len(trend_data) < 2:
            return ProgressTrend.UNKNOWN

        # 取最近几个点的进度值
        points = [d["progress"] for d in trend_data]
        recent = points[-3:] if len(points) >= 3 else points

        if len(recent) < 2:
            return ProgressTrend.UNKNOWN

        # 简单线性回归斜率
        n = len(recent)
        x_mean = sum(range(n)) / n
        y_mean = sum(recent) / n

        numerator = sum((i - x_mean) * (recent[i] - y_mean) for i in range(n))
        denominator = sum((i - x_mean) ** 2 for i in range(n))

        if denominator == 0:
            return ProgressTrend.STABLE

        slope = numerator / denominator

        if slope > 0.01:
            return ProgressTrend.IMPROVING
        elif slope < -0.01:
            return ProgressTrend.DECLINING
        return ProgressTrend.STABLE

    def _estimate_completion(
        self, trend_data: list[dict[str, Any]], goal: Goal
    ) -> str | None:
        """估算完成时间.

        Args:
            trend_data: 历史数据点
            goal:       目标

        Returns:
            str | None: 预计完成时间 (ISO 8601)
        """
        if len(trend_data) < 2:
            return None

        # 简单线性外推
        progress_values = [d["progress"] for d in trend_data]
        if len(progress_values) < 2:
            return None

        recent = progress_values[-3:] if len(progress_values) >= 3 else progress_values
        if len(recent) < 2:
            return None

        # 平均变化率
        total_change = recent[-1] - recent[0]
        periods = len(recent) - 1
        if periods == 0 or total_change <= 0:
            return None

        change_per_period = total_change / periods
        remaining = 1.0 - recent[-1]

        if change_per_period <= 0:
            return None

        periods_remaining = remaining / change_per_period

        # 估算时间 (假设每个 period 是 1 天)
        from datetime import timedelta
        estimated = datetime.now(timezone.utc) + timedelta(days=periods_remaining)
        return estimated.isoformat()

    # ── Query ───────────────────────────────────────────────────

    def get_progress(self, goal_id: str) -> GoalProgress | None:
        """获取目标进度."""
        return self._progress_cache.get(goal_id)

    def get_all_progress(self) -> dict[str, GoalProgress]:
        """获取所有进度."""
        return dict(self._progress_cache)

    def get_progress_summary(self, goal_id: str) -> dict[str, Any] | None:
        """获取进度摘要."""
        progress = self._progress_cache.get(goal_id)
        if progress is None:
            return None
        return {
            "goal_id": progress.goal_id,
            "progress": progress.progress,
            "current_value": progress.current_value,
            "remaining_gap": progress.remaining_gap,
            "trend": progress.trend.value,
            "trend_points": len(progress.trend_data),
            "estimated_completion": progress.estimated_completion,
        }

    def get_trend_data(self, goal_id: str) -> list[dict[str, Any]]:
        """获取趋势数据."""
        progress = self._progress_cache.get(goal_id)
        if progress is None:
            return []
        return progress.trend_data

    def reset(self) -> None:
        """重置追踪器."""
        self._progress_cache.clear()
        self._track_count = 0


__all__ = ["ProgressTracker"]