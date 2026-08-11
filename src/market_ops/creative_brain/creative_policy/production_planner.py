"""V4.3 Production Planner — generate today's production plan.

Output example:
  Today:
    Generate: 18
    Retest: 6
    Kill: 12

Outputs to Prompt Planner for actual generation.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .schemas import (
    CreativeTask, DailyProductionPlan, DecisionPolicy,
    Portfolio, BudgetAllocation, PolicyAction,
)
from .policy_engine import PolicyEngine
from .creative_scheduler import CreativeScheduler
from .portfolio_manager import PortfolioManager
from .budget_optimizer import BudgetOptimizer
from .resource_allocator import ResourceAllocator
from .exploration_manager import ExplorationManager


class ProductionPlanner:
    """Daily production plan generator.

    Orchestrates: Decide → Schedule → Allocate → Plan.
    """

    def __init__(self, policy_engine: PolicyEngine,
                 max_capacity: int = 50) -> None:
        self._engine = policy_engine
        self._max_capacity = max_capacity

        self._scheduler = CreativeScheduler()
        self._portfolio = PortfolioManager()
        self._budget = BudgetOptimizer()
        self._allocator = ResourceAllocator()
        self._exploration = ExplorationManager()

    def plan(self, creatives: list[dict[str, Any]],
             country_data: list[dict[str, Any]] | None = None,
             market_change_score: float = 0.0) -> DailyProductionPlan:
        """Generate today's production plan.

        Args:
            creatives: List of creative dicts for decision.
            country_data: Country performance data for budget allocation.
            market_change_score: 0=stable, 1=chaotic.

        Returns:
            DailyProductionPlan with tasks, portfolio, and budget.
        """
        # 1. Decide for all creatives
        tasks = self._engine.decide_batch(creatives)

        # 2. Adjust exploration
        failure_rate = self._engine.risk_controller.get_risk_summary()["failure_rate"]
        self._exploration.adjust(market_change_score, failure_rate)

        # 3. Portfolio allocation
        portfolio = self._portfolio.allocate(tasks, self._max_capacity)

        # 4. Budget allocation
        budget = self._budget.allocate(country_data or [])

        # 5. Resource allocation
        scheduled = self._allocator.allocate(tasks, portfolio, self._max_capacity)

        # 6. Schedule
        self._scheduler.schedule(scheduled, self._max_capacity)

        # Count actions
        generate_count = sum(1 for t in tasks if t.action == PolicyAction.GENERATE)
        retest_count = sum(1 for t in tasks if t.action == PolicyAction.RETEST)
        adapt_count = sum(1 for t in tasks if t.action == PolicyAction.ADAPT)
        kill_count = sum(1 for t in tasks if t.action == PolicyAction.KILL)

        return DailyProductionPlan(
            date=datetime.now().strftime("%Y-%m-%d"),
            total_creatives=len(scheduled),
            generate_count=generate_count,
            retest_count=retest_count,
            adapt_count=adapt_count,
            kill_count=kill_count,
            tasks=scheduled,
            portfolio=portfolio,
            budget=budget,
            risk_summary=self._engine.risk_controller.get_risk_summary(),
        )

    @property
    def scheduler(self) -> CreativeScheduler:
        return self._scheduler

    @property
    def portfolio(self) -> PortfolioManager:
        return self._portfolio

    @property
    def budget(self) -> BudgetOptimizer:
        return self._budget

    @property
    def exploration(self) -> ExplorationManager:
        return self._exploration