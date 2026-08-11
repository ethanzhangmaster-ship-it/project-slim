"""E13.3.3 Revenue Executor — 收入/变现机会 → 执行动作映射.

规则:
  - MONETIZATION_SCALE → INCREASE_BUDGET + INCREASE_RETENTION + CREATE_HIGH_VALUE_AUDIENCE
  - MONETIZATION_OPTIMIZE → OPTIMIZE_PRICING + OPTIMIZE_AD_PLACEMENT

连接:
  - OPTIMIZE_PRICING → IAP shop/pricing system
  - OPTIMIZE_AD_PLACEMENT → IAA ad mediation system
  - INCREASE_RETENTION → Player Journey / FTUE optimization
  - CREATE_HIGH_VALUE_AUDIENCE → UA targeting / lookalike audiences
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


class RevenueExecutor:
    """收入执行器 — 将收入/变现机会转换为可执行的变现操作.

    对接:
      - IAP: 商店优化、定价策略、付费转化漏斗
      - IAA: 广告位优化、广告频次、填充率
      - Retention: 玩家旅程优化、FTUE 改进
      - UA: 高价值用户定向、出价策略
    """

    def execute(self, opportunity: GrowthOpportunity) -> list[ExecutionAction]:
        """将收入/变现机会转换为执行动作列表.

        Args:
            opportunity: 收入/变现类 GrowthOpportunity

        Returns:
            list[ExecutionAction]: 可执行的变现操作列表
        """
        if opportunity.opportunity_type == OpportunityType.MONETIZATION_SCALE:
            return self._execute_monetization_scale(opportunity)
        elif opportunity.opportunity_type == OpportunityType.MONETIZATION_OPTIMIZE:
            return self._execute_monetization_optimize(opportunity)
        return []

    # ═══════════════════════════════════════════════════════════
    # Monetization Scale → Increase Budget + Retention + Audience
    # ═══════════════════════════════════════════════════════════

    def _execute_monetization_scale(self, opportunity: GrowthOpportunity) -> list[ExecutionAction]:
        actions: list[ExecutionAction] = []

        params = opportunity.recommended_params
        entity_id = opportunity.entity_id
        opp_id = opportunity.opportunity_id

        d30_ltv = params.get("d30_ltv", 0)
        bid_increase_pct = params.get("bid_increase_pct", 0.25)

        # Action 1: Increase UA Budget (based on LTV upside)
        increase_action = ExecutionAction(
            action_type=ExecutionActionType.INCREASE_BUDGET,
            source_opportunity_id=opp_id,
            source_opportunity_type=opportunity.opportunity_type,
            entity_id=entity_id,
            entity_type="campaign",
            priority=opportunity.priority,
            confidence=opportunity.confidence,
            params={
                "entity_id": entity_id,
                "bid_increase_pct": bid_increase_pct,
                "d30_ltv": d30_ltv,
                "reason": "ltv_upside",
                "ltv_based_bidding": True,
                "target_roas": params.get("target_roas", 2.5),
            },
            approval_level=ApprovalLevel.LOW,
            expected_impact=f"Increase UA bid by +{bid_increase_pct*100:.0f}% based on LTV=${d30_ltv:.2f}",
            rollback_action=ExecutionActionType.REDUCE_BUDGET,
            explanation=f"Increase UA bid by +{bid_increase_pct*100:.0f}% for {entity_id} "
                        f"based on D30 LTV=${d30_ltv:.2f} upside potential.",
        )
        actions.append(increase_action)

        # Action 2: Increase Retention Investment
        retention_budget = params.get("retention_boost_budget", d30_ltv * 0.1)
        retention_action = ExecutionAction(
            action_type=ExecutionActionType.INCREASE_RETENTION,
            source_opportunity_id=opp_id,
            source_opportunity_type=opportunity.opportunity_type,
            entity_id=entity_id,
            entity_type="product",
            priority=OpportunityPriority.MEDIUM,
            confidence=opportunity.confidence * 0.8,
            params={
                "product_id": entity_id,
                "retention_boost_budget": retention_budget,
                "focus_areas": ["ftue_optimization", "d7_engagement", "push_notifications"],
                "target_retention_lift": 0.10,
            },
            approval_level=ApprovalLevel.LOW,
            expected_impact=f"Boost retention investment by ${retention_budget:.2f}",
            rollback_action=None,
            explanation=f"Invest ${retention_budget:.2f} in retention optimization "
                        f"to capture high-LTV user value.",
        )
        actions.append(retention_action)

        # Action 3: Create High-Value Audience
        audience_action = ExecutionAction(
            action_type=ExecutionActionType.CREATE_HIGH_VALUE_AUDIENCE,
            source_opportunity_id=opp_id,
            source_opportunity_type=opportunity.opportunity_type,
            entity_id=entity_id,
            entity_type="audience",
            priority=OpportunityPriority.MEDIUM,
            confidence=opportunity.confidence * 0.75,
            params={
                "product_id": entity_id,
                "audience_type": "high_ltv_lookalike",
                "lookalike_pct": 2,
                "seed_source": "top_10pct_payers",
                "min_ltv_threshold": d30_ltv * 0.5,
            },
            approval_level=ApprovalLevel.LOW,
            expected_impact=f"Create high-LTV lookalike audience from top payers",
            rollback_action=None,
            explanation=f"Create lookalike audience from top 10% payers "
                        f"(LTV > ${d30_ltv * 0.5:.2f}) for {entity_id}.",
        )
        actions.append(audience_action)

        return actions

    # ═══════════════════════════════════════════════════════════
    # Monetization Optimize → Pricing + Ad Placement
    # ═══════════════════════════════════════════════════════════

    def _execute_monetization_optimize(self, opportunity: GrowthOpportunity) -> list[ExecutionAction]:
        actions: list[ExecutionAction] = []

        params = opportunity.recommended_params
        entity_id = opportunity.entity_id
        opp_id = opportunity.opportunity_id

        iap_conversion = params.get("iap_conversion", 0)
        ad_arpdau = params.get("ad_arpdau", 0)
        optimization_target = params.get("optimization_target", "iap")

        # Action 1: Optimize Pricing (IAP)
        if optimization_target in ("iap", "both") or iap_conversion > 0:
            pricing_action = ExecutionAction(
                action_type=ExecutionActionType.OPTIMIZE_PRICING,
                source_opportunity_id=opp_id,
                source_opportunity_type=opportunity.opportunity_type,
                entity_id=entity_id,
                entity_type="product",
                priority=opportunity.priority,
                confidence=opportunity.confidence,
                params={
                    "product_id": entity_id,
                    "current_iap_conversion": iap_conversion,
                    "optimization_scope": "full",
                    "actions": [
                        "analyze_payer_funnel",
                        "optimize_shop_experience",
                        "adjust_pricing_tiers",
                        "add_limited_time_offers",
                    ],
                    "target_conversion_lift": 0.20,
                },
                approval_level=ApprovalLevel.MEDIUM,
                expected_impact=f"Optimize IAP pricing to lift conversion from {iap_conversion:.4f}",
                rollback_action=None,
                explanation=f"Optimize IAP pricing and shop experience for {entity_id} "
                            f"to improve payer conversion from {iap_conversion:.4f}.",
            )
            actions.append(pricing_action)

        # Action 2: Optimize Ad Placement (IAA)
        if optimization_target in ("iaa", "both") or ad_arpdau > 0:
            ad_action = ExecutionAction(
                action_type=ExecutionActionType.OPTIMIZE_AD_PLACEMENT,
                source_opportunity_id=opp_id,
                source_opportunity_type=opportunity.opportunity_type,
                entity_id=entity_id,
                entity_type="product",
                priority=opportunity.priority,
                confidence=opportunity.confidence,
                params={
                    "product_id": entity_id,
                    "current_arpdau": ad_arpdau,
                    "optimization_scope": "full",
                    "actions": [
                        "optimize_ad_placement",
                        "adjust_ad_frequency",
                        "test_ad_networks",
                        "improve_ad_fill_rate",
                    ],
                    "target_arpdau_lift": 0.15,
                },
                approval_level=ApprovalLevel.MEDIUM,
                expected_impact=f"Optimize IAA placement to lift ARPDAU from ${ad_arpdau:.4f}",
                rollback_action=None,
                explanation=f"Optimize IAA ad placement and frequency for {entity_id} "
                            f"to improve ARPDAU from ${ad_arpdau:.4f}.",
            )
            actions.append(ad_action)

        # Fallback: if no specific optimization target, generate generic optimization
        if not actions:
            generic_action = ExecutionAction(
                action_type=ExecutionActionType.OPTIMIZE_PRICING,
                source_opportunity_id=opp_id,
                source_opportunity_type=opportunity.opportunity_type,
                entity_id=entity_id,
                entity_type="product",
                priority=opportunity.priority,
                confidence=opportunity.confidence,
                params={
                    "product_id": entity_id,
                    "optimization_scope": "diagnostic",
                    "actions": ["analyze_monetization_funnel", "identify_revenue_leaks"],
                },
                approval_level=ApprovalLevel.LOW,
                expected_impact="Diagnose monetization issues and identify revenue leaks",
                rollback_action=None,
                explanation=f"Run diagnostic analysis on monetization funnel for {entity_id} "
                            f"to identify revenue leak sources.",
            )
            actions.append(generic_action)

        return actions