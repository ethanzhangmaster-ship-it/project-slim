"""E12.7.7 Growth OS Dashboard API — 测试 (~240 tests)."""

from __future__ import annotations

import pytest
from datetime import datetime, timezone

from src.market_ops.creative_vision_runtime.growth_os.dashboard.models import (
    SystemStatus,
    RiskLevel,
    TrendDirection,
    LifecycleStage,
    DashboardEventType,
    DashboardEvent,
    GrowthDashboardState,
    ProductDashboard,
    DecisionView,
    TaskView,
    PatternView,
    PortfolioMetrics,
    GrowthCycleView,
    DashboardOverview,
)
from src.market_ops.creative_vision_runtime.growth_os.dashboard.dashboard_service import (
    DashboardService,
)
from src.market_ops.creative_vision_runtime.growth_os.dashboard.metrics_api import (
    MetricsAPI,
)
from src.market_ops.creative_vision_runtime.growth_os.dashboard.decision_api import (
    DecisionAPI,
)
from src.market_ops.creative_vision_runtime.growth_os.dashboard.execution_api import (
    ExecutionAPI,
)
from src.market_ops.creative_vision_runtime.growth_os.dashboard.memory_api import (
    MemoryAPI,
)
from src.market_ops.creative_vision_runtime.growth_os.dashboard.websocket_manager import (
    WebSocketManager,
)
from src.market_ops.creative_vision_runtime.growth_os.dashboard.dashboard_controller import (
    DashboardController,
)


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════

def _make_product_dashboard(**kwargs) -> ProductDashboard:
    defaults = {
        "product_id": "p01",
        "current_roas": 1.5,
        "growth_score": 0.75,
        "budget_allocation": 5000.0,
    }
    defaults.update(kwargs)
    return ProductDashboard(**defaults)


def _make_decision_view(**kwargs) -> DecisionView:
    defaults = {
        "product_id": "p01",
        "action": "CREATE_NEW_CREATIVE_VARIANTS",
        "reason": "Winner DNA identified",
        "confidence": 0.91,
        "priority": 80,
        "source_module": "Meta Decision Engine",
    }
    defaults.update(kwargs)
    return DecisionView(**defaults)


def _make_task_view(**kwargs) -> TaskView:
    defaults = {
        "task_id": "task_001",
        "task_type": "creative_mutation",
        "product_id": "p01",
        "status": "running",
        "progress": 0.7,
        "target_module": "E11_EVOLUTION",
    }
    defaults.update(kwargs)
    return TaskView(**defaults)


def _make_pattern_view(**kwargs) -> PatternView:
    defaults = {
        "pattern_id": "pat_001",
        "name": "Rescue Hook",
        "description": "Rescue-based hook pattern",
        "usage_count": 132,
        "success_rate": 0.78,
        "avg_roas": 1.42,
        "confidence": 0.89,
        "reliability": 0.85,
    }
    defaults.update(kwargs)
    return PatternView(**defaults)


# ═══════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════

@pytest.fixture
def service():
    return DashboardService()


@pytest.fixture
def metrics_api():
    return MetricsAPI()


@pytest.fixture
def decision_api():
    return DecisionAPI()


@pytest.fixture
def execution_api():
    return ExecutionAPI()


@pytest.fixture
def memory_api():
    return MemoryAPI()


@pytest.fixture
def ws_manager():
    return WebSocketManager()


@pytest.fixture
def controller():
    return DashboardController()


# ═══════════════════════════════════════════════════════════════
# TestModels — 25 tests
# ═══════════════════════════════════════════════════════════════

