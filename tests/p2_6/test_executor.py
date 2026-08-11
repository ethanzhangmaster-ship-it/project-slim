"""P2.6.5 — RecoveryExecutor 验收。

Test3 Retry Limit   : 重试成功 / 用尽 3 次 -> NOT_RECOVERED / 退避 1-5-30
Test4 Reconcile     : read_fn 已一致 -> 无操作恢复（RECOVERED, attempts=0）
Test5 Approval Boundary:
    - RecoveryExecutor 必须注入 SafeExecutor（否则 ValueError）
    - 恢复动作唯一出口是 safe_executor.execute（绝不直调 Provider API）
    - escalate_only 计划不调用 execute
    - 重试构造新 request_id（绕过 P2.4 幂等闸门）
"""

import pytest

from src.execution.recovery.executor import RecoveryExecutor
from src.execution.recovery.models import (
    INCIDENT_PLANNED,
    INCIDENT_RECOVERING,
    RECOVERY_ESCALATED,
    RECOVERY_NOT_RECOVERED,
    RECOVERY_RECOVERED,
    RecoveryIncident,
    RecoveryPlan,
    STRATEGY_ESCALATION,
    STRATEGY_RECONCILE,
    STRATEGY_RETRY,
)
from tests.p2_6.conftest import (
    FakeSafeExecutor,
    make_failed_outcome,
    make_outcome,
    make_request,
)


# ---------------------------------------------------------------------------
# Test5: 纪律红线 —— 必须走 SafeExecutor
# ---------------------------------------------------------------------------

def test_executor_requires_safe_executor():
    with pytest.raises(ValueError):
        RecoveryExecutor(None)


def test_executor_single_channel_only():
    """恢复动作唯一出口是注入的 safe_executor.execute。"""
    fake = FakeSafeExecutor([make_outcome("EXECUTED", action="disable_network")])
    ex = RecoveryExecutor(fake, sleep_fn=lambda s: None)
    incident = RecoveryIncident(execution_id="exe_1", action="disable_network",
                                target="merge_witch", status=INCIDENT_PLANNED)
    plan = RecoveryPlan(incident_id=incident.incident_id, strategy=STRATEGY_RETRY,
                        action="disable_network", target="merge_witch",
                        provider="max", max_attempts=3, backoff=[1.0, 5.0, 30.0])
    request = make_request(action="disable_network", risk=0.3)
    result = ex.recover(incident, plan, request)
    # 恰好调用一次 execute，且无其他执行通道
    assert len(fake.calls) == 1
    assert result.recovered is True


def test_executor_escalate_only_does_not_execute():
    fake = FakeSafeExecutor([])
    ex = RecoveryExecutor(fake, sleep_fn=lambda s: None)
    incident = RecoveryIncident(execution_id="exe_1", action="disable_network",
                                status=INCIDENT_PLANNED)
    plan = RecoveryPlan(incident_id=incident.incident_id, strategy=STRATEGY_ESCALATION,
                        escalate_only=True)
    request = make_request()
    result = ex.recover(incident, plan, request)
    assert result.status == RECOVERY_ESCALATED
    assert len(fake.calls) == 0  # 升级计划绝不触碰执行层
    assert incident.status == INCIDENT_PLANNED  # 停在 PLANNED，由 Escalation 迁


def test_executor_clones_request_new_id_each_attempt():
    """重试时构造新 request_id，避免 P2.4 幂等命中 RETURN_EXISTING。"""
    outcomes = [
        make_outcome("FAILED", error="timeout"),
        make_outcome("FAILED", error="timeout"),
        make_outcome("EXECUTED"),
    ]
    fake = FakeSafeExecutor(outcomes)
    ex = RecoveryExecutor(fake, sleep_fn=lambda s: None)
    incident = RecoveryIncident(execution_id="exe_1", action="disable_network",
                                status=INCIDENT_PLANNED)
    plan = RecoveryPlan(incident_id=incident.incident_id, strategy=STRATEGY_RETRY,
                        action="disable_network", target="merge_witch",
                        provider="max", max_attempts=3, backoff=[1.0, 5.0, 30.0])
    request = make_request(action="disable_network", risk=0.3)
    ex.recover(incident, plan, request)
    assert len(fake.calls) == 3
    # 每次请求都是新 request_id，但动作一致
    ids = [c.request_id for c in fake.calls]
    assert len(set(ids)) == 3  # 三个不同 id
    for c in fake.calls:
        assert c.intent.action.value == "disable_network"


# ---------------------------------------------------------------------------
# Test3: Retry Limit
# ---------------------------------------------------------------------------

def test_retry_recovers_on_third_attempt():
    outcomes = [
        make_outcome("FAILED", error="timeout"),
        make_outcome("FAILED", error="timeout"),
        make_outcome("EXECUTED", action="disable_network"),
    ]
    fake = FakeSafeExecutor(outcomes)
    waits = []
    ex = RecoveryExecutor(fake, sleep_fn=waits.append)
    incident = RecoveryIncident(execution_id="exe_1", action="disable_network",
                                status=INCIDENT_PLANNED)
    plan = RecoveryPlan(incident_id=incident.incident_id, strategy=STRATEGY_RETRY,
                        action="disable_network", target="merge_witch",
                        provider="max", max_attempts=3, backoff=[1.0, 5.0, 30.0])
    request = make_request(action="disable_network", risk=0.3)
    result = ex.recover(incident, plan, request)
    assert result.status == RECOVERY_RECOVERED
    assert result.attempts == 3
    # 退避在第 1/2/3 次前分别等待 1/5/30（注意：成功那次也等待了 30）
    assert waits == [1.0, 5.0, 30.0]
    assert incident.status == INCIDENT_RECOVERING


