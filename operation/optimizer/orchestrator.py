"""
E15.2.4 — Optimization Orchestrator

End-to-end monetization optimization loop:
analyze → detect issues → propose changes → safety check → execute

Integrates RevenueAnalyzer, WaterfallOptimizer, BidFloorOptimizer,
FrequencyOptimizer, SafetyAgent, and monetization_ops providers.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from operation.optimizer.analyzer import RevenueAnalyzer, RevenueIssue
from operation.optimizer.bid_floor import BidFloorOptimizer, FloorChange
from operation.optimizer.frequency import FrequencyOptimizer, FrequencyChange
from operation.optimizer.waterfall import WaterfallOptimizer, WaterfallChange


@dataclass
class OptimizationRun:
    """Result of one optimization cycle."""
    game_id: str
    issues_detected: List[RevenueIssue] = field(default_factory=list)
    waterfall_changes: List[WaterfallChange] = field(default_factory=list)
    floor_changes: List[FloorChange] = field(default_factory=list)
    frequency_changes: List[FrequencyChange] = field(default_factory=list)
    safety_results: List[Dict[str, Any]] = field(default_factory=list)
    executed_ops: List[str] = field(default_factory=list)

    @property
    def total_changes(self) -> int:
        return (len(self.waterfall_changes) + len(self.floor_changes) +
                len(self.frequency_changes))

    @property
    def summary(self) -> Dict[str, Any]:
        return {
            "game_id": self.game_id,
            "issues_count": len(self.issues_detected),
            "critical_issues": sum(1 for i in self.issues_detected if i.severity == "critical"),
            "waterfall_changes": len(self.waterfall_changes),
            "floor_changes": len(self.floor_changes),
            "frequency_changes": len(self.frequency_changes),
            "executed_ops": len(self.executed_ops),
            "safety_blocks": sum(
                1 for s in self.safety_results if s.get("status") == "blocked"),
        }


class OptimizationOrchestrator:
    """Runs the full monetization optimization cycle."""

    def __init__(
        self,
        safety_agent=None,       # operation.safety.SafetyAgent
        max_provider=None,       # operation.monetization_ops.max_ops.provider
        config_agent=None,       # operation.monetization_ops.config.agent
    ):
        self.analyzer = RevenueAnalyzer()
        self.waterfall_opt = WaterfallOptimizer()
        self.floor_opt = BidFloorOptimizer()
        self.freq_opt = FrequencyOptimizer()
        self.safety = safety_agent
        self.max_provider = max_provider
        self.config_agent = config_agent

    def run(
        self,
        game_id: str,
        metrics: List[Dict[str, Any]],
        baselines: Optional[Dict[str, Any]] = None,
        current_waterfalls: Optional[Dict[str, List[str]]] = None,
        current_floors: Optional[Dict[str, float]] = None,
        current_frequencies: Optional[Dict[str, float]] = None,
        dry_run: bool = True,
    ) -> OptimizationRun:
        """Execute one full optimization cycle."""

        run = OptimizationRun(game_id=game_id)

        # Step 1: Analyze metrics → detect issues
        run.issues_detected = self.analyzer.analyze(game_id, metrics, baselines)

        # Step 2: Waterfall optimization
        if current_waterfalls:
            for wf_key, networks in current_waterfalls.items():
                # Parse: "rewarded_US" → key parts
                parts = wf_key.split("_", 1)
                fmt = parts[0]
                country = parts[1] if len(parts) > 1 else "US"

                # Get network data from metrics
                net_data = [m for m in metrics
                           if m.get("format") == fmt and m.get("country") == country]
                net_perf = []
                for nd in net_data:
                    for net in nd.get("networks", []):
                        net_perf.append(net)

                if net_perf:
                    wf_change = self.waterfall_opt.optimize(
                        game_id, fmt, country, networks, net_perf)
                    if wf_change:
                        run.waterfall_changes.append(wf_change)

        # Step 3: Floor optimization
        if current_floors:
            for floor_key, floor_val in current_floors.items():
                parts = floor_key.split("_", 1)
                fmt = parts[0]
                country = parts[1] if len(parts) > 1 else "US"

                # Get eCPM and fill from metrics
                metric = next((m for m in metrics
                              if m.get("format") == fmt and m.get("country") == country), {})
                ecpm = metric.get("ecpm", 0)
                fill = metric.get("fill_rate", 1.0)

                fc = self.floor_opt.analyze(
                    game_id, fmt, country, floor_val, ecpm, fill)
                if fc:
                    run.floor_changes.append(fc)

        # Step 4: Frequency optimization
        if current_frequencies:
            for freq_key, interval in current_frequencies.items():
                fmt = freq_key  # assume key is format name
                fc = self.freq_opt.suggest_optimization(game_id, fmt, interval)
                if fc:
                    run.frequency_changes.append(fc)

        # Step 5: Safety check all proposed changes
        if self.safety and not dry_run:
            for wc in run.waterfall_changes:
                result = self.safety.check(
                    game_id=wc.game_id,
                    operation="add_waterfall_network",
                    provider="max",
                    changes={"networks": wc.new_order, "format": wc.format, "country": wc.country},
                    expected_impact=wc.expected_impact,
                    has_rollback=True,
                )
                run.safety_results.append(result.to_dict())
                if result.is_allowed:
                    run.executed_ops.append(f"waterfall:{wc.format}:{wc.country}")

            for fc in run.floor_changes:
                result = self.safety.check(
                    game_id=fc.game_id,
                    operation="raise_bid_floor" if fc.new_floor > fc.old_floor else "lower_bid_floor",
                    provider="max",
                    changes={"format": fc.format, "country": fc.country, "new_floor": fc.new_floor},
                    expected_impact=fc.expected_impact,
                    has_rollback=True,
                )
                run.safety_results.append(result.to_dict())
                if result.is_allowed:
                    run.executed_ops.append(f"floor:{fc.format}:{fc.country}")

            for frc in run.frequency_changes:
                if frc.recommendation == "block":
                    run.safety_results.append({
                        "status": "blocked",
                        "reason": frc.reason,
                    })
                elif frc.recommendation == "review":
                    run.safety_results.append({
                        "status": "require_confirmation",
                        "reason": frc.reason,
                    })
                else:
                    run.safety_results.append({
                        "status": "allowed",
                        "reason": frc.reason,
                    })
                    run.executed_ops.append(f"frequency:{frc.format}")

        return run


__all__ = ["OptimizationOrchestrator", "OptimizationRun"]