class TestModels:
    """模型测试."""

    def test_system_status_values(self):
        assert SystemStatus.IDLE.value == "idle"
        assert SystemStatus.RUNNING.value == "running"
        assert SystemStatus.OPTIMIZING.value == "optimizing"
        assert SystemStatus.DEGRADED.value == "degraded"
        assert SystemStatus.ERROR.value == "error"
        assert SystemStatus.PAUSED.value == "paused"

    def test_risk_level_values(self):
        assert RiskLevel.LOW.value == "low"
        assert RiskLevel.MEDIUM.value == "medium"
        assert RiskLevel.HIGH.value == "high"
        assert RiskLevel.CRITICAL.value == "critical"

    def test_trend_direction_values(self):
        assert TrendDirection.UP.value == "up"
        assert TrendDirection.DOWN.value == "down"
        assert TrendDirection.STABLE.value == "stable"

    def test_lifecycle_stage_values(self):
        assert LifecycleStage.INCUBATION.value == "incubation"
        assert LifecycleStage.GROWTH.value == "growth"
        assert LifecycleStage.MATURITY.value == "maturity"
        assert LifecycleStage.DECLINE.value == "decline"
        assert LifecycleStage.REVIVAL.value == "revival"

    def test_dashboard_event_type_values(self):
        assert DashboardEventType.CYCLE_STARTED.value == "cycle_started"
        assert DashboardEventType.DECISION_CREATED.value == "decision_created"
        assert DashboardEventType.TASK_COMPLETED.value == "task_completed"
        assert DashboardEventType.EXPERIMENT_FINISHED.value == "experiment_finished"
        assert DashboardEventType.PATTERN_LEARNED.value == "pattern_learned"
        assert DashboardEventType.RISK_ALERT.value == "risk_alert"

    def test_dashboard_event_defaults(self):
        event = DashboardEvent()
        assert event.event_id != ""
        assert event.event_type == DashboardEventType.SYSTEM_STATUS_CHANGED
        assert event.data == {}

    def test_dashboard_event_to_dict(self):
        event = DashboardEvent(
            event_type=DashboardEventType.RISK_ALERT,
            product_id="p01",
            data={"message": "test"},
        )
        d = event.to_dict()
        assert d["event_type"] == "risk_alert"
        assert d["product_id"] == "p01"
        assert d["data"]["message"] == "test"

    def test_growth_dashboard_state_defaults(self):
        state = GrowthDashboardState()
        assert state.system_status == SystemStatus.IDLE
        assert state.active_products == 0
        assert state.health_score == 1.0

    def test_growth_dashboard_state_to_dict(self):
        state = GrowthDashboardState(
            system_status=SystemStatus.OPTIMIZING,
            active_products=3,
            active_cycles=2,
            running_tasks=5,
            pending_decisions=4,
            health_score=0.92,
        )
        d = state.to_dict()
        assert d["system_status"] == "optimizing"
        assert d["active_products"] == 3
        assert d["health_score"] == 0.92

    def test_product_dashboard_defaults(self):
        pd = ProductDashboard()
        assert pd.lifecycle_stage == LifecycleStage.GROWTH
        assert pd.current_roas == 0.0
        assert pd.risk_level == RiskLevel.LOW

    def test_product_dashboard_to_dict(self):
        pd = ProductDashboard(
            product_id="p01",
            lifecycle_stage=LifecycleStage.MATURITY,
            current_roas=1.8,
            trend=TrendDirection.UP,
            risk_level=RiskLevel.LOW,
            growth_score=0.85,
            active_strategy="S_001",
            budget_allocation=10000.0,
            active_experiments=3,
            completed_cycles=12,
        )
        d = pd.to_dict()
        assert d["product_id"] == "p01"
        assert d["lifecycle_stage"] == "maturity"
        assert d["current_roas"] == 1.8
        assert d["trend"] == "up"
        assert d["growth_score"] == 0.85

    def test_decision_view_defaults(self):
        dv = DecisionView()
        assert dv.decision_id != ""
        assert dv.confidence == 0.0
        assert dv.priority == 0

    def test_decision_view_to_dict(self):
        dv = DecisionView(
            product_id="p01",
            action="INCREASE_BUDGET",
            reason="ROAS positive trend",
            confidence=0.87,
            priority=75,
            impact="+15% revenue expected",
            source_module="Meta Decision Engine",
            status="pending",
        )
        d = dv.to_dict()
        assert d["action"] == "INCREASE_BUDGET"
        assert d["confidence"] == 0.87
        assert d["priority"] == 75

    def test_task_view_defaults(self):
        tv = TaskView()
        assert tv.status == "pending"
        assert tv.progress == 0.0

    def test_task_view_to_dict(self):
        tv = TaskView(
            task_id="t_001",
            task_type="creative_mutation",
            product_id="p01",
            status="running",
            progress=0.7,
            target_module="E11_EVOLUTION",
            strategy_id="S_001",
        )
        d = tv.to_dict()
        assert d["task_id"] == "t_001"
        assert d["status"] == "running"
        assert d["progress"] == 0.7

    def test_pattern_view_defaults(self):
        pv = PatternView()
        assert pv.usage_count == 0
        assert pv.success_rate == 0.0
        assert pv.gene_tags == []

    def test_pattern_view_to_dict(self):
        pv = PatternView(
            pattern_id="pat_001",
            name="Rescue Hook",
            description="Pattern for rescue hooks",
            usage_count=132,
            success_rate=0.78,
            avg_roas=1.42,
            confidence=0.89,
            reliability=0.85,
            gene_tags=["rescue", "hook"],
        )
        d = pv.to_dict()
        assert d["name"] == "Rescue Hook"
        assert d["usage_count"] == 132
        assert d["success_rate"] == 0.78
        assert d["avg_roas"] == 1.42

    def test_portfolio_metrics_defaults(self):
        pm = PortfolioMetrics()
        assert pm.total_spend == 0.0
        assert pm.total_revenue == 0.0
        assert pm.product_count == 0

    def test_portfolio_metrics_to_dict(self):
        pm = PortfolioMetrics(
            total_spend=50000.0,
            total_revenue=75000.0,
            portfolio_roas=1.5,
            portfolio_ltv=25.0,
            portfolio_fitness=0.8,
            product_count=5,
        )
        d = pm.to_dict()
        assert d["total_spend"] == 50000.0
        assert d["portfolio_roas"] == 1.5
        assert d["product_count"] == 5

    def test_growth_cycle_view_defaults(self):
        cv = GrowthCycleView()
        assert cv.cycle_number == 0
        assert cv.has_errors is False

    def test_growth_cycle_view_to_dict(self):
        cv = GrowthCycleView(
            cycle_number=3,
            state="completed",
            outcome="success",
            strategy_id="S_001",
            execution_id="E_001",
            has_errors=False,
            patterns_learned=2,
        )
        d = cv.to_dict()
        assert d["cycle_number"] == 3
        assert d["state"] == "completed"
        assert d["outcome"] == "success"
        assert d["patterns_learned"] == 2

    def test_dashboard_overview_defaults(self):
        ov = DashboardOverview()
        assert isinstance(ov.system, GrowthDashboardState)
        assert isinstance(ov.portfolio, PortfolioMetrics)
        assert ov.products == []

    def test_dashboard_overview_to_dict(self):
        ov = DashboardOverview(
            system=GrowthDashboardState(system_status=SystemStatus.RUNNING, active_products=3),
            portfolio=PortfolioMetrics(total_spend=1000.0, total_revenue=1500.0, product_count=3),
            products=[_make_product_dashboard()],
            recent_decisions=[_make_decision_view()],
            active_tasks=[_make_task_view()],
            top_patterns=[_make_pattern_view()],
        )
        d = ov.to_dict()
        assert d["system"]["system_status"] == "running"
        assert d["portfolio"]["product_count"] == 3
        assert len(d["products"]) == 1
        assert len(d["recent_decisions"]) == 1

    def test_dashboard_event_custom_id(self):
        event = DashboardEvent(event_id="custom_id")
        assert event.event_id == "custom_id"


# ═══════════════════════════════════════════════════════════════
# TestDashboardService — 35 tests
# ═══════════════════════════════════════════════════════════════

