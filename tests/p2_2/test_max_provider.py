"""P2.2 验收场景 3 + 5：MAX Provider 执行纪律。

场景 3：DRY_RUN 模式 real_api_called 必须 False。
场景 5：PRODUCTION + 已审批（DISABLE_NETWORK 在免审白名单）+ mock server
        -> 真正尝试外部 API -> real_api_called=True。
"""
from operation.providers.live.max.client import MaxClient

from src.execution.models import ExecutionAction, ExecutionMode
from src.execution.providers import MaxExecutionProvider
from src.execution.providers.result import STATUS_DRY_RUN, STATUS_SUCCESS

from .conftest import make_request


def _armed_client():
    """构造一个被 mock server 武装的 MaxClient（生产调用的唯一 seam）。"""
    client = MaxClient()
    client.arm_real_client(
        lambda method, endpoint, data: {
            "success": True,
            "data": {"method": method, "endpoint": endpoint},
        }
    )
    return client


def test_disable_network_dry_run_no_real_api():
    provider = MaxExecutionProvider()
    req = make_request(
        ExecutionAction.DISABLE_NETWORK,
        mode=ExecutionMode.DRY_RUN,
        expected_impact={"network": "adcolony", "ad_unit_id": "au_1"},
    )
    res = provider.execute(req)
    assert res.status == STATUS_DRY_RUN
    assert res.real_api_called is False
    assert res.after_state["intended_action"] == "disable_network"


def test_disable_network_production_real_api_called():
    provider = MaxExecutionProvider(client=_armed_client())
    req = make_request(
        ExecutionAction.DISABLE_NETWORK,
        mode=ExecutionMode.PRODUCTION,
        expected_impact={"network": "adcolony", "ad_unit_id": "au_1"},
    )
    res = provider.execute(req)
    assert res.status == STATUS_SUCCESS
    assert res.real_api_called is True
    assert res.after_state["action"] == "disable_network"


def test_update_waterfall_production_real_api_called():
    provider = MaxExecutionProvider(client=_armed_client())
    req = make_request(
        ExecutionAction.UPDATE_WATERFALL,
        mode=ExecutionMode.PRODUCTION,
        expected_impact={"ad_unit_id": "au_1", "networks": ["applovin", "google"]},
    )
    res = provider.execute(req)
    assert res.status == STATUS_SUCCESS
    assert res.real_api_called is True


def test_production_failure_reflects_real_api_called():
    client = MaxClient()
    client.arm_real_client(
        lambda method, endpoint, data: {"success": False, "error": "403 forbidden"}
    )
    provider = MaxExecutionProvider(client=client)
    req = make_request(
        ExecutionAction.DISABLE_NETWORK,
        mode=ExecutionMode.PRODUCTION,
        expected_impact={"network": "x", "ad_unit_id": "au_1"},
    )
    res = provider.execute(req)
    # 失败也要标记真实调用已发生（平台限制/拒绝也是真实响应）
    assert res.real_api_called is True
    assert res.status != STATUS_SUCCESS
    assert res.error
