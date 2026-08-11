"""E13.3.2 Creative Opportunity Mapper — 创意信号 → 创意机会映射.

规则:
  - CREATIVE_WINNER → CREATIVE_SCALE + CREATIVE_MUTATION
  - CREATIVE_FATIGUE → CREATIVE_REFRESH + CREATIVE_MUTATION
  - CREATIVE_UNDERPERFORM → CREATIVE_REFRESH
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
    OpportunityType.CREATIVE_SCALE: 0.35,       # 预期提升 35%
    OpportunityType.CREATIVE_REFRESH: 0.18,      # 预期提升 18%
    OpportunityType.CREATIVE_MUTATION: 0.25,     # 预期提升 25%
}


class CreativeOpportunityMapper:
    """创意机会映射器.

    将创意类信号 (Winner / Fatigue / Underperform) 转换为可执行的创意机会.
    """

    def __init__(self, gains: dict[OpportunityType, float] | None = None):
        self._gains = {**DEFAULT_GAINS, **(gains or {})}

    def map(self, signal: GrowthSignal) -> list[GrowthOpportunity]:
        """将一个信号映射为多个机会.

        Args:
            signal: 创意类 GrowthSignal

        Returns:
            list[GrowthOpportunity]: 对应的增长机会列表
        """
        if signal.signal_type == SignalType.CREATIVE_WINNER:
            return self._map_winner(signal)
        elif signal.signal_type == SignalType.CREATIVE_FATIGUE:
            return self._map_fatigue(signal)
        elif signal.signal_type == SignalType.CREATIVE_UNDERPERFORM:
            return self._map_underperform(signal)
        return []

    # ═══════════════════════════════════════════════════════════
    # Winner → Scale + Mutation
    # ═══════════════════════════════════════════════════════════

    def _map_winner(self, signal: GrowthSignal) -> list[GrowthOpportunity]:
        opportunities: list[GrowthOpportunity] = []

        # Opportunity 1: Creative Scale
        scale_opp = GrowthOpportunity(
            opportunity_type=OpportunityType.CREATIVE_SCALE,
            source_signal=signal,
            source_signal_id=signal.signal_id,
            entity_id=signal.entity_id,
            entity_type=signal.entity_type,
            priority=self._map_priority(signal),
            confidence=signal.confidence,
            expected_gain=self._gains[OpportunityType.CREATIVE_SCALE],
            expected_gain_pct=self._gains[OpportunityType.CREATIVE_SCALE] * 100,
            actions=[
                "clone_creative_dna",
                "generate_variants",
                "launch_ab_test",
                "scale_winning_creative",
            ],
            recommended_params={
                "mutation_count": 5,
                "test_budget": signal.metrics.get("spend", 500) * 1.5,
                "scale_factor": 1.5,
            },
            evidence={
                "d30_roas": signal.metrics.get("d30_roas", 0),
                "d30_ltv": signal.metrics.get("d30_ltv", 0),
                "fitness_score": signal.metrics.get("fitness_score", 0),
            },
            risk="low",
            business_value=1.0,
            explanation=(
                f"Winner creative {signal.entity_id}: ROS={signal.metrics.get('d30_roas', 0):.2f}, "
                f"LTV=${signal.metrics.get('d30_ltv', 0):.2f}. "
                f"Scale by cloning DNA and generating variants."
            ),
        )
        opportunities.append(scale_opp)

        # Opportunity 2: Creative Mutation
        mutation_opp = GrowthOpportunity(
            opportunity_type=OpportunityType.CREATIVE_MUTATION,
            source_signal=signal,
            source_signal_id=signal.signal_id,
            entity_id=signal.entity_id,
            entity_type=signal.entity_type,
            priority=OpportunityPriority.MEDIUM,
            confidence=signal.confidence * 0.85,
            expected_gain=self._gains[OpportunityType.CREATIVE_MUTATION],
            expected_gain_pct=self._gains[OpportunityType.CREATIVE_MUTATION] * 100,
            actions=[
                "extract_winning_dna",
                "mutate_hook_variants",
                "preserve_psychological_mechanism",
                "create_mutation_population",
            ],
            recommended_params={
                "mutation_rate": 0.15,
                "population_size": 8,
                "preserve_core_dna": True,
            },
            evidence={
                "winning_roas": signal.metrics.get("d30_roas", 0),
                "fitness_score": signal.metrics.get("fitness_score", 0),
            },
            risk="low",
            business_value=0.8,
            explanation=(
                f"Evolve winner {signal.entity_id}: extract DNA, "
                f"mutate hooks while preserving winning psychological mechanisms."
            ),
        )
        opportunities.append(mutation_opp)

        return opportunities

    # ═══════════════════════════════════════════════════════════
    # Fatigue → Refresh + Mutation
    # ═══════════════════════════════════════════════════════════

    def _map_fatigue(self, signal: GrowthSignal) -> list[GrowthOpportunity]:
        opportunities: list[GrowthOpportunity] = []

        # Opportunity 1: Creative Refresh
        refresh_opp = GrowthOpportunity(
            opportunity_type=OpportunityType.CREATIVE_REFRESH,
            source_signal=signal,
            source_signal_id=signal.signal_id,
            entity_id=signal.entity_id,
            entity_type=signal.entity_type,
            priority=self._map_priority(signal),
            confidence=signal.confidence,
            expected_gain=self._gains[OpportunityType.CREATIVE_REFRESH],
            expected_gain_pct=self._gains[OpportunityType.CREATIVE_REFRESH] * 100,
            actions=[
                "extract_current_dna",
                "mutate_hook_contrast",
                "mutate_visual_style",
                "generate_new_population",
                "replace_fatigued_creative",
            ],
            recommended_params={
                "hook_contrast_delta": 0.20,
                "visual_density_delta": 0.10,
                "reward_speed_delta": 0.15,
                "population_size": 6,
            },
            evidence={
                "fatigue_score": signal.metrics.get("fatigue_score", 0),
                "ctr": signal.metrics.get("ctr", 0),
                "d7_roas": signal.metrics.get("d7_roas", 0),
                "frequency": signal.metrics.get("frequency", 0),
            },
            risk="medium",
            business_value=0.9,
            explanation=(
                f"Creative {signal.entity_id} fatigued (score={signal.metrics.get('fatigue_score', 0):.2f}). "
                f"Refresh by mutating hook contrast, visual style, and reward speed. "
                f"Generate new population to replace fatigued creative."
            ),
        )
        opportunities.append(refresh_opp)

        # Opportunity 2: Creative Mutation
        mutation_opp = GrowthOpportunity(
            opportunity_type=OpportunityType.CREATIVE_MUTATION,
            source_signal=signal,
            source_signal_id=signal.signal_id,
            entity_id=signal.entity_id,
            entity_type=signal.entity_type,
            priority=OpportunityPriority.MEDIUM,
            confidence=signal.confidence * 0.8,
            expected_gain=self._gains[OpportunityType.CREATIVE_MUTATION],
            expected_gain_pct=self._gains[OpportunityType.CREATIVE_MUTATION] * 100,
            actions=[
                "extract_fatigued_dna",
                "mutate_hook",
                "mutate_visual_style",
                "generate_mutation_population",
            ],
            recommended_params={
                "mutation_rate": 0.25,
                "population_size": 5,
                "hook_mutation_weight": 0.6,
                "visual_mutation_weight": 0.4,
            },
            evidence={
                "fatigue_score": signal.metrics.get("fatigue_score", 0),
                "ctr": signal.metrics.get("ctr", 0),
            },
            risk="medium",
            business_value=0.7,
            explanation=(
                f"Deep mutation of fatigued creative {signal.entity_id} "
                f"with higher mutation rate to explore new variations."
            ),
        )
        opportunities.append(mutation_opp)

        return opportunities

    # ═══════════════════════════════════════════════════════════
    # Underperform → Refresh
    # ═══════════════════════════════════════════════════════════

    def _map_underperform(self, signal: GrowthSignal) -> list[GrowthOpportunity]:
        refresh_opp = GrowthOpportunity(
            opportunity_type=OpportunityType.CREATIVE_REFRESH,
            source_signal=signal,
            source_signal_id=signal.signal_id,
            entity_id=signal.entity_id,
            entity_type=signal.entity_type,
            priority=self._map_priority(signal),
            confidence=signal.confidence,
            expected_gain=self._gains[OpportunityType.CREATIVE_REFRESH] * 0.7,
            expected_gain_pct=self._gains[OpportunityType.CREATIVE_REFRESH] * 70,
            actions=[
                "analyze_underperform_reasons",
                "extract_current_dna",
                "redesign_hook",
                "replace_underperforming_creative",
            ],
            recommended_params={
                "redesign_scope": "full",
                "hook_redesign": True,
                "visual_redesign": True,
            },
            evidence={
                "d7_roas": signal.metrics.get("d7_roas", 0),
                "ctr": signal.metrics.get("ctr", 0),
                "spend": signal.metrics.get("spend", 0),
            },
            risk="medium",
            business_value=0.6,
            explanation=(
                f"Creative {signal.entity_id} underperforming: "
                f"ROAS={signal.metrics.get('d7_roas', 0):.2f}, "
                f"CTR={signal.metrics.get('ctr', 0):.4f}. "
                f"Full redesign recommended."
            ),
        )
        return [refresh_opp]

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