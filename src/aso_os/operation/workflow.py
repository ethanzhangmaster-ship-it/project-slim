"""
E16.6.14 — ASO OS Operations: Workflow Engine & System Executor.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import uuid4

from src.aso_os.kernel.models import WorkflowStage


class WorkflowEngine:
    """8-stage workflow for all ASO actions."""

    STAGES = [
        WorkflowStage.DISCOVERED,
        WorkflowStage.ANALYZED,
        WorkflowStage.PLANNED,
        WorkflowStage.GENERATED,
        WorkflowStage.APPROVED,
        WorkflowStage.RUNNING,
        WorkflowStage.MEASURED,
        WorkflowStage.LEARNED,
    ]

    def __init__(self):
        self._workflows: Dict[str, List[WorkflowStage]] = {}

    def create(self, workflow_id: str) -> None:
        self._workflows[workflow_id] = [WorkflowStage.DISCOVERED]

    def advance(self, workflow_id: str) -> Optional[WorkflowStage]:
        stages = self._workflows.get(workflow_id)
        if not stages:
            return None
        current = stages[-1]
        idx = self.STAGES.index(current)
        if idx + 1 < len(self.STAGES):
            next_stage = self.STAGES[idx + 1]
            stages.append(next_stage)
            return next_stage
        return current

    def current_stage(self, workflow_id: str) -> Optional[WorkflowStage]:
        stages = self._workflows.get(workflow_id)
        return stages[-1] if stages else None

    def is_complete(self, workflow_id: str) -> bool:
        return self.current_stage(workflow_id) == WorkflowStage.LEARNED


class SystemExecutor:
    """Unified system executor — bridges E16.6.13 operator executor."""

    def __init__(self):
        self._executions: Dict[str, Dict[str, Any]] = {}

    def execute(self, workflow_id: str, action_type: str,
                game_id: str, market: str) -> str:
        task_id = str(uuid4())
        self._executions[task_id] = {
            "workflow_id": workflow_id,
            "action_type": action_type,
            "game_id": game_id,
            "market": market,
            "status": "executing",
            "result": None,
        }
        return task_id

    def complete(self, task_id: str, result: Dict = None) -> bool:
        if task_id not in self._executions:
            return False
        self._executions[task_id]["status"] = "completed"
        self._executions[task_id]["result"] = result or {}
        return True


__all__ = ["WorkflowEngine", "SystemExecutor"]
