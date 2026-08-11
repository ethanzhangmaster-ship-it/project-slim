"""E15.0.3 Safety Governor — 测试套件.

覆盖:
  - SafetyDecision: creation, to_dict, approved/not approved, risk levels
  - RiskLevel: 枚举值
  - ActionType: 枚举值
  - BudgetChangePolicy: small/medium/large change, zero budget, equal budgets
  - NewCampaignPolicy: requires approval, auto-approve mode
  - AutoPausePolicy: low ROAS triggers pause, normal ROAS no pause, high risk
  - CooldownPolicy: first action allowed, within cooldown blocked, after cooldown
  - SafetyGovernor: evaluate all action types, state management
  - Integration: budget change + cooldown, pause + cooldown
  - Edge cases: zero budget, negative budget, empty params, missing campaign_id
"""

import pytest
from datetime import datetime, timezone, timedelta
from enum import Enum

from market_ops.creative_vision_runtime.growth_runtime.safety import (
    ActionType,
    AutoPausePolicy,
    BudgetChangePolicy,
    CooldownPolicy,
    NewCampaignPolicy,
    RiskLevel,
    SafetyDecision,
    SafetyGovernor,
)


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════


def make_governor(
    budget_policy: BudgetChangePolicy | None = None,
    campaign_policy: NewCampaignPolicy | None = None,
    pause_policy: AutoPausePolicy | None = None,
    cooldown_policy: CooldownPolicy | None = None,
) -> SafetyGovernor:
    return SafetyGovernor(
        budget_policy=budget_policy,
        campaign_policy=campaign_policy,
        pause_policy=pause_policy,
        cooldown_policy=cooldown_policy,
    )


def past_time(days_ago: int) -> str:
    """生成 days_ago 天前的 ISO 时间戳."""
    t = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return t.isoformat()


# ═══════════════════════════════════════════════════════════════
# Test SafetyDecision
# ═══════════════════════════════════════════════════════════════


class TestSafetyDecision:
    """SafetyDecision 数据类测试."""

    def test_creation_defaults(self):
        d = SafetyDecision()
        assert d.approved is False
        assert d.risk_level == RiskLevel.LOW
        assert d.reason == ""
        assert d.requires_manual is False
        assert d.constraints == {}
        assert d.decision_id.startswith("safety_")
        assert len(d.decision_id) > 7

    def test_creation_custom_values(self):
        d = SafetyDecision(
            approved=True,
            risk_level=RiskLevel.HIGH,
            reason="Test reason",
            requires_manual=True,
            constraints={"max_change": 0.2},
        )
        assert d.approved is True
        assert d.risk_level == RiskLevel.HIGH
        assert d.reason == "Test reason"
        assert d.requires_manual is True
        assert d.constraints == {"max_change": 0.2}

    def test_to_dict_basic(self):
        d = SafetyDecision(approved=True, risk_level=RiskLevel.MEDIUM, reason="OK")
        result = d.to_dict()
        assert result["approved"] is True
        assert result["risk_level"] == "medium"
        assert result["reason"] == "OK"
        assert result["requires_manual"] is False
        assert result["constraints"] == {}
        assert "decision_id" in result
        assert "timestamp" in result

    def test_to_dict_with_constraints(self):
        d = SafetyDecision(
            approved=False,
            risk_level=RiskLevel.CRITICAL,
            reason="Blocked",
            constraints={"max_allowed_change": 0.2, "cooldown_end": "2026-01-01T00:00:00"},
        )
        result = d.to_dict()
        assert result["approved"] is False
        assert result["risk_level"] == "critical"
        assert result["constraints"] == {
            "max_allowed_change": 0.2,
            "cooldown_end": "2026-01-01T00:00:00",
        }

    def test_approved_true(self):
        d = SafetyDecision(approved=True)
        assert d.approved is True

    def test_approved_false(self):
        d = SafetyDecision(approved=False)
        assert d.approved is False

    def test_risk_level_low(self):
        d = SafetyDecision(risk_level=RiskLevel.LOW)
        assert d.risk_level == RiskLevel.LOW

    def test_risk_level_high(self):
        d = SafetyDecision(risk_level=RiskLevel.HIGH)
        assert d.risk_level == RiskLevel.HIGH

    def test_requires_manual_flag(self):
        d = SafetyDecision(requires_manual=True)
        assert d.requires_manual is True

    def test_decision_id_unique(self):
        d1 = SafetyDecision()
        d2 = SafetyDecision()
        assert d1.decision_id != d2.decision_id

    def test_timestamp_present(self):
        d = SafetyDecision()
        assert d.timestamp
        # 应该是有效的 ISO 时间戳
        parsed = datetime.fromisoformat(d.timestamp)
        assert isinstance(parsed, datetime)


