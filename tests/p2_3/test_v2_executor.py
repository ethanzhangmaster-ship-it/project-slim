"""P0 ApprovalGate V2 — V2ActionExecutor 集成测试。

Spec: docs/p0_approval_gate_v2_spec.md §7 (action_executor 集成), §8 (audit log), §10.1

覆盖：
- Level 0 自动执行（非 shadow）
- Level 0 shadow 模式（只记 audit 不执行）
- Level 0 执行异常（fail-closed）
- Level 1 dry_run 通过 → 升级真实执行
- Level 1 dry_run 失败 → 阻塞
- Level 1 dry_run disabled → 阻塞
- Level 2 → 阻塞等人工
- DENY → 阻塞
- V1 兼容路径（无 policy/config）
- audit log JSONL 落盘
- BudgetWindowTracker 记账验证
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from src.execution.approval.budget_window import BudgetWindowTracker
from src.execution.approval.config import ApprovalConfig
from src.execution.approval.dry_run_verifier import DryRunVerifier
from src.execution.approval.policy import ApprovalPolicy
from src.execution.approval.v2_executor import (
    DEFAULT_AUDIT_FILENAME,
    V2ActionExecutor,
    V2ExecutionOutcome,
)
from src.execution.models import (
    ExecutionAction,
    ExecutionDomain,
    ExecutionIntent,
)


# ──────────────────────────────────────────────
# Mock 对象
# ──────────────────────────────────────────────


@dataclass
class MockExecutionResult:
    """模拟 V1 ActionExecutor.execute() 返回值。"""
    success: bool = True
    error_message: str = ""
    response: Any = None


@dataclass
class MockV1Executor:
    """模拟 V1 ActionExecutor。"""
    result: MockExecutionResult = field(default_factory=MockExecutionResult)
    raise_exc: Exception | None = None
    call_count: int = 0
    last_dry_run: bool | None = None

    def execute(self, action: Any, dry_run: bool = False) -> MockExecutionResult:
        self.call_count += 1
        self.last_dry_run = dry_run
        if self._raise_for_test is not None:
            raise self._raise_for_test
        return self.result

    @property
    def _raise_for_test(self):
        return self.raise_exc


# ──────────────────────────────────────────────
# 辅助构造
# ──────────────────────────────────────────────


def _v2_intent(
    action: ExecutionAction,
    risk: float = 0.1,
    confidence: float = 0.95,
    budget_amount_usd: float = 0.0,
    target_id: str = "p04_witch_merge",
    domain: ExecutionDomain = ExecutionDomain.UA,
    expected_impact: Any = None,
) -> ExecutionIntent:
    intent = ExecutionIntent(
        intent_id="",
        decision_id="dec_test",
        domain=domain,
        action=action,
        target_id=target_id,
        reason="v2 integration test",
        confidence=confidence,
        expected_impact=expected_impact,
        risk_level=risk,
    )
    intent.budget_amount_usd = budget_amount_usd  # type: ignore[attr-defined]
    return intent


def _v2_action(action_id: str = "act_test") -> Any:
    """简化的 ExecutionAction mock（仅 V2 需要的字段）。"""
    from dataclasses import dataclass as _dc

    @_dc
    class _Action:
        action_id: str = "act_test"
        expected_impact: Any = None

    a = _Action()
    a.action_id = action_id
    return a


def _setup_v2(
    tmp_path: Path,
    level0_enabled: bool = True,
    shadow_mode: bool = False,
    dry_run_verify_enabled: bool = True,
    v1_result: MockExecutionResult | None = None,
    v1_raise: Exception | None = None,
) -> tuple[V2ActionExecutor, MockV1Executor, BudgetWindowTracker, ApprovalConfig]:
    """构造完整 V2 测试环境。"""
    cfg = ApprovalConfig(
        auto_budget_threshold_usd=50.0,
        auto_daily_cumulative_usd=200.0,
        level1_budget_threshold_usd=500.0,
        auto_max_risk=0.3,
        auto_min_confidence=0.9,
        level1_max_risk=0.6,
        level0_enabled=level0_enabled,
        shadow_mode=shadow_mode,
        dry_run_verify_enabled=dry_run_verify_enabled,
        audit_log_dir=str(tmp_path),
    )
    tracker = BudgetWindowTracker(audit_log_dir=str(tmp_path))
    policy = ApprovalPolicy(config=cfg, window_tracker=tracker)
    v1_executor = MockV1Executor(
        result=v1_result or MockExecutionResult(success=True),
        raise_exc=v1_raise,
    )
    verifier = DryRunVerifier(executor=v1_executor)
    v2 = V2ActionExecutor(
        executor=v1_executor,
        policy=policy,
        config=cfg,
        window_tracker=tracker,
        dry_run_verifier=verifier,
    )
    return v2, v1_executor, tracker, cfg


# ──────────────────────────────────────────────
# Level 0 自动执行
# ──────────────────────────────────────────────


class TestLevel0Execution:
    """Level 0 + auto_approved → 真实执行。"""

    def test_level0_pause_campaign_executes(self, tmp_path):
        v2, v1, tracker, cfg = _setup_v2(tmp_path, level0_enabled=True)
        intent = _v2_intent(
            ExecutionAction.PAUSE_CAMPAIGN,
            risk=0.1, confidence=0.95, budget_amount_usd=0.0,
        )
        action = _v2_action()
        outcome = v2.execute_with_approval(action, intent)
        assert outcome.executed is True
        assert outcome.decision.level == 0
        assert outcome.blocked_reason is None
        assert v1.call_count == 1
        assert v1.last_dry_run is False  # 真实执行

    def test_level0_scale_budget_executes(self, tmp_path):
        v2, v1, tracker, cfg = _setup_v2(tmp_path, level0_enabled=True)
        intent = _v2_intent(
            ExecutionAction.SCALE_BUDGET,
            risk=0.2, confidence=0.92, budget_amount_usd=30.0,
        )
        action = _v2_action()
        outcome = v2.execute_with_approval(action, intent)
        assert outcome.executed is True
        assert outcome.decision.level == 0

    def test_level0_records_budget_window(self, tmp_path):
        """Level 0 执行后，BudgetWindowTracker 应记账。"""
        v2, v1, tracker, cfg = _setup_v2(tmp_path, level0_enabled=True)
        intent = _v2_intent(
            ExecutionAction.SCALE_BUDGET,
            risk=0.1, confidence=0.95, budget_amount_usd=40.0,
            target_id="p04",
        )
        action = _v2_action()
        v2.execute_with_approval(action, intent)
        # v2_executor 用 str(action) 作 key，查询时也用 str(枚举)
        cumulative = tracker.get_cumulative(
            "p04", str(ExecutionAction.SCALE_BUDGET), date.today()
        )
        assert cumulative == 40.0

    def test_level0_execution_failure_blocks(self, tmp_path):
        """Level 0 真实执行失败 → outcome.executed=False。"""
        v2, v1, tracker, cfg = _setup_v2(
            tmp_path,
            level0_enabled=True,
            v1_result=MockExecutionResult(success=False, error_message="api error"),
        )
        intent = _v2_intent(
            ExecutionAction.PAUSE_CAMPAIGN,
            risk=0.1, confidence=0.95,
        )
        action = _v2_action()
        outcome = v2.execute_with_approval(action, intent)
        assert outcome.executed is False
        assert "api error" in outcome.blocked_reason

    def test_level0_execution_exception_blocks(self, tmp_path):
        """Level 0 执行抛异常 → fail-closed 阻塞。"""
        v2, v1, tracker, cfg = _setup_v2(
            tmp_path, level0_enabled=True,
            v1_raise=RuntimeError("network down"),
        )
        intent = _v2_intent(
            ExecutionAction.PAUSE_CAMPAIGN,
            risk=0.1, confidence=0.95,
        )
        action = _v2_action()
        outcome = v2.execute_with_approval(action, intent)
        assert outcome.executed is False
        assert "network down" in outcome.blocked_reason


# ──────────────────────────────────────────────
# Level 0 Shadow 模式
# ──────────────────────────────────────────────


class TestLevel0ShadowMode:
    """Level 0 + shadow_mode → 只记 audit 不执行。"""

    def test_shadow_mode_does_not_execute(self, tmp_path):
        v2, v1, tracker, cfg = _setup_v2(
            tmp_path, level0_enabled=True, shadow_mode=True
        )
        intent = _v2_intent(
            ExecutionAction.PAUSE_CAMPAIGN,
            risk=0.1, confidence=0.95,
        )
        action = _v2_action()
        outcome = v2.execute_with_approval(action, intent)
        assert outcome.executed is False
        assert "shadow" in outcome.blocked_reason.lower()
        assert v1.call_count == 0  # 不执行

    def test_shadow_mode_still_audits(self, tmp_path):
        """Shadow 模式仍写 audit log。"""
        v2, v1, tracker, cfg = _setup_v2(
            tmp_path, level0_enabled=True, shadow_mode=True
        )
        intent = _v2_intent(
            ExecutionAction.PAUSE_CAMPAIGN,
            risk=0.1, confidence=0.95,
        )
        action = _v2_action(action_id="act_shadow_1")
        outcome = v2.execute_with_approval(action, intent)
        audit_path = tmp_path / DEFAULT_AUDIT_FILENAME
        assert audit_path.exists()
        with open(audit_path, "r", encoding="utf-8") as f:
            records = [json.loads(ln) for ln in f if ln.strip()]
        assert len(records) == 1
        assert records[0]["action_id"] == "act_shadow_1"
        assert records[0]["shadow"] is True
        assert records[0]["executed"] is False


# ──────────────────────────────────────────────
# Level 1 + dry_run
# ──────────────────────────────────────────────


class TestLevel1DryRun:
    """Level 1 + dry_run_required → 验证后升级。"""

    def test_level1_dry_run_pass_promotes_to_real_execution(self, tmp_path):
        """dry_run 通过 → 升级真实执行。"""
        v2, v1, tracker, cfg = _setup_v2(
            tmp_path, level0_enabled=True, dry_run_verify_enabled=True,
            v1_result=MockExecutionResult(success=True, response={}),
        )
        # 中额 SCALE → Level 1 + dry_run_required
        intent = _v2_intent(
            ExecutionAction.SCALE_BUDGET,
            risk=0.3, confidence=0.9, budget_amount_usd=100.0,
        )
        action = _v2_action()
        outcome = v2.execute_with_approval(action, intent)
        assert outcome.decision.level == 1
        assert outcome.dry_run_result is not None
        assert outcome.dry_run_result[0] is True  # dry_run 通过
        assert outcome.executed is True  # 升级执行
        # dry_run + 真实执行 = 2 次调用
        assert v1.call_count == 2

    def test_level1_dry_run_fail_blocks(self, tmp_path):
        """dry_run 失败 → 阻塞。"""
        v2, v1, tracker, cfg = _setup_v2(
            tmp_path, level0_enabled=True, dry_run_verify_enabled=True,
            v1_result=MockExecutionResult(success=False, error_message="dry fail"),
        )
        intent = _v2_intent(
            ExecutionAction.SCALE_BUDGET,
            risk=0.3, confidence=0.9, budget_amount_usd=100.0,
        )
        action = _v2_action()
        outcome = v2.execute_with_approval(action, intent)
        assert outcome.executed is False
        assert outcome.dry_run_result[0] is False
        assert "dry_run" in outcome.blocked_reason.lower()
        # 只调 1 次（dry_run），未真实执行
        assert v1.call_count == 1

    def test_level1_dry_run_disabled_blocks(self, tmp_path):
        """dry_run_verify_enabled=False → Level 1 直接阻塞。"""
        v2, v1, tracker, cfg = _setup_v2(
            tmp_path, level0_enabled=True, dry_run_verify_enabled=False,
        )
        intent = _v2_intent(
            ExecutionAction.SCALE_BUDGET,
            risk=0.3, confidence=0.9, budget_amount_usd=100.0,
        )
        action = _v2_action()
        outcome = v2.execute_with_approval(action, intent)
        assert outcome.executed is False
        assert outcome.decision.level == 1
        assert outcome.decision.dry_run_required is False
        assert v1.call_count == 0  # 不执行 dry_run


# ──────────────────────────────────────────────
# Level 2 / DENY 阻塞
# ──────────────────────────────────────────────


class TestLevel2AndDeny:
    """Level 2 / DENY → 阻塞。"""

    def test_level2_large_amount_blocks(self, tmp_path):
        v2, v1, tracker, cfg = _setup_v2(tmp_path, level0_enabled=True)
        intent = _v2_intent(
            ExecutionAction.SCALE_BUDGET,
            risk=0.4, confidence=0.9, budget_amount_usd=600.0,
        )
        action = _v2_action()
        outcome = v2.execute_with_approval(action, intent)
        assert outcome.executed is False
        assert outcome.decision.level == 2
        assert "manual approval" in outcome.blocked_reason
        assert v1.call_count == 0

    def test_deny_unknown_action_blocks(self, tmp_path):
        v2, v1, tracker, cfg = _setup_v2(tmp_path, level0_enabled=True)
        intent = _v2_intent(
            ExecutionAction.PAUSE_CAMPAIGN,
            risk=0.1, confidence=0.95,
        )
        intent.action = "UNKNOWN_ACTION"  # type: ignore[assignment]
        action = _v2_action()
        outcome = v2.execute_with_approval(action, intent)
        assert outcome.executed is False
        assert outcome.blocked_reason.startswith("DENY:")
        assert v1.call_count == 0

    def test_create_release_admin_blocks(self, tmp_path):
        """CREATE_RELEASE → Level 2 ADMIN → 阻塞。"""
        v2, v1, tracker, cfg = _setup_v2(tmp_path, level0_enabled=True)
        intent = _v2_intent(
            ExecutionAction.CREATE_RELEASE,
            risk=0.05, confidence=0.99, budget_amount_usd=0.0,
            domain=ExecutionDomain.RELEASE,
        )
        action = _v2_action()
        outcome = v2.execute_with_approval(action, intent)
        assert outcome.executed is False
        assert outcome.decision.level == 2
        assert v1.call_count == 0


# ──────────────────────────────────────────────
# V1 兼容路径
# ──────────────────────────────────────────────


class TestV1Compat:
    """无 policy/config → 退化为 V1 直接执行。"""

    def test_no_policy_falls_back_to_v1(self, tmp_path):
        v1 = MockV1Executor(result=MockExecutionResult(success=True))
        v2 = V2ActionExecutor(executor=v1)  # 无 policy/config
        intent = _v2_intent(ExecutionAction.PAUSE_CAMPAIGN)
        action = _v2_action()
        outcome = v2.execute_with_approval(action, intent)
        assert outcome.executed is True
        assert v1.call_count == 1
        assert outcome.audit_record.get("mode") == "v1_compat"


# ──────────────────────────────────────────────
# Audit log
# ──────────────────────────────────────────────


class TestAuditLog:
    """Spec §8: audit log JSONL 落盘。"""

    def test_audit_log_appended_per_execution(self, tmp_path):
        v2, v1, tracker, cfg = _setup_v2(tmp_path, level0_enabled=True)
        # 执行 3 次
        for i in range(3):
            intent = _v2_intent(
                ExecutionAction.PAUSE_CAMPAIGN,
                risk=0.1, confidence=0.95,
            )
            action = _v2_action(action_id=f"act_{i}")
            v2.execute_with_approval(action, intent)
        audit_path = tmp_path / DEFAULT_AUDIT_FILENAME
        assert audit_path.exists()
        with open(audit_path, "r", encoding="utf-8") as f:
            records = [json.loads(ln) for ln in f if ln.strip()]
        assert len(records) == 3
        assert [r["action_id"] for r in records] == ["act_0", "act_1", "act_2"]

    def test_audit_record_fields(self, tmp_path):
        """audit 记录含 Spec §8 全部字段。"""
        v2, v1, tracker, cfg = _setup_v2(tmp_path, level0_enabled=True)
        intent = _v2_intent(
            ExecutionAction.SCALE_BUDGET,
            risk=0.2, confidence=0.92, budget_amount_usd=30.0,
            target_id="p04",
        )
        action = _v2_action(action_id="act_fields")
        outcome = v2.execute_with_approval(action, intent)
        record = outcome.audit_record
        assert record["action_id"] == "act_fields"
        assert record["game_id"] == "p04"
        assert record["action_type"] == "ExecutionAction.SCALE_BUDGET"
        assert record["amount_usd"] == 30.0
        assert record["risk"] == 0.2
        assert record["confidence"] == 0.92
        assert record["level"] == 0
        assert record["outcome"] == "AUTO"
        assert record["shadow"] is False
        assert record["executed"] is True
        assert "ts" in record
        assert "reason" in record


# ──────────────────────────────────────────────
# 端到端：Level 0 → Level 1 → Level 2 组合
# ──────────────────────────────────────────────


class TestEndToEndCombination:
    """模拟 24h growth loop 多动作组合。"""

    def test_mixed_actions_routing(self, tmp_path):
        """混合 Level 0/1/2 动作正确路由。"""
        v2, v1, tracker, cfg = _setup_v2(
            tmp_path, level0_enabled=True, dry_run_verify_enabled=True,
        )
        # Level 0: 小额 PAUSE
        i0 = _v2_intent(ExecutionAction.PAUSE_CAMPAIGN, risk=0.1, confidence=0.95)
        # Level 1: 中额 SCALE
        i1 = _v2_intent(ExecutionAction.SCALE_BUDGET, risk=0.3, confidence=0.9, budget_amount_usd=100.0)
        # Level 2: 大额 SCALE
        i2 = _v2_intent(ExecutionAction.SCALE_BUDGET, risk=0.4, confidence=0.9, budget_amount_usd=600.0)

        o0 = v2.execute_with_approval(_v2_action("a0"), i0)
        o1 = v2.execute_with_approval(_v2_action("a1"), i1)
        o2 = v2.execute_with_approval(_v2_action("a2"), i2)

        assert o0.decision.level == 0 and o0.executed is True
        assert o1.decision.level == 1 and o1.executed is True  # dry_run 通过
        assert o2.decision.level == 2 and o2.executed is False
