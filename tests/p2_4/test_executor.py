"""P2.4.6 SafeExecutor 七步编排 + 六类验收场景测试。

验收矩阵：
    ① 基础执行 PASS（DRY_RUN / PRODUCTION）
    ② 幂等 RETURN_EXISTING 短路
    ③ Provider 失败 -> 回滚 ROLLED_BACK
    ④ Snapshot 失败 -> BLOCK
    ⑤ Approval 过期 / 缺失 -> BLOCK
    ③变体：回滚失败 -> ESCALATE；无能力 -> FAILED；BLOCKED 不回滚
"""

import pytest

from src.execution.models import ExecutionAction, ExecutionMode, ExecutionRequest
from src.execution.providers.result import (
    STATUS_BLOCKED,
    STATUS_DRY_RUN,
    STATUS_FAILED,
    STATUS_SUCCESS,
    ExecutionResult,
)
from src.execution.safe_executor import (
    InMemoryIdempotencyStore,
    InMemorySnapshotStore,
    RollbackEngine,
    SafeExecutor,
    make_idempotency_key,
)
from src.execution.safe_executor.idempotency import (
    IDEM_FAILED,
    IDEM_RUNNING,
    IDEM_ROLLED_BACK,
    IDEM_SUCCESS,
    IdempotencyRecord,
)
from src.execution.safe_executor.models import (
    CTX_BLOCKED,
    CTX_FAILED,
    CTX_ROLLED_BACK,
    CTX_SUCCESS,
    VERDICT_BLOCKED,
    VERDICT_ESCALATED,
    VERDICT_EXECUTED,
    VERDICT_FAILED,
    VERDICT_RETURN_EXISTING,
    VERDICT_ROLLED_BACK,
)
from src.execution.safe_executor.audit import (
    EVENT_EXECUTION_FINISHED,
    EVENT_EXECUTION_STARTED,
    EVENT_PROVIDER_CALLED,
)
from tests.p2_4.conftest import (
    BadSnapshotProvider,
    FailingRollbackProvider,
    MaxProvider,
    RaisingRollbackProvider,
    make_auth,
    make_intent,
    make_request,
)


def _build(execute_fn, provider, idem, snap, audit, strict=False, rollback=None):
    return SafeExecutor(
        execute_fn=execute_fn,
        provider_resolver=(lambda r: provider) if provider is not None else None,
        idempotency_store=idem,
        snapshot_store=snap,
        rollback_engine=rollback or RollbackEngine(),
        audit=audit,
        strict_snapshot=strict,
    )


def _dry_result(r):
    return ExecutionResult(
        request_id=r.request_id, provider="max", status=STATUS_DRY_RUN,
        real_api_called=False, after_state={"intended": "x"},
    )


def _success_result(r):
    return ExecutionResult(
        request_id=r.request_id, provider="max", status=STATUS_SUCCESS,
        real_api_called=True, after_state={"network": "disabled"},
    )


def _failed_result(r, provider="max"):
    return ExecutionResult(
        request_id=r.request_id, provider=provider, status=STATUS_FAILED,
        real_api_called=True, error="boom",
    )


def _blocked_result(r):
    return ExecutionResult(
        request_id=r.request_id, provider="max", status=STATUS_BLOCKED,
        real_api_called=False, error="internal gate",
    )


