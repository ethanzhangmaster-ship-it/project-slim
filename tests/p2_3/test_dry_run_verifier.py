"""P0 ApprovalGate V2 — DryRunVerifier 单元测试。

Spec: docs/p0_approval_gate_v2_spec.md §5.1, §7, §12, §10.1 (场景 10/11)

覆盖：
- dry_run 成功 + 无 expected_impact → 通过
- dry_run 成功 + expected_impact dict + budget_delta 匹配 → 通过
- dry_run 成功 + expected_impact dict + budget_delta 差异 > tolerance → 拒绝
- dry_run 成功 + expected_impact 数值 → 通过（不对比）
- dry_run 返回 success=False → 拒绝
- dry_run 抛异常 → 拒绝（fail-closed）
- dry_run response 无可对比字段 → 通过（保守不阻塞）
- expected ≈ 0 + actual ≈ 0 → 通过
- expected ≈ 0 + actual 大 → 拒绝
- 自定义 tolerance / key
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from src.execution.approval.dry_run_verifier import (
    DEFAULT_BUDGET_DELTA_KEY,
    DEFAULT_RESPONSE_BUDGET_KEY,
    DEFAULT_TOLERANCE,
    DryRunVerifier,
)


# ──────────────────────────────────────────────
# Mock 对象
# ──────────────────────────────────────────────


@dataclass
class MockResult:
    """模拟 ExecutionResult（仅 DryRunVerifier 需要的字段）。"""
    success: bool = True
    error_message: str = ""
    response: Any = None


@dataclass
class MockAction:
    """模拟 ExecutionAction（仅 DryRunVerifier 需要的字段）。"""
    action_id: str = "act_test"
    expected_impact: Any = None


class MockExecutor:
    """模拟 ActionExecutor，可控 dry_run 结果。"""

    def __init__(
        self,
        result: MockResult | None = None,
        raise_exc: Exception | None = None,
    ) -> None:
        self._result = result or MockResult(success=True)
        self._raise = raise_exc
        self.call_count = 0
        self.last_dry_run: bool | None = None

    def execute(self, action: Any, dry_run: bool = False) -> MockResult:
        self.call_count += 1
        self.last_dry_run = dry_run
        if self._raise is not None:
            raise self._raise
        return self._result


# ──────────────────────────────────────────────
# 通过场景
# ──────────────────────────────────────────────


class TestPassScenarios:
    """dry_run 通过 → 可升级为真实执行。"""

    def test_pass_no_expected_impact(self):
        """无 expected_impact → 仅看 dry_run success → 通过。"""
        executor = MockExecutor(result=MockResult(success=True, response={"ok": 1}))
        action = MockAction(expected_impact=None)
        verifier = DryRunVerifier(executor)
        ok, reason = verifier.verify_and_promote(action)
        assert ok is True
        assert "no expected_impact" in reason
        assert executor.last_dry_run is True  # 确认调用了 dry_run=True

    def test_pass_empty_expected_impact(self):
        """expected_impact 为空 dict → 通过。"""
        executor = MockExecutor(result=MockResult(success=True, response={}))
        action = MockAction(expected_impact={})
        verifier = DryRunVerifier(executor)
        ok, _ = verifier.verify_and_promote(action)
        assert ok is True

    def test_pass_budget_delta_match(self):
        """expected budget_delta=100, actual target_budget=105 → diff 5% < 20% → 通过。"""
        executor = MockExecutor(
            result=MockResult(success=True, response={"target_budget": 105.0})
        )
        action = MockAction(expected_impact={"budget_delta": 100.0})
        verifier = DryRunVerifier(executor, tolerance=0.20)
        ok, reason = verifier.verify_and_promote(action)
        assert ok is True
        assert "match" in reason.lower()

    def test_pass_budget_delta_exact_match(self):
        """expected budget_delta=100, actual=100 → diff 0% → 通过。"""
        executor = MockExecutor(
            result=MockResult(success=True, response={"target_budget": 100.0})
        )
        action = MockAction(expected_impact={"budget_delta": 100.0})
        verifier = DryRunVerifier(executor)
        ok, _ = verifier.verify_and_promote(action)
        assert ok is True

    def test_pass_scalar_expected_impact(self):
        """expected_impact 是数值 → 不对比 → 通过。"""
        executor = MockExecutor(result=MockResult(success=True, response={"x": 1}))
        action = MockAction(expected_impact=0.5)
        verifier = DryRunVerifier(executor)
        ok, reason = verifier.verify_and_promote(action)
        assert ok is True
        assert "scalar" in reason

    def test_pass_no_budget_delta_key(self):
        """expected_impact dict 无 budget_delta → 通过。"""
        executor = MockExecutor(result=MockResult(success=True, response={}))
        action = MockAction(expected_impact={"other_metric": 0.8})
        verifier = DryRunVerifier(executor)
        ok, reason = verifier.verify_and_promote(action)
        assert ok is True
        assert "no 'budget_delta'" in reason

    def test_pass_response_no_budget_key(self):
        """dry_run response 无 target_budget → 通过（保守不阻塞）。"""
        executor = MockExecutor(
            result=MockResult(success=True, response={"other_field": 1})
        )
        action = MockAction(expected_impact={"budget_delta": 100.0})
        verifier = DryRunVerifier(executor)
        ok, reason = verifier.verify_and_promote(action)
        assert ok is True
        assert "no 'target_budget'" in reason

    def test_pass_both_near_zero(self):
        """expected≈0, actual≈0 → 通过。"""
        executor = MockExecutor(
            result=MockResult(success=True, response={"target_budget": 0.5})
        )
        action = MockAction(expected_impact={"budget_delta": 0.0})
        verifier = DryRunVerifier(executor)
        ok, reason = verifier.verify_and_promote(action)
        assert ok is True
        assert "near zero" in reason


# ──────────────────────────────────────────────
# 拒绝场景
# ──────────────────────────────────────────────


class TestRejectScenarios:
    """dry_run 失败 → 拒绝升级。"""

    def test_reject_dry_run_failure(self):
        """dry_run success=False → 拒绝。"""
        executor = MockExecutor(
            result=MockResult(success=False, error_message="simulated failure")
        )
        action = MockAction(expected_impact=None)
        verifier = DryRunVerifier(executor)
        ok, reason = verifier.verify_and_promote(action)
        assert ok is False
        assert "failure" in reason.lower()

    def test_reject_dry_run_exception(self):
        """dry_run 抛异常 → 拒绝（fail-closed）。"""
        executor = MockExecutor(raise_exc=RuntimeError("network error"))
        action = MockAction(expected_impact=None)
        verifier = DryRunVerifier(executor)
        ok, reason = verifier.verify_and_promote(action)
        assert ok is False
        assert "raised" in reason
        assert "RuntimeError" in reason

    def test_reject_budget_delta_mismatch(self):
        """expected=100, actual=150 → diff 50% > 20% → 拒绝。"""
        executor = MockExecutor(
            result=MockResult(success=True, response={"target_budget": 150.0})
        )
        action = MockAction(expected_impact={"budget_delta": 100.0})
        verifier = DryRunVerifier(executor, tolerance=0.20)
        ok, reason = verifier.verify_and_promote(action)
        assert ok is False
        assert "diff" in reason
        assert "50.0%" in reason

    def test_reject_expected_zero_actual_large(self):
        """expected=0, actual=100 → 拒绝。"""
        executor = MockExecutor(
            result=MockResult(success=True, response={"target_budget": 100.0})
        )
        action = MockAction(expected_impact={"budget_delta": 0.0})
        verifier = DryRunVerifier(executor)
        ok, reason = verifier.verify_and_promote(action)
        assert ok is False
        assert "expected≈0" in reason

    def test_reject_at_tolerance_boundary(self):
        """diff 恰好 = tolerance → 不拒绝（> 才拒绝，= 通过）。"""
        # expected=100, actual=120, diff=20% = tolerance 0.20 → 通过
        executor = MockExecutor(
            result=MockResult(success=True, response={"target_budget": 120.0})
        )
        action = MockAction(expected_impact={"budget_delta": 100.0})
        verifier = DryRunVerifier(executor, tolerance=0.20)
        ok, _ = verifier.verify_and_promote(action)
        assert ok is True

    def test_reject_just_over_tolerance(self):
        """diff 略 > tolerance → 拒绝。"""
        # expected=100, actual=121, diff=21% > 20% → 拒绝
        executor = MockExecutor(
            result=MockResult(success=True, response={"target_budget": 121.0})
        )
        action = MockAction(expected_impact={"budget_delta": 100.0})
        verifier = DryRunVerifier(executor, tolerance=0.20)
        ok, reason = verifier.verify_and_promote(action)
        assert ok is False
        assert "21.0%" in reason


# ──────────────────────────────────────────────
# 自定义配置
# ──────────────────────────────────────────────


class TestCustomConfig:
    """自定义 tolerance / key。"""

    def test_custom_tolerance_loose(self):
        """tolerance=0.5（50%）→ diff 30% 通过。"""
        executor = MockExecutor(
            result=MockResult(success=True, response={"target_budget": 130.0})
        )
        action = MockAction(expected_impact={"budget_delta": 100.0})
        verifier = DryRunVerifier(executor, tolerance=0.50)
        ok, _ = verifier.verify_and_promote(action)
        assert ok is True

    def test_custom_tolerance_strict(self):
        """tolerance=0.05（5%）→ diff 10% 拒绝。"""
        executor = MockExecutor(
            result=MockResult(success=True, response={"target_budget": 110.0})
        )
        action = MockAction(expected_impact={"budget_delta": 100.0})
        verifier = DryRunVerifier(executor, tolerance=0.05)
        ok, reason = verifier.verify_and_promote(action)
        assert ok is False
        assert "10.0%" in reason

    def test_custom_budget_delta_key(self):
        """自定义 budget_delta_key。"""
        executor = MockExecutor(
            result=MockResult(success=True, response={"target_budget": 100.0})
        )
        action = MockAction(expected_impact={"custom_delta": 100.0})
        verifier = DryRunVerifier(
            executor, budget_delta_key="custom_delta"
        )
        ok, reason = verifier.verify_and_promote(action)
        assert ok is True
        assert "match" in reason.lower()

    def test_custom_response_budget_key(self):
        """自定义 response_budget_key。"""
        executor = MockExecutor(
            result=MockResult(success=True, response={"custom_budget": 100.0})
        )
        action = MockAction(expected_impact={"budget_delta": 100.0})
        verifier = DryRunVerifier(
            executor, response_budget_key="custom_budget"
        )
        ok, _ = verifier.verify_and_promote(action)
        assert ok is True

    def test_default_constants(self):
        """默认常量值验证。"""
        assert DEFAULT_TOLERANCE == 0.20
        assert DEFAULT_BUDGET_DELTA_KEY == "budget_delta"
        assert DEFAULT_RESPONSE_BUDGET_KEY == "target_budget"


# ──────────────────────────────────────────────
# 调用验证
# ──────────────────────────────────────────────


class TestInvocation:
    """verify_and_promote 调用 executor.execute(dry_run=True)。"""

    def test_calls_execute_with_dry_run_true(self):
        executor = MockExecutor(result=MockResult(success=True))
        action = MockAction(expected_impact=None)
        verifier = DryRunVerifier(executor)
        verifier.verify_and_promote(action)
        assert executor.call_count == 1
        assert executor.last_dry_run is True

    def test_action_id_in_logs(self):
        """action_id 出现在 reason 中（便于审计追溯）。"""
        executor = MockExecutor(
            raise_exc=ValueError("test error"),
        )
        action = MockAction(action_id="act_abc123", expected_impact=None)
        verifier = DryRunVerifier(executor)
        ok, reason = verifier.verify_and_promote(action)
        # reason 含异常类型和消息（action_id 在 log 里，不在 reason 里）
        assert "ValueError" in reason
        assert "test error" in reason
