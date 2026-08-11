"""P2.4.1 SafeExecutionContext / RollbackCapability / RollbackPlan / SafeExecutionOutcome 模型测试。"""

import pytest

from src.execution.approval.models import ExecutionAuthorization
from src.execution.models import (
    ExecutionAction,
    ExecutionDomain,
    ExecutionIntent,
    ExecutionMode,
    ExecutionRequest,
)
from src.execution.safe_executor.models import (
    CTX_BLOCKED,
    CTX_CREATED,
    CTX_EXECUTING,
    CTX_FAILED,
    CTX_ROLLED_BACK,
    CTX_SUCCESS,
    CTX_VALIDATING,
    TERMINAL_CONTEXT_STATUSES,
    VALID_CONTEXT_STATUSES,
    VERDICT_BLOCKED,
    VERDICT_ESCALATED,
    VERDICT_EXECUTED,
    VERDICT_FAILED,
    VERDICT_RETURN_EXISTING,
    VERDICT_ROLLED_BACK,
    InvalidTransitionError,
    RollbackCapability,
    RollbackPlan,
    SafeExecutionContext,
    SafeExecutionOutcome,
)


def _intent():
    return ExecutionIntent(
        intent_id="int_1", decision_id="dec_1", domain=ExecutionDomain.UA,
        action=ExecutionAction.PAUSE_CAMPAIGN, target_id="p04", reason="r",
        confidence=0.8, expected_impact={"x": 1}, risk_level=0.4, requires_approval=True,
    )


def _request(mode=ExecutionMode.DRY_RUN, intent=None, auth=None):
    return ExecutionRequest(
        intent=intent or _intent(), request_id="req_1", mode=mode, authorization=auth
    )


class TestContextBasics:
    def test_default_status_and_history(self):
        ctx = SafeExecutionContext(request_id="r1", action="pause_campaign", target="p04")
        assert ctx.status == CTX_CREATED
        assert ctx.execution_id.startswith("exe_")
        assert ctx.started_at
        assert ctx.history[0][0] == CTX_CREATED

    def test_from_request_maps_fields(self):
        auth = ExecutionAuthorization(
            approval_id="apr_9", approved_by="ethan", allowed_action="pause_campaign"
        )
        ctx = SafeExecutionContext.from_request(_request(ExecutionMode.PRODUCTION, auth=auth))
        assert ctx.request_id == "req_1"
        assert ctx.action == "pause_campaign"
        assert ctx.target == "p04"
        assert ctx.mode == "production"
        assert ctx.authorization_id == "apr_9"
        assert abs(ctx.risk_score - 0.4) < 1e-6

    def test_invalid_status_raises(self):
        with pytest.raises(ValueError):
            SafeExecutionContext(request_id="r", action="a", target="t", status="BOGUS")

    def test_valid_statuses_complete(self):
        assert len(VALID_CONTEXT_STATUSES) == 9
        assert CTX_BLOCKED in VALID_CONTEXT_STATUSES

    def test_terminal_set(self):
        assert CTX_SUCCESS in TERMINAL_CONTEXT_STATUSES
        assert CTX_FAILED in TERMINAL_CONTEXT_STATUSES
        assert CTX_ROLLED_BACK in TERMINAL_CONTEXT_STATUSES
        assert CTX_BLOCKED in TERMINAL_CONTEXT_STATUSES
        assert CTX_CREATED not in TERMINAL_CONTEXT_STATUSES


class TestContextStateMachine:
    def test_valid_transition(self):
        ctx = SafeExecutionContext(request_id="r", action="a", target="t")
        ctx.transition(CTX_VALIDATING)
        assert ctx.status == CTX_VALIDATING
        assert ctx.history[-1][0] == CTX_VALIDATING

    def test_terminal_no_further_transition(self):
        ctx = SafeExecutionContext(request_id="r", action="a", target="t")
        ctx.transition(CTX_VALIDATING)
        ctx.transition(CTX_SUCCESS)
        assert ctx.is_terminal
        with pytest.raises(InvalidTransitionError):
            ctx.transition(CTX_FAILED)

    def test_invalid_transition_raises(self):
        ctx = SafeExecutionContext(request_id="r", action="a", target="t")
        with pytest.raises(InvalidTransitionError):
            ctx.transition(CTX_EXECUTING)  # CREATED -> EXECUTING illegal

    def test_terminal_sets_finished_at(self):
        ctx = SafeExecutionContext(request_id="r", action="a", target="t")
        ctx.transition(CTX_VALIDATING)
        ctx.transition(CTX_SUCCESS)
        assert ctx.finished_at
        assert ctx.history[-1][0] == CTX_SUCCESS

    def test_created_to_blocked_allowed(self):
        ctx = SafeExecutionContext(request_id="r", action="a", target="t")
        ctx.transition(CTX_BLOCKED, "rule 1")
        assert ctx.status == CTX_BLOCKED
        assert ctx.reason == "rule 1"
        assert ctx.is_terminal

    def test_is_production(self):
        ctx = SafeExecutionContext(request_id="r", action="a", target="t", mode="production")
        assert ctx.is_production
        ctx2 = SafeExecutionContext(request_id="r", action="a", target="t", mode="dry_run")
        assert not ctx2.is_production


