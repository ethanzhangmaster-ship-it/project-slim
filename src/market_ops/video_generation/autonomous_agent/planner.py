"""Planner - 规划器"""
from dataclasses import dataclass
from typing import Dict, Any, List


@dataclass
class PlanStep:
    """规划步骤"""
    step_id: str = ""
    action: str = ""
    target: str = ""
    dependencies: List[str] = None
    estimated_time: str = ""
    status: str = "pending"
    
    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "action": self.action,
            "target": self.target,
            "dependencies": self.dependencies,
            "estimated_time": self.estimated_time,
            "status": self.status,
        }


@dataclass
class Plan:
    """计划"""
    plan_id: str = ""
    name: str = ""
    steps: List[PlanStep] = None
    created_at: str = ""
    status: str = "pending"
    
    def __post_init__(self):
        if self.steps is None:
            self.steps = []
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "name": self.name,
            "steps": [s.to_dict() for s in self.steps],
            "created_at": self.created_at,
            "status": self.status,
        }


class Planner:
    """规划器"""
    
    def __init__(self):
        self._counter = 0
    
    def create_plan(self, objectives: List[str]) -> Plan:
        """创建计划"""
        self._counter += 1
        plan_id = f"plan_{self._counter:04d}"
        
        steps = []
        
        # 默认每日计划
        default_steps = [
            ("read_data", "Read Meta/Google/ASA data", []),
            ("attribution", "Run attribution analysis", ["read_data"]),
            ("discover_winners", "Discover winning creatives", ["attribution"]),
            ("match_audiences", "Match with best audiences", ["discover_winners"]),
            ("generate_strategy", "Generate strategy recommendations", ["match_audiences"]),
            ("adjust_budget", "Adjust budget allocations", ["generate_strategy"]),
            ("create_experiments", "Create A/B tests", ["adjust_budget"]),
            ("generate_report", "Generate daily report", ["create_experiments"]),
        ]
        
        for i, (action, target, dependencies) in enumerate(default_steps):
            steps.append(PlanStep(
                step_id=f"step_{i+1:02d}",
                action=action,
                target=target,
                dependencies=dependencies,
                estimated_time=f"{i * 15 + 15}min",
                status="pending",
            ))
        
        return Plan(
            plan_id=plan_id,
            name=f"Daily UA Plan {self._counter}",
            steps=steps,
            created_at="2024-01-15T08:00:00",
            status="active",
        )
    
    def get_plan(self, plan_id: str) -> Plan:
        """获取计划"""
        return Plan(plan_id=plan_id)
    
    def create_plan_demo(self) -> Plan:
        """演示创建计划"""
        objectives = ["Increase ROAS by 20%", "Scale top performers"]
        return self.create_plan(objectives)