# ═══════════════════════════════════════════════════════════════
# Test RiskLevel
# ═══════════════════════════════════════════════════════════════


class TestRiskLevel:
    """RiskLevel 枚举测试."""

    def test_low_value(self):
        assert RiskLevel.LOW.value == "low"

    def test_medium_value(self):
        assert RiskLevel.MEDIUM.value == "medium"

    def test_high_value(self):
        assert RiskLevel.HIGH.value == "high"

    def test_critical_value(self):
        assert RiskLevel.CRITICAL.value == "critical"

    def test_all_values(self):
        values = {r.value for r in RiskLevel}
        assert values == {"low", "medium", "high", "critical"}

    def test_string_construction(self):
        assert RiskLevel("low") == RiskLevel.LOW
        assert RiskLevel("high") == RiskLevel.HIGH


# ═══════════════════════════════════════════════════════════════
# Test ActionType
# ═══════════════════════════════════════════════════════════════


class TestActionType:
    """ActionType 枚举测试."""

    def test_budget_change(self):
        assert ActionType.BUDGET_CHANGE.value == "budget_change"

    def test_create_campaign(self):
        assert ActionType.CREATE_CAMPAIGN.value == "create_campaign"

    def test_pause_campaign(self):
        assert ActionType.PAUSE_CAMPAIGN.value == "pause_campaign"

    def test_resume_campaign(self):
        assert ActionType.RESUME_CAMPAIGN.value == "resume_campaign"

    def test_upload_creative(self):
        assert ActionType.UPLOAD_CREATIVE.value == "upload_creative"

    def test_mutate_creative(self):
        assert ActionType.MUTATE_CREATIVE.value == "mutate_creative"

    def test_rollback(self):
        assert ActionType.ROLLBACK.value == "rollback"

    def test_all_action_types(self):
        values = {a.value for a in ActionType}
        assert values == {
            "budget_change",
            "create_campaign",
            "pause_campaign",
            "resume_campaign",
            "upload_creative",
            "mutate_creative",
            "rollback",
        }


# ═══════════════════════════════════════════════════════════════
# Test BudgetChangePolicy
# ═══════════════════════════════════════════════════════════════


class TestBudgetChangePolicy:
    """BudgetChangePolicy 测试."""

    def test_small_change_approved(self):
        """变化 < 15%: 直接批准."""
        policy = BudgetChangePolicy(max_change_pct=0.20, require_approval_above_pct=0.15)
        decision = policy.evaluate(current_budget=1000, new_budget=1100)  # 10%
        assert decision.approved is True
        assert decision.risk_level == RiskLevel.LOW
        assert decision.requires_manual is False

    def test_medium_change_requires_approval(self):
        """变化 15-20%: 批准但需要人工审批."""
        policy = BudgetChangePolicy(max_change_pct=0.20, require_approval_above_pct=0.15)
        decision = policy.evaluate(current_budget=1000, new_budget=1180)  # 18%
        assert decision.approved is True
        assert decision.risk_level == RiskLevel.MEDIUM
        assert decision.requires_manual is True

    def test_large_change_blocked(self):
        """变化 > 20%: 拒绝."""
        policy = BudgetChangePolicy(max_change_pct=0.20, require_approval_above_pct=0.15)
        decision = policy.evaluate(current_budget=1000, new_budget=1300)  # 30%
        assert decision.approved is False
        assert decision.risk_level == RiskLevel.HIGH

    def test_zero_budget_blocked(self):
        """当前预算为 0: 拒绝."""
        policy = BudgetChangePolicy()
        decision = policy.evaluate(current_budget=0, new_budget=100)
        assert decision.approved is False
        assert decision.risk_level == RiskLevel.HIGH

    def test_equal_budgets_approved(self):
        """预算相等: 变化 0%."""
        policy = BudgetChangePolicy()
        decision = policy.evaluate(current_budget=1000, new_budget=1000)
        assert decision.approved is True
        assert decision.risk_level == RiskLevel.LOW

    def test_negative_budget_blocked(self):
        """负预算: 拒绝."""
        policy = BudgetChangePolicy()
        decision = policy.evaluate(current_budget=-100, new_budget=100)
        assert decision.approved is False
        assert decision.risk_level == RiskLevel.HIGH

    def test_exactly_15_percent_boundary(self):
        """恰好 15%: 不触发审批 (strict >)."""
        policy = BudgetChangePolicy(max_change_pct=0.20, require_approval_above_pct=0.15)
        decision = policy.evaluate(current_budget=1000, new_budget=1150)
        assert decision.approved is True
        assert decision.risk_level == RiskLevel.LOW
        assert decision.requires_manual is False

    def test_exactly_20_percent_boundary(self):
        """恰好 20%: 不触发 > 20% 拒绝."""
        policy = BudgetChangePolicy(max_change_pct=0.20, require_approval_above_pct=0.15)
        decision = policy.evaluate(current_budget=1000, new_budget=1200)
        assert decision.approved is True
        assert decision.risk_level == RiskLevel.MEDIUM

    def test_budget_decrease_medium(self):
        """预算减少 15-20%: 需要审批."""
        policy = BudgetChangePolicy(max_change_pct=0.20, require_approval_above_pct=0.15)
        decision = policy.evaluate(current_budget=1000, new_budget=830)  # -17%
        assert decision.approved is True
        assert decision.risk_level == RiskLevel.MEDIUM

    def test_budget_decrease_large(self):
        """预算减少 > 20%: 拒绝."""
        policy = BudgetChangePolicy(max_change_pct=0.20, require_approval_above_pct=0.15)
        decision = policy.evaluate(current_budget=1000, new_budget=700)  # -30%
        assert decision.approved is False
        assert decision.risk_level == RiskLevel.HIGH

    def test_custom_max_change_pct(self):
        """自定义 max_change_pct=0.10."""
        policy = BudgetChangePolicy(max_change_pct=0.10, require_approval_above_pct=0.05)
        decision = policy.evaluate(current_budget=1000, new_budget=1150)  # 15% > 10%
        assert decision.approved is False
        assert decision.risk_level == RiskLevel.HIGH

    def test_custom_require_approval_pct(self):
        """自定义 require_approval_above_pct=0.05."""
        policy = BudgetChangePolicy(max_change_pct=0.20, require_approval_above_pct=0.05)
        decision = policy.evaluate(current_budget=1000, new_budget=1080)  # 8% > 5%
        assert decision.approved is True
        assert decision.risk_level == RiskLevel.MEDIUM
        assert decision.requires_manual is True


