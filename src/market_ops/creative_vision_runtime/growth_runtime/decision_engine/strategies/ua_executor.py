"""E13.3.3 UA Executor — UA 机会 → 执行动作映射.

规则:
  - UA_SCALE → INCREASE_BUDGET + DUPLICATE_CAMPAIGN + EXPAND_TARGETING
  - BUDGET_REDUCTION → REDUCE_BUDGET + PAUSE_CAMPAIGN + REALLOCATE_BUDGET
  - UA_REBALANCE → REALLOCATE_BUDGET + ADJUST_BID

连接 Meta Ads API:
  - INCREASE_BUDGET → Meta Ads API: update campaign budget
  - REDUCE_BUDGET → Meta Ads API: update campaign budget
  - DUPLICATE_CAMPAIGN → Meta Ads API: create campaign copy
  - PAUSE_CAMPAIGN → Meta Ads API: update campaign status
  - EXPAND_TARGETING → Meta Ads API: update ad set targeting
  - REALLOCATE_BUDGET → Meta Ads API: budget reallocation
  - ADJUST_BID → Meta Ads API: update bid strategy
"""

from __future__ import annotations

from typing import Any

from ..models import (
    ApprovalLevel,
    ExecutionAction,
    ExecutionActionType,
    GrowthOpportunity,
    OpportunityPriority,
    OpportunityType,
)


