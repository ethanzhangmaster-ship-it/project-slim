"""P2.6.8 — RecoveryEngine 端到端验收（Test7 Full Autonomous Recovery）。

覆盖：
- 成功执行无需恢复 -> SKIPPED
- 完整超时重试 -> RECOVERED + 验证通过 + incident 关闭 + 经验回流
- 验证经平台实读 -> RECOVERED (platform_read)
- 验证不过 -> 降级为 NOT_RECOVERED -> 升级
- 认证失败 -> ESCALATED (HIGH)
- 状态漂移 -> RECONCILE 无操作恢复
- 回滚失败 -> CRITICAL 升级 + automation_halted
- 全局熔断：open CRITICAL 工单存在时一律只升级不自动执行
- 记忆回流（经验库 + 图谱懒跳过）
- build_recovery_engine 工厂
"""

import pytest

from src.execution.recovery import (
    build_recovery_engine,
    RecoveryEngine,
    RecoveryMemoryBridge,
    InMemoryRecoveryExperienceStore,
)
from src.execution.recovery.escalation import InMemoryEscalationStore
from src.execution.recovery.models import (
    INCIDENT_CLOSED,
    RECOVERY_ESCALATED,
    RECOVERY_NOT_RECOVERED,
    RECOVERY_RECOVERED,
    RECOVERY_SKIPPED,
    SEVERITY_CRITICAL,
    SEVERITY_HIGH,
    VERIFY_NOT_RECOVERED,
    VERIFY_RECOVERED,
)
from tests.p2_6.conftest import (
    build_test_engine,
    make_failed_outcome,
    make_outcome,
    make_request,
)


def test_engine_requires_safe_executor_or_executor():
    with pytest.raises(ValueError):
        RecoveryEngine()


def test_handle_success_is_skipped():
    engine, fake = build_test_engine([])
    outcome = make_outcome("EXECUTED", action="disable_network")
    request = make_request(action="disable_network", risk=0.3)
    result = engine.handle(outcome, request)
    assert result.status == RECOVERY_SKIPPED
    assert result.incident_id == ""
    assert len(fake.calls) == 0


def test_full_timeout_retry_recovered():
    engine, fake = build_test_engine(
        [make_outcome("EXECUTED", action="disable_network")],
    )
    outcome = make_failed_outcome("timeout", action="disable_network")
    request = make_request(action="disable_network", risk=0.3)
    result = engine.handle(outcome, request, expected_state={"status": "PAUSED"})
    assert result.status == RECOVERY_RECOVERED
    assert result.attempts == 1
    assert len(fake.calls) == 1
    # incident 收敛到 CLOSED
    assert result.escalation is None


def test_recovery_writes_experience_record():
    engine, fake = build_test_engine(
        [make_outcome("EXECUTED", action="disable_network")],
    )
    outcome = make_failed_outcome("timeout", action="disable_network")
    request = make_request(action="disable_network", risk=0.3)
    result = engine.handle(outcome, request)
    store = engine.memory.store
    rows = store.all()
    assert len(rows) == 1
    rec = rows[0]
    assert rec["failure"] == "PROVIDER_TIMEOUT"
    assert rec["recovery"] == "RETRY"
    assert rec["result"] == RECOVERY_RECOVERED
    assert rec["reward"] == 0.8
    assert rec["success"] is True


def test_recovery_verify_via_platform_read():
    engine, fake = build_test_engine(
        [make_outcome("EXECUTED", action="disable_network")],
        read_fn=lambda t: {"status": "PAUSED"},
    )
    outcome = make_failed_outcome("timeout", action="disable_network")
    request = make_request(action="disable_network", risk=0.3)
    result = engine.handle(outcome, request, expected_state={"status": "PAUSED"})
    assert result.status == RECOVERY_RECOVERED
    assert result.verification is not None
    assert result.verification.status == VERIFY_RECOVERED


def test_recovery_verify_failure_downgrades_and_escalates():
    # 执行返回 ok，但平台实际状态与期望不符 -> 验证不过 -> 升级
    engine, fake = build_test_engine(
        [make_outcome("EXECUTED", action="disable_network",
                      after_state={"status": "ACTIVE"})],
    )
    outcome = make_failed_outcome("timeout", action="disable_network")
    request = make_request(action="disable_network", risk=0.3)
    result = engine.handle(outcome, request, expected_state={"status": "PAUSED"})
    assert result.verification is not None
    assert result.verification.status == VERIFY_NOT_RECOVERED
    # 降级为未恢复 -> 升级
    assert result.status == RECOVERY_ESCALATED
    assert result.escalation is not None
    assert len(fake.calls) == 1  # 确实执行过一次（只是验证失败）