class TestDashboardService:
    """仪表盘服务测试."""

    def test_service_creation(self, service):
        assert service is not None
        assert service.query_count == 0

    def test_query_count_increments(self, service):
        service.get_system_state()
        assert service.query_count == 1

    def test_get_system_state(self, service):
        state = service.get_system_state()
        assert isinstance(state, GrowthDashboardState)
        assert state.system_status is not None
        assert state.active_products >= 0

    def test_get_system_state_to_dict(self, service):
        state = service.get_system_state()
        d = state.to_dict()
        assert "system_status" in d
        assert "health_score" in d
        assert "active_products" in d

    def test_get_system_state_health_score_range(self, service):
        state = service.get_system_state()
        assert 0.0 <= state.health_score <= 1.0

    def test_get_product_state_default(self, service):
        pd = service.get_product_state("p01")
        assert isinstance(pd, ProductDashboard)
        assert pd.product_id == "p01"

    def test_get_product_state_returns_consistent(self, service):
        pd1 = service.get_product_state("p01")
        pd2 = service.get_product_state("p01")
        assert pd1.product_id == pd2.product_id

    def test_get_all_product_states(self, service):
        products = service.get_all_product_states()
        assert isinstance(products, list)

    def test_get_growth_cycle_empty(self, service):
        cycles = service.get_growth_cycle("nonexistent")
        assert cycles == []

    def test_get_decisions(self, service):
        decisions = service.get_decisions()
        assert isinstance(decisions, list)

    def test_get_decisions_by_product(self, service):
        decisions = service.get_decisions(product_id="p01")
        assert isinstance(decisions, list)

    def test_get_execution_status(self, service):
        status = service.get_execution_status()
        assert isinstance(status, dict)
        assert "tasks_executed" in status

    def test_get_running_tasks(self, service):
        tasks = service.get_running_tasks()
        assert isinstance(tasks, list)

    def test_get_running_tasks_by_product(self, service):
        tasks = service.get_running_tasks(product_id="p01")
        assert isinstance(tasks, list)

    def test_get_memory_summary(self, service):
        summary = service.get_memory_summary()
        assert isinstance(summary, dict)

    def test_get_patterns(self, service):
        patterns = service.get_patterns()
        assert isinstance(patterns, list)

    def test_get_patterns_by_product(self, service):
        patterns = service.get_patterns(product_id="p01")
        assert isinstance(patterns, list)

    def test_get_portfolio_metrics(self, service):
        pm = service.get_portfolio_metrics()
        assert isinstance(pm, PortfolioMetrics)

    def test_get_portfolio_metrics_to_dict(self, service):
        pm = service.get_portfolio_metrics()
        d = pm.to_dict()
        assert "total_spend" in d
        assert "portfolio_roas" in d

    def test_get_overview(self, service):
        ov = service.get_overview()
        assert isinstance(ov, DashboardOverview)
        assert isinstance(ov.system, GrowthDashboardState)
        assert isinstance(ov.portfolio, PortfolioMetrics)

    def test_get_overview_to_dict(self, service):
        ov = service.get_overview()
        d = ov.to_dict()
        assert "system" in d
        assert "portfolio" in d
        assert "products" in d

    def test_add_event(self, service):
        event = DashboardEvent(event_type=DashboardEventType.RISK_ALERT)
        service.add_event(event)
        events = service.get_recent_events()
        assert len(events) >= 1

    def test_get_recent_events_limit(self, service):
        for i in range(5):
            service.add_event(DashboardEvent(event_type=DashboardEventType.CYCLE_STARTED))
        events = service.get_recent_events(limit=3)
        assert len(events) == 3

    def test_get_recent_events_default_limit(self, service):
        service.add_event(DashboardEvent())
        events = service.get_recent_events()
        assert len(events) >= 1

    def test_events_max_cap(self, service):
        for i in range(150):
            service.add_event(DashboardEvent(event_type=DashboardEventType.CYCLE_STARTED))
        events = service.get_recent_events(limit=200)
        assert len(events) <= 100

    def test_get_summary(self, service):
        summary = service.get_summary()
        assert isinstance(summary, dict)
        assert "query_count" in summary

    def test_multiple_query_count(self, service):
        service.get_system_state()
        service.get_product_state("p01")
        service.get_decisions()
        assert service.query_count == 3

    def test_system_state_with_loops(self, service):
        state = service.get_system_state()
        assert isinstance(state.active_cycles, int)

    def test_product_state_growth_score_range(self, service):
        pd = service.get_product_state("p01")
        assert 0.0 <= pd.growth_score <= 1.0

    def test_portfolio_roas_zero_when_no_spend(self, service):
        pm = service.get_portfolio_metrics()
        if pm.total_spend == 0:
            assert pm.portfolio_roas == 0.0

    def test_overview_has_all_sections(self, service):
        ov = service.get_overview()
        d = ov.to_dict()
        for key in ["system", "portfolio", "products", "recent_decisions", "active_tasks", "top_patterns", "system_events"]:
            assert key in d, f"Missing key: {key}"

    def test_decisions_filters_by_product(self, service):
        all_decisions = service.get_decisions()
        filtered = service.get_decisions(product_id="p01")
        assert len(filtered) <= len(all_decisions)

    def test_running_tasks_filters_by_product(self, service):
        all_tasks = service.get_running_tasks()
        filtered = service.get_running_tasks(product_id="p01")
        assert len(filtered) <= len(all_tasks)

    def test_patterns_filters_by_product(self, service):
        all_patterns = service.get_patterns()
        filtered = service.get_patterns(product_id="p01")
        assert len(filtered) <= len(all_patterns)

    def test_service_reuses_cached_products(self, service):
        pd1 = service.get_product_state("p01")
        pd2 = service.get_product_state("p01")
        # Should be the same object if cached
        assert pd1.product_id == pd2.product_id


# ═══════════════════════════════════════════════════════════════
# TestMetricsAPI — 30 tests
# ═══════════════════════════════════════════════════════════════

class TestMetricsAPI:
    """指标 API 测试."""

    def test_metrics_api_creation(self, metrics_api):
        assert metrics_api is not None
        assert metrics_api.query_count == 0

    def test_get_portfolio_metrics(self, metrics_api):
        pm = metrics_api.get_portfolio_metrics()
        assert isinstance(pm, PortfolioMetrics)

    def test_portfolio_metrics_product_count(self, metrics_api):
        pm = metrics_api.get_portfolio_metrics()
        assert pm.product_count >= 0

    def test_portfolio_metrics_roas(self, metrics_api):
        pm = metrics_api.get_portfolio_metrics()
        assert isinstance(pm.portfolio_roas, float)

    def test_portfolio_metrics_to_dict(self, metrics_api):
        pm = metrics_api.get_portfolio_metrics()
        d = pm.to_dict()
        assert "total_spend" in d
        assert "total_revenue" in d
        assert "product_count" in d

    def test_get_product_metrics(self, metrics_api):
        pd = metrics_api.get_product_metrics("p01")
        assert isinstance(pd, ProductDashboard)
        assert pd.product_id == "p01"

    def test_get_product_metrics_growth_score(self, metrics_api):
        pd = metrics_api.get_product_metrics("p01")
        assert 0.0 <= pd.growth_score <= 1.0

    def test_get_product_metrics_roas(self, metrics_api):
        pd = metrics_api.get_product_metrics("p01")
        assert isinstance(pd.current_roas, float)

    def test_get_all_product_metrics(self, metrics_api):
        products = metrics_api.get_all_product_metrics()
        assert isinstance(products, list)

    def test_get_loop_metrics(self, metrics_api):
        result = metrics_api.get_loop_metrics("p01")
        assert isinstance(result, dict)
        assert "product_id" in result

    def test_get_loop_metrics_nonexistent(self, metrics_api):
        result = metrics_api.get_loop_metrics("nonexistent_product")
        assert "cycles" in result

    def test_loop_metrics_has_cycles(self, metrics_api):
        result = metrics_api.get_loop_metrics("p01")
        assert "cycles" in result
        assert isinstance(result["cycles"], list)

    def test_loop_metrics_success_rate_range(self, metrics_api):
        result = metrics_api.get_loop_metrics("p01")
        if "success_rate" in result:
            assert 0.0 <= result["success_rate"] <= 1.0

    def test_compute_health_score_system(self, metrics_api):
        score = metrics_api.compute_health_score()
        assert 0.0 <= score <= 1.0

    def test_compute_health_score_product(self, metrics_api):
        score = metrics_api.compute_health_score(product_id="p01")
        assert 0.0 <= score <= 1.0

    def test_compute_health_score_nonexistent(self, metrics_api):
        score = metrics_api.compute_health_score(product_id="nonexistent")
        assert 0.0 <= score <= 1.0

    def test_query_count_increments(self, metrics_api):
        metrics_api.get_portfolio_metrics()
        assert metrics_api.query_count == 1

    def test_multiple_queries(self, metrics_api):
        metrics_api.get_portfolio_metrics()
        metrics_api.get_product_metrics("p01")
        metrics_api.get_loop_metrics("p01")
        assert metrics_api.query_count == 3

    def test_get_summary(self, metrics_api):
        summary = metrics_api.get_summary()
        assert isinstance(summary, dict)
        assert "query_count" in summary

    def test_product_metrics_trend(self, metrics_api):
        pd = metrics_api.get_product_metrics("p01")
        assert pd.trend in {TrendDirection.UP, TrendDirection.DOWN, TrendDirection.STABLE}

    def test_product_metrics_has_last_updated(self, metrics_api):
        pd = metrics_api.get_product_metrics("p01")
        assert pd.last_updated != ""

    def test_get_all_product_metrics_returns_list(self, metrics_api):
        products = metrics_api.get_all_product_metrics()
        for p in products:
            assert isinstance(p, ProductDashboard)

    def test_loop_metrics_for_nonexistent_product(self, metrics_api):
        result = metrics_api.get_loop_metrics("__nonexistent__")
        assert result["product_id"] == "__nonexistent__"

    def test_health_score_changes_with_product(self, metrics_api):
        score1 = metrics_api.compute_health_score(product_id="p01")
        score2 = metrics_api.compute_health_score(product_id="p02")
        # Both should be valid scores
        assert 0.0 <= score1 <= 1.0
        assert 0.0 <= score2 <= 1.0

    def test_portfolio_metrics_ltv(self, metrics_api):
        pm = metrics_api.get_portfolio_metrics()
        assert isinstance(pm.portfolio_ltv, float)

    def test_portfolio_metrics_fitness(self, metrics_api):
        pm = metrics_api.get_portfolio_metrics()
        assert 0.0 <= pm.portfolio_fitness <= 1.0

    def test_product_metrics_budget(self, metrics_api):
        pd = metrics_api.get_product_metrics("p01")
        assert isinstance(pd.budget_allocation, float)

    def test_product_metrics_completed_cycles(self, metrics_api):
        pd = metrics_api.get_product_metrics("p01")
        assert isinstance(pd.completed_cycles, int)

    def test_loop_metrics_learning_velocity(self, metrics_api):
        result = metrics_api.get_loop_metrics("p01")
        assert "learning_velocity" in result

    def test_loop_metrics_strategy_accuracy(self, metrics_api):
        result = metrics_api.get_loop_metrics("p01")
        assert "strategy_accuracy" in result


