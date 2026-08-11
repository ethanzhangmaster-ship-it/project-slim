"""
E16.6.13 — ASO Executor.

Unified execution interface for ASO operation plans.
MVP: creates task records that humans execute, with hooks for
future Google Play / App Store Connect API integration.

Supports:
  * Google Play Developer API (future: uploading images, updating listing)
  * App Store Connect API (future)
  * Human-executed tasks (current MVP)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import uuid4

from src.aso_intelligence.operator.models import (
    ASOOperationPlan,
    ASOOperationState,
    ApprovalLevel,
)


class ASOExecutor:
    """Execute ASO operation plans."""

    def __init__(self):
        self._tasks: Dict[str, Dict[str, Any]] = {}

    # ------------------------------------------------------------------ #
    def execute(self, plan: ASOOperationPlan) -> str:
        """Execute (or prepare for execution) an operation plan.

        For Level 1 (AUTO): marks as EXECUTING → immediately COMPLETED.
        For Level 2/3 (human): creates a task record, marks as READY.
        Returns the task_id.
        """
        task_id = str(uuid4())
        plan.task_id = task_id

        if plan.approval_level == ApprovalLevel.AUTO:
            # Auto-execute
            plan.advance(ASOOperationState.EXECUTING)
            self._tasks[task_id] = {
                "plan_id": plan.plan_id,
                "game_id": plan.game_id,
                "action_type": plan.action_type,
                "status": "auto_executed",
                "result": None,
            }
            plan.advance(ASOOperationState.COMPLETED)
        else:
            # Human execution required
            plan.advance(ASOOperationState.READY)
            self._tasks[task_id] = {
                "plan_id": plan.plan_id,
                "game_id": plan.game_id,
                "action_type": plan.action_type,
                "status": "ready_for_human",
                "result": None,
            }

        return task_id

    # ------------------------------------------------------------------ #
    def complete_task(
        self,
        task_id: str,
        result: Dict[str, Any] = None,
    ) -> bool:
        """Mark a human task as completed with results."""
        if task_id not in self._tasks:
            return False

        self._tasks[task_id]["status"] = "completed"
        self._tasks[task_id]["result"] = result or {}
        return True

    # ------------------------------------------------------------------ #
    def task_status(self, task_id: str) -> Optional[str]:
        task = self._tasks.get(task_id)
        return task["status"] if task else None

    # ------------------------------------------------------------------ #
    def pending_tasks(self) -> List[Dict[str, Any]]:
        return [
            {"task_id": tid, **t}
            for tid, t in self._tasks.items()
            if t["status"] == "ready_for_human"
        ]


__all__ = ["ASOExecutor"]
