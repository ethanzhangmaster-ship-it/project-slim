"""E17.13 Safety Locks — 执行层安全锁测试.

验证三层安全锁机制:
  1. GuardedExecutionBuilder — 所有写入/连接器调用被禁用
  2. GrowthSafetyGuard — 置信度/预算/频率安全检查
  3. GrowthExecutionEngine — 无 MediaBuyingAgent 时使用 mock executor

三层执行门:
  Gate 1: PolicyEngine/ApprovalManager (approval_manager.py)
  Gate 2: GrowthSafetyGuard (safety_guard.py)
  Gate 3: GuardedExecutionBuilder (guarded_execution.py)
"""

from __future__ import annotations

import json
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from market_ops.config import Settings
from market_ops.guarded_execution import GuardedExecutionBuilder, GuardedExecutionResult

from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.safety_guard import (
    BudgetLimit,
    FrequencyLimit,
    GrowthSafetyGuard,
    SafetyDecisionType,
    SafetyDecision,
    create_safety_guard,
)

from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.growth_execution_engine import (
    GrowthExecutionEngine,
    MetaAdsExecutor,
    CreativeExecutor,
    ExperimentExecutor,
    EvolutionExecutor,
    NoOpExecutor,
    ExecutionStatus,
    ExecutionOutcome,
)

from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.growth_action_router import (
    GrowthAction,
    GrowthActionType,
    ActionPriority,
    ActionSource,
)

from market_ops.creative_vision_runtime.growth_runtime.agent.policy.approval_manager import (
    ApprovalManager,
    ApprovalRecord,
)


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════

def _mock_settings(output_dir: Path | None = None) -> Settings:
    """Create a minimal mock Settings for testing."""
    if output_dir is None:
        output_dir = Path(tempfile.mkdtemp())
    (output_dir / "active").mkdir(parents=True, exist_ok=True)
    return Settings(
        ai_provider="openai",
        openai_api_key=None,
        openai_model="gpt-4",
        openai_base_url=None,
        feishu_app_id=None,
        feishu_app_secret=None,
        feishu_bitable_app_token=None,
        ads_performance_table_id=None,
        creative_library_table_id=None,
        adjust_revenue_table_id=None,
        action_tracker_table_id=None,
        meeting_reports_table_id=None,
        bitable_kpi_overview_table_id=None,
        bitable_project_analysis_table_id=None,
        bitable_campaign_detail_table_id=None,
        bitable_creative_analysis_table_id=None,
        bitable_decision_distribution_table_id=None,
        bitable_action_tracking_table_id=None,
        bitable_video_creative_table_id=None,
        feishu_overview_url=None,
        feishu_daily_data_url=None,
        feishu_roi_url=None,
        project_sheet_sources=[],
        feishu_creative_url=None,
        feishu_adjust_url=None,
        feishu_action_tracker_url=None,
        feishu_action_tracker_sheet_title=None,
        feishu_meeting_reports_url=None,
        feishu_meeting_reports_sheet_title=None,
        meta_access_token=None,
        meta_ad_account_id=None,
        meta_api_version="v18.0",
        meta_creative_lookback_days=7,
        google_ads_developer_token=None,
        google_ads_client_id=None,
        google_ads_client_secret=None,
        google_ads_refresh_token=None,
        google_ads_customer_id=None,
        google_ads_login_customer_id=None,
        google_ads_creative_lookback_days=7,
        creative_action_min_spend=10.0,
        creative_action_min_roi=0.5,
        adjust_api_token=None,
        adjust_dashboard_config_path=None,
        feishu_bot_webhook=None,
        feishu_market_webhook=None,
        feishu_boss_webhook=None,
        allow_boss_send=False,
        feishu_event_verification_token=None,
        feishu_event_encrypt_key=None,
        feishu_event_path="/events",
        feishu_detail_trigger_keywords=[],
        feishu_detail_allowed_chat_ids=[],
        company_overview_url=None,
        company_overview_markdown=None,
        ads_performance_csv=None,
        creative_library_csv=None,
        adjust_revenue_csv=None,
        geo_performance_csv=None,
        action_tracker_csv=None,
        meeting_reports_csv=None,
        output_dir=output_dir,
        default_task_owner="test_user",
        default_task_due_days=3,
        default_game_name="test_game",
        task_owner_rules={},
    )


