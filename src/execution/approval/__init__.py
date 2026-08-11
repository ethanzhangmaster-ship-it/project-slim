"""P2.3 Execution Approval Workflow — 包入口。

Execution Request -> Approval Workflow -> Permission Policy
    -> Human Decision -> Execution Authorization -> Provider
"""

from src.execution.approval.models import (
    ApprovalRequest,
    ExecutionAuthorization,
    STATUS_APPROVED,
    STATUS_CANCELLED,
    STATUS_EXPIRED,
    STATUS_PENDING,
    STATUS_REJECTED,
    TERMINAL_STATUSES,
    VALID_STATUSES,
    risk_category,
)
from src.execution.approval.policy import (
    ApprovalDecision,
    ApprovalPolicy,
    OUTCOME_ADMIN,
    OUTCOME_AUTO,
    OUTCOME_DENY,
    OUTCOME_MANUAL,
)
from src.execution.approval.roles import (
    ApprovalRole,
    ROLE_ALLOWED,
    ROLE_ORDER,
    minimum_role_for,
    role_can,
    role_level,
)
from src.execution.approval.service import ApprovalService
from src.execution.approval.store import (
    InMemoryApprovalStore,
    JsonlApprovalStore,
)
from src.execution.approval.workflow import (
    ApprovalWorkflow,
    ApprovalWorkflowError,
    AuthorizationGate,
    SubmitResult,
)

__all__ = [
    # models
    "ApprovalRequest",
    "ExecutionAuthorization",
    "STATUS_PENDING",
    "STATUS_APPROVED",
    "STATUS_REJECTED",
    "STATUS_EXPIRED",
    "STATUS_CANCELLED",
    "VALID_STATUSES",
    "TERMINAL_STATUSES",
    "risk_category",
    # roles
    "ApprovalRole",
    "ROLE_ORDER",
    "ROLE_ALLOWED",
    "role_can",
    "role_level",
    "minimum_role_for",
    # policy
    "ApprovalPolicy",
    "ApprovalDecision",
    "OUTCOME_AUTO",
    "OUTCOME_MANUAL",
    "OUTCOME_ADMIN",
    "OUTCOME_DENY",
    # store
    "InMemoryApprovalStore",
    "JsonlApprovalStore",
    # workflow
    "ApprovalWorkflow",
    "ApprovalWorkflowError",
    "AuthorizationGate",
    "SubmitResult",
    # service
    "ApprovalService",
]
