"""P2.4.5 Execution Sandbox 测试：Rule 1~3 闸门 + Post Verify。"""

import pytest

from src.execution.approval.models import ExecutionAuthorization
from src.execution.models import (
    ExecutionAction,
    ExecutionDomain,
    ExecutionIntent,
    ExecutionMode,
    ExecutionRequest,
)
from src.execution.providers.result import STATUS_BLOCKED, STATUS_FAILED, STATUS_SUCCESS, STATUS_DRY_RUN
from src.execution.safe_executor.idempotency import (
    IDEM_ROLLED_BACK,
    IDEM_RUNNING,
    IDEM_SUCCESS,
    IdempotencyRecord,
    InMemoryIdempotencyStore,
    VERDICT_ALLOW,
    VERDICT_BLOCK_ROLLED_BACK,
    VERDICT_REJECT_RUNNING,
    VERDICT_RETURN_EXISTING,
    check_idempotency,
)
from src.execution.safe_executor.rollback import RollbackResult, RB_ESCALATED
from src.execution.safe_executor.sandbox import (
    DEFAULT_RISK_BLOCK_THRESHOLD,
    ExecutionSandbox,
    GateCheck,
)


def _intent(action=ExecutionAction.DISABLE_NETWORK, risk=0.3):
    return ExecutionIntent(
        intent_id="i", decision_id="d", domain=ExecutionDomain.AD_MONETIZATION,
        action=action, target_id="p04", reason="r", confidence=0.8,
        risk_level=risk, requires_approval=True,
    )


def _req(mode=ExecutionMode.DRY_RUN, intent=None, auth=None):
    return ExecutionRequest(intent=intent or _intent(), mode=mode, authorization=auth)


class TestGateCheck:
    def test_to_dict(self):
        g = GateCheck(True, "authorization", "ok")
        assert g.to_dict() == {"ok": True, "gate": "authorization", "reason": "ok", "verdict": ""}


class TestRule1Authorization:
    def test_non_production_passes(self):
        sb = ExecutionSandbox()
        assert sb.check_authorization(_req(ExecutionMode.DRY_RUN)).ok
        assert sb.check_authorization(_req(ExecutionMode.SIMULATION)).ok

    def test_production_missing_auth_blocks(self):
        sb = ExecutionSandbox()
        g = sb.check_authorization(_req(ExecutionMode.PRODUCTION))
        assert not g.ok
        assert "Rule 1" in g.reason

    def test_production_action_mismatch_blocks(self):
        sb = ExecutionSandbox()
        auth = ExecutionAuthorization(
            approval_id="apr", approved_by="ethan", allowed_action="pause_campaign"
        )
        g = sb.check_authorization(_req(ExecutionMode.PRODUCTION, auth=auth))
        assert not g.ok

    def test_production_expired_blocks(self):
        sb = ExecutionSandbox()
        auth = ExecutionAuthorization(
            approval_id="apr", approved_by="ethan", allowed_action="disable_network",
            approved_at="2026-07-01T00:00:00Z", expires_at="2026-07-02T00:00:00Z",
        )
        g = sb.check_authorization(_req(ExecutionMode.PRODUCTION, auth=auth))
        assert not g.ok
        assert "过期" in g.reason

    def test_production_valid_passes(self):
        sb = ExecutionSandbox()
        auth = ExecutionAuthorization(
            approval_id="apr", approved_by="ethan", allowed_action="disable_network"
        )
        g = sb.check_authorization(_req(ExecutionMode.PRODUCTION, auth=auth))
        assert g.ok


class TestRiskGate:
    def test_production_high_risk_blocks(self):
        sb = ExecutionSandbox()
        auth = ExecutionAuthorization(
            approval_id="apr", approved_by="ethan", allowed_action="disable_network"
        )
        g = sb.check_authorization  # placeholder; use check_risk directly
        req = _req(ExecutionMode.PRODUCTION, intent=_intent(risk=0.95), auth=auth)
        assert not sb.check_risk(req).ok

    def test_production_low_risk_passes(self):
        sb = ExecutionSandbox()
        req = _req(ExecutionMode.PRODUCTION, intent=_intent(risk=0.5))
        assert sb.check_risk(req).ok

    def test_dry_run_high_risk_passes(self):
        sb = ExecutionSandbox()
        req = _req(ExecutionMode.DRY_RUN, intent=_intent(risk=0.99))
        assert sb.check_risk(req).ok

    def test_threshold_default(self):
        assert DEFAULT_RISK_BLOCK_THRESHOLD == 0.9


class TestIdempotencyGate:
    def test_allow(self):
        sb = ExecutionSandbox()
        store = InMemoryIdempotencyStore()
        g, rec = sb.check_idempotency(store, "k")
        assert g.ok and rec is None and g.verdict == VERDICT_ALLOW

    def test_return_existing_ok(self):
        sb = ExecutionSandbox()
        store = InMemoryIdempotencyStore()
        store.put(IdempotencyRecord(key="k", execution_id="e1", status=IDEM_SUCCESS))
        g, rec = sb.check_idempotency(store, "k")
        assert g.ok and g.verdict == VERDICT_RETURN_EXISTING and rec is not None

    def test_reject_running_blocks(self):
        sb = ExecutionSandbox()
        store = InMemoryIdempotencyStore()
        store.put(IdempotencyRecord(key="k", execution_id="e1", status=IDEM_RUNNING))
        g, rec = sb.check_idempotency(store, "k")
        assert not g.ok and g.verdict == VERDICT_REJECT_RUNNING

    def test_block_rolled_back(self):
        sb = ExecutionSandbox()
        store = InMemoryIdempotencyStore()
        store.put(IdempotencyRecord(key="k", execution_id="e1", status=IDEM_ROLLED_BACK))
        g, rec = sb.check_idempotency(store, "k")
        assert not g.ok and g.verdict == VERDICT_BLOCK_ROLLED_BACK

    def test_no_store_skips(self):
        sb = ExecutionSandbox()
        g, rec = sb.check_idempotency(None, "k")
        assert g.ok and rec is None


class TestPostVerify:
    def _result(self, status, real=False):
        return type("R", (), {"status": status, "real_api_called": real, "error": "e"})()

    def test_none_fails(self):
        sb = ExecutionSandbox()
        assert not sb.post_verify(None).ok

    def test_failed_triggers_rule4(self):
        sb = ExecutionSandbox()
        g = sb.post_verify(self._result(STATUS_FAILED))
        assert not g.ok and g.verdict == "FAILED"

    def test_blocked_no_rollback(self):
        sb = ExecutionSandbox()
        g = sb.post_verify(self._result(STATUS_BLOCKED))
        assert not g.ok and g.verdict == "BLOCKED"

    def test_success_ok(self):
        sb = ExecutionSandbox()
        assert sb.post_verify(self._result(STATUS_SUCCESS)).ok

    def test_dry_run_ok(self):
        sb = ExecutionSandbox()
        assert sb.post_verify(self._result(STATUS_DRY_RUN)).ok
