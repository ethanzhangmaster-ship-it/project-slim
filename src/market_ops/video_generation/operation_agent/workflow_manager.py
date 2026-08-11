from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime


@dataclass
class WorkflowStep:
    step_id: str
    name: str
    action: str
    status: str = "pending"
    result: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    executed_at: Optional[datetime] = None


@dataclass
class WorkflowResult:
    workflow_id: str
    steps: List[WorkflowStep]
    overall_status: str
    summary: str = ""
    completed_at: Optional[datetime] = None


class WorkflowManager:
    def __init__(self):
        self.workflows = {}

    def create_workflow(self, workflow_id: str, steps: List[WorkflowStep]) -> WorkflowResult:
        self.workflows[workflow_id] = {"steps": steps, "started_at": datetime.now()}
        return self.execute_workflow(workflow_id)

    def execute_workflow(self, workflow_id: str) -> WorkflowResult:
        workflow = self.workflows.get(workflow_id)
        if not workflow:
            return WorkflowResult(
                workflow_id=workflow_id,
                steps=[],
                overall_status="failed",
                summary="Workflow not found",
            )

        steps = workflow["steps"]
        
        for step in steps:
            step.executed_at = datetime.now()
            try:
                step.result = self._execute_step(step)
                step.status = "completed"
            except Exception as e:
                step.status = "failed"
                step.error = str(e)
                break

        all_completed = all(s.status == "completed" for s in steps)
        overall_status = "completed" if all_completed else "failed"
        
        return WorkflowResult(
            workflow_id=workflow_id,
            steps=steps,
            overall_status=overall_status,
            summary=f"{sum(1 for s in steps if s.status == 'completed')}/{len(steps)} steps completed",
            completed_at=datetime.now(),
        )

    def _execute_step(self, step: WorkflowStep) -> Dict[str, Any]:
        step_handlers = {
            "collect_data": lambda: {"data_collected": True, "sources": ["meta", "google", "asa"]},
            "analyze": lambda: {"analysis_complete": True, "insights": 5},
            "plan": lambda: {"plan_generated": True, "actions": 3},
            "execute": lambda: {"execution_complete": True, "success_count": 3},
            "report": lambda: {"report_generated": True, "recipients": ["growth@company.com"]},
        }
        
        handler = step_handlers.get(step.action, lambda: {"executed": True})
        return handler()

    def create_workflow_demo(self) -> WorkflowResult:
        steps = [
            WorkflowStep(step_id="step_1", name="Collect Data", action="collect_data"),
            WorkflowStep(step_id="step_2", name="Analyze", action="analyze"),
            WorkflowStep(step_id="step_3", name="Generate Plan", action="plan"),
            WorkflowStep(step_id="step_4", name="Execute", action="execute"),
            WorkflowStep(step_id="step_5", name="Report", action="report"),
        ]
        return self.create_workflow("workflow_daily", steps)
