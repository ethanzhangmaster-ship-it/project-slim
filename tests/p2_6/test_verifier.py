"""P2.6.6 — RecoveryVerifier 验收。

验证优先级：
1. read_fn 平台实读（异常 -> UNVERIFIABLE）
2. outcome.result.after_state
3. 都没有 -> UNVERIFIABLE（保守）
匹配 -> RECOVERED；不匹配 -> NOT_RECOVERED。
"""

import pytest

from src.execution.recovery.models import (
    RecoveryPlan,
    VERIFY_NOT_RECOVERED,
    VERIFY_RECOVERED,
    VERIFY_UNVERIFIABLE,
)
from src.execution.recovery.verifier import RecoveryVerifier
from tests.p2_6.conftest import make_outcome


def _plan(expected, target="merge_witch"):
    return RecoveryPlan(incident_id="i", strategy="RETRY", target=target,
                        expected_state=expected)


def test_verify_no_expected_state_is_unverifiable():
    v = RecoveryVerifier()
    plan = _plan({})
    res = v.verify(plan)
    assert res.status == VERIFY_UNVERIFIABLE


def test_verify_via_platform_read_recovered():
    read_fn = lambda target: {"status": "PAUSED", "network": "disabled"}
    v = RecoveryVerifier(read_fn=read_fn)
    plan = _plan({"status": "PAUSED"})
    res = v.verify(plan)
    assert res.status == VERIFY_RECOVERED
    assert res.recovered is True
    assert res.observed_state == {"status": "PAUSED", "network": "disabled"}


def test_verify_via_platform_read_not_recovered():
    read_fn = lambda target: {"status": "ACTIVE"}  # 期望 PAUSED
    v = RecoveryVerifier(read_fn=read_fn)
    plan = _plan({"status": "PAUSED"})
    res = v.verify(plan)
    assert res.status == VERIFY_NOT_RECOVERED
    assert res.recovered is False


def test_verify_platform_read_exception_is_unverifiable():
    def boom(target):
        raise RuntimeError("platform unreachable")
    v = RecoveryVerifier(read_fn=boom)
    plan = _plan({"status": "PAUSED"})
    res = v.verify(plan)
    assert res.status == VERIFY_UNVERIFIABLE


def test_verify_via_outcome_after_state_recovered():
    outcome = make_outcome("EXECUTED", after_state={"status": "PAUSED"})
    v = RecoveryVerifier()  # 无 read_fn
    plan = _plan({"status": "PAUSED"})
    res = v.verify(plan, outcome=outcome)
    assert res.status == VERIFY_RECOVERED


def test_verify_via_outcome_after_state_not_recovered():
    outcome = make_outcome("EXECUTED", after_state={"status": "ACTIVE"})
    v = RecoveryVerifier()
    plan = _plan({"status": "PAUSED"})
    res = v.verify(plan, outcome=outcome)
    assert res.status == VERIFY_NOT_RECOVERED


def test_verify_outcome_dict_form_supported():
    outcome = make_outcome("EXECUTED", after_state={"status": "PAUSED"}).to_dict()
    v = RecoveryVerifier()
    plan = _plan({"status": "PAUSED"})
    res = v.verify(plan, outcome=outcome)
    assert res.status == VERIFY_RECOVERED


def test_verify_case_insensitive_match():
    outcome = make_outcome("EXECUTED", after_state={"status": "paused"})
    v = RecoveryVerifier()
    plan = _plan({"status": "PAUSED"})
    res = v.verify(plan, outcome=outcome)
    assert res.status == VERIFY_RECOVERED


def test_verify_no_observed_is_unverifiable():
    # 无 read_fn，无 outcome -> 保守不可验证
    v = RecoveryVerifier()
    plan = _plan({"status": "PAUSED"})
    res = v.verify(plan)
    assert res.status == VERIFY_UNVERIFIABLE


def test_verify_override_expected_state():
    read_fn = lambda target: {"status": "PAUSED"}
    v = RecoveryVerifier(read_fn=read_fn)
    plan = _plan({"status": "ACTIVE"})  # plan 期望与 read 不一致
    res = v.verify(plan, expected_state={"status": "PAUSED"})  # 覆盖后一致
    assert res.status == VERIFY_RECOVERED


def test_verify_partial_expected_keys_all_must_match():
    read_fn = lambda target: {"status": "PAUSED", "extra": "ignored"}
    v = RecoveryVerifier(read_fn=read_fn)
    plan = _plan({"status": "PAUSED", "network": "disabled"})  # network 缺失
    res = v.verify(plan)
    assert res.status == VERIFY_NOT_RECOVERED
