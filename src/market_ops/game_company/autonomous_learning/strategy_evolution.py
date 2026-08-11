from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime


@dataclass
class EvolutionResult:
    evolution_id: str
    strategy_id: str
    evolved_strategy: Dict[str, Any] = field(default_factory=dict)
    changes: List[str] = field(default_factory=list)
    improvement_confidence: float = 0.0


class StrategyEvolution:
    def __init__(self):
        self.evolutions: Dict[str, EvolutionResult] = {}

    def evolve(self, strategy: Dict[str, Any], performance_data: Dict[str, Any]) -> EvolutionResult:
        evolved_strategy = strategy.copy()
        changes = self._identify_changes(strategy, performance_data)
        
        for change in changes:
            if change == "Increase UA budget":
                if "budget_allocation" not in evolved_strategy:
                    evolved_strategy["budget_allocation"] = {"dev": 0.4, "ua": 0.4}
                evolved_strategy["budget_allocation"]["ua"] = min(0.5, evolved_strategy["budget_allocation"].get("ua", 0.4) + 0.1)
            if change == "Reduce development time":
                if "timeline" not in evolved_strategy:
                    evolved_strategy["timeline"] = {"prototype": 4}
                evolved_strategy["timeline"]["prototype"] = max(2, evolved_strategy["timeline"].get("prototype", 4) - 1)
            if change == "Focus on retention features":
                evolved_strategy["focus"] = "retention"
            if change == "Expand target regions":
                evolved_strategy["regions"] = strategy.get("regions", ["US"]) + ["UK", "CA"]

        result = EvolutionResult(
            evolution_id=f"evo_{hash(str(strategy)) % 10000:04d}",
            strategy_id=strategy.get("strategy_id", "unknown"),
            evolved_strategy=evolved_strategy,
            changes=changes,
            improvement_confidence=self._calculate_confidence(len(changes)),
        )

        self.evolutions[result.evolution_id] = result
        return result

    def _identify_changes(self, strategy: Dict[str, Any], data: Dict[str, Any]) -> List[str]:
        changes = []
        
        roas = data.get("roas", 1.0)
        if roas > 2.0:
            changes.append("Increase UA budget")
        
        d30 = data.get("d30", 0.1)
        if d30 < 0.05:
            changes.append("Focus on retention features")
        
        timeline = strategy.get("timeline", {})
        if timeline.get("prototype", 4) > 4:
            changes.append("Reduce development time")
        
        regions = strategy.get("regions", [])
        if len(regions) < 3:
            changes.append("Expand target regions")
        
        return changes[:3]

    def _calculate_confidence(self, change_count: int) -> float:
        base = 0.6
        if change_count >= 2:
            base += 0.2
        return min(base, 0.9)

    def evolve_demo(self) -> EvolutionResult:
        strategy = {
            "strategy_id": "strat_001",
            "budget_allocation": {"dev": 0.4, "ua": 0.4, "aso": 0.1, "experiment": 0.1},
            "timeline": {"prototype": 4, "soft_launch": 8, "scale": 12},
            "regions": ["US"],
            "focus": "growth",
        }
        performance_data = {"roas": 2.5, "d30": 0.08, "cpi": 2.2}
        return self.evolve(strategy, performance_data)
