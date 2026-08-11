"""P2.4.7 集成验收：P2.1 Contract -> P2.3 Authorization -> P2.4 SafeExecutor -> P2.2 Provider -> Result -> Audit 全链路。

聚焦 P2 层内闭环（E17 决策在更高层，本测试不重复 E17 全链，但验证 P2.4 作为
控制平面把「合同 / 授权 / Provider / 审计」串起来的正确性，含 JSONL 持久层）。
"""

import pytest

from src.execution.models import ExecutionMode
from src.execution.providers.result import STATUS_FAILED, ExecutionResult
from src.execution.safe_executor import (
    JsonlIdempotencyStore,
    JsonlSnapshotStore,
    RollbackEngine,
    SafeExecutor,
    build_safe_executor,
    make_idempotency_key,
)
from src.execution.safe_executor.idempotency import (
    IDEM_ROLLED_BACK,
    IDEM_SUCCESS,
)
from src.execution.safe_executor.audit import (
    EVENT_EXECUTION_FINISHED,
    EVENT_EXECUTION_STARTED,
    EVENT_PROVIDER_CALLED,
    EVENT_ROLLBACK_FINISHED,
    ExecutionAuditLogger,
)
from tests.p2_4.conftest import FakeRouter, MaxProvider, make_auth, make_intent, make_request


def _success(r):
    return ExecutionResult(
        request_id=r.request_id, provider="max", status="success",
        real_api_called=True, after_state={"network": "disabled"},
    )


def _failed(r):
    return ExecutionResult(
        request_id=r.request_id, provider="max", status=STATUS_FAILED,
        real_api_called=True, error="boom",
    )


class TestFullChainDryRun:
    def test_dry_run_chain_with_jsonl(self, tmp_path):
        idem = JsonlIdempotencyStore(str(tmp_path / "idem.jsonl"))
        snap = JsonlSnapshotStore(str(tmp_path / "snaps"))
        audit = ExecutionAuditLogger(audit_dir=str(tmp_path / "audit"))
        provider = MaxProvider()
        req = make_request(mode=ExecutionMode.DRY_RUN, intent=make_intent())
        se = SafeExecutor(
            execute_fn=provider.execute, provider_resolver=lambda r: provider,
            idempotency_store=idem, snapshot_store=snap, rollback_engine=RollbackEngine(),
            audit=audit,
        )
        out = se.execute(req)
        assert out.ok
        # 快照落盘
        assert (tmp_path / "snaps" / f"{out.context.execution_id}.json").exists()
        # DRY_RUN 不写幂等
        assert (tmp_path / "idem.jsonl").read_text().strip() == ""
        # 审计三事件
        events = [e["event"] for e in audit.events_for(out.context.execution_id)]
        assert events == [EVENT_EXECUTION_STARTED, EVENT_PROVIDER_CALLED, EVENT_EXECUTION_FINISHED]


class TestFullChainProduction:
    def test_production_success_jsonl(self, tmp_path):
        idem = JsonlIdempotencyStore(str(tmp_path / "idem.jsonl"))
        snap = JsonlSnapshotStore(str(tmp_path / "snaps"))
        audit = ExecutionAuditLogger(audit_dir=str(tmp_path / "audit"))
        provider = MaxProvider()
        req = make_request(
            mode=ExecutionMode.PRODUCTION, intent=make_intent(),
            authorization=make_auth(),
        )
        se = SafeExecutor(
            execute_fn=provider.execute, provider_resolver=lambda r: provider,
            idempotency_store=idem, snapshot_store=snap, rollback_engine=RollbackEngine(),
            audit=audit,
        )
        out = se.execute(req)
        assert out.verdict == "EXECUTED" and out.ok
        assert out.result.real_api_called is True
        # 幂等 SUCCESS 落盘
        key = make_idempotency_key(req.intent.action, req.intent.target_id, req.intent.expected_impact)
        rec = idem.get(key)
        assert rec is not None and rec.status == IDEM_SUCCESS
        # 审计链完整
        events = [e["event"] for e in audit.events_for(out.context.execution_id)]
        assert EVENT_EXECUTION_STARTED in events
        assert EVENT_PROVIDER_CALLED in events
        assert EVENT_EXECUTION_FINISHED in events


class TestFullChainProductionFailure:
    def test_production_failure_rollback_jsonl(self, tmp_path):
        idem = JsonlIdempotencyStore(str(tmp_path / "idem.jsonl"))
        snap = JsonlSnapshotStore(str(tmp_path / "snaps"))
        audit = ExecutionAuditLogger(audit_dir=str(tmp_path / "audit"))
        provider = MaxProvider()
        req = make_request(
            mode=ExecutionMode.PRODUCTION, intent=make_intent(),
            authorization=make_auth(),
        )
        se = SafeExecutor(
            execute_fn=_failed, provider_resolver=lambda r: provider,
            idempotency_store=idem, snapshot_store=snap, rollback_engine=RollbackEngine(),
            audit=audit,
        )
        out = se.execute(req)
        assert out.verdict == "ROLLED_BACK"
        # 幂等 ROLLED_BACK 落盘
        key = make_idempotency_key(req.intent.action, req.intent.target_id, req.intent.expected_impact)
        assert idem.get(key).status == IDEM_ROLLED_BACK
        # 回滚审计事件
        events = [e["event"] for e in audit.events_for(out.context.execution_id)]
        assert EVENT_ROLLBACK_FINISHED in events


class TestFactoryBuildSafeExecutor:
    def test_build_from_router(self, mem_idem, mem_snap, tmp_audit):
        router = FakeRouter(MaxProvider())
        se = build_safe_executor(
            router, idempotency_store=mem_idem, snapshot_store=mem_snap, audit=tmp_audit
        )
        req = make_request(mode=ExecutionMode.DRY_RUN, intent=make_intent())
        out = se.execute(req)
        assert out.ok
        assert out.result is not None
        # resolver 路径：通过 router.registry.providers_for + router.providers 定位
        assert mem_snap.load(out.context.execution_id) is not None