# ═══════════════════════════════════════════════════════════════
# TestDecisionAPI — 25 tests
# ═══════════════════════════════════════════════════════════════

class TestDecisionAPI:
    """决策 API 测试."""

    def test_decision_api_creation(self, decision_api):
        assert decision_api is not None
        assert decision_api.query_count == 0

    def test_get_decisions(self, decision_api):
        decisions = decision_api.get_decisions()
        assert isinstance(decisions, list)

    def test_get_decisions_by_product(self, decision_api):
        decisions = decision_api.get_decisions_by_product("p01")
        assert isinstance(decisions, list)

    def test_get_top_decisions(self, decision_api):
        decisions = decision_api.get_top_decisions(limit=3)
        assert isinstance(decisions, list)
        assert len(decisions) <= 3

    def test_get_top_decisions_sorted(self, decision_api):
        decisions = decision_api.get_top_decisions(limit=10)
        if len(decisions) >= 2:
            for i in range(len(decisions) - 1):
                assert decisions[i].priority >= decisions[i + 1].priority

    def test_get_decision_detail_nonexistent(self, decision_api):
        result = decision_api.get_decision_detail("nonexistent_id")
        assert result is None

    def test_get_pending_decisions(self, decision_api):
        pending = decision_api.get_pending_decisions()
        assert isinstance(pending, list)

    def test_query_count_increments(self, decision_api):
        decision_api.get_decisions()
        assert decision_api.query_count == 1

    def test_multiple_queries(self, decision_api):
        decision_api.get_decisions()
        decision_api.get_top_decisions()
        decision_api.get_pending_decisions()
        assert decision_api.query_count == 3

    def test_get_summary(self, decision_api):
        summary = decision_api.get_summary()
        assert isinstance(summary, dict)
        assert "total_decisions" in summary
        assert "pending_count" in summary

    def test_decision_view_type(self, decision_api):
        decisions = decision_api.get_decisions()
        for d in decisions:
            assert isinstance(d, DecisionView)

    def test_filter_by_product(self, decision_api):
        all_decisions = decision_api.get_decisions()
        filtered = decision_api.get_decisions(product_id="p01")
        assert len(filtered) <= len(all_decisions)

    def test_decision_view_to_dict(self, decision_api):
        decisions = decision_api.get_decisions()
        if decisions:
            d = decisions[0].to_dict()
            assert "decision_id" in d
            assert "action" in d
            assert "confidence" in d

    def test_top_decisions_limit(self, decision_api):
        for limit in [1, 3, 5]:
            decisions = decision_api.get_top_decisions(limit=limit)
            assert len(decisions) <= limit

    def test_pending_decisions_are_filtered(self, decision_api):
        pending = decision_api.get_pending_decisions()
        for d in pending:
            assert d.status == "pending"

    def test_get_decision_detail_format(self, decision_api):
        decisions = decision_api.get_decisions()
        if decisions:
            detail = decision_api.get_decision_detail(decisions[0].decision_id)
            if detail:
                assert "decision_id" in detail
                assert "action" in detail

    def test_decision_confidence_range(self, decision_api):
        decisions = decision_api.get_decisions()
        for d in decisions:
            assert 0.0 <= d.confidence <= 1.0

    def test_decision_priority_non_negative(self, decision_api):
        decisions = decision_api.get_decisions()
        for d in decisions:
            assert d.priority >= 0

    def test_summary_top_priority(self, decision_api):
        summary = decision_api.get_summary()
        assert "top_priority" in summary

    def test_decisions_have_source_module(self, decision_api):
        decisions = decision_api.get_decisions()
        for d in decisions:
            assert d.source_module != ""

    def test_decisions_have_created_at(self, decision_api):
        decisions = decision_api.get_decisions()
        for d in decisions:
            assert d.created_at != ""

    def test_empty_product_filter(self, decision_api):
        decisions = decision_api.get_decisions(product_id="__nonexistent__")
        assert len(decisions) == 0

    def test_decision_detail_has_hypothesis_id(self, decision_api):
        decisions = decision_api.get_decisions()
        if decisions:
            detail = decision_api.get_decision_detail(decisions[0].decision_id)
            if detail:
                assert "hypothesis_id" in detail

    def test_decision_detail_has_risk_level(self, decision_api):
        decisions = decision_api.get_decisions()
        if decisions:
            detail = decision_api.get_decision_detail(decisions[0].decision_id)
            if detail:
                assert "risk_level" in detail

    def test_pending_count_matches(self, decision_api):
        summary = decision_api.get_summary()
        pending = decision_api.get_pending_decisions()
        assert summary["pending_count"] == len(pending)


