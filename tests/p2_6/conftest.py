"""P2.6 测试公共 fixture：复用 P2.5 的 make_outcome 模式，并扩展故障构造器。

提供：
- make_outcome / make_request  : P2.4 SafeExecutionOutcome / P2.1 ExecutionRequest 构造
- make_failed_outcome(kind)    : 四类故障 + 未知故障 的失败 outcome
- AlertStub                    : 轻量 P2.5 MonitorAlert 替身（drift 信号）
- FakeSafeExecutor             : 唯一执行出口替身（记录调用、按队列返回 outcome）
- build_test_engine            : 全内存版 RecoveryEngine（无磁盘 / 无网络）
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

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
from src.execution.recovery.escalation import (
    EscalationManager,
    InMemoryEscalationStore,
)
from src.execution.recovery.executor import RecoveryExecutor
from src.execution.recovery.__init__ import (  # noqa: F401
    RecoveryMemoryBridge,
    InMemoryRecoveryExperienceStore,
)
from src.execution.recovery.verifier import RecoveryVerifier

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


def make_request(
    action="update_waterfall",
    target="merge_witch",
    domain="ad_monetization",
    mode="dry_run",
    risk=0.3,
    requires_approval=False,
):
    intent = ExecutionIntent(
        intent_id="int_x",
        decision_id="dec_x",
        domain=domain,
        action=ExecutionAction(action),
        target_id=target,
        reason="test",
        confidence=0.9,
        risk_level=risk,
        requires_approval=requires_approval,
    )
    return ExecutionRequest(intent=intent, mode=mode)


# ---------------------------------------------------------------------------
# 故障构造器：四类故障 + 未知，供 Test1 / Test6 / Test7 使用
# ---------------------------------------------------------------------------

def make_failed_outcome(
    kind: str,
    *,
    action="disable_network",
    target="merge_witch",
    provider="max",
    mode="production",
    error=None,
    **kw,
):
    """构造指定种类的失败 outcome。

    kind:
        timeout   -> VERDICT_FAILED, error="provider timeout ..."
        auth      -> VERDICT_FAILED, error="401 unauthorized token expired"
        drift     -> VERDICT_FAILED, after_state expected/actual 不一致
        rollback  -> VERDICT_ESCALATED, error="rollback failed"
        unknown   -> VERDICT_FAILED, error="???"
    error: 可覆盖默认错误文本（用于优先级测试）
    """
    default_error = {
        "timeout": "provider timeout: connection reset by peer",
        "auth": "401 unauthorized: token expired",
        "drift": "state mismatch detected",
        "rollback": "rollback failed: snapshot corrupted",
        "unknown": "some incomprehensible failure",
    }[kind]
    err = error or default_error
    if kind == "drift":
        after_state = {"expected_status": "PAUSED", "status": "ACTIVE"}
        return make_outcome(
            VERDICT_FAILED, error=err, after_state=after_state,
            action=action, target=target, provider=provider, mode=mode, **kw,
        )
    verdict = VERDICT_ESCALATED if kind == "rollback" else VERDICT_FAILED
    return make_outcome(
        verdict, error=err,
        action=action, target=target, provider=provider, mode=mode, **kw,
    )
    raise ValueError(f"unknown failure kind: {kind}")


class AlertStub:
    """轻量 P2.5 MonitorAlert 替身（漂移信号载体）。"""

    def __init__(self, drifted: bool = False, kind: str = "", message: str = ""):
        self.drifted = drifted
        self.kind = kind
        self.type = kind
        self.message = message


class FakeSafeExecutor:
    """RecoveryExecutor 唯一执行出口的替身。

    按队列返回预置 outcome；记录每次 execute(request) 调用，
    并（可选）对 request 做 side_effect（如标记 real_api_called）。
    """

    def __init__(self, outcomes: Optional[List[Any]] = None, default_ok: bool = True):
        self._queue = list(outcomes or [])
        self.calls: List[Any] = []
        self.default_ok = default_ok

    def execute(self, request):
        self.calls.append(request)
        if self._queue:
            return self._queue.pop(0)
        # 默认返回一个成功 outcome（沿用 request 的动作/目标便于比对）
        action = "update_waterfall"
        target = "merge_witch"
        intent = getattr(request, "intent", None)
        if intent is not None:
            action = str(getattr(intent, "action", action))
            target = str(getattr(intent, "target_id", target))
        return make_outcome(
            VERDICT_EXECUTED, action=action, target=target,
            provider="max", mode=getattr(request, "mode", "production"),
        )


def build_test_engine(
    fake_executor_outcomes: Optional[List[Any]] = None,
    *,
    read_fn=None,
    sleep_fn=None,
    escalation_store=None,
    experience_store=None,
):
    """装配一个全内存、无磁盘、无网络的 RecoveryEngine 用于测试。"""
    fake = FakeSafeExecutor(fake_executor_outcomes or [])
    executor = RecoveryExecutor(
        fake, sleep_fn=sleep_fn or (lambda s: None), read_fn=read_fn,
    )
    engine = RecoveryEngine(
        safe_executor=fake,
        verifier=RecoveryVerifier(read_fn=read_fn),
        escalation=EscalationManager(store=escalation_store or InMemoryEscalationStore()),
        memory=RecoveryMemoryBridge(store=experience_store or InMemoryRecoveryExperienceStore()),
        executor=executor,
    )
    return engine, fake


# 延迟导入 RecoveryEngine（避免顶层循环 import 风险）
from src.execution.recovery import RecoveryEngine  # noqa: E402
