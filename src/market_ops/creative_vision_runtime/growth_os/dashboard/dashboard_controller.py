"""E12.7.7 Dashboard Controller — 总入口: get_overview / get_product / get_decisions / get_tasks / get_memory / stream_events."""

from __future__ import annotations

from typing import Any

from ..agent.agent_controller import AutonomousGrowthAgent
from ..execution.execution_controller import ExecutionController
from ..kernel.runtime import RuntimeManager
from ..loop.loop_controller import LoopController
from ..memory.memory_controller import MemoryController
from ..strategy.planner_controller import GrowthStrategyPlanner

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
    GrowthDashboardState,
    PatternView,
    PortfolioMetrics,
    ProductDashboard,
    TaskView,
)
from .websocket_manager import WebSocketManager


class DashboardController:
    """仪表盘控制器 — Growth OS Dashboard 的统一入口.

    提供:
      - get_overview():    系统总览
      - get_product():     单产品状态
      - get_decisions():   AI 决策
      - get_tasks():       执行状态
      - get_memory():      记忆/模式
      - stream_events():   实时事件流
    """

    def __init__(
        self,
        runtime: RuntimeManager | None = None,
        agent: AutonomousGrowthAgent | None = None,
        planner: GrowthStrategyPlanner | None = None,
        executor: ExecutionController | None = None,
        memory: MemoryController | None = None,
        loop_controller: LoopController | None = None,
        service: DashboardService | None = None,
        metrics: MetricsAPI | None = None,
        decisions: DecisionAPI | None = None,
        execution_api: ExecutionAPI | None = None,
        memory_api: MemoryAPI | None = None,
        ws: WebSocketManager | None = None,
    ):
        self._runtime = runtime or RuntimeManager()
        self._agent = agent or AutonomousGrowthAgent()
        self._planner = planner or GrowthStrategyPlanner()
        self._executor = executor or ExecutionController()
        self._memory = memory or MemoryController()
        self._loop = loop_controller or LoopController()

        self._service = service or DashboardService(
            runtime=self._runtime,
            agent=self._agent,
            planner=self._planner,
            executor=self._executor,
            memory=self._memory,
            loop_controller=self._loop,
        )
        self._metrics = metrics or MetricsAPI(
            loop_controller=self._loop,
            memory=self._memory,
        )
        self._decisions = decisions or DecisionAPI(agent=self._agent)
        self._execution_api = execution_api or ExecutionAPI(executor=self._executor)
        self._memory_api = memory_api or MemoryAPI(memory=self._memory)
        self._ws = ws or WebSocketManager()

        self._query_count: int = 0

    @property
    def service(self) -> DashboardService:
        return self._service

    @property
    def metrics(self) -> MetricsAPI:
        return self._metrics

    @property
    def decisions(self) -> DecisionAPI:
        return self._decisions

    @property
    def execution_api(self) -> ExecutionAPI:
        return self._execution_api

    @property
    def memory_api(self) -> MemoryAPI:
        return self._memory_api

    @property
    def ws(self) -> WebSocketManager:
        return self._ws

    @property
    def query_count(self) -> int:
        return self._query_count

    # ── Overview ──────────────────────────────────────────────

    def get_overview(self) -> DashboardOverview:
        """获取系统总览."""
        self._query_count += 1
        return self._service.get_overview()

    def get_system_status(self) -> GrowthDashboardState:
        """获取系统状态."""
        self._query_count += 1
        return self._service.get_system_state()

    # ── Product ───────────────────────────────────────────────

    def get_product(self, product_id: str) -> ProductDashboard:
        """获取产品状态."""
        self._query_count += 1
        return self._service.get_product_state(product_id)

    def get_all_products(self) -> list[ProductDashboard]:
        """获取所有产品."""
        self._query_count += 1
        return self._service.get_all_product_states()

    def get_portfolio(self) -> PortfolioMetrics:
        """获取组合指标."""
        self._query_count += 1
        return self._metrics.get_portfolio_metrics()

    # ── Decisions ─────────────────────────────────────────────

    def get_decisions(self, product_id: str = "") -> list[DecisionView]:
        """获取 AI 决策."""
        self._query_count += 1
        return self._decisions.get_decisions(product_id=product_id)

    def get_top_decisions(self, limit: int = 5) -> list[DecisionView]:
        """获取最高优先级决策."""
        self._query_count += 1
        return self._decisions.get_top_decisions(limit=limit)

    def get_pending_decisions(self) -> list[DecisionView]:
        """获取待处理决策."""
        self._query_count += 1
        return self._decisions.get_pending_decisions()

    # ── Tasks ─────────────────────────────────────────────────

    def get_tasks(self, product_id: str = "") -> list[TaskView]:
        """获取执行任务."""
        self._query_count += 1
        return self._execution_api.get_running_tasks(product_id=product_id)

    def get_all_tasks(self, product_id: str = "") -> list[TaskView]:
        """获取所有任务."""
        self._query_count += 1
        return self._execution_api.get_all_tasks(product_id=product_id)

    def get_execution_status(self) -> dict[str, Any]:
        """获取执行状态."""
        self._query_count += 1
        return self._execution_api.get_execution_summary()

    def approve_task(self, task_id: str) -> bool:
        """审批任务."""
        self._query_count += 1
        return self._execution_api.approve_task(task_id)

    def cancel_task(self, task_id: str) -> bool:
        """取消任务."""
        self._query_count += 1
        return self._execution_api.cancel_task(task_id)

    def rollback_task(self, task_id: str) -> bool:
        """回滚任务."""
        self._query_count += 1
        return self._execution_api.rollback_task(task_id)

    # ── Memory ────────────────────────────────────────────────

    def get_memory(self) -> dict[str, Any]:
        """获取记忆摘要."""
        self._query_count += 1
        return self._memory_api.get_summary()

    def get_patterns(self, product_id: str = "") -> list[PatternView]:
        """获取学习模式."""
        self._query_count += 1
        return self._memory_api.get_patterns(product_id=product_id)

    def get_experiences(self, product_id: str = "") -> list[dict[str, Any]]:
        """获取经验列表."""
        self._query_count += 1
        return self._memory_api.get_experiences(product_id=product_id)

    def search_memory(self, keywords: list[str], limit: int = 10) -> list[dict[str, Any]]:
        """搜索记忆."""
        self._query_count += 1
        return self._memory_api.search_memory(keywords, limit=limit)

    # ── Events ────────────────────────────────────────────────

    def stream_events(self) -> list[DashboardEvent]:
        """获取事件流（最近事件）."""
        self._query_count += 1
        return self._ws.get_history()

    def get_events_by_type(
        self, event_type: DashboardEventType, limit: int = 20,
    ) -> list[DashboardEvent]:
        """按类型获取事件."""
        self._query_count += 1
        return self._ws.get_history_by_type(event_type, limit=limit)

    def emit_event(self, event: DashboardEvent) -> int:
        """推送事件."""
        self._query_count += 1
        return self._ws.emit(event)

    def alert(self, product_id: str, message: str, severity: str = "high") -> DashboardEvent:
        """发送风险告警."""
        self._query_count += 1
        return self._ws.emit_risk_alert(product_id, {
            "message": message,
            "severity": severity,
        })

    # ── Summary ───────────────────────────────────────────────

    def get_summary(self) -> dict[str, Any]:
        return {
            "query_count": self._query_count,
            "service": self._service.get_summary(),
            "metrics": self._metrics.get_summary(),
            "decisions": self._decisions.get_summary(),
            "execution": self._execution_api.get_summary(),
            "memory": self._memory_api.get_summary(),
            "websocket": self._ws.get_summary(),
        }