# ═══════════════════════════════════════════════════════════════
# Test NewCampaignPolicy
# ═══════════════════════════════════════════════════════════════


class TestNewCampaignPolicy:
    """NewCampaignPolicy 测试."""

    def test_requires_approval_default(self):
        """默认需要人工审批."""
        policy = NewCampaignPolicy()
        decision = policy.evaluate()
        assert decision.approved is True
        assert decision.risk_level == RiskLevel.MEDIUM
        assert decision.requires_manual is True
        assert "human approval" in decision.reason

    def test_auto_approve_mode(self):
        """关闭审批: 自动批准."""
        policy = NewCampaignPolicy(require_approval=False)
        decision = policy.evaluate()
        assert decision.approved is True
        assert decision.risk_level == RiskLevel.LOW
        assert decision.requires_manual is False
        assert "auto-approved" in decision.reason

    def test_explicit_require_approval(self):
        """显式设置 require_approval=True."""
        policy = NewCampaignPolicy(require_approval=True)
        decision = policy.evaluate()
        assert decision.requires_manual is True
        assert decision.risk_level == RiskLevel.MEDIUM


# ═══════════════════════════════════════════════════════════════
# Test AutoPausePolicy
# ═══════════════════════════════════════════════════════════════


class TestAutoPausePolicy:
    """AutoPausePolicy 测试."""

    def test_low_roas_triggers_pause(self):
        """ROAS 低于阈值: 允许暂停."""
        policy = AutoPausePolicy(roas_threshold=0.5)
        decision = policy.evaluate(roas=0.3, risk_level=RiskLevel.LOW)
        assert decision.approved is True
        assert decision.risk_level == RiskLevel.MEDIUM
        assert "ROAS" in decision.reason

    def test_normal_roas_no_pause(self):
        """ROAS 正常: 不允许暂停."""
        policy = AutoPausePolicy(roas_threshold=0.5)
        decision = policy.evaluate(roas=0.8, risk_level=RiskLevel.LOW)
        assert decision.approved is False
        assert decision.risk_level == RiskLevel.LOW
        assert "not justified" in decision.reason

    def test_high_risk_triggers_pause(self):
        """高风险: 允许暂停 (即使 ROAS 正常)."""
        policy = AutoPausePolicy(roas_threshold=0.5)
        decision = policy.evaluate(roas=1.0, risk_level=RiskLevel.HIGH)
        assert decision.approved is True
        assert "Risk level" in decision.reason

    def test_low_risk_no_pause(self):
        """低风险 + 正常 ROAS: 不允许暂停."""
        policy = AutoPausePolicy()
        decision = policy.evaluate(roas=1.0, risk_level=RiskLevel.LOW)
        assert decision.approved is False

    def test_critical_risk_triggers_pause(self):
        """CRITICAL 风险: 允许暂停."""
        policy = AutoPausePolicy()
        decision = policy.evaluate(roas=1.0, risk_level=RiskLevel.CRITICAL)
        assert decision.approved is True

    def test_both_low_roas_and_high_risk(self):
        """低 ROAS + 高风险: 两个原因都出现."""
        policy = AutoPausePolicy(roas_threshold=0.5)
        decision = policy.evaluate(roas=0.2, risk_level=RiskLevel.HIGH)
        assert decision.approved is True
        assert "ROAS" in decision.reason
        assert "Risk level" in decision.reason

    def test_exactly_threshold_roas(self):
        """ROAS 恰好等于阈值: 不触发."""
        policy = AutoPausePolicy(roas_threshold=0.5)
        decision = policy.evaluate(roas=0.5, risk_level=RiskLevel.LOW)
        assert decision.approved is False

    def test_custom_roas_threshold(self):
        """自定义 ROAS 阈值."""
        policy = AutoPausePolicy(roas_threshold=0.3)
        decision = policy.evaluate(roas=0.4, risk_level=RiskLevel.LOW)
        assert decision.approved is False  # 0.4 >= 0.3


