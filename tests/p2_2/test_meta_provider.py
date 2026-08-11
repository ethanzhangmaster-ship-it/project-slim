"""P2.2：Meta Provider 执行纪律。

- DRY_RUN：real_api_called=False
- PRODUCTION + 已审批 + mock transport -> real_api_called=True
- PRODUCTION 传输失败 -> real_api_called=True（已真实尝试），status=failed
"""
from src.execution.models import ExecutionAction, ExecutionDomain, ExecutionMode
from src.execution.providers import MetaExecutionProvider
from src.execution.providers.result import STATUS_DRY_RUN, STATUS_SUCCESS

from .conftest import make_request


def _fake_transport(success=True):
    def _t(campaign_id, status):
        if success:
            return {"success": True, "data": {"campaign_id": campaign_id,
                                             "status": status}}
        return {"success": False, "error": "token expired"}
    return _t


def test_pause_campaign_dry_run_no_real_api():
    provider = MetaExecutionProvider(transport=_fake_transport())
    req = make_request(
        ExecutionAction.PAUSE_CAMPAIGN,
        mode=ExecutionMode.DRY_RUN,
        domain=ExecutionDomain.UA,
        expected_impact={"campaign_id": "camp_123"},
    )
    res = provider.execute(req)
    assert res.status == STATUS_DRY_RUN
    assert res.real_api_called is False


def test_pause_campaign_production_real_api_called():
    provider = MetaExecutionProvider(transport=_fake_transport())
    req = make_request(
        ExecutionAction.PAUSE_CAMPAIGN,
        mode=ExecutionMode.PRODUCTION,
        domain=ExecutionDomain.UA,
        expected_impact={"campaign_id": "camp_123"},
    )
    res = provider.execute(req)
    assert res.status == STATUS_SUCCESS
    assert res.real_api_called is True
    assert res.after_state["status"] == "PAUSED"


def test_pause_campaign_production_failure_marks_real():
    provider = MetaExecutionProvider(transport=_fake_transport(success=False))
    req = make_request(
        ExecutionAction.PAUSE_CAMPAIGN,
        mode=ExecutionMode.PRODUCTION,
        domain=ExecutionDomain.UA,
        expected_impact={"campaign_id": "camp_123"},
    )
    res = provider.execute(req)
    assert res.real_api_called is True
    assert res.status != STATUS_SUCCESS
    assert "token expired" in (res.error or "")
