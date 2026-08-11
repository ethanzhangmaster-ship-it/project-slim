"""Executor - 执行器"""
from dataclasses import dataclass
from typing import Dict, Any, List


@dataclass
class ExecutionResult:
    """执行结果"""
    step_id: str = ""
    action: str = ""
    target: str = ""
    success: bool = False
    result: Dict[str, Any] = None
    error: str = ""
    
    def __post_init__(self):
        if self.result is None:
            self.result = {}
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "action": self.action,
            "target": self.target,
            "success": self.success,
            "result": {k: round(v, 2) if isinstance(v, float) else v for k, v in self.result.items()},
            "error": self.error,
        }


class Executor:
    """执行器"""
    
    def execute(self, plan) -> List[ExecutionResult]:
        """执行计划"""
        results = []
        
        for step in plan.steps:
            result = self._execute_step(step)
            results.append(result)
            
            if result.success:
                step.status = "completed"
            else:
                step.status = "failed"
                break
        
        return results
    
    def _execute_step(self, step: 'PlanStep') -> ExecutionResult:
        """执行单个步骤"""
        action = step.action
        
        try:
            result = {}
            
            if action == "read_data":
                result = {"data_sources": ["Meta", "Google", "ASA"], "records": 10000}
            
            elif action == "attribution":
                result = {"attributed_creatives": 50, "top_performer": "creative_001"}
            
            elif action == "discover_winners":
                result = {"winners_found": 5, "patterns_found": 3}
            
            elif action == "match_audiences":
                result = {"matches_found": 8, "best_match": "US_Female_30-44"}
            
            elif action == "generate_strategy":
                result = {"strategies_generated": 3, "recommendations": ["Scale A", "Kill B"]}
            
            elif action == "adjust_budget":
                result = {"budgets_adjusted": 5, "total_increase": 500}
            
            elif action == "create_experiments":
                result = {"experiments_created": 2, "variants": 6}
            
            elif action == "generate_report":
                result = {"report_generated": True, "path": "/reports/daily_report.pdf"}
            
            return ExecutionResult(
                step_id=step.step_id,
                action=action,
                target=step.target,
                success=True,
                result=result,
            )
        
        except Exception as e:
            return ExecutionResult(
                step_id=step.step_id,
                action=action,
                target=step.target,
                success=False,
                error=str(e),
            )
    
    def execute_demo(self) -> List[ExecutionResult]:
        """演示执行"""
        from .planner import Planner
        
        planner = Planner()
        plan = planner.create_plan_demo()
        return self.execute(plan)