# ═══════════════════════════════════════════════════════════════
# Test CooldownPolicy
# ═══════════════════════════════════════════════════════════════


class TestCooldownPolicy:
    """CooldownPolicy 测试."""

    def test_first_action_allowed(self):
        """无上次操作: 允许."""
        policy = CooldownPolicy()
        decision = policy.evaluate(campaign_id="camp_001", last_action_time=None)
        assert decision.approved is True
        assert decision.risk_level == RiskLevel.LOW
        assert "No previous action" in decision.reason

    def test_within_cooldown_blocked(self):
        """冷却期内: 拒绝."""
        policy = CooldownPolicy(cooldown_days=7)
        last_time = past_time(days_ago=1)  # 1 天前
        decision = policy.evaluate(campaign_id="camp_001", last_action_time=last_time)
        assert decision.approved is False
        assert decision.risk_level == RiskLevel.MEDIUM
        assert "in cooldown" in decision.reason

    def test_after_cooldown_allowed(self):
        """冷却期过后: 允许."""
        policy = CooldownPolicy(cooldown_days=7)
        last_time = past_time(days_ago=10)  # 10 天前
        decision = policy.evaluate(campaign_id="camp_001", last_action_time=last_time)
        assert decision.approved is True
        assert decision.risk_level == RiskLevel.LOW
        assert "Cooldown passed" in decision.reason

    def test_no_last_action_empty_string(self):
        """空字符串 last_action_time: 视为无上次操作."""
        policy = CooldownPolicy()
        decision = policy.evaluate(campaign_id="camp_001", last_action_time="")
        assert decision.approved is True
        assert "No previous action" in decision.reason

    def test_invalid_timestamp_allowed(self):
        """无效时间戳: 容错, 允许."""
        policy = CooldownPolicy()
        decision = policy.evaluate(campaign_id="camp_001", last_action_time="not-a-timestamp")
        assert decision.approved is True
        assert "Cooldown passed" in decision.reason

    def test_custom_cooldown_days(self):
        """自定义冷却天数."""
        policy = CooldownPolicy(cooldown_days=3)
        last_time = past_time(days_ago=2)  # 2 天前, 在 3 天冷却期内
        decision = policy.evaluate(campaign_id="camp_001", last_action_time=last_time)
        assert decision.approved is False
        assert "in cooldown" in decision.reason

    def test_cooldown_constraints_has_cooldown_end(self):
        """冷却期决策包含 cooldown_end 约束."""
        policy = CooldownPolicy()
        last_time = past_time(days_ago=1)
        decision = policy.evaluate(campaign_id="camp_001", last_action_time=last_time)
        assert "cooldown_end" in decision.constraints

    def test_same_day_within_cooldown(self):
        """同一天操作: 在冷却期内."""
        policy = CooldownPolicy(cooldown_days=7)
        last_time = datetime.now(timezone.utc).isoformat()
        decision = policy.evaluate(campaign_id="camp_001", last_action_time=last_time)
        assert decision.approved is False


# ═══════════════════════════════════════════════════════════════
# Test SafetyGovernor — evaluate
# ═══════════════════════════════════════════════════════════════


