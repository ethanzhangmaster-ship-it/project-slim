"""E13.5.1 Growth Intelligence Models — 测试套件.

测试覆盖:
  - OpportunityType / OpportunitySource / DecisionStatus / RiskLevel / DecisionPriority 枚举
  - CurrentMetrics: 创建、to_dict、属性
  - SignalSummary: 创建、默认值、to_dict
  - MemoryContext: 创建、默认值、to_dict
  - DecisionContext: 创建、to_dict、has_metrics、has_memory
  - ExpectedImpact: 创建、to_dict、默认值
  - GrowthOpportunity: 创建、to_dict、is_high_priority、is_actionable、compute_priority
  - DecisionAction: 创建、to_dict、默认值
  - GrowthDecision: 创建、to_dict、生命周期、风险计算、审批
  - DecisionResult: 创建、to_dict、默认值
  - DecisionRecord: 创建、to_dict、完整记录
  - 集成场景: 完整决策链路
"""

from __future__ import annotations

import pytest


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════

def _make_metrics(**kwargs) -> Any:
    from market_ops.creative_vision_runtime.growth_runtime.intelligence.intelligence_models import CurrentMetrics
    defaults = {
        "spend": 500.0,
        "revenue": 750.0,
        "roas": 1.5,
        "ctr": 0.025,
        "cpi": 3.5,
        "impressions": 10000,
        "clicks": 250,
        "installs": 80,
        "payers": 8,
        "d7_ltv": 2.5,
        "d30_ltv": 5.0,
        "payer_rate": 0.1,
    }
    defaults.update(kwargs)
    return CurrentMetrics(**defaults)


def _make_opportunity(**kwargs) -> Any:
    from market_ops.creative_vision_runtime.growth_runtime.intelligence.intelligence_models import (
        GrowthOpportunity, OpportunityType, OpportunitySource,
    )
    defaults = {
        "opportunity_type": OpportunityType.CREATIVE_SCALE,
        "source": OpportunitySource.REALITY_INSIGHT,
        "product_id": "p001",
        "creative_id": "c001",
        "impact_score": 0.75,
        "confidence": 0.85,
        "urgency": 0.7,
        "reason": "CTR high, ROAS above target, ready to scale",
        "recommended_action": "increase_budget",
    }
    defaults.update(kwargs)
    return GrowthOpportunity(**defaults)


def _make_context(**kwargs) -> Any:
    from market_ops.creative_vision_runtime.growth_runtime.intelligence.intelligence_models import DecisionContext
    defaults = {
        "product_id": "p001",
        "campaign_id": "camp001",
        "creative_id": "c001",
        "date": "2026-07-24",
        "current_metrics": _make_metrics(),
    }
    defaults.update(kwargs)
    return DecisionContext(**defaults)


def _make_decision(**kwargs) -> Any:
    from market_ops.creative_vision_runtime.growth_runtime.intelligence.intelligence_models import GrowthDecision
    defaults = {
        "objective": "scale_spend",
        "confidence": 0.85,
        "reasoning": "CTR trends upward, CPI below target, safe to scale",
    }
    defaults.update(kwargs)
    return GrowthDecision(**defaults)


# ═══════════════════════════════════════════════════════════════
# Test: Enums
# ═══════════════════════════════════════════════════════════════

class TestOpportunityType:
    def test_values_exist(self):
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.intelligence_models import OpportunityType
        assert OpportunityType.CREATIVE_SCALE.value == "creative_scale"
        assert OpportunityType.CREATIVE_REFRESH.value == "creative_refresh"
        assert OpportunityType.BUDGET_OPTIMIZATION.value == "budget_optimization"
        assert OpportunityType.AUDIENCE_EXPANSION.value == "audience_expansion"
        assert OpportunityType.RISK_MITIGATION.value == "risk_mitigation"

    def test_total_count(self):
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.intelligence_models import OpportunityType
        assert len(OpportunityType) == 12


class TestOpportunitySource:
    def test_values_exist(self):
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.intelligence_models import OpportunitySource
        assert OpportunitySource.REALITY_INSIGHT.value == "reality_insight"
        assert OpportunitySource.PREDICTION.value == "prediction"
        assert OpportunitySource.PATTERN_MEMORY.value == "pattern_memory"
        assert OpportunitySource.STRATEGY_MEMORY.value == "strategy_memory"
        assert OpportunitySource.MANUAL.value == "manual"


