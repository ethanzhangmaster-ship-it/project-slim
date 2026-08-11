"""E10.1 Execution Engine — Core State Machine + Scheduler.

Phase 2: Core execution runtime with mock platform adapter.
No real platform API calls. Real integration deferred to E10.2.

Flow:
  ExecutionTask (CREATED)
        │
        ▼
  validate()
        │
        ▼
  check_permission()
        │
        ▼
  APPROVED
        │
        ▼
  adapter.execute()
        │
        ▼
  EXECUTING → VERIFYING → COMPLETED
        │
        ▼ (failure)
  FAILED → ROLLBACK_PENDING → ROLLED_BACK
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from market_ops.execution_runtime.schemas import (
    ExecutionTask, ExecutionResult, ExecutionEvent,
    ExecutionStatus, ActionType, EventType, ApprovalStatus,
    from_growth_action,
)
from market_ops.execution_runtime.mock_adapter import MockPlatformAdapter
from market_ops.execution_runtime.approval_gate import ApprovalGate


# ═══════════════════════════════════════════════════════════
# State Machine Rules
# ═══════════════════════════════════════════════════════════

# Valid transitions: {from_status: [to_status, ...]}
VALID_TRANSITIONS: dict[str, list[str]] = {
    ExecutionStatus.CREATED.value: [
        ExecutionStatus.PENDING_APPROVAL.value,
        ExecutionStatus.APPROVED.value,
    ],
    ExecutionStatus.PENDING_APPROVAL.value: [
        ExecutionStatus.APPROVED.value,
        ExecutionStatus.CREATED.value,  # reject → back to created
    ],
    ExecutionStatus.APPROVED.value: [
        ExecutionStatus.EXECUTING.value,
        ExecutionStatus.COMPLETED.value,  # WATCH/RETEST skip execution
    ],
    ExecutionStatus.EXECUTING.value: [
        ExecutionStatus.VERIFYING.value,
        ExecutionStatus.FAILED.value,
    ],
    ExecutionStatus.VERIFYING.value: [
        ExecutionStatus.COMPLETED.value,
        ExecutionStatus.FAILED.value,
    ],
    ExecutionStatus.FAILED.value: [
        ExecutionStatus.ROLLBACK_PENDING.value,
        ExecutionStatus.EXECUTING.value,  # retry
    ],
    ExecutionStatus.ROLLBACK_PENDING.value: [
        ExecutionStatus.ROLLED_BACK.value,
    ],
    ExecutionStatus.ROLLED_BACK.value: [
        # Terminal state, no further transitions
    ],
    ExecutionStatus.COMPLETED.value: [
        # Terminal state, no further transitions
    ],
}

# Forbidden transitions explicitly checked
FORBIDDEN_TRANSITIONS: set[tuple[str, str]] = {
    (ExecutionStatus.COMPLETED.value, ExecutionStatus.EXECUTING.value),
    (ExecutionStatus.FAILED.value, ExecutionStatus.COMPLETED.value),
    (ExecutionStatus.ROLLED_BACK.value, ExecutionStatus.EXECUTING.value),
    (ExecutionStatus.COMPLETED.value, ExecutionStatus.FAILED.value),
}

# Action types that skip platform execution
NO_EXECUTION_ACTIONS = {ActionType.WATCH.value, ActionType.RETEST.value}


class ExecutionEngine:
    """Core execution runtime for E10.1.

    Manages the full execution lifecycle:
      Task creation → state machine → mock adapter → result collection.

    Usage:
        engine = ExecutionEngine()
        task = engine.create_task(action_dict)
        result = engine.execute(task)
    """

    def __init__(
        self,
        adapter: MockPlatformAdapter | None = None,
        approval_gate: ApprovalGate | None = None,
    ) -> None:
        self.adapter = adapter or MockPlatformAdapter()
        self.approval_gate = approval_gate or ApprovalGate()
        self._events: list[ExecutionEvent] = []
        self._results: list[ExecutionResult] = []
        self._tasks: dict[str, ExecutionTask] = {}
        self._correlation_id: str = ""

    # ═══════════════════════════════════════════════════════
    # Task Creation
    # ═══════════════════════════════════════════════════════

    def create_task(self, action: dict[str, Any]) -> ExecutionTask:
        """Create an ExecutionTask from a GrowthAction dict.

        Args:
            action: Dict with E9.9.5 GrowthActionItem format:
                {creative_id, action, budget_change: {current, target}, ...}

        Returns:
            ExecutionTask with status=CREATED
        """
        task = from_growth_action(action)
        task.status = ExecutionStatus.CREATED.value
        self._tasks[task.task_id] = task

        self._record_event(task, ExecutionStatus.CREATED.value)
        return task

    def create_tasks(self, actions: list[dict[str, Any]]) -> list[ExecutionTask]:
        """Batch create tasks from a list of GrowthAction dicts."""
        self._correlation_id = str(uuid.uuid4())
        tasks = []
        for action in actions:
            task = self.create_task(action)
            task.correlation_id = self._correlation_id
            tasks.append(task)
        return tasks

    # ═══════════════════════════════════════════════════════
    # Main Execution Flow
    # ═══════════════════════════════════════════════════════

    def execute(self, task: ExecutionTask) -> ExecutionResult:
        """Execute a single task through the full state machine.

        Flow:
          1. validate() — pre-execution checks
          2. check_permission() — approval gate
          3. transition to APPROVED
          4. adapter.execute() — mock platform call
          5. transition to EXECUTING → VERIFYING
          6. adapter.verify() — confirm result
          7. COMPLETED or FAILED → ROLLBACK

        Returns:
            ExecutionResult with final status
        """
        # ── Step 1: Validate ───────────────────────────────
        if not self._validate(task):
            return self._finalize_failure(task, "Validation failed")

        # ── Step 2: Check Permission ───────────────────────
        approved = self._check_permission(task)
        if not approved:
            self._transition(task, ExecutionStatus.PENDING_APPROVAL.value)
            return ExecutionResult(
                task_id=task.task_id,
                status=ExecutionStatus.PENDING_APPROVAL.value,
                error_message="Task requires human approval",
            )

        # ── Step 3: Transition to APPROVED ─────────────────
        if task.status != ExecutionStatus.APPROVED.value:
            self._transition(task, ExecutionStatus.APPROVED.value)

        # ── Step 4: WATCH/RETEST skip execution ────────────
        if task.action_type in NO_EXECUTION_ACTIONS:
            self._transition(task, ExecutionStatus.COMPLETED.value)
            result = ExecutionResult(
                task_id=task.task_id,
                status=ExecutionStatus.COMPLETED.value,
                platform_response={"success": True, "noop": True},
                actual_change=task.budget_change,
            )
            self._results.append(result)
            return result

        # ── Step 5: Execute via adapter ────────────────────
        self._transition(task, ExecutionStatus.EXECUTING.value)
        result = self.adapter.execute(task)

        if result.status == ExecutionStatus.FAILED.value:
            return self._handle_failure(task, result)

        # ── Step 6: Verify ─────────────────────────────────
        self._transition(task, ExecutionStatus.VERIFYING.value)
        result = self.adapter.verify(task)

        if result.status == ExecutionStatus.FAILED.value:
            return self._handle_failure(task, result)

        # ── Step 7: Complete ───────────────────────────────
        self._transition(task, ExecutionStatus.COMPLETED.value)
        self._results.append(result)
        return result

    def execute_all(self, tasks: list[ExecutionTask] | None = None) -> list[ExecutionResult]:
        """Execute all tasks.

        Args:
            tasks: Task list to execute. If None, uses all created tasks.

        Returns:
            List of ExecutionResults
        """
        if tasks is None:
            tasks = list(self._tasks.values())

        results = []
        for task in tasks:
            result = self.execute(task)
            results.append(result)
        return results

    # ═══════════════════════════════════════════════════════
    # Manual Approval (for Phase 3 compatibility)
    # ═══════════════════════════════════════════════════════

    def approve_task(self, task_id: str, approved_by: str = "") -> ExecutionTask | None:
        """Manually approve a task via ApprovalGate."""
        task = self._tasks.get(task_id)
        if not task:
            return None

        # Update approval gate decision
        self.approval_gate.approve(task_id, approved_by=approved_by)

        if task.status == ExecutionStatus.PENDING_APPROVAL.value:
            self._transition(task, ExecutionStatus.APPROVED.value)
        return task

    def reject_task(self, task_id: str) -> ExecutionTask | None:
        """Manually reject a task via ApprovalGate."""
        task = self._tasks.get(task_id)
        if not task:
            return None

        # Update approval gate decision
        self.approval_gate.reject(task_id)

        if task.status == ExecutionStatus.PENDING_APPROVAL.value:
            self._transition(task, ExecutionStatus.CREATED.value)
        return task

    # ═══════════════════════════════════════════════════════
    # Internal: State Machine
    # ═══════════════════════════════════════════════════════

    def _transition(self, task: ExecutionTask, new_status: str) -> None:
        """Execute a state transition with validation and event recording.

        Raises:
            ValueError: If transition is forbidden.
        """
        old_status = task.status

        # Check forbidden transitions
        forbidden_key = (old_status, new_status)
        if forbidden_key in FORBIDDEN_TRANSITIONS:
            raise ValueError(
                f"Forbidden transition: {old_status} → {new_status}"
            )

        # Check valid transitions (if old_status has defined rules)
        if old_status in VALID_TRANSITIONS:
            if new_status not in VALID_TRANSITIONS[old_status]:
                raise ValueError(
                    f"Invalid transition: {old_status} → {new_status}. "
                    f"Valid: {VALID_TRANSITIONS[old_status]}"
                )

        task.status = new_status
        task.updated_at = datetime.now(timezone.utc).isoformat()
        self._record_event(task, new_status, old_status)

    def _record_event(
        self,
        task: ExecutionTask,
        new_status: str,
        old_status: str = "",
    ) -> ExecutionEvent:
        """Record a state change event."""
        event = ExecutionEvent(
            task_id=task.task_id,
            event_type=EventType.STATE_CHANGED.value,
            old_state=old_status,
            new_state=new_status,
            metadata={
                "action_type": task.action_type,
                "creative_id": task.creative_id,
                "risk_level": task.risk_level,
            },
        )
        self._events.append(event)
        return event

    # ═══════════════════════════════════════════════════════
    # Internal: Validation & Permission
    # ═══════════════════════════════════════════════════════

    def _validate(self, task: ExecutionTask) -> bool:
        """Pre-execution validation checks.

        Returns False if task should be rejected before execution.
        """
        # Must have a creative_id
        if not task.creative_id:
            return False
        # Must have a valid action_type
        if task.action_type not in [a.value for a in ActionType]:
            return False
        # Must not be in a terminal state
        if task.status in (
            ExecutionStatus.COMPLETED.value,
            ExecutionStatus.ROLLED_BACK.value,
        ):
            return False
        return True

    def _check_permission(self, task: ExecutionTask) -> bool:
        """Check if task can proceed using ApprovalGate.

        Returns True if task is APPROVED (AUTO or already approved).
        Returns False if task is PENDING (requires human/manager approval).
        """
        # If already approved (e.g., manually approved after pending), allow
        if task.status == ExecutionStatus.APPROVED.value:
            return True
        decision = self.approval_gate.check(task)
        return decision.status == ApprovalStatus.APPROVED.value

    # ═══════════════════════════════════════════════════════
    # Internal: Failure Handling
    # ═══════════════════════════════════════════════════════

    def _handle_failure(
        self, task: ExecutionTask, result: ExecutionResult
    ) -> ExecutionResult:
        """Handle execution failure: FAILED → ROLLBACK_PENDING → ROLLED_BACK."""
        self._transition(task, ExecutionStatus.FAILED.value)

        # Attempt rollback
        self._transition(task, ExecutionStatus.ROLLBACK_PENDING.value)
        rollback_result = self.adapter.rollback(task)
        self._transition(task, ExecutionStatus.ROLLED_BACK.value)

        rollback_result.error_message = result.error_message
        self._results.append(rollback_result)
        return rollback_result

    def _finalize_failure(
        self, task: ExecutionTask, error: str
    ) -> ExecutionResult:
        """Mark task as failed without execution."""
        self._transition(task, ExecutionStatus.FAILED.value)
        result = ExecutionResult(
            task_id=task.task_id,
            status=ExecutionStatus.FAILED.value,
            error_message=error,
        )
        self._results.append(result)
        return result

    # ═══════════════════════════════════════════════════════
    # Accessors
    # ═══════════════════════════════════════════════════════

    @property
    def events(self) -> list[ExecutionEvent]:
        return list(self._events)

    @property
    def results(self) -> list[ExecutionResult]:
        return list(self._results)

    def get_task(self, task_id: str) -> ExecutionTask | None:
        return self._tasks.get(task_id)

    def get_events_for_task(self, task_id: str) -> list[ExecutionEvent]:
        return [e for e in self._events if e.task_id == task_id]

    def get_result_for_task(self, task_id: str) -> ExecutionResult | None:
        for r in self._results:
            if r.task_id == task_id:
                return r
        return None

    @property
    def correlation_id(self) -> str:
        return self._correlation_id