class TestSafetyGovernorEvaluate:
    """SafetyGovernor.evaluate 测试."""

    def test_evaluate_budget_change_approved(self):
        """评估预算变化: 小变化, 批准."""
        gov = make_governor()
        decision = gov.evaluate(
            action_type=ActionType.BUDGET_CHANGE,
            params={"current_budget": 1000, "new_budget": 1100},
            campaign_id="camp_001",
        )
        assert decision.approved is True
        assert decision.risk_level == RiskLevel.LOW

    def test_evaluate_budget_change_blocked(self):
        """评估预算变化: 大变化, 拒绝."""
        gov = make_governor()
        decision = gov.evaluate(
            action_type=ActionType.BUDGET_CHANGE,
            params={"current_budget": 1000, "new_budget": 1500},
            campaign_id="camp_001",
        )
        assert decision.approved is False
        assert decision.risk_level == RiskLevel.HIGH

    def test_evaluate_create_campaign(self):
        """评估创建 Campaign: 需要审批."""
        gov = make_governor()
        decision = gov.evaluate(
            action_type=ActionType.CREATE_CAMPAIGN,
            campaign_id="camp_001",
        )
        assert decision.approved is True
        assert decision.risk_level == RiskLevel.MEDIUM
        assert decision.requires_manual is True

    def test_evaluate_pause_campaign_low_roas(self):
        """评估暂停: 低 ROAS, 允许 (governor 返回 cooldown 结果)."""
        gov = make_governor()
        decision = gov.evaluate(
            action_type=ActionType.PAUSE_CAMPAIGN,
            params={"roas": 0.3},
            campaign_id="camp_001",
        )
        assert decision.approved is True
        assert decision.risk_level == RiskLevel.LOW

    def test_evaluate_pause_campaign_normal_roas(self):
        """评估暂停: 正常 ROAS, 不允许."""
        gov = make_governor()
        decision = gov.evaluate(
            action_type=ActionType.PAUSE_CAMPAIGN,
            params={"roas": 1.0},
            campaign_id="camp_001",
        )
        assert decision.approved is False

    def test_evaluate_pause_campaign_high_risk(self):
        """评估暂停: 高风险, 允许."""
        gov = make_governor()
        decision = gov.evaluate(
            action_type=ActionType.PAUSE_CAMPAIGN,
            params={"roas": 1.0, "risk_level": RiskLevel.HIGH},
            campaign_id="camp_001",
        )
        assert decision.approved is True

    def test_evaluate_pause_campaign_risk_string(self):
        """评估暂停: risk_level 为字符串."""
        gov = make_governor()
        decision = gov.evaluate(
            action_type=ActionType.PAUSE_CAMPAIGN,
            params={"roas": 0.3, "risk_level": "high"},
            campaign_id="camp_001",
        )
        assert decision.approved is True

    def test_evaluate_pause_campaign_invalid_risk_string(self):
        """评估暂停: 无效 risk_level 字符串, 容错为 LOW."""
        gov = make_governor()
        decision = gov.evaluate(
            action_type=ActionType.PAUSE_CAMPAIGN,
            params={"roas": 0.3, "risk_level": "invalid_risk"},
            campaign_id="camp_001",
        )
        assert decision.approved is True

    def test_evaluate_resume_campaign(self):
        """评估恢复 Campaign."""
        gov = make_governor()
        decision = gov.evaluate(
            action_type=ActionType.RESUME_CAMPAIGN,
            campaign_id="camp_001",
        )
        assert decision.approved is True
        assert decision.risk_level == RiskLevel.LOW

    def test_evaluate_resume_campaign_no_id(self):
        """评估恢复: 无 campaign_id."""
        gov = make_governor()
        decision = gov.evaluate(
            action_type=ActionType.RESUME_CAMPAIGN,
        )
        assert decision.approved is True
        assert "cooldown not applicable" in decision.reason

    def test_evaluate_upload_creative(self):
        """评估上传素材: 低风险, 自动批准."""
        gov = make_governor()
        decision = gov.evaluate(
            action_type=ActionType.UPLOAD_CREATIVE,
            campaign_id="camp_001",
        )
        assert decision.approved is True
        assert decision.risk_level == RiskLevel.LOW
        assert "low risk" in decision.reason

    def test_evaluate_mutate_creative(self):
        """评估变异素材: 低风险, 自动批准."""
        gov = make_governor()
        decision = gov.evaluate(
            action_type=ActionType.MUTATE_CREATIVE,
            campaign_id="camp_001",
        )
        assert decision.approved is True
        assert decision.risk_level == RiskLevel.LOW

    def test_evaluate_rollback(self):
        """评估回滚: 总是允许."""
        gov = make_governor()
        decision = gov.evaluate(
            action_type=ActionType.ROLLBACK,
            campaign_id="camp_001",
        )
        assert decision.approved is True
        assert decision.risk_level == RiskLevel.MEDIUM
        assert "always allowed" in decision.reason

    def test_evaluate_unknown_action(self):
        """评估未知动作类型: 拒绝."""
        gov = make_governor()

        class FakeAction(str, Enum):
            UNKNOWN = "unknown"

        decision = gov.evaluate(
            action_type=FakeAction.UNKNOWN,
            campaign_id="camp_001",
        )
        assert decision.approved is False
        assert decision.risk_level == RiskLevel.HIGH
        assert "Unknown" in decision.reason

    def test_evaluate_empty_params(self):
        """空参数: 预算变化, 视为 0."""
        gov = make_governor()
        decision = gov.evaluate(
            action_type=ActionType.BUDGET_CHANGE,
            params={},
            campaign_id="camp_001",
        )
        assert decision.approved is False
        assert decision.risk_level == RiskLevel.HIGH

    def test_evaluate_missing_campaign_id(self):
        """缺少 campaign_id: 预算变化跳过冷却检查."""
        gov = make_governor()
        decision = gov.evaluate(
            action_type=ActionType.BUDGET_CHANGE,
            params={"current_budget": 1000, "new_budget": 1100},
        )
        assert decision.approved is True
        assert decision.risk_level == RiskLevel.LOW

    def test_evaluate_budget_change_with_defaults(self):
        """不传 params: 默认空 dict."""
        gov = make_governor()
        decision = gov.evaluate(
            action_type=ActionType.BUDGET_CHANGE,
            campaign_id="camp_001",
        )
        assert decision.approved is False


