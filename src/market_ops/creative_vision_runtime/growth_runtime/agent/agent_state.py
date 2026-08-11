"""E13.7.2 Agent State — 状态管理.

管理 Agent 的运行时状态:
  - 观察状态: 收集和缓存环境观察
  - 目标状态: 管理目标的创建、更新、完成
  - 上下文状态: 维护当前会话上下文
  - 状态转换: 控制 AgentPhase 之间的转换

连接:
  Agent State → Agent Core → Agent Reasoning → Agent Planner
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .agent_models import (
    AgentContext,
    AgentGoal,
    AgentPhase,
    AgentProfile,
    GoalPriority,
    GoalStatus,
    GrowthPlan,
    Insight,
    Observation,
    PlanStatus,
)


# ═══════════════════════════════════════════════════════════════
# Agent State Manager
# ═══════════════════════════════════════════════════════════════


class AgentStateManager:
    """Agent 状态管理器 — 管理 Agent 的完整运行时状态.

    职责:
      1. 观察管理: 收集、存储、检索环境观察
      2. 目标管理: 创建、更新、完成目标
      3. 上下文管理: 维护当前会话上下文
      4. 状态转换: 控制 AgentPhase 转换

    用法:
        state = AgentStateManager(profile=create_growth_agent_profile())
        state.add_observation(observation)
        state.add_goal(goal)
        state.transition(AgentPhase.REASONING)
    """

    MAX_OBSERVATIONS = 100
    MAX_INSIGHTS = 50
    MAX_GOALS = 20

    def __init__(self, profile: AgentProfile | None = None):
        self._profile = profile or AgentProfile()
        self._context = AgentContext(profile=self._profile)

        # 状态存储
        self._observations: list[Observation] = []
        self._insights: list[Insight] = []
        self._goals: list[AgentGoal] = []
        self._plans: list[GrowthPlan] = []

        # 转换日志
        self._phase_history: list[dict[str, Any]] = []

    # ── Properties ────────────────────────────────────────────

    @property
    def context(self) -> AgentContext:
        return self._context

    @property
    def phase(self) -> AgentPhase:
        return self._context.phase

    @property
    def observations(self) -> list[Observation]:
        return list(self._observations)

    @property
    def insights(self) -> list[Insight]:
        return list(self._insights)

    @property
    def goals(self) -> list[AgentGoal]:
        return list(self._goals)

    @property
    def active_goals(self) -> list[AgentGoal]:
        return [g for g in self._goals if g.status == GoalStatus.ACTIVE]

    @property
    def pending_goals(self) -> list[AgentGoal]:
        return [g for g in self._goals if g.status == GoalStatus.PENDING]

    @property
    def plans(self) -> list[GrowthPlan]:
        return list(self._plans)

    # ── 状态转换 ──────────────────────────────────────────────

    def transition(self, new_phase: AgentPhase) -> bool:
        """状态转换 — 验证并执行阶段转换.

        Args:
            new_phase: 目标阶段

        Returns:
            bool: 转换是否成功
        """
        old_phase = self._context.phase

        # 允许的转换
        valid_transitions = {
            AgentPhase.IDLE: {AgentPhase.OBSERVING, AgentPhase.ERROR},
            AgentPhase.OBSERVING: {AgentPhase.REASONING, AgentPhase.ERROR, AgentPhase.IDLE},
            AgentPhase.REASONING: {AgentPhase.PLANNING, AgentPhase.ERROR, AgentPhase.OBSERVING},
            AgentPhase.PLANNING: {AgentPhase.EXECUTING, AgentPhase.ERROR, AgentPhase.REASONING, AgentPhase.WAITING},
            AgentPhase.EXECUTING: {AgentPhase.LEARNING, AgentPhase.ERROR, AgentPhase.WAITING, AgentPhase.OBSERVING},
            AgentPhase.LEARNING: {AgentPhase.IDLE, AgentPhase.OBSERVING, AgentPhase.ERROR},
            AgentPhase.WAITING: {AgentPhase.OBSERVING, AgentPhase.ERROR, AgentPhase.IDLE},
            AgentPhase.ERROR: {AgentPhase.IDLE, AgentPhase.OBSERVING},
        }

        allowed = valid_transitions.get(old_phase, set())
        if new_phase not in allowed:
            return False

        self._phase_history.append({
            "from": old_phase.value,
            "to": new_phase.value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        self._context.phase = new_phase
        self._context.last_active_at = datetime.now(timezone.utc).isoformat()
        return True

    def can_transition(self, new_phase: AgentPhase) -> bool:
        """检查是否可以转换到目标阶段."""
        allowed = {
            AgentPhase.IDLE: {AgentPhase.OBSERVING, AgentPhase.ERROR},
            AgentPhase.OBSERVING: {AgentPhase.REASONING, AgentPhase.ERROR, AgentPhase.IDLE},
            AgentPhase.REASONING: {AgentPhase.PLANNING, AgentPhase.ERROR, AgentPhase.OBSERVING},
            AgentPhase.PLANNING: {AgentPhase.EXECUTING, AgentPhase.ERROR, AgentPhase.REASONING, AgentPhase.WAITING},
            AgentPhase.EXECUTING: {AgentPhase.LEARNING, AgentPhase.ERROR, AgentPhase.WAITING, AgentPhase.OBSERVING},
            AgentPhase.LEARNING: {AgentPhase.IDLE, AgentPhase.OBSERVING, AgentPhase.ERROR},
            AgentPhase.WAITING: {AgentPhase.OBSERVING, AgentPhase.ERROR, AgentPhase.IDLE},
            AgentPhase.ERROR: {AgentPhase.IDLE, AgentPhase.OBSERVING},
        }
        return new_phase in allowed.get(self._context.phase, set())

    def get_phase_history(self) -> list[dict[str, Any]]:
        return list(self._phase_history)

    # ── 观察管理 ──────────────────────────────────────────────

    def add_observation(self, observation: Observation) -> None:
        """添加观察."""
        self._observations.append(observation)
        if len(self._observations) > self.MAX_OBSERVATIONS:
            self._observations = self._observations[-self.MAX_OBSERVATIONS:]

        self._context.recent_observations = self._observations[-10:]

    def get_recent_observations(self, n: int = 10) -> list[Observation]:
        """获取最近 N 条观察."""
        return self._observations[-n:]

    def get_observations_by_source(self, source: str) -> list[Observation]:
        """按来源获取观察."""
        return [o for o in self._observations if o.source == source]

    def get_observations_by_phase(self, phase: AgentPhase) -> list[Observation]:
        """按阶段获取观察."""
        return [o for o in self._observations if o.phase == phase]

    # ── 洞察管理 ──────────────────────────────────────────────

    def add_insight(self, insight: Insight) -> None:
        """添加洞察."""
        self._insights.append(insight)
        if len(self._insights) > self.MAX_INSIGHTS:
            self._insights = self._insights[-self.MAX_INSIGHTS:]

        self._context.recent_insights = self._insights[-10:]

    def get_recent_insights(self, n: int = 10) -> list[Insight]:
        """获取最近 N 条洞察."""
        return self._insights[-n:]

    def get_high_confidence_insights(self, threshold: float = 0.7) -> list[Insight]:
        """获取高置信度洞察."""
        return [i for i in self._insights if i.confidence >= threshold]

    def get_urgent_insights(self, threshold: float = 0.7) -> list[Insight]:
        """获取紧急洞察."""
        return [i for i in self._insights if i.urgency >= threshold]

    # ── 目标管理 ──────────────────────────────────────────────

    def add_goal(self, goal: AgentGoal) -> None:
        """添加目标."""
        if len(self._goals) >= self.MAX_GOALS:
            self._goals = self._goals[-(self.MAX_GOALS - 1):]
        self._goals.append(goal)
        self._context.active_goals = self.active_goals

    def update_goal(self, goal_id: str, **updates) -> bool:
        """更新目标."""
        for goal in self._goals:
            if goal.goal_id == goal_id:
                for key, value in updates.items():
                    if hasattr(goal, key):
                        setattr(goal, key, value)
                return True
        return False

    def complete_goal(self, goal_id: str) -> bool:
        """完成目标."""
        return self.update_goal(
            goal_id,
            status=GoalStatus.COMPLETED,
            completed_at=datetime.now(timezone.utc).isoformat(),
        )

    def fail_goal(self, goal_id: str) -> bool:
        """标记目标失败."""
        return self.update_goal(
            goal_id,
            status=GoalStatus.FAILED,
            completed_at=datetime.now(timezone.utc).isoformat(),
        )

    def get_goal(self, goal_id: str) -> AgentGoal | None:
        """获取目标."""
        for g in self._goals:
            if g.goal_id == goal_id:
                return g
        return None

    def get_goals_by_priority(self, priority: GoalPriority) -> list[AgentGoal]:
        """按优先级获取目标."""
        return [g for g in self._goals if g.priority == priority]

    def get_goals_by_status(self, status: GoalStatus) -> list[AgentGoal]:
        """按状态获取目标."""
        return [g for g in self._goals if g.status == status]

    # ── 计划管理 ──────────────────────────────────────────────

    def add_plan(self, plan: GrowthPlan) -> None:
        """添加计划."""
        self._plans.append(plan)
        self._context.active_plans = [
            p for p in self._plans
            if p.status in {PlanStatus.DRAFT, PlanStatus.APPROVED, PlanStatus.EXECUTING}
        ]

    def update_plan(self, plan_id: str, **updates) -> bool:
        """更新计划."""
        for plan in self._plans:
            if plan.plan_id == plan_id:
                for key, value in updates.items():
                    if hasattr(plan, key):
                        setattr(plan, key, value)
                return True
        return False

    def get_plan(self, plan_id: str) -> GrowthPlan | None:
        """获取计划."""
        for p in self._plans:
            if p.plan_id == plan_id:
                return p
        return None

    def get_active_plans(self) -> list[GrowthPlan]:
        """获取活动计划."""
        return [
            p for p in self._plans
            if p.status in {PlanStatus.APPROVED, PlanStatus.EXECUTING}
        ]

    # ── 指标快照 ──────────────────────────────────────────────

    def update_metrics(self, metrics: dict[str, Any]) -> None:
        """更新指标快照."""
        self._context.metrics_snapshot = metrics

    def get_metric(self, key: str, default: Any = None) -> Any:
        """获取单个指标."""
        return self._context.metrics_snapshot.get(key, default)

    # ── 循环管理 ──────────────────────────────────────────────

    def increment_cycle(self) -> int:
        """递增循环计数."""
        self._context.cycle_count += 1
        return self._context.cycle_count

    # ── 统计 ──────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        return {
            "phase": self._context.phase.value,
            "cycle_count": self._context.cycle_count,
            "observation_count": len(self._observations),
            "insight_count": len(self._insights),
            "goal_count": len(self._goals),
            "active_goal_count": len(self.active_goals),
            "plan_count": len(self._plans),
            "active_plan_count": len(self.get_active_plans()),
            "phase_history": self._phase_history[-10:],
        }

    def reset(self) -> None:
        """重置状态."""
        self._observations.clear()
        self._insights.clear()
        self._goals.clear()
        self._plans.clear()
        self._phase_history.clear()
        self._context = AgentContext(profile=self._profile)