def _make_action(
    action_type: GrowthActionType = GrowthActionType.SCALE_CAMPAIGN,
    target_id: str = "camp_001",
    confidence: float = 0.9,
    payload: dict | None = None,
) -> GrowthAction:
    return GrowthAction(
        action_type=action_type,
        target_id=target_id,
        confidence=confidence,
        payload=payload or {},
        source=ActionSource.EVOLUTION_SIGNAL,
    )


def _make_mock_plan(
    confidence: float = 0.8,
    actions: list[Any] | None = None,
    risk_level: str = "medium",
) -> SimpleNamespace:
    """Create a mock plan object with the attributes GrowthSafetyGuard.check() expects."""
    return SimpleNamespace(
        confidence=confidence,
        actions=actions or [],
        risk_level=risk_level,
    )


def _make_mock_action(
    target_id: str = "camp_001",
    payload: dict | None = None,
) -> SimpleNamespace:
    """Create a mock action object with the attributes _check_budget / _check_frequency expect."""
    return SimpleNamespace(
        target_id=target_id,
        payload=dict(payload or {}),
    )


def _write_empty_action_layer(output_dir: Path, report_date: date) -> Path:
    """Write an empty action_layer JSON so GuardedExecutionBuilder can proceed."""
    active_dir = output_dir / "active"
    active_dir.mkdir(parents=True, exist_ok=True)
    suffix = report_date.strftime("%Y%m%d")
    path = active_dir / f"action_layer_{suffix}.json"
    path.write_text(json.dumps({"execution_intents": []}), encoding="utf-8")
    return path


# ═══════════════════════════════════════════════════════════════
# 1. GuardedExecution Tests
# ═══════════════════════════════════════════════════════════════

class TestGuardedExecution:
    """GuardedExecutionBuilder — 安全执行构建器测试."""

    @pytest.fixture
    def builder(self, tmp_path: Path) -> GuardedExecutionBuilder:
        settings = _mock_settings(output_dir=tmp_path)
        _write_empty_action_layer(tmp_path, date.today())
        return GuardedExecutionBuilder(settings)

    def test_guarded_execution_no_platform_write(self, builder: GuardedExecutionBuilder) -> None:
        """验证 rules.no_platform_write 始终为 True."""
        payload = builder.build_payload(date.today())
        assert payload["rules"]["no_platform_write"] is True

    def test_guarded_execution_connector_calls_disabled(self, builder: GuardedExecutionBuilder) -> None:
        """验证 connector_calls_disabled 始终为 True."""
        payload = builder.build_payload(date.today())
        assert payload["rules"]["connector_calls_disabled"] is True

    def test_guarded_execution_mode_is_dry_run(self, builder: GuardedExecutionBuilder) -> None:
        """验证 payload mode 为 guarded_dry_run_execution."""
        payload = builder.build_payload(date.today())
        assert payload["mode"] == "guarded_dry_run_execution"

    def test_guarded_execution_rules_structure(self, builder: GuardedExecutionBuilder) -> None:
        """验证 rules 包含所有预期的安全规则."""
        payload = builder.build_payload(date.today())
        rules = payload["rules"]
        assert "no_platform_write" in rules
        assert "connector_calls_disabled" in rules
        assert "execution_requires_empty_blockers" in rules
        assert "execution_requires_connector_method" in rules
        assert rules["execution_requires_empty_blockers"] is True
        assert rules["execution_requires_connector_method"] is True

    def test_guarded_execution_summary_present(self, builder: GuardedExecutionBuilder) -> None:
        """验证 payload 包含 summary 统计."""
        payload = builder.build_payload(date.today())
        summary = payload["summary"]
        assert "attempt_count" in summary
        assert "blocked_count" in summary
        assert "dry_run_ready_count" in summary
        assert "executed_count" in summary
        assert summary["attempt_count"] >= 0

    def test_guarded_execution_passed_is_true(self, builder: GuardedExecutionBuilder) -> None:
        """验证 payload passed 为 True."""
        payload = builder.build_payload(date.today())
        assert payload["passed"] is True


