"""P2.3.4 workflow tests.

验收场景 ①：ExecutionRequest -> ApprovalRequest 创建 PASS
验收场景 ③：审批通过 -> PENDING -> APPROVED 状态流转
"""

import pytest

from src.execution.approval.models import (
    STATUS_APPROVED,
    STATUS_CANCELLED,
    STATUS_PENDING,
    STATUS_REJECTED,
)
from src.execution.approval.roles import ApprovalRole
from src.execution.approval.store import InMemoryApprovalStore
from src.execution.approval.workflow import (
    ApprovalWorkflow,
    ApprovalWorkflowError,
    SYSTEM_APPROVER,
)
from src.execution.models import (
    ExecutionAction,
    ExecutionDomain,
    ExecutionIntent,
    ExecutionMode,
    ExecutionRequest,
)


def _exec_request(action=ExecutionAction.PAUSE_CAMPAIGN, risk=0.5, confidence=0.8,
                  mode=ExecutionMode.PRODUCTION, impact=None):
    intent = ExecutionIntent(
        intent_id="",
        decision_id="dec_1",
        domain=ExecutionDomain.UA,
        action=action,
        target_id="p04",
        reason="test",
        confidence=confidence,
        expected_impact=impact,
        risk_level=risk,
    )
    return ExecutionRequest(intent=intent, mode=mode)


@pytest.fixture
def workflow():
    return ApprovalWorkflow(store=InMemoryApprovalStore())


class TestSubmit:
    def test_submit_creates_pending_approval(self, workflow):
        # 验收 ①：ExecutionRequest -> ApprovalRequest
        req = _exec_request()
        result = workflow.submit(req, requested_by="ceo_agent")
        assert result.request.status == STATUS_PENDING
        assert result.request.execution_request_id == req.request_id
        assert result.request.intent_id == req.intent.intent_id
        assert result.request.action == ExecutionAction.PAUSE_CAMPAIGN
        assert result.request.requested_by == "ceo_agent"
        assert result.required_role == ApprovalRole.OPERATOR
        assert result.authorization is None
        # 已入库
        assert workflow.store.get(result.request.approval_id) is not None

    def test_submit_auto_approves_safe_action(self, workflow):
        req = _exec_request(
            action=ExecutionAction.DISABLE_NETWORK, risk=0.1, confidence=0.95
        )
        result = workflow.submit(req)
        assert result.auto_approved
        assert result.request.status == STATUS_APPROVED
        assert result.request.resolved_by == SYSTEM_APPROVER
        assert result.authorization is not None
        assert result.authorization.allows(ExecutionAction.DISABLE_NETWORK)

    def test_submit_admin_action_pending_at_admin(self, workflow):
        result = workflow.submit(_exec_request(action=ExecutionAction.CREATE_RELEASE))
        assert result.request.status == STATUS_PENDING
        assert result.required_role == ApprovalRole.ADMIN


class TestHumanDecision:
    def test_approve_transitions_and_returns_authorization(self, workflow):
        # 验收 ③：PENDING -> APPROVED
        result = workflow.submit(_exec_request())
        approval_id = result.request.approval_id
        auth = workflow.approve(approval_id, "ethan", ApprovalRole.OPERATOR)
        assert workflow.store.get(approval_id).status == STATUS_APPROVED
        assert auth.approval_id == approval_id
        assert auth.approved_by == "ethan"
        assert auth.allows(ExecutionAction.PAUSE_CAMPAIGN)

    def test_approve_denied_for_insufficient_role(self, workflow):
        # 验收 ②：OPERATOR 批 SCALE_BUDGET -> DENY
        result = workflow.submit(
            _exec_request(action=ExecutionAction.SCALE_BUDGET,
                          impact={"budget_delta": 0.2})
        )
        with pytest.raises(ApprovalWorkflowError):
            workflow.approve(result.request.approval_id, "op", ApprovalRole.OPERATOR)
        # 仍然 PENDING，未被污染
        assert workflow.store.get(result.request.approval_id).status == STATUS_PENDING

    def test_approve_missing_raises(self, workflow):
        with pytest.raises(ApprovalWorkflowError):
            workflow.approve("apr_nope", "ethan", ApprovalRole.ADMIN)

    def test_approve_twice_raises(self, workflow):
        result = workflow.submit(_exec_request())
        workflow.approve(result.request.approval_id, "ethan", ApprovalRole.OPERATOR)
        with pytest.raises(ApprovalWorkflowError):
            workflow.approve(result.request.approval_id, "ethan", ApprovalRole.ADMIN)

    def test_reject_with_reason(self, workflow):
        result = workflow.submit(_exec_request())
        rejected = workflow.reject(
            result.request.approval_id, "ethan", ApprovalRole.OPERATOR,
            reason="not now"
        )
        assert rejected.status == STATUS_REJECTED
        assert rejected.reason == "not now"

    def test_cancel(self, workflow):
        result = workflow.submit(_exec_request())
        cancelled = workflow.cancel(result.request.approval_id, by="system")
        assert cancelled.status == STATUS_CANCELLED

    def test_pending_queue(self, workflow):
        workflow.submit(_exec_request())
        workflow.submit(_exec_request(action=ExecutionAction.CREATE_RELEASE))
        assert len(workflow.pending()) == 2
