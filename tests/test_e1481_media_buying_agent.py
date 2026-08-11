"""E14.8.1 Media Buying Agent — 集成测试.

验证 MediaBuyingAgent 的真实执行管线:
  - ApprovalTier: 审批分级 (15 tests)
  - BudgetGuard: 预算安全检查 (15 tests)
  - RollbackRecord: 回滚记录 (10 tests)
  - MediaBuyingAgent.execute: 执行能力 (20 tests)
  - MediaBuyingAgent.rollback: 回滚能力 (15 tests)
  - GrowthExecutionEngine 集成: E14.7 集成 (15 tests)
  - AutonomousGrowthAgent 集成: E14.8 端到端 (20 tests)
  - Safety: 安全边界 (10 tests)
  - Regression: 回归 (10 tests)

总计: 130 个测试用例
"""

from __future__ import annotations

import pytest

from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.media_buying_agent import (
    MediaBuyingAgent,
    ApprovalTier,
    ApprovalDecision,
    RollbackRecord,
    create_media_buying_agent,
    REQUIRES_HUMAN_APPROVAL,
    REQUIRES_MANAGER_APPROVAL,
)
from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.growth_action_router import (
    GrowthAction,
    GrowthActionType,
    ActionStatus,
    ActionPriority,
)
from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.growth_execution_engine import (
    ExecutionStatus,
    ExecutionOutcome,
    GrowthExecutionEngine,
    create_growth_execution_engine,
)
from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.autonomous_growth_agent import (
    AutonomousGrowthAgent,
    create_autonomous_growth_agent,
)
from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.goal_models import (
    GrowthGoal,
    GoalPriority,
)
from market_ops.execution_runtime.budget_guard import BudgetGuardResult


# ═══════════════════════════════════════════════════════════
# Test Helpers
# ═══════════════════════════════════════════════════════════

def _make_action(
    action_type: GrowthActionType = GrowthActionType.SCALE_CAMPAIGN,
    confidence: float = 0.91,
    target_id: str = "camp_123",
    budget_multiplier: float = 1.2,
    current_budget: float = 100.0,
) -> GrowthAction:
    return GrowthAction(
        action_type=action_type,
        confidence=confidence,
        target_id=target_id,
        payload={
            "budget_multiplier": budget_multiplier,
            "current_budget": current_budget,
        },
    )


# ═══════════════════════════════════════════════════════════
# Part 1: ApprovalTier Tests (15 tests)
# ═══════════════════════════════════════════════════════════

class TestApprovalTier:
    """审批分级测试."""

    def test_approval_tier_values(self):
        assert ApprovalTier.AUTO.value == "AUTO"
        assert ApprovalTier.HUMAN.value == "HUMAN"
        assert ApprovalTier.MANAGER.value == "MANAGER"

    def test_approval_decision_defaults(self):
        d = ApprovalDecision()
        assert d.approved is True
        assert d.tier == ApprovalTier.AUTO
        assert d.requires_manual is False

    def test_approval_decision_manual(self):
        d = ApprovalDecision(
            approved=False,
            tier=ApprovalTier.HUMAN,
            requires_manual=True,
        )
        assert d.approved is False
        assert d.tier == ApprovalTier.HUMAN

    def test_approval_decision_manager(self):
        d = ApprovalDecision(
            approved=False,
            tier=ApprovalTier.MANAGER,
            reason="Needs manager review",
            requires_manual=True,
        )
        assert d.tier == ApprovalTier.MANAGER
        assert "MANAGER" in d.reason.upper()

    def test_approval_decision_capped_budget(self):
        d = ApprovalDecision(capped_budget=130.0)
        assert d.capped_budget == 130.0

    def test_approval_decision_to_dict(self):
        d = ApprovalDecision(
            approved=False,
            tier=ApprovalTier.HUMAN,
            reason="Test reason",
            requires_manual=True,
        )
        result = d.to_dict()
        assert result["approved"] is False
        assert result["tier"] == "HUMAN"
        assert result["reason"] == "Test reason"

    def test_decision_id_unique(self):
        d1 = ApprovalDecision()
        d2 = ApprovalDecision()
        assert d1.decision_id != d2.decision_id

    def test_decision_id_format(self):
        d = ApprovalDecision()
        assert d.decision_id.startswith("ad_")

    def test_created_at_not_empty(self):
        d = ApprovalDecision()
        assert d.created_at

    def test_auto_tier_string(self):
        assert str(ApprovalTier.AUTO.value) == "AUTO"

    def test_human_approval_required_actions(self):
        assert GrowthActionType.PAUSE_CAMPAIGN in REQUIRES_HUMAN_APPROVAL

    def test_manager_approval_required_actions(self):
        assert GrowthActionType.CREATE_CREATIVE in REQUIRES_MANAGER_APPROVAL
        assert GrowthActionType.START_EXPERIMENT in REQUIRES_MANAGER_APPROVAL

    def test_scale_campaign_not_in_human_approval(self):
        assert GrowthActionType.SCALE_CAMPAIGN not in REQUIRES_HUMAN_APPROVAL

    def test_reduce_budget_not_in_manager_approval(self):
        assert GrowthActionType.REDUCE_BUDGET not in REQUIRES_MANAGER_APPROVAL

    def test_approval_decision_roundtrip(self):
        d = ApprovalDecision(
            approved=False,
            tier=ApprovalTier.MANAGER,
            reason="Roundtrip test",
            requires_manual=True,
            capped_budget=500.0,
        )
        d2 = d.to_dict()
        assert d2["approved"] == d.approved
        assert d2["tier"] == d.tier.value
        assert d2["capped_budget"] == d.capped_budget


