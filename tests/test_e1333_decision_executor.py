"""E13.3.3 Growth Decision Executor — 测试套件.

测试覆盖:
  - ExecutionActionType / ExecutionStatus / ApprovalLevel 枚举
  - ExecutionAction / ExecutionResult / ExecutionBatch 模型
  - OPPORTUNITY_TO_ACTION_MAP
  - CreativeExecutor: Scale / Refresh / Mutation
  - UAExecutor: Scale / Reduction / Rebalance
  - RevenueExecutor: Monetization Scale / Monetization Optimize
  - GrowthDecisionExecutor: execute / convert / simulate / filters
  - 审批级别和回滚
  - 边界条件
  - 集成场景
"""

from __future__ import annotations

import pytest
from typing import Any


# ═══════════════════════════════════════════════════════════════
# Helper: Create minimal GrowthOpportunity for testing
# ═══════════════════════════════════════════════════════════════

def _make_opportunity(
    opp_type: Any = None,
    entity_id: str = "c001",
    priority: Any = None,
    confidence: float = 0.9,
    recommended_params: dict[str, Any] | None = None,
    **kwargs,
) -> Any:
    from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import (
        GrowthOpportunity, OpportunityType, OpportunityPriority,
    )
    if opp_type is None:
        opp_type = OpportunityType.CREATIVE_SCALE
    if priority is None:
        priority = OpportunityPriority.HIGH
    return GrowthOpportunity(
        opportunity_type=opp_type,
        entity_id=entity_id,
        priority=priority,
        confidence=confidence,
        recommended_params=recommended_params or {},
        **kwargs,
    )


# ═══════════════════════════════════════════════════════════════
# Model Tests — Execution Enums
# ═══════════════════════════════════════════════════════════════


