from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from enum import Enum


class WorkflowStatus(Enum):
    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class WorkflowState:
    workflow_id: str
    name: str
    status: WorkflowStatus = WorkflowStatus.CREATED
    current_step: str = ""
    total_steps: int = 0
    completed_steps: int = 0
    failed_steps: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: float = 0.0
    cost: float = 0.0
    error: Optional[str] = None


class WorkflowMonitor:
    def __init__(self):
        self._workflows: Dict[str, WorkflowState] = {}
        self._step_history: Dict[str, List[Dict[str, Any]]] = {}

    def register_workflow(self, workflow_id: str, name: str, total_steps: int = 0) -> WorkflowState:
        state = WorkflowState(
            workflow_id=workflow_id,
            name=name,
            total_steps=total_steps,
        )
        self._workflows[workflow_id] = state
        self._step_history[workflow_id] = []
        return state

    def start_workflow(self, workflow_id: str) -> bool:
        wf = self._workflows.get(workflow_id)
        if not wf:
            return False
        wf.status = WorkflowStatus.RUNNING
        wf.started_at = datetime.now()
        return True

    def step_started(self, workflow_id: str, step_name: str) -> bool:
        wf = self._workflows.get(workflow_id)
        if not wf:
            return False
        wf.current_step = step_name
        self._step_history[workflow_id].append({
            "step": step_name,
            "status": "started",
            "timestamp": datetime.now().isoformat(),
        })
        return True

    def step_completed(self, workflow_id: str, step_name: str, cost: float = 0.0) -> bool:
        wf = self._workflows.get(workflow_id)
        if not wf:
            return False
        wf.completed_steps += 1
        wf.cost += cost
        self._step_history[workflow_id].append({
            "step": step_name,
            "status": "completed",
            "timestamp": datetime.now().isoformat(),
            "cost": cost,
        })
        return True

    def step_failed(self, workflow_id: str, step_name: str, error: str = "") -> bool:
        wf = self._workflows.get(workflow_id)
        if not wf:
            return False
        wf.failed_steps += 1
        wf.error = error
        self._step_history[workflow_id].append({
            "step": step_name,
            "status": "failed",
            "timestamp": datetime.now().isoformat(),
            "error": error,
        })
        return True

    def complete_workflow(self, workflow_id: str, status: WorkflowStatus = WorkflowStatus.COMPLETED) -> bool:
        wf = self._workflows.get(workflow_id)
        if not wf:
            return False
        wf.status = status
        wf.completed_at = datetime.now()
        if wf.started_at:
            wf.duration_seconds = (wf.completed_at - wf.started_at).total_seconds()
        return True

    def get_workflow(self, workflow_id: str) -> Optional[WorkflowState]:
        return self._workflows.get(workflow_id)

    def get_workflows_by_status(self, status: WorkflowStatus) -> List[WorkflowState]:
        return [w for w in self._workflows.values() if w.status == status]

    def get_progress(self, workflow_id: str) -> Dict[str, Any]:
        wf = self._workflows.get(workflow_id)
        if not wf:
            return {}
        progress = wf.completed_steps / wf.total_steps * 100 if wf.total_steps > 0 else 0
        return {
            "workflow_id": workflow_id,
            "name": wf.name,
            "status": wf.status.value,
            "current_step": wf.current_step,
            "progress_percent": round(progress, 1),
            "completed_steps": wf.completed_steps,
            "total_steps": wf.total_steps,
            "failed_steps": wf.failed_steps,
        }

    def get_long_running(self, threshold_minutes: int = 60) -> List[WorkflowState]:
        now = datetime.now()
        long_running = []
        for wf in self._workflows.values():
            if wf.status != WorkflowStatus.RUNNING:
                continue
            if wf.started_at and (now - wf.started_at).total_seconds() > threshold_minutes * 60:
                long_running.append(wf)
        return long_running

    def get_dashboard(self) -> Dict[str, Any]:
        total = len(self._workflows)
        running = len(self.get_workflows_by_status(WorkflowStatus.RUNNING))
        completed = len(self.get_workflows_by_status(WorkflowStatus.COMPLETED))
        failed = len(self.get_workflows_by_status(WorkflowStatus.FAILED))
        total_cost = sum(w.cost for w in self._workflows.values())
        avg_duration = sum(w.duration_seconds for w in self._workflows.values() if w.completed_at) / max(completed, 1)

        return {
            "total_workflows": total,
            "running": running,
            "completed": completed,
            "failed": failed,
            "success_rate": round(completed / (completed + failed) * 100, 1) if (completed + failed) > 0 else 0,
            "total_cost": round(total_cost, 2),
            "avg_duration_seconds": round(avg_duration, 1),
            "timestamp": datetime.now().isoformat(),
        }