class TestDecisionStatus:
    def test_values_exist(self):
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.intelligence_models import DecisionStatus
        assert DecisionStatus.DRAFT.value == "draft"
        assert DecisionStatus.APPROVED.value == "approved"
        assert DecisionStatus.EXECUTED.value == "executed"
        assert DecisionStatus.BLOCKED.value == "blocked"
        assert DecisionStatus.ROLLED_BACK.value == "rolled_back"

    def test_total_count(self):
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.intelligence_models import DecisionStatus
        assert len(DecisionStatus) == 9


class TestRiskLevel:
    def test_values_exist(self):
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.intelligence_models import RiskLevel
        assert RiskLevel.NONE.value == "none"
        assert RiskLevel.LOW.value == "low"
        assert RiskLevel.MEDIUM.value == "medium"
        assert RiskLevel.HIGH.value == "high"
        assert RiskLevel.CRITICAL.value == "critical"


class TestDecisionPriority:
    def test_values_exist(self):
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.intelligence_models import DecisionPriority
        assert DecisionPriority.CRITICAL.value == "critical"
        assert DecisionPriority.HIGH.value == "high"
        assert DecisionPriority.MEDIUM.value == "medium"
        assert DecisionPriority.LOW.value == "low"


# ═══════════════════════════════════════════════════════════════
# Test: CurrentMetrics
# ═══════════════════════════════════════════════════════════════

class TestCurrentMetrics:
    def test_default_creation(self):
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.intelligence_models import CurrentMetrics
        m = CurrentMetrics()
        assert m.spend == 0.0
        assert m.roas == 0.0
        assert m.impressions == 0

    def test_full_creation(self):
        m = _make_metrics()
        assert m.spend == 500.0
        assert m.revenue == 750.0
        assert m.roas == 1.5
        assert m.ctr == 0.025
        assert m.cpi == 3.5
        assert m.impressions == 10000
        assert m.payers == 8

    def test_to_dict(self):
        m = _make_metrics()
        d = m.to_dict()
        assert d["spend"] == 500.0
        assert d["roas"] == 1.5
        assert "custom" in d

    def test_custom_metrics(self):
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.intelligence_models import CurrentMetrics
        m = CurrentMetrics(roas=2.0, custom={"ipm": 25.0, "cvr": 0.03})
        assert m.custom["ipm"] == 25.0
        assert m.custom["cvr"] == 0.03


# ═══════════════════════════════════════════════════════════════
# Test: SignalSummary
# ═══════════════════════════════════════════════════════════════

class TestSignalSummary:
    def test_default_creation(self):
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.intelligence_models import SignalSummary
        s = SignalSummary()
        assert s.active_signals == []
        assert s.fatigue_detected is False
        assert s.anomaly_detected is False
        assert s.trend == "stable"

    def test_fatigue_detected(self):
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.intelligence_models import SignalSummary
        s = SignalSummary(
            active_signals=["creative_fatigue"],
            fatigue_detected=True,
            prediction={"fatigue_probability": 0.87},
            trend="declining",
        )
        assert s.fatigue_detected is True
        assert s.prediction["fatigue_probability"] == 0.87

    def test_to_dict(self):
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.intelligence_models import SignalSummary
        s = SignalSummary(
            active_signals=["scale_opportunity"],
            anomaly_detected=True,
            trend="improving",
        )
        d = s.to_dict()
        assert d["trend"] == "improving"
        assert d["anomaly_detected"] is True


# ═══════════════════════════════════════════════════════════════
# Test: MemoryContext
# ═══════════════════════════════════════════════════════════════

class TestMemoryContext:
    def test_default_creation(self):
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.intelligence_models import MemoryContext
        mc = MemoryContext()
        assert mc.matched_patterns == []
        assert mc.historical_success_rate == 0.0
        assert mc.total_related_experiences == 0

    def test_populated(self):
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.intelligence_models import MemoryContext
        mc = MemoryContext(
            matched_patterns=["p1", "p2"],
            recommended_strategies=["s1"],
            relevant_failures=["f1"],
            historical_success_rate=0.78,
            total_related_experiences=25,
        )
        assert len(mc.matched_patterns) == 2
        assert mc.historical_success_rate == 0.78
        assert mc.total_related_experiences == 25

    def test_to_dict(self):
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.intelligence_models import MemoryContext
        mc = MemoryContext(matched_patterns=["p1"], total_related_experiences=10)
        d = mc.to_dict()
        assert d["matched_patterns"] == ["p1"]
        assert d["total_related_experiences"] == 10