def test_auth_failure_escalated_high():
    engine, fake = build_test_engine([])
    outcome = make_failed_outcome("auth", action="pause_campaign")
    request = make_request(action="pause_campaign", risk=0.4)
    result = engine.handle(outcome, request)
    assert result.status == RECOVERY_ESCALATED
    assert len(fake.calls) == 0  # 认证失败绝不自动重试
    assert result.escalation["severity"] == SEVERITY_HIGH


def test_drift_reconcile_noop_recovery():
    engine, fake = build_test_engine(
        [], read_fn=lambda t: {"status": "PAUSED"},
    )
    outcome = make_failed_outcome("drift", action="disable_network")
    request = make_request(action="disable_network", risk=0.3)
    result = engine.handle(outcome, request, expected_state={"status": "PAUSED"})
    assert result.status == RECOVERY_RECOVERED
    assert result.attempts == 0
    assert len(fake.calls) == 0  # 平台已一致，无重执行


def test_rollback_failure_critical_escalation_and_halt():
    engine, fake = build_test_engine([])
    outcome = make_failed_outcome("rollback", action="disable_network")
    request = make_request(action="disable_network", risk=0.3)
    result = engine.handle(outcome, request)
    assert result.status == RECOVERY_ESCALATED
    assert result.escalation["severity"] == SEVERITY_CRITICAL
    assert result.escalation["halt_automation"] is True
    assert engine.escalation.automation_halted() is True


def test_global_circuit_breaker_forces_escalation():
    esc_store = InMemoryEscalationStore()
    engine, fake = build_test_engine([], escalation_store=esc_store)
    # 1) 回滚失败 -> CRITICAL 工单，熔断开启
    r1 = engine.handle(make_failed_outcome("rollback"), make_request())
    assert r1.status == RECOVERY_ESCALATED
    assert engine.escalation.automation_halted() is True
    # 2) 后续即便是可重试的超时，也必须只升级、绝不自动执行
    r2 = engine.handle(
        make_failed_outcome("timeout", action="disable_network"),
        make_request(action="disable_network", risk=0.3),
    )
    assert r2.status == RECOVERY_ESCALATED
    assert len(fake.calls) == 0  # 全局熔断：根本没有尝试执行


def test_engine_memory_graph_skipped_without_graph():
    engine, fake = build_test_engine(
        [make_outcome("EXECUTED", action="disable_network")],
    )
    outcome = make_failed_outcome("timeout", action="disable_network")
    request = make_request(action="disable_network", risk=0.3)
    result = engine.handle(outcome, request)
    # 无 graph 注入时 push_to_graph 应优雅跳过
    from src.execution.recovery.models import RecoveryExperienceRecord
    record = RecoveryExperienceRecord(
        failure="PROVIDER_TIMEOUT", action="disable_network",
        recovery="RETRY", result=RECOVERY_RECOVERED,
    )
    pushed = engine.memory.push_to_graph(record)
    assert pushed == {"skipped": True, "reason": "no_graph"}


def test_build_recovery_engine_factory():
    from src.execution.recovery.executor import RecoveryExecutor
    fake = __import__(
        "tests.p2_6.conftest", fromlist=["FakeSafeExecutor"]
    ).FakeSafeExecutor([make_outcome("EXECUTED", action="disable_network")])
    engine = build_recovery_engine(
        safe_executor=fake,
        escalation_store=InMemoryEscalationStore(),
        experience_store=InMemoryRecoveryExperienceStore(),
    )
    assert isinstance(engine, RecoveryEngine)
    outcome = make_failed_outcome("timeout", action="disable_network")
    request = make_request(action="disable_network", risk=0.3)
    result = engine.handle(outcome, request, expected_state={"status": "PAUSED"})
    assert result.status == RECOVERY_RECOVERED


def test_unknown_failure_escalated():
    engine, fake = build_test_engine([])
    outcome = make_failed_outcome("unknown", action="disable_network")
    request = make_request(action="disable_network", risk=0.3)
    result = engine.handle(outcome, request)
    assert result.status == RECOVERY_ESCALATED
    assert result.escalation["severity"] == SEVERITY_HIGH


def test_retry_exhaustion_then_escalated():
    # 3 次全失败 -> NOT_RECOVERED -> 升级
    outcomes = [
        make_outcome("FAILED", error="timeout"),
        make_outcome("FAILED", error="timeout"),
        make_outcome("FAILED", error="timeout"),
    ]
    engine, fake = build_test_engine(outcomes)
    outcome = make_failed_outcome("timeout", action="disable_network")
    request = make_request(action="disable_network", risk=0.3)
    result = engine.handle(outcome, request)
    assert result.status == RECOVERY_ESCALATED
    assert len(fake.calls) == 3  # 三次重试都已尝试
    assert result.escalation is not None
