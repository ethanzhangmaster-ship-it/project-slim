"""E12.7.7 Metrics API — 核心指标展示: Portfolio / Product / Growth Loop."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..loop.loop_controller import LoopController
from ..memory.memory_controller import MemoryController

from .models import (
    GrowthCycleView,
    PortfolioMetrics,
    ProductDashboard,
    TrendDirection,
)


class MetricsAPI:
    """指标 API — 展示 Portfolio、Product、Growth Loop 核心指标.

    提供:
      - get_portfolio_metrics(): 组合指标
      - get_product_metrics():   产品指标
      - get_loop_metrics():      循环指标
      - compute_health_score():  健康分数
    """

    def __init__(
        self,
        loop_controller: LoopController | None = None,
        memory: MemoryController | None = None,
    ):
        self._loop = loop_controller or LoopController()
        self._memory = memory or MemoryController()
        self._query_count: int = 0

    @property
    def query_count(self) -> int:
        return self._query_count

    # ── Portfolio Metrics ─────────────────────────────────────

    def get_portfolio_metrics(self) -> PortfolioMetrics:
        """获取组合级别指标."""
        self._query_count += 1

        products = self._get_all_product_ids()
        total_spend = 0.0
        total_revenue = 0.0
        growth_scores: list[float] = []

        for pid in products:
            product = self._get_product_metrics_internal(pid)
            total_spend += product.budget_allocation
            if product.current_roas > 0:
                total_revenue += product.current_roas * product.budget_allocation
            growth_scores.append(product.growth_score)

        portfolio_roas = total_revenue / total_spend if total_spend > 0 else 0.0
        portfolio_fitness = sum(growth_scores) / max(1, len(growth_scores))

        return PortfolioMetrics(
            total_spend=round(total_spend, 2),
            total_revenue=round(total_revenue, 2),
            portfolio_roas=round(portfolio_roas, 4),
            portfolio_ltv=round(total_revenue * 2.0, 2),
            portfolio_fitness=round(portfolio_fitness, 2),
            product_count=len(products),
        )

    # ── Product Metrics ───────────────────────────────────────

    def get_product_metrics(self, product_id: str) -> ProductDashboard:
        """获取产品级别指标."""
        self._query_count += 1
        return self._get_product_metrics_internal(product_id)

    def _get_product_metrics_internal(self, product_id: str) -> ProductDashboard:
        """内部获取产品指标（不增加 query_count）."""
        loop = self._loop.get_loop_by_product(product_id)

        # Get patterns for this product from memory
        patterns = self._memory.learn_patterns()
        product_patterns = [p for p in patterns if p.product_id == product_id]

        avg_roas = 0.0
        success_count = 0
        total_count = 0
        for p in product_patterns:
            if p.metrics and p.metrics.roas > 0:
                avg_roas = max(avg_roas, p.metrics.roas)
            total_count += 1
            if p.outcome and p.outcome.value == "success":
                success_count += 1

        growth_score = min(1.0, avg_roas / 2.0) if avg_roas > 0 else 0.3

        budget = 0.0
        completed_cycles = 0
        active_strategy = ""
        if loop:
            completed_cycles = loop.cycle_count
            budget = loop.config.get("budget", 0.0) if loop.config else 0.0
            active_strategy = loop.active_strategy_id

        return ProductDashboard(
            product_id=product_id,
            current_roas=avg_roas,
            trend=TrendDirection.UP if avg_roas > 1.0 else TrendDirection.DOWN if avg_roas < 0.8 else TrendDirection.STABLE,
            growth_score=round(growth_score, 2),
            budget_allocation=round(budget, 2),
            active_strategy=active_strategy,
            completed_cycles=completed_cycles,
            active_experiments=len(product_patterns),
            last_updated=datetime.now(timezone.utc).isoformat(),
        )

    def get_all_product_metrics(self) -> list[ProductDashboard]:
        """获取所有产品指标."""
        self._query_count += 1
        return [self.get_product_metrics(pid) for pid in self._get_all_product_ids()]

    # ── Loop Metrics ──────────────────────────────────────────

    def get_loop_metrics(self, product_id: str) -> dict[str, Any]:
        """获取循环指标."""
        self._query_count += 1

        loop = self._loop.get_loop_by_product(product_id)
        if loop is None:
            return {
                "product_id": product_id,
                "cycles": [],
                "total_cycles": 0,
                "successful_cycles": 0,
                "failed_cycles": 0,
                "success_rate": 0.0,
                "learning_velocity": 0,
                "strategy_accuracy": 0.0,
            }

        cycles = loop.cycles
        total = len(cycles)
        successful = sum(1 for c in cycles if c.is_successful)
        failed = sum(1 for c in cycles if c.outcome and c.outcome.value == "failure")

        success_rate = successful / total if total > 0 else 0.0
        learning_velocity = sum(
            c.learning.get("patterns_learned", 0) if c.learning else 0
            for c in cycles
        )
        strategy_count = len({c.strategy_id for c in cycles if c.strategy_id})

        return {
            "product_id": product_id,
            "total_cycles": total,
            "successful_cycles": successful,
            "failed_cycles": failed,
            "success_rate": round(success_rate, 2),
            "learning_velocity": learning_velocity,
            "strategy_accuracy": round(strategy_count / max(1, total), 2),
            "cycles": [
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
                ).to_dict()
                for c in cycles
            ],
        }

    # ── Health Score ──────────────────────────────────────────

    def compute_health_score(
        self, product_id: str | None = None,
    ) -> float:
        """计算系统健康分数."""
        self._query_count += 1

        if product_id:
            metrics = self.get_loop_metrics(product_id)
            success_rate = metrics.get("success_rate", 0.0)
            loop = self._loop.get_loop_by_product(product_id)
            roas = 0.0
            if loop:
                patterns = self._memory.learn_patterns()
                product_patterns = [p for p in patterns if p.product_id == product_id]
                for p in product_patterns:
                    if p.metrics and p.metrics.roas > 0:
                        roas = max(roas, p.metrics.roas)
            roas_score = min(1.0, roas / 2.0)
            return round(0.4 * success_rate + 0.4 * roas_score + 0.2 * 0.7, 2)

        # System-wide health
        products = self._get_all_product_ids()
        if not products:
            return 0.5
        scores = [self.compute_health_score(pid) for pid in products]
        return round(sum(scores) / len(scores), 2)

    # ── Helpers ───────────────────────────────────────────────

    def _get_all_product_ids(self) -> list[str]:
        """获取所有产品 ID."""
        loops = self._loop.get_all_loops()
        pids = list({l.product_id for l in loops})
        if not pids:
            return ["default"]
        return pids

    # ── Summary ───────────────────────────────────────────────

    def get_summary(self) -> dict[str, Any]:
        return {
            "query_count": self._query_count,
        }