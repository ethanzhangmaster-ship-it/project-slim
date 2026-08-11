"""V4.4.1 State Manager — unified workflow/task state management.

State machine:
  IDLE → RUNNING → WAIT_GPU/WAIT_IO → PAUSED → RETRYING → ROLLING_BACK → SUCCESS/FAILED

Tracks execution state of all workflows and tasks.
"""

from __future__ import annotations

import time
from typing import Any

from .schemas import WorkflowState, WorkflowStateData, TaskStatus


class StateManager:
    """Unified state manager for all workflows and tasks."""

    # Valid state transitions
    _VALID_TRANSITIONS: dict[WorkflowState, set[WorkflowState]] = {
        WorkflowState.IDLE: {WorkflowState.RUNNING},
        WorkflowState.RUNNING: {
            WorkflowState.WAIT_GPU, WorkflowState.WAIT_IO,
            WorkflowState.PAUSED, WorkflowState.SUCCESS, WorkflowState.FAILED,
            WorkflowState.CANCELLED,
        },
        WorkflowState.WAIT_GPU: {WorkflowState.RUNNING, WorkflowState.FAILED, WorkflowState.CANCELLED},
        WorkflowState.WAIT_IO: {WorkflowState.RUNNING, WorkflowState.FAILED, WorkflowState.CANCELLED},
        WorkflowState.PAUSED: {WorkflowState.RUNNING, WorkflowState.CANCELLED},
        WorkflowState.RETRYING: {WorkflowState.RUNNING, WorkflowState.FAILED},
        WorkflowState.ROLLING_BACK: {WorkflowState.RUNNING, WorkflowState.FAILED},
        WorkflowState.SUCCESS: set(),     # Terminal
        WorkflowState.FAILED: set(),      # Terminal
        WorkflowState.CANCELLED: set(),   # Terminal
    }

    def __init__(self) -> None:
        self._workflow_states: dict[str, WorkflowStateData] = {}
        self._task_states: dict[str, TaskStatus] = {}
        self._state_history: list[dict[str, Any]] = []

    # ── Workflow State ─────────────────────────────────────

    def init_workflow(self, workflow_id: str, total_levels: int = 0,
                      metadata: dict[str, Any] | None = None) -> WorkflowStateData:
        """Initialize workflow state."""
        state = WorkflowStateData(
            workflow_id=workflow_id,
            state=WorkflowState.IDLE,
            total_levels=total_levels,
            started_at=time.time(),
            updated_at=time.time(),
            metadata=metadata or {},
        )
        self._workflow_states[workflow_id] = state
        self._log_transition(workflow_id, None, WorkflowState.IDLE)
        return state

    def transition(self, workflow_id: str, new_state: WorkflowState,
                   error: str = "") -> bool:
        """Transition a workflow to a new state.

        Returns:
            True if transition is valid and applied.
        """
        current = self._workflow_states.get(workflow_id)
        if current is None:
            return False

        old_state = current.state
        if new_state not in self._VALID_TRANSITIONS.get(old_state, set()):
            return False

        current.state = new_state
        current.updated_at = time.time()
        if error:
            current.error = error

        self._log_transition(workflow_id, old_state, new_state, error)
        return True

    def can_transition(self, workflow_id: str, new_state: WorkflowState) -> bool:
        """Check if a state transition is valid."""
        current = self._workflow_states.get(workflow_id)
        if current is None:
            return False
        return new_state in self._VALID_TRANSITIONS.get(current.state, set())

    def get_workflow_state(self, workflow_id: str) -> WorkflowStateData | None:
        """Get current workflow state."""
        return self._workflow_states.get(workflow_id)

    def get_workflow_state_value(self, workflow_id: str) -> WorkflowState:
        """Get current workflow state enum value."""
        state = self._workflow_states.get(workflow_id)
        return state.state if state else WorkflowState.IDLE

    def update_progress(self, workflow_id: str, current_level: int,
                        completed_task: str = "",
                        failed_task: str = "",
                        skipped_task: str = "") -> None:
        """Update workflow progress."""
        state = self._workflow_states.get(workflow_id)
        if state is None:
            return
        state.current_level = current_level
        state.updated_at = time.time()
        if completed_task:
            state.completed_tasks.append(completed_task)
        if failed_task:
            state.failed_tasks.append(failed_task)
        if skipped_task:
            state.skipped_tasks.append(skipped_task)

    def get_all_workflows(self) -> dict[str, WorkflowStateData]:
        """Get all workflow states."""
        return dict(self._workflow_states)

    def get_active_workflows(self) -> list[WorkflowStateData]:
        """Get all non-terminal workflows."""
        terminal = {WorkflowState.SUCCESS, WorkflowState.FAILED, WorkflowState.CANCELLED}
        return [s for s in self._workflow_states.values() if s.state not in terminal]

    def get_summary(self) -> dict[str, Any]:
        """Get state summary across all workflows."""
        states = self._workflow_states
        counts = {s.value: 0 for s in WorkflowState}
        for s in states.values():
            counts[s.state.value] += 1

        return {
            "total": len(states),
            "by_state": counts,
            "active": len(self.get_active_workflows()),
            "terminal": len(states) - len(self.get_active_workflows()),
        }

    # ── Task State ─────────────────────────────────────────

    def set_task_state(self, task_id: str, status: TaskStatus) -> None:
        """Set task state."""
        old = self._task_states.get(task_id)
        self._task_states[task_id] = status
        self._state_history.append({
            "type": "task",
            "task_id": task_id,
            "from": old.value if old else None,
            "to": status.value,
            "timestamp": time.time(),
        })

    def get_task_state(self, task_id: str) -> TaskStatus | None:
        """Get task state."""
        return self._task_states.get(task_id)

    def get_task_states(self) -> dict[str, TaskStatus]:
        """Get all task states."""
        return dict(self._task_states)

    # ── History ────────────────────────────────────────────

    def get_history(self, workflow_id: str | None = None,
                    limit: int = 50) -> list[dict[str, Any]]:
        """Get state transition history."""
        if workflow_id:
            return [h for h in self._state_history if h.get("workflow_id") == workflow_id][-limit:]
        return self._state_history[-limit:]

    def _log_transition(self, workflow_id: str, from_state: WorkflowState | None,
                        to_state: WorkflowState, error: str = "") -> None:
        """Log a state transition."""
        self._state_history.append({
            "type": "workflow",
            "workflow_id": workflow_id,
            "from": from_state.value if from_state else None,
            "to": to_state.value,
            "error": error,
            "timestamp": time.time(),
        })