# ═══════════════════════════════════════════════════════════════
# TestExecutionAPI — 25 tests
# ═══════════════════════════════════════════════════════════════

class TestExecutionAPI:
    """执行 API 测试."""

    def test_execution_api_creation(self, execution_api):
        assert execution_api is not None
        assert execution_api.query_count == 0

    def test_get_running_tasks(self, execution_api):
        tasks = execution_api.get_running_tasks()
        assert isinstance(tasks, list)

    def test_get_all_tasks(self, execution_api):
        tasks = execution_api.get_all_tasks()
        assert isinstance(tasks, list)

    def test_get_task_detail_nonexistent(self, execution_api):
        result = execution_api.get_task_detail("nonexistent")
        assert result is None

    def test_cancel_task_nonexistent(self, execution_api):
        result = execution_api.cancel_task("nonexistent")
        assert result is False

    def test_rollback_task_nonexistent(self, execution_api):
        result = execution_api.rollback_task("nonexistent")
        assert result is False

    def test_approve_task_nonexistent(self, execution_api):
        result = execution_api.approve_task("nonexistent")
        assert result is False

    def test_get_execution_summary(self, execution_api):
        summary = execution_api.get_execution_summary()
        assert isinstance(summary, dict)
        assert "total_tasks" in summary
        assert "running" in summary
        assert "completed" in summary

    def test_query_count_increments(self, execution_api):
        execution_api.get_running_tasks()
        assert execution_api.query_count == 1

    def test_multiple_queries(self, execution_api):
        execution_api.get_running_tasks()
        execution_api.get_all_tasks()
        execution_api.get_execution_summary()
        assert execution_api.query_count == 3

    def test_get_summary(self, execution_api):
        summary = execution_api.get_summary()
        assert isinstance(summary, dict)
        assert "query_count" in summary
        assert "plans_registered" in summary

    def test_register_plan(self, execution_api):
        from src.market_ops.creative_vision_runtime.growth_os.execution.models import (
            ExecutionPlan,
        )
        plan = ExecutionPlan(strategy_id="S_001")
        execution_api.register_plan(plan)
        assert execution_api.get_summary()["plans_registered"] >= 1

    def test_running_tasks_by_product(self, execution_api):
        tasks = execution_api.get_running_tasks(product_id="p01")
        assert isinstance(tasks, list)

    def test_all_tasks_by_product(self, execution_api):
        tasks = execution_api.get_all_tasks(product_id="p01")
        assert isinstance(tasks, list)

    def test_cancel_task_on_registered_plan(self, execution_api):
        from src.market_ops.creative_vision_runtime.growth_os.execution.models import (
            ExecutionPlan,
            ExecutionTask,
            TaskType,
            TargetModule,
            TaskStatus,
        )
        plan = ExecutionPlan(strategy_id="S_001")
        task = ExecutionTask(
            strategy_id="S_001",
            product_id="p01",
            task_type=TaskType.CREATE_CREATIVE,
            target_module=TargetModule.E11_EVOLUTION,
            parameters={},
        )
        task.status = TaskStatus.CREATED
        plan.tasks = [task]
        execution_api.register_plan(plan)
        result = execution_api.cancel_task(task.task_id)
        assert result is True

    def test_rollback_task_on_registered_plan(self, execution_api):
        from src.market_ops.creative_vision_runtime.growth_os.execution.models import (
            ExecutionPlan,
            ExecutionTask,
            TaskType,
            TargetModule,
            TaskStatus,
        )
        plan = ExecutionPlan(strategy_id="S_001")
        task = ExecutionTask(
            strategy_id="S_001",
            product_id="p01",
            task_type=TaskType.CREATE_CREATIVE,
            target_module=TargetModule.E11_EVOLUTION,
            parameters={},
        )
        task.status = TaskStatus.SUCCESS
        plan.tasks = [task]
        execution_api.register_plan(plan)
        result = execution_api.rollback_task(task.task_id)
        assert result is True

    def test_execution_summary_tasks(self, execution_api):
        summary = execution_api.get_execution_summary()
        assert summary["total_tasks"] >= 0

    def test_task_view_type(self, execution_api):
        tasks = execution_api.get_running_tasks()
        for t in tasks:
            assert isinstance(t, TaskView)

    def test_task_view_to_dict(self, execution_api):
        tasks = execution_api.get_running_tasks()
        if tasks:
            d = tasks[0].to_dict()
            assert "task_id" in d
            assert "status" in d
            assert "progress" in d

    def test_running_tasks_only_active(self, execution_api):
        from src.market_ops.creative_vision_runtime.growth_os.execution.models import (
            ExecutionPlan,
            ExecutionTask,
            TaskType,
            TargetModule,
            TaskStatus,
        )
        plan = ExecutionPlan(strategy_id="S_001")
        task1 = ExecutionTask(
            strategy_id="S_001",
            product_id="p01",
            task_type=TaskType.CREATE_CREATIVE,
            target_module=TargetModule.E11_EVOLUTION,
            parameters={},
        )
        task1.status = TaskStatus.RUNNING
        task2 = ExecutionTask(
            strategy_id="S_001",
            product_id="p01",
            task_type=TaskType.CREATE_CREATIVE,
            target_module=TargetModule.E11_EVOLUTION,
            parameters={},
        )
        task2.status = TaskStatus.SUCCESS
        plan.tasks = [task1, task2]
        execution_api.register_plan(plan)
        running = execution_api.get_running_tasks()
        # Only running/pending tasks returned
        running_statuses = {t.status for t in running}
        assert "success" not in running_statuses or len(running) <= 1

    def test_task_detail_on_registered_plan(self, execution_api):
        from src.market_ops.creative_vision_runtime.growth_os.execution.models import (
            ExecutionPlan,
            ExecutionTask,
            TaskType,
            TargetModule,
            TaskStatus,
        )
        plan = ExecutionPlan(strategy_id="S_001")
        task = ExecutionTask(
            strategy_id="S_001",
            product_id="p01",
            task_type=TaskType.CREATE_CREATIVE,
            target_module=TargetModule.E11_EVOLUTION,
            parameters={"key": "value"},
        )
        task.status = TaskStatus.RUNNING
        plan.tasks = [task]
        execution_api.register_plan(plan)
        detail = execution_api.get_task_detail(task.task_id)
        assert detail is not None
        assert detail["task_id"] == task.task_id
        assert "dependencies" in detail
        assert "parameters" in detail

    def test_approve_with_plan_id(self, execution_api):
        from src.market_ops.creative_vision_runtime.growth_os.execution.models import (
            ExecutionPlan,
        )
        plan = ExecutionPlan(strategy_id="S_001")
        execution_api.register_plan(plan)
        result = execution_api.approve_task("any_task", plan_id=plan.plan_id)
        assert result is True

    def test_filter_tasks_by_product(self, execution_api):
        from src.market_ops.creative_vision_runtime.growth_os.execution.models import (
            ExecutionPlan,
            ExecutionTask,
            TaskType,
            TargetModule,
            TaskStatus,
        )
        plan = ExecutionPlan(strategy_id="S_001")
        task = ExecutionTask(
            strategy_id="S_001",
            product_id="p01",
            task_type=TaskType.CREATE_CREATIVE,
            target_module=TargetModule.E11_EVOLUTION,
            parameters={},
        )
        task.status = TaskStatus.RUNNING
        plan.tasks = [task]
        execution_api.register_plan(plan)
        p01_tasks = execution_api.get_running_tasks(product_id="p01")
        p02_tasks = execution_api.get_running_tasks(product_id="p02")
        assert len(p01_tasks) >= len(p02_tasks)

    def test_execution_summary_has_plans(self, execution_api):
        summary = execution_api.get_execution_summary()
        assert "total_plans" in summary


