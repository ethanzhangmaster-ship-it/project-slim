from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime


@dataclass
class PriorityResult:
    item_id: str
    priority: int
    score: float
    reason: str
    factors: Dict[str, float] = field(default_factory=dict)


class PriorityEngine:
    def __init__(self):
        self.factor_weights = {
            "impact": 0.35,
            "confidence": 0.25,
            "urgency": 0.2,
            "resource_availability": 0.1,
            "alignment": 0.1,
        }

    def calculate(self, items: List[Dict[str, Any]]) -> List[PriorityResult]:
        results = []
        
        for item in items:
            score, factors = self._calculate_score(item)
            priority = self._score_to_priority(score)
            
            results.append(PriorityResult(
                item_id=item.get("id", ""),
                priority=priority,
                score=round(score, 2),
                reason=self._generate_reason(item, factors),
                factors=factors,
            ))
        
        results.sort(key=lambda x: x.priority, reverse=True)
        return results

    def _calculate_score(self, item: Dict[str, Any]) -> tuple:
        factors = {}
        
        factors["impact"] = item.get("impact", 0.5)
        factors["confidence"] = item.get("confidence", 0.5)
        factors["urgency"] = item.get("urgency", 0.5)
        factors["resource_availability"] = item.get("resource_availability", 0.5)
        factors["alignment"] = item.get("alignment", 0.5)
        
        score = sum(
            factors[factor] * weight
            for factor, weight in self.factor_weights.items()
        )
        
        return score, factors

    def _score_to_priority(self, score: float) -> int:
        if score >= 0.8:
            return 5
        elif score >= 0.65:
            return 4
        elif score >= 0.5:
            return 3
        elif score >= 0.35:
            return 2
        else:
            return 1

    def _generate_reason(self, item: Dict[str, Any], factors: Dict[str, float]) -> str:
        reasons = []
        
        if factors["impact"] >= 0.8:
            reasons.append("high impact")
        elif factors["impact"] <= 0.3:
            reasons.append("low impact")
        
        if factors["confidence"] >= 0.8:
            reasons.append("high confidence")
        
        if factors["urgency"] >= 0.8:
            reasons.append("urgent")
        
        if factors["alignment"] >= 0.8:
            reasons.append("aligned with goals")
        
        if not reasons:
            reasons.append("balanced factors")
        
        return ", ".join(reasons)

    def calculate_demo(self) -> List[PriorityResult]:
        items = [
            {"id": "scale_A", "impact": 0.9, "confidence": 0.88, "urgency": 0.7, "resource_availability": 0.9, "alignment": 0.95},
            {"id": "kill_B", "impact": 0.6, "confidence": 0.95, "urgency": 0.9, "resource_availability": 0.95, "alignment": 0.8},
            {"id": "test_C", "impact": 0.7, "confidence": 0.7, "urgency": 0.4, "resource_availability": 0.8, "alignment": 0.7},
        ]
        return self.calculate(items)
