"""P0 ApprovalGate V2 — policy.evaluate() Level 0/1/2 分级测试（场景 1-7）。

Spec: docs/p0_approval_gate_v2_spec.md §10.1

本文件覆盖 Spec §10.1 测试矩阵的场景 1-7：
  1. 小额 PAUSE + 低风险 + 高置信 → Level 0 AUTO
  2. 小额 SCALE + 低风险 + 高置信 → Level 0 AUTO
  3. 中额 SCALE → Level 1 MANUAL + dry_run_required
  4. 大额 SCALE → Level 2 MANUAL
  5. 超日累计 → Level 2 MANUAL
  6. CREATE_RELEASE → Level 2 ADMIN
  7. 未知动作 → Level 2 DENY

场景 8-12（开关控制/dry_run 验证）由 Day 5/6 后的完整 test_approval_level_v2.py 覆盖。

V2 测试需要给 ExecutionIntent 注入 budget_amount_usd 字段（V1 无此字段），
通过 dataclasses.replace 或直接构造带额外属性的 intent 实现。
"""
from __future__ import annotations

from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from src.execution.approval.budget_window import BudgetWindowTracker
from src.execution.approval.config import ApprovalConfig
from src.execution.approval.policy import (
    ADMIN_ACTIONS,
    LEVEL0_ALLOWLIST,
    OUTCOME_ADMIN,
    OUTCOME_AUTO,
    OUTCOME_DENY,
    OUTCOME_MANUAL,
    ApprovalDecision,
    ApprovalPolicy,
)
from src.execution.models import (
    ExecutionAction,
    ExecutionDomain,
    ExecutionIntent,
)


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
) -> ExecutionIntent:
    """构造带 budget_amount_usd 的 V2 intent。

    ExecutionIntent V1 无 budget_amount_usd 字段，通过 setattr 动态附加。
    policy.evaluate() 用 getattr(intent, 'budget_amount_usd', 0.0) 读取。
    """
    intent = ExecutionIntent(
        intent_id="",
        decision_id="dec_test",
        domain=domain,
        action=action,
        target_id=target_id,
        reason="v2 test",
        confidence=confidence,
        expected_impact=None,
        risk_level=risk,
    )
    # V2 字段动态附加（不修改 ExecutionIntent dataclass 定义）
    intent.budget_amount_usd = budget_amount_usd  # type: ignore[attr-defined]
    return intent


def _v2_policy(
    tmp_path: Path,
    level0_enabled: bool = True,
    shadow_mode: bool = False,
    dry_run_verify_enabled: bool = True,
    auto_budget_threshold_usd: float = 50.0,
    auto_daily_cumulative_usd: float = 200.0,
    level1_budget_threshold_usd: float = 500.0,
    auto_max_risk: float = 0.3,
    auto_min_confidence: float = 0.9,
    level1_max_risk: float = 0.6,
) -> tuple[ApprovalPolicy, BudgetWindowTracker]:
    """构造 V2 完整配置的 policy + window_tracker。"""
    cfg = ApprovalConfig(
        auto_budget_threshold_usd=auto_budget_threshold_usd,
        auto_daily_cumulative_usd=auto_daily_cumulative_usd,
        level1_budget_threshold_usd=level1_budget_threshold_usd,
        auto_max_risk=auto_max_risk,
        auto_min_confidence=auto_min_confidence,
        level1_max_risk=level1_max_risk,
        level0_enabled=level0_enabled,
        shadow_mode=shadow_mode,
        dry_run_verify_enabled=dry_run_verify_enabled,
        audit_log_dir=str(tmp_path),
    )
    tracker = BudgetWindowTracker(audit_log_dir=str(tmp_path))
    policy = ApprovalPolicy(config=cfg, window_tracker=tracker)
    return policy, tracker


# ──────────────────────────────────────────────
# 场景 1: 小额 PAUSE + 低风险 + 高置信 → Level 0 AUTO
# ──────────────────────────────────────────────


class TestScenario1Level0PauseAuto:
    """Spec §10.1 场景 1。"""

    def test_small_pause_low_risk_high_conf_auto(self, tmp_path):
        policy, _ = _v2_policy(tmp_path, level0_enabled=True)
        intent = _v2_intent(
            ExecutionAction.PAUSE_CAMPAIGN,
            risk=0.1,
            confidence=0.95,
            budget_amount_usd=0.0,
        )
        decision = policy.evaluate(intent)
        assert decision.level == 0
        assert decision.outcome == OUTCOME_AUTO
        assert decision.auto_approved is True
        assert decision.required_role == "SYSTEM"


