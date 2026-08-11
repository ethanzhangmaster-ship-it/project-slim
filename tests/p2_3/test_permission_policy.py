"""P2.3.2 roles + P2.3.3 policy tests.

验收场景 ②：OPERATOR 试图批准 SCALE_BUDGET -> DENY。
"""

from src.execution.approval.policy import (
    ApprovalPolicy,
    OUTCOME_ADMIN,
    OUTCOME_AUTO,
    OUTCOME_MANUAL,
)
from src.execution.approval.roles import (
    ApprovalRole,
    minimum_role_for,
    role_can,
    role_level,
)
from src.execution.models import (
    ExecutionAction,
    ExecutionDomain,
    ExecutionIntent,
)


def _intent(action, risk=0.5, confidence=0.8, impact=None, domain=ExecutionDomain.UA):
    return ExecutionIntent(
        intent_id="",
        decision_id="dec_1",
        domain=domain,
        action=action,
        target_id="p04",
        reason="test",
        confidence=confidence,
        expected_impact=impact,
        risk_level=risk,
    )


class TestRoles:
    def test_role_levels_ascending(self):
        assert role_level(ApprovalRole.SYSTEM) < role_level(ApprovalRole.OPERATOR)
        assert role_level(ApprovalRole.OPERATOR) < role_level(ApprovalRole.MANAGER)
        assert role_level(ApprovalRole.MANAGER) < role_level(ApprovalRole.ADMIN)
        assert role_level("nobody") == -1

    def test_operator_allowed_actions(self):
        assert role_can(ApprovalRole.OPERATOR, ExecutionAction.DISABLE_NETWORK)
        assert role_can(ApprovalRole.OPERATOR, ExecutionAction.CREATE_INVESTIGATION)
        assert role_can(ApprovalRole.OPERATOR, ExecutionAction.PAUSE_CAMPAIGN)

    def test_operator_denied_scale_budget_and_release(self):
        # 验收 ②：OPERATOR + SCALE_BUDGET -> DENY
        assert not role_can(ApprovalRole.OPERATOR, ExecutionAction.SCALE_BUDGET)
        assert not role_can(ApprovalRole.OPERATOR, ExecutionAction.CREATE_RELEASE)

    def test_manager_can_scale_budget_but_not_release(self):
        assert role_can(ApprovalRole.MANAGER, ExecutionAction.SCALE_BUDGET)
        assert role_can(ApprovalRole.MANAGER, ExecutionAction.UPDATE_WATERFALL)
        assert not role_can(ApprovalRole.MANAGER, ExecutionAction.CREATE_RELEASE)

    def test_admin_can_everything(self):
        for action in ExecutionAction:
            assert role_can(ApprovalRole.ADMIN, action)

    def test_unknown_role_denied(self):
        assert not role_can("INTERN", ExecutionAction.PAUSE_CAMPAIGN)

    def test_minimum_role_for(self):
        assert minimum_role_for(ExecutionAction.DISABLE_NETWORK) == ApprovalRole.SYSTEM
        assert minimum_role_for(ExecutionAction.PAUSE_CAMPAIGN) == ApprovalRole.OPERATOR
        assert minimum_role_for(ExecutionAction.SCALE_BUDGET) == ApprovalRole.MANAGER
        assert minimum_role_for(ExecutionAction.CREATE_RELEASE) == ApprovalRole.ADMIN
        assert minimum_role_for("nonsense") == ""


class TestPolicy:
    def setup_method(self):
        self.policy = ApprovalPolicy()

    def test_auto_approve_low_risk_disable_network(self):
        decision = self.policy.evaluate(
            _intent(ExecutionAction.DISABLE_NETWORK, risk=0.1, confidence=0.95)
        )
        assert decision.outcome == OUTCOME_AUTO
        assert decision.auto_approved
        assert decision.required_role == ApprovalRole.SYSTEM

    def test_disable_network_high_risk_needs_human(self):
        decision = self.policy.evaluate(
            _intent(ExecutionAction.DISABLE_NETWORK, risk=0.5, confidence=0.95)
        )
        assert decision.outcome == OUTCOME_MANUAL
        assert not decision.auto_approved

    def test_disable_network_low_confidence_needs_human(self):
        decision = self.policy.evaluate(
            _intent(ExecutionAction.DISABLE_NETWORK, risk=0.1, confidence=0.5)
        )
        assert decision.outcome == OUTCOME_MANUAL

    def test_pause_campaign_always_manual(self):
        decision = self.policy.evaluate(
            _intent(ExecutionAction.PAUSE_CAMPAIGN, risk=0.1, confidence=0.99)
        )
        assert decision.outcome == OUTCOME_MANUAL
        assert decision.required_role == ApprovalRole.OPERATOR

    def test_scale_budget_manual_at_manager(self):
        decision = self.policy.evaluate(
            _intent(ExecutionAction.SCALE_BUDGET, impact={"budget_delta": 0.2})
        )
        assert decision.outcome == OUTCOME_MANUAL
        assert decision.required_role == ApprovalRole.MANAGER

    def test_scale_budget_large_impact_escalates_admin(self):
        decision = self.policy.evaluate(
            _intent(ExecutionAction.SCALE_BUDGET, impact={"budget_delta": 0.9})
        )
        assert decision.outcome == OUTCOME_ADMIN
        assert decision.required_role == ApprovalRole.ADMIN

    def test_create_release_always_admin(self):
        decision = self.policy.evaluate(
            _intent(ExecutionAction.CREATE_RELEASE, risk=0.05, confidence=0.99)
        )
        assert decision.outcome == OUTCOME_ADMIN

    def test_can_role_approve_combined(self):
        intent = _intent(ExecutionAction.SCALE_BUDGET, impact={"budget_delta": 0.2})
        assert not self.policy.can_role_approve(ApprovalRole.OPERATOR, intent)
        assert self.policy.can_role_approve(ApprovalRole.MANAGER, intent)
        # 大额升级 ADMIN 后 MANAGER 也不行
        big = _intent(ExecutionAction.SCALE_BUDGET, impact={"budget_delta": 0.9})
        assert not self.policy.can_role_approve(ApprovalRole.MANAGER, big)
        assert self.policy.can_role_approve(ApprovalRole.ADMIN, big)