class TestBasicExecution:
    def test_dry_run_passes(self, max_provider, mem_idem, mem_snap, tmp_audit, request_dry):
        se = _build(max_provider.execute, max_provider, mem_idem, mem_snap, tmp_audit)
        out = se.execute(request_dry)
        assert out.verdict == VERDICT_EXECUTED
        assert out.context.status == CTX_SUCCESS
        assert out.result.status == STATUS_DRY_RUN
        assert out.result.real_api_called is False
        assert out.ok
        # 快照已保存
        assert mem_snap.load(out.context.execution_id) is not None
        # 审计链
        events = [e["event"] for e in tmp_audit.events_for(out.context.execution_id)]
        assert events == [EVENT_EXECUTION_STARTED, EVENT_PROVIDER_CALLED, EVENT_EXECUTION_FINISHED]

    def test_production_success_real_called(self, max_provider, mem_idem, mem_snap, tmp_audit, request_prod):
        se = _build(max_provider.execute, max_provider, mem_idem, mem_snap, tmp_audit)
        out = se.execute(request_prod)
        assert out.verdict == VERDICT_EXECUTED
        assert out.result.real_api_called is True
        # 幂等写入 SUCCESS
        key = make_idempotency_key(
            request_prod.intent.action, request_prod.intent.target_id,
            request_prod.intent.expected_impact,
        )
        rec = mem_idem.get(key)
        assert rec is not None and rec.status == IDEM_SUCCESS


class TestIdempotencyShortCircuit:
    def test_return_existing_no_provider_call(self, max_provider, mem_idem, mem_snap, tmp_audit, request_prod):
        key = make_idempotency_key(
            request_prod.intent.action, request_prod.intent.target_id,
            request_prod.intent.expected_impact,
        )
        mem_idem.put(IdempotencyRecord(key=key, execution_id="prev", status=IDEM_SUCCESS, result={"restored": True}))
        called = {"n": 0}

        def fn(r):
            called["n"] += 1
            return _success_result(r)

        se = _build(fn, max_provider, mem_idem, mem_snap, tmp_audit)
        out = se.execute(request_prod)
        assert out.verdict == VERDICT_RETURN_EXISTING
        assert out.result is None
        assert out.context.status == CTX_SUCCESS
        assert out.context.after_state == {"restored": True}
        assert called["n"] == 0  # 短路，未触碰外部系统


class TestProviderFailureRollback:
    def test_failure_triggers_rollback(self, max_provider, mem_idem, mem_snap, tmp_audit, request_prod):
        se = _build(_failed_result, max_provider, mem_idem, mem_snap, tmp_audit)
        out = se.execute(request_prod)
        assert out.verdict == VERDICT_ROLLED_BACK
        assert out.context.status == CTX_ROLLED_BACK
        assert out.rollback is not None
        assert out.rollback["status"] == "ROLLBACK_SUCCESS"
        key = make_idempotency_key(
            request_prod.intent.action, request_prod.intent.target_id,
            request_prod.intent.expected_impact,
        )
        assert mem_idem.get(key).status == IDEM_ROLLED_BACK
        # 回滚审计事件
        events = [e["event"] for e in tmp_audit.events_for(out.context.execution_id)]
        assert "rollback.finished" in events

    def test_failure_no_capability_failed(self, max_provider, mem_idem, mem_snap, tmp_audit, request_prod):
        def fn(r):
            return _failed_result(r, provider="unknown")  # 无回滚能力
        se = _build(fn, max_provider, mem_idem, mem_snap, tmp_audit)
        out = se.execute(request_prod)
        assert out.verdict == VERDICT_FAILED
        assert out.context.status == CTX_FAILED
        assert not out.escalated

    def test_failure_rollback_fails_escalates(self, max_provider, mem_idem, mem_snap, tmp_audit, request_prod):
        se = _build(_failed_result, FailingRollbackProvider(), mem_idem, mem_snap, tmp_audit)
        out = se.execute(request_prod)
        assert out.verdict == VERDICT_ESCALATED
        assert out.escalated is True
        assert out.context.status == CTX_FAILED

    def test_failure_rollback_raises_escalates(self, max_provider, mem_idem, mem_snap, tmp_audit, request_prod):
        se = _build(_failed_result, RaisingRollbackProvider(), mem_idem, mem_snap, tmp_audit)
        out = se.execute(request_prod)
        assert out.verdict == VERDICT_ESCALATED
        assert out.escalated is True