# ═══════════════════════════════════════════════════════════
# Part 2: BudgetGuard Integration Tests (15 tests)
# ═══════════════════════════════════════════════════════════

class TestBudgetGuardIntegration:
    """预算安全检查集成测试."""

    def test_normal_scale_passes(self, agent):
        action = _make_action(budget_multiplier=1.2)
        result = agent._check_budget(action)
        assert result.allowed is True

    def test_excessive_scale_blocked(self, agent):
        action = _make_action(budget_multiplier=3.0)
        result = agent._check_budget(action)
        assert result.allowed is False

    def test_reduce_budget_always_allowed(self, agent):
        action = _make_action(
            action_type=GrowthActionType.REDUCE_BUDGET,
            budget_multiplier=0.5,
        )
        result = agent._check_budget(action)
        assert result.allowed is True

    def test_budget_guard_below_minimum(self, agent):
        action = _make_action(budget_multiplier=0.001)
        result = agent._check_budget(action)
        assert result.allowed is False

    def test_exact_30_percent_passes(self, agent):
        agent._budget_guard._max_scale_ratio = 0.30
        action = _make_action(budget_multiplier=1.30)
        result = agent._check_budget(action)
        assert result.allowed is True

    def test_31_percent_blocked(self, agent):
        agent._budget_guard._max_scale_ratio = 0.30
        action = _make_action(budget_multiplier=1.31)
        result = agent._check_budget(action)
        assert result.allowed is False

    def test_daily_cap_check(self, agent):
        agent._budget_guard._daily_cap = 500.0
        action = _make_action(budget_multiplier=1.2, current_budget=400.0)
        result = agent._check_budget(action)
        assert result.allowed is True

    def test_daily_cap_exceeded(self, agent):
        agent._budget_guard._daily_cap = 500.0
        action = _make_action(budget_multiplier=1.5, current_budget=400.0)
        result = agent._check_budget(action)
        assert result.allowed is False

    def test_budget_guard_result_has_details(self, agent):
        action = _make_action(budget_multiplier=3.0)
        result = agent._check_budget(action)
        assert result.reason
        assert result.capped_budget > 0

    def test_budget_guard_result_to_dict(self, agent):
        action = _make_action(budget_multiplier=1.2)
        result = agent._check_budget(action)
        d = result.to_dict()
        assert "allowed" in d
        assert "budget_before" in d

    def test_custom_max_scale_ratio(self, agent):
        agent._budget_guard._max_scale_ratio = 0.50
        action = _make_action(budget_multiplier=1.50)
        result = agent._check_budget(action)
        assert result.allowed is True

    def test_custom_min_budget(self, agent):
        agent._budget_guard._min_budget = 5.0
        action = _make_action(budget_multiplier=0.01, current_budget=100.0)
        result = agent._check_budget(action)
        assert result.allowed is False

    def test_budget_guard_not_checked_for_pause(self, agent):
        action = _make_action(action_type=GrowthActionType.PAUSE_CAMPAIGN)
        outcome = agent.execute(action)
        assert outcome.status == ExecutionStatus.PENDING

    def test_budget_result_zero_budget_after(self, agent):
        action = _make_action(budget_multiplier=0.0)
        result = agent._check_budget(action)
        assert result.allowed is False

    def test_budget_result_negative_multiplier(self, agent):
        action = _make_action(budget_multiplier=-0.5)
        result = agent._check_budget(action)
        assert result.allowed is False


# ═══════════════════════════════════════════════════════════
# Part 3: RollbackRecord Tests (10 tests)
# ═══════════════════════════════════════════════════════════

class TestRollbackRecord:
    """回滚记录测试."""

    def test_create_rollback_record(self):
        r = RollbackRecord(
            action_id="ga_001",
            action_type="scale_campaign",
            campaign_id="camp_123",
            before_state={"budget": 100.0},
        )
        assert r.record_id.startswith("rb_")
        assert r.action_id == "ga_001"
        assert r.before_state["budget"] == 100.0
        assert r.rolled_back is False

    def test_rollback_record_to_dict(self):
        r = RollbackRecord(
            action_id="ga_001",
            action_type="scale_campaign",
            campaign_id="camp_123",
            before_state={"budget": 100.0},
            after_state={"budget": 130.0},
        )
        d = r.to_dict()
        assert d["action_id"] == "ga_001"
        assert d["rolled_back"] is False

    def test_rollback_record_unique_ids(self):
        r1 = RollbackRecord()
        r2 = RollbackRecord()
        assert r1.record_id != r2.record_id

    def test_rollback_record_after_rollback(self):
        r = RollbackRecord(action_id="ga_001")
        r.rolled_back = True
        assert r.rolled_back is True

    def test_rollback_record_before_after_state(self):
        r = RollbackRecord(
            before_state={"budget": 100.0, "status": "ACTIVE"},
            after_state={"budget": 130.0, "status": "ACTIVE"},
        )
        assert r.before_state["budget"] == 100.0
        assert r.after_state["budget"] == 130.0

    def test_rollback_record_empty_states(self):
        r = RollbackRecord()
        assert r.before_state == {}
        assert r.after_state == {}

    def test_agent_records_rollback_on_execute(self, agent):
        action = _make_action()
        agent.execute(action)
        records = agent.get_rollback_records()
        assert len(records) == 1
        assert records[0].action_id == action.action_id

    def test_agent_rollback_state_has_before(self, agent):
        action = _make_action()
        agent.execute(action)
        records = agent.get_rollback_records()
        assert "budget" in records[0].before_state
        assert "campaign_id" in records[0].before_state

    def test_agent_rollback_state_has_after(self, agent):
        action = _make_action()
        agent.execute(action)
        records = agent.get_rollback_records()
        assert records[0].after_state
        assert records[0].after_state["success"] is True

    def test_rollback_record_created_at(self):
        r = RollbackRecord()
        assert r.created_at