class TestExecutionActionType:
    """ExecutionActionType 枚举测试."""

    def test_all_types_exist(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import ExecutionActionType

        types = list(ExecutionActionType)
        assert len(types) == 18

    def test_creative_actions(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import ExecutionActionType

        assert ExecutionActionType.CLONE_DNA.value == "clone_dna"
        assert ExecutionActionType.GENERATE_VARIANTS.value == "generate_variants"
        assert ExecutionActionType.MUTATE_HOOK.value == "mutate_hook"
        assert ExecutionActionType.MUTATE_VISUAL.value == "mutate_visual"
        assert ExecutionActionType.CREATE_POPULATION.value == "create_population"
        assert ExecutionActionType.LAUNCH_AB_TEST.value == "launch_ab_test"
        assert ExecutionActionType.REPLACE_CREATIVE.value == "replace_creative"

    def test_ua_actions(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import ExecutionActionType

        assert ExecutionActionType.INCREASE_BUDGET.value == "increase_budget"
        assert ExecutionActionType.REDUCE_BUDGET.value == "reduce_budget"
        assert ExecutionActionType.DUPLICATE_CAMPAIGN.value == "duplicate_campaign"
        assert ExecutionActionType.PAUSE_CAMPAIGN.value == "pause_campaign"
        assert ExecutionActionType.EXPAND_TARGETING.value == "expand_targeting"
        assert ExecutionActionType.REALLOCATE_BUDGET.value == "reallocate_budget"
        assert ExecutionActionType.ADJUST_BID.value == "adjust_bid"

    def test_monetization_actions(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import ExecutionActionType

        assert ExecutionActionType.OPTIMIZE_PRICING.value == "optimize_pricing"
        assert ExecutionActionType.OPTIMIZE_AD_PLACEMENT.value == "optimize_ad_placement"
        assert ExecutionActionType.INCREASE_RETENTION.value == "increase_retention"
        assert ExecutionActionType.CREATE_HIGH_VALUE_AUDIENCE.value == "create_high_value_audience"


class TestExecutionStatus:
    """ExecutionStatus 枚举测试."""

    def test_all_statuses(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import ExecutionStatus

        statuses = list(ExecutionStatus)
        assert len(statuses) == 7

    def test_status_values(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import ExecutionStatus

        assert ExecutionStatus.PENDING.value == "pending"
        assert ExecutionStatus.APPROVED.value == "approved"
        assert ExecutionStatus.COMPLETED.value == "completed"
        assert ExecutionStatus.FAILED.value == "failed"
        assert ExecutionStatus.ROLLED_BACK.value == "rolled_back"


class TestApprovalLevel:
    """ApprovalLevel 枚举测试."""

    def test_all_levels(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import ApprovalLevel

        levels = list(ApprovalLevel)
        assert len(levels) == 5

    def test_level_values(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import ApprovalLevel

        assert ApprovalLevel.AUTO.value == "auto"
        assert ApprovalLevel.LOW.value == "low"
        assert ApprovalLevel.MEDIUM.value == "medium"
        assert ApprovalLevel.HIGH.value == "high"
        assert ApprovalLevel.CRITICAL.value == "critical"


# ═══════════════════════════════════════════════════════════════
# Model Tests — ExecutionAction
# ═══════════════════════════════════════════════════════════════


class TestExecutionAction:
    """ExecutionAction 模型测试."""

    def test_default_creation(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import ExecutionAction

        action = ExecutionAction()
        assert action.action_id
        assert action.action_type.value == "clone_dna"
        assert action.source_opportunity_id == ""
        assert action.status.value == "pending"

    def test_full_creation(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import (
            ExecutionAction, ExecutionActionType, ApprovalLevel, ExecutionStatus,
            OpportunityPriority, OpportunityType,
        )

        action = ExecutionAction(
            action_type=ExecutionActionType.INCREASE_BUDGET,
            source_opportunity_id="opp_001",
            source_opportunity_type=OpportunityType.UA_SCALE,
            entity_id="camp_001",
            entity_type="campaign",
            priority=OpportunityPriority.HIGH,
            confidence=0.92,
            params={"current_budget": 500, "new_budget": 3000},
            approval_level=ApprovalLevel.MEDIUM,
            status=ExecutionStatus.PENDING,
            expected_impact="+500% budget increase",
            rollback_action=ExecutionActionType.REDUCE_BUDGET,
            explanation="Scale campaign budget",
        )
        assert action.action_type == ExecutionActionType.INCREASE_BUDGET
        assert action.source_opportunity_id == "opp_001"
        assert action.entity_id == "camp_001"
        assert action.priority == OpportunityPriority.HIGH
        assert action.confidence == 0.92
        assert action.params["current_budget"] == 500
        assert action.approval_level == ApprovalLevel.MEDIUM
        assert action.rollback_action == ExecutionActionType.REDUCE_BUDGET

    def test_to_dict(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import (
            ExecutionAction, ExecutionActionType,
        )

        action = ExecutionAction(
            action_type=ExecutionActionType.CLONE_DNA,
            source_opportunity_id="opp_001",
            entity_id="c001",
        )
        d = action.to_dict()
        assert d["action_type"] == "clone_dna"
        assert d["source_opportunity_id"] == "opp_001"
        assert d["entity_id"] == "c001"
        assert d["status"] == "pending"

    def test_action_id_is_unique(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import ExecutionAction

        a1 = ExecutionAction()
        a2 = ExecutionAction()
        assert a1.action_id != a2.action_id

    def test_default_status_is_pending(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import ExecutionAction

        action = ExecutionAction()
        assert action.status.value == "pending"

    def test_rollback_action_none_by_default(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import ExecutionAction

        action = ExecutionAction()
        assert action.rollback_action is None

    def test_params_default_empty(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import ExecutionAction

        action = ExecutionAction()
        assert action.params == {}

    def test_metadata_default_empty(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import ExecutionAction

        action = ExecutionAction()
        assert action.metadata == {}


# ═══════════════════════════════════════════════════════════════
# Model Tests — ExecutionResult
# ═══════════════════════════════════════════════════════════════


class TestExecutionResult:
    """ExecutionResult 模型测试."""

    def test_default_creation(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import ExecutionResult

        result = ExecutionResult()
        assert result.result_id
        assert result.success is False
        assert result.status.value == "pending"

    def test_successful_result(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import (
            ExecutionResult, ExecutionStatus, ExecutionActionType,
        )

        result = ExecutionResult(
            action_id="act_001",
            action_type=ExecutionActionType.INCREASE_BUDGET,
            status=ExecutionStatus.COMPLETED,
            success=True,
            output={"new_budget": 3000},
            elapsed_ms=150.0,
        )
        assert result.success is True
        assert result.output["new_budget"] == 3000
        assert result.elapsed_ms == 150.0

    def test_failed_result(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import (
            ExecutionResult, ExecutionStatus,
        )

        result = ExecutionResult(
            status=ExecutionStatus.FAILED,
            success=False,
            error="API rate limit exceeded",
            rolled_back=True,
        )
        assert result.success is False
        assert result.error == "API rate limit exceeded"
        assert result.rolled_back is True

    def test_to_dict(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import (
            ExecutionResult, ExecutionStatus,
        )

        result = ExecutionResult(
            action_id="act_001",
            status=ExecutionStatus.COMPLETED,
            success=True,
        )
        d = result.to_dict()
        assert d["action_id"] == "act_001"
        assert d["success"] is True
        assert d["status"] == "completed"

    def test_result_id_is_unique(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import ExecutionResult

        r1 = ExecutionResult()
        r2 = ExecutionResult()
        assert r1.result_id != r2.result_id


# ═══════════════════════════════════════════════════════════════
# Model Tests — ExecutionBatch
# ═══════════════════════════════════════════════════════════════


class TestExecutionBatch:
    """ExecutionBatch 模型测试."""

    def test_default_creation(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import ExecutionBatch

        batch = ExecutionBatch()
        assert batch.batch_id
        assert batch.total_actions == 0
        assert batch.total_success == 0
        assert batch.actions == []

    def test_to_dict(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import ExecutionBatch

        batch = ExecutionBatch(
            product_id="p1",
            total_opportunities=3,
            total_actions=8,
            total_success=7,
            total_failed=1,
            summary={"increase_budget": 3, "clone_dna": 5},
        )
        d = batch.to_dict()
        assert d["product_id"] == "p1"
        assert d["total_opportunities"] == 3
        assert d["total_actions"] == 8
        assert d["total_success"] == 7

    def test_batch_id_is_unique(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import ExecutionBatch

        b1 = ExecutionBatch()
        b2 = ExecutionBatch()
        assert b1.batch_id != b2.batch_id


# ═══════════════════════════════════════════════════════════════
# Mapping Tests
# ═══════════════════════════════════════════════════════════════


class TestOpportunityToActionMap:
    """OPPORTUNITY_TO_ACTION_MAP 测试."""

    def test_all_opportunity_types_mapped(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import (
            OPPORTUNITY_TO_ACTION_MAP, OpportunityType,
        )

        for opp_type in OpportunityType:
            assert opp_type in OPPORTUNITY_TO_ACTION_MAP, f"{opp_type} not mapped"

    def test_creative_scale_maps_to_clone_generate_ab(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import (
            OPPORTUNITY_TO_ACTION_MAP, OpportunityType, ExecutionActionType,
        )

        actions = OPPORTUNITY_TO_ACTION_MAP[OpportunityType.CREATIVE_SCALE]
        assert ExecutionActionType.CLONE_DNA in actions
        assert ExecutionActionType.GENERATE_VARIANTS in actions
        assert ExecutionActionType.LAUNCH_AB_TEST in actions

    def test_creative_refresh_maps_to_mutate_replace(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import (
            OPPORTUNITY_TO_ACTION_MAP, OpportunityType, ExecutionActionType,
        )

        actions = OPPORTUNITY_TO_ACTION_MAP[OpportunityType.CREATIVE_REFRESH]
        assert ExecutionActionType.MUTATE_HOOK in actions
        assert ExecutionActionType.REPLACE_CREATIVE in actions

    def test_ua_scale_maps_to_increase_duplicate_expand(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import (
            OPPORTUNITY_TO_ACTION_MAP, OpportunityType, ExecutionActionType,
        )

        actions = OPPORTUNITY_TO_ACTION_MAP[OpportunityType.UA_SCALE]
        assert ExecutionActionType.INCREASE_BUDGET in actions
        assert ExecutionActionType.DUPLICATE_CAMPAIGN in actions
        assert ExecutionActionType.EXPAND_TARGETING in actions

    def test_budget_reduction_maps_to_reduce_pause(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import (
            OPPORTUNITY_TO_ACTION_MAP, OpportunityType, ExecutionActionType,
        )

        actions = OPPORTUNITY_TO_ACTION_MAP[OpportunityType.BUDGET_REDUCTION]
        assert ExecutionActionType.REDUCE_BUDGET in actions
        assert ExecutionActionType.PAUSE_CAMPAIGN in actions

    def test_monetization_scale_maps_to_increase_retention_audience(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import (
            OPPORTUNITY_TO_ACTION_MAP, OpportunityType, ExecutionActionType,
        )

        actions = OPPORTUNITY_TO_ACTION_MAP[OpportunityType.MONETIZATION_SCALE]
        assert ExecutionActionType.INCREASE_RETENTION in actions
        assert ExecutionActionType.CREATE_HIGH_VALUE_AUDIENCE in actions


# ═══════════════════════════════════════════════════════════════
# CreativeExecutor Tests
# ═══════════════════════════════════════════════════════════════


class TestCreativeExecutor:
    """CreativeExecutor 测试."""

    def test_scale_generates_three_actions(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.strategies.creative_executor import CreativeExecutor

        opp = _make_opportunity(
            opp_type=None,  # CREATIVE_SCALE
            recommended_params={"mutation_count": 5, "test_budget": 500},
        )
        executor = CreativeExecutor()
        actions = executor.execute(opp)
        assert len(actions) == 3

    def test_scale_first_action_is_clone_dna(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.strategies.creative_executor import CreativeExecutor
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import ExecutionActionType

        opp = _make_opportunity()
        executor = CreativeExecutor()
        actions = executor.execute(opp)
        assert actions[0].action_type == ExecutionActionType.CLONE_DNA

    def test_scale_second_action_is_generate_variants(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.strategies.creative_executor import CreativeExecutor
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import ExecutionActionType

        opp = _make_opportunity()
        executor = CreativeExecutor()
        actions = executor.execute(opp)
        assert actions[1].action_type == ExecutionActionType.GENERATE_VARIANTS

    def test_scale_third_action_is_launch_ab_test(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.strategies.creative_executor import CreativeExecutor
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import ExecutionActionType

        opp = _make_opportunity()
        executor = CreativeExecutor()
        actions = executor.execute(opp)
        assert actions[2].action_type == ExecutionActionType.LAUNCH_AB_TEST

    def test_scale_clone_dna_has_params(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.strategies.creative_executor import CreativeExecutor

        opp = _make_opportunity(entity_id="c_winner")
        executor = CreativeExecutor()
        actions = executor.execute(opp)
        assert actions[0].params["source_creative_id"] == "c_winner"
        assert actions[0].params["clone_hook"] is True
        assert actions[0].params["preserve_psychological_mechanism"] is True

    def test_scale_clone_approval_is_auto(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.strategies.creative_executor import CreativeExecutor
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import ApprovalLevel

        opp = _make_opportunity()
        executor = CreativeExecutor()
        actions = executor.execute(opp)
        assert actions[0].approval_level == ApprovalLevel.AUTO

    def test_scale_ab_test_approval_is_low(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.strategies.creative_executor import CreativeExecutor
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import ApprovalLevel

        opp = _make_opportunity()
        executor = CreativeExecutor()
        actions = executor.execute(opp)
        assert actions[2].approval_level == ApprovalLevel.LOW

    def test_scale_uses_variant_count_from_params(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.strategies.creative_executor import CreativeExecutor

        opp = _make_opportunity(recommended_params={"mutation_count": 10})
        executor = CreativeExecutor()
        actions = executor.execute(opp)
        assert actions[1].params["variant_count"] == 10

    def test_scale_actions_have_rollback(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.strategies.creative_executor import CreativeExecutor

        opp = _make_opportunity()
        executor = CreativeExecutor()
        actions = executor.execute(opp)
        for a in actions:
            assert a.rollback_action is not None

    def test_scale_actions_link_to_opportunity(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.strategies.creative_executor import CreativeExecutor

        opp = _make_opportunity()
        executor = CreativeExecutor()
        actions = executor.execute(opp)
        for a in actions:
            assert a.source_opportunity_id == opp.opportunity_id

    def test_refresh_generates_four_actions(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.strategies.creative_executor import CreativeExecutor
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import OpportunityType

        opp = _make_opportunity(opp_type=OpportunityType.CREATIVE_REFRESH)
        executor = CreativeExecutor()
        actions = executor.execute(opp)
        assert len(actions) == 4

    def test_refresh_first_is_mutate_hook(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.strategies.creative_executor import CreativeExecutor
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import OpportunityType, ExecutionActionType

        opp = _make_opportunity(opp_type=OpportunityType.CREATIVE_REFRESH)
        executor = CreativeExecutor()
        actions = executor.execute(opp)
        assert actions[0].action_type == ExecutionActionType.MUTATE_HOOK

    def test_refresh_second_is_mutate_visual(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.strategies.creative_executor import CreativeExecutor
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import OpportunityType, ExecutionActionType

        opp = _make_opportunity(opp_type=OpportunityType.CREATIVE_REFRESH)
        executor = CreativeExecutor()
        actions = executor.execute(opp)
        assert actions[1].action_type == ExecutionActionType.MUTATE_VISUAL

    def test_refresh_third_is_create_population(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.strategies.creative_executor import CreativeExecutor
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import OpportunityType, ExecutionActionType

        opp = _make_opportunity(opp_type=OpportunityType.CREATIVE_REFRESH)
        executor = CreativeExecutor()
        actions = executor.execute(opp)
        assert actions[2].action_type == ExecutionActionType.CREATE_POPULATION

    def test_refresh_fourth_is_replace_creative(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.strategies.creative_executor import CreativeExecutor
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import OpportunityType, ExecutionActionType

        opp = _make_opportunity(opp_type=OpportunityType.CREATIVE_REFRESH)
        executor = CreativeExecutor()
        actions = executor.execute(opp)
        assert actions[3].action_type == ExecutionActionType.REPLACE_CREATIVE

    def test_refresh_mutate_hook_has_hook_contrast_delta(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.strategies.creative_executor import CreativeExecutor
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import OpportunityType

        opp = _make_opportunity(
            opp_type=OpportunityType.CREATIVE_REFRESH,
            recommended_params={"hook_contrast_delta": 0.30},
        )
        executor = CreativeExecutor()
        actions = executor.execute(opp)
        assert actions[0].params["hook_contrast_delta"] == 0.30

    def test_refresh_create_population_has_population_size(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.strategies.creative_executor import CreativeExecutor
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import OpportunityType

        opp = _make_opportunity(
            opp_type=OpportunityType.CREATIVE_REFRESH,
            recommended_params={"population_size": 8},
        )
        executor = CreativeExecutor()
        actions = executor.execute(opp)
        assert actions[2].params["population_size"] == 8

    def test_refresh_replace_approval_is_low(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.strategies.creative_executor import CreativeExecutor
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import OpportunityType, ApprovalLevel

        opp = _make_opportunity(opp_type=OpportunityType.CREATIVE_REFRESH)
        executor = CreativeExecutor()
        actions = executor.execute(opp)
        assert actions[3].approval_level == ApprovalLevel.LOW

    def test_refresh_mutate_hook_approval_is_auto(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.strategies.creative_executor import CreativeExecutor
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import OpportunityType, ApprovalLevel

        opp = _make_opportunity(opp_type=OpportunityType.CREATIVE_REFRESH)
        executor = CreativeExecutor()
        actions = executor.execute(opp)
        assert actions[0].approval_level == ApprovalLevel.AUTO

    def test_mutation_generates_three_actions(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.strategies.creative_executor import CreativeExecutor
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import OpportunityType

        opp = _make_opportunity(opp_type=OpportunityType.CREATIVE_MUTATION)
        executor = CreativeExecutor()
        actions = executor.execute(opp)
        assert len(actions) == 3

    def test_mutation_uses_mutation_rate(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.strategies.creative_executor import CreativeExecutor
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import OpportunityType

        opp = _make_opportunity(
            opp_type=OpportunityType.CREATIVE_MUTATION,
            recommended_params={"mutation_rate": 0.35},
        )
        executor = CreativeExecutor()
        actions = executor.execute(opp)
        assert actions[0].params["mutation_rate"] == 0.35

    def test_mutation_actions_are_auto(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.strategies.creative_executor import CreativeExecutor
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import OpportunityType, ApprovalLevel

        opp = _make_opportunity(opp_type=OpportunityType.CREATIVE_MUTATION)
        executor = CreativeExecutor()
        actions = executor.execute(opp)
        for a in actions:
            assert a.approval_level == ApprovalLevel.AUTO

    def test_execute_unknown_type_returns_empty(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.strategies.creative_executor import CreativeExecutor
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import OpportunityType

        opp = _make_opportunity(opp_type=OpportunityType.UA_SCALE)
        executor = CreativeExecutor()
        actions = executor.execute(opp)
        assert actions == []


# ═══════════════════════════════════════════════════════════════
# UAExecutor Tests
# ═══════════════════════════════════════════════════════════════


class TestUAExecutor:
    """UAExecutor 测试."""

    def test_scale_generates_three_actions(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.strategies.ua_executor import UAExecutor
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import OpportunityType

        opp = _make_opportunity(
            opp_type=OpportunityType.UA_SCALE,
            recommended_params={"current_budget": 500, "recommended_budget": 3000, "spend_multiplier": 6.0},
        )
        executor = UAExecutor()
        actions = executor.execute(opp)
        assert len(actions) == 3

    def test_scale_first_is_increase_budget(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.strategies.ua_executor import UAExecutor
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import OpportunityType, ExecutionActionType

        opp = _make_opportunity(
            opp_type=OpportunityType.UA_SCALE,
            recommended_params={"current_budget": 500, "recommended_budget": 3000, "spend_multiplier": 6.0},
        )
        executor = UAExecutor()
        actions = executor.execute(opp)
        assert actions[0].action_type == ExecutionActionType.INCREASE_BUDGET

    def test_scale_second_is_duplicate_campaign(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.strategies.ua_executor import UAExecutor
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import OpportunityType, ExecutionActionType

        opp = _make_opportunity(
            opp_type=OpportunityType.UA_SCALE,
            recommended_params={"current_budget": 500, "recommended_budget": 3000, "spend_multiplier": 6.0},
        )
        executor = UAExecutor()
        actions = executor.execute(opp)
        assert actions[1].action_type == ExecutionActionType.DUPLICATE_CAMPAIGN

    def test_scale_third_is_expand_targeting(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.strategies.ua_executor import UAExecutor
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import OpportunityType, ExecutionActionType

        opp = _make_opportunity(
            opp_type=OpportunityType.UA_SCALE,
            recommended_params={"current_budget": 500, "recommended_budget": 3000, "spend_multiplier": 6.0},
        )
        executor = UAExecutor()
        actions = executor.execute(opp)
        assert actions[2].action_type == ExecutionActionType.EXPAND_TARGETING

    def test_scale_high_multiplier_approval_high(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.strategies.ua_executor import UAExecutor
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import OpportunityType, ApprovalLevel

        opp = _make_opportunity(
            opp_type=OpportunityType.UA_SCALE,
            recommended_params={"current_budget": 500, "recommended_budget": 3000, "spend_multiplier": 6.0},
        )
        executor = UAExecutor()
        actions = executor.execute(opp)
        assert actions[0].approval_level == ApprovalLevel.HIGH

    def test_scale_moderate_multiplier_approval_medium(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.strategies.ua_executor import UAExecutor
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import OpportunityType, ApprovalLevel

        opp = _make_opportunity(
            opp_type=OpportunityType.UA_SCALE,
            recommended_params={"current_budget": 500, "recommended_budget": 2000, "spend_multiplier": 4.0},
        )
        executor = UAExecutor()
        actions = executor.execute(opp)
        assert actions[0].approval_level == ApprovalLevel.MEDIUM

    def test_scale_low_multiplier_approval_low(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.strategies.ua_executor import UAExecutor
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import OpportunityType, ApprovalLevel

        opp = _make_opportunity(
            opp_type=OpportunityType.UA_SCALE,
            recommended_params={"current_budget": 500, "recommended_budget": 1000, "spend_multiplier": 2.0},
        )
        executor = UAExecutor()
        actions = executor.execute(opp)
        assert actions[0].approval_level == ApprovalLevel.LOW

    def test_scale_increase_has_rollback(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.strategies.ua_executor import UAExecutor
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import OpportunityType, ExecutionActionType

        opp = _make_opportunity(
            opp_type=OpportunityType.UA_SCALE,
            recommended_params={"current_budget": 500, "recommended_budget": 3000, "spend_multiplier": 6.0},
        )
        executor = UAExecutor()
        actions = executor.execute(opp)
        assert actions[0].rollback_action == ExecutionActionType.REDUCE_BUDGET

    def test_scale_increase_has_budget_params(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.strategies.ua_executor import UAExecutor
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import OpportunityType

        opp = _make_opportunity(
            opp_type=OpportunityType.UA_SCALE,
            recommended_params={"current_budget": 500, "recommended_budget": 3000, "spend_multiplier": 6.0},
        )
        executor = UAExecutor()
        actions = executor.execute(opp)
        assert actions[0].params["current_daily_budget"] == 500
        assert actions[0].params["new_daily_budget"] == 3000

    def test_scale_aggressive_duplicate_count(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.strategies.ua_executor import UAExecutor
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import OpportunityType

        opp = _make_opportunity(
            opp_type=OpportunityType.UA_SCALE,
            recommended_params={
                "current_budget": 500, "recommended_budget": 3000,
                "spend_multiplier": 6.0, "scale_strategy": "aggressive",
            },
        )
        executor = UAExecutor()
        actions = executor.execute(opp)
        assert actions[1].params["duplicate_count"] == 2

    def test_scale_moderate_duplicate_count(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.strategies.ua_executor import UAExecutor
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import OpportunityType

        opp = _make_opportunity(
            opp_type=OpportunityType.UA_SCALE,
            recommended_params={
                "current_budget": 500, "recommended_budget": 1000,
                "spend_multiplier": 2.0, "scale_strategy": "moderate",
            },
        )
        executor = UAExecutor()
        actions = executor.execute(opp)
        assert actions[1].params["duplicate_count"] == 1

    def test_reduction_generates_three_actions_when_high_reduction(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.strategies.ua_executor import UAExecutor
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import OpportunityType

        opp = _make_opportunity(
            opp_type=OpportunityType.BUDGET_REDUCTION,
            recommended_params={"current_budget": 500, "recommended_budget": 100, "reduction_pct": 0.8},
        )
        executor = UAExecutor()
        actions = executor.execute(opp)
        assert len(actions) == 3

    def test_reduction_first_is_reduce_budget(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.strategies.ua_executor import UAExecutor
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import OpportunityType, ExecutionActionType

        opp = _make_opportunity(
            opp_type=OpportunityType.BUDGET_REDUCTION,
            recommended_params={"current_budget": 500, "recommended_budget": 100, "reduction_pct": 0.8},
        )
        executor = UAExecutor()
        actions = executor.execute(opp)
        assert actions[0].action_type == ExecutionActionType.REDUCE_BUDGET

    def test_reduction_second_is_pause_when_critical(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.strategies.ua_executor import UAExecutor
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import OpportunityType, ExecutionActionType

        opp = _make_opportunity(
            opp_type=OpportunityType.BUDGET_REDUCTION,
            recommended_params={"current_budget": 500, "recommended_budget": 100, "reduction_pct": 0.8},
        )
        executor = UAExecutor()
        actions = executor.execute(opp)
        assert actions[1].action_type == ExecutionActionType.PAUSE_CAMPAIGN

    def test_reduction_pause_has_auto_resume(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.strategies.ua_executor import UAExecutor
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import OpportunityType

        opp = _make_opportunity(
            opp_type=OpportunityType.BUDGET_REDUCTION,
            recommended_params={"current_budget": 500, "recommended_budget": 100, "reduction_pct": 0.8},
        )
        executor = UAExecutor()
        actions = executor.execute(opp)
        assert actions[1].params["auto_resume_threshold"] == 1.2
        assert actions[1].params["auto_resume_metric"] == "d7_roas"

    def test_reduction_reduce_has_rollback(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.strategies.ua_executor import UAExecutor
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import OpportunityType, ExecutionActionType

        opp = _make_opportunity(
            opp_type=OpportunityType.BUDGET_REDUCTION,
            recommended_params={"current_budget": 500, "recommended_budget": 100, "reduction_pct": 0.8},
        )
        executor = UAExecutor()
        actions = executor.execute(opp)
        assert actions[0].rollback_action == ExecutionActionType.INCREASE_BUDGET

    def test_reduction_no_pause_when_low_reduction(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.strategies.ua_executor import UAExecutor
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import OpportunityType

        opp = _make_opportunity(
            opp_type=OpportunityType.BUDGET_REDUCTION,
            recommended_params={"current_budget": 500, "recommended_budget": 350, "reduction_pct": 0.3},
        )
        executor = UAExecutor()
        actions = executor.execute(opp)
        action_types = [a.action_type.value for a in actions]
        assert "pause_campaign" not in action_types

    def test_rebalance_generates_two_actions(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.strategies.ua_executor import UAExecutor
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import OpportunityType

        opp = _make_opportunity(
            opp_type=OpportunityType.UA_REBALANCE,
            recommended_params={"target_roas": 1.2, "shift_pct": 0.5},
        )
        executor = UAExecutor()
        actions = executor.execute(opp)
        assert len(actions) == 2

    def test_rebalance_first_is_reallocate(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.strategies.ua_executor import UAExecutor
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import OpportunityType, ExecutionActionType

        opp = _make_opportunity(
            opp_type=OpportunityType.UA_REBALANCE,
            recommended_params={"target_roas": 1.2, "shift_pct": 0.5},
        )
        executor = UAExecutor()
        actions = executor.execute(opp)
        assert actions[0].action_type == ExecutionActionType.REALLOCATE_BUDGET

    def test_rebalance_second_is_adjust_bid(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.strategies.ua_executor import UAExecutor
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import OpportunityType, ExecutionActionType

        opp = _make_opportunity(
            opp_type=OpportunityType.UA_REBALANCE,
            recommended_params={"target_roas": 1.2, "shift_pct": 0.5},
        )
        executor = UAExecutor()
        actions = executor.execute(opp)
        assert actions[1].action_type == ExecutionActionType.ADJUST_BID

    def test_rebalance_approval_low(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.strategies.ua_executor import UAExecutor
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import OpportunityType, ApprovalLevel

        opp = _make_opportunity(
            opp_type=OpportunityType.UA_REBALANCE,
            recommended_params={"target_roas": 1.2, "shift_pct": 0.5},
        )
        executor = UAExecutor()
        actions = executor.execute(opp)
        for a in actions:
            assert a.approval_level == ApprovalLevel.LOW

    def test_execute_unknown_type_returns_empty(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.strategies.ua_executor import UAExecutor
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import OpportunityType

        opp = _make_opportunity(opp_type=OpportunityType.CREATIVE_SCALE)
        executor = UAExecutor()
        actions = executor.execute(opp)
        assert actions == []


# ═══════════════════════════════════════════════════════════════
# RevenueExecutor Tests
# ═══════════════════════════════════════════════════════════════


class TestRevenueExecutor:
    """RevenueExecutor 测试."""

    def test_monetization_scale_generates_three_actions(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.strategies.revenue_executor import RevenueExecutor
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import OpportunityType

        opp = _make_opportunity(
            opp_type=OpportunityType.MONETIZATION_SCALE,
            recommended_params={"d30_ltv": 5.0, "bid_increase_pct": 0.25},
        )
        executor = RevenueExecutor()
        actions = executor.execute(opp)
        assert len(actions) == 3

    def test_monetization_scale_first_is_increase_budget(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.strategies.revenue_executor import RevenueExecutor
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import OpportunityType, ExecutionActionType

        opp = _make_opportunity(
            opp_type=OpportunityType.MONETIZATION_SCALE,
            recommended_params={"d30_ltv": 5.0, "bid_increase_pct": 0.25},
        )
        executor = RevenueExecutor()
        actions = executor.execute(opp)
        assert actions[0].action_type == ExecutionActionType.INCREASE_BUDGET

    def test_monetization_scale_second_is_increase_retention(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.strategies.revenue_executor import RevenueExecutor
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import OpportunityType, ExecutionActionType

        opp = _make_opportunity(
            opp_type=OpportunityType.MONETIZATION_SCALE,
            recommended_params={"d30_ltv": 5.0, "bid_increase_pct": 0.25},
        )
        executor = RevenueExecutor()
        actions = executor.execute(opp)
        assert actions[1].action_type == ExecutionActionType.INCREASE_RETENTION

    def test_monetization_scale_third_is_create_audience(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.strategies.revenue_executor import RevenueExecutor
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import OpportunityType, ExecutionActionType

        opp = _make_opportunity(
            opp_type=OpportunityType.MONETIZATION_SCALE,
            recommended_params={"d30_ltv": 5.0, "bid_increase_pct": 0.25},
        )
        executor = RevenueExecutor()
        actions = executor.execute(opp)
        assert actions[2].action_type == ExecutionActionType.CREATE_HIGH_VALUE_AUDIENCE

    def test_monetization_scale_increase_has_ltv_params(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.strategies.revenue_executor import RevenueExecutor
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import OpportunityType

        opp = _make_opportunity(
            opp_type=OpportunityType.MONETIZATION_SCALE,
            recommended_params={"d30_ltv": 5.0, "bid_increase_pct": 0.25},
        )
        executor = RevenueExecutor()
        actions = executor.execute(opp)
        assert actions[0].params["d30_ltv"] == 5.0
        assert actions[0].params["ltv_based_bidding"] is True

    def test_monetization_scale_approval_is_low(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.strategies.revenue_executor import RevenueExecutor
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import OpportunityType, ApprovalLevel

        opp = _make_opportunity(
            opp_type=OpportunityType.MONETIZATION_SCALE,
            recommended_params={"d30_ltv": 5.0, "bid_increase_pct": 0.25},
        )
        executor = RevenueExecutor()
        actions = executor.execute(opp)
        for a in actions:
            assert a.approval_level == ApprovalLevel.LOW

    def test_monetization_scale_increase_has_rollback(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.strategies.revenue_executor import RevenueExecutor
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import OpportunityType, ExecutionActionType

        opp = _make_opportunity(
            opp_type=OpportunityType.MONETIZATION_SCALE,
            recommended_params={"d30_ltv": 5.0, "bid_increase_pct": 0.25},
        )
        executor = RevenueExecutor()
        actions = executor.execute(opp)
        assert actions[0].rollback_action == ExecutionActionType.REDUCE_BUDGET

    def test_monetization_optimize_iap_generates_pricing_action(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.strategies.revenue_executor import RevenueExecutor
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import OpportunityType, ExecutionActionType

        opp = _make_opportunity(
            opp_type=OpportunityType.MONETIZATION_OPTIMIZE,
            recommended_params={"iap_conversion": 0.005, "optimization_target": "iap"},
        )
        executor = RevenueExecutor()
        actions = executor.execute(opp)
        assert len(actions) == 1
        assert actions[0].action_type == ExecutionActionType.OPTIMIZE_PRICING

    def test_monetization_optimize_iaa_generates_ad_placement_action(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.strategies.revenue_executor import RevenueExecutor
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import OpportunityType, ExecutionActionType

        opp = _make_opportunity(
            opp_type=OpportunityType.MONETIZATION_OPTIMIZE,
            recommended_params={"ad_arpdau": 0.005, "optimization_target": "iaa"},
        )
        executor = RevenueExecutor()
        actions = executor.execute(opp)
        assert len(actions) == 1
        assert actions[0].action_type == ExecutionActionType.OPTIMIZE_AD_PLACEMENT

    def test_monetization_optimize_both_generates_two_actions(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.strategies.revenue_executor import RevenueExecutor
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import OpportunityType

        opp = _make_opportunity(
            opp_type=OpportunityType.MONETIZATION_OPTIMIZE,
            recommended_params={"iap_conversion": 0.005, "ad_arpdau": 0.005, "optimization_target": "both"},
        )
        executor = RevenueExecutor()
        actions = executor.execute(opp)
        assert len(actions) == 2

    def test_monetization_optimize_iap_has_shop_actions(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.strategies.revenue_executor import RevenueExecutor
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import OpportunityType

        opp = _make_opportunity(
            opp_type=OpportunityType.MONETIZATION_OPTIMIZE,
            recommended_params={"iap_conversion": 0.005, "optimization_target": "iap"},
        )
        executor = RevenueExecutor()
        actions = executor.execute(opp)
        pricing_actions = actions[0].params["actions"]
        assert "analyze_payer_funnel" in pricing_actions
        assert "optimize_shop_experience" in pricing_actions

    def test_monetization_optimize_iaa_has_ad_actions(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.strategies.revenue_executor import RevenueExecutor
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import OpportunityType

        opp = _make_opportunity(
            opp_type=OpportunityType.MONETIZATION_OPTIMIZE,
            recommended_params={"ad_arpdau": 0.005, "optimization_target": "iaa"},
        )
        executor = RevenueExecutor()
        actions = executor.execute(opp)
        ad_actions = actions[0].params["actions"]
        assert "optimize_ad_placement" in ad_actions
        assert "adjust_ad_frequency" in ad_actions

    def test_monetization_optimize_approval_is_medium(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.strategies.revenue_executor import RevenueExecutor
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import OpportunityType, ApprovalLevel

        opp = _make_opportunity(
            opp_type=OpportunityType.MONETIZATION_OPTIMIZE,
            recommended_params={"iap_conversion": 0.005, "optimization_target": "iap"},
        )
        executor = RevenueExecutor()
        actions = executor.execute(opp)
        assert actions[0].approval_level == ApprovalLevel.MEDIUM

    def test_monetization_optimize_zero_metrics_fallback(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.strategies.revenue_executor import RevenueExecutor
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import OpportunityType, ExecutionActionType

        opp = _make_opportunity(
            opp_type=OpportunityType.MONETIZATION_OPTIMIZE,
            recommended_params={"iap_conversion": 0, "ad_arpdau": 0, "optimization_target": "none"},
        )
        executor = RevenueExecutor()
        actions = executor.execute(opp)
        assert len(actions) == 1
        assert actions[0].action_type == ExecutionActionType.OPTIMIZE_PRICING
        assert "diagnostic" in actions[0].params["optimization_scope"]

    def test_execute_unknown_type_returns_empty(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.strategies.revenue_executor import RevenueExecutor
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import OpportunityType

        opp = _make_opportunity(opp_type=OpportunityType.UA_SCALE)
        executor = RevenueExecutor()
        actions = executor.execute(opp)
        assert actions == []


# ═══════════════════════════════════════════════════════════════
# GrowthDecisionExecutor Tests
# ═══════════════════════════════════════════════════════════════


class TestGrowthDecisionExecutor:
    """GrowthDecisionExecutor 测试."""

    def test_execute_empty_opportunities(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.decision_executor import GrowthDecisionExecutor

        executor = GrowthDecisionExecutor()
        batch = executor.execute([])
        assert batch.total_opportunities == 0
        assert batch.total_actions == 0
        assert batch.actions == []

    def test_execute_creative_scale_opportunity(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.decision_executor import GrowthDecisionExecutor

        opp = _make_opportunity()
        executor = GrowthDecisionExecutor()
        batch = executor.execute([opp])
        assert batch.total_opportunities == 1
        assert batch.total_actions == 3
        assert len(batch.actions) == 3

    def test_execute_multiple_opportunities(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.decision_executor import GrowthDecisionExecutor
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import OpportunityType

        opps = [
            _make_opportunity(),
            _make_opportunity(opp_type=OpportunityType.UA_SCALE, recommended_params={
                "current_budget": 500, "recommended_budget": 3000, "spend_multiplier": 6.0,
            }),
        ]
        executor = GrowthDecisionExecutor()
        batch = executor.execute(opps)
        assert batch.total_opportunities == 2
        assert batch.total_actions == 6  # 3 creative + 3 UA

    def test_execute_with_auto_execute_generates_results(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.decision_executor import GrowthDecisionExecutor

        opp = _make_opportunity(confidence=0.9)
        executor = GrowthDecisionExecutor(auto_execute=True)
        batch = executor.execute([opp])
        assert len(batch.results) == 3
        assert all(r.success for r in batch.results)

    def test_execute_without_auto_execute_no_results(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.decision_executor import GrowthDecisionExecutor

        opp = _make_opportunity()
        executor = GrowthDecisionExecutor(auto_execute=False)
        batch = executor.execute([opp])
        assert batch.results == []

    def test_execute_override_auto_execute(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.decision_executor import GrowthDecisionExecutor

        opp = _make_opportunity(confidence=0.9)
        executor = GrowthDecisionExecutor(auto_execute=False)
        batch = executor.execute([opp], auto_execute=True)
        assert len(batch.results) == 3

    def test_execute_low_confidence_actions_fail(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.decision_executor import GrowthDecisionExecutor

        opp = _make_opportunity(confidence=0.3)
        executor = GrowthDecisionExecutor(auto_execute=True)
        batch = executor.execute([opp])
        assert batch.total_failed > 0

    def test_execute_product_id(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.decision_executor import GrowthDecisionExecutor

        opp = _make_opportunity()
        executor = GrowthDecisionExecutor()
        batch = executor.execute([opp], product_id="product_01")
        assert batch.product_id == "product_01"

    def test_execute_summary(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.decision_executor import GrowthDecisionExecutor

        opp = _make_opportunity()
        executor = GrowthDecisionExecutor()
        batch = executor.execute([opp])
        assert "clone_dna" in batch.summary
        assert "generate_variants" in batch.summary
        assert "launch_ab_test" in batch.summary

    def test_execute_all_opportunity_types(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.decision_executor import GrowthDecisionExecutor
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import OpportunityType

        opps = [
            _make_opportunity(opp_type=OpportunityType.CREATIVE_SCALE),
            _make_opportunity(opp_type=OpportunityType.CREATIVE_REFRESH),
            _make_opportunity(opp_type=OpportunityType.CREATIVE_MUTATION),
            _make_opportunity(opp_type=OpportunityType.UA_SCALE, recommended_params={
                "current_budget": 500, "recommended_budget": 3000, "spend_multiplier": 6.0,
            }),
            _make_opportunity(opp_type=OpportunityType.BUDGET_REDUCTION, recommended_params={
                "current_budget": 500, "recommended_budget": 100, "reduction_pct": 0.8,
            }),
            _make_opportunity(opp_type=OpportunityType.UA_REBALANCE, recommended_params={
                "target_roas": 1.2, "shift_pct": 0.5,
            }),
            _make_opportunity(opp_type=OpportunityType.MONETIZATION_SCALE, recommended_params={
                "d30_ltv": 5.0, "bid_increase_pct": 0.25,
            }),
            _make_opportunity(opp_type=OpportunityType.MONETIZATION_OPTIMIZE, recommended_params={
                "iap_conversion": 0.005, "optimization_target": "iap",
            }),
        ]
        executor = GrowthDecisionExecutor()
        batch = executor.execute(opps)
        assert batch.total_opportunities == 8
        assert batch.total_actions > 0

    def test_execute_batch_to_dict(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.decision_executor import GrowthDecisionExecutor

        opp = _make_opportunity()
        executor = GrowthDecisionExecutor(auto_execute=True)
        batch = executor.execute([opp], product_id="p1", date="2026-07-24")
        d = batch.to_dict()
        assert d["product_id"] == "p1"
        assert d["date"] == "2026-07-24"
        assert len(d["actions"]) == 3
        assert len(d["results"]) == 3

    def test_get_actions_by_type(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.decision_executor import GrowthDecisionExecutor
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import ExecutionActionType

        opp = _make_opportunity()
        executor = GrowthDecisionExecutor()
        batch = executor.execute([opp])
        clone_actions = GrowthDecisionExecutor.get_actions_by_type(
            batch.actions, ExecutionActionType.CLONE_DNA,
        )
        assert len(clone_actions) == 1
        assert clone_actions[0].action_type == ExecutionActionType.CLONE_DNA

    def test_get_actions_by_approval(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.decision_executor import GrowthDecisionExecutor
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import ApprovalLevel, OpportunityType

        opp = _make_opportunity(
            opp_type=OpportunityType.UA_SCALE,
            recommended_params={"current_budget": 500, "recommended_budget": 3000, "spend_multiplier": 6.0},
        )
        executor = GrowthDecisionExecutor()
        batch = executor.execute([opp])
        high_actions = GrowthDecisionExecutor.get_actions_by_approval(
            batch.actions, ApprovalLevel.HIGH,
        )
        assert len(high_actions) >= 1

    def test_get_autonomous_actions(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.decision_executor import GrowthDecisionExecutor

        opp = _make_opportunity()
        executor = GrowthDecisionExecutor()
        batch = executor.execute([opp])
        auto_actions = GrowthDecisionExecutor.get_autonomous_actions(batch.actions)
        assert len(auto_actions) >= 2  # clone_dna + generate_variants are AUTO

    def test_get_actions_by_priority(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.decision_executor import GrowthDecisionExecutor
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import OpportunityPriority

        opp = _make_opportunity(priority=OpportunityPriority.HIGH)
        executor = GrowthDecisionExecutor()
        batch = executor.execute([opp])
        high_actions = GrowthDecisionExecutor.get_actions_by_priority(
            batch.actions, OpportunityPriority.HIGH,
        )
        assert len(high_actions) >= 1

    def test_get_successful_and_failed_results(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.decision_executor import GrowthDecisionExecutor

        opp = _make_opportunity(confidence=0.3)
        executor = GrowthDecisionExecutor(auto_execute=True)
        batch = executor.execute([opp])
        failed = GrowthDecisionExecutor.get_failed_results(batch.results)
        assert len(failed) > 0

    def test_auto_execute_property(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.decision_executor import GrowthDecisionExecutor

        executor = GrowthDecisionExecutor()
        assert executor.auto_execute is False
        executor.auto_execute = True
        assert executor.auto_execute is True


# ═══════════════════════════════════════════════════════════════
# Edge Cases
# ═══════════════════════════════════════════════════════════════


class TestEdgeCases:
    """边界条件测试."""

    def test_zero_confidence_opportunity(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.decision_executor import GrowthDecisionExecutor

        opp = _make_opportunity(confidence=0.0)
        executor = GrowthDecisionExecutor()
        batch = executor.execute([opp])
        assert batch.total_actions > 0  # Actions still generated

    def test_empty_recommended_params(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.decision_executor import GrowthDecisionExecutor

        opp = _make_opportunity(recommended_params={})
        executor = GrowthDecisionExecutor()
        batch = executor.execute([opp])
        assert batch.total_actions > 0  # Uses defaults

    def test_many_opportunities(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.decision_executor import GrowthDecisionExecutor

        opps = [_make_opportunity(entity_id=f"c{i:03d}") for i in range(50)]
        executor = GrowthDecisionExecutor()
        batch = executor.execute(opps)
        assert batch.total_opportunities == 50
        assert batch.total_actions == 150  # 3 per creative scale

    def test_all_actions_have_explanations(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.decision_executor import GrowthDecisionExecutor
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import (
            OpportunityType, OpportunityPriority,
        )

        opps = [
            _make_opportunity(opp_type=OpportunityType.CREATIVE_SCALE, priority=OpportunityPriority.HIGH),
            _make_opportunity(opp_type=OpportunityType.CREATIVE_REFRESH, priority=OpportunityPriority.HIGH),
            _make_opportunity(opp_type=OpportunityType.UA_SCALE, priority=OpportunityPriority.HIGH, recommended_params={
                "current_budget": 500, "recommended_budget": 3000, "spend_multiplier": 6.0,
            }),
            _make_opportunity(opp_type=OpportunityType.BUDGET_REDUCTION, priority=OpportunityPriority.CRITICAL, recommended_params={
                "current_budget": 500, "recommended_budget": 100, "reduction_pct": 0.8,
            }),
        ]
        executor = GrowthDecisionExecutor()
        batch = executor.execute(opps)
        for action in batch.actions:
            assert action.explanation, f"Action {action.action_type.value} has no explanation"

    def test_low_confidence_simulation_fails(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.decision_executor import GrowthDecisionExecutor

        opp = _make_opportunity(confidence=0.1)
        executor = GrowthDecisionExecutor(auto_execute=True)
        batch = executor.execute([opp])
        for result in batch.results:
            assert result.success is False

    def test_execution_creates_unique_action_ids(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.decision_executor import GrowthDecisionExecutor

        opps = [_make_opportunity() for _ in range(3)]
        executor = GrowthDecisionExecutor()
        batch = executor.execute(opps)
        action_ids = [a.action_id for a in batch.actions]
        assert len(action_ids) == len(set(action_ids))


# ═══════════════════════════════════════════════════════════════
# Integration Scenarios
# ═══════════════════════════════════════════════════════════════


class TestIntegrationScenarios:
    """集成场景测试."""

    def test_full_pipeline_opportunity_to_action(self):
        """完整流水线: Opportunity → ExecutionAction."""
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.decision_executor import GrowthDecisionExecutor
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import ExecutionActionType

        opp = _make_opportunity(
            entity_id="creative_winner_001",
            recommended_params={"mutation_count": 5, "test_budget": 500},
        )
        executor = GrowthDecisionExecutor()
        batch = executor.execute([opp], product_id="game_x")

        assert batch.total_actions == 3
        assert batch.actions[0].entity_id == "creative_winner_001"
        assert batch.actions[0].action_type == ExecutionActionType.CLONE_DNA
        assert batch.actions[1].action_type == ExecutionActionType.GENERATE_VARIANTS
        assert batch.actions[2].action_type == ExecutionActionType.LAUNCH_AB_TEST

    def test_full_pipeline_with_execution(self):
        """完整流水线: Opportunity → ExecutionAction → ExecutionResult."""
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.decision_executor import GrowthDecisionExecutor

        opp = _make_opportunity(confidence=0.9)
        executor = GrowthDecisionExecutor(auto_execute=True)
        batch = executor.execute([opp], product_id="game_x", date="2026-07-24")

        assert batch.total_actions == 3
        assert batch.total_success == 3
        assert batch.total_failed == 0
        assert batch.elapsed_ms > 0

    def test_winner_to_scale_full_flow(self):
        """Winner 素材 → Scale 机会 → 执行动作."""
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.decision_executor import GrowthDecisionExecutor
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import (
            ExecutionActionType, ApprovalLevel,
        )

        opp = _make_opportunity(
            entity_id="winner_001",
            confidence=0.95,
            recommended_params={"mutation_count": 8, "test_budget": 1000},
        )
        executor = GrowthDecisionExecutor()
        batch = executor.execute([opp])

        # Clone DNA
        clone = batch.actions[0]
        assert clone.action_type == ExecutionActionType.CLONE_DNA
        assert clone.approval_level == ApprovalLevel.AUTO
        assert "clone_hook" in clone.params

        # Generate Variants
        generate = batch.actions[1]
        assert generate.action_type == ExecutionActionType.GENERATE_VARIANTS
        assert generate.params["variant_count"] == 8

        # Launch AB Test
        ab_test = batch.actions[2]
        assert ab_test.action_type == ExecutionActionType.LAUNCH_AB_TEST
        assert ab_test.params["test_budget"] == 1000

    def test_fatigue_to_refresh_full_flow(self):
        """Fatigue 素材 → Refresh 机会 → 执行动作."""
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.decision_executor import GrowthDecisionExecutor
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import (
            OpportunityType, ExecutionActionType,
        )

        opp = _make_opportunity(
            opp_type=OpportunityType.CREATIVE_REFRESH,
            entity_id="fatigued_001",
            confidence=0.85,
            recommended_params={
                "hook_contrast_delta": 0.25,
                "visual_density_delta": 0.15,
                "population_size": 8,
            },
        )
        executor = GrowthDecisionExecutor()
        batch = executor.execute([opp])

        assert batch.actions[0].action_type == ExecutionActionType.MUTATE_HOOK
        assert batch.actions[1].action_type == ExecutionActionType.MUTATE_VISUAL
        assert batch.actions[2].action_type == ExecutionActionType.CREATE_POPULATION
        assert batch.actions[3].action_type == ExecutionActionType.REPLACE_CREATIVE

    def test_budget_waste_to_reduction_flow(self):
        """Budget Waste → Reduction 机会 → 执行动作."""
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.decision_executor import GrowthDecisionExecutor
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import (
            OpportunityType, ExecutionActionType, OpportunityPriority,
        )

        opp = _make_opportunity(
            opp_type=OpportunityType.BUDGET_REDUCTION,
            entity_id="camp_waste_001",
            priority=OpportunityPriority.CRITICAL,
            confidence=0.88,
            recommended_params={
                "current_budget": 1000,
                "recommended_budget": 200,
                "reduction_pct": 0.8,
            },
        )
        executor = GrowthDecisionExecutor()
        batch = executor.execute([opp])

        assert batch.actions[0].action_type == ExecutionActionType.REDUCE_BUDGET
        assert batch.actions[0].params["current_daily_budget"] == 1000
        assert batch.actions[0].params["new_daily_budget"] == 200
        assert batch.actions[1].action_type == ExecutionActionType.PAUSE_CAMPAIGN

    def test_actions_preserve_opportunity_link(self):
        """执行动作保留与机会的关联."""
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.decision_executor import GrowthDecisionExecutor

        opp = _make_opportunity(entity_id="linked_creative")
        executor = GrowthDecisionExecutor()
        batch = executor.execute([opp])

        for action in batch.actions:
            assert action.source_opportunity_id == opp.opportunity_id
            assert action.entity_id == "linked_creative"

    def test_batch_has_all_statistics(self):
        """ExecutionBatch 包含完整统计."""
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.decision_executor import GrowthDecisionExecutor

        opp = _make_opportunity(confidence=0.9)
        executor = GrowthDecisionExecutor(auto_execute=True)
        batch = executor.execute([opp], product_id="p1")

        assert batch.total_opportunities == 1
        assert batch.total_actions == 3
        assert batch.total_success == 3
        assert batch.total_failed == 0
        assert batch.total_rolled_back == 0
        assert batch.elapsed_ms > 0
        assert batch.created_at
        assert "clone_dna" in batch.summary