"""P2.3.6/P2.3.7 集成测试 — Router x AuthorizationGate x Provider 全链。

用户验收 6 场景：
① ExecutionRequest -> ApprovalRequest 创建 PASS（见 workflow 测试，此处链上复验）
② OPERATOR + SCALE_BUDGET -> DENY
③ 审批通过 -> PENDING -> APPROVED
④ 未审批 PRODUCTION 执行 -> BLOCK（Rule 1）
⑤ APPROVED -> Provider 执行 -> SUCCESS
⑥ 越权执行（批准 A 执行 B）-> BLOCK（Rule 2）
外加：Rule 3 过期 BLOCK、Rule 4 重放 BLOCK、DRY_RUN 不需要授权。
"""

import pytest

from src.execution.approval import (
    ApprovalRole,
    ApprovalService,
    ApprovalWorkflowError,
    AuthorizationGate,
    ExecutionAuthorization,
    InMemoryApprovalStore,
    STATUS_APPROVED,
    STATUS_PENDING,
)
from src.execution.models import (
    ExecutionAction,
    ExecutionDomain,
    ExecutionIntent,
    ExecutionMode,
    ExecutionRequest,
)
from src.execution.providers import (
    MetaExecutionProvider,
    STATUS_BLOCKED,
    STATUS_DRY_RUN,
    STATUS_SUCCESS,
    build_execution_router,
)


def _exec_request(action=ExecutionAction.PAUSE_CAMPAIGN, mode=ExecutionMode.PRODUCTION,
                  risk=0.5, confidence=0.8, impact=None):
    intent = ExecutionIntent(
        intent_id="",
        decision_id="dec_1",
        domain=ExecutionDomain.UA,
        action=action,
        target_id="p04_campaign",
        reason="integration test",
        confidence=confidence,
        expected_impact=impact,
        risk_level=risk,
    )
    return ExecutionRequest(intent=intent, mode=mode)


def _fake_transport(campaign_id, status):
    return {"success": True, "campaign_id": campaign_id, "status": status}


@pytest.fixture
def service():
    """共享一个 store 的 service + router（meta transport 注入 fake）。"""
    store = InMemoryApprovalStore()
    svc = ApprovalService(store=store)
    router = build_execution_router(
        authorization_gate=svc.gate,
        meta_kwargs={"transport": _fake_transport},
    )
    svc.router = router
    return svc


class TestFullChain:
    def test_scenario_1_submit_creates_approval(self, service):
        req = _exec_request()
        result = service.submit(req, requested_by="ceo_agent")
        assert result.request.status == STATUS_PENDING
        assert result.request.execution_request_id == req.request_id

    def test_scenario_2_operator_cannot_approve_scale_budget(self, service):
        req = _exec_request(action=ExecutionAction.SCALE_BUDGET,
                            impact={"budget_delta": 0.2})
        result = service.submit(req)
        with pytest.raises(ApprovalWorkflowError):
            service.approve(result.request.approval_id, "op", ApprovalRole.OPERATOR)

    def test_scenario_3_pending_to_approved(self, service):
        result = service.submit(_exec_request())
        auth = service.approve(
            result.request.approval_id, "ethan", ApprovalRole.OPERATOR
        )
        assert service.store.get(result.request.approval_id).status == STATUS_APPROVED
        assert auth.allows(ExecutionAction.PAUSE_CAMPAIGN)

    def test_scenario_4_unapproved_production_blocked(self, service):
        # Rule 1：未带 authorization 的 PRODUCTION -> BLOCK
        req = _exec_request()
        service.submit(req)  # 只提交，不批准
        result = service.execute(req)
        assert result.status == STATUS_BLOCKED
        assert not result.real_api_called
        assert "Rule1" in (result.error or "")

    def test_scenario_5_approved_executes_success(self, service):
        req = _exec_request()
        submit = service.submit(req)
        auth = service.approve(
            submit.request.approval_id, "ethan", ApprovalRole.OPERATOR
        )
        service.authorize(req, auth)
        result = service.execute(req)
        assert result.status == STATUS_SUCCESS
        assert result.real_api_called  # PRODUCTION 真调（fake transport）
        assert result.provider == "meta"

    def test_scenario_6_action_mismatch_blocked(self, service):
        # Rule 2：批准 DISABLE_NETWORK 却执行 PAUSE_CAMPAIGN -> BLOCK
        req = _exec_request(action=ExecutionAction.PAUSE_CAMPAIGN)
        service.submit(req)
        wrong_auth = ExecutionAuthorization(
            approval_id="apr_other",
            approved_by="ethan",
            allowed_action=ExecutionAction.DISABLE_NETWORK,
        )
        service.authorize(req, wrong_auth)
        result = service.execute(req)
        assert result.status == STATUS_BLOCKED
        assert "Rule2" in (result.error or "")