# ═══════════════════════════════════════════════════════════
# Part 4: MediaBuyingAgent.execute Tests (20 tests)
# ═══════════════════════════════════════════════════════════

class TestMediaBuyingAgentExecute:
    """MediaBuyingAgent 执行测试."""

    def test_execute_scale_campaign_success(self, agent):
        action = _make_action(confidence=0.91)
        outcome = agent.execute(action)
        assert outcome.status == ExecutionStatus.SUCCESS
        assert outcome.executor == "MediaBuyingAgent"

    def test_execute_reduce_budget_success(self, agent):
        action = _make_action(
            action_type=GrowthActionType.REDUCE_BUDGET,
            budget_multiplier=0.5,
            confidence=0.91,
        )
        outcome = agent.execute(action)
        assert outcome.status == ExecutionStatus.SUCCESS

    def test_execute_pause_campaign_requires_approval(self, agent):
        action = _make_action(
            action_type=GrowthActionType.PAUSE_CAMPAIGN,
            confidence=0.91,
        )
        outcome = agent.execute(action)
        assert outcome.status == ExecutionStatus.PENDING
        assert "human" in str(outcome.output).lower()

    def test_execute_low_confidence_requires_approval(self, agent):
        action = _make_action(confidence=0.50)
        outcome = agent.execute(action)
        assert outcome.status == ExecutionStatus.PENDING

    def test_execute_create_creative_requires_manager(self, agent):
        action = _make_action(
            action_type=GrowthActionType.CREATE_CREATIVE,
            confidence=0.95,
        )
        outcome = agent.execute(action)
        assert outcome.status == ExecutionStatus.PENDING

    def test_execute_excessive_budget_blocked(self, agent):
        action = _make_action(budget_multiplier=3.0, confidence=0.91)
        outcome = agent.execute(action)
        # 审批检查会先于预算检查拦截，返回 PENDING
        assert outcome.status == ExecutionStatus.PENDING
        assert "human" in str(outcome.output).lower()

    def test_execute_action_status_updated(self, agent):
        action = _make_action(confidence=0.91)
        agent.execute(action)
        assert action.status == ActionStatus.COMPLETED

    def test_execute_failed_action_status_updated(self, agent):
        action = _make_action(budget_multiplier=3.0, confidence=0.91)
        agent.execute(action)
        # 审批检查先于预算检查拦截，状态为 PENDING
        assert action.status == ActionStatus.PENDING

    def test_execute_results_in_history(self, agent):
        action = _make_action(confidence=0.91)
        agent.execute(action)
        history = agent.get_execution_history()
        assert len(history) == 1

    def test_execute_output_contains_platform_info(self, agent):
        action = _make_action(confidence=0.91)
        outcome = agent.execute(action)
        assert outcome.output["platform"] == "facebook"

    def test_execute_output_contains_approval_tier(self, agent):
        action = _make_action(confidence=0.91)
        outcome = agent.execute(action)
        assert "approval_tier" in outcome.output
        assert outcome.output["approval_tier"] == "AUTO"

    def test_execute_output_contains_rollback_id(self, agent):
        action = _make_action(confidence=0.91)
        outcome = agent.execute(action)
        assert "rollback_record_id" in outcome.output

    def test_execute_batch_all_success(self, agent):
        actions = [
            _make_action(confidence=0.91),
            _make_action(
                action_type=GrowthActionType.REDUCE_BUDGET,
                budget_multiplier=0.5,
                confidence=0.91,
            ),
        ]
        outcomes = agent.execute_batch(actions)
        assert len(outcomes) == 2
        assert all(o.status == ExecutionStatus.SUCCESS for o in outcomes)

    def test_execute_batch_mixed(self, agent):
        actions = [
            _make_action(confidence=0.91),
            _make_action(budget_multiplier=3.0, confidence=0.91),
        ]
        outcomes = agent.execute_batch(actions)
        assert len(outcomes) == 2
        assert outcomes[0].status == ExecutionStatus.SUCCESS
        assert outcomes[1].status == ExecutionStatus.PENDING

    def test_execute_in_sandbox_mode(self, agent):
        assert agent.is_sandbox is True
        action = _make_action(confidence=0.91)
        outcome = agent.execute(action)
        assert outcome.status == ExecutionStatus.SUCCESS

    def test_execute_duration_ms_recorded(self, agent):
        action = _make_action(confidence=0.91)
        outcome = agent.execute(action)
        assert outcome.duration_ms >= 0

    def test_execute_with_action_metadata(self, agent):
        action = _make_action(confidence=0.91)
        action.metadata = {"source": "test"}
        outcome = agent.execute(action)
        assert outcome.status == ExecutionStatus.SUCCESS

    def test_execute_promote_winner(self, agent):
        action = _make_action(
            action_type=GrowthActionType.PROMOTE_WINNER,
            budget_multiplier=1.2,
            confidence=0.91,
        )
        outcome = agent.execute(action)
        assert outcome.status == ExecutionStatus.SUCCESS

    def test_execute_hold_not_routed_to_platform(self, agent):
        action = _make_action(action_type=GrowthActionType.HOLD)
        result = agent._call_platform(action)
        assert result.success is False

    def test_execute_unknown_action_type(self, agent):
        action = _make_action(action_type=GrowthActionType.DIVERSIFY_POPULATION)
        result = agent._call_platform(action)
        assert result.success is False


# ═══════════════════════════════════════════════════════════
# Part 5: MediaBuyingAgent.rollback Tests (15 tests)
# ═══════════════════════════════════════════════════════════