# ═══════════════════════════════════════════════════════════════
# Test: DecisionContext
# ═══════════════════════════════════════════════════════════════

class TestDecisionContext:
    def test_default_creation(self):
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.intelligence_models import DecisionContext
        ctx = DecisionContext()
        assert ctx.context_id != ""
        assert ctx.product_id == ""
        assert ctx.platform == "meta_ads"

    def test_full_creation(self):
        ctx = _make_context()
        assert ctx.product_id == "p001"
        assert ctx.campaign_id == "camp001"
        assert ctx.current_metrics.roas == 1.5

    def test_to_dict(self):
        ctx = _make_context()
        d = ctx.to_dict()
        assert d["product_id"] == "p001"
        assert d["current_metrics"]["roas"] == 1.5
        assert "signals" in d
        assert "memory_context" in d

    def test_has_metrics(self):
        ctx = _make_context()
        assert ctx.has_metrics is True

        from market_ops.creative_vision_runtime.growth_runtime.intelligence.intelligence_models import DecisionContext
        empty = DecisionContext()
        assert empty.has_metrics is False

    def test_has_memory(self):
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.intelligence_models import (
            DecisionContext, MemoryContext,
        )
        ctx = DecisionContext(memory_context=MemoryContext(total_related_experiences=15))
        assert ctx.has_memory is True

        ctx2 = DecisionContext()
        assert ctx2.has_memory is False

    def test_unique_ids(self):
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.intelligence_models import DecisionContext
        ids = {DecisionContext().context_id for _ in range(10)}
        assert len(ids) == 10


# ═══════════════════════════════════════════════════════════════
# Test: ExpectedImpact
# ═══════════════════════════════════════════════════════════════

class TestExpectedImpact:
    def test_default_creation(self):
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.intelligence_models import ExpectedImpact
        ei = ExpectedImpact()
        assert ei.roas_change == 0.0
        assert ei.timeframe_days == 7

    def test_full_creation(self):
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.intelligence_models import ExpectedImpact
        ei = ExpectedImpact(
            roas_change=0.15,
            spend_change=200.0,
            revenue_change=300.0,
            confidence=0.8,
            timeframe_days=14,
        )
        assert ei.roas_change == 0.15
        assert ei.revenue_change == 300.0
        assert ei.timeframe_days == 14

    def test_to_dict(self):
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.intelligence_models import ExpectedImpact
        ei = ExpectedImpact(roas_change=0.1, confidence=0.85)
        d = ei.to_dict()
        assert d["roas_change"] == 0.1
        assert d["confidence"] == 0.85


# ═══════════════════════════════════════════════════════════════
# Test: GrowthOpportunity
# ═══════════════════════════════════════════════════════════════

