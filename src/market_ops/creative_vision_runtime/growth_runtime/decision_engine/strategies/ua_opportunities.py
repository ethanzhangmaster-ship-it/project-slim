"""E13.3.2 UA Opportunity Mapper — UA 信号 → UA 机会映射.

规则:
  - SCALE_OPPORTUNITY → UA_SCALE
  - BUDGET_WASTE → BUDGET_REDUCTION + UA_REBALANCE
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
    OpportunityType.UA_SCALE: 0.40,           # 预期提升 40%
    OpportunityType.UA_REBALANCE: 0.15,        # 预期提升 15%
    OpportunityType.BUDGET_REDUCTION: 0.20,    # 预期节省 20%
}


class UAOpportunityMapper:
    """UA 机会映射器.

    将 UA 类信号 (Scale / Waste) 转换为可执行的 UA 机会.
    """

    def __init__(self, gains: dict[OpportunityType, float] | None = None):
        self._gains = {**DEFAULT_GAINS, **(gains or {})}

    def map(self, signal: GrowthSignal) -> list[GrowthOpportunity]:
        """将一个信号映射为多个机会.

        Args:
            signal: UA 类 GrowthSignal

        Returns:
            list[GrowthOpportunity]: 对应的增长机会列表
        """
        if signal.signal_type == SignalType.SCALE_OPPORTUNITY:
            return self._map_scale(signal)
        elif signal.signal_type == SignalType.BUDGET_WASTE:
            return self._map_waste(signal)
        return []

    # ═══════════════════════════════════════════════════════════
    # Scale Opportunity → UA Scale
    # ═══════════════════════════════════════════════════════════

    def _map_scale(self, signal: GrowthSignal) -> list[GrowthOpportunity]:
        current_spend = signal.metrics.get("spend", 500)
        roas = signal.metrics.get("d30_roas", 0)

        # 推荐预算: 基于 ROAS 表现推荐放大倍数
        if roas > 2.0:
            spend_multiplier = 6.0
        elif roas > 1.5:
            spend_multiplier = 4.0
        else:
            spend_multiplier = 2.5

        recommended_budget = current_spend * spend_multiplier

        scale_opp = GrowthOpportunity(
            opportunity_type=OpportunityType.UA_SCALE,
            source_signal=signal,
            source_signal_id=signal.signal_id,
            entity_id=signal.entity_id,
            entity_type=signal.entity_type,
            priority=self._map_priority(signal),
            confidence=signal.confidence,
            expected_gain=self._gains[OpportunityType.UA_SCALE],
            expected_gain_pct=self._gains[OpportunityType.UA_SCALE] * 100,
            actions=[
                "increase_budget",
                "duplicate_campaign",
                "expand_targeting",
                "scale_geographic",
            ],
            recommended_params={
                "current_budget": current_spend,
                "recommended_budget": recommended_budget,
                "spend_multiplier": spend_multiplier,
                "scale_strategy": "aggressive" if roas > 2.0 else "moderate",
            },
            evidence={
                "d30_roas": roas,
                "current_spend": current_spend,
                "fitness_score": signal.metrics.get("fitness_score", 0),
            },
            risk="low" if roas > 2.0 else "medium",
            business_value=1.0,
            explanation=(
                f"Scale opportunity for {signal.entity_id}: "
                f"ROAS={roas:.2f}, current spend=${current_spend:.0f}. "
                f"Recommend scaling to ${recommended_budget:.0f}/day "
                f"({spend_multiplier:.0f}x)."
            ),
        )
        return [scale_opp]

    # ═══════════════════════════════════════════════════════════
    # Budget Waste → Reduction + Rebalance
    # ═══════════════════════════════════════════════════════════

    def _map_waste(self, signal: GrowthSignal) -> list[GrowthOpportunity]:
        opportunities: list[GrowthOpportunity] = []

        spend = signal.metrics.get("spend", 500)
        roas = signal.metrics.get("d7_roas", 0)
        revenue = signal.metrics.get("total_revenue", 0)

        # 推荐削减预算
        reduction_pct = min(0.8, max(0.3, (1.0 - roas) / 2.0))
        recommended_budget = spend * (1 - reduction_pct)

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
                "pause_low_performing_ads",
                "reallocate_budget_to_winners",
            ],
            recommended_params={
                "current_budget": spend,
                "recommended_budget": recommended_budget,
                "reduction_pct": reduction_pct,
                "waste_amount": spend - revenue,
            },
            evidence={
                "d7_roas": roas,
                "spend": spend,
                "total_revenue": revenue,
            },
            risk="low",
            business_value=0.9,
            explanation=(
                f"Budget waste detected for {signal.entity_id}: "
                f"ROAS={roas:.2f}, Spend=${spend:.0f}, Revenue=${revenue:.0f}. "
                f"Reduce budget by {reduction_pct*100:.0f}% to ${recommended_budget:.0f}."
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
                "rebalance_campaign_budget",
                "shift_to_high_performing_segments",
                "optimize_bid_strategy",
            ],
            recommended_params={
                "rebalance_target": "roas_target",
                "target_roas": 1.2,
                "shift_pct": 0.5,
            },
            evidence={
                "d7_roas": roas,
                "spend": spend,
            },
            risk="low",
            business_value=0.6,
            explanation=(
                f"Rebalance UA spend for {signal.entity_id}: "
                f"shift budget from low-ROAS to high-ROAS segments."
            ),
        )
        opportunities.append(rebalance_opp)

        return opportunities

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