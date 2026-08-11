"""E12.7.7 Dashboard Service — 统一查询层，聚合 Kernel/Agent/Planner/Execution/Memory/Loop."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..agent.agent_controller import AutonomousGrowthAgent
from ..execution.execution_controller import ExecutionController
from ..kernel.runtime import RuntimeManager
from ..loop.loop_controller import LoopController
from ..memory.memory_controller import MemoryController
from ..strategy.planner_controller import GrowthStrategyPlanner

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


class DashboardService:
    """仪表盘服务 — 聚合所有 Growth OS 子系统的数据.

    提供统一的查询接口:
      - get_system_state():   系统总览
      - get_product_state():  单产品状态
      - get_growth_cycle():   增长循环
      - get_decisions():      AI 决策
      - get_execution_status(): 执行状态
      - get_memory_summary():  记忆摘要
    """

    def __init__(
        self,
        runtime: RuntimeManager | None = None,
        agent: AutonomousGrowthAgent | None = None,
        planner: GrowthStrategyPlanner | None = None,
        executor: ExecutionController | None = None,
        memory: MemoryController | None = None,
        loop_controller: LoopController | None = None,
    ):
        self._runtime = runtime or RuntimeManager()
        self._agent = agent or AutonomousGrowthAgent()
        self._planner = planner or GrowthStrategyPlanner()
        self._executor = executor or ExecutionController()
        self._memory = memory or MemoryController()
        self._loop = loop_controller or LoopController()

        self._events: list[DashboardEvent] = []
        self._products: dict[str, ProductDashboard] = {}
        self._query_count: int = 0

    @property
    def query_count(self) -> int:
        return self._query_count

    # ── System State ──────────────────────────────────────────

    def get_system_state(self) -> GrowthDashboardState:
        """获取系统总览状态."""
        self._query_count += 1

        runtime_status = self._runtime.get_status()
        loop_status = self._loop.get_status()
        agent_status = self._agent.get_status()

        # Determine system status
        runtime_state = runtime_status.get("status", "idle")
        if runtime_state == "running":
            system_status = self._derive_system_status(agent_status, loop_status)
        else:
            system_status = SystemStatus.IDLE

        active_products = self._count_active_products()
        active_cycles = loop_status.get("active_loops", 0)
        running_tasks = self._count_running_tasks()

        health_score = self._compute_health_score(runtime_status, loop_status, agent_status)

        return GrowthDashboardState(
            system_status=system_status,
            active_products=active_products,
            active_cycles=active_cycles,
            running_tasks=running_tasks,
            pending_decisions=agent_status.get("decision_count", 0),
            health_score=health_score,
            last_update=datetime.now(timezone.utc).isoformat(),
        )

    def _derive_system_status(
        self, agent_status: dict[str, Any], loop_status: dict[str, Any],
    ) -> SystemStatus:
        """推导系统状态."""
        if loop_status.get("active_loops", 0) > 0:
            return SystemStatus.OPTIMIZING
        if agent_status.get("decision_count", 0) > 0:
            return SystemStatus.RUNNING
        return SystemStatus.RUNNING

    def _count_active_products(self) -> int:
        """统计活跃产品数."""
        loops = self._loop.get_all_loops()
        return len({l.product_id for l in loops if l.state and l.state.value not in ("completed", "failed")})

    def _count_running_tasks(self) -> int:
        """统计运行中任务数."""
        summary = self._executor.get_summary()
        engine = summary.get("engine", {})
        return engine.get("tasks_executed", 0)

    def _compute_health_score(
        self,
        runtime_status: dict[str, Any],
        loop_status: dict[str, Any],
        agent_status: dict[str, Any],
    ) -> float:
        """计算系统健康分."""
        score = 1.0

        # Runtime status
        if runtime_status.get("status") != "running":
            score -= 0.2

        # Active loops
        active = loop_status.get("active_loops", 0)
        completed = loop_status.get("completed_loops", 0)
        if active + completed == 0:
            score -= 0.1

        # Agent status
        if not agent_status.get("has_observation", False):
            score -= 0.1

        return max(0.0, min(1.0, score))

    # ── Product State ─────────────────────────────────────────

    def get_product_state(self, product_id: str) -> ProductDashboard:
        """获取单产品状态."""
        self._query_count += 1

        if product_id in self._products:
            return self._products[product_id]

        return self._build_product_dashboard(product_id)

    def get_all_product_states(self) -> list[ProductDashboard]:
        """获取所有产品状态."""
        self._query_count += 1

        loops = self._loop.get_all_loops()
        product_ids = {l.product_id for l in loops}
        if not product_ids:
            product_ids = {"default"}

        return [self.get_product_state(pid) for pid in product_ids]

    def _build_product_dashboard(self, product_id: str) -> ProductDashboard:
        """构建产品仪表盘."""
        # Get loop info
        loop = self._loop.get_loop_by_product(product_id)

        # Get memory
        patterns = self._memory.learn_patterns()
        product_patterns = [p for p in patterns if p.product_id == product_id]

        # Compute metrics
        avg_roas = 0.0
        success_count = 0
        total_count = 0
        for p in product_patterns:
            metrics = p.metrics
            if metrics and metrics.roas > 0:
                avg_roas = max(avg_roas, metrics.roas)
            total_count += 1
            if p.outcome and p.outcome.value == "success":
                success_count += 1

        growth_score = min(1.0, avg_roas / 2.0) if avg_roas > 0 else 0.3

        completed_cycles = loop.cycle_count if loop else 0

        return ProductDashboard(
            product_id=product_id,
            lifecycle_stage=LifecycleStage.GROWTH,
            current_roas=avg_roas,
            trend=TrendDirection.UP if avg_roas > 1.0 else TrendDirection.STABLE,
            risk_level=RiskLevel.LOW if avg_roas >= 1.0 else RiskLevel.MEDIUM,
            growth_score=round(growth_score, 2),
            active_strategy=loop.active_strategy_id if loop else "",
            completed_cycles=completed_cycles,
            last_updated=datetime.now(timezone.utc).isoformat(),
        )

    # ── Growth Cycle ──────────────────────────────────────────

    def get_growth_cycle(self, product_id: str) -> list[GrowthCycleView]:
        """获取增长循环历史."""
        self._query_count += 1

        loop = self._loop.get_loop_by_product(product_id)
        if loop is None:
            return []

        return [
            GrowthCycleView(
                cycle_number=c.cycle_number,
                state=c.state.value if c.state else "",
                outcome=c.outcome.value if c.outcome else "",
                strategy_id=c.strategy_id,
                execution_id=c.execution_id,
                has_errors=bool(c.errors),
                patterns_learned=c.learning.get("patterns_learned", 0) if c.learning else 0,
                started_at=c.started_at.isoformat() if c.started_at else "",
                completed_at=c.completed_at.isoformat() if c.completed_at else "",
            )
            for c in loop.cycles
        ]

    # ── Decisions ─────────────────────────────────────────────

    def get_decisions(self, product_id: str = "") -> list[DecisionView]:
        """获取 AI 决策列表."""
        self._query_count += 1

        decisions = self._agent.get_last_decisions()
        result: list[DecisionView] = []

        for d in decisions:
            dv = DecisionView(
                decision_id=d.decision_id,
                product_id=d.product_id,
                action=d.action_type.value if d.action_type else "",
                reason=d.reason,
                confidence=d.confidence,
                priority=d.priority,
                impact=d.expected_impact,
                source_module="Agent Decision Engine",
                status="pending" if d.priority > 0 else "done",
                created_at=d.created_at.isoformat() if d.created_at else "",
            )
            if not product_id or dv.product_id == product_id:
                result.append(dv)

        return result

    # ── Execution Status ──────────────────────────────────────

    def get_execution_status(self) -> dict[str, Any]:
        """获取执行状态."""
        self._query_count += 1

        summary = self._executor.get_summary()
        engine = summary.get("engine", {})
        monitor = summary.get("monitor", {})
        rollback = summary.get("rollback", {})

        return {
            "tasks_executed": engine.get("tasks_executed", 0),
            "tasks_succeeded": engine.get("tasks_succeeded", 0),
            "tasks_failed": engine.get("tasks_failed", 0),
            "plans_executed": engine.get("plans_executed", 0),
            "alerts": monitor.get("alert_count", 0),
            "rollbacks": rollback.get("rollback_count", 0),
            "summary": summary,
        }

    def get_running_tasks(self, product_id: str = "") -> list[TaskView]:
        """获取运行中的任务."""
        self._query_count += 1

        summary = self._executor.get_summary()
        engine = summary.get("engine", {})
        recent_tasks = engine.get("recent_tasks", [])

        result: list[TaskView] = []
        for t in recent_tasks:
            if not isinstance(t, dict):
                continue
            tv = TaskView(
                task_id=t.get("task_id", ""),
                task_type=t.get("task_type", ""),
                product_id=t.get("product_id", ""),
                status=t.get("status", "pending"),
                progress=t.get("progress", 0.0),
                target_module=t.get("target_module", ""),
                strategy_id=t.get("strategy_id", ""),
                created_at=t.get("created_at", ""),
                started_at=t.get("started_at", ""),
                completed_at=t.get("completed_at", ""),
            )
            if not product_id or tv.product_id == product_id:
                result.append(tv)

        return result

    # ── Memory ────────────────────────────────────────────────

    def get_memory_summary(self) -> dict[str, Any]:
        """获取记忆摘要."""
        self._query_count += 1

        return self._memory.get_summary()

    def get_patterns(self, product_id: str = "") -> list[PatternView]:
        """获取学习模式."""
        self._query_count += 1

        patterns = self._memory.learn_patterns()
        result: list[PatternView] = []

        for p in patterns:
            if product_id and p.product_id != product_id:
                continue
            pv = PatternView(
                pattern_id=p.pattern_id,
                name=p.name,
                description=p.description,
                usage_count=p.usage_count,
                success_rate=p.success_rate,
                avg_roas=p.metrics.roas if p.metrics else 0.0,
                confidence=p.confidence,
                reliability=p.reliability,
                gene_tags=p.gene_tags if p.gene_tags else [],
                created_at=p.created_at.isoformat() if p.created_at else "",
            )
            result.append(pv)

        return result

    # ── Portfolio ─────────────────────────────────────────────

    def get_portfolio_metrics(self) -> PortfolioMetrics:
        """获取组合指标."""
        self._query_count += 1

        products = self.get_all_product_states()
        total_spend = sum(p.budget_allocation for p in products)
        total_revenue = sum(p.current_roas * p.budget_allocation for p in products if p.current_roas > 0)
        portfolio_roas = total_revenue / total_spend if total_spend > 0 else 0.0

        return PortfolioMetrics(
            total_spend=total_spend,
            total_revenue=total_revenue,
            portfolio_roas=round(portfolio_roas, 4),
            portfolio_ltv=total_revenue * 2.0,
            portfolio_fitness=sum(p.growth_score for p in products) / max(1, len(products)),
            product_count=len(products),
        )

    # ── Overview ──────────────────────────────────────────────

    def get_overview(self) -> DashboardOverview:
        """获取仪表盘总览."""
        self._query_count += 1

        return DashboardOverview(
            system=self.get_system_state(),
            portfolio=self.get_portfolio_metrics(),
            products=self.get_all_product_states(),
            recent_decisions=self.get_decisions(),
            active_tasks=self.get_running_tasks(),
            top_patterns=self.get_patterns(),
            system_events=self._events[-20:],
        )

    # ── Events ────────────────────────────────────────────────

    def add_event(self, event: DashboardEvent) -> None:
        """添加事件."""
        self._events.append(event)
        if len(self._events) > 100:
            self._events = self._events[-100:]

    def get_recent_events(self, limit: int = 20) -> list[DashboardEvent]:
        """获取最近事件."""
        return self._events[-limit:]

    # ── Summary ───────────────────────────────────────────────

    def get_summary(self) -> dict[str, Any]:
        return {
            "query_count": self._query_count,
            "event_count": len(self._events),
            "products_tracked": len(self._products),
        }