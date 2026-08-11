"""P2.3.4 Approval Workflow Engine + AuthorizationGate.

ApprovalWorkflow:
    submit(execution_request)
        -> evaluate policy
        -> create ApprovalRequest (PENDING, or auto-APPROVED)
        -> persist to store
    approve(approval_id, approver, role) -> ExecutionAuthorization
    reject(approval_id, approver, role, reason)

AuthorizationGate (security rules, checked at execution time):
    Rule 1: PRODUCTION without an authorization        -> BLOCK
    Rule 2: authorization.allowed_action != action     -> BLOCK
    Rule 3: authorization expired                      -> BLOCK
    Rule 4: approval_id already consumed (one-shot)    -> BLOCK
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from src.execution.approval.models import (
    ApprovalRequest,
    ExecutionAuthorization,
    STATUS_APPROVED,
    STATUS_CANCELLED,
    STATUS_REJECTED,
    impact_float,
    risk_category,
)
from src.execution.approval.policy import (
    ApprovalPolicy,
    OUTCOME_AUTO,
    OUTCOME_DENY,
)
from src.execution.approval.roles import ApprovalRole, role_can
from src.execution.approval.store import InMemoryApprovalStore
from src.execution.models import ExecutionMode, ExecutionRequest

SYSTEM_APPROVER = "policy:auto"


@dataclass
class SubmitResult:
    """Outcome of submitting an execution request for approval."""

    request: ApprovalRequest
    outcome: str
    required_role: str
    reason: str
    authorization: Optional[ExecutionAuthorization] = None

    @property
    def auto_approved(self) -> bool:
        return self.authorization is not None


class ApprovalWorkflowError(Exception):
    pass


class ApprovalWorkflow:
    """Full approval lifecycle around a store + policy."""

    def __init__(
        self,
        store=None,
        policy: Optional[ApprovalPolicy] = None,
    ) -> None:
        self.store = store if store is not None else InMemoryApprovalStore()
        self.policy = policy if policy is not None else ApprovalPolicy()

    # ------------------------------------------------------------------
    # submit
    # ------------------------------------------------------------------

    def submit(
        self,
        execution_request: ExecutionRequest,
        requested_by: str = "system",
    ) -> SubmitResult:
        intent = execution_request.intent
        decision = self.policy.evaluate(intent)

        request = ApprovalRequest(
            execution_request_id=execution_request.request_id,
            intent_id=intent.intent_id,
            action=intent.action,
            domain=intent.domain,
            target=getattr(intent, "target_id", ""),
            risk_level=risk_category(getattr(intent, "risk_level", 1.0)),
            expected_impact=impact_float(getattr(intent, "expected_impact", 0.0)),
            confidence=impact_float(getattr(intent, "confidence", 0.0)),
            requested_by=requested_by,
            reason=decision.reason,
        )

        if decision.outcome == OUTCOME_DENY:
            request.status = STATUS_REJECTED
            request.resolved_by = SYSTEM_APPROVER
            request.reason = decision.reason
            self.store.save(request)
            return SubmitResult(
                request=request,
                outcome=decision.outcome,
                required_role="",
                reason=decision.reason,
            )

        if decision.outcome == OUTCOME_AUTO:
            request.status = STATUS_APPROVED
            request.resolved_by = SYSTEM_APPROVER
            self.store.save(request)
            authorization = ExecutionAuthorization(
                approval_id=request.approval_id,
                approved_by=SYSTEM_APPROVER,
                allowed_action=request.action,
            )
            return SubmitResult(
                request=request,
                outcome=decision.outcome,
                required_role=ApprovalRole.SYSTEM,
                reason=decision.reason,
                authorization=authorization,
            )

        # MANUAL / ADMIN -> PENDING, waits for a human
        self.store.save(request)
        return SubmitResult(
            request=request,
            outcome=decision.outcome,
            required_role=decision.required_role,
            reason=decision.reason,
        )

    # ------------------------------------------------------------------
    # human decisions
    # ------------------------------------------------------------------

    def approve(
        self,
        approval_id: str,
        approver: str,
        role: str,
    ) -> ExecutionAuthorization:
        request = self.store.get(approval_id)
        if request is None:
            raise ApprovalWorkflowError(f"approval not found: {approval_id}")
        if not request.is_pending:
            raise ApprovalWorkflowError(
                f"approval {approval_id} is not PENDING (status={request.status})"
            )
        if not role_can(role, request.action):
            raise ApprovalWorkflowError(
                f"role {role} cannot approve action {request.action}"
            )
        resolved = self.store.resolve(
            approval_id, STATUS_APPROVED, resolved_by=approver
        )
        if resolved is None:
            raise ApprovalWorkflowError(f"failed to resolve approval {approval_id}")
        return ExecutionAuthorization(
            approval_id=approval_id,
            approved_by=approver,
            allowed_action=request.action,
        )

    def reject(
        self,
        approval_id: str,
        approver: str,
        role: str,
        reason: str = "",
    ) -> ApprovalRequest:
        request = self.store.get(approval_id)
        if request is None:
            raise ApprovalWorkflowError(f"approval not found: {approval_id}")
        if not request.is_pending:
            raise ApprovalWorkflowError(
                f"approval {approval_id} is not PENDING (status={request.status})"
            )
        # Any known role may reject (rejecting is always safe)
        resolved = self.store.resolve(
            approval_id, STATUS_REJECTED, resolved_by=approver, reason=reason
        )
        if resolved is None:
            raise ApprovalWorkflowError(f"failed to resolve approval {approval_id}")
        return resolved

    def cancel(self, approval_id: str, by: str = "system") -> Optional[ApprovalRequest]:
        return self.store.resolve(approval_id, STATUS_CANCELLED, resolved_by=by)

    def pending(self):
        return self.store.pending()


class AuthorizationGate:
    """Execution-time enforcement of Rules 1-4.

    The router calls check() right before dispatching to a provider.
    Providers never decide approval themselves.
    """

    def __init__(self, store=None) -> None:
        self.store = store if store is not None else InMemoryApprovalStore()

    def check(
        self,
        request: ExecutionRequest,
        now: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """Returns (allowed, reason). Non-PRODUCTION modes always pass."""
        if request.mode != ExecutionMode.PRODUCTION:
            return True, "non-production mode: no authorization required"

        authorization = getattr(request, "authorization", None)

        # Rule 1: no authorization in PRODUCTION -> BLOCK
        if authorization is None:
            return False, "Rule1: PRODUCTION execution without authorization"

        # Rule 2: action mismatch -> BLOCK
        action = request.intent.action
        if not authorization.allows(action):
            return False, (
                f"Rule2: authorization allows '{authorization.allowed_action}' "
                f"but execution action is '{action}'"
            )

        # Rule 3: expired -> BLOCK
        if authorization.is_expired(now=now):
            return False, (
                f"Rule3: authorization expired at {authorization.expires_at}"
            )

        # Cross-check: the approval must exist and be APPROVED
        record = self.store.get(authorization.approval_id)
        if record is None or record.status != STATUS_APPROVED:
            status = record.status if record is not None else "MISSING"
            return False, (
                f"Rule1: approval {authorization.approval_id} not APPROVED "
                f"(status={status})"
            )

        # Rule 4: single-use — consume the approval atomically
        if not self.store.mark_executed(authorization.approval_id):
            return False, (
                f"Rule4: approval {authorization.approval_id} already executed"
            )

        return True, "authorized"
