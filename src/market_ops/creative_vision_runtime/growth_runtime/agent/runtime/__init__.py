"""E13.7.4.1 Production Agent Runtime — 生产运行时内核.

Production Growth Runtime 将 GrowthAgent 从 "run_cycle()" 升级为
完整的生产自主运行系统:

  - ProductionGrowthRuntime: 核心运行时 (生命周期 + 调度 + 循环 + 监控)
  - LifecycleManager: 生命周期管理 (启停/暂停/安全模式)
  - AgentScheduler: 生产调度器 (5min/1hr/24hr 定时任务)
  - RuntimeState: 运行状态管理
  - EventBus: 事件系统 (发布/订阅)
"""

from .agent_scheduler import (
    AgentJob,
    AgentScheduler,
    JobPriority,
    JobStatus,
    create_default_jobs,
    create_scheduler,
)
from .lifecycle_manager import (
    LifecycleError,
    LifecycleManager,
    create_lifecycle_manager,
)
from .production_runtime import (
    ProductionGrowthRuntime,
    create_production_runtime,
)
from .runtime_events import (
    EventBus,
    RuntimeEvent,
    RuntimeEventType,
    create_event_bus,
)
from .runtime_state import (
    RuntimeState,
    RuntimeStatus,
    create_runtime_state,
)

__all__ = [
    # Core Runtime
    "ProductionGrowthRuntime",
    "create_production_runtime",
    # Lifecycle
    "LifecycleManager",
    "LifecycleError",
    "create_lifecycle_manager",
    # Scheduler
    "AgentScheduler",
    "AgentJob",
    "JobPriority",
    "JobStatus",
    "create_scheduler",
    "create_default_jobs",
    # State
    "RuntimeState",
    "RuntimeStatus",
    "create_runtime_state",
    # Events
    "EventBus",
    "RuntimeEvent",
    "RuntimeEventType",
    "create_event_bus",
]