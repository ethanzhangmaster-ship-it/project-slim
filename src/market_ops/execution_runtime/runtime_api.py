"""E10.1 Runtime API — Unified facade for Execution Runtime.

Provides a stable API boundary so E9.9.5 Learning Layer and
external consumers can create, execute, query, and export
execution artifacts without touching internal modules.

No real platform API calls. No imports from E9.9.5 decision layer.
"""

from __future__ import annotations

from typing import Any

from market_ops.execution_runtime.schemas import (
    ExecutionTask,
    ExecutionResult,
    ExecutionStatus,
    APIResponse,
    from_growth_action,
)
from market_ops.execution_runtime.execution_engine import ExecutionEngine
from market_ops.execution_runtime.result_collector import ResultCollector
from market_ops.execution_runtime.feedback_loop import FeedbackLoop
from market_ops.execution_runtime.export_service import ExportService


class RuntimeAPI:
    """Facade for the entire E10.1 Execution Runtime.

    Usage:
        api = RuntimeAPI()
        resp = api.create_execution({"action": "SCALE", ...})
        resp = api.execute_task(task_id)
        resp = api.get_execution(task_id)
        resp = api.get_feedback(task_id)
    """

    def __init__(
        self,
        engine: ExecutionEngine | None = None,
        collector: ResultCollector | None = None,
        feedback: FeedbackLoop | None = None,
        exporter: ExportService | None = None,
    ) -> None:
        self.engine = engine or ExecutionEngine()
        self.collector = collector or ResultCollector()
        self.feedback = feedback or FeedbackLoop()
        self.exporter = exporter or ExportService()

    def create_execution(self, action: dict[str, Any]) -> APIResponse:
        """Create an ExecutionTask from a GrowthAction dict.

        Args:
            action: Dict with keys matching E9.9.5 GrowthActionItem.

        Returns:
            APIResponse with task_id and CREATED status.
        """
        try:
            task = from_growth_action(action)
            self.engine._tasks[task.task_id] = task
            return APIResponse(
                success=True,
                data={
                    "task_id": task.task_id,
                    "status": task.status,
                    "action_type": task.action_type,
                },
            )
        except Exception as exc:
            return APIResponse(success=False, error=str(exc))

    def execute_task(self, task_id: str) -> APIResponse:
        """Execute a previously created task.

        Args:
            task_id: The task to execute.

        Returns:
            APIResponse with execution result status and result_id.
        """
        task = self.engine._tasks.get(task_id)
        if not task:
            return APIResponse(
                success=False,
                error=f"Task not found: {task_id}",
            )

        try:
            result = self.engine.execute(task)
            # Auto-collect and generate feedback on completion
            if result.status == ExecutionStatus.COMPLETED.value:
                record = self.collector.collect(result)
                snap = self.collector.snapshot(record)
                self.feedback.generate(snap)

            return APIResponse(
                success=True,
                data={
                    "task_id": task_id,
                    "status": result.status,
                    "result_id": result.result_id,
                },
            )
        except Exception as exc:
            return APIResponse(success=False, error=str(exc))

    def get_execution(self, task_id: str) -> APIResponse:
        """Query the current state of a task.

        Args:
            task_id: The task to query.

        Returns:
            APIResponse with task state and metadata.
        """
        task = self.engine._tasks.get(task_id)
        if not task:
            return APIResponse(
                success=False,
                error=f"Task not found: {task_id}",
            )

        return APIResponse(
            success=True,
            data={
                "task_id": task_id,
                "state": task.status,
                "action_type": task.action_type,
                "risk_level": task.risk_level,
            },
        )

    def get_feedback(self, task_id: str) -> APIResponse:
        """Query the most recent learning signal for a task.

        Args:
            task_id: The task to query.

        Returns:
            APIResponse with feedback_type, recommendation, and confidence.
        """
        signals = self.feedback.get_history(task_id)
        if not signals:
            return APIResponse(
                success=False,
                error=f"No feedback found for task: {task_id}",
            )

        latest = signals[0]
        return APIResponse(
            success=True,
            data={
                "task_id": task_id,
                "feedback_type": latest.feedback_type,
                "recommendation": latest.recommendation,
                "confidence": latest.confidence,
                "metrics": latest.metrics,
            },
        )

    def approve_task(self, task_id: str, approved_by: str = "") -> APIResponse:
        """Manually approve a pending task.

        Args:
            task_id: The task to approve.
            approved_by: Who approved it.

        Returns:
            APIResponse with updated task state.
        """
        task = self.engine.approve_task(task_id, approved_by=approved_by)
        if not task:
            return APIResponse(
                success=False,
                error=f"Task not found or not pending: {task_id}",
            )

        return APIResponse(
            success=True,
            data={
                "task_id": task_id,
                "state": task.status,
            },
        )
