"""E12.7.7 Growth OS Dashboard API — 可视化与控制入口.

将内部 Growth OS 能力暴露给外部:
  Internal Growth Engine → Dashboard API → Human Operator / Agent / UI

模块:
  - models:              GrowthDashboardState, ProductDashboard, DecisionView, TaskView, PatternView
  - dashboard_service:   统一查询层 (聚合所有子系统)
  - metrics_api:         核心指标 (Portfolio / Product / Loop)
  - decision_api:        AI 决策 (查看 / 筛选 / 详情)
  - execution_api:       执行状态 (任务 / 审批 / 回滚)
  - memory_api:          AI 学习 (模式 / 经验 / 搜索)
  - websocket_manager:   实时推送
  - dashboard_controller: 总入口
"""

from .dashboard_controller import DashboardController
from .dashboard_service import DashboardService
from .decision_api import DecisionAPI
from .execution_api import ExecutionAPI
from .memory_api import MemoryAPI
from .metrics_api import MetricsAPI
from .models import (
    DashboardEvent,
    DashboardEventType,
    DashboardOverview,
    DecisionView,
    GrowthCycleView,
    GrowthDashboardState,
    LifecycleStage,
    PatternView,
    PortfolioMetrics,
    ProductDashboard,
    RiskLevel,
    SystemStatus,
    TaskView,
    TrendDirection,
)
from .websocket_manager import WebSocketManager

__all__ = [
    # Enums
    "SystemStatus",
    "RiskLevel",
    "TrendDirection",
    "LifecycleStage",
    "DashboardEventType",
    # Models
    "DashboardEvent",
    "GrowthDashboardState",
    "ProductDashboard",
    "DecisionView",
    "TaskView",
    "PatternView",
    "PortfolioMetrics",
    "GrowthCycleView",
    "DashboardOverview",
    # APIs
    "MetricsAPI",
    "DecisionAPI",
    "ExecutionAPI",
    "MemoryAPI",
    # Core
    "DashboardService",
    "WebSocketManager",
    "DashboardController",
]