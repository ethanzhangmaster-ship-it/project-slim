"""
E15.2.4 — Optimization Executor

Executes an OptimizationPlan through:
Safety Agent → Monetization Ops Provider → Memory Record
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from operation.optimizer.models import (
    OptimizationAction, OptimizationPlan, OptimizationResult,
)


class OptimizationExecutor:
    """Safety-gated execution of optimization plans."""

    # Enhanced safety rules
    MAX_BID_FLOOR_CHANGE_PCT = 20.0     # block if floor change > 20%
    MAX_WATERFALL_NETWORKS_REMOVED = 0.5  # block removing > 50% networks
    MAX_FREQUENCY_CHANGE_PCT = 20.0     # block daily frequency change > 20%

    def __init__(
        self,
        safety_agent=None,       # operation.safety.SafetyAgent
        memory_agent=None,       # operation.memory.MemoryAgent
        ads_provider=None,       # operation.providers.contracts.AdsProvider
        config_provider=None,    # operation.providers.contracts.ConfigProvider
        dry_run: bool = True,
    ):
        self.safety = safety_agent
        self.memory = memory_agent
        self.ads_provider = ads_provider
        self.config_provider = config_provider
        self.dry_run = dry_run

    def execute(self, plan: OptimizationPlan) -> OptimizationResult:
        """Execute all actions in a plan, gated by safety checks."""

        result = OptimizationResult(
            plan_id=plan.plan_id, game_id=plan.game_id,
            actions_total=plan.total_actions,
        )

        for action in plan.sorted_by_priority():
            # Step 1: Enhanced safety pre-check
            safety_check = self._safety_pre_check(action)
            if safety_check:
                result.actions_blocked += 1
                result.results.append({
                    "action_id": action.action_id,
                    "action_type": action.action_type,
                    "status": "blocked",
                    "reason": safety_check,
                })
                continue

            # Step 2: Execute via provider
            if self.dry_run:
                exec_result = {"success": True, "detail": "dry_run — not executed"}
            else:
                exec_result = self._execute_action(action)

            # Step 3: Record to memory
            if self.memory:
                self.memory.record(
                    game_id=action.game_id,
                    operation=action.action_type,
                    provider=action.provider,
                    sandbox="SIMULATION" if self.dry_run else "PRODUCTION",
                    context={"country": action.country, "ad_format": action.ad_format},
                    before_state=action.changes.get("old_floor", {}) or {},
                    after_state=action.changes,
                    result_success=exec_result.get("success", False),
                    result_metrics=action.expected_impact,
                    error=exec_result.get("error", ""),
                    confidence=0.7,
                    tags=["optimization_v2", action.action_type],
                )

            if exec_result.get("success"):
                result.actions_executed += 1
                result.results.append({
                    "action_id": action.action_id,
                    "action_type": action.action_type,
                    "status": "executed",
                    "provider_result": exec_result,
                })
            else:
                result.actions_failed += 1
                result.results.append({
                    "action_id": action.action_id,
                    "action_type": action.action_type,
                    "status": "failed",
                    "reason": exec_result.get("error", "unknown"),
                })

        return result

    def _safety_pre_check(self, action: OptimizationAction) -> Optional[str]:
        """Enhanced safety checks beyond the SafetyAgent."""
        changes = action.changes

        # Bid floor limit
        if action.action_type in ("raise_bid_floor", "lower_bid_floor"):
            pct = abs(changes.get("change_pct", 0))
            if pct > self.MAX_BID_FLOOR_CHANGE_PCT:
                return f"Bid floor change {pct:.0f}% exceeds max {self.MAX_BID_FLOOR_CHANGE_PCT}%"

        # Waterfall protection: don't remove > 50% networks
        if action.action_type == "remove_network":
            old_order = changes.get("old_order", [])
            new_order = changes.get("new_order", [])
            if old_order and new_order:
                removed = len(old_order) - len(new_order)
                if removed > len(old_order) * self.MAX_WATERFALL_NETWORKS_REMOVED:
                    return f"Removing {removed} networks exceeds {self.MAX_WATERFALL_NETWORKS_REMOVED*100:.0f}% limit"

        # Frequency daily change limit
        if action.action_type == "adjust_frequency":
            pct = abs(changes.get("change_pct", 0))
            if pct > self.MAX_FREQUENCY_CHANGE_PCT:
                return f"Frequency change {pct:.0f}% exceeds daily {self.MAX_FREQUENCY_CHANGE_PCT}% limit"

        # Delegate to SafetyAgent for standard checks
        if self.safety:
            safety_result = self.safety.check(
                game_id=action.game_id,
                operation=action.action_type,
                provider=action.provider,
                changes=changes,
                expected_impact=action.expected_impact,
                has_rollback=True,
            )
            if safety_result.is_blocked:
                return safety_result.reason

        return None

    def _execute_action(self, action: OptimizationAction) -> Dict[str, Any]:
        """Route action to the correct provider method."""
        if not self.ads_provider:
            return {"success": False, "error": "no ads_provider configured"}

        if action.action_type in ("raise_bid_floor", "lower_bid_floor"):
            new_floor = action.changes.get("new_floor")
            if new_floor is not None:
                return self.ads_provider.update_bid_floor(
                    ad_unit_id=f"{action.ad_format}_{action.country}",
                    floor=new_floor, ad_type=action.ad_format,
                )

        elif action.action_type == "reorder_waterfall":
            from operation.providers.contracts.ads import WaterfallConfig
            new_order = action.changes.get("new_order", [])
            return self.ads_provider.update_waterfall(WaterfallConfig(
                ad_unit_id=f"{action.ad_format}_{action.country}",
                networks=[{"network": n, "priority": i} for i, n in enumerate(new_order)],
                country=action.country,
            ))

        elif action.action_type == "adjust_frequency":
            new_interval = action.changes.get("new_interval_s")
            if new_interval is not None and self.config_provider:
                return self.config_provider.update(
                    f"ad_frequency_{action.ad_format}", new_interval)

        return {"success": False, "error": f"unsupported action: {action.action_type}"}


class OptimizationScheduler:
    """Schedules periodic optimization cycles."""

    def __init__(self, planner: OptimizationPlanner,
                 executor: Optional[OptimizationExecutor] = None):
        self.planner = planner
        self.executor = executor
        self._cycles: List[Dict[str, Any]] = []

    def run_cycle(
        self,
        game_id: str,
        metrics: List[Dict[str, Any]],
        baselines: Optional[Dict[str, Any]] = None,
        network_data: Optional[List[Dict[str, Any]]] = None,
        current_order: Optional[Dict[str, List[str]]] = None,
        current_floors: Optional[Dict[str, float]] = None,
        current_frequencies: Optional[Dict[str, float]] = None,
        dry_run: bool = True,
    ) -> Dict[str, Any]:
        """One full optimization cycle: plan → execute → record."""

        cycle_start = time.time()

        plan = self.planner.plan(
            game_id=game_id, metrics=metrics, baselines=baselines,
            network_data=network_data, current_order=current_order,
            current_floors=current_floors, current_frequencies=current_frequencies,
        )

        result = None
        if self.executor:
            self.executor.dry_run = dry_run
            result = self.executor.execute(plan)

        cycle = {
            "game_id": game_id,
            "timestamp": cycle_start,
            "plan_id": plan.plan_id,
            "signals_detected": plan.metadata.get("signals_detected", 0),
            "actions_planned": plan.total_actions,
            "actions_executed": result.actions_executed if result else 0,
            "actions_blocked": result.actions_blocked if result else 0,
            "dry_run": dry_run,
            "elapsed_ms": round((time.time() - cycle_start) * 1000, 1),
        }
        self._cycles.append(cycle)
        return cycle

    def run_multi_game(
        self,
        game_data: Dict[str, Dict[str, Any]],
        dry_run: bool = True,
    ) -> List[Dict[str, Any]]:
        """Run optimization across multiple games."""
        results = []
        for game_id, data in game_data.items():
            cycle = self.run_cycle(
                game_id=game_id,
                metrics=data.get("metrics", []),
                baselines=data.get("baselines"),
                network_data=data.get("network_data"),
                current_order=data.get("current_order"),
                current_floors=data.get("current_floors"),
                current_frequencies=data.get("current_frequencies"),
                dry_run=dry_run,
            )
            results.append(cycle)
        return results


__all__ = ["OptimizationExecutor", "OptimizationScheduler"]