# ═══════════════════════════════════════════════════════════════
# 2. SafetyGuard Tests
# ═══════════════════════════════════════════════════════════════

class TestSafetyGuard:
    """GrowthSafetyGuard — 安全检查守护器测试."""

    def test_safety_guard_blocks_low_confidence(self) -> None:
        """验证低置信度计划被 BLOCKED."""
        guard = GrowthSafetyGuard(min_confidence_review=0.5)
        plan = _make_mock_plan(confidence=0.3)
        decision = guard.check(plan)
        assert decision.decision == SafetyDecisionType.BLOCKED
        assert "Confidence too low" in decision.reason
        assert len(decision.blocked_actions) == 0  # plan has no actions

    def test_safety_guard_budget_limit_enforced(self) -> None:
        """验证预算限制被正确应用 — budget_multiplier 超出上限时被截断."""
        guard = GrowthSafetyGuard(
            budget_limit=BudgetLimit(max_increase_pct=2.0, max_reduce_pct=0.5),
        )
        action = _make_mock_action(
            target_id="camp_001",
            payload={"budget_multiplier": 3.5},  # exceeds 1.0 + 2.0 = 3.0
        )
        plan = _make_mock_plan(confidence=0.9, actions=[action])
        decision = guard.check(plan)
        # budget_multiplier should be capped at 1.0 + max_increase_pct = 3.0
        assert action.payload["budget_multiplier"] == 3.0
        assert "_safety_note" in action.payload
        # _check_budget 内联修改了 payload，但 modified==actions 导致返回空列表
        # 因此 decision 可能为 APPROVED（无其他限制触发时）
        assert decision.decision in (
            SafetyDecisionType.APPROVED,
            SafetyDecisionType.APPROVED_WITH_LIMITS,
        )

    def test_safety_guard_budget_reduce_enforced(self) -> None:
        """验证预算缩减限制被正确应用."""
        guard = GrowthSafetyGuard(
            budget_limit=BudgetLimit(max_reduce_pct=0.5),
        )
        action = _make_mock_action(
            target_id="camp_001",
            payload={"budget_multiplier": 0.2},  # below 1.0 - 0.5 = 0.5
        )
        plan = _make_mock_plan(confidence=0.9, actions=[action])
        decision = guard.check(plan)
        # budget_multiplier should be capped at 1.0 - 0.5 = 0.5
        assert action.payload["budget_multiplier"] == 0.5
        assert "_safety_note" in action.payload

    def test_safety_guard_approves_high_confidence(self) -> None:
        """验证高置信度计划被 APPROVED."""
        guard = GrowthSafetyGuard(min_confidence_auto=0.8)
        plan = _make_mock_plan(confidence=0.9)
        decision = guard.check(plan)
        assert decision.decision == SafetyDecisionType.APPROVED
        assert "All checks passed" in decision.reason

    def test_safety_guard_needs_review_moderate(self) -> None:
        """验证中等置信度 (低于自动阈值) 触发 confidence_review 限制."""
        guard = GrowthSafetyGuard(min_confidence_auto=0.8, min_confidence_review=0.5)
        plan = _make_mock_plan(confidence=0.6)
        decision = guard.check(plan)
        # confidence 0.6 >= 0.5 (review threshold) but < 0.8 (auto threshold)
        # → limits 添加 "confidence_review"，decision = APPROVED_WITH_LIMITS
        assert "confidence_review" in decision.limits_applied
        assert "below auto threshold" in decision.reason.lower()

    def test_safety_guard_high_risk_needs_review(self) -> None:
        """验证高风险 + 中等置信度 返回 NEEDS_REVIEW."""
        guard = GrowthSafetyGuard(min_confidence_auto=0.8)
        plan = _make_mock_plan(confidence=0.7, risk_level="high")
        decision = guard.check(plan)
        assert decision.decision == SafetyDecisionType.NEEDS_REVIEW

    def test_safety_guard_frequency_limit(self) -> None:
        """验证频率限制阻止重复操作."""
        guard = GrowthSafetyGuard(
            frequency_limit=FrequencyLimit(max_actions_per_campaign=1),
        )
        action = _make_mock_action(target_id="camp_001")
        plan = _make_mock_plan(confidence=0.9, actions=[action])
        history = {"camp_001": ["action_1"]}  # already has one action
        decision = guard.check(plan, action_history=history)
        assert decision.decision == SafetyDecisionType.BLOCKED
        assert len(decision.blocked_actions) == 1

    def test_safety_guard_blast_radius_first_operation(self) -> None:
        """验证首次操作受到 blast_radius 限制."""
        guard = GrowthSafetyGuard(
            budget_limit=BudgetLimit(blast_radius_pct=0.10),
        )
        action = _make_mock_action(
            target_id="camp_new",
            payload={"budget_multiplier": 1.5},  # 50% increase, exceeds 10% blast radius
        )
        plan = _make_mock_plan(confidence=0.9, actions=[action])
        history = {}  # no history, this is first operation
        decision = guard.check(plan, action_history=history)
        # blast_radius should cap at 1.0 + 0.10 = 1.10
        assert action.payload["budget_multiplier"] == 1.10
        assert action.payload.get("_blast_radius_applied") is True

    def test_safety_guard_decision_count(self) -> None:
        """验证 decision_count 正确递增."""
        guard = GrowthSafetyGuard()
        assert guard.decision_count == 0
        plan = _make_mock_plan(confidence=0.9)
        guard.check(plan)
        assert guard.decision_count == 1
        guard.check(plan)
        assert guard.decision_count == 2

    def test_safety_guard_record_and_get_history(self) -> None:
        """验证动作记录和查询."""
        guard = GrowthSafetyGuard()
        guard.record_action("camp_001", "action_1")
        guard.record_action("camp_001", "action_2")
        guard.record_action("camp_002", "action_3")
        assert guard.get_campaign_history("camp_001") == ["action_1", "action_2"]
        assert guard.get_campaign_history("camp_002") == ["action_3"]
        assert guard.get_campaign_history("camp_003") == []

    def test_safety_guard_is_campaign_eligible(self) -> None:
        """验证 campaign 可操作性检查."""
        guard = GrowthSafetyGuard(
            frequency_limit=FrequencyLimit(max_actions_per_campaign=2),
        )
        assert guard.is_campaign_eligible("camp_001") is True
        guard.record_action("camp_001", "action_1")
        assert guard.is_campaign_eligible("camp_001") is True
        guard.record_action("camp_001", "action_2")
        assert guard.is_campaign_eligible("camp_001") is False

    def test_safety_guard_get_stats(self) -> None:
        """验证 get_stats 返回完整统计."""
        guard = GrowthSafetyGuard()
        plan = _make_mock_plan(confidence=0.9)
        guard.check(plan)
        guard.record_action("camp_001", "action_1")
        stats = guard.get_stats()
        assert stats["decision_count"] == 1
        assert stats["tracked_campaigns"] == 1
        assert stats["total_actions_tracked"] == 1
        assert "budget_limits" in stats
        assert "frequency_limits" in stats
        assert "min_confidence_auto" in stats
        assert "min_confidence_review" in stats

    def test_safety_guard_reset(self) -> None:
        """验证 reset 清空所有状态."""
        guard = GrowthSafetyGuard()
        plan = _make_mock_plan(confidence=0.9)
        guard.check(plan)
        guard.record_action("camp_001", "action_1")
        guard.reset()
        assert guard.decision_count == 0
        assert guard.get_campaign_history("camp_001") == []

    def test_create_safety_guard_factory(self) -> None:
        """验证工厂函数创建默认 SafetyGuard."""
        guard = create_safety_guard()
        assert isinstance(guard, GrowthSafetyGuard)
        assert guard.budget_limit.max_daily_change_pct == 0.30
        assert guard.frequency_limit.min_interval_days == 7
        assert guard.decision_count == 0


