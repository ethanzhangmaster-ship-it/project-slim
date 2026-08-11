from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime


@dataclass
class PolicyUpdate:
    policy_id: str
    old_value: Any
    new_value: Any
    reason: str
    confidence: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)


class PolicyOptimizer:
    def __init__(self):
        self.policies = {
            "min_roas_for_scale": 1.5,
            "max_cpi_for_budget": 5.0,
            "confidence_threshold": 0.8,
            "max_daily_spend": 10000,
            "pause_after_days": 7,
        }

    def optimize(self, performance_data: List[Dict[str, Any]]) -> List[PolicyUpdate]:
        updates = []

        if not performance_data:
            return updates

        roas_values = [d.get("roas", 0) for d in performance_data]
        avg_roas = sum(roas_values) / len(roas_values) if roas_values else 0

        if avg_roas > 2.0:
            updates.append(PolicyUpdate(
                policy_id="min_roas_for_scale",
                old_value=self.policies["min_roas_for_scale"],
                new_value=1.8,
                reason=f"Average ROAS {avg_roas:.2f} is high, can be more aggressive",
                confidence=0.85,
            ))

        cpi_values = [d.get("cpi", 0) for d in performance_data if d.get("cpi", 0) > 0]
        avg_cpi = sum(cpi_values) / len(cpi_values) if cpi_values else 0

        if avg_cpi < 2.0:
            updates.append(PolicyUpdate(
                policy_id="max_cpi_for_budget",
                old_value=self.policies["max_cpi_for_budget"],
                new_value=6.0,
                reason=f"Average CPI ${avg_cpi:.2f} is low, can increase tolerance",
                confidence=0.8,
            ))

        for update in updates:
            self.policies[update.policy_id] = update.new_value

        return updates

    def optimize_demo(self) -> List[PolicyUpdate]:
        data = [
            {"roas": 2.8, "cpi": 1.8},
            {"roas": 2.5, "cpi": 2.2},
            {"roas": 3.0, "cpi": 1.5},
            {"roas": 2.3, "cpi": 2.0},
        ]
        return self.optimize(data)
