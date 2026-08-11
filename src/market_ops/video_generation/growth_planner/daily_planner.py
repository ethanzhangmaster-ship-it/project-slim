from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime, date


@dataclass
class PlanItem:
    id: str
    action: str
    target: str
    reason: str
    priority: int
    budget: float = 0.0
    expected_outcome: str = ""
    status: str = "pending"


@dataclass
class DailyPlan:
    date: date
    plan_id: str
    items: List[PlanItem] = field(default_factory=list)
    summary: str = ""
    created_at: datetime = field(default_factory=datetime.now)


class DailyPlanner:
    def __init__(self):
        self.priority_weights = {
            "scale": 5,
            "kill": 4,
            "optimize": 3,
            "test": 2,
            "monitor": 1,
        }

    def generate(self, data: Dict[str, Any]) -> DailyPlan:
        today = date.today()
        plan_id = f"daily_plan_{today.strftime('%Y%m%d')}"
        items = []

        winners = data.get("winners", [])
        for winner in winners:
            if winner.get("roas", 0) > 2.0:
                items.append(PlanItem(
                    id=f"plan_{len(items)+1:03d}",
                    action="scale",
                    target=winner.get("creative_id", ""),
                    reason=f"D7 ROAS {winner.get('roas', 0):.1f}+ - high performer",
                    priority=self.priority_weights["scale"],
                    budget=winner.get("budget", 0) * 1.3,
                    expected_outcome=f"Expected ROAS maintain at {winner.get('roas', 0):.1f}, revenue increase by 30%",
                ))

        failures = data.get("failures", [])
        for failure in failures:
            items.append(PlanItem(
                id=f"plan_{len(items)+1:03d}",
                action="kill",
                target=failure.get("creative_id", ""),
                reason=failure.get("reason", "Performance below threshold"),
                priority=self.priority_weights["kill"],
            ))

        opportunities = data.get("opportunities", [])
        for opp in opportunities:
            items.append(PlanItem(
                id=f"plan_{len(items)+1:03d}",
                action="test",
                target=opp.get("target", ""),
                reason=opp.get("reason", "New opportunity"),
                priority=self.priority_weights["test"],
                budget=opp.get("budget", 0),
                expected_outcome=opp.get("expected_outcome", ""),
            ))

        items.sort(key=lambda x: x.priority, reverse=True)

        summary = self._generate_summary(items)

        return DailyPlan(
            date=today,
            plan_id=plan_id,
            items=items,
            summary=summary,
        )

    def _generate_summary(self, items: List[PlanItem]) -> str:
        scale_count = sum(1 for i in items if i.action == "scale")
        kill_count = sum(1 for i in items if i.action == "kill")
        test_count = sum(1 for i in items if i.action == "test")
        
        summary = f"Today's Strategy:\n"
        if scale_count > 0:
            summary += f"\n1. Scale {scale_count} creative(s)\n"
            for item in items[:scale_count]:
                summary += f"   - {item.target}: {item.reason}\n"
        
        if kill_count > 0:
            summary += f"\n2. Kill {kill_count} creative(s)\n"
            kills = [i for i in items if i.action == "kill"][:3]
            for item in kills:
                summary += f"   - {item.target}: {item.reason}\n"
        
        if test_count > 0:
            summary += f"\n3. Test {test_count} new variant(s)\n"
        
        return summary

    def generate_demo(self) -> DailyPlan:
        data = {
            "winners": [
                {"creative_id": "creative_A", "roas": 3.5, "budget": 500},
                {"creative_id": "creative_B", "roas": 2.8, "budget": 400},
            ],
            "failures": [
                {"creative_id": "creative_C", "reason": "CTR -35%, no purchases"},
            ],
            "opportunities": [
                {"target": "new_segment_US_35-44", "reason": "High match score 0.91", "budget": 300, "expected_outcome": "Test new audience segment"},
            ],
        }
        return self.generate(data)
