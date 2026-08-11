"""E12.7.4 Autonomous Execution Manager — Growth OS 执行层.

将 GrowthStrategy → ExecutionTask → Real Module Execution 打通.
"""

from .execution_controller import ExecutionController
from .execution_engine import ExecutionEngine
from .execution_monitor import ExecutionMonitor
from .models import (
    ApprovalStatus,
    ExecutionPlan,
    ExecutionResult,
    ExecutionTask,
    MonitorEvent,
    RollbackRecord,
    TargetModule,
    TaskStatus,
    TaskType,
)
from .module_adapter import (
    CreativeAdapter,
    ExperimentAdapter,
    ModuleAdapter,
    PortfolioAdapter,
    ResourceAdapter,
    SafetyAdapter,
)
from .rollback_manager import RollbackManager
from .task_dispatcher import TaskDispatcher

__all__ = [
    # Models
    "ExecutionTask",
    "ExecutionResult",
    "ExecutionPlan",
    "MonitorEvent",
    "RollbackRecord",
    "TaskType",
    "TaskStatus",
    "ApprovalStatus",
    "TargetModule",
    # Adapters
    "ModuleAdapter",
    "CreativeAdapter",
    "ExperimentAdapter",
    "ResourceAdapter",
    "PortfolioAdapter",
    "SafetyAdapter",
    # Core
    "TaskDispatcher",
    "ExecutionEngine",
    "ExecutionMonitor",
    "RollbackManager",
    "ExecutionController",
]