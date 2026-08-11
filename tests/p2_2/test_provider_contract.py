"""P2.2 验收场景 1：Provider 契约实现接口。

验证三个真实执行器（MAX / Meta / Play）都正确实现 ExecutionProvider Protocol：
- 暴露 provider_id 字符串属性
- 实现 can_execute(intent) -> bool
- 实现 execute(request) -> ExecutionResult
"""
import pytest
from typing import runtime_checkable

from src.execution.models import ExecutionAction, ExecutionMode
from src.execution.providers import (
    ExecutionProvider,
    MaxExecutionProvider,
    MetaExecutionProvider,
    PlayExecutionProvider,
)
from src.execution.providers.result import ExecutionResult

from .conftest import make_request


@pytest.mark.parametrize(
    "provider",
    [
        MaxExecutionProvider(),
        MetaExecutionProvider(),
        PlayExecutionProvider(),
    ],
)
def test_provider_exposes_id_and_is_protocol_instance(provider):
    # provider_id 必须是非空字符串
    assert isinstance(provider.provider_id, str) and provider.provider_id
    # 必须是 ExecutionProvider 的结构化实现（runtime_checkable 检查属性与方法）
    assert isinstance(provider, ExecutionProvider)


@pytest.mark.parametrize(
    "provider,action,expect",
    [
        (MaxExecutionProvider(), ExecutionAction.DISABLE_NETWORK, True),
        (MaxExecutionProvider(), ExecutionAction.PAUSE_CAMPAIGN, False),
        (MetaExecutionProvider(), ExecutionAction.PAUSE_CAMPAIGN, True),
        (MetaExecutionProvider(), ExecutionAction.DISABLE_NETWORK, False),
        (PlayExecutionProvider(), ExecutionAction.CREATE_RELEASE, True),
        (PlayExecutionProvider(), ExecutionAction.PAUSE_CAMPAIGN, False),
    ],
)
def test_can_execute_routing(provider, action, expect):
    req = make_request(action)
    assert provider.can_execute(req.intent) is expect


@pytest.mark.parametrize(
    "provider,action",
    [
        (MaxExecutionProvider(), ExecutionAction.DISABLE_NETWORK),
        (MetaExecutionProvider(), ExecutionAction.PAUSE_CAMPAIGN),
        (PlayExecutionProvider(), ExecutionAction.CREATE_RELEASE),
    ],
)
def test_execute_returns_execution_result(provider, action):
    req = make_request(action, mode=ExecutionMode.DRY_RUN)
    res = provider.execute(req)
    assert isinstance(res, ExecutionResult)
    assert res.request_id == req.request_id
    assert res.provider == provider.provider_id