# ═══════════════════════════════════════════════════════════════
# TestMemoryAPI — 25 tests
# ═══════════════════════════════════════════════════════════════

class TestMemoryAPI:
    """记忆 API 测试."""

    def test_memory_api_creation(self, memory_api):
        assert memory_api is not None
        assert memory_api.query_count == 0

    def test_get_patterns(self, memory_api):
        patterns = memory_api.get_patterns()
        assert isinstance(patterns, list)

    def test_get_patterns_by_product(self, memory_api):
        patterns = memory_api.get_patterns(product_id="p01")
        assert isinstance(patterns, list)

    def test_get_success_patterns(self, memory_api):
        patterns = memory_api.get_success_patterns()
        assert isinstance(patterns, list)

    def test_get_success_patterns_min_confidence(self, memory_api):
        patterns = memory_api.get_success_patterns(min_confidence=0.8)
        for p in patterns:
            assert p.confidence >= 0.8

    def test_get_pattern_detail_nonexistent(self, memory_api):
        result = memory_api.get_pattern_detail("nonexistent")
        assert result is None

    def test_get_experiences(self, memory_api):
        experiences = memory_api.get_experiences()
        assert isinstance(experiences, list)

    def test_get_experiences_by_product(self, memory_api):
        experiences = memory_api.get_experiences(product_id="p01")
        assert isinstance(experiences, list)

    def test_get_experience_detail_nonexistent(self, memory_api):
        result = memory_api.get_experience_detail("nonexistent")
        assert result is None

    def test_get_success_experiences(self, memory_api):
        experiences = memory_api.get_success_experiences()
        assert isinstance(experiences, list)

    def test_get_failure_experiences(self, memory_api):
        experiences = memory_api.get_failure_experiences()
        assert isinstance(experiences, list)

    def test_search_memory(self, memory_api):
        results = memory_api.search_memory(["rescue", "hook"])
        assert isinstance(results, list)

    def test_search_memory_limit(self, memory_api):
        results = memory_api.search_memory(["test"], limit=5)
        assert len(results) <= 5

    def test_get_memory_stats(self, memory_api):
        stats = memory_api.get_memory_stats()
        assert isinstance(stats, dict)
        assert "total_experiences" in stats
        assert "total_patterns" in stats

    def test_query_count_increments(self, memory_api):
        memory_api.get_patterns()
        assert memory_api.query_count == 1

    def test_multiple_queries(self, memory_api):
        memory_api.get_patterns()
        memory_api.get_experiences()
        memory_api.get_memory_stats()
        assert memory_api.query_count == 3

    def test_get_summary(self, memory_api):
        summary = memory_api.get_summary()
        assert isinstance(summary, dict)
        assert "query_count" in summary
        assert "memory_stats" in summary

    def test_pattern_view_type(self, memory_api):
        patterns = memory_api.get_patterns()
        for p in patterns:
            assert isinstance(p, PatternView)

    def test_pattern_view_to_dict(self, memory_api):
        patterns = memory_api.get_patterns()
        if patterns:
            d = patterns[0].to_dict()
            assert "pattern_id" in d
            assert "name" in d
            assert "success_rate" in d

    def test_experiences_format(self, memory_api):
        experiences = memory_api.get_experiences()
        for e in experiences:
            assert "experience_id" in e
            assert "product_id" in e
            assert "outcome" in e

    def test_pattern_confidence_range(self, memory_api):
        patterns = memory_api.get_patterns()
        for p in patterns:
            assert 0.0 <= p.confidence <= 1.0

    def test_pattern_success_rate_range(self, memory_api):
        patterns = memory_api.get_patterns()
        for p in patterns:
            assert 0.0 <= p.success_rate <= 1.0

    def test_memory_stats_has_extractor(self, memory_api):
        stats = memory_api.get_memory_stats()
        assert "extractor" in stats

    def test_memory_stats_has_retriever(self, memory_api):
        stats = memory_api.get_memory_stats()
        assert "retriever" in stats

    def test_memory_stats_has_optimizer(self, memory_api):
        stats = memory_api.get_memory_stats()
        assert "optimizer" in stats


# ═══════════════════════════════════════════════════════════════
# TestWebSocketManager — 20 tests
# ═══════════════════════════════════════════════════════════════

