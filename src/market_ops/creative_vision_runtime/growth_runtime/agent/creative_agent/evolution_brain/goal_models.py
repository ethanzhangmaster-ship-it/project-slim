"""E14.8.1 Goal Management — 增长目标管理模型.

E14.8 Autonomous Growth Agent 第一层:
  定义和追踪增长目标，计算目标差距，驱动自主优化循环.

核心模型:
  - GoalPriority: 目标优先级
  - GoalStatus: 目标状态 (active / achieved / failed / paused)
  - GrowthGoal: 增长目标
  - GoalGap: 目标差距分析
  - GoalManager: 目标管理器
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


# ═══════════════════════════════════════════════════════════
# 枚举
# ═══════════════════════════════════════════════════════════

class GoalPriority(str, Enum):
    """目标优先级."""
    CRITICAL = "critical"   # 核心业务指标 (必须达成)
    HIGH = "high"           # 重要目标
    MEDIUM = "medium"       # 一般目标
    LOW = "low"             # 辅助目标


class GoalStatus(str, Enum):
    """目标状态."""
    ACTIVE = "active"           # 进行中
    ACHIEVED = "achieved"       # 已达成
    FAILED = "failed"           # 未达成 (超时)
    PAUSED = "paused"           # 暂停
    CANCELLED = "cancelled"     # 取消


# ═══════════════════════════════════════════════════════════
# 模型
# ═══════════════════════════════════════════════════════════

@dataclass
class GrowthGoal:
    """增长目标 — 定义 Agent 需要优化的业务指标.

    Attributes:
        goal_id: 目标唯一 ID
        name: 目标名称 (如 "D30 ROAS 提升至 1.0")
        metric: 目标指标 (如 "D30_ROAS", "payer_rate", "CPI")
        target_value: 目标值
        current_value: 当前值
        trend: 趋势方向 ("up" / "down" / "stable")
        deadline_days: 截止天数
        priority: 优先级
        status: 目标状态
        tolerance: 容差范围 (如 ±0.05 视为达成)
        created_at: 创建时间
        updated_at: 更新时间
        metadata: 扩展元数据
    """
    goal_id: str = field(default_factory=lambda: f"goal_{uuid.uuid4().hex[:8]}")
    name: str = ""
    metric: str = ""
    target_value: float = 0.0
    current_value: float = 0.0
    trend: str = "stable"
    deadline_days: int = 30
    priority: GoalPriority = GoalPriority.MEDIUM
    status: GoalStatus = GoalStatus.ACTIVE
    tolerance: float = 0.05
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def gap(self) -> float:
        """计算目标差距 (target - current)."""
        return round(self.target_value - self.current_value, 4)

    @property
    def gap_pct(self) -> float:
        """计算目标差距百分比."""
        if self.target_value == 0:
            return 0.0
        return round(self.gap / self.target_value, 4)

    @property
    def is_achieved(self) -> bool:
        """是否已达成."""
        if self.metric.startswith("CPI") or self.metric.startswith("cpi"):
            # CPI 是越低越好
            return self.current_value <= self.target_value + self.tolerance
        return self.current_value >= self.target_value - self.tolerance

    @property
    def is_urgent(self) -> bool:
        """是否紧急 (deadline 不足 7 天)."""
        return self.deadline_days <= 7

    @property
    def direction(self) -> str:
        """优化方向 ('maximize' 或 'minimize')."""
        lower_is_better = {"CPI", "CPA", "CPM", "cpi", "cpa", "cpm"}
        return "minimize" if self.metric in lower_is_better else "maximize"

    def update(self, current_value: float, trend: str = "") -> None:
        """更新当前值."""
        self.current_value = round(current_value, 4)
        if trend:
            self.trend = trend
        self.updated_at = datetime.now(timezone.utc).isoformat()
        if self.is_achieved:
            self.status = GoalStatus.ACHIEVED

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal_id": self.goal_id,
            "name": self.name,
            "metric": self.metric,
            "target_value": self.target_value,
            "current_value": self.current_value,
            "trend": self.trend,
            "gap": self.gap,
            "gap_pct": self.gap_pct,
            "deadline_days": self.deadline_days,
            "priority": self.priority.value,
            "status": self.status.value,
            "is_achieved": self.is_achieved,
            "is_urgent": self.is_urgent,
            "direction": self.direction,
            "tolerance": self.tolerance,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }


@dataclass
class GoalGap:
    """目标差距分析 — 详细的目标差距诊断.

    Attributes:
        goal: 关联的增长目标
        absolute_gap: 绝对差距
        percentage_gap: 百分比差距
        required_improvement: 所需改进幅度
        status_label: 状态标签 (on_track / at_risk / off_track / critical)
        estimated_cycles: 预计所需优化周期
    """
    goal: GrowthGoal
    absolute_gap: float = 0.0
    percentage_gap: float = 0.0
    required_improvement: float = 0.0
    status_label: str = "on_track"
    estimated_cycles: int = 0

    @classmethod
    def analyze(cls, goal: GrowthGoal) -> "GoalGap":
        """分析目标差距."""
        gap = goal.gap
        pct = goal.gap_pct
        improvement = abs(pct)

        # 状态标签
        if goal.is_achieved:
            label = "achieved"
        elif improvement > 0.5:
            label = "critical"
        elif improvement > 0.3:
            label = "off_track"
        elif improvement > 0.15:
            label = "at_risk"
        else:
            label = "on_track"

        # 预计周期 (每个周期改进约 5%)
        improvement_per_cycle = 0.05
        cycles = max(1, int(improvement / improvement_per_cycle))

        return cls(
            goal=goal,
            absolute_gap=gap,
            percentage_gap=pct,
            required_improvement=improvement,
            status_label=label,
            estimated_cycles=cycles,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal_id": self.goal.goal_id,
            "metric": self.goal.metric,
            "absolute_gap": self.absolute_gap,
            "percentage_gap": self.percentage_gap,
            "required_improvement": self.required_improvement,
            "status_label": self.status_label,
            "estimated_cycles": self.estimated_cycles,
        }


# ═══════════════════════════════════════════════════════════
# GoalManager
# ═══════════════════════════════════════════════════════════

class GoalManager:
    """目标管理器 — 管理多个增长目标，追踪进度.

    用法:
        mgr = GoalManager()
        mgr.add_goal(GrowthGoal(metric="D30_ROAS", target_value=1.0, current_value=0.53))
        gaps = mgr.analyze_all_gaps()
    """

    def __init__(self, max_goals: int = 10):
        self._goals: dict[str, GrowthGoal] = {}
        self._max_goals = max_goals
        self._history: list[dict[str, Any]] = []

    def add_goal(self, goal: GrowthGoal) -> str:
        """添加目标."""
        if len(self._goals) >= self._max_goals:
            # 移除最低优先级
            lowest = max(self._goals.values(), key=lambda g: (
                list(GoalPriority).index(g.priority),
            ))
            self._goals.pop(lowest.goal_id, None)
        self._goals[goal.goal_id] = goal
        return goal.goal_id

    def remove_goal(self, goal_id: str) -> bool:
        """移除目标."""
        return self._goals.pop(goal_id, None) is not None

    def get_goal(self, goal_id: str) -> GrowthGoal | None:
        return self._goals.get(goal_id)

    def update_goal(self, goal_id: str, current_value: float, trend: str = "") -> GrowthGoal | None:
        """更新目标当前值."""
        goal = self._goals.get(goal_id)
        if goal is None:
            return None
        self._history.append({
            "goal_id": goal_id,
            "metric": goal.metric,
            "old_value": goal.current_value,
            "new_value": current_value,
            "trend": trend,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        goal.update(current_value, trend)
        return goal

    def get_active_goals(self) -> list[GrowthGoal]:
        """获取所有活跃目标."""
        return [g for g in self._goals.values() if g.status == GoalStatus.ACTIVE]

    def get_by_priority(self, priority: GoalPriority) -> list[GrowthGoal]:
        return [g for g in self._goals.values() if g.priority == priority]

    def get_urgent_goals(self) -> list[GrowthGoal]:
        return [g for g in self._goals.values() if g.is_urgent and g.status == GoalStatus.ACTIVE]

    def get_top_priority_goal(self) -> GrowthGoal | None:
        """获取最高优先级活跃目标."""
        active = self.get_active_goals()
        if not active:
            return None
        return min(active, key=lambda g: list(GoalPriority).index(g.priority))

    def analyze_all_gaps(self) -> list[GoalGap]:
        """分析所有目标的差距."""
        return [GoalGap.analyze(g) for g in self._goals.values()]

    def analyze_gap(self, goal_id: str) -> GoalGap | None:
        """分析单个目标差距."""
        goal = self._goals.get(goal_id)
        if goal is None:
            return None
        return GoalGap.analyze(goal)

    def check_achievements(self) -> list[GrowthGoal]:
        """检查是否有新达成的目标."""
        newly_achieved: list[GrowthGoal] = []
        for goal in self._goals.values():
            if goal.status == GoalStatus.ACTIVE and goal.is_achieved:
                goal.status = GoalStatus.ACHIEVED
                newly_achieved.append(goal)
        return newly_achieved

    def get_stats(self) -> dict[str, Any]:
        """获取目标统计."""
        goals = list(self._goals.values())
        total = len(goals)
        if total == 0:
            return {
                "total_goals": 0,
                "active": 0,
                "achieved": 0,
                "failed": 0,
                "avg_gap_pct": 0.0,
            }
        status_counts = {s.value: 0 for s in GoalStatus}
        for g in goals:
            status_counts[g.status.value] = status_counts.get(g.status.value, 0) + 1
        avg_gap = round(sum(abs(g.gap_pct) for g in goals) / total, 4)

        return {
            "total_goals": total,
            "active": status_counts.get("active", 0),
            "achieved": status_counts.get("achieved", 0),
            "failed": status_counts.get("failed", 0),
            "paused": status_counts.get("paused", 0),
            "avg_gap_pct": avg_gap,
            "history_count": len(self._history),
        }

    @property
    def goal_count(self) -> int:
        return len(self._goals)

    def reset(self) -> None:
        self._goals.clear()
        self._history.clear()


def create_goal_manager(max_goals: int = 10) -> GoalManager:
    """创建默认 GoalManager."""
    return GoalManager(max_goals=max_goals)