# ═══════════════════════════════════════════════════════════════
# Test SafetyGovernor — State
# ═══════════════════════════════════════════════════════════════


class TestSafetyGovernorState:
    """SafetyGovernor 状态管理测试."""

    def test_record_action(self):
        gov = make_governor()
        gov.record_action("camp_001")
        last = gov.get_last_action("camp_001")
        assert last is not None
        parsed = datetime.fromisoformat(last)
        assert isinstance(parsed, datetime)

    def test_get_last_action_none(self):
        gov = make_governor()
        assert gov.get_last_action("camp_001") is None

    def test_get_last_action_after_record(self):
        gov = make_governor()
        gov.record_action("camp_001")
        assert gov.get_last_action("camp_001") is not None

    def test_reset_cooldown(self):
        gov = make_governor()
        gov.record_action("camp_001")
        assert gov.get_last_action("camp_001") is not None
        gov.reset_cooldown("camp_001")
        assert gov.get_last_action("camp_001") is None

    def test_reset_cooldown_nonexistent(self):
        """reset 不存在的 campaign: 不报错."""
        gov = make_governor()
        gov.reset_cooldown("nonexistent")
        # 不应抛出异常

    def test_get_summary(self):
        gov = make_governor()
        summary = gov.get_summary()
        assert "budget_max_change_pct" in summary
        assert "campaign_require_approval" in summary
        assert "pause_roas_threshold" in summary
        assert "cooldown_days" in summary
        assert "tracked_campaigns" in summary
        assert summary["budget_max_change_pct"] == 0.20
        assert summary["campaign_require_approval"] is True
        assert summary["pause_roas_threshold"] == 0.5
        assert summary["cooldown_days"] == 7
        assert summary["tracked_campaigns"] == 0

    def test_get_summary_after_actions(self):
        gov = make_governor()
        gov.record_action("camp_001")
        gov.record_action("camp_002")
        summary = gov.get_summary()
        assert summary["tracked_campaigns"] == 2

    def test_multiple_campaigns_tracked(self):
        gov = make_governor()
        gov.record_action("camp_A")
        gov.record_action("camp_B")
        gov.record_action("camp_C")
        assert gov.get_last_action("camp_A") is not None
        assert gov.get_last_action("camp_B") is not None
        assert gov.get_last_action("camp_C") is not None
        assert gov.get_last_action("camp_D") is None

    def test_overwrite_last_action(self):
        """同一 campaign 多次记录: 覆盖 (时间戳可能相同)."""
        gov = make_governor()
        gov.record_action("camp_001")
        first = gov.get_last_action("camp_001")
        assert first is not None
        gov.record_action("camp_001")
        second = gov.get_last_action("camp_001")
        assert second is not None
        # 两次记录都是有效的 ISO 时间戳
        assert datetime.fromisoformat(first)
        assert datetime.fromisoformat(second)


# ═══════════════════════════════════════════════════════════════
# Test SafetyGovernor — Custom Policies
# ═══════════════════════════════════════════════════════════════