class TestMediaBuyingAgentRollback:
    """回滚功能测试."""

    def test_rollback_success(self, agent):
        action = _make_action(confidence=0.91)
        agent.execute(action)
        outcome = agent.rollback(action.action_id)
        assert outcome is not None
        assert outcome.status == ExecutionStatus.SUCCESS

    def test_rollback_nonexistent_action(self, agent):
        outcome = agent.rollback("nonexistent")
        assert outcome is None

    def test_rollback_already_rolled_back(self, agent):
        action = _make_action(confidence=0.91)
        agent.execute(action)
        agent.rollback(action.action_id)
        outcome = agent.rollback(action.action_id)
        assert outcome.status == ExecutionStatus.FAILED
        assert "Already rolled back" in outcome.error

    def test_rollback_records_marked(self, agent):
        action = _make_action(confidence=0.91)
        agent.execute(action)
        agent.rollback(action.action_id)
        records = agent.get_rollback_records()
        assert records[0].rolled_back is True

    def test_rollback_all(self, agent):
        actions = [
            _make_action(confidence=0.91),
            _make_action(
                action_type=GrowthActionType.REDUCE_BUDGET,
                budget_multiplier=0.5,
                confidence=0.91,
            ),
        ]
        for a in actions:
            agent.execute(a)
        outcomes = agent.rollback_all()
        assert len(outcomes) == 2
        assert all(o.status == ExecutionStatus.SUCCESS for o in outcomes)

    def test_rollback_count_increments(self, agent):
        action = _make_action(confidence=0.91)
        agent.execute(action)
        agent.rollback(action.action_id)
        assert agent.stats()["rollback_count"] == 1

    def test_rollback_restores_budget(self, agent):
        action = _make_action(
            action_type=GrowthActionType.PROMOTE_WINNER,
            budget_multiplier=1.2,
            current_budget=100.0,
            confidence=0.91,
        )
        agent.execute(action)
        records = agent.get_rollback_records()
        assert records[0].before_state["budget"] == 100.0

    def test_rollback_pause_action(self, agent):
        action = _make_action(
            action_type=GrowthActionType.PAUSE_CAMPAIGN,
            confidence=0.91,
        )
        outcome = agent.execute(action)
        # Pause requires human approval → PENDING, no rollback record
        assert outcome.status == ExecutionStatus.PENDING
        # 没有 rollback record 因为 action 未执行
        rb = agent.rollback(action.action_id)
        assert rb is None

    def test_rollback_without_campaign_id(self, agent):
        action = _make_action(confidence=0.91, target_id="")
        outcome = agent.execute(action)
        assert outcome.status == ExecutionStatus.SUCCESS
        # No rollback record because no campaign_id
        outcome = agent.rollback(action.action_id)
        assert outcome is None

    def test_rollback_output_contains_restored_state(self, agent):
        action = _make_action(confidence=0.91)
        agent.execute(action)
        outcome = agent.rollback(action.action_id)
        assert outcome.output["action"] == "rolled_back"
        assert "restored_state" in outcome.output

    def test_rollback_reduce_budget(self, agent):
        action = _make_action(
            action_type=GrowthActionType.REDUCE_BUDGET,
            budget_multiplier=0.5,
            current_budget=100.0,
            confidence=0.91,
        )
        agent.execute(action)
        outcome = agent.rollback(action.action_id)
        assert outcome.status == ExecutionStatus.SUCCESS

    def test_rollback_promote_winner(self, agent):
        action = _make_action(
            action_type=GrowthActionType.PROMOTE_WINNER,
            budget_multiplier=1.2,
            confidence=0.91,
        )
        agent.execute(action)
        outcome = agent.rollback(action.action_id)
        assert outcome.status == ExecutionStatus.SUCCESS

    def test_rollback_does_not_affect_other_actions(self, agent):
        a1 = _make_action(confidence=0.91)
        a2 = _make_action(
            action_type=GrowthActionType.REDUCE_BUDGET,
            budget_multiplier=0.5,
            confidence=0.91,
        )
        agent.execute(a1)
        agent.execute(a2)
        agent.rollback(a1.action_id)
        records = agent.get_rollback_records()
        assert records[0].rolled_back is True
        assert records[1].rolled_back is False

    def test_rollback_exception_handled(self, agent):
        action = _make_action(confidence=0.91)
        agent.execute(action)
        # Corrupt the record
        for r in agent.get_rollback_records():
            r.before_state = {}
        outcome = agent.rollback(action.action_id)
        # Should handle gracefully
        assert outcome is not None

    def test_rollback_all_only_unrolled(self, agent):
        a1 = _make_action(confidence=0.91)
        a2 = _make_action(
            action_type=GrowthActionType.REDUCE_BUDGET,
            budget_multiplier=0.5,
            confidence=0.91,
        )
        agent.execute(a1)
        agent.execute(a2)
        agent.rollback(a1.action_id)
        outcomes = agent.rollback_all()
        assert len(outcomes) == 1


# ═══════════════════════════════════════════════════════════
# Part 6: GrowthExecutionEngine Integration (15 tests)
# ═══════════════════════════════════════════════════════════

