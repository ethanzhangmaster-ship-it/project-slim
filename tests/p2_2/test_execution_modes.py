"""P2.2 验收场景 4 + 5 + P1.7 真实审计门 + P2.1->P2.2 全链集成。

场景 4：PRODUCTION 模式、未审批的动作 -> BLOCKED（无法执行）。
场景 5：PRODUCTION + 已审批（或免审白名单）+ mock server -> real_api_called=True。
P1.7  ：单游戏 RealityScore < 0.5 -> 即使生产审批通过也被 BLOCK。
集成   ：P2.1 build_contract(GrowthDecision) -> ExecutionRequest -> ProviderRouter。
"""
from operation.providers.live.max.client import MaxClient

from src.ceo_intelligence.decision_engine.models import DecisionType, GrowthDecision
from src.execution.models import ExecutionAction, ExecutionDomain, ExecutionMode
from src.execution.providers import (
    InMemoryApprovalStore,
    P1_7RealityGate,
    ProductionApprovalGate,
    ProviderRouter,
    build_default_providers,
    build_default_registry,
    build_execution_router,
)
from src.execution.providers.result import STATUS_BLOCKED, STATUS_SUCCESS

from .conftest import make_request


def _armed_client():
    client = MaxClient()
    client.arm_real_client(
        lambda method, endpoint, data: {"success": True, "data": {}}
    )
    return client


def _fake_meta_transport():
    def _t(campaign_id, status):
        return {"success": True, "data": {"campaign_id": campaign_id,
                                         "status": status}}
    return _t


# --------------------------------------------------------------------------- #
# 场景 4：PRODUCTION 未审批 -> BLOCKED
# --------------------------------------------------------------------------- #
def test_production_pause_without_approval_blocked():
    reg = build_default_registry()
    providers = build_default_providers(meta_kwargs={"transport": _fake_meta_transport()})
    gate = ProductionApprovalGate(store=InMemoryApprovalStore())
    router = ProviderRouter(reg, providers, approval_gate=gate)

    req = make_request(
        ExecutionAction.PAUSE_CAMPAIGN,
        mode=ExecutionMode.PRODUCTION,
        domain=ExecutionDomain.UA,
        expected_impact={"campaign_id": "camp_1"},
    )
    res = router.route(req)
    assert res.status == STATUS_BLOCKED
    assert res.real_api_called is False
    assert "审批" in (res.error or "")


# --------------------------------------------------------------------------- #
# 场景 5a：PRODUCTION + 免审白名单（DISABLE_NETWORK）+ mock -> real_api_called=True
# --------------------------------------------------------------------------- #
def test_production_disable_network_allowlisted_executes():
    router = build_execution_router(max_client=_armed_client())
    req = make_request(
        ExecutionAction.DISABLE_NETWORK,
        mode=ExecutionMode.PRODUCTION,
        expected_impact={"network": "adcolony", "ad_unit_id": "au_1"},
    )
    res = router.route(req)
    assert res.status == STATUS_SUCCESS
    assert res.real_api_called is True


# --------------------------------------------------------------------------- #
# 场景 5b：PRODUCTION + 已审批 PAUSE_CAMPAIGN + mock -> real_api_called=True
# --------------------------------------------------------------------------- #
def test_production_pause_with_approval_executes():
    reg = build_default_registry()
    providers = build_default_providers(meta_kwargs={"transport": _fake_meta_transport()})
    store = InMemoryApprovalStore()
    gate = ProductionApprovalGate(store=store)
    router = ProviderRouter(reg, providers, approval_gate=gate)

    req = make_request(
        ExecutionAction.PAUSE_CAMPAIGN,
        mode=ExecutionMode.PRODUCTION,
        domain=ExecutionDomain.UA,
        request_id="req_approve_1",
        expected_impact={"campaign_id": "camp_1"},
    )
    store.mark_approved(req.request_id)  # 模拟人工已审批
    res = router.route(req)
    assert res.status == STATUS_SUCCESS
    assert res.real_api_called is True


# --------------------------------------------------------------------------- #
# P1.7 真实审计门：低可信度 -> BLOCK（即使生产审批通过）
# --------------------------------------------------------------------------- #
def test_p1_7_reality_gate_blocks_low_score():
    # DISABLE_NETWORK 是免审白名单，但真实数据不足应被拦
    gate = P1_7RealityGate(scores={"p04_merge_witch": 0.3})
    router = build_execution_router(
        reality_gate=gate, max_client=_armed_client()
    )
    req = make_request(
        ExecutionAction.DISABLE_NETWORK,
        mode=ExecutionMode.PRODUCTION,
        expected_impact={"network": "adcolony", "ad_unit_id": "au_1"},
    )
    res = router.route(req)
    assert res.status == STATUS_BLOCKED
    assert res.real_api_called is False
    assert "RealityScore" in (res.error or "")


def test_p1_7_reality_gate_allows_high_score():
    gate = P1_7RealityGate(scores={"p04_merge_witch": 0.9})
    router = build_execution_router(
        reality_gate=gate, max_client=_armed_client()
    )
    req = make_request(
        ExecutionAction.DISABLE_NETWORK,
        mode=ExecutionMode.PRODUCTION,
        expected_impact={"network": "adcolony", "ad_unit_id": "au_1"},
    )
    res = router.route(req)
    assert res.real_api_called is True


# --------------------------------------------------------------------------- #
# 集成：P2.1 build_contract -> ExecutionRequest -> ProviderRouter
# --------------------------------------------------------------------------- #
def _decision(action: str, decision_type: DecisionType, risk: float = 0.2):
    return GrowthDecision(
        game_id="p04_merge_witch",
        opportunity_id="opp_1",
        action=action,
        decision_type=decision_type,
        expected_value=0.05,
        confidence=0.9,
        risk=risk,
        reason="integration test",
    )


def test_p2_1_to_p2_2_disable_network_full_chain():
    from src.execution.contracts import build_contract

    reg = build_default_registry()
    decision = _decision("MAX_OPTIMIZE", DecisionType.EXECUTE, risk=0.2)
    contract = build_contract(decision, registry=reg, mode=ExecutionMode.PRODUCTION)
    assert contract.request is not None

    router = build_execution_router(max_client=_armed_client())
    res = router.route(contract.request)
    assert res.real_api_called is True
    assert res.status == STATUS_SUCCESS


def test_p2_1_to_p2_2_pause_needs_approval_chain():
    from src.execution.contracts import build_contract

    reg = build_default_registry()
    decision = _decision("UA_STOP", DecisionType.EXECUTE, risk=0.2)
    contract = build_contract(decision, registry=reg, mode=ExecutionMode.PRODUCTION)
    assert contract.request is not None
    # 合同层已经标记为需审批
    assert contract.needs_approval

    providers = build_default_providers(meta_kwargs={"transport": _fake_meta_transport()})
    store = InMemoryApprovalStore()
    gate = ProductionApprovalGate(store=store)
    router = ProviderRouter(reg, providers, approval_gate=gate)
    res = router.route(contract.request)
    # 未审批 -> BLOCKED
    assert res.status == STATUS_BLOCKED

    store.mark_approved(contract.request.request_id)
    res2 = router.route(contract.request)
    assert res2.real_api_called is True
