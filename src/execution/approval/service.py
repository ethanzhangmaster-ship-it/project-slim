"""P2.3.6 Approval Service — 聚合服务层。

One facade wiring the full chain:

    ExecutionRequest
        -> ApprovalWorkflow.submit()      (policy -> ApprovalRequest -> store)
        -> [human] approve()/reject()     (role checked)
        -> ExecutionAuthorization         (token, TTL, single-use)
        -> attach to request.authorization
        -> ProviderRouter.route()         (AuthorizationGate enforces Rule1~4)

The service NEVER executes anything itself; it only orchestrates the
workflow and hands an authorized request to the router.
"""

from __future__ import annotations

from typing import Any, Optional

from src.execution.approval.models import ExecutionAuthorization
from src.execution.approval.policy import ApprovalPolicy
from src.execution.approval.store import InMemoryApprovalStore
from src.execution.approval.workflow import (
    ApprovalWorkflow,
    AuthorizationGate,
    SubmitResult,
)
from src.execution.models import ExecutionRequest


class ApprovalService:
    """Facade over workflow + gate sharing ONE store."""

    def __init__(
        self,
        store=None,
        policy: Optional[ApprovalPolicy] = None,
        router: Any = None,
    ) -> None:
        self.store = store if store is not None else InMemoryApprovalStore()
        self.workflow = ApprovalWorkflow(store=self.store, policy=policy)
        self.gate = AuthorizationGate(store=self.store)
        self.router = router

    # ------------------------------------------------------------------
    # workflow passthrough
    # ------------------------------------------------------------------

    def submit(
        self, request: ExecutionRequest, requested_by: str = "system"
    ) -> SubmitResult:
        result = self.workflow.submit(request, requested_by=requested_by)
        # auto-approved -> attach the token immediately
        if result.authorization is not None:
            request.authorization = result.authorization
        return result

    def approve(
        self, approval_id: str, approver: str, role: str
    ) -> ExecutionAuthorization:
        return self.workflow.approve(approval_id, approver, role)

    def reject(self, approval_id: str, approver: str, role: str, reason: str = ""):
        return self.workflow.reject(approval_id, approver, role, reason=reason)

    def pending(self):
        return self.workflow.pending()

    # ------------------------------------------------------------------
    # authorize + execute
    # ------------------------------------------------------------------

    def authorize(
        self, request: ExecutionRequest, authorization: ExecutionAuthorization
    ) -> ExecutionRequest:
        """Attach an authorization token to the request (returns same obj)."""
        request.authorization = authorization
        return request

    def execute(self, request: ExecutionRequest):
        """Route an (authorized) request through the router.

        Requires a router to be configured; the router's AuthorizationGate
        enforces Rule1~4 for PRODUCTION requests.
        """
        if self.router is None:
            raise RuntimeError("ApprovalService has no router configured")
        return self.router.route(request)