class TestSnapshotFailure:
    def test_snapshot_failure_blocks(self, mem_idem, mem_snap, tmp_audit, request_dry):
        se = _build(_success_result, BadSnapshotProvider(), mem_idem, mem_snap, tmp_audit)
        out = se.execute(request_dry)
        assert out.verdict == VERDICT_BLOCKED
        assert out.context.status == CTX_BLOCKED
        assert out.result is None  # 从未触碰 Provider
        # 未写幂等
        assert mem_idem.get("anything") is None

    def test_strict_snapshot_blocks_when_unimplemented(self, mem_idem, mem_snap, tmp_audit, request_dry):
        class NoSnapshot:
            provider_id = "max"
        se = _build(_success_result, NoSnapshot(), mem_idem, mem_snap, tmp_audit, strict=True)
        out = se.execute(request_dry)
        assert out.verdict == VERDICT_BLOCKED
        assert out.context.status == CTX_BLOCKED


class TestAuthorizationGates:
    def test_missing_authorization_blocks(self, max_provider, mem_idem, mem_snap, tmp_audit):
        req = make_request(mode=ExecutionMode.PRODUCTION, intent=make_intent())
        se = _build(max_provider.execute, max_provider, mem_idem, mem_snap, tmp_audit)
        out = se.execute(req)
        assert out.verdict == VERDICT_BLOCKED
        assert out.context.status == CTX_BLOCKED

    def test_expired_authorization_blocks(self, max_provider, mem_idem, mem_snap, tmp_audit):
        auth = make_auth(ExecutionAction.DISABLE_NETWORK)
        auth.approved_at = "2026-07-01T00:00:00Z"
        auth.expires_at = "2026-07-02T00:00:00Z"
        req = make_request(
            mode=ExecutionMode.PRODUCTION, intent=make_intent(), authorization=auth
        )
        se = _build(max_provider.execute, max_provider, mem_idem, mem_snap, tmp_audit)
        out = se.execute(req)
        assert out.verdict == VERDICT_BLOCKED
        assert out.context.status == CTX_BLOCKED

    def test_high_risk_blocks(self, max_provider, mem_idem, mem_snap, tmp_audit):
        auth = make_auth(ExecutionAction.DISABLE_NETWORK)
        req = make_request(
            mode=ExecutionMode.PRODUCTION, intent=make_intent(risk_level=0.95), authorization=auth
        )
        se = _build(max_provider.execute, max_provider, mem_idem, mem_snap, tmp_audit)
        out = se.execute(req)
        assert out.verdict == VERDICT_BLOCKED
        assert out.context.status == CTX_BLOCKED


class TestBlockedVerdictNoRollback:
    def test_provider_blocked_no_rollback(self, max_provider, mem_idem, mem_snap, tmp_audit, request_prod):
        se = _build(_blocked_result, max_provider, mem_idem, mem_snap, tmp_audit)
        out = se.execute(request_prod)
        assert out.verdict == VERDICT_BLOCKED
        assert out.context.status == CTX_BLOCKED
        assert out.rollback is None  # 未动手，无需回滚
        # RUNNING 占位已清理为 FAILED（允许后续重试）
        key = make_idempotency_key(
            request_prod.intent.action, request_prod.intent.target_id,
            request_prod.intent.expected_impact,
        )
        assert mem_idem.get(key).status == IDEM_FAILED


class TestExecuteFnRaise:
    def test_execute_fn_raises_failed(self, max_provider, mem_idem, mem_snap, tmp_audit, request_prod):
        def boom(r):
            raise RuntimeError("explode")
        se = _build(boom, max_provider, mem_idem, mem_snap, tmp_audit)
        out = se.execute(request_prod)
        assert out.verdict == VERDICT_FAILED
        assert out.context.status == CTX_FAILED
        assert out.result is None
        key = make_idempotency_key(
            request_prod.intent.action, request_prod.intent.target_id,
            request_prod.intent.expected_impact,
        )
        assert mem_idem.get(key).status == IDEM_FAILED