# ──────────────────────────────────────────────
# 场景 2: 小额 SCALE + 低风险 + 高置信 → Level 0 AUTO
# ──────────────────────────────────────────────


class TestScenario2Level0ScaleAuto:
    """Spec §10.1 场景 2。"""

    def test_small_scale_low_risk_high_conf_auto(self, tmp_path):
        policy, _ = _v2_policy(tmp_path, level0_enabled=True)
        intent = _v2_intent(
            ExecutionAction.SCALE_BUDGET,
            risk=0.2,
            confidence=0.92,
            budget_amount_usd=30.0,
        )
        decision = policy.evaluate(intent)
        assert decision.level == 0
        assert decision.outcome == OUTCOME_AUTO
        assert decision.auto_approved is True


# ──────────────────────────────────────────────
# 场景 3: 中额 SCALE → Level 1 MANUAL + dry_run_required
# ──────────────────────────────────────────────


class TestScenario3Level1MediumAmount:
    """Spec §10.1 场景 3。"""

    def test_medium_scale_level1_dry_run_required(self, tmp_path):
        policy, _ = _v2_policy(
            tmp_path, level0_enabled=True, dry_run_verify_enabled=True
        )
        intent = _v2_intent(
            ExecutionAction.SCALE_BUDGET,
            risk=0.3,
            confidence=0.9,
            budget_amount_usd=100.0,  # 100 ∈ [50, 500)
        )
        decision = policy.evaluate(intent)
        assert decision.level == 1
        assert decision.outcome == OUTCOME_MANUAL
        assert decision.dry_run_required is True

    def test_medium_scale_level1_dry_run_disabled(self, tmp_path):
        """dry_run_verify_enabled=false 时 Level 1 不要求 dry_run。"""
        policy, _ = _v2_policy(
            tmp_path, level0_enabled=True, dry_run_verify_enabled=False
        )
        intent = _v2_intent(
            ExecutionAction.SCALE_BUDGET,
            risk=0.3,
            confidence=0.9,
            budget_amount_usd=100.0,
        )
        decision = policy.evaluate(intent)
        assert decision.level == 1
        assert decision.outcome == OUTCOME_MANUAL
        assert decision.dry_run_required is False


# ──────────────────────────────────────────────
# 场景 4: 大额 SCALE → Level 2 MANUAL
# ──────────────────────────────────────────────


class TestScenario4Level2LargeAmount:
    """Spec §10.1 场景 4。"""

    def test_large_scale_level2_manual(self, tmp_path):
        policy, _ = _v2_policy(tmp_path, level0_enabled=True)
        intent = _v2_intent(
            ExecutionAction.SCALE_BUDGET,
            risk=0.4,
            confidence=0.9,
            budget_amount_usd=600.0,  # >= 500
        )
        decision = policy.evaluate(intent)
        assert decision.level == 2
        assert decision.outcome == OUTCOME_MANUAL
        assert decision.dry_run_required is False


# ──────────────────────────────────────────────
# 场景 5: 超日累计 → Level 2 MANUAL
# ──────────────────────────────────────────────


class TestScenario5Level2CumulativeOverflow:
    """Spec §10.1 场景 5。"""

    def test_cumulative_overflow_level2(self, tmp_path):
        policy, tracker = _v2_policy(tmp_path, level0_enabled=True)
        # 预填当日累计 180（接近 200 上限）
        # 用 str(枚举) 作 key，与 policy.py get_cumulative 一致
        tracker.record(
            "p04_witch_merge",
            str(ExecutionAction.SCALE_BUDGET),
            180.0,
            "prior_action",
            day=date.today(),
        )
        # 再来一个 30 的动作 → 180+30=210 > 200 → Level 2
        intent = _v2_intent(
            ExecutionAction.SCALE_BUDGET,
            risk=0.1,
            confidence=0.95,
            budget_amount_usd=30.0,
        )
        decision = policy.evaluate(intent)
        assert decision.level == 2
        assert decision.outcome == OUTCOME_MANUAL
        assert "cumulative overflow" in decision.reason

    def test_cumulative_exact_limit_not_overflow(self, tmp_path):
        """累计 + 金额 == 上限不算溢出（用 > 而非 >=）。"""
        policy, tracker = _v2_policy(tmp_path, level0_enabled=True)
        tracker.record(
            "p04_witch_merge",
            str(ExecutionAction.SCALE_BUDGET),
            170.0,
            "prior_action",
            day=date.today(),
        )
        # 170 + 30 = 200 == 上限，不溢出 → Level 0
        intent = _v2_intent(
            ExecutionAction.SCALE_BUDGET,
            risk=0.1,
            confidence=0.95,
            budget_amount_usd=30.0,
        )
        decision = policy.evaluate(intent)
        assert decision.level == 0
        assert decision.outcome == OUTCOME_AUTO