class UAExecutor:
    """UA 执行器 — 将 UA 机会转换为可执行的广告操作.

    对接 Meta Ads API / Google Ads API:
      - INCREASE_BUDGET / REDUCE_BUDGET → update_campaign_budget()
      - DUPLICATE_CAMPAIGN → create_campaign_copy()
      - PAUSE_CAMPAIGN → update_campaign_status("PAUSED")
      - EXPAND_TARGETING → update_adset_targeting()
      - REALLOCATE_BUDGET → reallocate_campaign_budgets()
      - ADJUST_BID → update_bid_strategy()
    """

    def execute(self, opportunity: GrowthOpportunity) -> list[ExecutionAction]:
        """将 UA 机会转换为执行动作列表.

        Args:
            opportunity: UA 类 GrowthOpportunity

        Returns:
            list[ExecutionAction]: 可执行的 UA 操作列表
        """
        if opportunity.opportunity_type == OpportunityType.UA_SCALE:
            return self._execute_scale(opportunity)
        elif opportunity.opportunity_type == OpportunityType.BUDGET_REDUCTION:
            return self._execute_reduction(opportunity)
        elif opportunity.opportunity_type == OpportunityType.UA_REBALANCE:
            return self._execute_rebalance(opportunity)
        return []

    # ═══════════════════════════════════════════════════════════
    # UA Scale → Increase Budget + Duplicate Campaign + Expand
    # ═══════════════════════════════════════════════════════════

    def _execute_scale(self, opportunity: GrowthOpportunity) -> list[ExecutionAction]:
        actions: list[ExecutionAction] = []

        params = opportunity.recommended_params
        entity_id = opportunity.entity_id
        opp_id = opportunity.opportunity_id

        current_budget = params.get("current_budget", 500)
        recommended_budget = params.get("recommended_budget", 3000)
        spend_multiplier = params.get("spend_multiplier", 6.0)
        scale_strategy = params.get("scale_strategy", "moderate")

        # Determine approval level based on budget scale
        if spend_multiplier > 5.0:
            approval = ApprovalLevel.HIGH
        elif spend_multiplier > 3.0:
            approval = ApprovalLevel.MEDIUM
        else:
            approval = ApprovalLevel.LOW

        # Action 1: Increase Budget
        increase_action = ExecutionAction(
            action_type=ExecutionActionType.INCREASE_BUDGET,
            source_opportunity_id=opp_id,
            source_opportunity_type=opportunity.opportunity_type,
            entity_id=entity_id,
            entity_type="campaign",
            priority=opportunity.priority,
            confidence=opportunity.confidence,
            params={
                "campaign_id": entity_id,
                "current_daily_budget": current_budget,
                "new_daily_budget": recommended_budget,
                "spend_multiplier": spend_multiplier,
                "scale_strategy": scale_strategy,
                "incremental_steps": 3 if scale_strategy == "aggressive" else 5,
            },
            approval_level=approval,
            expected_impact=f"Increase budget ${current_budget:.0f} → ${recommended_budget:.0f}/day ({spend_multiplier:.0f}x)",
            rollback_action=ExecutionActionType.REDUCE_BUDGET,
            explanation=f"Scale campaign {entity_id} budget from ${current_budget:.0f} to "
                        f"${recommended_budget:.0f}/day ({spend_multiplier:.0f}x) using "
                        f"{scale_strategy} strategy.",
        )
        actions.append(increase_action)

        # Action 2: Duplicate Campaign
        dup_action = ExecutionAction(
            action_type=ExecutionActionType.DUPLICATE_CAMPAIGN,
            source_opportunity_id=opp_id,
            source_opportunity_type=opportunity.opportunity_type,
            entity_id=entity_id,
            entity_type="campaign",
            priority=OpportunityPriority.MEDIUM,
            confidence=opportunity.confidence * 0.8,
            params={
                "source_campaign_id": entity_id,
                "duplicate_count": 2 if scale_strategy == "aggressive" else 1,
                "copy_creatives": True,
                "copy_targeting": True,
                "increment_budget": True,
            },
            approval_level=ApprovalLevel.LOW,
            expected_impact=f"Duplicate campaign {entity_id} to scale reach",
            rollback_action=ExecutionActionType.PAUSE_CAMPAIGN,
            explanation=f"Duplicate campaign {entity_id} to create additional reach "
                        f"while maintaining original campaign structure.",
        )
        actions.append(dup_action)

        # Action 3: Expand Targeting
        expand_action = ExecutionAction(
            action_type=ExecutionActionType.EXPAND_TARGETING,
            source_opportunity_id=opp_id,
            source_opportunity_type=opportunity.opportunity_type,
            entity_id=entity_id,
            entity_type="campaign",
            priority=OpportunityPriority.MEDIUM,
            confidence=opportunity.confidence * 0.7,
            params={
                "campaign_id": entity_id,
                "expand_lookalike": True,
                "lookalike_pct": 3 if scale_strategy == "aggressive" else 2,
                "expand_geo": ["US", "GB", "CA", "AU"] if scale_strategy == "aggressive" else ["US"],
                "expand_age_range": True,
            },
            approval_level=ApprovalLevel.LOW,
            expected_impact="Expand targeting to new audiences and geographies",
            rollback_action=ExecutionActionType.REALLOCATE_BUDGET,
            explanation=f"Expand targeting for campaign {entity_id}: "
                        f"add lookalike audiences and broaden geographic reach.",
        )
        actions.append(expand_action)

        return actions

    # ═══════════════════════════════════════════════════════════
    # Budget Reduction → Reduce Budget + Pause + Reallocate
    # ═══════════════════════════════════════════════════════════

    def _execute_reduction(self, opportunity: GrowthOpportunity) -> list[ExecutionAction]:
        actions: list[ExecutionAction] = []

        params = opportunity.recommended_params
        entity_id = opportunity.entity_id
        opp_id = opportunity.opportunity_id

        current_budget = params.get("current_budget", 500)
        recommended_budget = params.get("recommended_budget", 100)
        reduction_pct = params.get("reduction_pct", 0.8)

        # Action 1: Reduce Budget
        reduce_action = ExecutionAction(
            action_type=ExecutionActionType.REDUCE_BUDGET,
            source_opportunity_id=opp_id,
            source_opportunity_type=opportunity.opportunity_type,
            entity_id=entity_id,
            entity_type="campaign",
            priority=opportunity.priority,
            confidence=opportunity.confidence,
            params={
                "campaign_id": entity_id,
                "current_daily_budget": current_budget,
                "new_daily_budget": recommended_budget,
                "reduction_pct": reduction_pct,
                "reason": "budget_waste",
            },
            approval_level=self._map_approval(opportunity.priority),
            expected_impact=f"Reduce budget ${current_budget:.0f} → ${recommended_budget:.0f}/day (-{reduction_pct*100:.0f}%)",
            rollback_action=ExecutionActionType.INCREASE_BUDGET,
            explanation=f"Reduce budget for campaign {entity_id} from ${current_budget:.0f} to "
                        f"${recommended_budget:.0f}/day (-{reduction_pct*100:.0f}%) due to waste.",
        )
        actions.append(reduce_action)

        # Action 2: Pause Campaign (if budget is critical)
        if reduction_pct >= 0.7:
            pause_action = ExecutionAction(
                action_type=ExecutionActionType.PAUSE_CAMPAIGN,
                source_opportunity_id=opp_id,
                source_opportunity_type=opportunity.opportunity_type,
                entity_id=entity_id,
                entity_type="campaign",
                priority=OpportunityPriority.HIGH,
                confidence=opportunity.confidence * 0.9,
                params={
                    "campaign_id": entity_id,
                    "pause_reason": "severe_budget_waste",
                    "auto_resume_threshold": 1.2,
                    "auto_resume_metric": "d7_roas",
                },
                approval_level=ApprovalLevel.MEDIUM,
                expected_impact=f"Pause campaign {entity_id} to stop waste",
                rollback_action=None,
                explanation=f"Pause campaign {entity_id} due to severe budget waste "
                            f"(reduction >70%). Auto-resume when ROAS > 1.2.",
            )
            actions.append(pause_action)

        # Action 3: Reallocate Budget
        reallocate_action = ExecutionAction(
            action_type=ExecutionActionType.REALLOCATE_BUDGET,
            source_opportunity_id=opp_id,
            source_opportunity_type=opportunity.opportunity_type,
            entity_id=entity_id,
            entity_type="campaign",
            priority=OpportunityPriority.MEDIUM,
            confidence=opportunity.confidence * 0.7,
            params={
                "source_campaign_id": entity_id,
                "reallocation_pct": reduction_pct,
                "target_metric": "d30_roas",
                "target_min_roas": 1.5,
            },
            approval_level=ApprovalLevel.LOW,
            expected_impact=f"Reallocate {reduction_pct*100:.0f}% of budget to high-ROAS campaigns",
            rollback_action=ExecutionActionType.REALLOCATE_BUDGET,
            explanation=f"Reallocate {reduction_pct*100:.0f}% of budget from {entity_id} "
                        f"to campaigns with ROAS > 1.5.",
        )
        actions.append(reallocate_action)

        return actions

    # ═══════════════════════════════════════════════════════════
    # UA Rebalance → Reallocate Budget + Adjust Bid
    # ═══════════════════════════════════════════════════════════

    def _execute_rebalance(self, opportunity: GrowthOpportunity) -> list[ExecutionAction]:
        actions: list[ExecutionAction] = []

        params = opportunity.recommended_params
        entity_id = opportunity.entity_id
        opp_id = opportunity.opportunity_id

        target_roas = params.get("target_roas", 1.2)
        shift_pct = params.get("shift_pct", 0.5)

        # Action 1: Reallocate Budget
        reallocate_action = ExecutionAction(
            action_type=ExecutionActionType.REALLOCATE_BUDGET,
            source_opportunity_id=opp_id,
            source_opportunity_type=opportunity.opportunity_type,
            entity_id=entity_id,
            entity_type="campaign",
            priority=opportunity.priority,
            confidence=opportunity.confidence,
            params={
                "source_campaign_id": entity_id,
                "reallocation_pct": shift_pct,
                "target_metric": "roas",
                "target_min_roas": target_roas,
                "rebalance_strategy": "roas_weighted",
            },
            approval_level=ApprovalLevel.LOW,
            expected_impact=f"Rebalance {shift_pct*100:.0f}% of budget toward ROAS > {target_roas}",
            rollback_action=ExecutionActionType.REALLOCATE_BUDGET,
            explanation=f"Rebalance {shift_pct*100:.0f}% of budget from {entity_id} "
                        f"toward campaigns with ROAS > {target_roas}.",
        )
        actions.append(reallocate_action)

        # Action 2: Adjust Bid
        adjust_bid_action = ExecutionAction(
            action_type=ExecutionActionType.ADJUST_BID,
            source_opportunity_id=opp_id,
            source_opportunity_type=opportunity.opportunity_type,
            entity_id=entity_id,
            entity_type="campaign",
            priority=OpportunityPriority.MEDIUM,
            confidence=opportunity.confidence * 0.8,
            params={
                "campaign_id": entity_id,
                "bid_strategy": "target_cost",
                "target_roas": target_roas,
                "bid_cap_multiplier": 0.8,
                "adjustment_reason": "rebalance_for_efficiency",
            },
            approval_level=ApprovalLevel.LOW,
            expected_impact=f"Adjust bid strategy to target ROAS {target_roas}",
            rollback_action=ExecutionActionType.ADJUST_BID,
            explanation=f"Adjust bid strategy for {entity_id} to target ROAS {target_roas} "
                        f"with 80% bid cap multiplier.",
        )
        actions.append(adjust_bid_action)

        return actions

    # ═══════════════════════════════════════════════════════════
    # Helpers
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def _map_approval(priority: OpportunityPriority) -> ApprovalLevel:
        """将机会优先级映射为审批级别."""
        approval_map = {
            OpportunityPriority.CRITICAL: ApprovalLevel.CRITICAL,
            OpportunityPriority.HIGH: ApprovalLevel.HIGH,
            OpportunityPriority.MEDIUM: ApprovalLevel.MEDIUM,
            OpportunityPriority.LOW: ApprovalLevel.LOW,
        }
        return approval_map.get(priority, ApprovalLevel.MEDIUM)