"""E10.1 Approval Workflow — Approval request lifecycle management.

Manages the state machine for human-in-the-loop approvals:
  PENDING → APPROVED
  PENDING → REJECTED
  PENDING → EXPIRED
  PENDING → ESCALATED

No real platform API calls. All in-memory state tracking.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from market_ops.execution_runtime.schemas import (
    ApprovalRequest,
    ApprovalStatus,
)


class ApprovalWorkflow:
    """Manages approval request lifecycle.

    Usage:
        workflow = ApprovalWorkflow()
        req = workflow.create_request(task, reason="budget +50%")
        req = workflow.approve(req.request_id, approved_by="ops_lead")
    """

    def __init__(self) -> None:
        self._requests: dict[str, ApprovalRequest] = {}

    def create_request(
        self,
        task: Any,
        reason: str = "",
        requested_by: str = "E10.1",
    ) -> ApprovalRequest:
        """Create a new approval request for a task.

        Args:
            task: ExecutionTask (duck-typed to avoid circular import)
            reason: Why approval is needed
            requested_by: System or user requesting approval

        Returns:
            ApprovalRequest with status=PENDING
        """
        req = ApprovalRequest(
            task_id=getattr(task, "task_id", ""),
            risk_level=getattr(task, "risk_level", "SAFE"),
            reason=reason,
            requested_by=requested_by,
            status=ApprovalStatus.PENDING.value,
        )
        self._requests[req.request_id] = req
        return req

    def approve(self, request_id: str, approved_by: str = "") -> ApprovalRequest | None:
        """Approve a pending request.

        Args:
            request_id: The approval request ID
            approved_by: Who approved it

        Returns:
            Updated ApprovalRequest, or None if not found / not pending
        """
        req = self._requests.get(request_id)
        if not req:
            return None
        if req.status != ApprovalStatus.PENDING.value:
            return None

        req.status = ApprovalStatus.APPROVED.value
        req.approved_by = approved_by
        return req

    def reject(self, request_id: str) -> ApprovalRequest | None:
        """Reject a pending request.

        Args:
            request_id: The approval request ID

        Returns:
            Updated ApprovalRequest, or None if not found / not pending
        """
        req = self._requests.get(request_id)
        if not req:
            return None
        if req.status != ApprovalStatus.PENDING.value:
            return None

        req.status = ApprovalStatus.REJECTED.value
        return req

    def expire(self, request_id: str) -> ApprovalRequest | None:
        """Mark a pending request as expired.

        Args:
            request_id: The approval request ID

        Returns:
            Updated ApprovalRequest, or None if not found / not pending
        """
        req = self._requests.get(request_id)
        if not req:
            return None
        if req.status != ApprovalStatus.PENDING.value:
            return None

        req.status = ApprovalStatus.EXPIRED.value
        return req

    def escalate(self, request_id: str) -> ApprovalRequest | None:
        """Escalate a pending request to higher tier.

        Args:
            request_id: The approval request ID

        Returns:
            Updated ApprovalRequest, or None if not found / not pending
        """
        req = self._requests.get(request_id)
        if not req:
            return None
        if req.status != ApprovalStatus.PENDING.value:
            return None

        req.status = ApprovalStatus.ESCALATED.value
        return req

    def get_request(self, request_id: str) -> ApprovalRequest | None:
        """Get an approval request by ID."""
        return self._requests.get(request_id)

    def get_request_for_task(self, task_id: str) -> ApprovalRequest | None:
        """Find the most recent approval request for a task."""
        matches = [r for r in self._requests.values() if r.task_id == task_id]
        if not matches:
            return None
        return max(matches, key=lambda r: r.created_at)

    @property
    def requests(self) -> list[ApprovalRequest]:
        """All tracked approval requests."""
        return list(self._requests.values())
