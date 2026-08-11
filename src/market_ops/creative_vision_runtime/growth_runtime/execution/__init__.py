"""E13.6 Execution Layer — 自主执行运行时.

将 Decision Engine 的输出转换为真实增长动作，连接 Meta Ads API、Creative Evolution Engine 和 Budget Control。

模块:
  E13.6.1 Execution Foundation: 执行层数据模型
  E13.6.2 Action Planner: 策略 → 执行步骤拆解
  E13.6.3 Execution Engine: 执行引擎核心 (Registry + StateMachine + AuditLog)
  E13.6.4 Safety Layer: 安全层
  E13.6.5 Feedback Loop: 反馈闭环
  E13.6.6 Runtime Monitor: 执行监控
  E13.6.7 Autonomous Loop Controller: 自主循环

E15.0.9 Execution Adapter Layer:
  - growth_action:      GrowthAction + ActionType (高层动作模型)
  - adapter_base:       ExecutionAdapter + AdapterExecutionResult (统一适配器接口)
  - adapter_registry:   AdapterRegistry (ActionType → Adapter 映射)
  - adapter_router:     ExecutionRouter (路由 + 安全 + 审计 + 监控)
  - wiring:             wire_execution_layer (一键接入 Safety / Audit / Monitoring)
  - adapters/:          MetaAdsAdapter / GooglePlayAdapter / CreativeAdapter / AdjustAdapter
"""

from .models import (
    ExecutionAction,
    ExecutionActionType,
    ExecutionDomain,
    ExecutionPlan,
    ExecutionPriority,
    ExecutionStatus,
    ExecutionTask,
)
from .task_converter import TaskConverter
from .action_models import (
    ActionDependency,
    ActionNode,
    ActionPlan,
    ActionStatus,
    ActionTemplate,
    PlanPhase,
)
from .action_graph import ActionGraph
from .action_planner import ActionPlanner
from .base_executor import (
    BaseExecutor,
    ExecutionResult,
    ExecutionResultStatus,
    GuardContext,
)
from .state_machine import (
    ExecutionPhase,
    ExecutionStateMachine,
    TransitionRecord,
)
from .executor_registry import ExecutorRegistry
from .audit_log import AuditEntry, AuditLog
from .execution_context import ExecutionContext
from .execution_core import EngineResult, ExecutionEngine

# ── E15.0.9 Execution Adapter Layer ──────────────────────────────
from .growth_action import (
    ActionType as GrowthActionType,
    GrowthAction,
    create_budget_action,
    create_pause_action,
    create_resume_action,
    create_upload_creative_action,
    create_publish_release_action,
)
from .adapter_base import (
    AdapterExecutionResult,
    AdapterResultStatus,
    ExecutionAdapter,
)
from .adapter_registry import AdapterRegistry
from .adapter_router import ExecutionRouter
from .wiring import wire_execution_layer

__all__ = [
    # ── E13.6.1 Enums ──
    "ExecutionStatus",
    "ExecutionActionType",
    "ExecutionPriority",
    "ExecutionDomain",
    # ── E13.6.1 Models ──
    "ExecutionAction",
    "ExecutionTask",
    "ExecutionPlan",
    # ── E13.6.1 Converter ──
    "TaskConverter",
    # ── E13.6.2 Enums ──
    "ActionStatus",
    "ActionDependency",
    "PlanPhase",
    # ── E13.6.2 Models ──
    "ActionNode",
    "ActionPlan",
    "ActionTemplate",
    # ── E13.6.2 Graph ──
    "ActionGraph",
    # ── E13.6.2 Planner ──
    "ActionPlanner",
    # ── E13.6.3 Base Executor ──
    "BaseExecutor",
    "ExecutionResult",
    "ExecutionResultStatus",
    "GuardContext",
    # ── E13.6.3 State Machine ──
    "ExecutionPhase",
    "ExecutionStateMachine",
    "TransitionRecord",
    # ── E13.6.3 Registry ──
    "ExecutorRegistry",
    # ── E13.6.3 Audit ──
    "AuditEntry",
    "AuditLog",
    # ── E13.6.3 Engine ──
    "EngineResult",
    "ExecutionEngine",
    # ── E13.6.3 Context ──
    "ExecutionContext",
    # ── E15.0.9 Growth Action ──
    "GrowthActionType",
    "GrowthAction",
    "create_budget_action",
    "create_pause_action",
    "create_resume_action",
    "create_upload_creative_action",
    "create_publish_release_action",
    # ── E15.0.9 Adapter Base ──
    "AdapterExecutionResult",
    "AdapterResultStatus",
    "ExecutionAdapter",
    # ── E15.0.9 Adapter Registry ──
    "AdapterRegistry",
    # ── E15.0.9 Execution Router ──
    "ExecutionRouter",
    # ── E15.0.9 Wiring ──
    "wire_execution_layer",
]