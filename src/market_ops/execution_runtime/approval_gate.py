"""E10.1 Approval Gate — Safety gate before execution.

Routes ExecutionTasks through the correct approval tier:
  SAFE     → AUTO     (immediate approval)
  WARNING  → HUMAN    (human approval required)
  CRITICAL → MANAGER  (manager approval required)

Special rules:
  KILL action → always HUMAN (regardless of risk level)

No real platform API calls. No imports from E9.9.5 decision layer.
"""

from __future__ import annotations

from market_ops.execution_runtime.schemas import (
    ExecutionTask,
    ApprovalDecision,
    ApprovalLevel,
    ApprovalStatus,
)
from market_ops.execution_runtime.approval_workflow import ApprovalWorkflow


class ApprovalGate:
    """Safety gate that determines if a task can proceed to execution.

    Usage:
        gate = ApprovalGate()
        decision = gate.check(task)
        if decision.status == ApprovalStatus.APPROVED.value:
            engine.execute(task)
        else:
            # Task is blocked pending approval
            pass
    """

    def __init__(self, workflow: ApprovalWorkflow | None = None) -> None:
        self.workflow = workflow or ApprovalWorkflow()
        self._decisions: dict[str, ApprovalDecision] = {}

    def check(self, task: ExecutionTask) -> ApprovalDecision:
        """Analyze a task and return an approval decision.

        Args:
            task: The ExecutionTask to evaluate

        Returns:
            ApprovalDecision with level and status
        """
        level = self._determine_level(task)

        if level == ApprovalLevel.AUTO.value:
            decision = ApprovalDecision(
                task_id=task.task_id,
                approval_level=level,
                status=ApprovalStatus.APPROVED.value,
                reason="Auto-approved: SAFE risk level",
            )
        else:
            # Human or manager approval required
            reason = self._build_reason(task, level)
            decision = ApprovalDecision(
                task_id=task.task_id,
                approval_level=level,
                status=ApprovalStatus.PENDING.value,
                reason=reason,
            )
            # Create an ApprovalRequest in the workflow
            self.workflow.create_request(task, reason=reason)

        self._decisions[decision.decision_id] = decision
        return decision

    def get_decision(self, decision_id: str) -> ApprovalDecision | None:
        """Get a decision by ID."""
        return self._decisions.get(decision_id)

    def get_decision_for_task(self, task_id: str) -> ApprovalDecision | None:
        """Find the most recent decision for a task."""
        matches = [d for d in self._decisions.values() if d.task_id == task_id]
        if not matches:
            return None
        return max(matches, key=lambda d: d.created_at)

    def approve(self, task_id: str, approved_by: str = "") -> ApprovalDecision | None:
        """Manually approve a pending decision and its associated request.

        Args:
            task_id: The task to approve
            approved_by: Who approved it

        Returns:
            Updated ApprovalDecision, or None if not found
        """
        decision = self.get_decision_for_task(task_id)
        if not decision:
            return None
        if decision.status != ApprovalStatus.PENDING.value:
            return None

        # Update the approval request in workflow
        req = self.workflow.get_request_for_task(task_id)
        if req:
            self.workflow.approve(req.request_id, approved_by=approved_by)

        decision.status = ApprovalStatus.APPROVED.value
        decision.resolved_at = __import__(
            "datetime", fromlist=["datetime"]
        ).datetime.now(__import__("datetime", fromlist=["timezone"]).timezone.utc).isoformat()
        return decision

    def reject(self, task_id: str) -> ApprovalDecision | None:
        """Reject a pending decision.

        Args:
            task_id: The task to reject

        Returns:
            Updated ApprovalDecision, or None if not found
        """
        decision = self.get_decision_for_task(task_id)
        if not decision:
            return None
        if decision.status != ApprovalStatus.PENDING.value:
            return None

        req = self.workflow.get_request_for_task(task_id)
        if req:
            self.workflow.reject(req.request_id)

        decision.status = ApprovalStatus.REJECTED.value
        decision.resolved_at = __import__(
            "datetime", fromlist=["datetime"]
        ).datetime.now(__import__("datetime", fromlist=["timezone"]).timezone.utc).isoformat()
        return decision

    @property
    def decisions(self) -> list[ApprovalDecision]:
        """All tracked approval decisions."""
        return list(self._decisions.values())

    # ───────────────────────────────────────────────────────
    # Internal: Level determination
    # ───────────────────────────────────────────────────────

    @staticmethod
    def _determine_level(task: ExecutionTask) -> str:
        """Determine approval level based on task risk and action type.

        Rules (in priority order):
          1. KILL action     → HUMAN
          2. CRITICAL risk   → MANAGER
          3. WARNING risk    → HUMAN
          4. SAFE risk       → AUTO
        """
        # Rule 1: KILL always requires human approval
        if task.action_type == "KILL":
            return ApprovalLevel.HUMAN.value

        # Rule 2-4: Risk-based routing
        if task.risk_level == "CRITICAL":
            return ApprovalLevel.MANAGER.value
        if task.risk_level == "WARNING":
            return ApprovalLevel.HUMAN.value

        return ApprovalLevel.AUTO.value

    @staticmethod
    def _build_reason(task: ExecutionTask, level: str) -> str:
        """Build human-readable reason for approval requirement."""
        if task.action_type == "KILL":
            return f"KILL action requires {level} approval"
        return f"{task.risk_level} risk requires {level} approval"