class TestSecurityRules:
    def test_rule3_expired_authorization_blocked(self, service):
        req = _exec_request()
        submit = service.submit(req)
        auth = service.approve(
            submit.request.approval_id, "ethan", ApprovalRole.OPERATOR
        )
        # 手动做过期令牌
        auth.expires_at = "2000-01-01T00:00:00Z"
        service.authorize(req, auth)
        result = service.execute(req)
        assert result.status == STATUS_BLOCKED
        assert "Rule3" in (result.error or "")

    def test_rule4_replay_blocked(self, service):
        req = _exec_request()
        submit = service.submit(req)
        auth = service.approve(
            submit.request.approval_id, "ethan", ApprovalRole.OPERATOR
        )
        service.authorize(req, auth)
        first = service.execute(req)
        assert first.status == STATUS_SUCCESS
        # 同一 approval_id 重放 -> Rule 4 BLOCK
        replay = _exec_request()
        service.authorize(replay, auth)
        second = service.execute(replay)
        assert second.status == STATUS_BLOCKED
        assert "Rule4" in (second.error or "")

    def test_forged_authorization_without_record_blocked(self, service):
        # 伪造令牌：store 里根本没有该 approval -> BLOCK
        req = _exec_request()
        forged = ExecutionAuthorization(
            approval_id="apr_forged",
            approved_by="attacker",
            allowed_action=ExecutionAction.PAUSE_CAMPAIGN,
        )
        service.authorize(req, forged)
        result = service.execute(req)
        assert result.status == STATUS_BLOCKED

    def test_pending_not_approved_authorization_blocked(self, service):
        # 令牌指向仍 PENDING 的 approval -> BLOCK
        req = _exec_request()
        submit = service.submit(req)
        fake_auth = ExecutionAuthorization(
            approval_id=submit.request.approval_id,
            approved_by="attacker",
            allowed_action=ExecutionAction.PAUSE_CAMPAIGN,
        )
        service.authorize(req, fake_auth)
        result = service.execute(req)
        assert result.status == STATUS_BLOCKED


class TestModesAndCompat:
    def test_dry_run_needs_no_authorization(self, service):
        req = _exec_request(mode=ExecutionMode.DRY_RUN)
        result = service.execute(req)
        assert result.status == STATUS_DRY_RUN
        assert not result.real_api_called

    def test_gate_passthrough_non_production(self):
        gate = AuthorizationGate(store=InMemoryApprovalStore())
        ok, _ = gate.check(_exec_request(mode=ExecutionMode.SIMULATION))
        assert ok

    def test_auto_approved_action_executes_directly(self, service):
        # 策略自动批准（DISABLE_NETWORK 低风险高置信）-> 提交即拿到令牌
        req = _exec_request(
            action=ExecutionAction.DISABLE_NETWORK, risk=0.1, confidence=0.95
        )
        submit = service.submit(req)
        assert submit.auto_approved
        assert req.authorization is not None
        result = service.execute(req)
        # max provider 无 client 时 PRODUCTION 真调会失败/回退，但授权门必须已放行
        assert "Rule" not in (result.error or "")

    def test_request_roundtrip_with_authorization(self):
        req = _exec_request()
        req.authorization = ExecutionAuthorization(
            approval_id="apr_1",
            approved_by="ethan",
            allowed_action=ExecutionAction.PAUSE_CAMPAIGN,
        )
        restored = ExecutionRequest.from_dict(req.to_dict())
        assert restored.authorization is not None
        assert restored.authorization.approval_id == "apr_1"
        assert restored.authorization.allows(ExecutionAction.PAUSE_CAMPAIGN)

    def test_legacy_router_without_gate_still_works(self):
        # 向后兼容：不注入 authorization_gate 时走 P2.2 ProductionApprovalGate
        router = build_execution_router(meta_kwargs={"transport": _fake_transport})
        req = _exec_request()  # PRODUCTION 未审批
        result = router.route(req)
        assert result.status == STATUS_BLOCKED