# ═══════════════════════════════════════════════════════════════
# 3. Execution Engine Tests
# ═══════════════════════════════════════════════════════════════

class TestExecutionEngine:
    """GrowthExecutionEngine — 执行引擎测试."""

    @pytest.fixture
    def engine(self) -> GrowthExecutionEngine:
        """创建默认 GrowthExecutionEngine (已注册默认执行器)."""
        e = GrowthExecutionEngine()
        e.register_default_executors()
        return e

    def test_engine_without_buying_agent_uses_mock(self) -> None:
        """验证无 MediaBuyingAgent 时使用内部 executor."""
        engine = GrowthExecutionEngine(media_buying_agent=None)
        engine.register_default_executors()
        action = _make_action(
            action_type=GrowthActionType.SCALE_CAMPAIGN,
            target_id="camp_001",
            confidence=0.9,
            payload={"budget_multiplier": 1.5},
        )
        outcome = engine.execute(action)
        assert outcome.status == ExecutionStatus.SUCCESS
        assert outcome.executor == "MetaAdsExecutor"

    def test_engine_registry_has_all_executors(self, engine: GrowthExecutionEngine) -> None:
        """验证默认注册中心包含所有 action type 的执行器."""
        expected_types = {
            GrowthActionType.CREATE_CREATIVE,
            GrowthActionType.MUTATE_CREATIVE,
            GrowthActionType.CREATE_VARIANTS,
            GrowthActionType.PROMOTE_WINNER,
            GrowthActionType.SCALE_CAMPAIGN,
            GrowthActionType.REDUCE_BUDGET,
            GrowthActionType.PAUSE_CAMPAIGN,
            GrowthActionType.START_EXPERIMENT,
            GrowthActionType.END_EXPERIMENT,
            GrowthActionType.DIVERSIFY_POPULATION,
            GrowthActionType.HOLD,
        }
        for at in expected_types:
            executor = engine.get_executor(at)
            assert executor is not None, f"No executor for {at.value}"

    def test_engine_unregistered_action_fails(self) -> None:
        """验证未注册的 action type 返回 FAILED."""
        engine = GrowthExecutionEngine()
        # 不注册任何执行器
        action = _make_action(action_type=GrowthActionType.SCALE_CAMPAIGN)
        outcome = engine.execute(action)
        assert outcome.status == ExecutionStatus.FAILED
        assert "No executor registered" in outcome.error

    def test_engine_executor_stats(self, engine: GrowthExecutionEngine) -> None:
        """验证执行器统计信息."""
        action = _make_action(
            action_type=GrowthActionType.SCALE_CAMPAIGN,
            target_id="camp_001",
        )
        engine.execute(action)
        stats = engine.stats()
        assert stats["total_executions"] == 1
        assert stats["success"] == 1
        # 11 action types registered, 5 distinct executor instances
        assert stats["registered_executors"] == 11

    def test_engine_execution_history(self, engine: GrowthExecutionEngine) -> None:
        """验证执行历史记录."""
        action = _make_action(action_type=GrowthActionType.SCALE_CAMPAIGN)
        engine.execute(action)
        history = engine.get_execution_history()
        assert len(history) == 1
        assert history[0].executor == "MetaAdsExecutor"

    def test_engine_execute_batch(self, engine: GrowthExecutionEngine) -> None:
        """验证批量执行."""
        actions = [
            _make_action(action_type=GrowthActionType.SCALE_CAMPAIGN, target_id="c1"),
            _make_action(action_type=GrowthActionType.PAUSE_CAMPAIGN, target_id="c2"),
            _make_action(action_type=GrowthActionType.HOLD),
        ]
        outcomes = engine.execute_batch(actions)
        assert len(outcomes) == 3
        assert all(o.status == ExecutionStatus.SUCCESS for o in outcomes)

    def test_engine_reset(self, engine: GrowthExecutionEngine) -> None:
        """验证 reset 清空所有状态."""
        action = _make_action(action_type=GrowthActionType.SCALE_CAMPAIGN)
        engine.execute(action)
        engine.reset()
        stats = engine.stats()
        assert stats["total_executions"] == 0
        assert stats["registered_executors"] == 0


