"""P2.4 Safe Executor 测试 fixtures。

集中构造 P2.1 ExecutionRequest / P2.3 ExecutionAuthorization / P2.2 Provider 子类，
供 P2.4 各层（models / idempotency / snapshot / rollback / sandbox / executor /
integration）复用，避免每个测试文件重复样板。
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Dict, Optional

import pytest

from src.execution.approval.models import ExecutionAuthorization
from src.execution.models import (
    ExecutionAction,
    ExecutionDomain,
    ExecutionIntent,
    ExecutionMode,
    ExecutionRequest,
)
from src.execution.providers.base import BaseExecutionProvider
from src.execution.providers.result import (
    STATUS_BLOCKED,
    STATUS_DRY_RUN,
    STATUS_FAILED,
    STATUS_SUCCESS,
    ExecutionResult,
)
from src.execution.safe_executor import (
    ExecutionAuditLogger,
    InMemoryIdempotencyStore,
    InMemorySnapshotStore,
    RollbackEngine,
)


# ---------------------------------------------------------------------------
# P2.1 Intent / Request builders
# ---------------------------------------------------------------------------

def make_intent(
    action: ExecutionAction = ExecutionAction.DISABLE_NETWORK,
    target: str = "p04",
    risk_level: float = 0.3,
    expected_impact: Optional[Dict[str, Any]] = None,
    domain: ExecutionDomain = ExecutionDomain.AD_MONETIZATION,
):
    return ExecutionIntent(
        intent_id="int_test",
        decision_id="dec_test",
        domain=domain,
        action=action,
        target_id=target,
        reason="test intent",
        confidence=0.9,
        expected_impact=expected_impact if expected_impact is not None else {"budget": 100},
        risk_level=risk_level,
        requires_approval=True,
    )


def make_auth(allowed_action: ExecutionAction = ExecutionAction.DISABLE_NETWORK):
    return ExecutionAuthorization(
        approval_id="apr_test",
        approved_by="ethan",
        allowed_action=allowed_action.value,
    )


def make_request(
    mode: ExecutionMode = ExecutionMode.DRY_RUN,
    intent: Optional[ExecutionIntent] = None,
    authorization: Optional[ExecutionAuthorization] = None,
):
    return ExecutionRequest(
        intent=intent or make_intent(),
        request_id="req_test",
        mode=mode,
        authorization=authorization,
    )


# ---------------------------------------------------------------------------
# P2.2 Provider 子类
# ---------------------------------------------------------------------------

class MaxProvider(BaseExecutionProvider):
    provider_id = "max"
    supported_actions = (ExecutionAction.DISABLE_NETWORK,)

    def _do_real(self, request):
        return self._ok(request, after_state={"network": "disabled"})


class FailingRollbackProvider(MaxProvider):
    """rollback 返回失败（Rule 5 -> ESCALATE）。"""

    def rollback(self, plan):
        return {"success": False, "error": "restore rejected by upstream"}


class RaisingRollbackProvider(MaxProvider):
    """rollback 抛异常（Rule 5 -> ESCALATE）。"""

    def rollback(self, plan):
        raise RuntimeError("rollback exploded")


class PlainProvider:
    """没有 rollback 方法的 Provider（回滚引擎应判 ESCALATED）。"""

    provider_id = "max"

    def snapshot_state(self, request):
        return {"provider": "max", "ok": True}

    def execute(self, request):
        return ExecutionResult(
            request_id=request.request_id,
            provider="max",
            status=STATUS_FAILED,
            real_api_called=True,
            error="boom",
        )


class BadSnapshotProvider:
    """snapshot_state 抛异常 -> SnapshotError（Rule 3 -> BLOCK）。"""

    provider_id = "max"

    def snapshot_state(self, request):
        raise RuntimeError("cannot read external state")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mem_idem():
    return InMemoryIdempotencyStore()


@pytest.fixture
def mem_snap():
    return InMemorySnapshotStore()


@pytest.fixture
def tmp_audit(tmp_path):
    return ExecutionAuditLogger(audit_dir=str(tmp_path / "audit"))


@pytest.fixture
def max_provider():
    return MaxProvider()


@pytest.fixture
def intent_disable():
    return make_intent(action=ExecutionAction.DISABLE_NETWORK, target="p04", risk_level=0.3)


@pytest.fixture
def auth_valid():
    return make_auth(ExecutionAction.DISABLE_NETWORK)


@pytest.fixture
def request_dry(intent_disable):
    return make_request(mode=ExecutionMode.DRY_RUN, intent=intent_disable)


@pytest.fixture
def request_prod(intent_disable, auth_valid):
    return make_request(
        mode=ExecutionMode.PRODUCTION,
        intent=intent_disable,
        authorization=auth_valid,
    )


@pytest.fixture
def rollback_engine():
    return RollbackEngine()


# ---------------------------------------------------------------------------
# 仅供集成测试的假 Router（验证 build_safe_executor 工厂 + resolver 路径）
# ---------------------------------------------------------------------------

class FakeRouter:
    def __init__(self, provider):
        self._provider = provider
        self.registry = SimpleNamespace(
            providers_for=lambda action: ["max"]
        )
        self.providers = {"max": provider}

    def route(self, request):
        return self._provider.execute(request)


__all__ = [
    "make_intent",
    "make_auth",
    "make_request",
    "MaxProvider",
    "FailingRollbackProvider",
    "RaisingRollbackProvider",
    "PlainProvider",
    "BadSnapshotProvider",
    "FakeRouter",
]