class TestGrowthOpportunity:
    def test_default_creation(self):
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.intelligence_models import GrowthOpportunity
        opp = GrowthOpportunity()
        assert opp.opportunity_id != ""
        assert opp.opportunity_type.value == "creative_scale"
        assert opp.priority.value == "medium"

    def test_full_creation(self):
        opp = _make_opportunity()
        assert opp.product_id == "p001"
        assert opp.impact_score == 0.75
        assert opp.confidence == 0.85
        assert opp.urgency == 0.7

    def test_to_dict(self):
        opp = _make_opportunity()
        d = opp.to_dict()
        assert d["opportunity_type"] == "creative_scale"
        assert d["source"] == "reality_insight"
        assert d["confidence"] == 0.85
        assert "expected_impact" in d

    def test_is_high_priority(self):
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.intelligence_models import DecisionPriority
        opp = _make_opportunity(priority=DecisionPriority.HIGH)
        assert opp.is_high_priority is True

        opp2 = _make_opportunity(priority=DecisionPriority.MEDIUM)
        assert opp2.is_high_priority is False

    def test_is_actionable(self):
        opp = _make_opportunity(confidence=0.85, impact_score=0.75)
        assert opp.is_actionable is True

        from market_ops.creative_vision_runtime.growth_runtime.intelligence.intelligence_models import GrowthOpportunity
        opp2 = GrowthOpportunity(confidence=0.5, impact_score=0.2)
        assert opp2.is_actionable is False

    def test_compute_priority_critical(self):
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.intelligence_models import (
            GrowthOpportunity, DecisionPriority,
        )
        opp = GrowthOpportunity(impact_score=0.9, urgency=0.85)
        opp.compute_priority()
        assert opp.priority == DecisionPriority.CRITICAL

    def test_compute_priority_high(self):
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.intelligence_models import (
            GrowthOpportunity, DecisionPriority,
        )
        opp = GrowthOpportunity(impact_score=0.7, urgency=0.5)
        opp.compute_priority()
        assert opp.priority == DecisionPriority.HIGH

    def test_compute_priority_medium(self):
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.intelligence_models import (
            GrowthOpportunity, DecisionPriority,
        )
        opp = GrowthOpportunity(impact_score=0.5, urgency=0.3)
        opp.compute_priority()
        assert opp.priority == DecisionPriority.MEDIUM

    def test_compute_priority_low(self):
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.intelligence_models import (
            GrowthOpportunity, DecisionPriority,
        )
        opp = GrowthOpportunity(impact_score=0.2, urgency=0.1)
        opp.compute_priority()
        assert opp.priority == DecisionPriority.LOW

    def test_with_memory_references(self):
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.intelligence_models import (
            GrowthOpportunity, OpportunitySource,
        )
        opp = GrowthOpportunity(
            source=OpportunitySource.PATTERN_MEMORY,
            source_pattern_ids=["p1", "p2"],
            source_strategy_id="s1",
            related_failure_ids=["f1"],
        )
        assert len(opp.source_pattern_ids) == 2
        assert opp.source_strategy_id == "s1"
        assert len(opp.related_failure_ids) == 1

    def test_unique_ids(self):
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.intelligence_models import GrowthOpportunity
        ids = {GrowthOpportunity().opportunity_id for _ in range(10)}
        assert len(ids) == 10


# ═══════════════════════════════════════════════════════════════
# Test: DecisionAction
# ═══════════════════════════════════════════════════════════════

class TestDecisionAction:
    def test_default_creation(self):
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.intelligence_models import DecisionAction
        action = DecisionAction()
        assert action.action_id != ""
        assert action.action_type == ""
        assert action.order == 1
        assert action.approval_level == "auto"

    def test_full_creation(self):
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.intelligence_models import DecisionAction
        action = DecisionAction(
            action_type="increase_budget",
            target_entity_id="c001",
            target_entity_type="creative",
            params={"budget": 500, "multiplier": 1.5},
            order=2,
            expected_impact={"roas_boost": 0.1},
            approval_level="manual",
        )
        assert action.action_type == "increase_budget"
        assert action.params["budget"] == 500
        assert action.order == 2
        assert action.approval_level == "manual"

    def test_to_dict(self):
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.intelligence_models import DecisionAction
        action = DecisionAction(action_type="scale_winner", target_entity_id="c002")
        d = action.to_dict()
        assert d["action_type"] == "scale_winner"
        assert d["target_entity_id"] == "c002"

    def test_unique_ids(self):
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.intelligence_models import DecisionAction
        ids = {DecisionAction().action_id for _ in range(10)}
        assert len(ids) == 10


# ═══════════════════════════════════════════════════════════════
# Test: GrowthDecision
# ═══════════════════════════════════════════════════════════════