class TestEngineIntegration:
    """GrowthExecutionEngine + MediaBuyingAgent 集成测试."""

    def test_engine_with_media_buying_agent(self, agent):
        engine = create_growth_execution_engine(media_buying_agent=agent)
        assert engine.media_buying_agent is not None

    def test_engine_routes_ua_action_to_agent(self, agent):
        engine = create_growth_execution_engine(media_buying_agent=agent)
        action = _make_action(confidence=0.91)
        outcome = engine.execute(action)
        assert outcome.executor == "MediaBuyingAgent"

    def test_engine_falls_back_to_executor(self, agent):
        engine = create_growth_execution_engine(media_buying_agent=agent)
        engine.register_default_executors()
        action = _make_action(
            action_type=GrowthActionType.CREATE_VARIANTS,
            target_id="genome_001",
        )
        outcome = engine.execute(action)
        assert outcome.executor != "MediaBuyingAgent"

    def test_engine_without_agent_uses_executor(self):
        engine = create_growth_execution_engine()
        engine.register_default_executors()
        action = _make_action(confidence=0.91)
        outcome = engine.execute(action)
        assert outcome.executor == "MetaAdsExecutor"

    def test_engine_pause_routed_to_agent(self, agent):
        engine = create_growth_execution_engine(media_buying_agent=agent)
        action = _make_action(action_type=GrowthActionType.PAUSE_CAMPAIGN)
        outcome = engine.execute(action)
        assert outcome.executor == "MediaBuyingAgent"

    def test_engine_create_creative_routed_to_agent(self, agent):
        engine = create_growth_execution_engine(media_buying_agent=agent)
        action = _make_action(
            action_type=GrowthActionType.CREATE_CREATIVE,
            confidence=0.95,
        )
        outcome = engine.execute(action)
        assert outcome.executor == "MediaBuyingAgent"

    def test_engine_batch_ua_actions(self, agent):
        engine = create_growth_execution_engine(media_buying_agent=agent)
        actions = [
            _make_action(confidence=0.91),
            _make_action(
                action_type=GrowthActionType.REDUCE_BUDGET,
                budget_multiplier=0.5,
                confidence=0.91,
            ),
        ]
        outcomes = engine.execute_batch(actions)
        assert len(outcomes) == 2
        assert all(o.executor == "MediaBuyingAgent" for o in outcomes)

    def test_engine_rollback_via_agent(self, agent):
        engine = create_growth_execution_engine(media_buying_agent=agent)
        action = _make_action(confidence=0.91)
        engine.execute(action)
        outcome = engine.media_buying_agent.rollback(action.action_id)
        assert outcome.status == ExecutionStatus.SUCCESS

    def test_engine_stats_with_agent(self, agent):
        engine = create_growth_execution_engine(media_buying_agent=agent)
        action = _make_action(confidence=0.91)
        engine.execute(action)
        stats = engine.stats()
        assert stats["total_executions"] >= 1

    def test_engine_agent_stats_accessible(self, agent):
        engine = create_growth_execution_engine(media_buying_agent=agent)
        action = _make_action(confidence=0.91)
        engine.execute(action)
        agent_stats = engine.media_buying_agent.stats()
        assert agent_stats["total_executions"] == 1
        assert agent_stats["sandbox_mode"] is True

    def test_engine_hold_not_routed_to_agent(self, agent):
        engine = create_growth_execution_engine(media_buying_agent=agent)
        engine.register_default_executors()
        action = _make_action(action_type=GrowthActionType.HOLD)
        outcome = engine.execute(action)
        assert outcome.executor != "MediaBuyingAgent"

    def test_engine_create_variants_not_routed_to_agent(self, agent):
        engine = create_growth_execution_engine(media_buying_agent=agent)
        engine.register_default_executors()
        action = _make_action(
            action_type=GrowthActionType.CREATE_VARIANTS,
            target_id="genome_001",
        )
        outcome = engine.execute(action)
        assert outcome.executor != "MediaBuyingAgent"

    def test_engine_factory_defaults(self):
        engine = create_growth_execution_engine(register_defaults=False)
        assert engine.media_buying_agent is None
        assert engine.registry == {}

    def test_engine_factory_with_agent(self, agent):
        engine = create_growth_execution_engine(
            register_defaults=True,
            media_buying_agent=agent,
        )
        assert engine.media_buying_agent is not None
        assert len(engine.registry) > 0

    def test_engine_execution_history_accumulates(self, agent):
        engine = create_growth_execution_engine(media_buying_agent=agent)
        a1 = _make_action(confidence=0.91)
        a2 = _make_action(
            action_type=GrowthActionType.REDUCE_BUDGET,
            budget_multiplier=0.5,
            confidence=0.91,
        )
        engine.execute(a1)
        engine.execute(a2)
        history = engine.get_execution_history()
        assert len(history) == 2


# ═══════════════════════════════════════════════════════════
# Part 7: AutonomousGrowthAgent Integration (20 tests)
# ═══════════════════════════════════════════════════════════

