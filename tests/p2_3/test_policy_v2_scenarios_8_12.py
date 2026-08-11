"""P0 ApprovalGate V2 — policy 场景 8-12 + action_planner V2 测试。

Spec: docs/p0_approval_gate_v2_spec.md §10.1

本文件覆盖 Spec §10.1 测试矩阵的场景 8-12：
  8.  Level 0 关闭（level0_enabled=false） → MANUAL
  9.  Shadow 模式（shadow_mode=true）→ MANUAL (log only)
  10. dry_run 验证通过 → AUTO (promoted)（由 Day 6 DryRunVerifier 完整实现，此处测 policy 输出）
  11. dry_run 验证失败 → MANUAL (blocked)（同上）
  12. risk 过高 → Level 2 MANUAL

外加：
  - roles.py SYSTEM 角色扩展验证（V2 新增 PAUSE_CAMPAIGN/SCALE_BUDGET）
  - action_planner._compute_approval V2 金额维度验证
"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.execution.approval.config import ApprovalConfig
from src.execution.approval.policy import (
    LEVEL0_ALLOWLIST,
    OUTCOME_AUTO,
    OUTCOME_MANUAL,
    ApprovalPolicy,
)
from src.execution.approval.roles import (
    ApprovalRole,
    minimum_role_for,
    role_can,
)
from src.execution.approval.budget_window import BudgetWindowTracker
from src.execution.models import (
    ExecutionAction,
    ExecutionDomain,
    ExecutionIntent,
)
from scripts.action_planner import ActionPlanner


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
    """构造带 budget_amount_usd 的 V2 intent。"""
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
# 场景 8: Level 0 关闭 → MANUAL
# ──────────────────────────────────────────────


class TestScenario8Level0Disabled:
    """Spec §10.1 场景 8。"""

    def test_level0_disabled_small_pause_becomes_manual(self, tmp_path):
        """level0_enabled=false 时，原本 Level 0 的 PAUSE_CAMPAIGN 降级为 MANUAL。"""
        policy, _ = _v2_policy(tmp_path, level0_enabled=False)
        intent = _v2_intent(
            ExecutionAction.PAUSE_CAMPAIGN,
            risk=0.1,
            confidence=0.95,
            budget_amount_usd=0.0,
        )
        decision = policy.evaluate(intent)
        # PAUSE_CAMPAIGN 不在 V1 AUTO_ELIGIBLE_ACTIONS，所以 Level 0 关闭后走 manual
        assert decision.outcome == OUTCOME_MANUAL
        # 走 _v1_fallback_manual，level=1（语义：需人工，非 Level 0 自动）
        assert decision.level == 1
        assert decision.auto_approved is False

    def test_level0_disabled_disable_network_still_auto(self, tmp_path):
        """level0_enabled=false 时，DISABLE_NETWORK 仍走 V1 AUTO（V1 兼容）。"""
        policy, _ = _v2_policy(tmp_path, level0_enabled=False)
        intent = _v2_intent(
            ExecutionAction.DISABLE_NETWORK,
            risk=0.1,
            confidence=0.95,
            budget_amount_usd=0.0,
        )
        decision = policy.evaluate(intent)
        assert decision.outcome == OUTCOME_AUTO
        assert decision.level == 0
        assert decision.auto_approved is True


# ──────────────────────────────────────────────
# 场景 9: Shadow 模式 → MANUAL (log only)
# ──────────────────────────────────────────────


class TestScenario9ShadowMode:
    """Spec §10.1 场景 9。"""

    def test_shadow_mode_pause_campaign_manual(self, tmp_path):
        """shadow_mode=true 时，Level 0 决策记 MANUAL（不执行）。"""
        policy, _ = _v2_policy(
            tmp_path, level0_enabled=True, shadow_mode=True
        )
        intent = _v2_intent(
            ExecutionAction.PAUSE_CAMPAIGN,
            risk=0.1,
            confidence=0.95,
            budget_amount_usd=0.0,
        )
        decision = policy.evaluate(intent)
        assert decision.outcome == OUTCOME_MANUAL
        assert decision.level == 0
        assert decision.auto_approved is False
        assert "shadow" in decision.reason.lower()

    def test_shadow_mode_scale_budget_manual(self, tmp_path):
        """shadow_mode=true 时，小额 SCALE 也走 MANUAL（log only）。"""
        policy, _ = _v2_policy(
            tmp_path, level0_enabled=True, shadow_mode=True
        )
        intent = _v2_intent(
            ExecutionAction.SCALE_BUDGET,
            risk=0.2,
            confidence=0.92,
            budget_amount_usd=30.0,
        )
        decision = policy.evaluate(intent)
        assert decision.outcome == OUTCOME_MANUAL
        assert decision.level == 0
        assert "shadow" in decision.reason.lower()


# ──────────────────────────────────────────────
# 场景 10: dry_run 验证通过 → policy 输出 dry_run_required（升 AUTO 由 executor 完成）
# ──────────────────────────────────────────────


class TestScenario10DryRunRequired:
    """Spec §10.1 场景 10：policy 输出 dry_run_required=true。

    注：实际的 dry_run 验证 + 升 AUTO 由 Day 6 的 DryRunVerifier 在
    action_executor 层完成。policy 只负责标记 dry_run_required。
    """

    def test_medium_scale_dry_run_required_true(self, tmp_path):
        """中额 SCALE → Level 1 + dry_run_required=True。"""
        policy, _ = _v2_policy(
            tmp_path, level0_enabled=True, dry_run_verify_enabled=True
        )
        intent = _v2_intent(
            ExecutionAction.SCALE_BUDGET,
            risk=0.3,
            confidence=0.9,
            budget_amount_usd=100.0,  # 中额
        )
        decision = policy.evaluate(intent)
        assert decision.level == 1
        assert decision.dry_run_required is True
        assert decision.outcome == OUTCOME_MANUAL  # policy 仍标 MANUAL，升 AUTO 由 executor


# ──────────────────────────────────────────────
# 场景 11: dry_run 验证失败 → policy 仍输出 MANUAL
# ──────────────────────────────────────────────


class TestScenario11DryRunFailed:
    """Spec §10.1 场景 11：dry_run 失败时 policy 已输出 MANUAL，executor 阻塞。"""

    def test_medium_scale_dry_run_required_blocks_at_manual(self, tmp_path):
        """中额 SCALE + dry_run_required=True 时，policy 输出 MANUAL（等 executor 验证）。"""
        policy, _ = _v2_policy(
            tmp_path, level0_enabled=True, dry_run_verify_enabled=True
        )
        intent = _v2_intent(
            ExecutionAction.SCALE_BUDGET,
            risk=0.3,
            confidence=0.9,
            budget_amount_usd=100.0,
        )
        decision = policy.evaluate(intent)
        # policy 层面：MANUAL + dry_run_required
        # executor 层面：dry_run 失败 → 保持 MANUAL（不升 AUTO）
        assert decision.outcome == OUTCOME_MANUAL
        assert decision.dry_run_required is True
        assert decision.auto_approved is False


# ──────────────────────────────────────────────
# 场景 12: risk 过高 → Level 2 MANUAL
# ──────────────────────────────────────────────


class TestScenario12HighRisk:
    """Spec §10.1 场景 12。"""

    def test_high_risk_small_amount_level2(self, tmp_path):
        """risk >= level1_max_risk（默认 0.6）→ Level 2，即使金额小。"""
        policy, _ = _v2_policy(tmp_path, level0_enabled=True)
        intent = _v2_intent(
            ExecutionAction.SCALE_BUDGET,
            risk=0.7,  # >= 0.6
            confidence=0.95,
            budget_amount_usd=30.0,  # 小额
        )
        decision = policy.evaluate(intent)
        assert decision.level == 2
        assert decision.outcome == OUTCOME_MANUAL
        assert "risk" in decision.reason.lower()

    def test_medium_risk_small_amount_level1(self, tmp_path):
        """risk ∈ [auto_max_risk, level1_max_risk) → Level 1。"""
        policy, _ = _v2_policy(
            tmp_path, level0_enabled=True, dry_run_verify_enabled=False
        )
        intent = _v2_intent(
            ExecutionAction.SCALE_BUDGET,
            risk=0.4,  # ∈ [0.3, 0.6)
            confidence=0.95,
            budget_amount_usd=30.0,
        )
        decision = policy.evaluate(intent)
        assert decision.level == 1
        assert decision.outcome == OUTCOME_MANUAL


# ──────────────────────────────────────────────
# roles.py V1 行为保留验证（V2 不改 roles.py，仅 policy.py 扩展）
# ──────────────────────────────────────────────


class TestRolesV1Preserved:
    """V2 不修改 roles.py（保持 V1 向后兼容）。

    Policy 层的 Level 0 扩展（PAUSE_CAMPAIGN/SCALE_BUDGET 走 AUTO）
    由 policy.py 直接输出 required_role=SYSTEM，不经过 role_can 校验。
    因此 roles.py 的 SYSTEM 角色仍保持 V1 行为。
    """

    def test_system_cannot_pause_campaign(self):
        """V1 行为：SYSTEM 角色不能批准 PAUSE_CAMPAIGN（仍由 policy 层放行）。"""
        assert not role_can(ApprovalRole.SYSTEM, ExecutionAction.PAUSE_CAMPAIGN)

    def test_system_cannot_scale_budget(self):
        """V1 行为：SYSTEM 角色不能批准 SCALE_BUDGET。"""
        assert not role_can(ApprovalRole.SYSTEM, ExecutionAction.SCALE_BUDGET)

    def test_system_cannot_create_release(self):
        """ADMIN 动作仍不允许 SYSTEM。"""
        assert not role_can(ApprovalRole.SYSTEM, ExecutionAction.CREATE_RELEASE)

    def test_minimum_role_for_pause_campaign_is_operator(self):
        """V1 行为保留：PAUSE_CAMPAIGN 最低角色是 OPERATOR。"""
        assert minimum_role_for(ExecutionAction.PAUSE_CAMPAIGN) == ApprovalRole.OPERATOR

    def test_minimum_role_for_scale_budget_is_manager(self):
        """V1 行为保留：SCALE_BUDGET 最低角色是 MANAGER。"""
        assert minimum_role_for(ExecutionAction.SCALE_BUDGET) == ApprovalRole.MANAGER


# ──────────────────────────────────────────────
# action_planner._compute_approval V2 测试
# ──────────────────────────────────────────────


class TestComputeApprovalV2:
    """Spec §4.1：_compute_approval 引入 budget_impact_usd 维度。"""

    @pytest.fixture
    def planner(self):
        return ActionPlanner()

    # V1 兼容路径（budget_impact_usd=None）

    def test_v1_path_small_impact_auto(self, planner):
        """V1：小 impact（<WARN 50）→ Level 0。"""
        requires, level = planner._compute_approval(10.0, "low")
        assert requires is False
        assert level == 0

    def test_v1_path_medium_impact_confirm(self, planner):
        """V1：中 impact（>=APPROVAL 200, <BLOCK 500）→ Level 1。"""
        requires, level = planner._compute_approval(250.0, "medium")
        assert requires is True
        assert level == 1

    def test_v1_path_large_impact_approval(self, planner):
        """V1：大 impact（>=BLOCK 500）→ Level 2。"""
        requires, level = planner._compute_approval(600.0, "high")
        assert requires is True
        assert level == 2

    # V2 路径（budget_impact_usd 提供）

    def test_v2_small_amount_low_risk_auto(self, planner):
        """V2：<$50 + 低风险 → Level 0。"""
        requires, level = planner._compute_approval(
            0.0, "low", budget_impact_usd=30.0
        )
        assert requires is False
        assert level == 0

    def test_v2_small_amount_high_risk_level1(self, planner):
        """V2：<$50 但 high risk → Level 1（risk 升级）。"""
        requires, level = planner._compute_approval(
            0.0, "high", budget_impact_usd=30.0
        )
        assert requires is True
        assert level == 1

    def test_v2_medium_amount_level1(self, planner):
        """V2：$50-$500 → Level 1。"""
        requires, level = planner._compute_approval(
            0.0, "low", budget_impact_usd=200.0
        )
        assert requires is True
        assert level == 1

    def test_v2_large_amount_level2(self, planner):
        """V2：>=$500 → Level 2。"""
        requires, level = planner._compute_approval(
            0.0, "low", budget_impact_usd=600.0
        )
        assert requires is True
        assert level == 2

    def test_v2_negative_amount_absoluted(self, planner):
        """V2：负金额取绝对值。"""
        requires_pos, level_pos = planner._compute_approval(
            0.0, "low", budget_impact_usd=30.0
        )
        requires_neg, level_neg = planner._compute_approval(
            0.0, "low", budget_impact_usd=-30.0
        )
        assert (requires_pos, level_pos) == (requires_neg, level_neg)

    def test_v2_critical_risk_level1(self, planner):
        """V2：critical risk → Level 1（即使小额）。"""
        requires, level = planner._compute_approval(
            0.0, "critical", budget_impact_usd=30.0
        )
        assert requires is True
        assert level == 1

    def test_v2_threshold_boundary_50(self, planner):
        """V2：$50 边界 → Level 1（>= 触发）。"""
        requires, level = planner._compute_approval(
            0.0, "low", budget_impact_usd=50.0
        )
        assert requires is True
        assert level == 1

    def test_v2_threshold_boundary_500(self, planner):
        """V2：$500 边界 → Level 2（>= 触发）。"""
        requires, level = planner._compute_approval(
            0.0, "low", budget_impact_usd=500.0
        )
        assert requires is True
        assert level == 2

    def test_v2_zero_amount_low_risk_auto(self, planner):
        """V2：$0 + low risk → Level 0（如 PAUSE_CAMPAIGN）。"""
        requires, level = planner._compute_approval(
            0.0, "low", budget_impact_usd=0.0
        )
        assert requires is False
        assert level == 0
