"""E13.3.2 Revenue Opportunity Mapper — 收入/变现信号 → 机会映射.

规则:
  - LTV_UPSIDE → MONETIZATION_SCALE + UA_SCALE
  - ROAS_DROP → BUDGET_REDUCTION + UA_REBALANCE
  - MONETIZATION_ISSUE → MONETIZATION_OPTIMIZE
"""

from __future__ import annotations

from typing import Any

from ..models import (
    GrowthOpportunity,
    GrowthSignal,
    OpportunityPriority,
    OpportunityType,
    SignalType,
)


# ═══════════════════════════════════════════════════════════════
# Default Gain Estimates
# ═══════════════════════════════════════════════════════════════

DEFAULT_GAINS = {
    OpportunityType.MONETIZATION_SCALE: 0.30,    # 预期提升 30%
    OpportunityType.MONETIZATION_OPTIMIZE: 0.15,  # 预期提升 15%
    OpportunityType.UA_SCALE: 0.25,               # 预期提升 25%
    OpportunityType.BUDGET_REDUCTION: 0.20,       # 预期节省 20%
    OpportunityType.UA_REBALANCE: 0.12,            # 预期提升 12%
}


class RevenueOpportunityMapper:
    """收入/变现机会映射器.

    将收入/变现类信号 (ROAS Drop / LTV Upside / Monetization Issue)
    转换为可执行的收入优化机会.
    """

    def __init__(self, gains: dict[OpportunityType, float] | None = None):
        self._gains = {**DEFAULT_GAINS, **(gains or {})}

    def map(self, signal: GrowthSignal) -> list[GrowthOpportunity]:
        """将一个信号映射为多个机会.

        Args:
            signal: 收入/变现类 GrowthSignal

        Returns:
            list[GrowthOpportunity]: 对应的增长机会列表
        """
        if signal.signal_type == SignalType.LTV_UPSIDE:
            return self._map_ltv_upside(signal)
        elif signal.signal_type == SignalType.ROAS_DROP:
            return self._map_roas_drop(signal)
        elif signal.signal_type == SignalType.MONETIZATION_ISSUE:
            return self._map_monetization_issue(signal)
        return []

    # ═══════════════════════════════════════════════════════════
    # LTV Upside → Monetization Scale + UA Scale
    # ═══════════════════════════════════════════════════════════

    def _map_ltv_upside(self, signal: GrowthSignal) -> list[GrowthOpportunity]:
        opportunities: list[GrowthOpportunity] = []

        d7_ltv = signal.metrics.get("d7_ltv", 0)
        d30_ltv = signal.metrics.get("d30_ltv", 0)
        ltv_ratio = signal.metrics.get("ltv_ratio", 0)

        # Opportunity 1: Monetization Scale
        monetization_opp = GrowthOpportunity(
            opportunity_type=OpportunityType.MONETIZATION_SCALE,
            source_signal=signal,
            source_signal_id=signal.signal_id,
            entity_id=signal.entity_id,
            entity_type=signal.entity_type,
            priority=self._map_priority(signal),
            confidence=signal.confidence,
            expected_gain=self._gains[OpportunityType.MONETIZATION_SCALE],
            expected_gain_pct=self._gains[OpportunityType.MONETIZATION_SCALE] * 100,
            actions=[
                "increase_ua_bid",
                "increase_retention_investment",
                "create_high_value_audience",
                "optimize_pricing_for_ltv",
            ],
            recommended_params={
                "d7_ltv": d7_ltv,
                "d30_ltv": d30_ltv,
                "ltv_ratio": ltv_ratio,
                "bid_increase_pct": min(0.5, ltv_ratio * 0.5),
                "retention_boost_budget": d30_ltv * 0.1,
            },
            evidence={
                "d7_ltv": d7_ltv,
                "d30_ltv": d30_ltv,
                "ltv_gain": signal.metrics.get("ltv_absolute_gain", 0),
            },
            risk="low",
            business_value=1.0,
            explanation=(
                f"LTV upside detected for {signal.entity_id}: "
                f"D7=${d7_ltv:.2f} → D30=${d30_ltv:.2f} "
                f"(+{ltv_ratio*100:.0f}%). "
                f"Increase UA bid and retention investment to capture high-LTV users."
            ),
        )
        opportunities.append(monetization_opp)

        # Opportunity 2: UA Scale (via LTV signal)
        ua_scale_opp = GrowthOpportunity(
            opportunity_type=OpportunityType.UA_SCALE,
            source_signal=signal,
            source_signal_id=signal.signal_id,
            entity_id=signal.entity_id,
            entity_type=signal.entity_type,
            priority=OpportunityPriority.HIGH if signal.confidence > 0.8 else OpportunityPriority.MEDIUM,
            confidence=signal.confidence * 0.8,
            expected_gain=self._gains[OpportunityType.UA_SCALE],
            expected_gain_pct=self._gains[OpportunityType.UA_SCALE] * 100,
            actions=[
                "increase_ua_spend",
                "target_high_ltv_segments",
                "expand_lookalike_audiences",
            ],
            recommended_params={
                "spend_multiplier": 2.0,
                "ltv_based_bidding": True,
                "target_roas": d30_ltv / (d30_ltv * 0.4),
            },
            evidence={
                "d30_ltv": d30_ltv,
                "ltv_ratio": ltv_ratio,
            },
            risk="medium",
            business_value=0.8,
            explanation=(
                f"Scale UA based on LTV upside: D30 LTV=${d30_ltv:.2f} "
                f"supports higher acquisition costs."
            ),
        )
        opportunities.append(ua_scale_opp)

        return opportunities

    # ═══════════════════════════════════════════════════════════
    # ROAS Drop → Budget Reduction + Rebalance
    # ═══════════════════════════════════════════════════════════

    def _map_roas_drop(self, signal: GrowthSignal) -> list[GrowthOpportunity]:
        opportunities: list[GrowthOpportunity] = []

        current_roas = signal.metrics.get("current_d7_roas", 0)
        predicted_roas = signal.metrics.get("predicted_roas", 0)
        decay_pct = signal.metrics.get("roas_decay_pct", 0)

        # Opportunity 1: Budget Reduction
        reduction_opp = GrowthOpportunity(
            opportunity_type=OpportunityType.BUDGET_REDUCTION,
            source_signal=signal,
            source_signal_id=signal.signal_id,
            entity_id=signal.entity_id,
            entity_type=signal.entity_type,
            priority=self._map_priority(signal),
            confidence=signal.confidence,
            expected_gain=self._gains[OpportunityType.BUDGET_REDUCTION],
            expected_gain_pct=self._gains[OpportunityType.BUDGET_REDUCTION] * 100,
            actions=[
                "reduce_spend",
                "pause_underperforming_campaigns",
                "adjust_bid_cap",
            ],
            recommended_params={
                "current_roas": current_roas,
                "predicted_roas": predicted_roas,
                "decay_pct": decay_pct,
                "reduction_pct": min(0.5, decay_pct * 0.8),
            },
            evidence={
                "current_d7_roas": current_roas,
                "predicted_roas": predicted_roas,
                "roas_decay_pct": decay_pct,
            },
            risk="low",
            business_value=0.9,
            explanation=(
                f"ROAS drop detected for {signal.entity_id}: "
                f"D7={current_roas:.2f} vs predicted={predicted_roas:.2f} "
                f"(-{decay_pct*100:.0f}%). "
                f"Reduce spend and adjust bids to protect margin."
            ),
        )
        opportunities.append(reduction_opp)

        # Opportunity 2: UA Rebalance
        rebalance_opp = GrowthOpportunity(
            opportunity_type=OpportunityType.UA_REBALANCE,
            source_signal=signal,
            source_signal_id=signal.signal_id,
            entity_id=signal.entity_id,
            entity_type=signal.entity_type,
            priority=OpportunityPriority.MEDIUM,
            confidence=signal.confidence * 0.7,
            expected_gain=self._gains[OpportunityType.UA_REBALANCE],
            expected_gain_pct=self._gains[OpportunityType.UA_REBALANCE] * 100,
            actions=[
                "rebalance_to_stable_segments",
                "optimize_targeting",
                "adjust_creative_mix",
            ],
            recommended_params={
                "rebalance_target": "stability",
                "target_roas": predicted_roas * 0.9,
            },
            evidence={
                "current_roas": current_roas,
                "predicted_roas": predicted_roas,
            },
            risk="medium",
            business_value=0.6,
            explanation=(
                f"Rebalance UA portfolio for {signal.entity_id}: "
                f"shift to stable segments while ROAS recovers."
            ),
        )
        opportunities.append(rebalance_opp)

        return opportunities

    # ═══════════════════════════════════════════════════════════
    # Monetization Issue → Optimize
    # ═══════════════════════════════════════════════════════════

    def _map_monetization_issue(self, signal: GrowthSignal) -> list[GrowthOpportunity]:
        iap_conv = signal.metrics.get("iap_conversion", 0)
        ad_arpdau = signal.metrics.get("ad_arpdau", 0)

        actions: list[str] = []
        if iap_conv > 0 and iap_conv < 0.01:
            actions.extend([
                "analyze_payer_funnel",
                "optimize_shop_experience",
                "adjust_pricing_tiers",
                "add_limited_time_offers",
            ])
        if ad_arpdau > 0 and ad_arpdau < 0.01:
            actions.extend([
                "optimize_ad_placement",
                "adjust_ad_frequency",
                "test_ad_networks",
                "improve_ad_fill_rate",
            ])

        if not actions:
            actions = ["analyze_monetization_funnel", "identify_revenue_leaks"]

        optimize_opp = GrowthOpportunity(
            opportunity_type=OpportunityType.MONETIZATION_OPTIMIZE,
            source_signal=signal,
            source_signal_id=signal.signal_id,
            entity_id=signal.entity_id,
            entity_type=signal.entity_type,
            priority=self._map_priority(signal),
            confidence=signal.confidence,
            expected_gain=self._gains[OpportunityType.MONETIZATION_OPTIMIZE],
            expected_gain_pct=self._gains[OpportunityType.MONETIZATION_OPTIMIZE] * 100,
            actions=actions,
            recommended_params={
                "iap_conversion": iap_conv,
                "ad_arpdau": ad_arpdau,
                "optimization_target": "iap" if iap_conv > 0 else "iaa",
            },
            evidence={
                "iap_conversion": iap_conv,
                "ad_arpdau": ad_arpdau,
                "ecpm": signal.metrics.get("ecpm", 0),
                "fill_rate": signal.metrics.get("fill_rate", 0),
            },
            risk="medium",
            business_value=0.7,
            explanation=(
                f"Monetization issue for {signal.entity_id}: "
                f"IAP conversion={iap_conv:.4f}, ARPDAU=${ad_arpdau:.4f}. "
                f"Optimize {', '.join(actions[:3])}."
            ),
        )
        return [optimize_opp]

    # ═══════════════════════════════════════════════════════════
    # Helpers
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def _map_priority(signal: GrowthSignal) -> OpportunityPriority:
        """将信号严重度映射为机会优先级."""
        from ..models import SignalSeverity

        priority_map = {
            SignalSeverity.CRITICAL: OpportunityPriority.CRITICAL,
            SignalSeverity.HIGH: OpportunityPriority.HIGH,
            SignalSeverity.MEDIUM: OpportunityPriority.MEDIUM,
            SignalSeverity.LOW: OpportunityPriority.LOW,
        }
        return priority_map.get(signal.severity, OpportunityPriority.MEDIUM)