"""E15.1 Workflow Definition & Execution Layer — 声明式 Workflow 系统.

提供:
  - WorkflowTask:           单个执行节点定义
  - WorkflowDefinition:     Workflow 静态模板 (DAG)
  - WorkflowInstance:       Workflow 运行实例
  - WorkflowBuilder:        Builder 模式构建 Workflow
  - WorkflowRegistry:       Workflow 注册与查询
  - ExecutionContext:       运行时执行上下文 (E15.1.2)
  - WorkflowState:          细粒度运行时状态 (E15.1.2)
  - TaskExecutionState:     Task 运行时执行记录 (E15.1.2)
  - ContextEvent:           上下文事件 (E15.1.2)
  - TaskScheduler:          优先级 + 条件调度器 (E15.1.3)
  - MemoryFeedbackBridge:   执行→记忆→智能 闭环桥梁 (E15.1.5)

架构位置:
  Growth Decision → Workflow Definition → Execution Context
  → Task Scheduler → Execution Engine → Memory Feedback Bridge
  → Experience Store → Pattern Memory → Decision Improvement
"""

from .builder import (
    WorkflowBuilder,
    create_campaign_optimization_workflow,
    create_creative_refresh_workflow,
    create_growth_recovery_workflow,
)
from .context import ExecutionContext
from .events import ContextEvent, ContextEventType
from .memory_bridge import (
    ExecutionResult,
    ExecutionStatus,
    ExperienceBuilder,
    MemoryFeedbackBridge,
    MemoryFeedbackEvent,
    MemoryFeedbackEventType,
    PatternUpdater,
    RewardCalculator,
    TaskExecutionResult,
)
from .models import (
    TaskStatus,
    WorkflowDefinition,
    WorkflowInstance,
    WorkflowStatus,
    WorkflowTask,
)
from .registry import WorkflowRegistry, WorkflowRegistryEntry
from .scheduler import (
    DAGScheduler,
    FailureAction,
    FailureResolution,
    ScheduleResult,
    ScheduleState,
    TaskPriority,
    TaskScheduleInfo,
    TaskScheduleStatus,
    TaskScheduler,
)
from .state import TaskExecutionState, TaskExecutionStatus, WorkflowState

__all__ = [
    # Models (E15.1.1)
    "WorkflowStatus",
    "TaskStatus",
    "WorkflowTask",
    "WorkflowDefinition",
    "WorkflowInstance",
    # Builder (E15.1.1)
    "WorkflowBuilder",
    "create_campaign_optimization_workflow",
    "create_creative_refresh_workflow",
    "create_growth_recovery_workflow",
    # Registry (E15.1.1)
    "WorkflowRegistry",
    "WorkflowRegistryEntry",
    # State (E15.1.2)
    "WorkflowState",
    "TaskExecutionStatus",
    "TaskExecutionState",
    # Context (E15.1.2)
    "ExecutionContext",
    # Events (E15.1.2)
    "ContextEventType",
    "ContextEvent",
    # Scheduler (E15.1.3)
    "TaskScheduler",
    "DAGScheduler",
    "TaskPriority",
    "TaskScheduleStatus",
    "TaskScheduleInfo",
    "ScheduleState",
    "ScheduleResult",
    "FailureAction",
    "FailureResolution",
    # Memory Bridge (E15.1.5)
    "ExecutionStatus",
    "ExecutionResult",
    "TaskExecutionResult",
    "RewardCalculator",
    "ExperienceBuilder",
    "PatternUpdater",
    "MemoryFeedbackEventType",
    "MemoryFeedbackEvent",
    "MemoryFeedbackBridge",
]