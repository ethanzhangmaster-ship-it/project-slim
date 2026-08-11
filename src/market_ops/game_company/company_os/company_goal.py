from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime


@dataclass
class GoalDecomposition:
    goal_id: str
    business_goal: Dict[str, Any] = field(default_factory=dict)
    product_goals: List[Dict[str, Any]] = field(default_factory=list)
    development_goals: List[Dict[str, Any]] = field(default_factory=list)
    marketing_goals: List[Dict[str, Any]] = field(default_factory=list)
    financial_goals: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class GoalProgress:
    current_arr: float = 0.0
    months_completed: int = 0
    target_arr: float = 0.0
    timeline_months: int = 0
    progress_percentage: float = 0.0


class CompanyGoal:
    def __init__(self):
        self.goals: Dict[str, GoalDecomposition] = {}
        self.current_goal = None

    def set_goal(self, target_arr: float, timeline_months: int) -> GoalProgress:
        self.current_goal = {
            "target_arr": target_arr,
            "timeline_months": timeline_months,
        }
        return GoalProgress(
            target_arr=target_arr,
            timeline_months=timeline_months,
            current_arr=0,
            months_completed=0,
            progress_percentage=0,
        )

    def track_progress(self, current_arr: float, months_completed: int) -> GoalProgress:
        if not self.current_goal:
            return GoalProgress()
        
        target_arr = self.current_goal["target_arr"]
        timeline = self.current_goal["timeline_months"]
        
        progress = (current_arr / target_arr) * 100 if target_arr > 0 else 0
        
        return GoalProgress(
            current_arr=current_arr,
            months_completed=months_completed,
            target_arr=target_arr,
            timeline_months=timeline,
            progress_percentage=round(progress, 1),
        )

    def set_business_goal(self, objective: str, target: Dict[str, Any]) -> GoalDecomposition:
        goal_id = f"goal_{hash(objective) % 10000:04d}"
        
        product_goals = self._decompose_to_product(target)
        development_goals = self._decompose_to_development(product_goals)
        marketing_goals = self._decompose_to_marketing(target)
        financial_goals = self._decompose_to_financial(target)

        decomposition = GoalDecomposition(
            goal_id=goal_id,
            business_goal={"objective": objective, "target": target},
            product_goals=product_goals,
            development_goals=development_goals,
            marketing_goals=marketing_goals,
            financial_goals=financial_goals,
        )
        
        self.goals[goal_id] = decomposition
        return decomposition

    def _decompose_to_product(self, target: Dict[str, Any]) -> List[Dict[str, Any]]:
        arr = target.get("arr", 10_000_000)
        
        return [
            {"name": "Game Concept", "target": "Discovery", "priority": 1},
            {"name": "Core Loop Design", "target": "Engaging", "priority": 1},
            {"name": "Monetization Design", "target": f"${arr / 12:,.0f}/month", "priority": 2},
            {"name": "Retention Optimization", "target": "D30 > 10%", "priority": 2},
        ]

    def _decompose_to_development(self, product_goals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [
            {"name": "MVP Development", "target": "8 weeks", "priority": 1},
            {"name": "Feature Implementation", "target": "12 weeks", "priority": 2},
            {"name": "Bug Fixing", "target": "< 5 critical", "priority": 3},
            {"name": "Performance Optimization", "target": "60 FPS", "priority": 3},
        ]

    def _decompose_to_marketing(self, target: Dict[str, Any]) -> List[Dict[str, Any]]:
        return [
            {"name": "Creative Production", "target": "50 assets/month", "priority": 1},
            {"name": "UA Scale", "target": "500 installs/day", "priority": 2},
            {"name": "ASO Optimization", "target": "Top 10 Keywords", "priority": 2},
            {"name": "Community Building", "target": "10k followers", "priority": 3},
        ]

    def _decompose_to_financial(self, target: Dict[str, Any]) -> List[Dict[str, Any]]:
        arr = target.get("arr", 10_000_000)
        
        return [
            {"name": "Monthly Revenue", "target": f"${arr / 12:,.0f}", "priority": 1},
            {"name": "ROAS", "target": "> 1.5", "priority": 1},
            {"name": "Payback Period", "target": "< 90 days", "priority": 2},
            {"name": "Profit Margin", "target": "> 30%", "priority": 2},
        ]

    def get_goal(self, goal_id: str) -> Optional[GoalDecomposition]:
        return self.goals.get(goal_id)

    def set_goal_demo(self) -> GoalDecomposition:
        return self.set_business_goal(
            objective="12 months to $10M ARR",
            target={"arr": 10_000_000, "timeline": 12},
        )