def test_retry_exhausts_after_three_failures():
    outcomes = [
        make_outcome("FAILED", error="timeout"),
        make_outcome("FAILED", error="timeout"),
        make_outcome("FAILED", error="timeout"),
    ]
    fake = FakeSafeExecutor(outcomes)
    waits = []
    ex = RecoveryExecutor(fake, sleep_fn=waits.append)
    incident = RecoveryIncident(execution_id="exe_1", action="disable_network",
                                status=INCIDENT_PLANNED)
    plan = RecoveryPlan(incident_id=incident.incident_id, strategy=STRATEGY_RETRY,
                        action="disable_network", target="merge_witch",
                        provider="max", max_attempts=3, backoff=[1.0, 5.0, 30.0])
    request = make_request(action="disable_network", risk=0.3)
    result = ex.recover(incident, plan, request)
    assert result.status == RECOVERY_NOT_RECOVERED
    assert result.attempts == 3
    assert len(result.attempt_log) == 3
    # 所有尝试都失败
    assert all(not a.ok for a in result.attempt_log)


def test_retry_zero_backoff_no_sleep():
    outcomes = [make_outcome("EXECUTED")]
    fake = FakeSafeExecutor(outcomes)
    waits = []
    ex = RecoveryExecutor(fake, sleep_fn=waits.append)
    incident = RecoveryIncident(execution_id="exe_1", action="disable_network",
                                status=INCIDENT_PLANNED)
    plan = RecoveryPlan(incident_id=incident.incident_id, strategy=STRATEGY_RETRY,
                        action="disable_network", provider="max",
                        max_attempts=1, backoff=[])
    request = make_request(action="disable_network", risk=0.3)
    result = ex.recover(incident, plan, request)
    assert result.status == RECOVERY_RECOVERED
    assert waits == []  # 无退避不打断


# ---------------------------------------------------------------------------
# Test4: Reconcile
# ---------------------------------------------------------------------------

def test_reconcile_noop_when_platform_already_expected():
    """read_fn 读到的平台状态已与期望一致 -> 无操作恢复。"""
    expected = {"status": "PAUSED"}
    read_fn = lambda target: {"status": "PAUSED"}  # 已一致
    fake = FakeSafeExecutor([])
    ex = RecoveryExecutor(fake, sleep_fn=lambda s: None, read_fn=read_fn)
    incident = RecoveryIncident(execution_id="exe_1", action="disable_network",
                                status=INCIDENT_PLANNED)
    plan = RecoveryPlan(incident_id=incident.incident_id, strategy=STRATEGY_RECONCILE,
                        action="disable_network", target="merge_witch",
                        provider="max", max_attempts=1,
                        expected_state=expected)
    request = make_request(action="disable_network", risk=0.3)
    result = ex.recover(incident, plan, request)
    assert result.status == RECOVERY_RECOVERED
    assert result.attempts == 0
    assert result.outcome is None  # 未执行任何动作
    assert len(fake.calls) == 0   # 无需重执行


def test_reconcile_proceeds_when_state_drift_persists():
    """read_fn 状态仍不一致 -> 真正重执行 SafeExecutor。"""
    read_fn = lambda target: {"status": "ACTIVE"}  # 仍漂移
    fake = FakeSafeExecutor([make_outcome("EXECUTED", action="disable_network")])
    ex = RecoveryExecutor(fake, sleep_fn=lambda s: None, read_fn=read_fn)
    incident = RecoveryIncident(execution_id="exe_1", action="disable_network",
                                status=INCIDENT_PLANNED)
    plan = RecoveryPlan(incident_id=incident.incident_id, strategy=STRATEGY_RECONCILE,
                        action="disable_network", target="merge_witch",
                        provider="max", max_attempts=1,
                        expected_state={"status": "PAUSED"})
    request = make_request(action="disable_network", risk=0.3)
    result = ex.recover(incident, plan, request)
    assert result.status == RECOVERY_RECOVERED
    assert len(fake.calls) == 1


def test_reconcile_no_read_fn_executes_directly():
    """无 read_fn 注入时直接走 SafeExecutor 重执行。"""
    fake = FakeSafeExecutor([make_outcome("EXECUTED", action="disable_network")])
    ex = RecoveryExecutor(fake, sleep_fn=lambda s: None)
    incident = RecoveryIncident(execution_id="exe_1", action="disable_network",
                                status=INCIDENT_PLANNED)
    plan = RecoveryPlan(incident_id=incident.incident_id, strategy=STRATEGY_RECONCILE,
                        action="disable_network", target="merge_witch",
                        provider="max", max_attempts=1,
                        expected_state={"status": "PAUSED"})
    request = make_request(action="disable_network", risk=0.3)
    result = ex.recover(incident, plan, request)
    assert result.status == RECOVERY_RECOVERED
    assert len(fake.calls) == 1
