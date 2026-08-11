"""E14.2.6 Supervisor Agent — 增长主管 Agent.

Supervisor 是多 Agent 组织的核心:

    输入: Business Goal (e.g. "本月利润提升30%")
    输出: 协调整合的 Agent 任务分配和执行监控

核心循环:
  1. Goal Manager: 解析目标 → 分解为子目标
  2. Priority Engine: 评估信号优先级
  3. Task Allocator: 分配任务给 Agent
  4. Conflict Resolver: 处理 Agent 冲突
  5. Supervisor Memory: 记录组织学习

设计原则:
  - Supervisor 不直接执行，只协调
  - 所有决策可追溯
  - 支持多种管理模式 (自动/半自动/手动)
  - 组织学习持续改进
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from ..communication.agent_message import (
    AgentIdentity,
    AgentRole,
    AgentMessage,
    MessagePriority,
    StandardMessageType,
    create_supervisor_agent_identity,
)
from ..communication.agent_registry import AgentRegistry, AgentStatus
from ..communication.message_bus import MessageBus
from ..communication.collaboration import CollaborationEngine
from ..communication.task_protocol import TaskStatus
from .goal_manager import (
    GoalManager,
    GrowthGoal,
    GoalType,
    GoalStatus,
    GoalConstraint,
    SubGoal,
    create_goal_manager,
)
from .priority_engine import (
    PriorityEngine,
    PrioritySignal,
    PriorityDecision,
    SignalCategory,
    SignalSeverity,
    create_priority_engine,
)
from .task_allocator import (
    TaskAllocator,
    AllocationRecord,
    AllocationStatus,
    create_task_allocator,
)
from .conflict_resolver import (
    ConflictResolver,
    Conflict,
    ConflictType,
    ConflictParty,
    ResolutionStrategy,
    create_conflict_resolver,
)
from .supervisor_memory import (
    SupervisorMemory,
    OrganizationMemory,
    MemoryType,
    create_supervisor_memory,
)


# ═══════════════════════════════════════════════════════════════
# Supervisor Models
# ═══════════════════════════════════════════════════════════════


class SupervisorMode(str, Enum):
    """Supervisor 运行模式."""
    FULL_AUTO = "full_auto"          # 全自动: 自动分解+分配+解决
    SEMI_AUTO = "semi_auto"          # 半自动: 自动分配, 冲突需审批
    ADVISORY = "advisory"            # 建议模式: 仅建议, 不执行
    MANUAL = "manual"                # 手动: 所有决策需人工确认


class SupervisorState(str, Enum):
    """Supervisor 状态."""
    IDLE = "idle"
    PLANNING = "planning"            # 目标分解中
    DISPATCHING = "dispatching"      # 任务分配中
    MONITORING = "monitoring"        # 监控中
    RESOLVING = "resolving"          # 冲突解决中
    LEARNING = "learning"            # 学习中
    ERROR = "error"


@dataclass
class SupervisorReport:
    """Supervisor 运行报告.

    Attributes:
        report_id: 报告 ID
        cycle_id: 循环 ID
        active_goals: 活跃目标
        tasks_dispatched: 已分配任务数
        conflicts_resolved: 已解决冲突数
        agent_performances: Agent 绩效
        organization_health: 组织健康度
        recommendations: 建议
        created_at: 报告时间
        metadata: 扩展元数据
    """
    report_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    cycle_id: str = ""
    active_goals: list[dict[str, Any]] = field(default_factory=list)
    tasks_dispatched: int = 0
    conflicts_resolved: int = 0
    agent_performances: dict[str, Any] = field(default_factory=dict)
    organization_health: dict[str, Any] = field(default_factory=dict)
    recommendations: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "cycle_id": self.cycle_id,
            "active_goals": self.active_goals,
            "tasks_dispatched": self.tasks_dispatched,
            "conflicts_resolved": self.conflicts_resolved,
            "agent_performances": self.agent_performances,
            "organization_health": self.organization_health,
            "recommendations": self.recommendations,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }


# ═══════════════════════════════════════════════════════════════
# Supervisor Agent
# ═══════════════════════════════════════════════════════════════


class SupervisorAgent:
    """增长主管 Agent — 多 Agent 组织的协调者.

    职责:
      1. 接收 Business Goal
      2. 分解目标为 Agent 级子目标
      3. 分配任务给各专业 Agent
      4. 监控执行进度
      5. 处理 Agent 间冲突
      6. 记录组织学习
      7. 生成运行报告

    用法:
        supervisor = SupervisorAgent(bus, registry)
        supervisor.run_cycle("本月利润提升30%")
        report = supervisor.generate_report()
    """

    def __init__(
        self,
        bus: MessageBus | None = None,
        registry: AgentRegistry | None = None,
        collab: CollaborationEngine | None = None,
        mode: SupervisorMode = SupervisorMode.FULL_AUTO,
    ):
        self._identity = create_supervisor_agent_identity()
        self._bus = bus or MessageBus()
        self._registry = registry or AgentRegistry()
        self._collab = collab or CollaborationEngine(bus=self._bus, registry=self._registry)
        self._mode = mode

        # 子模块
        self._goal_manager = create_goal_manager()
        self._priority_engine = create_priority_engine()
        self._task_allocator = create_task_allocator(self._registry, self._bus)
        self._conflict_resolver = create_conflict_resolver(self._collab)
        self._memory = create_supervisor_memory()

        # 运行时状态
        self._state = SupervisorState.IDLE
        self._cycle_count: int = 0
        self._reports: list[SupervisorReport] = []
        self._active_signals: list[PrioritySignal] = []

    # ── 核心循环 ──────────────────────────────────────────────

    def run_cycle(
        self,
        business_goal: str | None = None,
        signals: list[PrioritySignal] | None = None,
        goal_type: GoalType = GoalType.PROFIT,
        target_value: float = 0.3,
        constraints: GoalConstraint | None = None,
    ) -> SupervisorReport:
        """执行一个完整 Supervisor 循环.

        Args:
            business_goal: 业务目标 (None = 仅处理信号)
            signals: 外部信号
            goal_type: 目标类型
            target_value: 目标值
            constraints: 约束条件

        Returns:
            SupervisorReport: 运行报告
        """
        self._cycle_count += 1
        cycle_id = str(uuid.uuid4())

        # Phase 1: 目标分解
        if business_goal:
            self._state = SupervisorState.PLANNING
            goal, sub_goals = self._decompose_goal(
                business_goal, goal_type, target_value, constraints
            )
        else:
            goal = None
            sub_goals = []

        # Phase 2: 信号处理
        if signals:
            self._active_signals.extend(signals)

        if self._active_signals:
            self._state = SupervisorState.PLANNING
            priority_decision = self._priority_engine.rank(self._active_signals)
            self._active_signals = []  # 已处理
        else:
            priority_decision = None

        # Phase 3: 任务分配
        self._state = SupervisorState.DISPATCHING
        allocations = self._dispatch_tasks(sub_goals, priority_decision)

        # Phase 4: 冲突检测与解决
        self._state = SupervisorState.RESOLVING
        conflicts_resolved = self._resolve_conflicts()

        # Phase 5: 学习
        self._state = SupervisorState.LEARNING
        self._learn_from_cycle(goal, allocations, conflicts_resolved)

        # Phase 6: 生成报告
        self._state = SupervisorState.MONITORING
        report = self._generate_report(cycle_id, goal, allocations, conflicts_resolved)
        self._reports.append(report)

        self._state = SupervisorState.IDLE
        return report

    def _decompose_goal(
        self,
        business_goal: str,
        goal_type: GoalType,
        target_value: float,
        constraints: GoalConstraint | None,
    ) -> tuple[GrowthGoal, list[SubGoal]]:
        """分解目标."""
        goal, sub_goals = self._goal_manager.decompose_goal(
            objective=business_goal,
            goal_type=goal_type,
            target_value=target_value,
            constraints=constraints,
        )
        self._goal_manager.activate_goal(goal.goal_id)
        return goal, sub_goals

    def _dispatch_tasks(
        self,
        sub_goals: list[SubGoal],
        priority_decision: PriorityDecision | None,
    ) -> list[AllocationRecord]:
        """分配任务."""
        allocations = []

        # 分配子目标
        for sg in sub_goals:
            record = self._task_allocator.allocate_sub_goal(
                sg, assigned_by=self._identity.agent_id
            )
            if record:
                allocations.append(record)

        # 分配优先级信号
        if priority_decision and priority_decision.ranked_signals:
            for signal in priority_decision.ranked_signals[:3]:  # Top 3
                record = self._task_allocator.allocate_signal(
                    signal, assigned_by=self._identity.agent_id
                )
                if record:
                    allocations.append(record)

        return allocations

    def _resolve_conflicts(self) -> list[Conflict]:
        """检测并解决冲突."""
        active_conflicts = self._conflict_resolver.get_active_conflicts()
        resolved = []

        for conflict in active_conflicts:
            if self._mode == SupervisorMode.FULL_AUTO:
                self._conflict_resolver.auto_resolve(conflict)
            elif self._mode == SupervisorMode.SEMI_AUTO:
                # 半自动: 数据驱动决定
                context = self._memory.get_decision_context(
                    AgentRole.SUPERVISOR,
                    context_tags=[conflict.conflict_type.value],
                )
                self._conflict_resolver.resolve_by_data(conflict, context)
            else:
                # 建议模式: 推迟
                self._conflict_resolver.resolve_by_supervisor(
                    conflict,
                    decision="deferred",
                    rationale="Manual mode - requires human approval",
                )

            if conflict.is_resolved:
                resolved.append(conflict)
                self._memory.record_conflict(
                    f"Resolved: {conflict.description[:80]}",
                    AgentRole.SUPERVISOR,
                    conflict.resolution_result,
                )

        return resolved

    def _learn_from_cycle(
        self,
        goal: GrowthGoal | None,
        allocations: list[AllocationRecord],
        conflicts_resolved: list[Conflict],
    ) -> None:
        """从本循环中学习."""
        if goal:
            self._memory.record_decision(
                f"Goal set: {goal.objective}",
                AgentRole.SUPERVISOR,
                action=f"decomposed to {len(allocations)} tasks",
                outcome=f"target={goal.target_value}",
                success_rating=0.5,  # 初始中性
            )

        for alloc in allocations:
            self._memory.record_decision(
                f"Task allocated: {alloc.task_id[:8]}",
                alloc.assigned_role or AgentRole.SUPERVISOR,
                action=f"assigned to {alloc.assigned_to[:8]}",
                outcome=f"match={alloc.capability_match:.2f}",
                success_rating=alloc.capability_match,
            )

    def _generate_report(
        self,
        cycle_id: str,
        goal: GrowthGoal | None,
        allocations: list[AllocationRecord],
        conflicts_resolved: list[Conflict],
    ) -> SupervisorReport:
        """生成运行报告."""
        org_health = self._memory.get_organization_health()

        recommendations = self._generate_recommendations(allocations, conflicts_resolved)

        return SupervisorReport(
            cycle_id=cycle_id,
            active_goals=[goal.to_dict()] if goal else [],
            tasks_dispatched=len(allocations),
            conflicts_resolved=len(conflicts_resolved),
            agent_performances=org_health.get("performances", {}),
            organization_health=org_health,
            recommendations=recommendations,
        )

    def _generate_recommendations(
        self,
        allocations: list[AllocationRecord],
        conflicts_resolved: list[Conflict],
    ) -> list[str]:
        """生成建议."""
        recs = []

        # 负载建议
        overloaded = [
            agent_id for agent_id, load in self._task_allocator.get_all_loads().items()
            if load.is_overloaded
        ]
        if overloaded:
            recs.append(f"Agent load warning: {len(overloaded)} agents overloaded")

        # 冲突建议
        if conflicts_resolved:
            types = [c.conflict_type.value for c in conflicts_resolved]
            recs.append(f"Conflicts resolved: {len(conflicts_resolved)} ({', '.join(set(types))})")

        # 最佳策略建议
        best_strategies = self._memory.get_best_strategies(top_n=3)
        if best_strategies:
            top = best_strategies[0]
            recs.append(
                f"Best strategy: {top.agent_role.value if top.agent_role else '?'} "
                f"- {top.description[:50]} (success={top.success_rating:.0%})"
            )

        return recs

    # ── 快速操作 ──────────────────────────────────────────────

    def process_goal(self, business_goal: str) -> SupervisorReport:
        """处理单个业务目标."""
        return self.run_cycle(business_goal=business_goal)

    def process_signals(self, signals: list[PrioritySignal]) -> SupervisorReport:
        """处理一批信号."""
        return self.run_cycle(signals=signals)

    def process_alert(
        self,
        category: SignalCategory,
        description: str,
        severity: SignalSeverity = SignalSeverity.HIGH,
        impact: float = 0.7,
        urgency: float = 0.7,
    ) -> SupervisorReport:
        """处理单个告警."""
        signal = PrioritySignal(
            category=category,
            severity=severity,
            description=description,
            impact=impact,
            urgency=urgency,
        )
        return self.process_signals([signal])

    # ── 冲突管理 ──────────────────────────────────────────────

    def report_conflict(
        self,
        description: str,
        conflict_type: ConflictType,
        parties: list[ConflictParty],
        context: dict[str, Any] | None = None,
    ) -> Conflict:
        """报告冲突 (由 Agent 或外部调用)."""
        return self._conflict_resolver.create_conflict(
            description=description,
            conflict_type=conflict_type,
            parties=parties,
            context=context,
        )

    def resolve_current_conflicts(self) -> list[Conflict]:
        """解决当前所有活跃冲突."""
        return self._resolve_conflicts()

    # ── 广播 ──────────────────────────────────────────────────

    def broadcast_goal(self, goal: GrowthGoal) -> None:
        """广播目标给所有 Agent."""
        self._collab.broadcast(
            self._identity,
            f"新目标: {goal.objective}",
            {
                "goal_id": goal.goal_id,
                "goal_type": goal.goal_type.value,
                "target_value": goal.target_value,
                "metric": goal.metric,
            },
            standard_type=StandardMessageType.GOAL_ASSIGNMENT,
            priority=MessagePriority.HIGH,
        )

    def broadcast_strategy_update(self, strategy: dict[str, Any]) -> None:
        """广播策略更新."""
        self._collab.broadcast(
            self._identity,
            "策略更新",
            strategy,
            standard_type=StandardMessageType.STRATEGY_UPDATE,
            priority=MessagePriority.NORMAL,
        )

    # ── 查询 ──────────────────────────────────────────────────

    @property
    def identity(self) -> AgentIdentity:
        return self._identity

    @property
    def state(self) -> SupervisorState:
        return self._state

    @property
    def cycle_count(self) -> int:
        return self._cycle_count

    @property
    def mode(self) -> SupervisorMode:
        return self._mode

    def get_goal_manager(self) -> GoalManager:
        return self._goal_manager

    def get_priority_engine(self) -> PriorityEngine:
        return self._priority_engine

    def get_task_allocator(self) -> TaskAllocator:
        return self._task_allocator

    def get_conflict_resolver(self) -> ConflictResolver:
        return self._conflict_resolver

    def get_memory(self) -> SupervisorMemory:
        return self._memory

    def get_reports(self, n: int = 10) -> list[SupervisorReport]:
        return self._reports[-n:]

    def get_last_report(self) -> SupervisorReport | None:
        return self._reports[-1] if self._reports else None

    def set_mode(self, mode: SupervisorMode) -> None:
        self._mode = mode

    # ── 统计 ──────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        return {
            "identity": self._identity.to_dict(),
            "state": self._state.value,
            "mode": self._mode.value,
            "cycle_count": self._cycle_count,
            "goals": self._goal_manager.stats(),
            "signals": self._priority_engine.stats(),
            "allocations": self._task_allocator.stats(),
            "conflicts": self._conflict_resolver.stats(),
            "memory": self._memory.stats(),
            "reports": len(self._reports),
        }

    def reset(self) -> None:
        self._goal_manager.reset()
        self._priority_engine.reset()
        self._task_allocator.reset()
        self._conflict_resolver.reset()
        self._memory.reset()
        self._reports.clear()
        self._cycle_count = 0
        self._state = SupervisorState.IDLE


# ═══════════════════════════════════════════════════════════════
# Factory
# ═══════════════════════════════════════════════════════════════


def create_supervisor_agent(
    bus: MessageBus | None = None,
    registry: AgentRegistry | None = None,
    mode: SupervisorMode = SupervisorMode.FULL_AUTO,
) -> SupervisorAgent:
    """创建默认 Supervisor Agent."""
    return SupervisorAgent(bus=bus, registry=registry, mode=mode)