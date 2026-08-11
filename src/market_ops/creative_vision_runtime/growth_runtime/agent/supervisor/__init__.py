"""E14.2 Growth Supervisor Agent — 多 Agent 组织大脑.

核心组件:
  1. goal_manager: 业务目标拆解与量化
  2. priority_engine: 多信号优先级决策
  3. task_allocator: 基于能力的任务分配
  4. conflict_resolver: Agent 冲突处理
  5. supervisor_memory: 组织级记忆
  6. supervisor_agent: Supervisor 核心循环

典型用法:
    from supervisor import (
        SupervisorAgent, SupervisorMode,
        create_supervisor_agent,
    )

    supervisor = create_supervisor_agent()
    report = supervisor.run_cycle("本月利润提升30%")
"""

from .goal_manager import (
    GrowthGoal,
    GoalType,
    GoalStatus,
    GoalConstraint,
    SubGoal,
    GoalManager,
    create_goal_manager,
)

from .priority_engine import (
    PrioritySignal,
    PriorityDecision,
    PriorityEngine,
    SignalCategory,
    SignalSeverity,
    create_priority_engine,
)

from .task_allocator import (
    TaskAllocator,
    AllocationRecord,
    AllocationStatus,
    AgentLoad,
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
    AgentPerformance,
    MemoryType,
    create_supervisor_memory,
)

from .supervisor_agent import (
    SupervisorAgent,
    SupervisorMode,
    SupervisorState,
    SupervisorReport,
    create_supervisor_agent,
)

__all__ = [
    # goal_manager
    "GrowthGoal", "GoalType", "GoalStatus", "GoalConstraint", "SubGoal",
    "GoalManager", "create_goal_manager",
    # priority_engine
    "PrioritySignal", "PriorityDecision", "PriorityEngine",
    "SignalCategory", "SignalSeverity", "create_priority_engine",
    # task_allocator
    "TaskAllocator", "AllocationRecord", "AllocationStatus", "AgentLoad",
    "create_task_allocator",
    # conflict_resolver
    "ConflictResolver", "Conflict", "ConflictType", "ConflictParty",
    "ResolutionStrategy", "create_conflict_resolver",
    # supervisor_memory
    "SupervisorMemory", "OrganizationMemory", "AgentPerformance",
    "MemoryType", "create_supervisor_memory",
    # supervisor_agent
    "SupervisorAgent", "SupervisorMode", "SupervisorState",
    "SupervisorReport", "create_supervisor_agent",
]