class TestSafetyGovernorCustomPolicies:
    """自定义策略测试."""

    def test_custom_budget_policy(self):
        policy = BudgetChangePolicy(max_change_pct=0.10)
        gov = make_governor(budget_policy=policy)
        decision = gov.evaluate(
            action_type=ActionType.BUDGET_CHANGE,
            params={"current_budget": 1000, "new_budget": 1150},
            campaign_id="camp_001",
        )
        assert decision.approved is False

    def test_custom_campaign_policy(self):
        policy = NewCampaignPolicy(require_approval=False)
        gov = make_governor(campaign_policy=policy)
        decision = gov.evaluate(
            action_type=ActionType.CREATE_CAMPAIGN,
            campaign_id="camp_001",
        )
        assert decision.requires_manual is False
        assert decision.risk_level == RiskLevel.LOW

    def test_custom_pause_policy(self):
        policy = AutoPausePolicy(roas_threshold=0.8)
        gov = make_governor(pause_policy=policy)
        decision = gov.evaluate(
            action_type=ActionType.PAUSE_CAMPAIGN,
            params={"roas": 0.6},
            campaign_id="camp_001",
        )
        assert decision.approved is True

    def test_custom_cooldown_policy(self):
        policy = CooldownPolicy(cooldown_days=1)
        gov = make_governor(cooldown_policy=policy)
        gov.record_action("camp_001")
        # 立即再次评估: 在 1 天冷却期内
        decision = gov.evaluate(
            action_type=ActionType.BUDGET_CHANGE,
            params={"current_budget": 1000, "new_budget": 1100},
            campaign_id="camp_001",
        )
        assert decision.approved is False


# ═══════════════════════════════════════════════════════════════
# Test Integration
# ═══════════════════════════════════════════════════════════════


class TestIntegration:
    """集成测试."""

    def test_budget_change_then_cooldown_blocked(self):
        """预算变化成功 → 同 campaign 再次变化被冷却阻止."""
        gov = make_governor()
        # 第一次: 成功
        d1 = gov.evaluate(
            action_type=ActionType.BUDGET_CHANGE,
            params={"current_budget": 1000, "new_budget": 1100},
            campaign_id="camp_001",
        )
        assert d1.approved is True
        # 第二次: 冷却阻止
        d2 = gov.evaluate(
            action_type=ActionType.BUDGET_CHANGE,
            params={"current_budget": 1000, "new_budget": 1100},
            campaign_id="camp_001",
        )
        assert d2.approved is False
        assert "in cooldown" in d2.reason

    def test_pause_with_cooldown_blocked(self):
        """暂停不会自动记录冷却, 连续暂停均可通过."""
        gov = make_governor()
        d1 = gov.evaluate(
            action_type=ActionType.PAUSE_CAMPAIGN,
            params={"roas": 0.3},
            campaign_id="camp_001",
        )
        assert d1.approved is True
        # 暂停不记录 action history, 所以第二次仍然通过
        d2 = gov.evaluate(
            action_type=ActionType.PAUSE_CAMPAIGN,
            params={"roas": 0.3},
            campaign_id="camp_001",
        )
        assert d2.approved is True

    def test_different_campaigns_no_cooldown_conflict(self):
        """不同 campaign 互不影响."""
        gov = make_governor()
        d1 = gov.evaluate(
            action_type=ActionType.BUDGET_CHANGE,
            params={"current_budget": 1000, "new_budget": 1100},
            campaign_id="camp_A",
        )
        assert d1.approved is True
        d2 = gov.evaluate(
            action_type=ActionType.BUDGET_CHANGE,
            params={"current_budget": 1000, "new_budget": 1100},
            campaign_id="camp_B",
        )
        assert d2.approved is True

    def test_budget_rejected_still_records_cooldown(self):
        """预算被拒绝: 仍然记录操作时间."""
        gov = make_governor()
        gov.evaluate(
            action_type=ActionType.BUDGET_CHANGE,
            params={"current_budget": 1000, "new_budget": 1500},  # 大变化, 拒绝
            campaign_id="camp_001",
        )
        # 被拒绝后不应记录操作时间
        assert gov.get_last_action("camp_001") is None

    def test_pause_rejected_no_cooldown(self):
        """暂停被拒绝: 不记录冷却."""
        gov = make_governor()
        gov.evaluate(
            action_type=ActionType.PAUSE_CAMPAIGN,
            params={"roas": 1.0},  # 正常 ROAS, 拒绝
            campaign_id="camp_001",
        )
        assert gov.get_last_action("camp_001") is None

    def test_reset_cooldown_then_allow(self):
        """重置冷却后: 允许操作."""
        gov = make_governor()
        gov.record_action("camp_001")
        d1 = gov.evaluate(
            action_type=ActionType.BUDGET_CHANGE,
            params={"current_budget": 1000, "new_budget": 1100},
            campaign_id="camp_001",
        )
        assert d1.approved is False
        gov.reset_cooldown("camp_001")
        d2 = gov.evaluate(
            action_type=ActionType.BUDGET_CHANGE,
            params={"current_budget": 1000, "new_budget": 1100},
            campaign_id="camp_001",
        )
        assert d2.approved is True

    def test_rollback_always_allowed_even_after_actions(self):
        """回滚: 即使有操作历史也允许."""
        gov = make_governor()
        gov.record_action("camp_001")
        decision = gov.evaluate(
            action_type=ActionType.ROLLBACK,
            campaign_id="camp_001",
        )
        assert decision.approved is True

    def test_upload_creative_always_allowed(self):
        """上传素材: 总是允许, 不受冷却影响."""
        gov = make_governor()
        gov.record_action("camp_001")
        decision = gov.evaluate(
            action_type=ActionType.UPLOAD_CREATIVE,
            campaign_id="camp_001",
        )
        assert decision.approved is True


