"""P2.5 测试公共 fixture：构造各类 SafeExecutionOutcome 用于 7 类验收。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from src.execution.models import ExecutionAction, ExecutionIntent, ExecutionRequest
from src.execution.providers.result import (
    STATUS_BLOCKED,
    STATUS_DRY_RUN,
    STATUS_FAILED,
    STATUS_SUCCESS,
    ExecutionResult,
)
from src.execution.safe_executor.models import (
    CTX_BLOCKED,
    CTX_CREATED,
    CTX_EXECUTING,
    CTX_FAILED,
    CTX_ROLLED_BACK,
    CTX_SNAPSHOTTING,
    CTX_SUCCESS,
    CTX_VALIDATING,
    CTX_VERIFYING,
    VERDICT_BLOCKED,
    VERDICT_ESCALATED,
    VERDICT_EXECUTED,
    VERDICT_FAILED,
    VERDICT_RETURN_EXISTING,
    VERDICT_ROLLED_BACK,
    SafeExecutionContext,
    SafeExecutionOutcome,
)

BASE_TIME = datetime(2026, 7, 30, 12, 0, 0, tzinfo=timezone.utc)

# verdict -> (P2.4 状态时间线, context 终态, result 状态, real_api_called 默认)
_VERDICT_SHAPE = {
    VERDICT_EXECUTED: (
        [CTX_CREATED, CTX_VALIDATING, CTX_SNAPSHOTTING, CTX_EXECUTING, CTX_VERIFYING, CTX_SUCCESS],
        CTX_SUCCESS, STATUS_SUCCESS, True,
    ),
    VERDICT_RETURN_EXISTING: (
        [CTX_CREATED, CTX_VALIDATING, CTX_SUCCESS],
        CTX_SUCCESS, None, False,
    ),
    VERDICT_BLOCKED: (
        [CTX_CREATED, CTX_VALIDATING, CTX_BLOCKED],
        CTX_BLOCKED, None, False,
    ),
    VERDICT_FAILED: (
        [CTX_CREATED, CTX_VALIDATING, CTX_SNAPSHOTTING, CTX_EXECUTING, CTX_VERIFYING, CTX_FAILED],
        CTX_FAILED, STATUS_FAILED, True,
    ),
    VERDICT_ROLLED_BACK: (
        [CTX_CREATED, CTX_VALIDATING, CTX_SNAPSHOTTING, CTX_EXECUTING, CTX_VERIFYING, CTX_FAILED, CTX_ROLLED_BACK],
        CTX_ROLLED_BACK, STATUS_FAILED, True,
    ),
    VERDICT_ESCALATED: (
        [CTX_CREATED, CTX_VALIDATING, CTX_SNAPSHOTTING, CTX_EXECUTING, CTX_VERIFYING, CTX_FAILED],
        CTX_FAILED, STATUS_FAILED, True,
    ),
}


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def make_outcome(
    verdict,
    *,
    action="update_waterfall",
    target="merge_witch",
    provider="max",
    mode="production",
    real_api_called=None,
    latency_seconds=2.0,
    before_state=None,
    after_state=None,
    authorization_id="",
    error=None,
    intent_action=None,
    started_at: datetime = BASE_TIME,
):
    """构造一个贴近 P2.4 真实产出的 SafeExecutionOutcome。"""
    shape = _VERDICT_SHAPE[verdict]
    timeline, ctx_status, result_status, real_default = shape
    real_api_called = real_default if real_api_called is None else real_api_called

    ctx = SafeExecutionContext(
        request_id="req_x",
        action=action,
        target=target,
        mode=mode,
        authorization_id=authorization_id,
    )
    # 覆盖状态时间线 + 终态 + 结束时间
    ctx.status = ctx_status
    ctx.history = [(s, _iso(started_at)) for s in timeline]
    ctx.finished_at = _iso(started_at + timedelta(seconds=latency_seconds))
    ctx.started_at = _iso(started_at)
    ctx.before_state = before_state or {}
    ctx.after_state = after_state or {}

    result = None
    if result_status is not None:
        result = ExecutionResult(
            request_id="req_x",
            provider=provider,
            status=result_status,
            real_api_called=real_api_called,
            before_state=before_state or {},
            after_state=after_state or {},
            error=error,
            timestamp=_iso(started_at),
        )
    return SafeExecutionOutcome(context=ctx, result=result, verdict=verdict)


def make_request(action="update_waterfall", target="merge_witch", domain="ad_monetization", mode="dry_run"):
    intent = ExecutionIntent(
        intent_id="int_x",
        decision_id="dec_x",
        domain=domain,
        action=ExecutionAction(action),
        target_id=target,
        reason="test",
        confidence=0.9,
        risk_level=0.3,
        requires_approval=False,
    )
    return ExecutionRequest(intent=intent, mode=mode)


@pytest.fixture
def base_time():
    return BASE_TIME


@pytest.fixture
def executed_outcome():
    return make_outcome(VERDICT_EXECUTED, latency_seconds=3.0)


@pytest.fixture
def executed_outcome_meta():
    return make_outcome(
        VERDICT_EXECUTED, provider="meta", action="pause_campaign",
        target="merge_witch", latency_seconds=15.0,
    )


@pytest.fixture
def blocked_outcome():
    return make_outcome(VERDICT_BLOCKED)


@pytest.fixture
def failed_outcome():
    return make_outcome(VERDICT_FAILED, target="game_a", error="boom")


@pytest.fixture
def rollback_outcome():
    return make_outcome(VERDICT_ROLLED_BACK, target="game_b")


@pytest.fixture
def escalated_outcome():
    return make_outcome(VERDICT_ESCALATED, target="game_c")


@pytest.fixture
def idempotent_outcome():
    return make_outcome(VERDICT_RETURN_EXISTING)


@pytest.fixture
def sample_request():
    return make_request()


@pytest.fixture
def monitor():
    from src.execution.monitor import ExecutionMonitor

    return ExecutionMonitor()
