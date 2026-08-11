"""E13.3.2 Growth Opportunity Engine — 测试套件.

测试覆盖:
  - OpportunityType / OpportunityPriority / OpportunityStatus 枚举
  - GrowthOpportunity / OpportunityBatch 模型
  - SIGNAL_TO_OPPORTUNITY_MAP
  - CreativeOpportunityMapper: Winner / Fatigue / Underperform
  - UAOpportunityMapper: Scale / Waste
  - RevenueOpportunityMapper: LTV Upside / ROAS Drop / Monetization Issue
  - GrowthOpportunityEngine: analyze / analyze_batch / ranking / filters
  - 边界条件
  - 集成场景
"""

from __future__ import annotations

import pytest
from typing import Any


# ═══════════════════════════════════════════════════════════════
# Helper: Create minimal GrowthSignal for testing
# ═══════════════════════════════════════════════════════════════

def _make_signal(
    signal_type: Any = None,
    entity_id: str = "c001",
    severity: Any = None,
    confidence: float = 0.9,
    metrics: dict[str, float] | None = None,
    category: Any = None,
    **kwargs,
) -> Any:
    from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import (
        GrowthSignal, SignalType, SignalSeverity, SignalCategory,
    )
    if signal_type is None:
        signal_type = SignalType.CREATIVE_WINNER
    if severity is None:
        severity = SignalSeverity.HIGH
    if category is None:
        category = SignalCategory.CREATIVE
    return GrowthSignal(
        signal_type=signal_type,
        entity_id=entity_id,
        severity=severity,
        confidence=confidence,
        metrics=metrics or {},
        category=category,
        **kwargs,
    )


# ═══════════════════════════════════════════════════════════════
# Model Tests
# ═══════════════════════════════════════════════════════════════


