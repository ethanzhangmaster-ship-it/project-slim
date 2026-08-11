from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime


@dataclass
class EvolutionResult:
    evolution_id: str
    original_creative_id: str
    evolved_creative_id: str
    improvements: List[str] = field(default_factory=list)
    confidence: float = 0.0


class CreativeEvolution:
    def __init__(self):
        self.evolutions: Dict[str, EvolutionResult] = {}

    def evolve(self, creative, performance_data: Dict[str, Any]) -> EvolutionResult:
        improvements = self._identify_improvements(creative, performance_data)
        evolved_id = f"evo_{hash(str(creative)) % 10000:04d}"

        result = EvolutionResult(
            evolution_id=f"evo_{hash(str(performance_data)) % 10000:04d}",
            original_creative_id=getattr(creative, "video_id", "unknown"),
            evolved_creative_id=evolved_id,
            improvements=improvements,
            confidence=self._calculate_confidence(len(improvements)),
        )

        self.evolutions[result.evolution_id] = result
        return result

    def _identify_improvements(self, creative, data: Dict[str, Any]) -> List[str]:
        improvements = []
        
        ctr = data.get("ctr", 0.02)
        if ctr < 0.03:
            improvements.append("Improve hook")
            improvements.append("Add visual impact")
        
        cvr = data.get("cvr", 0.02)
        if cvr < 0.03:
            improvements.append("Show gameplay value")
            improvements.append("Clearer CTA")
        
        if len(improvements) == 0:
            improvements.append("Minor visual tweaks")
        
        return improvements

    def _calculate_confidence(self, improvement_count: int) -> float:
        base = 0.7
        if improvement_count > 2:
            base += 0.15
        elif improvement_count > 1:
            base += 0.1
        return min(base, 0.95)

    def evolve_demo(self) -> EvolutionResult:
        creative = {"video_id": "test_video"}
        performance = {"ctr": 0.025, "cvr": 0.022}
        return self.evolve(creative, performance)