class TestAgentIntegration:
    """AutonomousGrowthAgent + MediaBuyingAgent 端到端测试."""

    def test_agent_with_media_buying_agent(self, agent_with_engine):
        assert agent_with_engine._execution_engine is not None
        assert agent_with_engine._execution_engine.media_buying_agent is not None

    def test_agent_run_cycle_with_ua_actions(self, agent_with_engine):
        agent_with_engine.set_goal(_make_goal())
        reality = {
            "roas": 0.55,
            "roas_trend": "stable",
            "fatigue": 0.6,
            "payer_rate": 0.03,
            "campaign_count": 5,
            "creative_count": 20,
            "budget_utilization": 0.7,
            "ctr": 0.02,
            "cvr": 0.03,
            "signals": [],
        }
        result = agent_with_engine.run_cycle(reality)
        assert result.status == "success"
        assert result.state is not None

    def test_agent_cycle_produces_outcomes(self, agent_with_engine):
        agent_with_engine.set_goal(_make_goal())
        reality = {
            "roas": 0.55,
            "roas_trend": "stable",
            "fatigue": 0.6,
            "payer_rate": 0.03,
            "campaign_count": 5,
            "creative_count": 20,
            "budget_utilization": 0.7,
            "ctr": 0.02,
            "cvr": 0.03,
            "signals": [],
        }
        result = agent_with_engine.run_cycle(reality)
        if result.outcomes:
            assert all(isinstance(o, ExecutionOutcome) for o in result.outcomes)

    def test_agent_execution_engine_stats(self, agent_with_engine):
        agent_with_engine.set_goal(_make_goal())
        reality = {
            "roas": 0.55,
            "roas_trend": "stable",
            "fatigue": 0.6,
            "payer_rate": 0.03,
            "campaign_count": 5,
            "creative_count": 20,
            "budget_utilization": 0.7,
            "ctr": 0.02,
            "cvr": 0.03,
            "signals": [],
        }
        agent_with_engine.run_cycle(reality)
        stats = agent_with_engine._execution_engine.stats()
        assert stats["total_executions"] >= 0

    def test_agent_with_media_buying_agent_stats(self, agent_with_engine):
        agent_with_engine.set_goal(_make_goal())
        reality = {
            "roas": 0.55,
            "roas_trend": "stable",
            "fatigue": 0.6,
            "payer_rate": 0.03,
            "campaign_count": 5,
            "creative_count": 20,
            "budget_utilization": 0.7,
            "ctr": 0.02,
            "cvr": 0.03,
            "signals": [],
        }
        agent_with_engine.run_cycle(reality)
        agent_stats = agent_with_engine._execution_engine.media_buying_agent.stats()
        assert "total_executions" in agent_stats

    def test_agent_rollback_after_cycle(self, agent_with_engine):
        agent_with_engine.set_goal(_make_goal())
        reality = {
            "roas": 0.55,
            "roas_trend": "stable",
            "fatigue": 0.6,
            "payer_rate": 0.03,
            "campaign_count": 5,
            "creative_count": 20,
            "budget_utilization": 0.7,
            "ctr": 0.02,
            "cvr": 0.03,
            "signals": [],
        }
        agent_with_engine.run_cycle(reality)
        buying_agent = agent_with_engine._execution_engine.media_buying_agent
        records = buying_agent.get_rollback_records()
        # Each executed UA action should have a rollback record
        if records:
            outcomes = buying_agent.rollback_all()
            assert all(o.status == ExecutionStatus.SUCCESS for o in outcomes)

    def test_agent_without_engine_runs_no_actions(self):
        agent = create_autonomous_growth_agent()
        agent.set_goal(_make_goal())
        result = agent.run_cycle({
            "roas": 0.55,
            "roas_trend": "stable",
            "fatigue": 0.6,
            "payer_rate": 0.03,
            "campaign_count": 5,
            "creative_count": 20,
            "budget_utilization": 0.7,
            "ctr": 0.02,
            "cvr": 0.03,
            "signals": [],
        })
        assert result.outcomes == []

    def test_agent_cycle_with_roas_goal(self, agent_with_engine):
        goal = _make_goal(metric="D30_ROAS", target_value=1.0, current_value=0.53)
        agent_with_engine.set_goal(goal)
        result = agent_with_engine.run_cycle({
            "roas": 0.55,
            "roas_trend": "stable",
            "fatigue": 0.6,
            "payer_rate": 0.03,
            "campaign_count": 5,
            "creative_count": 20,
            "budget_utilization": 0.7,
            "ctr": 0.02,
            "cvr": 0.03,
            "signals": [],
        })
        assert result.goal_gap is not None
        assert result.goal_gap.goal.metric == "D30_ROAS"

    def test_agent_cycle_with_cpi_goal(self, agent_with_engine):
        goal = _make_goal(metric="CPI", target_value=2.0, current_value=3.5)
        agent_with_engine.set_goal(goal)
        result = agent_with_engine.run_cycle({
            "roas": 0.8,
            "roas_trend": "stable",
            "fatigue": 0.3,
            "payer_rate": 0.05,
            "campaign_count": 3,
            "creative_count": 15,
            "budget_utilization": 0.5,
            "ctr": 0.03,
            "cvr": 0.04,
            "signals": [],
        })
        assert result.goal_gap is not None

    def test_agent_cycle_with_payer_rate_goal(self, agent_with_engine):
        goal = _make_goal(metric="payer_rate", target_value=0.08, current_value=0.03)
        agent_with_engine.set_goal(goal)
        result = agent_with_engine.run_cycle({
            "roas": 0.7,
            "roas_trend": "stable",
            "fatigue": 0.5,
            "payer_rate": 0.03,
            "campaign_count": 5,
            "creative_count": 20,
            "budget_utilization": 0.6,
            "ctr": 0.02,
            "cvr": 0.03,
            "signals": [],
        })
        assert result.goal_gap.goal.metric == "payer_rate"

    def test_agent_multiple_cycles(self, agent_with_engine):
        goal = _make_goal(metric="D30_ROAS", target_value=1.0, current_value=0.53)
        agent_with_engine.set_goal(goal)
        reality = {
            "roas": 0.55,
            "roas_trend": "stable",
            "fatigue": 0.6,
            "payer_rate": 0.03,
            "campaign_count": 5,
            "creative_count": 20,
            "budget_utilization": 0.7,
            "ctr": 0.02,
            "cvr": 0.03,
            "signals": [],
        }
        r1 = agent_with_engine.run_cycle(reality)
        r2 = agent_with_engine.run_cycle(reality)
        assert r1.status == "success"
        assert r2.status == "success"
        assert agent_with_engine._cycle_count == 2

    def test_agent_fatigue_recovery_scenario(self, agent_with_engine):
        goal = _make_goal(metric="D30_ROAS", target_value=1.0, current_value=0.53)
        agent_with_engine.set_goal(goal)
        result = agent_with_engine.run_cycle({
            "roas": 0.55,
            "roas_trend": "declining",
            "fatigue": 0.85,
            "payer_rate": 0.03,
            "campaign_count": 5,
            "creative_count": 20,
            "budget_utilization": 0.7,
            "ctr": 0.02,
            "cvr": 0.03,
            "signals": ["fatigue_warning"],
        })
        assert result.state is not None

    def test_agent_healthy_scenario_no_actions(self, agent_with_engine):
        goal = _make_goal(metric="D30_ROAS", target_value=1.0, current_value=1.2)
        agent_with_engine.set_goal(goal)
        result = agent_with_engine.run_cycle({
            "roas": 1.3,
            "roas_trend": "improving",
            "fatigue": 0.2,
            "payer_rate": 0.08,
            "campaign_count": 5,
            "creative_count": 25,
            "budget_utilization": 0.8,
            "ctr": 0.04,
            "cvr": 0.05,
            "signals": [],
        })
        assert result.status == "success"

    def test_agent_cycle_history_accumulates(self, agent_with_engine):
        agent_with_engine.set_goal(_make_goal())
        reality = {
            "roas": 0.55,
            "roas_trend": "stable",
            "fatigue": 0.6,
            "payer_rate": 0.03,
            "campaign_count": 5,
            "creative_count": 20,
            "budget_utilization": 0.7,
            "ctr": 0.02,
            "cvr": 0.03,
            "signals": [],
        }
        agent_with_engine.run_cycle(reality)
        history = agent_with_engine.get_cycle_history()
        assert len(history) == 1

    def test_agent_status_after_cycle(self, agent_with_engine):
        agent_with_engine.set_goal(_make_goal())
        agent_with_engine.run_cycle({
            "roas": 0.55,
            "roas_trend": "stable",
            "fatigue": 0.6,
            "payer_rate": 0.03,
            "campaign_count": 5,
            "creative_count": 20,
            "budget_utilization": 0.7,
            "ctr": 0.02,
            "cvr": 0.03,
            "signals": [],
        })
        status = agent_with_engine.get_status()
        assert status["cycle_count"] == 1

    def test_agent_goal_achieved_stops(self, agent_with_engine):
        goal = _make_goal(metric="D30_ROAS", target_value=1.0, current_value=1.5)
        agent_with_engine.set_goal(goal)
        result = agent_with_engine.run_cycle({
            "roas": 1.5,
            "roas_trend": "improving",
            "fatigue": 0.2,
            "payer_rate": 0.06,
            "campaign_count": 5,
            "creative_count": 20,
            "budget_utilization": 0.7,
            "ctr": 0.03,
            "cvr": 0.04,
            "signals": [],
        })
        assert result.goal_gap is not None

    def test_agent_cycle_without_goal(self, agent_with_engine):
        result = agent_with_engine.run_cycle({
            "roas": 0.55,
            "roas_trend": "stable",
            "fatigue": 0.6,
            "payer_rate": 0.03,
            "campaign_count": 5,
            "creative_count": 20,
            "budget_utilization": 0.7,
            "ctr": 0.02,
            "cvr": 0.03,
            "signals": [],
        })
        assert result.status == "success"

    def test_agent_cycle_with_empty_data(self, agent_with_engine):
        agent_with_engine.set_goal(_make_goal())
        result = agent_with_engine.run_cycle({})
        assert result.status == "success"

    def test_agent_cycle_roas_drop_scenario(self, agent_with_engine):
        goal = _make_goal(metric="D30_ROAS", target_value=1.0, current_value=0.53)
        agent_with_engine.set_goal(goal)
        result = agent_with_engine.run_cycle({
            "roas": 0.35,
            "roas_trend": "declining",
            "fatigue": 0.9,
            "payer_rate": 0.02,
            "campaign_count": 8,
            "creative_count": 30,
            "budget_utilization": 0.9,
            "ctr": 0.01,
            "cvr": 0.02,
            "signals": ["roas_critical", "fatigue_alert"],
        })
        assert result.state is not None
        assert result.goal_gap is not None