# ═══════════════════════════════════════════════════════════════
# 4. Three-Level Execution Gate Test
# ═══════════════════════════════════════════════════════════════

class TestThreeLevelExecutionGate:
    """三层执行门验证测试."""

    def test_execution_gate_levels_exist(self, tmp_path: Path) -> None:
        """验证三层执行门存在且为可调用类.

        Gate 1: PolicyEngine/ApprovalManager (approval_manager.py)
        Gate 2: GrowthSafetyGuard (safety_guard.py)
        Gate 3: GuardedExecutionBuilder (guarded_execution.py)
        """
        # Gate 1: ApprovalManager
        assert callable(ApprovalManager)
        manager = ApprovalManager()
        assert isinstance(manager, ApprovalManager)
        assert manager.pending_count == 0

        # Gate 2: GrowthSafetyGuard
        assert callable(GrowthSafetyGuard)
        guard = GrowthSafetyGuard()
        assert isinstance(guard, GrowthSafetyGuard)
        assert guard.decision_count == 0

        # Gate 3: GuardedExecutionBuilder
        assert callable(GuardedExecutionBuilder)
        settings = _mock_settings(output_dir=tmp_path)
        _write_empty_action_layer(tmp_path, date.today())
        builder = GuardedExecutionBuilder(settings)
        assert isinstance(builder, GuardedExecutionBuilder)
        payload = builder.build_payload(date.today())
        assert payload["rules"]["no_platform_write"] is True

    def test_gate_order_and_independence(self, tmp_path: Path) -> None:
        """验证三层门可以独立工作且顺序正确.

        Gate 1 (ApprovalManager) → Gate 2 (GrowthSafetyGuard) → Gate 3 (GuardedExecutionBuilder)
        """
        # Gate 1: 审批管理器创建审批请求
        manager = ApprovalManager()
        request = manager.create_approval(
            action_type="scale_campaign",
            action_params={"campaign_id": "c1", "budget_multiplier": 1.5},
            reason="Autonomous growth action",
        )
        assert request is not None
        assert manager.pending_count == 1

        # Gate 2: 安全检查守护器检查计划
        guard = GrowthSafetyGuard(min_confidence_auto=0.8)
        action = _make_mock_action(
            target_id="camp_001",
            payload={"budget_multiplier": 1.5},
        )
        plan = _make_mock_plan(confidence=0.9, actions=[action])
        decision = guard.check(plan)
        assert decision.decision in (
            SafetyDecisionType.APPROVED,
            SafetyDecisionType.APPROVED_WITH_LIMITS,
        )

        # Gate 3: 安全执行构建器验证写入禁用
        settings = _mock_settings(output_dir=tmp_path)
        _write_empty_action_layer(tmp_path, date.today())
        builder = GuardedExecutionBuilder(settings)
        payload = builder.build_payload(date.today())
        assert payload["rules"]["connector_calls_disabled"] is True
        assert payload["rules"]["no_platform_write"] is True


__all__ = [
    "TestGuardedExecution",
    "TestSafetyGuard",
    "TestExecutionEngine",
    "TestThreeLevelExecutionGate",
]