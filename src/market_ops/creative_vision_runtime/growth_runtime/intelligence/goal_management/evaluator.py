"""E15.3.3 Goal Evaluator — 目标评估器.

判断目标最终状态:
  - 成功: current >= target (above) / current <= target (below)
  - 失败: deadline 到达且 progress < threshold
  - 继续: 未到期且未达成

用法:
    evaluator = GoalEvaluator()
    status = evaluator.evaluate(goal, progress)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .models import (
    Goal,
    GoalProgress,
    GoalResult,
    GoalStatus,
    ProgressTrend,
    SubGoal,
)


# ═══════════════════════════════════════════════════════════════
# Goal Evaluator
# ═══════════════════════════════════════════════════════════════


class GoalEvaluator:
    """E15.3.3 目标评估器 — 评估目标是否达成/失败/继续.

    评估规则:
      - current >= target (above) → ACHIEVED
      - deadline passed AND progress < 0.8 → FAILED
      - deadline passed AND progress >= 0.8 → ACHIEVED (近完成)
      - 否则 → CONTINUE (保持 ACTIVE)

    用法:
        evaluator = GoalEvaluator()
        status = evaluator.evaluate(goal, progress)
    """

    # 阈值
    ACHIEVEMENT_THRESHOLD = 0.95  # 达成阈值 (>= 95% 视为达成)
    FAILURE_THRESHOLD = 0.5       # 失败阈值 (到期时 < 50% 视为失败)
    PARTIAL_THRESHOLD = 0.8       # 部分成功阈值

    def __init__(
        self,
        achievement_threshold: float = 0.95,
        failure_threshold: float = 0.5,
        partial_threshold: float = 0.8,
    ):
        self._achievement_threshold = achievement_threshold
        self._failure_threshold = failure_threshold
        self._partial_threshold = partial_threshold
        self._evaluation_count: int = 0

    # ── Properties ──────────────────────────────────────────────

    @property
    def evaluation_count(self) -> int:
        return self._evaluation_count

    # ── Core: Evaluate ──────────────────────────────────────────

    def evaluate(
        self, goal: Goal, progress: GoalProgress | None = None
    ) -> GoalStatus:
        """评估目标状态.

        Args:
            goal:     目标
            progress: 进度 (可选)

        Returns:
            GoalStatus: 应设置的目标状态
        """
        self._evaluation_count += 1

        # 检查是否已达目标值
        if goal.is_achieved():
            return GoalStatus.ACHIEVED

        # 检查进度是否达到阈值
        current_progress = goal.progress()
        if current_progress >= self._achievement_threshold:
            return GoalStatus.ACHIEVED

        # 检查是否过期
        if goal.is_expired():
            if current_progress >= self._partial_threshold:
                return GoalStatus.ACHIEVED  # 到期但接近完成
            if current_progress >= self._failure_threshold:
                return GoalStatus.FAILED
            return GoalStatus.FAILED

        return GoalStatus.ACTIVE

    def evaluate_with_progress(
        self, goal: Goal, progress: GoalProgress
    ) -> GoalStatus:
        """使用进度对象评估."""
        return self.evaluate(goal, progress)

    def evaluate_batch(self, goals: list[Goal]) -> dict[str, GoalStatus]:
        """批量评估."""
        return {g.goal_id: self.evaluate(g) for g in goals}

    # ── SubGoal Evaluation ──────────────────────────────────────

    def evaluate_subgoal(self, subgoal: SubGoal) -> GoalStatus:
        """评估子目标状态."""
        if subgoal.is_achieved():
            return GoalStatus.ACHIEVED
        if subgoal.progress >= self._achievement_threshold:
            return GoalStatus.ACHIEVED
        return GoalStatus.ACTIVE

    def evaluate_subgoals(
        self, subgoals: list[SubGoal]
    ) -> dict[str, GoalStatus]:
        """批量评估子目标."""
        return {sg.subgoal_id: self.evaluate_subgoal(sg) for sg in subgoals}

    # ── Result Building ─────────────────────────────────────────

    def build_result(
        self, goal: Goal, subgoals: list[SubGoal]
    ) -> GoalResult:
        """构建目标结果摘要.

        Args:
            goal:     目标
            subgoals: 子目标列表

        Returns:
            GoalResult: 目标结果
        """
        final_status = self.evaluate(goal)

        # 达成率
        achievement_rate = goal.progress()

        # 子目标完成情况
        subgoals_completed = sum(1 for sg in subgoals if sg.status == GoalStatus.ACHIEVED)
        subgoals_total = len(subgoals)

        # 耗时
        from datetime import datetime, timezone
        try:
            created = datetime.fromisoformat(goal.created_at)
            now = datetime.now(timezone.utc)
            duration_days = (now - created).total_seconds() / 86400
        except (ValueError, TypeError):
            duration_days = 0.0

        # 经验教训
        lessons = self._extract_lessons(goal, final_status, achievement_rate)

        return GoalResult(
            goal_id=goal.goal_id,
            goal_name=goal.name,
            status=final_status,
            final_value=goal.current_value,
            target_value=goal.target_value,
            achievement_rate=round(achievement_rate, 4),
            duration_days=round(duration_days, 1),
            subgoals_completed=subgoals_completed,
            subgoals_total=subgoals_total,
            lessons=lessons,
        )

    def _extract_lessons(
        self, goal: Goal, status: GoalStatus, achievement_rate: float
    ) -> list[str]:
        """提取经验教训."""
        lessons: list[str] = []
        if status == GoalStatus.ACHIEVED:
            lessons.append(
                f"Goal '{goal.name}' achieved at {achievement_rate:.1%} "
                f"({goal.metric}: {goal.current_value:.2f} vs target {goal.target_value:.2f})"
            )
        elif status == GoalStatus.FAILED:
            gap = goal.gap()
            lessons.append(
                f"Goal '{goal.name}' failed (gap={gap:.1%}, "
                f"current={goal.current_value:.2f}, target={goal.target_value:.2f})"
            )
            lessons.append("Consider adjusting strategy or decomposing differently")
        return lessons

    # ── Need Adaptation Check ────────────────────────────────────

    def needs_adaptation(
        self, goal: Goal, progress: GoalProgress, max_stagnant_periods: int = 3
    ) -> bool:
        """判断是否需要调整目标策略.

        条件:
          - 趋势持续下降
          - 进度停滞超过 max_stagnant_periods 个周期
          - 剩余时间不足

        Args:
            goal:                 目标
            progress:             进度
            max_stagnant_periods: 最大停滞周期

        Returns:
            bool: 是否需要调整
        """
        if progress.trend == ProgressTrend.DECLINING:
            return True

        # 检查停滞
        if len(progress.trend_data) >= max_stagnant_periods:
            recent = progress.trend_data[-max_stagnant_periods:]
            progress_values = [p["progress"] for p in recent]
            if max(progress_values) - min(progress_values) < 0.02:
                return True

        # 检查紧急度
        if progress.remaining_gap > 0.5 and progress.trend != ProgressTrend.IMPROVING:
            return True

        return False


__all__ = ["GoalEvaluator"]