class TestGrowthDecision:
    def test_default_creation(self):
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.intelligence_models import (
            GrowthDecision, DecisionStatus, RiskLevel,
        )
        d = GrowthDecision()
        assert d.decision_id != ""
        assert d.status == DecisionStatus.DRAFT
        assert d.risk_level == RiskLevel.NONE
        assert d.actions == []

    def test_full_creation(self):
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.intelligence_models import (
            GrowthDecision, DecisionAction,
        )
        actions = [
            DecisionAction(action_type="clone_dna", order=1),
            DecisionAction(action_type="increase_budget", order=2),
        ]
        d = GrowthDecision(
            objective="scale_spend",
            selected_strategy_id="s1",
            actions=actions,
            confidence=0.85,
            risk_score=0.1,
            reasoning="Safe to scale based on CTR trend",
        )
        assert d.objective == "scale_spend"
        assert d.action_count == 2
        assert d.confidence == 0.85

    def test_to_dict(self):
        d = _make_decision()
        result = d.to_dict()
        assert result["objective"] == "scale_spend"
        assert result["status"] == "draft"
        assert "actions" in result
        assert "expected_impact" in result

    def test_approve(self):
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.intelligence_models import (
            GrowthDecision, DecisionStatus,
        )
        d = GrowthDecision()
        d.approve()
        assert d.status == DecisionStatus.APPROVED
        assert d.is_approved is True

    def test_reject(self):
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.intelligence_models import (
            GrowthDecision, DecisionStatus,
        )
        d = GrowthDecision()
        d.reject("Too risky")
        assert d.status == DecisionStatus.REJECTED
        assert d.reasoning == "Too risky"

    def test_block(self):
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.intelligence_models import (
            GrowthDecision, DecisionStatus, RiskLevel,
        )
        d = GrowthDecision()
        d.block("Budget scaling before creative validation")
        assert d.status == DecisionStatus.BLOCKED
        assert d.risk_level == RiskLevel.CRITICAL
        assert len(d.failure_warnings) == 1

    def test_mark_executed(self):
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.intelligence_models import (
            GrowthDecision, DecisionStatus,
        )
        d = GrowthDecision()
        d.mark_executed()
        assert d.status == DecisionStatus.EXECUTED
        assert d.executed_at != ""

    def test_compute_risk_level_critical(self):
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.intelligence_models import (
            GrowthDecision, RiskLevel,
        )
        d = GrowthDecision(risk_score=0.85)
        d.compute_risk_level()
        assert d.risk_level == RiskLevel.CRITICAL
        assert d.requires_approval is True

    def test_compute_risk_level_high(self):
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.intelligence_models import (
            GrowthDecision, RiskLevel,
        )
        d = GrowthDecision(risk_score=0.65)
        d.compute_risk_level()
        assert d.risk_level == RiskLevel.HIGH
        assert d.requires_approval is True

    def test_compute_risk_level_medium(self):
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.intelligence_models import (
            GrowthDecision, RiskLevel,
        )
        d = GrowthDecision(risk_score=0.45)
        d.compute_risk_level()
        assert d.risk_level == RiskLevel.MEDIUM

    def test_compute_risk_level_low(self):
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.intelligence_models import (
            GrowthDecision, RiskLevel,
        )
        d = GrowthDecision(risk_score=0.25)
        d.compute_risk_level()
        assert d.risk_level == RiskLevel.LOW

    def test_compute_risk_level_none(self):
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.intelligence_models import (
            GrowthDecision, RiskLevel,
        )
        d = GrowthDecision(risk_score=0.05)
        d.compute_risk_level()
        assert d.risk_level == RiskLevel.NONE

    def test_is_executable(self):
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.intelligence_models import (
            GrowthDecision, DecisionStatus, RiskLevel,
        )
        d = GrowthDecision(status=DecisionStatus.APPROVED, risk_level=RiskLevel.LOW)
        assert d.is_executable is True

        d2 = GrowthDecision(status=DecisionStatus.APPROVED, risk_level=RiskLevel.HIGH, requires_approval=True)
        assert d2.is_executable is False

    def test_is_blocked(self):
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.intelligence_models import (
            GrowthDecision, RiskLevel,
        )
        d = GrowthDecision(risk_level=RiskLevel.CRITICAL, requires_approval=True)
        assert d.is_blocked is True

        d2 = GrowthDecision(risk_level=RiskLevel.LOW, requires_approval=False)
        assert d2.is_blocked is False

    def test_unique_ids(self):
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.intelligence_models import GrowthDecision
        ids = {GrowthDecision().decision_id for _ in range(10)}
        assert len(ids) == 10


# ═══════════════════════════════════════════════════════════════
# Test: DecisionResult
# ═══════════════════════════════════════════════════════════════

