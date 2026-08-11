"""
E15.2.4 — Optimization Planner

Converts detected signals into an ordered OptimizationPlan.
"""
from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional

from operation.optimizer.analyzers.ecpm_analyzer import EcpmAnalyzer
from operation.optimizer.analyzers.fill_analyzer import (
    FillAnalyzer, RetentionImpactAnalyzer, WaterfallAnalyzer,
)
from operation.optimizer.analyzers.revenue_analyzer import RevenueAnalyzer
from operation.optimizer.models import (
    OptimizationAction, OptimizationPlan, OptimizationSignal,
)
from operation.optimizer.strategies.strategies import (
    BidFloorStrategy, FrequencyStrategy, NetworkStrategy, WaterfallStrategy,
)


class OptimizationPlanner:
    """Analyzes metrics → generates signals → produces OptimizationPlan."""

    def __init__(self):
        self.revenue_analyzer = RevenueAnalyzer()
        self.ecpm_analyzer = EcpmAnalyzer()
        self.fill_analyzer = FillAnalyzer()
        self.waterfall_analyzer = WaterfallAnalyzer()
        self.retention_analyzer = RetentionImpactAnalyzer()
        self.bid_floor_strategy = BidFloorStrategy()
        self.waterfall_strategy = WaterfallStrategy()
        self.frequency_strategy = FrequencyStrategy()
        self.network_strategy = NetworkStrategy()

    def plan(
        self,
        game_id: str,
        metrics: List[Dict[str, Any]],
        baselines: Optional[Dict[str, Any]] = None,
        network_data: Optional[List[Dict[str, Any]]] = None,
        current_order: Optional[Dict[str, List[str]]] = None,
        current_floors: Optional[Dict[str, float]] = None,
        current_frequencies: Optional[Dict[str, float]] = None,
        retention_data: Optional[Dict[str, Any]] = None,
    ) -> OptimizationPlan:
        """Full planning cycle: analyze → strategy → plan."""

        plan_id = f"plan_{uuid.uuid4().hex[:8]}"
        plan = OptimizationPlan(plan_id=plan_id, game_id=game_id,
                                created_at=time.time())

        # Phase 1: Analyze — collect all signals
        all_signals: List[OptimizationSignal] = []
        all_signals.extend(self.revenue_analyzer.analyze(game_id, metrics, baselines))
        all_signals.extend(self.ecpm_analyzer.analyze(game_id, metrics, baselines))
        all_signals.extend(self.fill_analyzer.analyze(game_id, metrics, baselines))

        # Waterfall analysis per format/country
        if network_data and current_order:
            for wf_key, order in current_order.items():
                parts = wf_key.split("_", 1)
                fmt = parts[0]
                country = parts[1] if len(parts) > 1 else "US"
                relevant = [nd for nd in network_data
                           if nd.get("format") == fmt and nd.get("country") == country]
                if relevant:
                    all_signals.extend(
                        self.waterfall_analyzer.analyze(game_id, fmt, country, relevant, order))

        # Phase 2: Strategy — convert signals to actions
        all_actions: List[OptimizationAction] = []
        all_actions.extend(
            self.bid_floor_strategy.generate(all_signals, current_floors))
        all_actions.extend(
            self.waterfall_strategy.generate(all_signals, current_order))
        all_actions.extend(
            self.frequency_strategy.generate(all_signals, current_frequencies))
        all_actions.extend(
            self.network_strategy.generate(all_signals))

        # Deduplicate actions
        seen = set()
        unique_actions = []
        for a in all_actions:
            dedup_key = f"{a.action_type}|{a.game_id}|{a.country}|{a.ad_format}"
            if dedup_key not in seen:
                seen.add(dedup_key)
                unique_actions.append(a)

        plan.actions = plan.sorted_by_priority.__func__(plan)
        # Rebuild with sorted
        temp = OptimizationPlan(plan_id=plan_id, game_id=game_id,
                                created_at=plan.created_at)
        # Actually just sort in place
        plan.actions = sorted(unique_actions, key=lambda a: (a.priority, a.action_type))

        plan.metadata = {
            "signals_detected": len(all_signals),
            "actions_generated": len(all_actions),
            "actions_deduped": len(unique_actions),
            "critical_signals": sum(1 for s in all_signals if s.is_critical),
        }

        return plan


__all__ = ["OptimizationPlanner"]