# ──────────────────────────────────────────────
# 场景 6: CREATE_RELEASE → Level 2 ADMIN
# ──────────────────────────────────────────────


class TestScenario6Level2AdminRelease:
    """Spec §10.1 场景 6。"""

    def test_create_release_always_admin(self, tmp_path):
        policy, _ = _v2_policy(tmp_path, level0_enabled=True)
        intent = _v2_intent(
            ExecutionAction.CREATE_RELEASE,
            risk=0.05,
            confidence=0.99,
            budget_amount_usd=0.0,
            domain=ExecutionDomain.RELEASE,
        )
        decision = policy.evaluate(intent)
        assert decision.level == 2
        assert decision.outcome == OUTCOME_ADMIN
        assert decision.required_role == "ADMIN"


# ──────────────────────────────────────────────
# 场景 7: 未知动作 → Level 2 DENY
# ──────────────────────────────────────────────


class TestScenario7Level2DenyUnknown:
    """Spec §10.1 场景 7。"""

    def test_unknown_action_denied(self, tmp_path):
        policy, _ = _v2_policy(tmp_path, level0_enabled=True)
        intent = _v2_intent(
            ExecutionAction.PAUSE_CAMPAIGN,  # 用合法动作构造，再改 action
            risk=0.1,
            confidence=0.95,
            budget_amount_usd=0.0,
        )
        # 改成未知动作
        intent.action = "UNKNOWN_NONEXISTENT_ACTION"  # type: ignore[assignment]
        decision = policy.evaluate(intent)
        assert decision.level == 2
        assert decision.outcome == OUTCOME_DENY
        assert "not approvable" in decision.reason


# ──────────────────────────────────────────────
# 附加：ApprovalDecision V2 字段
# ──────────────────────────────────────────────


class TestApprovalDecisionV2Fields:
    """ApprovalDecision 新增 level / dry_run_required 字段。"""

    def test_default_level_is_2(self):
        """V1 兼容：默认 level=2（兜底最严格）。"""
        d = ApprovalDecision(
            outcome=OUTCOME_MANUAL, required_role="OPERATOR", reason="test"
        )
        assert d.level == 2
        assert d.dry_run_required is False

    def test_to_dict_includes_v2_fields(self):
        d = ApprovalDecision(
            outcome=OUTCOME_AUTO,
            required_role="SYSTEM",
            reason="Level 0",
            auto_approved=True,
            level=0,
            dry_run_required=False,
        )
        d_dict = d.to_dict()
        assert d_dict["level"] == 0
        assert d_dict["dry_run_required"] is False
        assert d_dict["auto_approved"] is True


# ──────────────────────────────────────────────
# 附加：LEVEL0_ALLOWLIST 内容
# ──────────────────────────────────────────────


class TestLevel0Allowlist:
    """Spec §6 LEVEL0_ALLOWLIST 内容验证。"""

    def test_pause_campaign_in_allowlist(self):
        """V2 新增：PAUSE_CAMPAIGN 在 Level 0 白名单。"""
        assert ExecutionAction.PAUSE_CAMPAIGN in LEVEL0_ALLOWLIST

    def test_scale_budget_in_allowlist(self):
        """V2 新增：SCALE_BUDGET 在 Level 0 白名单。"""
        assert ExecutionAction.SCALE_BUDGET in LEVEL0_ALLOWLIST

    def test_disable_network_in_allowlist(self):
        assert ExecutionAction.DISABLE_NETWORK in LEVEL0_ALLOWLIST

    def test_create_investigation_in_allowlist(self):
        assert ExecutionAction.CREATE_INVESTIGATION in LEVEL0_ALLOWLIST

    def test_create_release_not_in_allowlist(self):
        """ADMIN 动作不在 Level 0 白名单。"""
        assert ExecutionAction.CREATE_RELEASE not in LEVEL0_ALLOWLIST

    def test_create_release_in_admin_actions(self):
        assert ExecutionAction.CREATE_RELEASE in ADMIN_ACTIONS
