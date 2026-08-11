from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime, date, timedelta


@dataclass
class WeeklyPlan:
    week_start: date
    week_end: date
    plan_id: str
    objectives: List[str] = field(default_factory=list)
    strategies: List[Dict[str, Any]] = field(default_factory=list)
    budget_allocation: Dict[str, float] = field(default_factory=dict)
    key_metrics: Dict[str, float] = field(default_factory=dict)


class WeeklyStrategy:
    def __init__(self):
        self.goal_types = {
            "growth": self._build_growth_strategy,
            "efficiency": self._build_efficiency_strategy,
            "exploration": self._build_exploration_strategy,
            "defense": self._build_defense_strategy,
        }

    def generate(self, data: Dict[str, Any], goal: str = "growth") -> WeeklyPlan:
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        plan_id = f"weekly_plan_{week_start.strftime('%Y%m%d')}"

        builder = self.goal_types.get(goal, self._build_growth_strategy)
        objectives, strategies, budget_allocation, key_metrics = builder(data)

        return WeeklyPlan(
            week_start=week_start,
            week_end=week_end,
            plan_id=plan_id,
            objectives=objectives,
            strategies=strategies,
            budget_allocation=budget_allocation,
            key_metrics=key_metrics,
        )

    def _build_growth_strategy(self, data: Dict[str, Any]) -> tuple:
        return (
            ["Increase revenue by 20%", "Scale top performers", "Expand to new audiences"],
            [
                {"name": "Scale Winners", "action": "Increase budget by 30% for ROAS > 2.5", "priority": "high"},
                {"name": "New Audience Expansion", "action": "Test 3 new audience segments", "priority": "medium"},
                {"name": "Creative Refresh", "action": "Generate 20 new variants from winning DNA", "priority": "medium"},
            ],
            {"winners": 60, "new_segments": 25, "testing": 15},
            {"target_roas": 2.0, "target_cpi": 2.5, "revenue_growth": 0.2},
        )

    def _build_efficiency_strategy(self, data: Dict[str, Any]) -> tuple:
        return (
            ["Improve ROAS by 15%", "Reduce wasted spend", "Optimize underperforming campaigns"],
            [
                {"name": "Cut Waste", "action": "Pause campaigns with ROAS < 1.0", "priority": "high"},
                {"name": "Bid Optimization", "action": "Adjust bids based on CPI performance", "priority": "medium"},
                {"name": "Creative Rotation", "action": "Rotate fatigued creatives", "priority": "medium"},
            ],
            {"optimization": 70, "maintenance": 20, "testing": 10},
            {"target_roas": 2.2, "waste_reduction": 0.3, "efficiency_gain": 0.15},
        )

    def _build_exploration_strategy(self, data: Dict[str, Any]) -> tuple:
        return (
            ["Discover new winning creatives", "Test new platforms", "Explore new geographies"],
            [
                {"name": "Creative Experimentation", "action": "Test 50+ new creative variants", "priority": "high"},
                {"name": "Platform Expansion", "action": "Launch on TikTok if not active", "priority": "medium"},
                {"name": "Geo Testing", "action": "Test 2 new countries", "priority": "medium"},
            ],
            {"exploration": 50, "testing": 30, "core": 20},
            {"new_winners_found": 5, "platforms_tested": 1, "geos_tested": 2},
        )

    def _build_defense_strategy(self, data: Dict[str, Any]) -> tuple:
        return (
            ["Maintain revenue stability", "Protect top performers", "Prevent creative fatigue"],
            [
                {"name": "Protect Winners", "action": "Maintain budget for top 20% campaigns", "priority": "high"},
                {"name": "Fatigue Prevention", "action": "Proactively rotate creatives at 60% fatigue", "priority": "medium"},
                {"name": "Budget Protection", "action": "Set minimum budget floor for key campaigns", "priority": "medium"},
            ],
            {"protection": 75, "rotation": 15, "testing": 10},
            {"revenue_stability": 0.95, "fatigue_rate": 0.1, "key_campaigns_protected": 10},
        )

    def generate_demo(self) -> WeeklyPlan:
        data = {
            "current_revenue": 50000,
            "current_roas": 2.2,
            "top_performers": 15,
            "new_audiences": ["DE", "AU"],
        }
        return self.generate(data, "growth")
