from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime


@dataclass
class EvolutionResult:
    strategy_id: str
    old_strategy: Dict[str, Any]
    new_strategy: Dict[str, Any]
    improvements: List[str] = field(default_factory=list)
    confidence: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)


class StrategyEvolution:
    def __init__(self):
        self.evolution_history: List[EvolutionResult] = []

    def evolve(self, current_strategy: Dict[str, Any], results: List[Dict[str, Any]]) -> EvolutionResult:
        new_strategy = current_strategy.copy()
        improvements = []

        scale_results = [r for r in results if r.get("action") == "scale"]
        if scale_results:
            success_rate = sum(1 for r in scale_results if r.get("success")) / len(scale_results)
            
            if success_rate > 0.8:
                new_strategy["scale_aggressiveness"] = min(new_strategy.get("scale_aggressiveness", 1.0) * 1.1, 2.0)
                improvements.append(f"Increase scale aggressiveness: {new_strategy['scale_aggressiveness']:.2f}")
            
            elif success_rate < 0.5:
                new_strategy["scale_aggressiveness"] = max(new_strategy.get("scale_aggressiveness", 1.0) * 0.9, 0.5)
                improvements.append(f"Decrease scale aggressiveness: {new_strategy['scale_aggressiveness']:.2f}")

        test_results = [r for r in results if r.get("action") == "test"]
        if test_results:
            avg_impact = sum(r.get("impact", 0) for r in test_results) / len(test_results)
            
            if avg_impact > 0.2:
                new_strategy["test_frequency"] = min(new_strategy.get("test_frequency", 1.0) * 1.2, 2.0)
                improvements.append(f"Increase test frequency: {new_strategy['test_frequency']:.2f}")

        result = EvolutionResult(
            strategy_id=f"evo_{hash(str(current_strategy)) % 10000:04d}",
            old_strategy=current_strategy,
            new_strategy=new_strategy,
            improvements=improvements,
            confidence=0.7 + len(improvements) * 0.1,
        )
        
        self.evolution_history.append(result)
        return result

    def get_evolution_history(self) -> List[EvolutionResult]:
        return self.evolution_history

    def evolve_demo(self) -> EvolutionResult:
        current_strategy = {
            "mode": "scale",
            "scale_aggressiveness": 1.0,
            "test_frequency": 1.0,
        }
        results = [
            {"action": "scale", "success": True, "impact": 0.3},
            {"action": "scale", "success": True, "impact": 0.25},
            {"action": "scale", "success": False, "impact": -0.1},
            {"action": "test", "success": True, "impact": 0.28},
            {"action": "test", "success": True, "impact": 0.32},
        ]
        return self.evolve(current_strategy, results)