class TestDecisionResult:
    def test_default_creation(self):
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.intelligence_models import (
            DecisionResult, DecisionStatus,
        )
        r = DecisionResult()
        assert r.result_id != ""
        assert r.status == DecisionStatus.EXECUTED
        assert r.success is False

    def test_full_creation(self):
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.intelligence_models import (
            DecisionResult, DecisionStatus,
        )
        r = DecisionResult(
            decision_id="d001",
            status=DecisionStatus.EXECUTED,
            success=True,
            metrics_delta={"roas": 0.08, "spend": 100.0},
            executed_at="2026-07-24T10:00:00Z",
        )
        assert r.decision_id == "d001"
        assert r.success is True
        assert r.metrics_delta["roas"] == 0.08

    def test_to_dict(self):
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.intelligence_models import DecisionResult
        r = DecisionResult(decision_id="d001", success=True)
        d = r.to_dict()
        assert d["success"] is True
        assert "actual_metrics" in d

    def test_rollback(self):
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.intelligence_models import DecisionResult
        r = DecisionResult(rollback_performed=True, error_message="Budget exceeded")
        assert r.rollback_performed is True
        assert r.error_message == "Budget exceeded"

    def test_unique_ids(self):
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.intelligence_models import DecisionResult
        ids = {DecisionResult().result_id for _ in range(10)}
        assert len(ids) == 10


# ═══════════════════════════════════════════════════════════════
# Test: DecisionRecord
# ═══════════════════════════════════════════════════════════════

class TestDecisionRecord:
    def test_default_creation(self):
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.intelligence_models import DecisionRecord
        record = DecisionRecord()
        assert record.record_id != ""
        assert record.decision is not None
        assert record.created_at != ""

    def test_full_creation(self):
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.intelligence_models import DecisionRecord
        decision = _make_decision()
        context = _make_context()
        opportunity = _make_opportunity()
        record = DecisionRecord(
            decision=decision,
            context=context,
            opportunity=opportunity,
        )
        assert record.decision.objective == "scale_spend"
        assert record.context.product_id == "p001"
        assert record.opportunity.impact_score == 0.75

    def test_to_dict(self):
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.intelligence_models import DecisionRecord
        record = DecisionRecord(
            decision=_make_decision(),
            context=_make_context(),
            opportunity=_make_opportunity(),
        )
        d = record.to_dict()
        assert d["decision"]["objective"] == "scale_spend"
        assert d["context"]["product_id"] == "p001"
        assert d["opportunity"]["reason"] == "CTR high, ROAS above target, ready to scale"

    def test_with_result(self):
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.intelligence_models import (
            DecisionRecord, DecisionResult,
        )
        result = DecisionResult(decision_id="d001", success=True)
        record = DecisionRecord(result=result)
        d = record.to_dict()
        assert d["result"]["success"] is True

    def test_unique_ids(self):
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.intelligence_models import DecisionRecord
        ids = {DecisionRecord().record_id for _ in range(10)}
        assert len(ids) == 10


# ═══════════════════════════════════════════════════════════════
# Test: Integration - Full Decision Pipeline
# ═══════════════════════════════════════════════════════════════

