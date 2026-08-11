"""P2.6.3 — Recovery Strategy 验收（Test2 Retry Policy）。

覆盖：
- backoff_for 退避查表（边界 / 越界 / 空表）
- RetryPolicy 默认 3 次 / 1s-5s-30s
- ReconcilePolicy（reread_before_execute）
- RollbackRetryPolicy（max_retry=1）
- EscalationPolicy（manual_intervention）
- policy_for_treatment 映射（含未知 -> 保守升级）
"""

from src.execution.recovery.models import (
    STRATEGY_ESCALATION,
    STRATEGY_RECONCILE,
    STRATEGY_RETRY,
    STRATEGY_ROLLBACK_RETRY,
    TREATMENT_EMERGENCY_ESCALATE,
    TREATMENT_ESCALATE,
    TREATMENT_RECONCILE,
    TREATMENT_RETRY,
    TREATMENT_ROLLBACK_RETRY,
)
from src.execution.recovery.strategy import (
    backoff_for,
    DEFAULT_RETRY_BACKOFF,
    DEFAULT_RETRY_MAX_ATTEMPTS,
    DEFAULT_ROLLBACK_MAX_RETRY,
    EscalationPolicy,
    policy_for_treatment,
    ReconcilePolicy,
    RetryPolicy,
    RollbackRetryPolicy,
)


def test_backoff_for_index():
    b = [1.0, 5.0, 30.0]
    assert backoff_for(1, b) == 1.0
    assert backoff_for(2, b) == 5.0
    assert backoff_for(3, b) == 30.0


def test_backoff_for_out_of_range_uses_last():
    b = [1.0, 5.0, 30.0]
    # 第 4 次及以上取最后一项
    assert backoff_for(4, b) == 30.0
    assert backoff_for(10, b) == 30.0


def test_backoff_for_empty_returns_zero():
    assert backoff_for(1, []) == 0.0
    assert backoff_for(0, []) == 0.0


def test_backoff_for_negative_attempt_clamped():
    b = [1.0, 5.0]
    assert backoff_for(-3, b) == 1.0


def test_default_constants():
    assert DEFAULT_RETRY_BACKOFF == (1.0, 5.0, 30.0)
    assert DEFAULT_RETRY_MAX_ATTEMPTS == 3
    assert DEFAULT_ROLLBACK_MAX_RETRY == 1


def test_retry_policy_defaults():
    p = RetryPolicy()
    assert p.strategy == STRATEGY_RETRY
    assert p.max_attempts == 3
    assert p.backoff == (1.0, 5.0, 30.0)
    assert p.escalate_on_exhaust is True


def test_retry_policy_wait_before():
    p = RetryPolicy()
    assert p.wait_before(1) == 1.0
    assert p.wait_before(2) == 5.0
    assert p.wait_before(3) == 30.0


def test_reconcile_policy_rereads():
    p = ReconcilePolicy()
    assert p.strategy == STRATEGY_RECONCILE
    assert p.max_attempts == 1
    assert p.reread_before_execute is True
    assert p.escalate_on_exhaust is True


def test_rollback_retry_policy_single_attempt():
    p = RollbackRetryPolicy()
    assert p.strategy == STRATEGY_ROLLBACK_RETRY
    assert p.max_attempts == 1
    assert p.emergency_on_exhaust is True
    assert p.backoff == (1.0,)


def test_escalation_policy_manual():
    p = EscalationPolicy()
    assert p.strategy == STRATEGY_ESCALATION
    assert p.manual_intervention is True
    assert p.wait_before(1) == 0.0


def test_policy_for_treatment_mappings():
    assert isinstance(policy_for_treatment(TREATMENT_RETRY), RetryPolicy)
    assert isinstance(policy_for_treatment(TREATMENT_RECONCILE), ReconcilePolicy)
    assert isinstance(policy_for_treatment(TREATMENT_ROLLBACK_RETRY), RollbackRetryPolicy)
    assert isinstance(policy_for_treatment(TREATMENT_ESCALATE), EscalationPolicy)
    assert isinstance(policy_for_treatment(TREATMENT_EMERGENCY_ESCALATE), EscalationPolicy)


def test_policy_for_treatment_unknown_is_conservative():
    # 未知处置一律保守：升级策略
    p = policy_for_treatment("WEIRD_TREATMENT")
    assert isinstance(p, EscalationPolicy)


def test_policy_roundtrip():
    for p in (RetryPolicy(), ReconcilePolicy(), RollbackRetryPolicy(), EscalationPolicy()):
        d = p.to_dict()
        assert d["strategy"] in (
            STRATEGY_RETRY, STRATEGY_RECONCILE,
            STRATEGY_ROLLBACK_RETRY, STRATEGY_ESCALATION,
        )