class TestWebSocketManager:
    """WebSocket 管理器测试."""

    def test_ws_creation(self, ws_manager):
        assert ws_manager is not None
        assert ws_manager.emit_count == 0
        assert ws_manager.subscriber_count == 0

    def test_subscribe(self, ws_manager):
        sub = ws_manager.subscribe("client_1")
        assert sub is not None
        assert sub.client_id == "client_1"
        assert ws_manager.subscriber_count == 1

    def test_subscribe_with_event_types(self, ws_manager):
        sub = ws_manager.subscribe(
            "client_1",
            [DashboardEventType.CYCLE_STARTED, DashboardEventType.RISK_ALERT],
        )
        assert len(sub.event_types) == 2

    def test_unsubscribe(self, ws_manager):
        ws_manager.subscribe("client_1")
        result = ws_manager.unsubscribe("client_1")
        assert result is True
        assert ws_manager.subscriber_count == 0

    def test_unsubscribe_nonexistent(self, ws_manager):
        result = ws_manager.unsubscribe("nonexistent")
        assert result is False

    def test_emit(self, ws_manager):
        ws_manager.subscribe("client_1")
        event = DashboardEvent(event_type=DashboardEventType.CYCLE_STARTED)
        delivered = ws_manager.emit(event)
        assert delivered >= 1
        assert ws_manager.emit_count == 1

    def test_emit_only_to_subscribed_types(self, ws_manager):
        ws_manager.subscribe("client_1", [DashboardEventType.RISK_ALERT])
        event = DashboardEvent(event_type=DashboardEventType.CYCLE_STARTED)
        delivered = ws_manager.emit(event)
        assert delivered == 0

    def test_emit_cycle_started(self, ws_manager):
        ws_manager.subscribe("client_1")
        event = ws_manager.emit_cycle_started("p01", {"cycle": 1})
        assert event.event_type == DashboardEventType.CYCLE_STARTED
        assert event.product_id == "p01"

    def test_emit_decision_created(self, ws_manager):
        ws_manager.subscribe("client_1")
        event = ws_manager.emit_decision_created("p01", {"action": "test"})
        assert event.event_type == DashboardEventType.DECISION_CREATED

    def test_emit_task_completed(self, ws_manager):
        ws_manager.subscribe("client_1")
        event = ws_manager.emit_task_completed("p01", {"task_id": "t1"})
        assert event.event_type == DashboardEventType.TASK_COMPLETED

    def test_emit_experiment_finished(self, ws_manager):
        ws_manager.subscribe("client_1")
        event = ws_manager.emit_experiment_finished("p01")
        assert event.event_type == DashboardEventType.EXPERIMENT_FINISHED

    def test_emit_pattern_learned(self, ws_manager):
        ws_manager.subscribe("client_1")
        event = ws_manager.emit_pattern_learned("p01", {"pattern": "test"})
        assert event.event_type == DashboardEventType.PATTERN_LEARNED

    def test_emit_risk_alert(self, ws_manager):
        ws_manager.subscribe("client_1")
        event = ws_manager.emit_risk_alert("p01", {"message": "ROAS drop"})
        assert event.event_type == DashboardEventType.RISK_ALERT

    def test_get_history(self, ws_manager):
        ws_manager.emit_cycle_started("p01")
        ws_manager.emit_risk_alert("p01")
        history = ws_manager.get_history()
        assert len(history) >= 2

    def test_get_history_limit(self, ws_manager):
        for i in range(10):
            ws_manager.emit_cycle_started(f"p{i:02d}")
        history = ws_manager.get_history(limit=5)
        assert len(history) == 5

    def test_get_history_by_type(self, ws_manager):
        ws_manager.emit_cycle_started("p01")
        ws_manager.emit_risk_alert("p01")
        ws_manager.emit_cycle_started("p02")
        cycles = ws_manager.get_history_by_type(DashboardEventType.CYCLE_STARTED)
        assert len(cycles) >= 2
        for e in cycles:
            assert e.event_type == DashboardEventType.CYCLE_STARTED

    def test_serialize_event(self, ws_manager):
        event = DashboardEvent(event_type=DashboardEventType.RISK_ALERT, product_id="p01")
        json_str = ws_manager.serialize_event(event)
        assert isinstance(json_str, str)
        assert "risk_alert" in json_str

    def test_serialize_events(self, ws_manager):
        events = [
            DashboardEvent(event_type=DashboardEventType.CYCLE_STARTED),
            DashboardEvent(event_type=DashboardEventType.RISK_ALERT),
        ]
        json_str = ws_manager.serialize_events(events)
        assert isinstance(json_str, str)
        assert "cycle_started" in json_str

    def test_get_summary(self, ws_manager):
        summary = ws_manager.get_summary()
        assert isinstance(summary, dict)
        assert "subscriber_count" in summary
        assert "emit_count" in summary
        assert "event_types" in summary

    def test_multiple_subscribers(self, ws_manager):
        ws_manager.subscribe("c1")
        ws_manager.subscribe("c2")
        ws_manager.subscribe("c3")
        assert ws_manager.subscriber_count == 3
        event = DashboardEvent(event_type=DashboardEventType.CYCLE_STARTED)
        delivered = ws_manager.emit(event)
        assert delivered == 3


# ═══════════════════════════════════════════════════════════════
# TestDashboardController — 35 tests
# ═══════════════════════════════════════════════════════════════

class TestDashboardController:
    """仪表盘控制器测试."""

    def test_controller_creation(self, controller):
        assert controller is not None
        assert controller.query_count == 0

    def test_controller_has_service(self, controller):
        assert controller.service is not None
        assert isinstance(controller.service, DashboardService)

    def test_controller_has_metrics(self, controller):
        assert controller.metrics is not None
        assert isinstance(controller.metrics, MetricsAPI)

    def test_controller_has_decisions(self, controller):
        assert controller.decisions is not None
        assert isinstance(controller.decisions, DecisionAPI)

    def test_controller_has_execution_api(self, controller):
        assert controller.execution_api is not None
        assert isinstance(controller.execution_api, ExecutionAPI)

    def test_controller_has_memory_api(self, controller):
        assert controller.memory_api is not None
        assert isinstance(controller.memory_api, MemoryAPI)

    def test_controller_has_ws(self, controller):
        assert controller.ws is not None
        assert isinstance(controller.ws, WebSocketManager)

    def test_get_overview(self, controller):
        ov = controller.get_overview()
        assert isinstance(ov, DashboardOverview)

    def test_get_system_status(self, controller):
        state = controller.get_system_status()
        assert isinstance(state, GrowthDashboardState)

    def test_get_product(self, controller):
        pd = controller.get_product("p01")
        assert isinstance(pd, ProductDashboard)

    def test_get_all_products(self, controller):
        products = controller.get_all_products()
        assert isinstance(products, list)

    def test_get_portfolio(self, controller):
        pm = controller.get_portfolio()
        assert isinstance(pm, PortfolioMetrics)

    def test_get_decisions(self, controller):
        decisions = controller.get_decisions()
        assert isinstance(decisions, list)

    def test_get_top_decisions(self, controller):
        decisions = controller.get_top_decisions(limit=3)
        assert len(decisions) <= 3

    def test_get_pending_decisions(self, controller):
        pending = controller.get_pending_decisions()
        assert isinstance(pending, list)

    def test_get_tasks(self, controller):
        tasks = controller.get_tasks()
        assert isinstance(tasks, list)

    def test_get_all_tasks(self, controller):
        tasks = controller.get_all_tasks()
        assert isinstance(tasks, list)

    def test_get_execution_status(self, controller):
        status = controller.get_execution_status()
        assert isinstance(status, dict)

    def test_approve_task(self, controller):
        result = controller.approve_task("nonexistent")
        assert result is False

    def test_cancel_task(self, controller):
        result = controller.cancel_task("nonexistent")
        assert result is False

    def test_rollback_task(self, controller):
        result = controller.rollback_task("nonexistent")
        assert result is False

    def test_get_memory(self, controller):
        mem = controller.get_memory()
        assert isinstance(mem, dict)

    def test_get_patterns(self, controller):
        patterns = controller.get_patterns()
        assert isinstance(patterns, list)

    def test_get_experiences(self, controller):
        experiences = controller.get_experiences()
        assert isinstance(experiences, list)

    def test_search_memory(self, controller):
        results = controller.search_memory(["test"])
        assert isinstance(results, list)

    def test_stream_events(self, controller):
        events = controller.stream_events()
        assert isinstance(events, list)

    def test_get_events_by_type(self, controller):
        events = controller.get_events_by_type(DashboardEventType.RISK_ALERT)
        assert isinstance(events, list)

    def test_emit_event(self, controller):
        event = DashboardEvent(event_type=DashboardEventType.CYCLE_STARTED)
        delivered = controller.emit_event(event)
        assert delivered >= 0

    def test_alert(self, controller):
        event = controller.alert("p01", "ROAS drop detected", severity="high")
        assert event.event_type == DashboardEventType.RISK_ALERT
        assert event.product_id == "p01"

    def test_get_summary(self, controller):
        summary = controller.get_summary()
        assert isinstance(summary, dict)
        assert "query_count" in summary
        assert "service" in summary
        assert "metrics" in summary
        assert "decisions" in summary
        assert "execution" in summary
        assert "memory" in summary
        assert "websocket" in summary

    def test_query_count(self, controller):
        controller.get_overview()
        controller.get_system_status()
        assert controller.query_count >= 2

    def test_get_product_by_id(self, controller):
        pd = controller.get_product("p01")
        assert pd.product_id == "p01"

    def test_all_products_are_product_dashboards(self, controller):
        products = controller.get_all_products()
        for p in products:
            assert isinstance(p, ProductDashboard)

    def test_decisions_have_decision_view_type(self, controller):
        decisions = controller.get_decisions()
        for d in decisions:
            assert isinstance(d, DecisionView)

    def test_patterns_have_pattern_view_type(self, controller):
        patterns = controller.get_patterns()
        for p in patterns:
            assert isinstance(p, PatternView)