# ═══════════════════════════════════════════════════════════════
# Test Edge Cases
# ═══════════════════════════════════════════════════════════════


class TestEdgeCases:
    """边界情况测试."""

    def test_zero_budget_budget_change(self):
        """预算变化: 当前预算为 0."""
        gov = make_governor()
        decision = gov.evaluate(
            action_type=ActionType.BUDGET_CHANGE,
            params={"current_budget": 0, "new_budget": 100},
            campaign_id="camp_001",
        )
        assert decision.approved is False
        assert decision.risk_level == RiskLevel.HIGH

    def test_negative_budget_budget_change(self):
        """预算变化: 负预算."""
        gov = make_governor()
        decision = gov.evaluate(
            action_type=ActionType.BUDGET_CHANGE,
            params={"current_budget": -100, "new_budget": 100},
            campaign_id="camp_001",
        )
        assert decision.approved is False
        assert decision.risk_level == RiskLevel.HIGH

    def test_empty_params_all_types(self):
        """空参数: 各类动作类型."""
        gov = make_governor()
        for action_type in ActionType:
            decision = gov.evaluate(
                action_type=action_type,
                params={},
                campaign_id="test",
            )
            assert isinstance(decision, SafetyDecision)

    def test_missing_campaign_id_pause(self):
        """缺少 campaign_id: 暂停跳过冷却."""
        gov = make_governor()
        decision = gov.evaluate(
            action_type=ActionType.PAUSE_CAMPAIGN,
            params={"roas": 0.3},
        )
        assert decision.approved is True

    def test_very_large_budget_change(self):
        """非常大的预算变化."""
        gov = make_governor()
        decision = gov.evaluate(
            action_type=ActionType.BUDGET_CHANGE,
            params={"current_budget": 1, "new_budget": 1000000},
            campaign_id="camp_001",
        )
        assert decision.approved is False
        assert decision.risk_level == RiskLevel.HIGH

    def test_float_precision_budget(self):
        """浮点精度预算."""
        gov = make_governor()
        decision = gov.evaluate(
            action_type=ActionType.BUDGET_CHANGE,
            params={"current_budget": 100.0, "new_budget": 114.999999},
            campaign_id="camp_001",
        )
        assert decision.approved is True  # 仍然 < 15%

    def test_pause_with_string_risk_critical(self):
        """暂停: risk_level 字符串 'critical'."""
        gov = make_governor()
        decision = gov.evaluate(
            action_type=ActionType.PAUSE_CAMPAIGN,
            params={"roas": 1.0, "risk_level": "critical"},
            campaign_id="camp_001",
        )
        assert decision.approved is True

    def test_create_campaign_auto_approve_edge(self):
        """创建 Campaign: auto-approve 模式."""
        policy = NewCampaignPolicy(require_approval=False)
        gov = make_governor(campaign_policy=policy)
        decision = gov.evaluate(
            action_type=ActionType.CREATE_CAMPAIGN,
            campaign_id="camp_001",
        )
        assert decision.requires_manual is False

    def test_cooldown_policy_zero_days(self):
        """冷却时间为 0 天: 立即可操作."""
        policy = CooldownPolicy(cooldown_days=0)
        gov = make_governor(cooldown_policy=policy)
        gov.record_action("camp_001")
        decision = gov.evaluate(
            action_type=ActionType.BUDGET_CHANGE,
            params={"current_budget": 1000, "new_budget": 1100},
            campaign_id="camp_001",
        )
        assert decision.approved is True

    def test_budget_change_policy_zero_max_change(self):
        """max_change_pct=0: 任何变化都拒绝."""
        policy = BudgetChangePolicy(max_change_pct=0.0, require_approval_above_pct=0.0)
        decision = policy.evaluate(current_budget=1000, new_budget=1001)
        assert decision.approved is False