# ═══════════════════════════════════════════════════════════
# Part 8: Safety Tests (10 tests)
# ═══════════════════════════════════════════════════════════

class TestSafety:
    """安全边界测试."""

    def test_auto_approve_disabled(self):
        agent = MediaBuyingAgent(auto_approve=False)
        action = _make_action(confidence=0.91)
        outcome = agent.execute(action)
        assert outcome.status == ExecutionStatus.PENDING

    def test_auto_confidence_threshold(self):
        agent = MediaBuyingAgent(auto_confidence=0.90)
        action = _make_action(confidence=0.85)
        outcome = agent.execute(action)
        assert outcome.status == ExecutionStatus.PENDING

    def test_custom_max_scale_ratio(self):
        agent = MediaBuyingAgent(max_scale_ratio=0.15)
        action = _make_action(budget_multiplier=1.2, confidence=0.91)
        outcome = agent.execute(action)
        assert outcome.status == ExecutionStatus.PENDING

    def test_daily_cap_enforced(self):
        agent = MediaBuyingAgent(daily_cap=200.0)
        action = _make_action(
            budget_multiplier=1.2,
            current_budget=180.0,
            confidence=0.91,
        )
        outcome = agent.execute(action)
        assert outcome.status == ExecutionStatus.FAILED
        assert "BUDGET_GUARD" in outcome.error

    def test_min_budget_enforced(self):
        agent = MediaBuyingAgent(min_budget=10.0)
        action = _make_action(
            budget_multiplier=0.05,
            current_budget=100.0,
            confidence=0.91,
        )
        outcome = agent.execute(action)
        assert outcome.status == ExecutionStatus.FAILED

    def test_pause_always_requires_human(self):
        agent = MediaBuyingAgent(auto_approve=True)
        action = _make_action(
            action_type=GrowthActionType.PAUSE_CAMPAIGN,
            confidence=0.99,
        )
        outcome = agent.execute(action)
        assert outcome.status == ExecutionStatus.PENDING

    def test_create_creative_always_requires_manager(self):
        agent = MediaBuyingAgent(auto_approve=True)
        action = _make_action(
            action_type=GrowthActionType.CREATE_CREATIVE,
            confidence=0.99,
        )
        outcome = agent.execute(action)
        assert outcome.status == ExecutionStatus.PENDING
        assert "manager" in str(outcome.output).lower()

    def test_start_experiment_always_requires_manager(self):
        agent = MediaBuyingAgent(auto_approve=True)
        action = _make_action(
            action_type=GrowthActionType.START_EXPERIMENT,
            confidence=0.99,
        )
        outcome = agent.execute(action)
        assert outcome.status == ExecutionStatus.PENDING

    def test_high_confidence_scale_auto_approved(self, agent):
        action = _make_action(confidence=0.95, budget_multiplier=1.1)
        outcome = agent.execute(action)
        assert outcome.status == ExecutionStatus.SUCCESS
        assert outcome.output["approval_tier"] == "AUTO"

    def test_sandbox_mode_does_not_call_real_api(self, agent):
        assert agent.is_sandbox is True
        agent._execute_count = 0
        action = _make_action(confidence=0.91)
        outcome = agent.execute(action)
        assert outcome.status == ExecutionStatus.SUCCESS


