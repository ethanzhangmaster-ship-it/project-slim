"""P2.2 验收场景 2 + 6：Provider Router 路由正确性。

场景 2：DISABLE_NETWORK -> 路由到 MAXProvider。
场景 6：未知动作（注册表里没有）-> 无 Provider -> BLOCK。
"""
from src.execution.models import ExecutionAction, ExecutionDomain, ExecutionMode
from src.execution.providers import (
    ProviderRouter,
    build_default_registry,
    build_default_providers,
)
from src.execution.providers.result import STATUS_BLOCKED

from .conftest import make_request


def _router():
    reg = build_default_registry()
    providers = build_default_providers()
    return ProviderRouter(reg, providers)


def test_disable_network_routes_to_max():
    router = _router()
    req = make_request(ExecutionAction.DISABLE_NETWORK, mode=ExecutionMode.DRY_RUN)
    res = router.route(req)
    assert res.provider == "max"
    assert res.status != STATUS_BLOCKED


def test_pause_campaign_routes_to_meta():
    router = _router()
    req = make_request(
        ExecutionAction.PAUSE_CAMPAIGN,
        mode=ExecutionMode.DRY_RUN,
        domain=ExecutionDomain.UA,
    )
    res = router.route(req)
    assert res.provider == "meta"
    assert res.status != STATUS_BLOCKED


def test_create_release_routes_to_play():
    router = _router()
    req = make_request(
        ExecutionAction.CREATE_RELEASE,
        mode=ExecutionMode.DRY_RUN,
        domain=ExecutionDomain.RELEASE,
    )
    res = router.route(req)
    assert res.provider == "play"
    assert res.status != STATUS_BLOCKED


def test_unknown_action_blocks_no_provider():
    router = _router()
    # SCALE_BUDGET 未在默认注册表登记 -> 无 Provider
    req = make_request(
        ExecutionAction.SCALE_BUDGET,
        mode=ExecutionMode.DRY_RUN,
        domain=ExecutionDomain.UA,
    )
    res = router.route(req)
    assert res.status == STATUS_BLOCKED
    assert res.real_api_called is False
    assert "未知动作" in (res.error or "")