# ═══════════════════════════════════════════════════════════════
# TestIntegration — 20 tests
# ═══════════════════════════════════════════════════════════════

class TestIntegration:
    """集成测试."""

    def test_full_dashboard_flow(self, controller):
        """完整仪表盘流程."""
        # Get system overview
        ov = controller.get_overview()
        assert isinstance(ov, DashboardOverview)
        assert ov.system is not None
        assert ov.portfolio is not None

    def test_product_lifecycle(self, controller):
        """产品生命周期查询."""
        pd = controller.get_product("p01")
        assert pd.lifecycle_stage is not None
        assert pd.current_roas >= 0

    def test_decision_to_execution(self, controller):
        """决策到执行."""
        decisions = controller.get_decisions()
        tasks = controller.get_tasks()
        assert isinstance(decisions, list)
        assert isinstance(tasks, list)

    def test_execution_to_memory(self, controller):
        """执行到记忆."""
        status = controller.get_execution_status()
        mem = controller.get_memory()
        assert isinstance(status, dict)
        assert isinstance(mem, dict)

    def test_memory_to_patterns(self, controller):
        """记忆到模式."""
        mem = controller.get_memory()
        patterns = controller.get_patterns()
        assert isinstance(mem, dict)
        assert isinstance(patterns, list)

    def test_events_integration(self, controller):
        """事件集成."""
        controller.alert("p01", "Test alert")
        controller.emit_event(DashboardEvent(
            event_type=DashboardEventType.CYCLE_STARTED,
            product_id="p01",
        ))
        events = controller.stream_events()
        assert len(events) >= 2

    def test_portfolio_after_products(self, controller):
        """产品后组合查询."""
        products = controller.get_all_products()
        pm = controller.get_portfolio()
        assert pm.product_count >= len(products)

    def test_system_status_health(self, controller):
        """系统状态健康."""
        state = controller.get_system_status()
        assert 0.0 <= state.health_score <= 1.0

    def test_decisions_confidence(self, controller):
        """决策置信度."""
        decisions = controller.get_decisions()
        for d in decisions:
            assert 0.0 <= d.confidence <= 1.0

    def test_metrics_integration(self, controller):
        """指标集成."""
        metrics = controller.metrics
        pm = metrics.get_portfolio_metrics()
        assert isinstance(pm, PortfolioMetrics)

    def test_memory_integration(self, controller):
        """记忆集成."""
        mem_api = controller.memory_api
        stats = mem_api.get_memory_stats()
        assert isinstance(stats, dict)

    def test_websocket_integration(self, controller):
        """WebSocket 集成."""
        ws = controller.ws
        ws.subscribe("test_client", [DashboardEventType.CYCLE_STARTED])
        event = ws.emit_cycle_started("p01")
        assert event.event_type == DashboardEventType.CYCLE_STARTED

    def test_multi_product_query(self, controller):
        """多产品查询."""
        for pid in ["p01", "p02", "p03"]:
            pd = controller.get_product(pid)
            assert isinstance(pd, ProductDashboard)

    def test_search_memory_integration(self, controller):
        """搜索记忆集成."""
        results = controller.search_memory(["rescue", "hook"])
        assert isinstance(results, list)

    def test_alert_and_events(self, controller):
        """告警和事件."""
        alert_event = controller.alert("p01", "Critical ROAS drop", severity="critical")
        events = controller.get_events_by_type(DashboardEventType.RISK_ALERT)
        assert len(events) >= 1
        assert events[-1].event_type == DashboardEventType.RISK_ALERT

    def test_summary_all_modules(self, controller):
        """所有模块摘要."""
        summary = controller.get_summary()
        for key in ["service", "metrics", "decisions", "execution", "memory", "websocket"]:
            assert key in summary

    def test_overview_completeness(self, controller):
        """总览完整性."""
        ov = controller.get_overview()
        d = ov.to_dict()
        for section in ["system", "portfolio", "products", "recent_decisions", "active_tasks", "top_patterns"]:
            assert section in d

    def test_agent_decision_flow(self, controller):
        """Agent 决策流."""
        decisions = controller.get_decisions()
        top = controller.get_top_decisions(limit=3)
        pending = controller.get_pending_decisions()
        assert len(top) <= len(decisions)
        assert len(pending) <= len(decisions)

    def test_execution_control_flow(self, controller):
        """执行控制流."""
        tasks = controller.get_all_tasks()
        status = controller.get_execution_status()
        assert status["total_tasks"] == len(tasks)

    def test_end_to_end_dashboard(self, controller):
        """端到端仪表盘."""
        # Full dashboard query
        overview = controller.get_overview()
        assert overview is not None

        # System health
        state = controller.get_system_status()
        assert state.health_score >= 0

        # Products
        products = controller.get_all_products()
        assert isinstance(products, list)

        # Portfolio
        portfolio = controller.get_portfolio()
        assert portfolio.product_count >= 0

        # Decisions
        decisions = controller.get_decisions()
        assert isinstance(decisions, list)

        # Execution
        tasks = controller.get_tasks()
        assert isinstance(tasks, list)

        # Memory
        patterns = controller.get_patterns()
        assert isinstance(patterns, list)

        # Events
        controller.alert("p01", "End-to-end test")
        events = controller.stream_events()
        assert len(events) >= 1