class TestIntegration:
    """完整决策链路集成测试."""

    def test_full_decision_pipeline(self):
        """模拟完整决策链路: Context → Opportunity → Decision → Execute → Result → Record."""
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.intelligence_models import (
            CurrentMetrics, SignalSummary, MemoryContext, DecisionContext,
            GrowthOpportunity, OpportunityType, OpportunitySource, DecisionPriority,
            ExpectedImpact,
            DecisionAction,
            GrowthDecision, DecisionStatus, RiskLevel,
            DecisionResult,
            DecisionRecord,
        )

        # Step 1: 构建决策上下文
        metrics = CurrentMetrics(
            spend=500.0, revenue=650.0, roas=1.3,
            ctr=0.018, cpi=4.0, impressions=15000, clicks=270,
            installs=70, payers=9, d7_ltv=2.8, payer_rate=0.128,
        )
        signals = SignalSummary(
            active_signals=["creative_fatigue"],
            fatigue_detected=True,
            prediction={"fatigue_probability": 0.82},
            trend="declining",
        )
        memory = MemoryContext(
            matched_patterns=["p_creative_refresh"],
            recommended_strategies=["s_replace_hook"],
            relevant_failures=["f_budget_scale_fatigue"],
            historical_success_rate=0.72,
            total_related_experiences=18,
        )
        context = DecisionContext(
            product_id="p001",
            campaign_id="camp_a",
            creative_id="c_old",
            date="2026-07-24",
            current_metrics=metrics,
            signals=signals,
            memory_context=memory,
            audience_segment="android_puzzle",
        )

        # Step 2: 发现机会
        opportunity = GrowthOpportunity(
            opportunity_type=OpportunityType.CREATIVE_REFRESH,
            source=OpportunitySource.REALITY_INSIGHT,
            product_id="p001",
            campaign_id="camp_a",
            creative_id="c_old",
            impact_score=0.72,
            confidence=0.82,
            urgency=0.75,
            reason="CTR -35%, frequency +40%, fatigue detected",
            recommended_action="replace_hook_dna",
            source_pattern_ids=["p_creative_refresh"],
            source_strategy_id="s_replace_hook",
            related_failure_ids=["f_budget_scale_fatigue"],
        )
        opportunity.compute_priority()
        assert opportunity.priority in {DecisionPriority.HIGH, DecisionPriority.CRITICAL}

        # Step 3: 制定决策
        actions = [
            DecisionAction(
                action_type="generate_dna_variants", order=1,
                params={"count": 5, "gene": "hook"},
            ),
            DecisionAction(
                action_type="upload_creative", order=2,
                params={"platform": "meta_ads"},
            ),
            DecisionAction(
                action_type="set_budget", order=3,
                params={"daily_budget": 500, "campaign_id": "camp_a"},
                approval_level="auto",
            ),
        ]
        expected = ExpectedImpact(
            roas_change=0.18, spend_change=500.0,
            revenue_change=650.0, confidence=0.82,
        )
        decision = GrowthDecision(
            context_id=context.context_id,
            opportunity_id=opportunity.opportunity_id,
            objective="recover_roas",
            selected_strategy_id="s_replace_hook",
            actions=actions,
            confidence=0.82,
            risk_score=0.15,
            expected_impact=expected,
            reasoning="Replace fatigued creative with fresh DNA variants, "
                       "based on historical 72% success pattern",
        )
        decision.compute_risk_level()
        assert decision.risk_level == RiskLevel.NONE
        assert decision.action_count == 3

        # Step 4: 审批
        decision.approve()
        assert decision.is_approved is True
        assert decision.is_executable is True

        # Step 5: 执行
        decision.mark_executed()
        assert decision.status == DecisionStatus.EXECUTED

        # Step 6: 记录结果
        result_metrics = CurrentMetrics(
            spend=500.0, revenue=780.0, roas=1.56,
            ctr=0.028, cpi=3.2, impressions=12000, clicks=336,
            installs=95, payers=14, d7_ltv=3.1, payer_rate=0.147,
        )
        result = DecisionResult(
            decision_id=decision.decision_id,
            success=True,
            actual_metrics=result_metrics,
            metrics_delta={"roas": 0.26, "ctr": 0.01, "cpi": -0.8},
        )

        # Step 7: 完整记录
        record = DecisionRecord(
            decision=decision,
            result=result,
            context=context,
            opportunity=opportunity,
        )
        d = record.to_dict()
        assert d["decision"]["objective"] == "recover_roas"
        assert d["result"]["success"] is True
        assert d["context"]["product_id"] == "p001"
        assert d["opportunity"]["opportunity_type"] == "creative_refresh"

    def test_risk_blocked_pipeline(self):
        """高风险决策被拦截的链路."""
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.intelligence_models import (
            GrowthDecision, DecisionStatus, RiskLevel,
        )

        decision = GrowthDecision(
            objective="scale_spend",
            confidence=0.6,
            risk_score=0.9,
            reasoning="Attempting to scale despite fatigue signals",
        )
        decision.compute_risk_level()
        assert decision.risk_level == RiskLevel.CRITICAL
        assert decision.is_blocked is True

        # 应该被拦截
        decision.block("Budget scaling before creative validation has 80% failure rate")
        assert decision.status == DecisionStatus.BLOCKED
        assert len(decision.failure_warnings) == 1

    def test_low_risk_auto_pipeline(self):
        """低风险自动执行链路."""
        from market_ops.creative_vision_runtime.growth_runtime.intelligence.intelligence_models import (
            GrowthDecision, DecisionStatus, RiskLevel, DecisionAction,
        )

        decision = GrowthDecision(
            objective="optimize_budget",
            confidence=0.9,
            risk_score=0.05,
            actions=[
                DecisionAction(action_type="adjust_bid", order=1, approval_level="auto"),
            ],
        )
        decision.compute_risk_level()
        assert decision.risk_level == RiskLevel.NONE

        decision.approve()
        assert decision.is_executable is True
        decision.mark_executed()
        assert decision.status == DecisionStatus.EXECUTED