class TestContextSerialization:
    def test_roundtrip(self):
        ctx = SafeExecutionContext(
            request_id="r1", action=ExecutionAction.PAUSE_CAMPAIGN, target="p04",
            mode="production", risk_score=0.42, authorization_id="apr_x",
            before_state={"a": 1}, after_state={"b": 2}, reason="ok",
        )
        ctx.transition(CTX_VALIDATING)
        ctx.transition(CTX_SUCCESS)
        restored = SafeExecutionContext.from_dict(ctx.to_dict())
        assert restored.request_id == "r1"
        assert restored.action == "pause_campaign"
        assert restored.target == "p04"
        assert restored.mode == "production"
        assert abs(restored.risk_score - 0.42) < 1e-6
        assert restored.authorization_id == "apr_x"
        assert restored.status == CTX_SUCCESS
        assert restored.before_state == {"a": 1}
        assert restored.after_state == {"b": 2}
        assert restored.history[0][0] == CTX_CREATED
        assert restored.history[-1][0] == CTX_SUCCESS

    def test_action_roundtrip_preserves_value(self):
        ctx = SafeExecutionContext(
            request_id="r", action=ExecutionAction.DISABLE_NETWORK, target="t"
        )
        assert ctx.to_dict()["action"] == "disable_network"
        restored = SafeExecutionContext.from_dict(ctx.to_dict())
        assert restored.action == "disable_network"


class TestRollbackCapability:
    def test_matches(self):
        cap = RollbackCapability(
            provider="max", original_action="disable_network", rollback_action="enable_network"
        )
        assert cap.matches("max", "disable_network")
        assert cap.matches("max", ExecutionAction.DISABLE_NETWORK)
        assert not cap.matches("meta", "disable_network")
        assert not cap.matches("max", "pause_campaign")

    def test_to_dict(self):
        cap = RollbackCapability(
            provider="meta", original_action="pause_campaign", rollback_action="active_campaign"
        )
        d = cap.to_dict()
        assert d == {
            "provider": "meta",
            "original_action": "pause_campaign",
            "rollback_action": "active_campaign",
            "description": "",
        }


class TestRollbackPlan:
    def test_defaults(self):
        plan = RollbackPlan(
            original_action="disable_network", rollback_action="enable_network",
            snapshot={"s": 1}, provider="max",
        )
        assert plan.plan_id.startswith("rbp_")
        assert plan.created_at
        assert plan.original_action == "disable_network"
        assert plan.rollback_action == "enable_network"

    def test_action_as_enum_normalized(self):
        plan = RollbackPlan(
            original_action=ExecutionAction.DISABLE_NETWORK, rollback_action="enable_network",
            snapshot={}, provider="max",
        )
        assert plan.original_action == "disable_network"

    def test_roundtrip(self):
        plan = RollbackPlan(
            original_action="disable_network", rollback_action="enable_network",
            snapshot={"s": 1}, provider="max", target="p04", execution_id="exe_1",
        )
        restored = RollbackPlan.from_dict(plan.to_dict())
        assert restored.original_action == "disable_network"
        assert restored.snapshot == {"s": 1}
        assert restored.target == "p04"
        assert restored.execution_id == "exe_1"


class TestSafeExecutionOutcome:
    def _ctx(self):
        return SafeExecutionContext(request_id="r", action="a", target="t")

    def test_ok_for_executed(self):
        out = SafeExecutionOutcome(context=self._ctx(), verdict=VERDICT_EXECUTED)
        assert out.ok

    def test_ok_for_return_existing(self):
        out = SafeExecutionOutcome(context=self._ctx(), verdict=VERDICT_RETURN_EXISTING)
        assert out.ok

    def test_not_ok_for_blocked(self):
        out = SafeExecutionOutcome(context=self._ctx(), verdict=VERDICT_BLOCKED)
        assert not out.ok

    def test_invalid_verdict_raises(self):
        with pytest.raises(ValueError):
            SafeExecutionOutcome(context=self._ctx(), verdict="BOGUS")

    def test_escalated_flag(self):
        out = SafeExecutionOutcome(
            context=self._ctx(), verdict=VERDICT_ESCALATED, escalated=True
        )
        assert out.escalated
        assert out.verdict == VERDICT_ESCALATED

    def test_rolled_back_verdict(self):
        out = SafeExecutionOutcome(context=self._ctx(), verdict=VERDICT_ROLLED_BACK)
        assert out.verdict == VERDICT_ROLLED_BACK
        assert not out.ok

    def test_failed_verdict(self):
        out = SafeExecutionOutcome(context=self._ctx(), verdict=VERDICT_FAILED)
        assert out.verdict == VERDICT_FAILED
        assert not out.ok

    def test_to_dict_roundtrip(self):
        ctx = SafeExecutionContext(request_id="r", action="a", target="t")
        ctx.transition(CTX_VALIDATING)
        ctx.transition(CTX_SUCCESS)
        out = SafeExecutionOutcome(
            context=ctx, verdict=VERDICT_EXECUTED, rollback={"k": "v"}
        )
        d = out.to_dict()
        assert d["verdict"] == VERDICT_EXECUTED
        assert d["context"]["status"] == CTX_SUCCESS
        assert d["rollback"] == {"k": "v"}
