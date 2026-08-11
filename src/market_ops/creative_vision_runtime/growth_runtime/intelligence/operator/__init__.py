"""E15.3.1 Operator Controller — 自主 Operator 入口层.

E15.3 Autonomous Operator Loop 的第一层，提供:
  - 目标管理: 管理长期增长目标
  - 环境观察: 收集 Reality Data
  - 触发引擎: 定时/事件/异常触发
  - 生命周期: 状态转换管理
  - 核心控制器: observe→think→act→learn 循环
  - 记忆桥接: 连接 E15.1.5 Memory Feedback

连接:
  - E15.2 Intelligence Layer → 推理决策
  - E15.1 Workflow Execution → 执行动作
  - E15.1.5 Memory Feedback → 经验记录
"""

from .controller import OperatorController
from .goal import GoalManager
from .lifecycle import LifecycleManager, VALID_TRANSITIONS
from .memory import OperatorMemoryBridge
from .models import (
    CycleOutcome,
    GoalStatus,
    OperatorCycleResult,
    OperatorExperience,
    OperatorGoal,
    OperatorObservation,
    OperatorSession,
    OperatorState,
    OperatorTrigger,
    TriggerType,
)
from .observation import ObservationCollector
from .trigger import TriggerEngine

__all__ = [
    # Enums
    "OperatorState",
    "GoalStatus",
    "TriggerType",
    "CycleOutcome",
    # Models
    "OperatorGoal",
    "OperatorObservation",
    "OperatorTrigger",
    "OperatorSession",
    "OperatorCycleResult",
    "OperatorExperience",
    # Goal Manager
    "GoalManager",
    # Observation
    "ObservationCollector",
    # Trigger
    "TriggerEngine",
    # Lifecycle
    "LifecycleManager",
    "VALID_TRANSITIONS",
    # Memory
    "OperatorMemoryBridge",
    # Controller
    "OperatorController",
]