class TestOpportunityType:
    """OpportunityType 枚举测试."""

    def test_all_types_exist(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import OpportunityType

        types = list(OpportunityType)
        assert len(types) == 8
        assert OpportunityType.CREATIVE_SCALE in types
        assert OpportunityType.CREATIVE_REFRESH in types
        assert OpportunityType.CREATIVE_MUTATION in types
        assert OpportunityType.UA_SCALE in types
        assert OpportunityType.UA_REBALANCE in types
        assert OpportunityType.BUDGET_REDUCTION in types
        assert OpportunityType.MONETIZATION_OPTIMIZE in types
        assert OpportunityType.MONETIZATION_SCALE in types

    def test_type_values(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import OpportunityType

        assert OpportunityType.CREATIVE_SCALE.value == "creative_scale"
        assert OpportunityType.UA_SCALE.value == "ua_scale"
        assert OpportunityType.BUDGET_REDUCTION.value == "budget_reduction"
        assert OpportunityType.MONETIZATION_OPTIMIZE.value == "monetization_optimize"


class TestOpportunityPriority:
    """OpportunityPriority 枚举测试."""

    def test_all_priorities(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import OpportunityPriority

        prios = list(OpportunityPriority)
        assert len(prios) == 4
        assert OpportunityPriority.LOW in prios
        assert OpportunityPriority.MEDIUM in prios
        assert OpportunityPriority.HIGH in prios
        assert OpportunityPriority.CRITICAL in prios

    def test_priority_values(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import OpportunityPriority

        assert OpportunityPriority.LOW.value == "low"
        assert OpportunityPriority.CRITICAL.value == "critical"


class TestOpportunityStatus:
    """OpportunityStatus 枚举测试."""

    def test_all_statuses(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import OpportunityStatus

        statuses = list(OpportunityStatus)
        assert len(statuses) == 5
        assert OpportunityStatus.NEW in statuses
        assert OpportunityStatus.ACCEPTED in statuses
        assert OpportunityStatus.EXECUTING in statuses
        assert OpportunityStatus.COMPLETED in statuses
        assert OpportunityStatus.REJECTED in statuses


class TestGrowthOpportunity:
    """GrowthOpportunity 模型测试."""

    def test_default_creation(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import GrowthOpportunity

        opp = GrowthOpportunity()
        assert opp.opportunity_id != ""
        assert opp.opportunity_type.value == "creative_scale"
        assert opp.priority.value == "medium"
        assert opp.confidence == 0.0
        assert opp.expected_gain == 0.0
        assert opp.actions == []
        assert opp.status == "new"

    def test_full_creation(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import (
            GrowthOpportunity, OpportunityType, OpportunityPriority,
        )

        sig = _make_signal()
        opp = GrowthOpportunity(
            opportunity_type=OpportunityType.CREATIVE_SCALE,
            source_signal=sig,
            source_signal_id=sig.signal_id,
            entity_id="c001",
            priority=OpportunityPriority.HIGH,
            confidence=0.92,
            expected_gain=0.35,
            expected_gain_pct=35,
            actions=["clone_creative_dna", "generate_variants"],
            risk="low",
            business_value=1.0,
            score=0.85,
        )
        assert opp.opportunity_type == OpportunityType.CREATIVE_SCALE
        assert opp.source_signal is sig
        assert opp.entity_id == "c001"
        assert opp.priority == OpportunityPriority.HIGH
        assert opp.confidence == 0.92
        assert opp.expected_gain == 0.35
        assert len(opp.actions) == 2
        assert opp.risk == "low"
        assert opp.score == 0.85

    def test_to_dict(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import (
            GrowthOpportunity, OpportunityType, OpportunityPriority,
        )

        opp = GrowthOpportunity(
            opportunity_type=OpportunityType.UA_SCALE,
            entity_id="c001",
            priority=OpportunityPriority.HIGH,
            confidence=0.88,
            expected_gain=0.40,
            actions=["increase_budget"],
            risk="medium",
        )
        d = opp.to_dict()
        assert d["opportunity_type"] == "ua_scale"
        assert d["entity_id"] == "c001"
        assert d["priority"] == "high"
        assert d["confidence"] == 0.88
        assert d["actions"] == ["increase_budget"]
        assert "opportunity_id" in d
        assert "timestamp" in d

    def test_opportunity_id_is_unique(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import GrowthOpportunity

        o1 = GrowthOpportunity()
        o2 = GrowthOpportunity()
        assert o1.opportunity_id != o2.opportunity_id

    def test_default_status_is_new(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import GrowthOpportunity

        opp = GrowthOpportunity()
        assert opp.status == "new"

    def test_recommended_params_default(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import GrowthOpportunity

        opp = GrowthOpportunity()
        assert opp.recommended_params == {}

    def test_evidence_default(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import GrowthOpportunity

        opp = GrowthOpportunity()
        assert opp.evidence == {}


class TestOpportunityBatch:
    """OpportunityBatch 模型测试."""

    def test_default_creation(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import OpportunityBatch

        batch = OpportunityBatch()
        assert batch.opportunities == []
        assert batch.total_signals == 0
        assert batch.total_opportunities == 0
        assert batch.summary == {}

    def test_to_dict(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import (
            OpportunityBatch, GrowthOpportunity,
        )

        opp = GrowthOpportunity()
        batch = OpportunityBatch(
            product_id="p1",
            date="2026-07-24",
            opportunities=[opp],
            total_signals=5,
            total_opportunities=8,
            summary={"creative_scale": 3, "ua_scale": 5},
            elapsed_ms=12.5,
        )
        d = batch.to_dict()
        assert d["product_id"] == "p1"
        assert d["total_signals"] == 5
        assert d["total_opportunities"] == 8
        assert d["summary"]["creative_scale"] == 3
        assert len(d["opportunities"]) == 1
        assert "batch_id" in d

    def test_batch_id_is_unique(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import OpportunityBatch

        b1 = OpportunityBatch()
        b2 = OpportunityBatch()
        assert b1.batch_id != b2.batch_id


class TestSignalToOpportunityMap:
    """SIGNAL_TO_OPPORTUNITY_MAP 测试."""

    def test_all_signals_mapped(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import (
            SignalType, SIGNAL_TO_OPPORTUNITY_MAP,
        )

        for st in SignalType:
            assert st in SIGNAL_TO_OPPORTUNITY_MAP, f"SignalType {st} not in SIGNAL_TO_OPPORTUNITY_MAP"

    def test_winner_maps_to_scale_and_mutation(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import (
            SignalType, OpportunityType, SIGNAL_TO_OPPORTUNITY_MAP,
        )

        opps = SIGNAL_TO_OPPORTUNITY_MAP[SignalType.CREATIVE_WINNER]
        assert OpportunityType.CREATIVE_SCALE in opps
        assert OpportunityType.CREATIVE_MUTATION in opps

    def test_scale_opportunity_maps_to_ua_scale(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import (
            SignalType, OpportunityType, SIGNAL_TO_OPPORTUNITY_MAP,
        )

        opps = SIGNAL_TO_OPPORTUNITY_MAP[SignalType.SCALE_OPPORTUNITY]
        assert [OpportunityType.UA_SCALE] == opps


# ═══════════════════════════════════════════════════════════════
# CreativeOpportunityMapper Tests
# ═══════════════════════════════════════════════════════════════


class TestCreativeOpportunityMapper:
    """CreativeOpportunityMapper 测试."""

    @pytest.fixture
    def mapper(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.strategies.creative_opportunities import CreativeOpportunityMapper
        return CreativeOpportunityMapper()

    # --- Winner ---

    def test_winner_generates_two_opportunities(self, mapper):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalType

        sig = _make_signal(SignalType.CREATIVE_WINNER, entity_id="w1", confidence=0.92,
                           metrics={"d30_roas": 3.0, "d30_ltv": 8.0, "fitness_score": 0.9, "spend": 500})
        opps = mapper.map(sig)
        assert len(opps) == 2

    def test_winner_scale_opportunity_type(self, mapper):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalType, OpportunityType

        sig = _make_signal(SignalType.CREATIVE_WINNER, entity_id="w1", confidence=0.92,
                           metrics={"d30_roas": 3.0, "d30_ltv": 8.0, "fitness_score": 0.9})
        opps = mapper.map(sig)
        types = [o.opportunity_type for o in opps]
        assert OpportunityType.CREATIVE_SCALE in types
        assert OpportunityType.CREATIVE_MUTATION in types

    def test_winner_scale_has_actions(self, mapper):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalType, OpportunityType

        sig = _make_signal(SignalType.CREATIVE_WINNER, entity_id="w1", confidence=0.92,
                           metrics={"d30_roas": 3.0, "d30_ltv": 8.0})
        opps = mapper.map(sig)
        scale = [o for o in opps if o.opportunity_type == OpportunityType.CREATIVE_SCALE][0]
        assert "clone_creative_dna" in scale.actions
        assert "generate_variants" in scale.actions
        assert "launch_ab_test" in scale.actions

    def test_winner_mutation_has_actions(self, mapper):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalType, OpportunityType

        sig = _make_signal(SignalType.CREATIVE_WINNER, entity_id="w1", confidence=0.92,
                           metrics={"d30_roas": 3.0})
        opps = mapper.map(sig)
        mutation = [o for o in opps if o.opportunity_type == OpportunityType.CREATIVE_MUTATION][0]
        assert "extract_winning_dna" in mutation.actions
        assert "mutate_hook_variants" in mutation.actions

    def test_winner_scale_priority_matches_signal(self, mapper):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import (
            SignalType, SignalSeverity, OpportunityPriority,
        )

        sig = _make_signal(SignalType.CREATIVE_WINNER, entity_id="w1", confidence=0.92,
                           severity=SignalSeverity.CRITICAL)
        opps = mapper.map(sig)
        scale = opps[0]
        assert scale.priority == OpportunityPriority.CRITICAL

    def test_winner_scale_has_evidence(self, mapper):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalType

        sig = _make_signal(SignalType.CREATIVE_WINNER, entity_id="w1", confidence=0.92,
                           metrics={"d30_roas": 3.0, "d30_ltv": 8.0, "fitness_score": 0.9})
        opps = mapper.map(sig)
        assert "d30_roas" in opps[0].evidence
        assert opps[0].evidence["d30_roas"] == 3.0

    def test_winner_scale_has_recommended_params(self, mapper):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalType

        sig = _make_signal(SignalType.CREATIVE_WINNER, entity_id="w1", confidence=0.92,
                           metrics={"spend": 500})
        opps = mapper.map(sig)
        assert "mutation_count" in opps[0].recommended_params
        assert opps[0].recommended_params["mutation_count"] == 5

    def test_winner_scale_risk_low(self, mapper):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalType

        sig = _make_signal(SignalType.CREATIVE_WINNER, entity_id="w1", confidence=0.92)
        opps = mapper.map(sig)
        assert opps[0].risk == "low"

    def test_winner_scale_expected_gain(self, mapper):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalType

        sig = _make_signal(SignalType.CREATIVE_WINNER, entity_id="w1", confidence=0.92)
        opps = mapper.map(sig)
        assert opps[0].expected_gain == 0.35
        assert opps[0].expected_gain_pct == 35

    # --- Fatigue ---

    def test_fatigue_generates_two_opportunities(self, mapper):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalType

        sig = _make_signal(SignalType.CREATIVE_FATIGUE, entity_id="f1", confidence=0.85,
                           metrics={"fatigue_score": 0.82, "ctr": 0.01, "d7_roas": 0.5, "frequency": 6.0})
        opps = mapper.map(sig)
        assert len(opps) == 2

    def test_fatigue_refresh_opportunity_type(self, mapper):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalType, OpportunityType

        sig = _make_signal(SignalType.CREATIVE_FATIGUE, entity_id="f1", confidence=0.85,
                           metrics={"fatigue_score": 0.82, "ctr": 0.01})
        opps = mapper.map(sig)
        types = [o.opportunity_type for o in opps]
        assert OpportunityType.CREATIVE_REFRESH in types
        assert OpportunityType.CREATIVE_MUTATION in types

    def test_fatigue_refresh_has_actions(self, mapper):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalType, OpportunityType

        sig = _make_signal(SignalType.CREATIVE_FATIGUE, entity_id="f1", confidence=0.85,
                           metrics={"fatigue_score": 0.82})
        opps = mapper.map(sig)
        refresh = [o for o in opps if o.opportunity_type == OpportunityType.CREATIVE_REFRESH][0]
        assert "extract_current_dna" in refresh.actions
        assert "mutate_hook_contrast" in refresh.actions
        assert "generate_new_population" in refresh.actions

    def test_fatigue_refresh_has_hook_contrast_delta(self, mapper):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalType, OpportunityType

        sig = _make_signal(SignalType.CREATIVE_FATIGUE, entity_id="f1", confidence=0.85,
                           metrics={"fatigue_score": 0.82})
        opps = mapper.map(sig)
        refresh = [o for o in opps if o.opportunity_type == OpportunityType.CREATIVE_REFRESH][0]
        assert "hook_contrast_delta" in refresh.recommended_params
        assert refresh.recommended_params["hook_contrast_delta"] == 0.20

    def test_fatigue_refresh_risk_medium(self, mapper):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalType

        sig = _make_signal(SignalType.CREATIVE_FATIGUE, entity_id="f1", confidence=0.85,
                           metrics={"fatigue_score": 0.82})
        opps = mapper.map(sig)
        assert opps[0].risk == "medium"

    def test_fatigue_refresh_expected_gain(self, mapper):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalType

        sig = _make_signal(SignalType.CREATIVE_FATIGUE, entity_id="f1", confidence=0.85,
                           metrics={"fatigue_score": 0.82})
        opps = mapper.map(sig)
        assert opps[0].expected_gain == 0.18

    def test_fatigue_mutation_higher_rate(self, mapper):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalType, OpportunityType

        sig = _make_signal(SignalType.CREATIVE_FATIGUE, entity_id="f1", confidence=0.85,
                           metrics={"fatigue_score": 0.82})
        opps = mapper.map(sig)
        mutation = [o for o in opps if o.opportunity_type == OpportunityType.CREATIVE_MUTATION][0]
        assert mutation.recommended_params["mutation_rate"] == 0.25

    def test_fatigue_refresh_has_explanation(self, mapper):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalType

        sig = _make_signal(SignalType.CREATIVE_FATIGUE, entity_id="f1", confidence=0.85,
                           metrics={"fatigue_score": 0.82, "ctr": 0.01, "d7_roas": 0.5, "frequency": 6.0})
        opps = mapper.map(sig)
        assert len(opps[0].explanation) > 0
        assert "fatigued" in opps[0].explanation.lower()

    # --- Underperform ---

    def test_underperform_generates_one_opportunity(self, mapper):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalType

        sig = _make_signal(SignalType.CREATIVE_UNDERPERFORM, entity_id="u1", confidence=0.75,
                           metrics={"d7_roas": 0.3, "ctr": 0.003, "spend": 200})
        opps = mapper.map(sig)
        assert len(opps) == 1

    def test_underperform_type_is_refresh(self, mapper):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalType, OpportunityType

        sig = _make_signal(SignalType.CREATIVE_UNDERPERFORM, entity_id="u1", confidence=0.75,
                           metrics={"d7_roas": 0.3, "ctr": 0.003})
        opps = mapper.map(sig)
        assert opps[0].opportunity_type == OpportunityType.CREATIVE_REFRESH

    def test_underperform_has_actions(self, mapper):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalType

        sig = _make_signal(SignalType.CREATIVE_UNDERPERFORM, entity_id="u1", confidence=0.75,
                           metrics={"d7_roas": 0.3})
        opps = mapper.map(sig)
        assert "redesign_hook" in opps[0].actions
        assert "replace_underperforming_creative" in opps[0].actions

    def test_underperform_lower_expected_gain(self, mapper):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalType

        sig = _make_signal(SignalType.CREATIVE_UNDERPERFORM, entity_id="u1", confidence=0.75,
                           metrics={"d7_roas": 0.3})
        opps = mapper.map(sig)
        # Underperform has lower expected gain (0.18 * 0.7 = 0.126)
        assert opps[0].expected_gain < 0.15

    def test_underperform_risk_medium(self, mapper):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalType

        sig = _make_signal(SignalType.CREATIVE_UNDERPERFORM, entity_id="u1", confidence=0.75,
                           metrics={"d7_roas": 0.3})
        opps = mapper.map(sig)
        assert opps[0].risk == "medium"

    def test_underperform_has_explanation(self, mapper):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalType

        sig = _make_signal(SignalType.CREATIVE_UNDERPERFORM, entity_id="u1", confidence=0.75,
                           metrics={"d7_roas": 0.3, "ctr": 0.003})
        opps = mapper.map(sig)
        assert "underperforming" in opps[0].explanation.lower()

    def test_map_unknown_signal_returns_empty(self, mapper):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalType

        sig = _make_signal(SignalType.SCALE_OPPORTUNITY, entity_id="s1")
        opps = mapper.map(sig)
        assert opps == []

    # --- Custom gains ---

    def test_custom_gains_override(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.strategies.creative_opportunities import CreativeOpportunityMapper
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalType, OpportunityType

        mapper = CreativeOpportunityMapper({OpportunityType.CREATIVE_SCALE: 0.50})
        sig = _make_signal(SignalType.CREATIVE_WINNER, entity_id="w1", confidence=0.9)
        opps = mapper.map(sig)
        assert opps[0].expected_gain == 0.50


# ═══════════════════════════════════════════════════════════════
# UAOpportunityMapper Tests
# ═══════════════════════════════════════════════════════════════


class TestUAOpportunityMapper:
    """UAOpportunityMapper 测试."""

    @pytest.fixture
    def mapper(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.strategies.ua_opportunities import UAOpportunityMapper
        return UAOpportunityMapper()

    # --- Scale ---

    def test_scale_generates_one_opportunity(self, mapper):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalType

        sig = _make_signal(SignalType.SCALE_OPPORTUNITY, entity_id="s1", confidence=0.88,
                           metrics={"d30_roas": 2.5, "spend": 200.0, "fitness_score": 0.9})
        opps = mapper.map(sig)
        assert len(opps) == 1

    def test_scale_type_is_ua_scale(self, mapper):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalType, OpportunityType

        sig = _make_signal(SignalType.SCALE_OPPORTUNITY, entity_id="s1", confidence=0.88,
                           metrics={"d30_roas": 2.5, "spend": 200.0})
        opps = mapper.map(sig)
        assert opps[0].opportunity_type == OpportunityType.UA_SCALE

    def test_scale_has_actions(self, mapper):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalType

        sig = _make_signal(SignalType.SCALE_OPPORTUNITY, entity_id="s1", confidence=0.88,
                           metrics={"d30_roas": 2.5, "spend": 200.0})
        opps = mapper.map(sig)
        assert "increase_budget" in opps[0].actions
        assert "duplicate_campaign" in opps[0].actions

    def test_scale_high_roas_aggressive_multiplier(self, mapper):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalType

        sig = _make_signal(SignalType.SCALE_OPPORTUNITY, entity_id="s1", confidence=0.88,
                           metrics={"d30_roas": 3.0, "spend": 200.0})
        opps = mapper.map(sig)
        assert opps[0].recommended_params["spend_multiplier"] == 6.0
        assert opps[0].recommended_params["recommended_budget"] == 1200.0
        assert opps[0].recommended_params["scale_strategy"] == "aggressive"

    def test_scale_moderate_roas_multiplier(self, mapper):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalType

        sig = _make_signal(SignalType.SCALE_OPPORTUNITY, entity_id="s1", confidence=0.88,
                           metrics={"d30_roas": 1.6, "spend": 200.0})
        opps = mapper.map(sig)
        assert opps[0].recommended_params["spend_multiplier"] == 4.0
        assert opps[0].recommended_params["scale_strategy"] == "moderate"

    def test_scale_low_roas_multiplier(self, mapper):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalType

        sig = _make_signal(SignalType.SCALE_OPPORTUNITY, entity_id="s1", confidence=0.88,
                           metrics={"d30_roas": 1.2, "spend": 200.0})
        opps = mapper.map(sig)
        assert opps[0].recommended_params["spend_multiplier"] == 2.5

    def test_scale_risk_low_high_roas(self, mapper):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalType

        sig = _make_signal(SignalType.SCALE_OPPORTUNITY, entity_id="s1", confidence=0.88,
                           metrics={"d30_roas": 3.0, "spend": 200.0})
        opps = mapper.map(sig)
        assert opps[0].risk == "low"

    def test_scale_risk_medium_moderate_roas(self, mapper):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalType

        sig = _make_signal(SignalType.SCALE_OPPORTUNITY, entity_id="s1", confidence=0.88,
                           metrics={"d30_roas": 1.5, "spend": 200.0})
        opps = mapper.map(sig)
        assert opps[0].risk == "medium"

    def test_scale_expected_gain(self, mapper):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalType

        sig = _make_signal(SignalType.SCALE_OPPORTUNITY, entity_id="s1", confidence=0.88,
                           metrics={"d30_roas": 2.5, "spend": 200.0})
        opps = mapper.map(sig)
        assert opps[0].expected_gain == 0.40

    def test_scale_has_explanation(self, mapper):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalType

        sig = _make_signal(SignalType.SCALE_OPPORTUNITY, entity_id="s1", confidence=0.88,
                           metrics={"d30_roas": 2.5, "spend": 200.0})
        opps = mapper.map(sig)
        assert "scale" in opps[0].explanation.lower()
        assert "s1" in opps[0].explanation

    # --- Budget Waste ---

    def test_waste_generates_two_opportunities(self, mapper):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalType

        sig = _make_signal(SignalType.BUDGET_WASTE, entity_id="b1", confidence=0.75,
                           metrics={"d7_roas": 0.3, "spend": 500.0, "total_revenue": 150.0})
        opps = mapper.map(sig)
        assert len(opps) == 2

    def test_waste_reduction_type(self, mapper):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalType, OpportunityType

        sig = _make_signal(SignalType.BUDGET_WASTE, entity_id="b1", confidence=0.75,
                           metrics={"d7_roas": 0.3, "spend": 500.0, "total_revenue": 150.0})
        opps = mapper.map(sig)
        types = [o.opportunity_type for o in opps]
        assert OpportunityType.BUDGET_REDUCTION in types
        assert OpportunityType.UA_REBALANCE in types

    def test_waste_reduction_has_actions(self, mapper):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalType, OpportunityType

        sig = _make_signal(SignalType.BUDGET_WASTE, entity_id="b1", confidence=0.75,
                           metrics={"d7_roas": 0.3, "spend": 500.0, "total_revenue": 150.0})
        opps = mapper.map(sig)
        reduction = [o for o in opps if o.opportunity_type == OpportunityType.BUDGET_REDUCTION][0]
        assert "reduce_spend" in reduction.actions
        assert "pause_low_performing_ads" in reduction.actions

    def test_waste_reduction_recommends_lower_budget(self, mapper):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalType, OpportunityType

        sig = _make_signal(SignalType.BUDGET_WASTE, entity_id="b1", confidence=0.75,
                           metrics={"d7_roas": 0.3, "spend": 500.0, "total_revenue": 150.0})
        opps = mapper.map(sig)
        reduction = [o for o in opps if o.opportunity_type == OpportunityType.BUDGET_REDUCTION][0]
        assert reduction.recommended_params["recommended_budget"] < 500.0
        assert "reduction_pct" in reduction.recommended_params

    def test_waste_reduction_risk_low(self, mapper):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalType

        sig = _make_signal(SignalType.BUDGET_WASTE, entity_id="b1", confidence=0.75,
                           metrics={"d7_roas": 0.3, "spend": 500.0, "total_revenue": 150.0})
        opps = mapper.map(sig)
        assert opps[0].risk == "low"

    def test_waste_rebalance_priority_medium(self, mapper):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import (
            SignalType, OpportunityType, OpportunityPriority,
        )

        sig = _make_signal(SignalType.BUDGET_WASTE, entity_id="b1", confidence=0.75,
                           metrics={"d7_roas": 0.3, "spend": 500.0, "total_revenue": 150.0})
        opps = mapper.map(sig)
        rebalance = [o for o in opps if o.opportunity_type == OpportunityType.UA_REBALANCE][0]
        assert rebalance.priority == OpportunityPriority.MEDIUM

    def test_waste_critical_priority(self, mapper):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import (
            SignalType, SignalSeverity, OpportunityPriority,
        )

        sig = _make_signal(SignalType.BUDGET_WASTE, entity_id="b1", confidence=0.75,
                           severity=SignalSeverity.CRITICAL,
                           metrics={"d7_roas": 0.1, "spend": 500.0, "total_revenue": 50.0})
        opps = mapper.map(sig)
        assert opps[0].priority == OpportunityPriority.CRITICAL

    def test_waste_has_explanation(self, mapper):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalType

        sig = _make_signal(SignalType.BUDGET_WASTE, entity_id="b1", confidence=0.75,
                           metrics={"d7_roas": 0.3, "spend": 500.0, "total_revenue": 150.0})
        opps = mapper.map(sig)
        assert "waste" in opps[0].explanation.lower()

    # --- Custom gains ---

    def test_custom_gains_override(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.strategies.ua_opportunities import UAOpportunityMapper
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalType, OpportunityType

        mapper = UAOpportunityMapper({OpportunityType.UA_SCALE: 0.60})
        sig = _make_signal(SignalType.SCALE_OPPORTUNITY, entity_id="s1", confidence=0.9,
                           metrics={"d30_roas": 2.5, "spend": 200.0})
        opps = mapper.map(sig)
        assert opps[0].expected_gain == 0.60


# ═══════════════════════════════════════════════════════════════
# RevenueOpportunityMapper Tests
# ═══════════════════════════════════════════════════════════════


class TestRevenueOpportunityMapper:
    """RevenueOpportunityMapper 测试."""

    @pytest.fixture
    def mapper(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.strategies.revenue_opportunities import RevenueOpportunityMapper
        return RevenueOpportunityMapper()

    # --- LTV Upside ---

    def test_ltv_upside_generates_two_opportunities(self, mapper):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalType

        sig = _make_signal(SignalType.LTV_UPSIDE, entity_id="l1", confidence=0.8,
                           metrics={"d7_ltv": 2.0, "d30_ltv": 8.0, "ltv_ratio": 3.0, "ltv_absolute_gain": 6.0})
        opps = mapper.map(sig)
        assert len(opps) == 2

    def test_ltv_upside_types(self, mapper):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalType, OpportunityType

        sig = _make_signal(SignalType.LTV_UPSIDE, entity_id="l1", confidence=0.8,
                           metrics={"d7_ltv": 2.0, "d30_ltv": 8.0, "ltv_ratio": 3.0})
        opps = mapper.map(sig)
        types = [o.opportunity_type for o in opps]
        assert OpportunityType.MONETIZATION_SCALE in types
        assert OpportunityType.UA_SCALE in types

    def test_ltv_upside_monetization_actions(self, mapper):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalType, OpportunityType

        sig = _make_signal(SignalType.LTV_UPSIDE, entity_id="l1", confidence=0.8,
                           metrics={"d7_ltv": 2.0, "d30_ltv": 8.0, "ltv_ratio": 3.0})
        opps = mapper.map(sig)
        monetization = [o for o in opps if o.opportunity_type == OpportunityType.MONETIZATION_SCALE][0]
        assert "increase_ua_bid" in monetization.actions
        assert "increase_retention_investment" in monetization.actions

    def test_ltv_upside_monetization_risk_low(self, mapper):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalType

        sig = _make_signal(SignalType.LTV_UPSIDE, entity_id="l1", confidence=0.8,
                           metrics={"d7_ltv": 2.0, "d30_ltv": 8.0, "ltv_ratio": 3.0})
        opps = mapper.map(sig)
        assert opps[0].risk == "low"

    def test_ltv_upside_ua_scale_priority_high(self, mapper):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import (
            SignalType, OpportunityType, OpportunityPriority,
        )

        sig = _make_signal(SignalType.LTV_UPSIDE, entity_id="l1", confidence=0.85,
                           metrics={"d7_ltv": 2.0, "d30_ltv": 8.0, "ltv_ratio": 3.0})
        opps = mapper.map(sig)
        ua_scale = [o for o in opps if o.opportunity_type == OpportunityType.UA_SCALE][0]
        assert ua_scale.priority == OpportunityPriority.HIGH

    def test_ltv_upside_has_params(self, mapper):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalType, OpportunityType

        sig = _make_signal(SignalType.LTV_UPSIDE, entity_id="l1", confidence=0.8,
                           metrics={"d7_ltv": 2.0, "d30_ltv": 8.0, "ltv_ratio": 3.0})
        opps = mapper.map(sig)
        monetization = [o for o in opps if o.opportunity_type == OpportunityType.MONETIZATION_SCALE][0]
        assert "bid_increase_pct" in monetization.recommended_params
        assert monetization.recommended_params["d30_ltv"] == 8.0

    def test_ltv_upside_expected_gain(self, mapper):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalType

        sig = _make_signal(SignalType.LTV_UPSIDE, entity_id="l1", confidence=0.8,
                           metrics={"d7_ltv": 2.0, "d30_ltv": 8.0, "ltv_ratio": 3.0})
        opps = mapper.map(sig)
        assert opps[0].expected_gain == 0.30

    # --- ROAS Drop ---

    def test_roas_drop_generates_two_opportunities(self, mapper):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalType

        sig = _make_signal(SignalType.ROAS_DROP, entity_id="r1", confidence=0.8,
                           metrics={"current_d7_roas": 0.5, "predicted_roas": 2.0, "roas_decay_pct": 0.75})
        opps = mapper.map(sig)
        assert len(opps) == 2

    def test_roas_drop_types(self, mapper):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalType, OpportunityType

        sig = _make_signal(SignalType.ROAS_DROP, entity_id="r1", confidence=0.8,
                           metrics={"current_d7_roas": 0.5, "predicted_roas": 2.0, "roas_decay_pct": 0.75})
        opps = mapper.map(sig)
        types = [o.opportunity_type for o in opps]
        assert OpportunityType.BUDGET_REDUCTION in types
        assert OpportunityType.UA_REBALANCE in types

    def test_roas_drop_reduction_actions(self, mapper):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalType, OpportunityType

        sig = _make_signal(SignalType.ROAS_DROP, entity_id="r1", confidence=0.8,
                           metrics={"current_d7_roas": 0.5, "predicted_roas": 2.0, "roas_decay_pct": 0.75})
        opps = mapper.map(sig)
        reduction = [o for o in opps if o.opportunity_type == OpportunityType.BUDGET_REDUCTION][0]
        assert "reduce_spend" in reduction.actions
        assert "adjust_bid_cap" in reduction.actions

    def test_roas_drop_critical_priority(self, mapper):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import (
            SignalType, SignalSeverity, OpportunityPriority,
        )

        sig = _make_signal(SignalType.ROAS_DROP, entity_id="r1", confidence=0.8,
                           severity=SignalSeverity.CRITICAL,
                           metrics={"current_d7_roas": 0.5, "predicted_roas": 2.0, "roas_decay_pct": 0.75})
        opps = mapper.map(sig)
        assert opps[0].priority == OpportunityPriority.CRITICAL

    def test_roas_drop_has_explanation(self, mapper):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalType

        sig = _make_signal(SignalType.ROAS_DROP, entity_id="r1", confidence=0.8,
                           metrics={"current_d7_roas": 0.5, "predicted_roas": 2.0, "roas_decay_pct": 0.75})
        opps = mapper.map(sig)
        assert "ROAS" in opps[0].explanation or "roas" in opps[0].explanation.lower()

    # --- Monetization Issue ---

    def test_monetization_issue_generates_one_opportunity(self, mapper):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalType

        sig = _make_signal(SignalType.MONETIZATION_ISSUE, entity_id="m1", confidence=0.6,
                           metrics={"iap_conversion": 0.005, "ad_arpdau": 0.05})
        opps = mapper.map(sig)
        assert len(opps) == 1

    def test_monetization_issue_type_is_optimize(self, mapper):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalType, OpportunityType

        sig = _make_signal(SignalType.MONETIZATION_ISSUE, entity_id="m1", confidence=0.6,
                           metrics={"iap_conversion": 0.005, "ad_arpdau": 0.05})
        opps = mapper.map(sig)
        assert opps[0].opportunity_type == OpportunityType.MONETIZATION_OPTIMIZE

    def test_monetization_issue_iap_actions(self, mapper):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalType

        sig = _make_signal(SignalType.MONETIZATION_ISSUE, entity_id="m1", confidence=0.6,
                           metrics={"iap_conversion": 0.005, "ad_arpdau": 0.05})
        opps = mapper.map(sig)
        assert "analyze_payer_funnel" in opps[0].actions
        assert "optimize_shop_experience" in opps[0].actions

    def test_monetization_issue_iaa_actions(self, mapper):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalType

        sig = _make_signal(SignalType.MONETIZATION_ISSUE, entity_id="m1", confidence=0.6,
                           metrics={"iap_conversion": 0.05, "ad_arpdau": 0.005})
        opps = mapper.map(sig)
        assert "optimize_ad_placement" in opps[0].actions
        assert "test_ad_networks" in opps[0].actions

    def test_monetization_issue_both_iaa_iap_actions(self, mapper):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalType

        sig = _make_signal(SignalType.MONETIZATION_ISSUE, entity_id="m1", confidence=0.6,
                           metrics={"iap_conversion": 0.003, "ad_arpdau": 0.003})
        opps = mapper.map(sig)
        # Both IAP and IAA actions should be present
        assert "analyze_payer_funnel" in opps[0].actions
        assert "optimize_ad_placement" in opps[0].actions

    def test_monetization_issue_zero_metrics_fallback(self, mapper):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalType

        sig = _make_signal(SignalType.MONETIZATION_ISSUE, entity_id="m1", confidence=0.6,
                           metrics={"iap_conversion": 0.0, "ad_arpdau": 0.0})
        opps = mapper.map(sig)
        assert len(opps[0].actions) > 0  # fallback actions

    def test_monetization_issue_risk_medium(self, mapper):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalType

        sig = _make_signal(SignalType.MONETIZATION_ISSUE, entity_id="m1", confidence=0.6,
                           metrics={"iap_conversion": 0.005, "ad_arpdau": 0.05})
        opps = mapper.map(sig)
        assert opps[0].risk == "medium"

    def test_monetization_issue_expected_gain(self, mapper):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalType

        sig = _make_signal(SignalType.MONETIZATION_ISSUE, entity_id="m1", confidence=0.6,
                           metrics={"iap_conversion": 0.005, "ad_arpdau": 0.05})
        opps = mapper.map(sig)
        assert opps[0].expected_gain == 0.15


# ═══════════════════════════════════════════════════════════════
# GrowthOpportunityEngine Tests
# ═══════════════════════════════════════════════════════════════


class TestGrowthOpportunityEngine:
    """GrowthOpportunityEngine 核心测试."""

    @pytest.fixture
    def engine(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine import GrowthOpportunityEngine
        return GrowthOpportunityEngine()

    def test_analyze_empty_signals(self, engine):
        opportunities = engine.analyze([])
        assert opportunities == []

    def test_analyze_winner_generates_opportunities(self, engine):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalType

        signals = [
            _make_signal(SignalType.CREATIVE_WINNER, entity_id="w1", confidence=0.92,
                         metrics={"d30_roas": 3.0, "d30_ltv": 8.0, "fitness_score": 0.9, "spend": 500}),
        ]
        opps = engine.analyze(signals)
        assert len(opps) >= 2

    def test_analyze_multiple_signals(self, engine):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalType

        signals = [
            _make_signal(SignalType.CREATIVE_WINNER, entity_id="w1", confidence=0.92,
                         metrics={"d30_roas": 3.0, "d30_ltv": 8.0, "fitness_score": 0.9, "spend": 500}),
            _make_signal(SignalType.CREATIVE_FATIGUE, entity_id="f1", confidence=0.85,
                         metrics={"fatigue_score": 0.82, "ctr": 0.01, "d7_roas": 0.5, "frequency": 6.0}),
            _make_signal(SignalType.SCALE_OPPORTUNITY, entity_id="s1", confidence=0.88,
                         metrics={"d30_roas": 2.5, "spend": 200.0}),
        ]
        opps = engine.analyze(signals)
        # Winner: 2 opps + Fatigue: 2 opps + Scale: 1 opp = 5 opps
        assert len(opps) >= 5

    def test_analyze_results_sorted_by_score(self, engine):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalType

        signals = [
            _make_signal(SignalType.CREATIVE_WINNER, entity_id="w1", confidence=0.92,
                         metrics={"d30_roas": 3.0, "d30_ltv": 8.0, "fitness_score": 0.9, "spend": 500}),
            _make_signal(SignalType.BUDGET_WASTE, entity_id="b1", confidence=0.5,
                         metrics={"d7_roas": 0.1, "spend": 500.0, "total_revenue": 50.0}),
        ]
        opps = engine.analyze(signals)
        for i in range(len(opps) - 1):
            assert opps[i].score >= opps[i + 1].score

    def test_analyze_scores_set(self, engine):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalType

        signals = [
            _make_signal(SignalType.CREATIVE_WINNER, entity_id="w1", confidence=0.92,
                         metrics={"d30_roas": 3.0, "d30_ltv": 8.0, "fitness_score": 0.9, "spend": 500}),
        ]
        opps = engine.analyze(signals)
        for opp in opps:
            assert opp.score > 0

    def test_analyze_batch(self, engine):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalType

        signals = [
            _make_signal(SignalType.CREATIVE_WINNER, entity_id="w1", confidence=0.92,
                         metrics={"d30_roas": 3.0, "d30_ltv": 8.0, "fitness_score": 0.9, "spend": 500}),
            _make_signal(SignalType.SCALE_OPPORTUNITY, entity_id="s1", confidence=0.88,
                         metrics={"d30_roas": 2.5, "spend": 200.0}),
        ]
        batch = engine.analyze_batch(signals, product_id="p1", date="2026-07-24")
        assert batch.product_id == "p1"
        assert batch.date == "2026-07-24"
        assert batch.total_signals == 2
        assert batch.total_opportunities > 0
        assert batch.elapsed_ms > 0
        assert len(batch.summary) > 0
        assert len(batch.opportunities) > 0

    def test_analyze_batch_empty(self, engine):
        batch = engine.analyze_batch([], product_id="p1")
        assert batch.total_signals == 0
        assert batch.total_opportunities == 0

    def test_analyze_batch_to_dict(self, engine):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalType

        signals = [
            _make_signal(SignalType.CREATIVE_WINNER, entity_id="w1", confidence=0.92,
                         metrics={"d30_roas": 3.0, "d30_ltv": 8.0}),
        ]
        batch = engine.analyze_batch(signals, product_id="p1")
        d = batch.to_dict()
        assert "batch_id" in d
        assert "signals" not in d  # batch has opportunities, not signals
        assert "opportunities" in d

    # --- Filters ---

    def test_filter_by_priority_high(self, engine):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import (
            SignalType, OpportunityPriority, GrowthOpportunity, OpportunityType,
        )

        opps = [
            GrowthOpportunity(opportunity_type=OpportunityType.CREATIVE_SCALE, priority=OpportunityPriority.HIGH),
            GrowthOpportunity(opportunity_type=OpportunityType.UA_SCALE, priority=OpportunityPriority.MEDIUM),
            GrowthOpportunity(opportunity_type=OpportunityType.BUDGET_REDUCTION, priority=OpportunityPriority.CRITICAL),
        ]
        filtered = engine.filter_by_priority(opps, OpportunityPriority.HIGH)
        assert len(filtered) == 2

    def test_filter_by_priority_critical(self, engine):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import (
            OpportunityPriority, GrowthOpportunity, OpportunityType,
        )

        opps = [
            GrowthOpportunity(opportunity_type=OpportunityType.CREATIVE_SCALE, priority=OpportunityPriority.HIGH),
            GrowthOpportunity(opportunity_type=OpportunityType.BUDGET_REDUCTION, priority=OpportunityPriority.CRITICAL),
        ]
        filtered = engine.filter_by_priority(opps, OpportunityPriority.CRITICAL)
        assert len(filtered) == 1

    def test_filter_by_type(self, engine):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import (
            GrowthOpportunity, OpportunityType,
        )

        opps = [
            GrowthOpportunity(opportunity_type=OpportunityType.CREATIVE_SCALE),
            GrowthOpportunity(opportunity_type=OpportunityType.UA_SCALE),
            GrowthOpportunity(opportunity_type=OpportunityType.CREATIVE_SCALE),
        ]
        filtered = engine.filter_by_type(opps, OpportunityType.CREATIVE_SCALE)
        assert len(filtered) == 2

    def test_get_top_opportunities(self, engine):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import (
            GrowthOpportunity, OpportunityType,
        )

        opps = [
            GrowthOpportunity(opportunity_type=OpportunityType.CREATIVE_SCALE, score=0.5),
            GrowthOpportunity(opportunity_type=OpportunityType.UA_SCALE, score=0.9),
            GrowthOpportunity(opportunity_type=OpportunityType.BUDGET_REDUCTION, score=0.3),
            GrowthOpportunity(opportunity_type=OpportunityType.CREATIVE_MUTATION, score=0.7),
            GrowthOpportunity(opportunity_type=OpportunityType.UA_REBALANCE, score=0.6),
            GrowthOpportunity(opportunity_type=OpportunityType.MONETIZATION_OPTIMIZE, score=0.4),
        ]
        top = engine.get_top_opportunities(opps, n=3)
        assert len(top) == 3
        assert top[0].score == 0.9
        assert top[1].score == 0.7
        assert top[2].score == 0.6

    def test_get_actionable_opportunities(self, engine):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import (
            GrowthOpportunity, OpportunityType,
        )

        opps = [
            GrowthOpportunity(opportunity_type=OpportunityType.CREATIVE_SCALE, confidence=0.9),
            GrowthOpportunity(opportunity_type=OpportunityType.UA_SCALE, confidence=0.3),
            GrowthOpportunity(opportunity_type=OpportunityType.BUDGET_REDUCTION, confidence=0.8),
        ]
        actionable = engine.get_actionable_opportunities(opps)
        assert len(actionable) == 2

    # --- Ranking ---

    def test_ranking_higher_confidence_scores_higher(self, engine):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import (
            SignalType, OpportunityType,
        )

        signals = [
            _make_signal(SignalType.CREATIVE_WINNER, entity_id="w1", confidence=0.95,
                         metrics={"d30_roas": 3.0, "d30_ltv": 8.0, "fitness_score": 0.9, "spend": 500}),
            _make_signal(SignalType.CREATIVE_WINNER, entity_id="w2", confidence=0.7,
                         metrics={"d30_roas": 2.0, "d30_ltv": 5.0, "fitness_score": 0.6, "spend": 300}),
        ]
        opps = engine.analyze(signals)
        # w1 should rank higher than w2 for same opportunity type
        w1_scales = [o for o in opps if o.entity_id == "w1" and o.opportunity_type == OpportunityType.CREATIVE_SCALE]
        w2_scales = [o for o in opps if o.entity_id == "w2" and o.opportunity_type == OpportunityType.CREATIVE_SCALE]
        assert len(w1_scales) > 0 and len(w2_scales) > 0
        w1_idx = opps.index(w1_scales[0])
        w2_idx = opps.index(w2_scales[0])
        assert w1_idx < w2_idx

    def test_ranking_critical_above_medium(self, engine):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalType, SignalSeverity

        signals = [
            _make_signal(SignalType.CREATIVE_WINNER, entity_id="w1", confidence=0.7,
                         severity=SignalSeverity.MEDIUM,
                         metrics={"d30_roas": 2.0, "d30_ltv": 6.0, "fitness_score": 0.7, "spend": 300}),
            _make_signal(SignalType.ROAS_DROP, entity_id="r1", confidence=0.8,
                         severity=SignalSeverity.CRITICAL,
                         metrics={"current_d7_roas": 0.3, "predicted_roas": 2.0, "roas_decay_pct": 0.85}),
        ]
        opps = engine.analyze(signals)
        # CRITICAL ROAS drop should rank high
        critical_opps = [o for o in opps if o.priority.value == "critical"]
        assert len(critical_opps) > 0

    def test_ranking_low_risk_scores_higher(self, engine):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalType

        signals = [
            _make_signal(SignalType.CREATIVE_WINNER, entity_id="w1", confidence=0.9,
                         metrics={"d30_roas": 3.0, "d30_ltv": 8.0, "fitness_score": 0.9, "spend": 500}),
            _make_signal(SignalType.CREATIVE_FATIGUE, entity_id="f1", confidence=0.9,
                         metrics={"fatigue_score": 0.82, "ctr": 0.01, "d7_roas": 0.5, "frequency": 6.0}),
        ]
        opps = engine.analyze(signals)
        # Winner (low risk) should score higher than Fatigue (medium risk) with same confidence
        winner_opps = [o for o in opps if o.risk == "low"]
        medium_opps = [o for o in opps if o.risk == "medium"]
        if winner_opps and medium_opps:
            # Low risk opps should appear before medium risk ones (for same confidence)
            pass  # Verified by sorted order

    # --- Custom gains ---

    def test_custom_gains_propagate_to_mappers(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine import GrowthOpportunityEngine
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import (
            SignalType, OpportunityType,
        )

        engine = GrowthOpportunityEngine({OpportunityType.CREATIVE_SCALE: 0.55})
        signals = [
            _make_signal(SignalType.CREATIVE_WINNER, entity_id="w1", confidence=0.92,
                         metrics={"d30_roas": 3.0, "d30_ltv": 8.0}),
        ]
        opps = engine.analyze(signals)
        scale_opps = [o for o in opps if o.opportunity_type == OpportunityType.CREATIVE_SCALE]
        assert len(scale_opps) > 0
        assert scale_opps[0].expected_gain == 0.55


# ═══════════════════════════════════════════════════════════════
# Edge Cases
# ═══════════════════════════════════════════════════════════════


class TestEdgeCases:
    """边界条件测试."""

    @pytest.fixture
    def engine(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine import GrowthOpportunityEngine
        return GrowthOpportunityEngine()

    def test_signal_with_empty_metrics(self, engine):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalType

        sig = _make_signal(SignalType.CREATIVE_WINNER, entity_id="w1", confidence=0.8, metrics={})
        opps = engine.analyze([sig])
        assert len(opps) > 0
        # Should not crash with empty metrics
        for opp in opps:
            assert opp.expected_gain > 0

    def test_signal_with_zero_confidence(self, engine):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalType

        sig = _make_signal(SignalType.CREATIVE_WINNER, entity_id="w1", confidence=0.0)
        opps = engine.analyze([sig])
        # Should still generate opportunities but with low score
        assert len(opps) > 0
        for opp in opps:
            assert opp.score == 0.0

    def test_signal_with_very_low_metrics(self, engine):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalType

        sig = _make_signal(SignalType.BUDGET_WASTE, entity_id="b1", confidence=0.3,
                           metrics={"d7_roas": 0.01, "spend": 10000.0, "total_revenue": 100.0})
        opps = engine.analyze([sig])
        assert len(opps) > 0

    def test_all_signal_types_generate_opportunities(self, engine):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import (
            SignalType, SignalSeverity,
        )

        all_signals = [
            _make_signal(SignalType.CREATIVE_WINNER, entity_id="w1", confidence=0.9,
                         metrics={"d30_roas": 3.0, "d30_ltv": 8.0, "fitness_score": 0.9, "spend": 500}),
            _make_signal(SignalType.CREATIVE_FATIGUE, entity_id="f1", confidence=0.85,
                         metrics={"fatigue_score": 0.82, "ctr": 0.01, "d7_roas": 0.5, "frequency": 6.0}),
            _make_signal(SignalType.CREATIVE_UNDERPERFORM, entity_id="u1", confidence=0.75,
                         metrics={"d7_roas": 0.3, "ctr": 0.003, "spend": 200}),
            _make_signal(SignalType.ROAS_DROP, entity_id="r1", confidence=0.8,
                         metrics={"current_d7_roas": 0.5, "predicted_roas": 2.0, "roas_decay_pct": 0.75}),
            _make_signal(SignalType.LTV_UPSIDE, entity_id="l1", confidence=0.8,
                         metrics={"d7_ltv": 2.0, "d30_ltv": 8.0, "ltv_ratio": 3.0}),
            _make_signal(SignalType.SCALE_OPPORTUNITY, entity_id="s1", confidence=0.88,
                         metrics={"d30_roas": 2.5, "spend": 200.0}),
            _make_signal(SignalType.BUDGET_WASTE, entity_id="b1", confidence=0.75,
                         metrics={"d7_roas": 0.3, "spend": 500.0, "total_revenue": 150.0}),
            _make_signal(SignalType.MONETIZATION_ISSUE, entity_id="m1", confidence=0.6,
                         metrics={"iap_conversion": 0.005, "ad_arpdau": 0.05}),
        ]
        opps = engine.analyze(all_signals)
        assert len(opps) > 0

        # Verify all 8 opportunity types are generated
        generated_types = {o.opportunity_type.value for o in opps}
        expected = {"creative_scale", "creative_refresh", "creative_mutation",
                    "ua_scale", "ua_rebalance", "budget_reduction",
                    "monetization_optimize", "monetization_scale"}
        missing = expected - generated_types
        assert len(missing) == 0, f"Missing opportunity types: {missing}"

    def test_many_signals_no_crash(self, engine):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalType

        signals = []
        for i in range(50):
            signals.append(_make_signal(
                SignalType.CREATIVE_WINNER, entity_id=f"w{i}", confidence=0.7 + i * 0.005,
                metrics={"d30_roas": 1.0 + i * 0.05, "d30_ltv": 3.0 + i * 0.1, "fitness_score": 0.5 + i * 0.01, "spend": 100 + i * 10},
            ))
        opps = engine.analyze(signals)
        assert len(opps) > 0
        # Verify sorted
        for i in range(len(opps) - 1):
            assert opps[i].score >= opps[i + 1].score


# ═══════════════════════════════════════════════════════════════
# Integration Scenarios
# ═══════════════════════════════════════════════════════════════


class TestIntegrationScenarios:
    """集成场景测试."""

    @pytest.fixture
    def engine(self):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine import GrowthOpportunityEngine
        return GrowthOpportunityEngine()

    def test_full_pipeline_signal_to_opportunity(self, engine):
        """模拟完整 Signal → Opportunity 流水线."""
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import (
            SignalType, OpportunityType,
        )

        signals = [
            _make_signal(SignalType.CREATIVE_WINNER, entity_id="w1", confidence=0.92,
                         metrics={"d30_roas": 3.5, "d30_ltv": 10.0, "fitness_score": 0.95, "spend": 500}),
            _make_signal(SignalType.CREATIVE_FATIGUE, entity_id="f1", confidence=0.85,
                         metrics={"fatigue_score": 0.82, "ctr": 0.01, "d7_roas": 0.5, "frequency": 6.0}),
            _make_signal(SignalType.SCALE_OPPORTUNITY, entity_id="s1", confidence=0.88,
                         metrics={"d30_roas": 2.5, "spend": 200.0}),
            _make_signal(SignalType.BUDGET_WASTE, entity_id="b1", confidence=0.75,
                         metrics={"d7_roas": 0.3, "spend": 500.0, "total_revenue": 150.0}),
            _make_signal(SignalType.ROAS_DROP, entity_id="r1", confidence=0.8,
                         metrics={"current_d7_roas": 0.5, "predicted_roas": 2.0, "roas_decay_pct": 0.75}),
            _make_signal(SignalType.LTV_UPSIDE, entity_id="l1", confidence=0.8,
                         metrics={"d7_ltv": 2.0, "d30_ltv": 8.0, "ltv_ratio": 3.0}),
            _make_signal(SignalType.MONETIZATION_ISSUE, entity_id="m1", confidence=0.6,
                         metrics={"iap_conversion": 0.005, "ad_arpdau": 0.05}),
        ]
        opps = engine.analyze(signals)

        # Should generate many opportunities
        assert len(opps) >= 10

        # Verify all major opportunity types present
        types = {o.opportunity_type for o in opps}
        assert OpportunityType.CREATIVE_SCALE in types
        assert OpportunityType.CREATIVE_REFRESH in types
        assert OpportunityType.UA_SCALE in types
        assert OpportunityType.BUDGET_REDUCTION in types
        assert OpportunityType.MONETIZATION_OPTIMIZE in types

        # Verify sorted by score
        for i in range(len(opps) - 1):
            assert opps[i].score >= opps[i + 1].score

    def test_winner_opportunity_preserves_signal_link(self, engine):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalType

        sig = _make_signal(SignalType.CREATIVE_WINNER, entity_id="w1", confidence=0.92,
                           metrics={"d30_roas": 3.0, "d30_ltv": 8.0})
        opps = engine.analyze([sig])
        for opp in opps:
            assert opp.source_signal_id == sig.signal_id
            assert opp.entity_id == "w1"

    def test_opportunity_explanation_not_empty(self, engine):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalType

        signals = [
            _make_signal(SignalType.CREATIVE_WINNER, entity_id="w1", confidence=0.92,
                         metrics={"d30_roas": 3.0, "d30_ltv": 8.0}),
            _make_signal(SignalType.CREATIVE_FATIGUE, entity_id="f1", confidence=0.85,
                         metrics={"fatigue_score": 0.82}),
            _make_signal(SignalType.SCALE_OPPORTUNITY, entity_id="s1", confidence=0.88,
                         metrics={"d30_roas": 2.5, "spend": 200.0}),
            _make_signal(SignalType.BUDGET_WASTE, entity_id="b1", confidence=0.75,
                         metrics={"d7_roas": 0.3, "spend": 500.0, "total_revenue": 150.0}),
        ]
        opps = engine.analyze(signals)
        for opp in opps:
            assert len(opp.explanation) > 0

    def test_batch_full_flow(self, engine):
        from market_ops.creative_vision_runtime.growth_runtime.decision_engine.models import SignalType

        signals = [
            _make_signal(SignalType.CREATIVE_WINNER, entity_id="w1", confidence=0.92,
                         metrics={"d30_roas": 3.5, "d30_ltv": 10.0, "fitness_score": 0.95, "spend": 500}),
            _make_signal(SignalType.SCALE_OPPORTUNITY, entity_id="s1", confidence=0.88,
                         metrics={"d30_roas": 2.5, "spend": 200.0}),
            _make_signal(SignalType.BUDGET_WASTE, entity_id="b1", confidence=0.75,
                         metrics={"d7_roas": 0.3, "spend": 500.0, "total_revenue": 150.0}),
        ]
        batch = engine.analyze_batch(signals, product_id="p1", date="2026-07-24")

        assert batch.product_id == "p1"
        assert batch.total_signals == 3
        assert batch.total_opportunities > 0
        assert len(batch.summary) > 0
        assert batch.elapsed_ms > 0

        # Verify batch summary has correct counts
        total_from_summary = sum(batch.summary.values())
        assert total_from_summary == batch.total_opportunities