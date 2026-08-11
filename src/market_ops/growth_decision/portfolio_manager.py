"""E9.9.5 Module 5: Portfolio Manager.

Manages creative asset lifecycle and 3-tier budget pool allocation.

Portfolio Model:
  Exploration (30%): PROMISING / RETEST — new opportunities
  Growth (50%):      WINNER — scaling assets
  Harvest (20%):     mature, stable ROI — cost reduction

Lifecycle State Machine:
  NEW → TESTING → GROWING → MATURE → HARVEST → RETIRED
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from market_ops.growth_decision.schemas import (
    GrowthDecision, CreativePortfolio, RiskReport, ScalePlan,
    GrowthAction, WinnerLevel, PortfolioBucket, LifecycleStage, RiskLevel,
)

# ── Pool Allocation Targets ────────────────────────────────

EXPLORATION_TARGET = 0.30   # 30% of total budget
GROWTH_TARGET = 0.50        # 50%
HARVEST_TARGET = 0.20       # 20%

# ── Pool Constraints ───────────────────────────────────────

MIN_EXPLORATION = 0.20      # Minimum 20% for exploration
MAX_GROWTH = 0.50           # Maximum 50% for growth
MAX_HARVEST = 0.30          # Maximum 30% for harvest


class PortfolioManager:
    """Manages creative asset lifecycle and budget pool allocation.

    Usage:
        manager = PortfolioManager()
        portfolios = manager.create_portfolio(decisions, total_budget=10000)
        manager.rebalance(portfolios, risk_report)
    """

    def __init__(self) -> None:
        pass

    # ═══════════════════════════════════════════════════════
    # 1. Portfolio Creation
    # ═══════════════════════════════════════════════════════

    def create_portfolio(
        self,
        decisions: list[GrowthDecision],
        total_budget: float = 10000.0,
    ) -> list[CreativePortfolio]:
        """Create portfolio entries from GrowthDecisions.

        Maps each decision to a bucket and lifecycle stage:
          WINNER      → GROWTH bucket, GROWING stage
          PROMISING   → EXPLORATION bucket, TESTING stage
          FAILED      → HARVEST bucket, RETIRED stage (learn & archive)
          INCONCLUSIVE → EXPLORATION bucket, TESTING stage

        Args:
            decisions: GrowthDecision list from WinnerDetector
            total_budget: Total budget across all creatives

        Returns:
            List of CreativePortfolio objects
        """
        portfolios = []

        for d in decisions:
            bucket = self._map_to_bucket(d)
            lifecycle = self._map_to_lifecycle(d)

            portfolio = CreativePortfolio(
                creative_id=d.creative_id,
                bucket=bucket,
                lifecycle_stage=lifecycle,
                allocated_budget=0.0,  # filled by allocate_budget
                roi=0.0,
                risk_score=0.0,
                archetype=self._extract_archetype(d),
                updated_at=datetime.now(timezone.utc).isoformat(),
            )
            portfolios.append(portfolio)

        # Allocate budgets after creation
        self.allocate_budget(portfolios, total_budget)

        return portfolios

    # ── Mapping Helpers ────────────────────────────────────

    def _map_to_bucket(self, decision: GrowthDecision) -> str:
        """Map GrowthDecision to portfolio bucket."""
        mapping = {
            GrowthAction.SCALE.value: PortfolioBucket.GROWTH.value,
            GrowthAction.WATCH.value: PortfolioBucket.EXPLORATION.value,
            GrowthAction.RETEST.value: PortfolioBucket.EXPLORATION.value,
            GrowthAction.KILL.value: PortfolioBucket.HARVEST.value,
        }
        return mapping.get(decision.decision, PortfolioBucket.EXPLORATION.value)

    def _map_to_lifecycle(self, decision: GrowthDecision) -> str:
        """Map GrowthDecision to lifecycle stage."""
        mapping = {
            GrowthAction.SCALE.value: LifecycleStage.GROWING.value,
            GrowthAction.WATCH.value: LifecycleStage.TESTING.value,
            GrowthAction.RETEST.value: LifecycleStage.TESTING.value,
            GrowthAction.KILL.value: LifecycleStage.RETIRED.value,
        }
        return mapping.get(decision.decision, LifecycleStage.NEW.value)

    def _extract_archetype(self, decision: GrowthDecision) -> str:
        """Extract archetype from decision reason if available."""
        # In production, archetype comes from E9.9 experiment data
        # For now, use a reasonable default
        return "unknown"

    # ═══════════════════════════════════════════════════════
    # 2. Budget Allocation
    # ═══════════════════════════════════════════════════════

    def allocate_budget(
        self,
        portfolios: list[CreativePortfolio],
        total_budget: float = 10000.0,
    ) -> dict[str, float]:
        """Allocate budget across 3 pools according to target ratios.

        Pool targets:
          Exploration: 30% (min 20%)
          Growth:      50% (max 50%)
          Harvest:     20% (max 30%)

        Within each pool, budget is split equally among all entries.

        Args:
            portfolios: Portfolio entries to allocate
            total_budget: Total budget across all creatives

        Returns:
            {pool_name: allocated_budget} summary
        """
        # Group by bucket
        pools: dict[str, list[CreativePortfolio]] = {
            PortfolioBucket.EXPLORATION.value: [],
            PortfolioBucket.GROWTH.value: [],
            PortfolioBucket.HARVEST.value: [],
        }

        for p in portfolios:
            bucket = p.bucket
            if bucket in pools:
                pools[bucket].append(p)

        # Calculate pool budgets
        pool_budgets = {
            PortfolioBucket.EXPLORATION.value: total_budget * EXPLORATION_TARGET,
            PortfolioBucket.GROWTH.value: total_budget * GROWTH_TARGET,
            PortfolioBucket.HARVEST.value: total_budget * HARVEST_TARGET,
        }

        # Distribute within each pool
        allocation = {}
        for pool_name, entries in pools.items():
            pool_total = pool_budgets.get(pool_name, 0.0)
            if entries:
                per_entry = pool_total / len(entries)
                for entry in entries:
                    entry.allocated_budget = round(per_entry, 2)
            allocation[pool_name] = pool_total

        return allocation

    def get_allocation_summary(
        self, portfolios: list[CreativePortfolio]
    ) -> dict[str, Any]:
        """Get current allocation state across pools."""
        pools: dict[str, dict[str, Any]] = {
            PortfolioBucket.EXPLORATION.value: {"count": 0, "budget": 0.0},
            PortfolioBucket.GROWTH.value: {"count": 0, "budget": 0.0},
            PortfolioBucket.HARVEST.value: {"count": 0, "budget": 0.0},
        }

        total = 0.0
        for p in portfolios:
            if p.bucket in pools:
                pools[p.bucket]["count"] += 1
                pools[p.bucket]["budget"] += p.allocated_budget
                total += p.allocated_budget

        # Calculate ratios
        for name, data in pools.items():
            data["ratio"] = round(data["budget"] / max(1.0, total), 3)

        return {
            "total_budget": round(total, 2),
            "total_assets": len(portfolios),
            "pools": pools,
            "targets": {
                "exploration": EXPLORATION_TARGET,
                "growth": GROWTH_TARGET,
                "harvest": HARVEST_TARGET,
            },
        }

    # ═══════════════════════════════════════════════════════
    # 3. Lifecycle Management
    # ═══════════════════════════════════════════════════════

    def update_lifecycle(
        self,
        portfolio: CreativePortfolio,
        performance: dict[str, Any] | None = None,
    ) -> CreativePortfolio:
        """Update lifecycle stage based on performance and time.

        State transitions:
          NEW      → TESTING  (entered experiment)
          TESTING  → GROWING  (WINNER, ROAS stable)
          GROWING  → MATURE   (3+ cycles, stable ROAS)
          MATURE   → HARVEST  (ROAS declining)
          HARVEST  → RETIRED  (ROAS below threshold)

        Args:
            portfolio: Portfolio entry to update
            performance: Optional performance dict {roas, cycles, retention}

        Returns:
            Updated CreativePortfolio
        """
        current = portfolio.lifecycle_stage
        perf = performance or {}

        transitions = {
            LifecycleStage.NEW.value: self._new_to_testing,
            LifecycleStage.TESTING.value: self._testing_to_growing,
            LifecycleStage.GROWING.value: self._growing_to_mature,
            LifecycleStage.MATURE.value: self._mature_to_harvest,
            LifecycleStage.HARVEST.value: self._harvest_to_retired,
            LifecycleStage.RETIRED.value: lambda p, pf: LifecycleStage.RETIRED.value,
        }

        handler = transitions.get(current, lambda p, pf: current)
        new_stage = handler(portfolio, perf)

        if new_stage != current:
            portfolio.lifecycle_stage = new_stage
            # Update bucket on major transitions
            if new_stage == LifecycleStage.GROWING.value:
                portfolio.bucket = PortfolioBucket.GROWTH.value
            elif new_stage == LifecycleStage.HARVEST.value:
                portfolio.bucket = PortfolioBucket.HARVEST.value
            elif new_stage == LifecycleStage.RETIRED.value:
                portfolio.bucket = PortfolioBucket.HARVEST.value
                portfolio.allocated_budget = 0.0

        portfolio.updated_at = datetime.now(timezone.utc).isoformat()
        if perf.get("roas"):
            portfolio.roi = perf["roas"]

        return portfolio

    def _new_to_testing(
        self, _portfolio: CreativePortfolio, _perf: dict[str, Any]
    ) -> str:
        """NEW → TESTING: always transition when experiment starts."""
        return LifecycleStage.TESTING.value

    def _testing_to_growing(
        self, portfolio: CreativePortfolio, perf: dict[str, Any]
    ) -> str:
        """TESTING → GROWING: WINNER with stable ROAS."""
        roas = perf.get("roas", 0.0)
        if portfolio.bucket == PortfolioBucket.GROWTH.value and roas > 1.0:
            return LifecycleStage.GROWING.value
        return LifecycleStage.TESTING.value

    def _growing_to_mature(
        self, _portfolio: CreativePortfolio, perf: dict[str, Any]
    ) -> str:
        """GROWING → MATURE: 3+ cycles with stable ROAS > 1.0."""
        cycles = perf.get("cycles", 0)
        roas = perf.get("roas", 0.0)
        if cycles >= 3 and roas > 1.0:
            return LifecycleStage.MATURE.value
        return LifecycleStage.GROWING.value

    def _mature_to_harvest(
        self, _portfolio: CreativePortfolio, perf: dict[str, Any]
    ) -> str:
        """MATURE → HARVEST: ROAS declining below threshold."""
        roas = perf.get("roas", 0.0)
        if roas < 0.8:
            return LifecycleStage.HARVEST.value
        return LifecycleStage.MATURE.value

    def _harvest_to_retired(
        self, _portfolio: CreativePortfolio, perf: dict[str, Any]
    ) -> str:
        """HARVEST → RETIRED: ROAS consistently below threshold."""
        roas = perf.get("roas", 0.0)
        cycles_low = perf.get("cycles_low", 0)
        if roas < 0.5 and cycles_low >= 2:
            return LifecycleStage.RETIRED.value
        return LifecycleStage.HARVEST.value

    def update_all_lifecycles(
        self,
        portfolios: list[CreativePortfolio],
        performance_map: dict[str, dict[str, Any]] | None = None,
    ) -> list[CreativePortfolio]:
        """Update lifecycle for all portfolios.

        Args:
            portfolios: All portfolio entries
            performance_map: {creative_id: {roas, cycles, ...}}

        Returns:
            Updated portfolio list
        """
        perf_map = performance_map or {}
        for p in portfolios:
            perf = perf_map.get(p.creative_id, {})
            self.update_lifecycle(p, perf)
        return portfolios

    # ═══════════════════════════════════════════════════════
    # 4. Rebalance (HHI-based)
    # ═══════════════════════════════════════════════════════

    def rebalance(
        self,
        portfolios: list[CreativePortfolio],
        risk_report: RiskReport,
        total_budget: float = 10000.0,
    ) -> list[CreativePortfolio]:
        """Rebalance portfolio based on risk report.

        If HHI > 0.5 (archetype concentration):
          - Reduce budget for dominant archetype
          - Increase Exploration pool budget
          - Move some Growth assets to Exploration

        Args:
            portfolios: Current portfolio allocations
            risk_report: RiskReport from RiskController
            total_budget: Total budget to reallocate

        Returns:
            Rebalanced portfolio list
        """
        if risk_report.diversity_risk == RiskLevel.SAFE.value:
            return portfolios

        # Find dominant archetype (highest budget concentration)
        arch_budget: dict[str, float] = {}
        for p in portfolios:
            arch = p.archetype or "unknown"
            arch_budget[arch] = arch_budget.get(arch, 0.0) + p.allocated_budget

        if not arch_budget:
            return portfolios

        dominant_arch = max(arch_budget, key=arch_budget.get)
        dominant_ratio = arch_budget[dominant_arch] / max(1.0, total_budget)

        # Reduce dominant archetype budget by 20%
        reduction_ratio = 0.80
        freed_budget = 0.0

        for p in portfolios:
            if p.archetype == dominant_arch:
                old_budget = p.allocated_budget
                p.allocated_budget = round(old_budget * reduction_ratio, 2)
                freed_budget += old_budget - p.allocated_budget

        # Move freed budget to Exploration pool
        exploration_entries = [
            p for p in portfolios
            if p.bucket == PortfolioBucket.EXPLORATION.value
        ]

        if exploration_entries and freed_budget > 0:
            per_entry = freed_budget / len(exploration_entries)
            for p in exploration_entries:
                p.allocated_budget = round(p.allocated_budget + per_entry, 2)

        return portfolios

    # ═══════════════════════════════════════════════════════
    # Summary
    # ═══════════════════════════════════════════════════════

    def get_portfolio_summary(
        self, portfolios: list[CreativePortfolio]
    ) -> dict[str, Any]:
        """Get comprehensive portfolio summary."""
        by_bucket: dict[str, int] = {}
        by_lifecycle: dict[str, int] = {}
        by_archetype: dict[str, dict[str, Any]] = {}
        total_budget = 0.0

        for p in portfolios:
            by_bucket[p.bucket] = by_bucket.get(p.bucket, 0) + 1
            by_lifecycle[p.lifecycle_stage] = by_lifecycle.get(p.lifecycle_stage, 0) + 1
            total_budget += p.allocated_budget

            arch = p.archetype or "unknown"
            if arch not in by_archetype:
                by_archetype[arch] = {"count": 0, "budget": 0.0}
            by_archetype[arch]["count"] += 1
            by_archetype[arch]["budget"] += p.allocated_budget

        # Calculate archetype budget ratios
        for arch_data in by_archetype.values():
            arch_data["ratio"] = round(
                arch_data["budget"] / max(1.0, total_budget), 3
            )

        return {
            "total_assets": len(portfolios),
            "total_budget": round(total_budget, 2),
            "by_bucket": by_bucket,
            "by_lifecycle": by_lifecycle,
            "by_archetype": by_archetype,
            "pool_targets": {
                "exploration": EXPLORATION_TARGET,
                "growth": GROWTH_TARGET,
                "harvest": HARVEST_TARGET,
            },
        }