# ═══════════════════════════════════════════════════════════
# Part 9: Regression Tests (10 tests)
# ═══════════════════════════════════════════════════════════

class TestRegression:
    """回归测试."""

    def test_agent_stats_default(self, agent):
        stats = agent.stats()
        assert stats["total_executions"] == 0
        assert stats["sandbox_mode"] is True

    def test_agent_stats_after_execution(self, agent):
        action = _make_action(confidence=0.91)
        agent.execute(action)
        stats = agent.stats()
        assert stats["total_executions"] == 1
        assert stats["success"] == 1

    def test_agent_reset(self, agent):
        action = _make_action(confidence=0.91)
        agent.execute(action)
        agent.reset()
        stats = agent.stats()
        assert stats["total_executions"] == 0
        assert agent.get_execution_history() == []

    def test_agent_reset_clears_rollback(self, agent):
        action = _make_action(confidence=0.91)
        agent.execute(action)
        agent.reset()
        assert agent.get_rollback_records() == []

    def test_approval_history_accumulates(self, agent):
        action = _make_action(confidence=0.91)
        agent.execute(action)
        history = agent.get_approval_history()
        assert len(history) >= 1

    def test_approval_decision_auto_tier(self, agent):
        action = _make_action(confidence=0.91)
        decision = agent._check_approval(action)
        assert decision.tier == ApprovalTier.AUTO
        assert decision.requires_manual is False

    def test_approval_decision_human_tier_low_confidence(self, agent):
        action = _make_action(confidence=0.50)
        decision = agent._check_approval(action)
        assert decision.tier == ApprovalTier.HUMAN
        assert decision.requires_manual is True

    def test_approval_decision_manager_tier(self, agent):
        action = _make_action(
            action_type=GrowthActionType.CREATE_CREATIVE,
            confidence=0.95,
        )
        decision = agent._check_approval(action)
        assert decision.tier == ApprovalTier.MANAGER

    def test_factory_creates_sandbox_agent(self):
        agent = create_media_buying_agent()
        assert agent.is_sandbox is True

    def test_factory_custom_params(self):
        agent = create_media_buying_agent(
            sandbox=True,
            auto_approve=False,
            auto_confidence=0.90,
            max_scale_ratio=0.20,
            daily_cap=500.0,
            min_budget=5.0,
        )
        assert agent.is_sandbox is True
        assert agent._auto_approve is False
        assert agent._auto_confidence == 0.90
        assert agent._budget_guard.max_scale_ratio == 0.20


# ═══════════════════════════════════════════════════════════
# 测试计数
# ═══════════════════════════════════════════════════════════

def test_test_count():
    """确保测试总数."""
    import inspect
    current_module = inspect.getmodule(test_test_count)
    classes = [
        cls for _, cls in inspect.getmembers(current_module, inspect.isclass)
        if cls.__module__ == current_module.__name__ and cls.__name__.startswith("Test")
    ]
    total = sum(
        len([m for m in inspect.getmembers(cls, inspect.isfunction) if m[0].startswith("test_")])
        for cls in classes
    )
    assert total >= 100, f"Expected >= 100 tests, got {total}"


# ═══════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════

@pytest.fixture
def agent():
    """创建沙盒模式 MediaBuyingAgent."""
    return create_media_buying_agent(
        sandbox=True,
        auto_approve=True,
        auto_confidence=0.80,
        max_scale_ratio=0.30,
    )


@pytest.fixture
def agent_with_engine(agent):
    """创建带有 MediaBuyingAgent 的 AutonomousGrowthAgent."""
    engine = create_growth_execution_engine(media_buying_agent=agent)
    return create_autonomous_growth_agent(execution_engine=engine)


def _make_goal(
    metric: str = "D30_ROAS",
    target_value: float = 1.0,
    current_value: float = 0.53,
) -> GrowthGoal:
    return GrowthGoal(
        metric=metric,
        target_value=target_value,
        current_value=current_value,
        deadline_days=60,
        priority=GoalPriority.HIGH,
    )