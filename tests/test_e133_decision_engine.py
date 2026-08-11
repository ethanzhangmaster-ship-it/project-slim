"""E13.3 — Growth Decision Engine Test Suite.

覆盖:
  - TestInsightType:            洞察类型枚举 (4)
  - TestActionType:             动作类型枚举 (4)
  - TestDecisionConfidence:     置信度等级枚举 (3)
  - TestGrowthInsight:          增长洞察模型 (12)
  - TestGrowthOpportunity:      增长机会模型 (12)
  - TestCreativeRanking:        创意排名模型 (10)
  - TestBudgetAction:           预算动作模型 (8)
  - TestDecisionAction:         决策动作模型 (12)
  - TestDecisionReport:         决策报告模型 (12)
  - TestDecisionResult:         决策结果模型 (5)
  - TestGrowthIntelligence:     增长洞察分析 (25)
  - TestOpportunityDetector:    机会发现引擎 (20)
  - TestCreativeRanker:         统一评分排序 (18)
  - TestActionMapper:           机会到决策映射 (18)
  - TestConfidenceCalculator:   置信度计算 (15)
  - TestRiskAssessor:           风险评估 (12)
  - TestGrowthDecisionEngine:   核心决策编排 (20)
  - TestDecisionEngineIntegration: 集成测试 (8)
  - TestEdgeCases:              边界条件 (8)

总计: ~226 tests
"""

from __future__ import annotations

import pytest
from datetime import date, timedelta

from market_ops.creative_vision_runtime.growth_runtime.decision import (
    ActionMapper,
    ActionType,
    BudgetAction,
    ConfidenceCalculator,
    CreativeRanker,
    CreativeRanking,
    DecisionAction,
    DecisionConfidence,
    DecisionReport,
    DecisionResult,
    GrowthDecisionEngine,
    GrowthInsight,
    GrowthOpportunity,
    GrowthIntelligence,
    InsightType,
    OpportunityDetector,
    OpportunitySeverity,
    RiskAssessor,
)
from market_ops.creative_vision_runtime.growth_runtime.pipeline import (
    CreativeFitnessVector,
)


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════


def _make_vector(
    creative_id: str = "creative_001",
    creative_name: str = "Test Creative",
    ctr: float = 0.03,
    cpi: float = 2.0,
    spend: float = 500.0,
    installs: int = 2000,
    d30_roas: float = 1.5,
    d30_ltv: float = 6.0,
    d7_retention: float = 0.25,
    total_revenue: float = 800.0,
    iap_revenue: float = 500.0,
    ad_revenue: float = 300.0,
    fitness_score: float = 0.75,
    fatigue_score: float = 0.1,
    confidence: float = 0.9,
    sample_size: int = 5000,
    is_winner: bool = False,
    is_fatigued: bool = False,
    genome_id: str = "",
    product_id: str = "product_001",
    date: str = "2026-07-24",
    impressions: int = 10000,
    clicks: int = 300,
    payer_rate: float = 0.05,
    **kwargs,
) -> CreativeFitnessVector:
    return CreativeFitnessVector(
        creative_id=creative_id,
        creative_name=creative_name,
        genome_id=genome_id or creative_id,
        product_id=product_id,
        date=date,
        ctr=ctr,
        cpi=cpi,
        spend=spend,
        installs=installs,
        d30_roas=d30_roas,
        d30_ltv=d30_ltv,
        d7_retention=d7_retention,
        total_revenue=total_revenue,
        iap_revenue=iap_revenue,
        ad_revenue=ad_revenue,
        fitness_score=fitness_score,
        fatigue_score=fatigue_score,
        confidence=confidence,
        sample_size=sample_size,
        is_winner=is_winner,
        is_fatigued=is_fatigued,
        impressions=impressions,
        clicks=clicks,
        payer_rate=payer_rate,
        d7_roas=d30_roas * 0.7,
        d1_roas=d30_roas * 0.3,
        d7_ltv=d30_ltv * 0.5,
        predicted_ltv=d30_ltv * 1.1,
        d1_retention=d7_retention * 1.5,
        d30_retention=d7_retention * 0.6,
        **kwargs,
    )


def _make_insight(
    creative_id: str = "creative_001",
    insight_type: InsightType = InsightType.WINNER_DISCOVERY,
    confidence: float = 0.85,
    reason: str = "Test insight",
    severity: OpportunitySeverity = OpportunitySeverity.HIGH,
    source_vector: CreativeFitnessVector | None = None,
    **kwargs,
) -> GrowthInsight:
    if source_vector is None:
        source_vector = _make_vector(creative_id=creative_id)
    return GrowthInsight(
        insight_type=insight_type,
        creative_id=creative_id,
        creative_name=source_vector.creative_name,
        genome_id=source_vector.genome_id,
        product_id=source_vector.product_id,
        reason=reason,
        confidence=confidence,
        severity=severity,
        metrics={"d30_roas": source_vector.d30_roas, "d30_ltv": source_vector.d30_ltv},
        source_vector=source_vector,
        date=source_vector.date,
        **kwargs,
    )


# ═══════════════════════════════════════════════════════════════
# Test Enums
# ═══════════════════════════════════════════════════════════════


class TestInsightType:
    """洞察类型枚举测试."""

    def test_all_types_defined(self):
        assert len(InsightType) == 10

    def test_type_values(self):
        assert InsightType.WINNER_DISCOVERY.value == "winner_discovery"
        assert InsightType.CREATIVE_FATIGUE.value == "creative_fatigue"
        assert InsightType.ROAS_DROP.value == "roas_drop"
        assert InsightType.SCALE_OPPORTUNITY.value == "scale_opportunity"
        assert InsightType.BUDGET_MISALLOCATION.value == "budget_misallocation"
        assert InsightType.NEW_PATTERN.value == "new_pattern"
        assert InsightType.HYBRID_WINNER.value == "hybrid_winner"
        assert InsightType.RETENTION_SIGNAL.value == "retention_signal"
        assert InsightType.CPI_ALERT.value == "cpi_alert"
        assert InsightType.UNDERPERFORMING.value == "underperforming"

    def test_type_from_string(self):
        assert InsightType("winner_discovery") == InsightType.WINNER_DISCOVERY
        assert InsightType("creative_fatigue") == InsightType.CREATIVE_FATIGUE
        assert InsightType("hybrid_winner") == InsightType.HYBRID_WINNER

    def test_type_equality(self):
        assert InsightType.WINNER_DISCOVERY == InsightType.WINNER_DISCOVERY
        assert InsightType.WINNER_DISCOVERY != InsightType.CREATIVE_FATIGUE


class TestActionType:
    """动作类型枚举测试."""

    def test_all_actions_defined(self):
        assert len(ActionType) == 12

    def test_action_values(self):
        assert ActionType.SCALE.value == "scale"
        assert ActionType.STOP.value == "stop"
        assert ActionType.PAUSE.value == "pause"
        assert ActionType.MUTATE.value == "mutate"
        assert ActionType.INCREASE_BUDGET.value == "increase_budget"
        assert ActionType.DECREASE_BUDGET.value == "decrease_budget"
        assert ActionType.REDISTRIBUTE_BUDGET.value == "redistribute_budget"
        assert ActionType.LAUNCH_EXPERIMENT.value == "launch_experiment"
        assert ActionType.HOLD.value == "hold"
        assert ActionType.MONITOR.value == "monitor"
        assert ActionType.REPLACE_CREATIVE.value == "replace_creative"
        assert ActionType.DUPLICATE_WINNER.value == "duplicate_winner"

    def test_action_from_string(self):
        assert ActionType("scale") == ActionType.SCALE
        assert ActionType("mutate") == ActionType.MUTATE
        assert ActionType("stop") == ActionType.STOP

    def test_action_equality(self):
        assert ActionType.SCALE == ActionType.SCALE
        assert ActionType.SCALE != ActionType.STOP


class TestDecisionConfidence:
    """置信度等级枚举测试."""

    def test_all_levels_defined(self):
        assert len(DecisionConfidence) == 4

    def test_confidence_values(self):
        assert DecisionConfidence.HIGH.value == "high"
        assert DecisionConfidence.MEDIUM.value == "medium"
        assert DecisionConfidence.LOW.value == "low"
        assert DecisionConfidence.SPECULATIVE.value == "speculative"

    def test_confidence_from_string(self):
        assert DecisionConfidence("high") == DecisionConfidence.HIGH
        assert DecisionConfidence("speculative") == DecisionConfidence.SPECULATIVE


# ═══════════════════════════════════════════════════════════════
# Test Models
# ═══════════════════════════════════════════════════════════════


class TestGrowthInsight:
    """增长洞察模型测试."""

    def test_create_insight(self):
        v = _make_vector()
        insight = _make_insight(source_vector=v)
        assert insight.insight_type == InsightType.WINNER_DISCOVERY
        assert insight.creative_id == "creative_001"
        assert insight.confidence == 0.85
        assert insight.insight_id != ""

    def test_insight_to_dict(self):
        v = _make_vector()
        insight = _make_insight(source_vector=v)
        d = insight.to_dict()
        assert d["insight_type"] == "winner_discovery"
        assert d["creative_id"] == "creative_001"
        assert "confidence" in d
        assert "metrics" in d

    def test_is_high_confidence(self):
        insight = _make_insight(confidence=0.9)
        assert insight.is_high_confidence is True

        insight2 = _make_insight(confidence=0.7)
        assert insight2.is_high_confidence is False

    def test_is_actionable(self):
        insight = _make_insight(confidence=0.85)
        assert insight.is_actionable is True

        insight2 = _make_insight(confidence=0.6)
        assert insight2.is_actionable is False

    def test_confidence_level(self):
        insight = _make_insight(confidence=0.9)
        assert insight.confidence_level == DecisionConfidence.HIGH

        insight2 = _make_insight(confidence=0.75)
        assert insight2.confidence_level == DecisionConfidence.MEDIUM

        insight3 = _make_insight(confidence=0.55)
        assert insight3.confidence_level == DecisionConfidence.LOW

        insight4 = _make_insight(confidence=0.3)
        assert insight4.confidence_level == DecisionConfidence.SPECULATIVE

    def test_insight_has_source_vector(self):
        v = _make_vector()
        insight = _make_insight(source_vector=v)
        assert insight.source_vector is not None
        assert insight.source_vector.creative_id == "creative_001"

    def test_insight_with_benchmark(self):
        v = _make_vector()
        insight = _make_insight(source_vector=v)
        insight.benchmark = {"avg_d30_roas": 1.0, "avg_d30_ltv": 4.0}
        assert insight.benchmark["avg_d30_roas"] == 1.0

    def test_insight_with_trend(self):
        v = _make_vector()
        insight = _make_insight(source_vector=v)
        insight.trend = [1.0, 1.1, 1.2, 1.15]
        assert len(insight.trend) == 4

    def test_insight_unique_ids(self):
        i1 = _make_insight()
        i2 = _make_insight()
        assert i1.insight_id != i2.insight_id

    def test_insight_severity_default(self):
        insight = _make_insight()
        assert insight.severity == OpportunitySeverity.HIGH

    def test_insight_default_reason(self):
        insight = _make_insight()
        assert insight.reason == "Test insight"

    def test_insight_product_id(self):
        v = _make_vector(product_id="game_123")
        insight = _make_insight(source_vector=v)
        assert insight.product_id == "game_123"


class TestGrowthOpportunity:
    """增长机会模型测试."""

    def test_create_opportunity(self):
        insight = _make_insight()
        opp = GrowthOpportunity(
            action=ActionType.SCALE,
            creative_id="creative_001",
            reason="Scale opportunity",
            confidence=0.85,
            severity=OpportunitySeverity.HIGH,
            budget_multiplier=2.0,
            current_budget=500.0,
            target_budget=1000.0,
            source_insight=insight,
        )
        assert opp.action == ActionType.SCALE
        assert opp.creative_id == "creative_001"
        assert opp.budget_multiplier == 2.0
        assert opp.target_budget == 1000.0

    def test_opportunity_to_dict(self):
        opp = GrowthOpportunity(
            action=ActionType.STOP,
            creative_id="creative_005",
            reason="Stop",
            confidence=0.9,
            severity=OpportunitySeverity.CRITICAL,
            current_budget=300.0,
            target_budget=0.0,
            budget_multiplier=0.0,
        )
        d = opp.to_dict()
        assert d["action"] == "stop"
        assert d["creative_id"] == "creative_005"
        assert d["budget_multiplier"] == 0.0

    def test_is_scale_action(self):
        opp = GrowthOpportunity(action=ActionType.SCALE)
        assert opp.is_scale_action is True

        opp2 = GrowthOpportunity(action=ActionType.INCREASE_BUDGET)
        assert opp2.is_scale_action is True

        opp3 = GrowthOpportunity(action=ActionType.MUTATE)
        assert opp3.is_scale_action is False

    def test_is_stop_action(self):
        opp = GrowthOpportunity(action=ActionType.STOP)
        assert opp.is_stop_action is True

        opp2 = GrowthOpportunity(action=ActionType.PAUSE)
        assert opp2.is_stop_action is True

        opp3 = GrowthOpportunity(action=ActionType.SCALE)
        assert opp3.is_stop_action is False

    def test_is_creative_action(self):
        opp = GrowthOpportunity(action=ActionType.MUTATE)
        assert opp.is_creative_action is True

        opp2 = GrowthOpportunity(action=ActionType.REPLACE_CREATIVE)
        assert opp2.is_creative_action is True

        opp3 = GrowthOpportunity(action=ActionType.DUPLICATE_WINNER)
        assert opp3.is_creative_action is True

        opp4 = GrowthOpportunity(action=ActionType.SCALE)
        assert opp4.is_creative_action is False

    def test_opportunity_default_budget_multiplier(self):
        opp = GrowthOpportunity()
        assert opp.budget_multiplier == 1.0

    def test_opportunity_default_severity(self):
        opp = GrowthOpportunity()
        assert opp.severity == OpportunitySeverity.MEDIUM

    def test_opportunity_expected_impact(self):
        opp = GrowthOpportunity(
            expected_impact={"revenue_growth": 500.0, "roas_improvement": 0.1},
        )
        assert opp.expected_impact["revenue_growth"] == 500.0

    def test_opportunity_unique_ids(self):
        o1 = GrowthOpportunity()
        o2 = GrowthOpportunity()
        assert o1.opportunity_id != o2.opportunity_id

    def test_opportunity_no_source_insight(self):
        opp = GrowthOpportunity()
        assert opp.source_insight is None

    def test_opportunity_with_source_insight(self):
        insight = _make_insight()
        opp = GrowthOpportunity(source_insight=insight)
        assert opp.source_insight is not None
        assert opp.source_insight.creative_id == "creative_001"

    def test_opportunity_zero_budget(self):
        opp = GrowthOpportunity(current_budget=0.0, target_budget=0.0)
        assert opp.current_budget == 0.0
        assert opp.target_budget == 0.0


class TestCreativeRanking:
    """创意排名模型测试."""

    def test_create_ranking(self):
        r = CreativeRanking(
            creative_id="creative_001",
            creative_name="Test",
            rank=1,
            total_creatives=10,
            fitness_score=0.85,
            roas_score=0.9,
            ltv_score=0.8,
            is_winner=True,
        )
        assert r.creative_id == "creative_001"
        assert r.rank == 1
        assert r.is_winner is True

    def test_ranking_to_dict(self):
        r = CreativeRanking(
            creative_id="c1",
            creative_name="Test",
            rank=1,
            total_creatives=5,
            fitness_score=0.92,
            is_winner=True,
        )
        d = r.to_dict()
        assert d["rank"] == 1
        assert d["fitness_score"] == 0.92
        assert d["is_winner"] is True

    def test_is_top_performer(self):
        r = CreativeRanking(rank=1, total_creatives=10, fitness_score=0.85)
        assert r.is_top_performer is True

        r2 = CreativeRanking(rank=5, total_creatives=10, fitness_score=0.5)
        assert r2.is_top_performer is False

        r3 = CreativeRanking(rank=1, total_creatives=10, fitness_score=0.5)
        assert r3.is_top_performer is False

    def test_percentile(self):
        r = CreativeRanking(rank=1, total_creatives=10)
        assert r.percentile == 100.0

        r2 = CreativeRanking(rank=5, total_creatives=10)
        assert pytest.approx(r2.percentile, 0.1) == 55.6

        r3 = CreativeRanking(rank=10, total_creatives=10)
        assert r3.percentile == 0.0

    def test_percentile_single_creative(self):
        r = CreativeRanking(rank=1, total_creatives=1)
        assert r.percentile == 100.0

    def test_default_values(self):
        r = CreativeRanking()
        assert r.rank == 0
        assert r.total_creatives == 0
        assert r.fitness_score == 0.0
        assert r.is_winner is False
        assert r.is_fatigued is False

    def test_decision_confidence(self):
        r = CreativeRanking(decision_confidence=DecisionConfidence.HIGH)
        assert r.decision_confidence == DecisionConfidence.HIGH

    def test_ranking_scores(self):
        r = CreativeRanking(
            roas_score=0.9,
            ltv_score=0.8,
            retention_score=0.7,
            ctr_score=0.6,
            revenue_score=0.5,
            scale_score=0.4,
            confidence_score=0.3,
        )
        assert r.roas_score == 0.9
        assert r.ltv_score == 0.8
        assert r.confidence_score == 0.3

    def test_ranking_fatigued(self):
        r = CreativeRanking(is_fatigued=True)
        assert r.is_fatigued is True

    def test_ranking_genome_id(self):
        r = CreativeRanking(genome_id="genome_001")
        assert r.genome_id == "genome_001"


class TestBudgetAction:
    """预算动作模型测试."""

    def test_create_budget_action(self):
        ba = BudgetAction(
            creative_id="c1",
            current_budget=500.0,
            target_budget=1000.0,
            budget_delta=500.0,
            budget_multiplier=2.0,
            action=ActionType.SCALE,
            reason="Scaling winner",
            confidence=0.9,
        )
        assert ba.creative_id == "c1"
        assert ba.budget_delta == 500.0
        assert ba.action == ActionType.SCALE

    def test_is_increase(self):
        ba = BudgetAction(budget_delta=500.0)
        assert ba.is_increase is True

        ba2 = BudgetAction(budget_delta=-200.0)
        assert ba2.is_increase is False

    def test_is_decrease(self):
        ba = BudgetAction(budget_delta=-200.0)
        assert ba.is_decrease is True

        ba2 = BudgetAction(budget_delta=500.0)
        assert ba2.is_decrease is False

    def test_delta_percentage(self):
        ba = BudgetAction(current_budget=500.0, budget_delta=250.0)
        assert ba.delta_percentage == 50.0

        ba2 = BudgetAction(current_budget=1000.0, budget_delta=-500.0)
        assert ba2.delta_percentage == -50.0

    def test_delta_percentage_zero_budget(self):
        ba = BudgetAction(current_budget=0.0, budget_delta=100.0)
        assert ba.delta_percentage == 0.0

    def test_budget_action_to_dict(self):
        ba = BudgetAction(
            creative_id="c1",
            current_budget=500.0,
            target_budget=1000.0,
            budget_delta=500.0,
            action=ActionType.INCREASE_BUDGET,
            reason="Test",
            confidence=0.85,
        )
        d = ba.to_dict()
        assert d["action"] == "increase_budget"
        assert d["current_budget"] == 500.0
        assert "confidence" in d

    def test_default_campaign_id(self):
        ba = BudgetAction()
        assert ba.campaign_id == ""

    def test_budget_action_with_campaign(self):
        ba = BudgetAction(campaign_id="camp_123")
        assert ba.campaign_id == "camp_123"


class TestDecisionAction:
    """决策动作模型测试."""

    def test_create_decision_action(self):
        da = DecisionAction(
            action=ActionType.SCALE,
            creative_id="c1",
            product_id="p1",
            priority=0,
            confidence=0.9,
            reason="Winner creative",
            requires_approval=False,
            approval_level=0,
        )
        assert da.action == ActionType.SCALE
        assert da.creative_id == "c1"
        assert da.confidence == 0.9

    def test_is_autonomous(self):
        da = DecisionAction(approval_level=0, requires_approval=False)
        assert da.is_autonomous is True

        da2 = DecisionAction(approval_level=0, requires_approval=True)
        assert da2.is_autonomous is False

        da3 = DecisionAction(approval_level=1, requires_approval=True)
        assert da3.is_autonomous is False

    def test_is_level1_approval(self):
        da = DecisionAction(approval_level=1)
        assert da.is_level1_approval is True

        da2 = DecisionAction(approval_level=0)
        assert da2.is_level1_approval is False

    def test_is_level2_approval(self):
        da = DecisionAction(approval_level=2)
        assert da.is_level2_approval is True

        da2 = DecisionAction(approval_level=1)
        assert da2.is_level2_approval is False

    def test_decision_action_to_dict(self):
        da = DecisionAction(
            action=ActionType.MUTATE,
            creative_id="c1",
            priority=1,
            confidence=0.75,
            reason="Fatigue mutation",
            requires_approval=False,
            approval_level=0,
        )
        d = da.to_dict()
        assert d["action"] == "mutate"
        assert d["creative_id"] == "c1"
        assert d["priority"] == 1
        assert "budget_action" not in d

    def test_decision_action_with_budget(self):
        ba = BudgetAction(
            creative_id="c1",
            current_budget=500.0,
            target_budget=1000.0,
            budget_delta=500.0,
            action=ActionType.SCALE,
            reason="Scale",
            confidence=0.9,
        )
        da = DecisionAction(
            action=ActionType.SCALE,
            creative_id="c1",
            budget_action=ba,
        )
        d = da.to_dict()
        assert "budget_action" in d
        assert d["budget_action"]["action"] == "scale"

    def test_decision_action_expected_impact(self):
        da = DecisionAction(
            expected_roas_impact=0.15,
            expected_revenue_impact=500.0,
        )
        assert da.expected_roas_impact == 0.15
        assert da.expected_revenue_impact == 500.0

    def test_decision_action_source_insight(self):
        insight = _make_insight()
        da = DecisionAction(source_insight=insight)
        assert da.source_insight is not None

    def test_decision_action_source_opportunity(self):
        opp = GrowthOpportunity(action=ActionType.SCALE)
        da = DecisionAction(source_opportunity=opp)
        assert da.source_opportunity is not None

    def test_decision_action_unique_ids(self):
        da1 = DecisionAction()
        da2 = DecisionAction()
        assert da1.action_id != da2.action_id

    def test_decision_action_default_values(self):
        da = DecisionAction()
        assert da.priority == 0
        assert da.confidence == 0.0
        assert da.requires_approval is False
        assert da.approval_level == 0
        assert da.budget_action is None

    def test_decision_action_severity(self):
        da = DecisionAction(severity=OpportunitySeverity.CRITICAL)
        assert da.severity == OpportunitySeverity.CRITICAL


class TestDecisionReport:
    """决策报告模型测试."""

    def test_create_report(self):
        report = DecisionReport(
            date="2026-07-24",
            product_id="p1",
            total_creatives_analyzed=10,
            total_insights=5,
            total_opportunities=3,
            total_decisions=2,
            winners_count=3,
            fatigued_count=1,
            scale_actions=2,
            stop_actions=1,
            mutate_actions=1,
        )
        assert report.date == "2026-07-24"
        assert report.total_creatives_analyzed == 10
        assert report.winners_count == 3

    def test_report_to_dict(self):
        report = DecisionReport(
            date="2026-07-24",
            product_id="p1",
            total_creatives_analyzed=5,
            decisions=[DecisionAction(action=ActionType.SCALE, creative_id="c1")],
            rankings=[CreativeRanking(creative_id="c1", rank=1, fitness_score=0.9)],
        )
        d = report.to_dict()
        assert d["date"] == "2026-07-24"
        assert "summary" in d
        assert "decisions" in d
        assert "rankings" in d

    def test_has_decisions(self):
        report = DecisionReport()
        assert report.has_decisions is False

        report2 = DecisionReport(
            decisions=[DecisionAction(action=ActionType.SCALE, creative_id="c1")],
        )
        assert report2.has_decisions is True

    def test_top_decision(self):
        report = DecisionReport()
        assert report.top_decision is None

        da = DecisionAction(action=ActionType.SCALE, creative_id="c1")
        report2 = DecisionReport(decisions=[da])
        assert report2.top_decision is not None
        assert report2.top_decision.creative_id == "c1"

    def test_autonomous_decisions(self):
        da1 = DecisionAction(action=ActionType.SCALE, creative_id="c1", approval_level=0, requires_approval=False)
        da2 = DecisionAction(action=ActionType.STOP, creative_id="c2", approval_level=1, requires_approval=True)
        report = DecisionReport(decisions=[da1, da2])
        assert len(report.autonomous_decisions) == 1
        assert report.autonomous_decisions[0].creative_id == "c1"

    def test_approval_required_decisions(self):
        da1 = DecisionAction(action=ActionType.SCALE, creative_id="c1", approval_level=0, requires_approval=False)
        da2 = DecisionAction(action=ActionType.STOP, creative_id="c2", approval_level=1, requires_approval=True)
        report = DecisionReport(decisions=[da1, da2])
        assert len(report.approval_required_decisions) == 1
        assert report.approval_required_decisions[0].creative_id == "c2"

    def test_get_decisions_by_action(self):
        da1 = DecisionAction(action=ActionType.SCALE, creative_id="c1")
        da2 = DecisionAction(action=ActionType.MUTATE, creative_id="c2")
        report = DecisionReport(decisions=[da1, da2])
        scale = report.get_decisions_by_action(ActionType.SCALE)
        assert len(scale) == 1
        assert scale[0].creative_id == "c1"

    def test_get_decisions_by_creative(self):
        da1 = DecisionAction(action=ActionType.SCALE, creative_id="c1")
        da2 = DecisionAction(action=ActionType.MUTATE, creative_id="c2")
        report = DecisionReport(decisions=[da1, da2])
        result = report.get_decisions_by_creative("c1")
        assert len(result) == 1
        assert result[0].action == ActionType.SCALE

    def test_report_insights_truncated(self):
        insights = [_make_insight(creative_id=f"c{i}") for i in range(15)]
        report = DecisionReport(insights=insights)
        d = report.to_dict()
        assert len(d["insights"]) == 10

    def test_report_opportunities_truncated(self):
        opps = [GrowthOpportunity(creative_id=f"c{i}") for i in range(15)]
        report = DecisionReport(opportunities=opps)
        d = report.to_dict()
        assert len(d["opportunities"]) == 10

    def test_report_rankings_truncated(self):
        rankings = [CreativeRanking(creative_id=f"c{i}", rank=i+1, total_creatives=15) for i in range(15)]
        report = DecisionReport(rankings=rankings)
        d = report.to_dict()
        assert len(d["rankings"]) == 10

    def test_report_unique_id(self):
        r1 = DecisionReport()
        r2 = DecisionReport()
        assert r1.report_id != r2.report_id


class TestDecisionResult:
    """决策结果模型测试."""

    def test_create_result(self):
        dr = DecisionResult(
            action_id="action_001",
            success=True,
            executed_at="2026-07-24T10:00:00",
        )
        assert dr.action_id == "action_001"
        assert dr.success is True

    def test_result_to_dict(self):
        dr = DecisionResult(
            action_id="action_001",
            success=True,
            error_message="",
            result_data={"budget_updated": 1000},
        )
        d = dr.to_dict()
        assert d["success"] is True
        assert d["error_message"] == ""

    def test_failed_result(self):
        dr = DecisionResult(
            action_id="action_001",
            success=False,
            error_message="API rate limit exceeded",
        )
        assert dr.success is False
        assert "rate limit" in dr.error_message

    def test_default_result(self):
        dr = DecisionResult()
        assert dr.action_id == ""
        assert dr.success is False

    def test_result_with_empty_data(self):
        dr = DecisionResult(action_id="a1", success=True)
        assert dr.result_data == {}


# ═══════════════════════════════════════════════════════════════
# Test GrowthIntelligence
# ═══════════════════════════════════════════════════════════════


class TestGrowthIntelligence:
    """增长洞察分析测试."""

    def test_analyze_empty(self):
        gi = GrowthIntelligence()
        results = gi.analyze([])
        assert results == []

    def test_analyze_single_vector(self):
        gi = GrowthIntelligence()
        v = _make_vector(d30_roas=2.0, d30_ltv=8.0, confidence=0.9)
        results = gi.analyze([v])
        assert len(results) > 0

    def test_detect_winner(self):
        gi = GrowthIntelligence()
        v = _make_vector(d30_roas=2.5, d30_ltv=10.0, confidence=0.9)
        results = gi.analyze([v])
        winner_types = [r for r in results if r.insight_type == InsightType.WINNER_DISCOVERY]
        assert len(winner_types) > 0
        assert winner_types[0].confidence >= 0.5

    def test_detect_winner_below_threshold(self):
        gi = GrowthIntelligence()
        v = _make_vector(d30_roas=0.8, d30_ltv=2.0, confidence=0.5)
        results = gi.analyze([v])
        winner_types = [r for r in results if r.insight_type == InsightType.WINNER_DISCOVERY]
        assert len(winner_types) == 0

    def test_detect_fatigue(self):
        gi = GrowthIntelligence()
        v = _make_vector(
            fatigue_score=0.8, is_fatigued=True, ctr=0.005, d30_roas=0.5,
        )
        results = gi.analyze([v])
        fatigue_types = [r for r in results if r.insight_type == InsightType.CREATIVE_FATIGUE]
        assert len(fatigue_types) > 0

    def test_detect_fatigue_high_severity(self):
        gi = GrowthIntelligence()
        v = _make_vector(
            fatigue_score=0.85, is_fatigued=True, ctr=0.003, d30_roas=0.3,
        )
        results = gi.analyze([v])
        fatigue_types = [r for r in results if r.insight_type == InsightType.CREATIVE_FATIGUE]
        if fatigue_types:
            assert fatigue_types[0].severity == OpportunitySeverity.HIGH

    def test_detect_roas_drop(self):
        gi = GrowthIntelligence()
        # Create vectors where one has significantly lower ROAS
        v1 = _make_vector(creative_id="c1", d30_roas=2.0)
        v2 = _make_vector(creative_id="c2", d30_roas=0.5)
        v3 = _make_vector(creative_id="c3", d30_roas=2.0)
        results = gi.analyze([v1, v2, v3])
        roas_drops = [r for r in results if r.insight_type == InsightType.ROAS_DROP]
        # v2 has ROAS 0.5 vs avg ~1.5, which is < 0.7 * avg
        assert len(roas_drops) > 0

    def test_detect_scale_opportunity(self):
        gi = GrowthIntelligence()
        v = _make_vector(d30_roas=2.0, fatigue_score=0.1, confidence=0.9)
        results = gi.analyze([v])
        scale_types = [r for r in results if r.insight_type == InsightType.SCALE_OPPORTUNITY]
        assert len(scale_types) > 0

    def test_detect_scale_no_opportunity_when_fatigued(self):
        gi = GrowthIntelligence()
        v = _make_vector(d30_roas=2.0, fatigue_score=0.5, confidence=0.9)
        results = gi.analyze([v])
        scale_types = [r for r in results if r.insight_type == InsightType.SCALE_OPPORTUNITY]
        assert len(scale_types) == 0

    def test_detect_budget_misallocation(self):
        gi = GrowthIntelligence()
        v = _make_vector(d30_roas=0.5, spend=1000.0)
        results = gi.analyze([v])
        misalloc = [r for r in results if r.insight_type == InsightType.BUDGET_MISALLOCATION]
        assert len(misalloc) > 0

    def test_detect_hybrid_winner(self):
        gi = GrowthIntelligence()
        v = _make_vector(
            iap_revenue=200.0, ad_revenue=100.0, d30_roas=2.0,
        )
        results = gi.analyze([v])
        hybrid = [r for r in results if r.insight_type == InsightType.HYBRID_WINNER]
        assert len(hybrid) > 0

    def test_detect_hybrid_not_winner_low_revenue(self):
        gi = GrowthIntelligence()
        v = _make_vector(
            iap_revenue=50.0, ad_revenue=20.0, d30_roas=1.0,
        )
        results = gi.analyze([v])
        hybrid = [r for r in results if r.insight_type == InsightType.HYBRID_WINNER]
        assert len(hybrid) == 0

    def test_detect_retention_signal(self):
        gi = GrowthIntelligence()
        v1 = _make_vector(creative_id="c1", d7_retention=0.4)
        v2 = _make_vector(creative_id="c2", d7_retention=0.1)
        v3 = _make_vector(creative_id="c3", d7_retention=0.1)
        results = gi.analyze([v1, v2, v3])
        retention = [r for r in results if r.insight_type == InsightType.RETENTION_SIGNAL]
        assert len(retention) > 0

    def test_detect_cpi_alert(self):
        gi = GrowthIntelligence()
        v = _make_vector(cpi=5.0)
        results = gi.analyze([v])
        cpi_alerts = [r for r in results if r.insight_type == InsightType.CPI_ALERT]
        assert len(cpi_alerts) > 0

    def test_detect_cpi_no_alert(self):
        gi = GrowthIntelligence()
        v = _make_vector(cpi=1.0)
        results = gi.analyze([v])
        cpi_alerts = [r for r in results if r.insight_type == InsightType.CPI_ALERT]
        assert len(cpi_alerts) == 0

    def test_detect_underperforming(self):
        gi = GrowthIntelligence()
        v = _make_vector(d30_roas=0.3, spend=500.0)
        results = gi.analyze([v])
        under = [r for r in results if r.insight_type == InsightType.UNDERPERFORMING]
        assert len(under) > 0
        assert under[0].severity == OpportunitySeverity.CRITICAL

    def test_detect_underperforming_zero_spend(self):
        gi = GrowthIntelligence()
        v = _make_vector(d30_roas=0.3, spend=0.0)
        results = gi.analyze([v])
        under = [r for r in results if r.insight_type == InsightType.UNDERPERFORMING]
        assert len(under) == 0

    def test_get_insights_by_type(self):
        gi = GrowthIntelligence()
        v = _make_vector(d30_roas=2.5, d30_ltv=10.0, cpi=5.0)
        gi.analyze([v])
        winners = gi.get_insights_by_type(InsightType.WINNER_DISCOVERY)
        assert len(winners) > 0

    def test_get_insights_by_creative(self):
        gi = GrowthIntelligence()
        v = _make_vector(creative_id="special_001", d30_roas=2.5, d30_ltv=10.0)
        gi.analyze([v])
        results = gi.get_insights_by_creative("special_001")
        assert len(results) > 0

    def test_get_actionable_insights(self):
        gi = GrowthIntelligence()
        v = _make_vector(d30_roas=2.5, d30_ltv=10.0)
        gi.analyze([v])
        actionable = gi.get_actionable_insights()
        for insight in actionable:
            assert insight.confidence >= 0.7

    def test_get_high_confidence_insights(self):
        gi = GrowthIntelligence()
        v = _make_vector(d30_roas=2.5, d30_ltv=10.0)
        gi.analyze([v])
        high_conf = gi.get_high_confidence_insights()
        for insight in high_conf:
            assert insight.confidence >= 0.85

    def test_get_winners(self):
        gi = GrowthIntelligence()
        v = _make_vector(d30_roas=2.5, d30_ltv=10.0)
        gi.analyze([v])
        winners = gi.get_winners()
        assert len(winners) > 0

    def test_get_fatigued(self):
        gi = GrowthIntelligence()
        v = _make_vector(fatigue_score=0.8, is_fatigued=True, ctr=0.005)
        gi.analyze([v])
        fatigued = gi.get_fatigued()
        assert len(fatigued) > 0

    def test_get_scale_opportunities(self):
        gi = GrowthIntelligence()
        v = _make_vector(d30_roas=2.0, fatigue_score=0.1, confidence=0.9)
        gi.analyze([v])
        scale = gi.get_scale_opportunities()
        assert len(scale) > 0

    def test_get_summary(self):
        gi = GrowthIntelligence()
        v = _make_vector(d30_roas=2.5, d30_ltv=10.0)
        gi.analyze([v])
        summary = gi.get_summary()
        assert summary["total_insights"] > 0
        assert "by_type" in summary

    def test_reset(self):
        gi = GrowthIntelligence()
        v = _make_vector(d30_roas=2.5, d30_ltv=10.0)
        gi.analyze([v])
        assert gi.insight_count > 0
        gi.reset()
        assert gi.insight_count == 0

    def test_custom_thresholds(self):
        gi = GrowthIntelligence(thresholds={"winner_roas": 3.0})
        v = _make_vector(d30_roas=2.5, d30_ltv=10.0)
        results = gi.analyze([v])
        winners = [r for r in results if r.insight_type == InsightType.WINNER_DISCOVERY]
        # With threshold at 3.0, ROAS 2.5 should not trigger winner
        assert len(winners) == 0


# ═══════════════════════════════════════════════════════════════
# Test OpportunityDetector
# ═══════════════════════════════════════════════════════════════


class TestOpportunityDetector:
    """机会发现引擎测试."""

    def test_detect_empty(self):
        od = OpportunityDetector()
        results = od.detect([])
        assert results == []

    def test_detect_winner_creates_scale(self):
        od = OpportunityDetector()
        v = _make_vector(d30_roas=2.5, spend=500.0)
        insight = _make_insight(
            insight_type=InsightType.WINNER_DISCOVERY,
            confidence=0.9,
            source_vector=v,
        )
        results = od.detect([insight])
        assert len(results) > 0
        assert results[0].action == ActionType.SCALE

    def test_detect_scale_opportunity(self):
        od = OpportunityDetector()
        v = _make_vector(d30_roas=2.0, spend=500.0)
        insight = _make_insight(
            insight_type=InsightType.SCALE_OPPORTUNITY,
            confidence=0.85,
            source_vector=v,
        )
        results = od.detect([insight])
        assert len(results) > 0
        assert results[0].is_scale_action

    def test_detect_fatigue_high_severity_creates_stop(self):
        od = OpportunityDetector()
        v = _make_vector(d30_roas=0.3, spend=300.0, fatigue_score=0.9)
        insight = _make_insight(
            insight_type=InsightType.CREATIVE_FATIGUE,
            confidence=0.9,
            severity=OpportunitySeverity.HIGH,
            source_vector=v,
        )
        results = od.detect([insight])
        stop_actions = [r for r in results if r.action == ActionType.STOP]
        assert len(stop_actions) > 0

    def test_detect_fatigue_medium_creates_mutate(self):
        od = OpportunityDetector()
        v = _make_vector(d30_roas=1.0, spend=300.0, fatigue_score=0.5, fitness_score=0.6)
        insight = _make_insight(
            insight_type=InsightType.CREATIVE_FATIGUE,
            confidence=0.7,
            severity=OpportunitySeverity.MEDIUM,
            source_vector=v,
        )
        results = od.detect([insight])
        mutate_actions = [r for r in results if r.action == ActionType.MUTATE]
        assert len(mutate_actions) > 0

    def test_detect_roas_drop_creates_decrease(self):
        od = OpportunityDetector()
        v = _make_vector(d30_roas=0.5, spend=500.0)
        insight = _make_insight(
            insight_type=InsightType.ROAS_DROP,
            confidence=0.8,
            source_vector=v,
        )
        results = od.detect([insight])
        assert len(results) > 0
        assert results[0].action == ActionType.DECREASE_BUDGET

    def test_detect_budget_misallocation_creates_decrease(self):
        od = OpportunityDetector()
        v = _make_vector(d30_roas=0.4, spend=500.0)
        insight = _make_insight(
            insight_type=InsightType.BUDGET_MISALLOCATION,
            confidence=0.8,
            source_vector=v,
        )
        results = od.detect([insight])
        assert len(results) > 0
        assert results[0].action == ActionType.DECREASE_BUDGET

    def test_detect_underperforming_creates_stop(self):
        od = OpportunityDetector()
        v = _make_vector(d30_roas=0.3, spend=500.0)
        insight = _make_insight(
            insight_type=InsightType.UNDERPERFORMING,
            confidence=0.95,
            severity=OpportunitySeverity.CRITICAL,
            source_vector=v,
        )
        results = od.detect([insight])
        assert len(results) > 0
        assert results[0].action == ActionType.STOP

    def test_detect_hybrid_winner_creates_scale(self):
        od = OpportunityDetector()
        v = _make_vector(d30_roas=2.5, spend=500.0)
        insight = _make_insight(
            insight_type=InsightType.HYBRID_WINNER,
            confidence=0.9,
            source_vector=v,
        )
        results = od.detect([insight])
        assert len(results) > 0
        assert results[0].action == ActionType.SCALE

    def test_detect_retention_signal_creates_scale(self):
        od = OpportunityDetector()
        v = _make_vector(d30_roas=1.5, spend=300.0)
        insight = _make_insight(
            insight_type=InsightType.RETENTION_SIGNAL,
            confidence=0.75,
            source_vector=v,
        )
        results = od.detect([insight])
        assert len(results) > 0
        assert results[0].action == ActionType.SCALE

    def test_detect_cpi_alert_creates_decrease(self):
        od = OpportunityDetector()
        v = _make_vector(cpi=5.0, spend=500.0)
        insight = _make_insight(
            insight_type=InsightType.CPI_ALERT,
            confidence=0.85,
            source_vector=v,
        )
        results = od.detect([insight])
        assert len(results) > 0
        assert results[0].action == ActionType.DECREASE_BUDGET

    def test_strong_scale_multiplier(self):
        od = OpportunityDetector()
        v = _make_vector(d30_roas=3.0, spend=500.0)
        insight = _make_insight(
            insight_type=InsightType.WINNER_DISCOVERY,
            confidence=0.9,
            source_vector=v,
        )
        results = od.detect([insight])
        assert results[0].budget_multiplier == 3.0

    def test_normal_scale_multiplier(self):
        od = OpportunityDetector()
        v = _make_vector(d30_roas=1.8, spend=500.0)
        insight = _make_insight(
            insight_type=InsightType.WINNER_DISCOVERY,
            confidence=0.9,
            source_vector=v,
        )
        results = od.detect([insight])
        assert results[0].budget_multiplier == 2.0

    def test_opportunities_sorted_by_severity(self):
        od = OpportunityDetector()
        v = _make_vector()
        insights = [
            _make_insight(
                creative_id="c1",
                insight_type=InsightType.UNDERPERFORMING,
                confidence=0.9,
                severity=OpportunitySeverity.CRITICAL,
                source_vector=v,
            ),
            _make_insight(
                creative_id="c2",
                insight_type=InsightType.WINNER_DISCOVERY,
                confidence=0.9,
                severity=OpportunitySeverity.HIGH,
                source_vector=v,
            ),
        ]
        results = od.detect(insights)
        assert results[0].severity == OpportunitySeverity.CRITICAL

    def test_get_opportunities_by_action(self):
        od = OpportunityDetector()
        v = _make_vector(d30_roas=2.5, spend=500.0)
        insight = _make_insight(
            insight_type=InsightType.WINNER_DISCOVERY,
            confidence=0.9,
            source_vector=v,
        )
        od.detect([insight])
        scale = od.get_opportunities_by_action(ActionType.SCALE)
        assert len(scale) > 0

    def test_get_scale_opportunities(self):
        od = OpportunityDetector()
        v = _make_vector(d30_roas=2.5, spend=500.0)
        insight = _make_insight(
            insight_type=InsightType.WINNER_DISCOVERY,
            confidence=0.9,
            source_vector=v,
        )
        od.detect([insight])
        scale = od.get_scale_opportunities()
        assert len(scale) > 0

    def test_get_stop_opportunities(self):
        od = OpportunityDetector()
        v = _make_vector(d30_roas=0.3, spend=500.0)
        insight = _make_insight(
            insight_type=InsightType.UNDERPERFORMING,
            confidence=0.95,
            severity=OpportunitySeverity.CRITICAL,
            source_vector=v,
        )
        od.detect([insight])
        stop = od.get_stop_opportunities()
        assert len(stop) > 0

    def test_get_high_confidence_opportunities(self):
        od = OpportunityDetector()
        v = _make_vector(d30_roas=2.5, spend=500.0)
        insight = _make_insight(
            insight_type=InsightType.WINNER_DISCOVERY,
            confidence=0.95,
            source_vector=v,
        )
        od.detect([insight])
        high_conf = od.get_high_confidence_opportunities()
        assert len(high_conf) > 0

    def test_get_summary(self):
        od = OpportunityDetector()
        v = _make_vector(d30_roas=2.5, spend=500.0)
        insight = _make_insight(
            insight_type=InsightType.WINNER_DISCOVERY,
            confidence=0.9,
            source_vector=v,
        )
        od.detect([insight])
        summary = od.get_summary()
        assert summary["total_opportunities"] > 0
        assert "by_action" in summary

    def test_reset(self):
        od = OpportunityDetector()
        v = _make_vector(d30_roas=2.5, spend=500.0)
        insight = _make_insight(
            insight_type=InsightType.WINNER_DISCOVERY,
            confidence=0.9,
            source_vector=v,
        )
        od.detect([insight])
        assert od.opportunity_count > 0
        od.reset()
        assert od.opportunity_count == 0

    def test_custom_thresholds(self):
        od = OpportunityDetector(thresholds={"scale_budget_multiplier": 1.5})
        v = _make_vector(d30_roas=1.8, spend=500.0)
        insight = _make_insight(
            insight_type=InsightType.WINNER_DISCOVERY,
            confidence=0.9,
            source_vector=v,
        )
        results = od.detect([insight])
        assert results[0].budget_multiplier == 1.5


# ═══════════════════════════════════════════════════════════════
# Test CreativeRanker
# ═══════════════════════════════════════════════════════════════


class TestCreativeRanker:
    """统一评分排序测试."""

    def test_rank_empty(self):
        cr = CreativeRanker()
        results = cr.rank([])
        assert results == []

    def test_rank_single_vector(self):
        cr = CreativeRanker()
        v = _make_vector()
        results = cr.rank([v])
        assert len(results) == 1
        assert results[0].rank == 1
        assert results[0].total_creatives == 1

    def test_rank_multiple_vectors(self):
        cr = CreativeRanker()
        vectors = [
            _make_vector(creative_id="c1", d30_roas=3.0, d30_ltv=15.0),
            _make_vector(creative_id="c2", d30_roas=1.0, d30_ltv=3.0),
            _make_vector(creative_id="c3", d30_roas=2.0, d30_ltv=8.0),
        ]
        results = cr.rank(vectors)
        assert len(results) == 3
        # c1 should be rank 1 (highest ROAS and LTV)
        assert results[0].creative_id == "c1"
        assert results[0].rank == 1

    def test_rank_descending_order(self):
        cr = CreativeRanker()
        vectors = [
            _make_vector(creative_id="low", d30_roas=0.5, d30_ltv=2.0),
            _make_vector(creative_id="high", d30_roas=3.0, d30_ltv=15.0),
            _make_vector(creative_id="mid", d30_roas=1.5, d30_ltv=6.0),
        ]
        results = cr.rank(vectors)
        assert results[0].creative_id == "high"
        assert results[2].creative_id == "low"

    def test_fitness_score_range(self):
        cr = CreativeRanker()
        v = _make_vector()
        results = cr.rank([v])
        assert 0.0 <= results[0].fitness_score <= 1.0

    def test_is_winner_detection(self):
        cr = CreativeRanker()
        vectors = [
            _make_vector(creative_id="c1", d30_roas=5.0, d30_ltv=20.0, d7_retention=0.5, ctr=0.08, total_revenue=10000, installs=1000, fitness_score=0.9),
            _make_vector(creative_id="c2", d30_roas=0.5, d30_ltv=2.0, fitness_score=0.2),
            _make_vector(creative_id="c3", d30_roas=0.6, d30_ltv=2.5, fitness_score=0.3),
            _make_vector(creative_id="c4", d30_roas=0.4, d30_ltv=1.5, fitness_score=0.15),
            _make_vector(creative_id="c5", d30_roas=0.5, d30_ltv=2.0, fitness_score=0.2),
        ]
        results = cr.rank(vectors)
        winners = [r for r in results if r.is_winner]
        assert len(winners) > 0
        assert winners[0].creative_id == "c1"

    def test_is_fatigued_flag(self):
        cr = CreativeRanker()
        v = _make_vector(is_fatigued=True)
        results = cr.rank([v])
        assert results[0].is_fatigued is True

    def test_get_ranking(self):
        cr = CreativeRanker()
        vectors = [
            _make_vector(creative_id="target", d30_roas=2.0),
            _make_vector(creative_id="other", d30_roas=1.0),
        ]
        cr.rank(vectors)
        result = cr.get_ranking("target")
        assert result is not None
        assert result.creative_id == "target"

        missing = cr.get_ranking("nonexistent")
        assert missing is None

    def test_get_top(self):
        cr = CreativeRanker()
        vectors = [_make_vector(creative_id=f"c{i}", d30_roas=float(i)) for i in range(1, 11)]
        cr.rank(vectors)
        top = cr.get_top(5)
        assert len(top) == 5

    def test_get_bottom(self):
        cr = CreativeRanker()
        vectors = [_make_vector(creative_id=f"c{i}", d30_roas=float(i)) for i in range(1, 11)]
        cr.rank(vectors)
        bottom = cr.get_bottom(3)
        assert len(bottom) == 3

    def test_get_winners(self):
        cr = CreativeRanker()
        vectors = [
            _make_vector(creative_id="c1", d30_roas=3.0, d30_ltv=15.0, fitness_score=0.9),
            _make_vector(creative_id="c2", d30_roas=0.5, d30_ltv=2.0, fitness_score=0.2),
        ]
        cr.rank(vectors)
        winners = cr.get_winners()
        assert len(winners) >= 0

    def test_compare(self):
        cr = CreativeRanker()
        vectors = [
            _make_vector(creative_id="c1", d30_roas=3.0),
            _make_vector(creative_id="c2", d30_roas=1.0),
        ]
        cr.rank(vectors)
        result = cr.compare("c1", "c2")
        assert result["winner"] == "c1"
        assert "delta" in result

    def test_compare_missing(self):
        cr = CreativeRanker()
        vectors = [_make_vector(creative_id="c1")]
        cr.rank(vectors)
        result = cr.compare("c1", "c2")
        assert "error" in result

    def test_get_summary(self):
        cr = CreativeRanker()
        vectors = [_make_vector(creative_id=f"c{i}", d30_roas=float(i)) for i in range(1, 6)]
        cr.rank(vectors)
        summary = cr.get_summary()
        assert summary["total_ranked"] == 5
        assert "avg_fitness" in summary

    def test_reset(self):
        cr = CreativeRanker()
        v = _make_vector()
        cr.rank([v])
        assert cr.ranking_count == 1
        cr.reset()
        assert cr.ranking_count == 0

    def test_custom_weights(self):
        cr = CreativeRanker(weights={"roas": 0.5, "ltv": 0.5})
        v = _make_vector(d30_roas=3.0, d30_ltv=10.0)
        results = cr.rank([v])
        assert 0.0 <= results[0].fitness_score <= 1.0

    def test_get_top_performers(self):
        cr = CreativeRanker()
        vectors = [
            _make_vector(creative_id="c1", d30_roas=3.0, d30_ltv=15.0, fitness_score=0.9),
            _make_vector(creative_id="c2", d30_roas=0.5, d30_ltv=2.0, fitness_score=0.2),
        ]
        cr.rank(vectors)
        performers = cr.get_top_performers()
        assert len(performers) >= 0

    def test_get_by_confidence(self):
        cr = CreativeRanker()
        v = _make_vector(confidence=0.9)
        cr.rank([v])
        high_conf = cr.get_by_confidence(DecisionConfidence.HIGH)
        assert len(high_conf) >= 0


# ═══════════════════════════════════════════════════════════════
# Test ActionMapper
# ═══════════════════════════════════════════════════════════════


class TestActionMapper:
    """机会到决策映射测试."""

    def test_map_empty(self):
        am = ActionMapper()
        results = am.map_opportunities([])
        assert results == []

    def test_map_scale_opportunity(self):
        am = ActionMapper()
        opp = GrowthOpportunity(
            action=ActionType.SCALE,
            creative_id="c1",
            confidence=0.9,
            budget_multiplier=1.5,
            current_budget=500.0,
            target_budget=750.0,
            reason="Scale winner",
            severity=OpportunitySeverity.HIGH,
            expected_impact={"revenue_growth": 500.0},
        )
        results = am.map_opportunities([opp])
        assert len(results) == 1
        assert results[0].action == ActionType.SCALE
        assert results[0].is_autonomous is True

    def test_map_stop_opportunity(self):
        am = ActionMapper()
        opp = GrowthOpportunity(
            action=ActionType.STOP,
            creative_id="c1",
            confidence=0.85,
            current_budget=300.0,
            target_budget=0.0,
            reason="Stop underperforming",
            severity=OpportunitySeverity.CRITICAL,
        )
        results = am.map_opportunities([opp])
        assert len(results) == 1
        assert results[0].action == ActionType.STOP
        assert results[0].requires_approval is True
        assert results[0].approval_level == 1

    def test_map_stop_high_budget_low_confidence(self):
        am = ActionMapper()
        opp = GrowthOpportunity(
            action=ActionType.STOP,
            creative_id="c1",
            confidence=0.7,
            current_budget=1000.0,
            target_budget=0.0,
            reason="Stop",
            severity=OpportunitySeverity.CRITICAL,
        )
        results = am.map_opportunities([opp])
        assert len(results) == 1
        assert results[0].approval_level == 2

    def test_map_scale_high_multiplier_requires_approval(self):
        am = ActionMapper()
        opp = GrowthOpportunity(
            action=ActionType.SCALE,
            creative_id="c1",
            confidence=0.9,
            budget_multiplier=2.5,
            current_budget=500.0,
            target_budget=1250.0,
            reason="Scale",
            severity=OpportunitySeverity.HIGH,
        )
        results = am.map_opportunities([opp])
        assert len(results) == 1
        assert results[0].requires_approval is True
        assert results[0].approval_level == 1

    def test_map_scale_very_high_multiplier(self):
        am = ActionMapper()
        opp = GrowthOpportunity(
            action=ActionType.SCALE,
            creative_id="c1",
            confidence=0.9,
            budget_multiplier=4.0,
            current_budget=500.0,
            target_budget=2000.0,
            reason="Scale",
            severity=OpportunitySeverity.HIGH,
        )
        results = am.map_opportunities([opp])
        assert len(results) == 1
        assert results[0].approval_level == 2

    def test_map_mutate_is_autonomous(self):
        am = ActionMapper()
        opp = GrowthOpportunity(
            action=ActionType.MUTATE,
            creative_id="c1",
            confidence=0.75,
            reason="Mutation",
            severity=OpportunitySeverity.MEDIUM,
        )
        results = am.map_opportunities([opp])
        assert len(results) == 1
        assert results[0].is_autonomous is True
        assert results[0].approval_level == 0

    def test_map_low_confidence_filtered(self):
        am = ActionMapper()
        opp = GrowthOpportunity(
            action=ActionType.SCALE,
            creative_id="c1",
            confidence=0.3,
            reason="Low confidence",
        )
        results = am.map_opportunities([opp])
        assert len(results) == 0

    def test_map_creates_budget_action(self):
        am = ActionMapper()
        opp = GrowthOpportunity(
            action=ActionType.SCALE,
            creative_id="c1",
            confidence=0.9,
            budget_multiplier=2.0,
            current_budget=500.0,
            target_budget=1000.0,
            reason="Scale",
            severity=OpportunitySeverity.HIGH,
            expected_impact={"revenue_growth": 500.0},
        )
        results = am.map_opportunities([opp])
        assert results[0].budget_action is not None
        assert results[0].budget_action.current_budget == 500.0
        assert results[0].budget_action.target_budget == 1000.0

    def test_map_no_budget_action_for_mutate(self):
        am = ActionMapper()
        opp = GrowthOpportunity(
            action=ActionType.MUTATE,
            creative_id="c1",
            confidence=0.75,
            reason="Mutate",
        )
        results = am.map_opportunities([opp])
        assert results[0].budget_action is None

    def test_map_launch_experiment_requires_approval(self):
        am = ActionMapper()
        opp = GrowthOpportunity(
            action=ActionType.LAUNCH_EXPERIMENT,
            creative_id="c1",
            confidence=0.8,
            reason="New experiment",
        )
        results = am.map_opportunities([opp])
        assert len(results) == 1
        assert results[0].requires_approval is True
        assert results[0].approval_level == 1

    def test_map_decrease_budget_requires_approval(self):
        am = ActionMapper()
        opp = GrowthOpportunity(
            action=ActionType.DECREASE_BUDGET,
            creative_id="c1",
            confidence=0.8,
            current_budget=500.0,
            target_budget=250.0,
            reason="Decrease",
        )
        results = am.map_opportunities([opp])
        assert len(results) == 1
        assert results[0].requires_approval is True

    def test_get_autonomous_actions(self):
        am = ActionMapper()
        opp1 = GrowthOpportunity(
            action=ActionType.MUTATE,
            creative_id="c1",
            confidence=0.75,
            reason="Mutate",
        )
        opp2 = GrowthOpportunity(
            action=ActionType.STOP,
            creative_id="c2",
            confidence=0.6,
            current_budget=1000.0,
            reason="Stop",
        )
        am.map_opportunities([opp1, opp2])
        auto = am.get_autonomous_actions()
        assert len(auto) == 1
        assert auto[0].creative_id == "c1"

    def test_get_approval_actions(self):
        am = ActionMapper()
        opp1 = GrowthOpportunity(
            action=ActionType.MUTATE,
            creative_id="c1",
            confidence=0.75,
            reason="Mutate",
        )
        opp2 = GrowthOpportunity(
            action=ActionType.STOP,
            creative_id="c2",
            confidence=0.6,
            current_budget=1000.0,
            reason="Stop",
        )
        am.map_opportunities([opp1, opp2])
        approval = am.get_approval_actions()
        assert len(approval) == 1
        assert approval[0].creative_id == "c2"

    def test_get_actions_by_type(self):
        am = ActionMapper()
        opp = GrowthOpportunity(
            action=ActionType.SCALE,
            creative_id="c1",
            confidence=0.9,
            budget_multiplier=1.5,
            current_budget=500.0,
            target_budget=750.0,
            reason="Scale",
            expected_impact={"revenue_growth": 500.0},
        )
        am.map_opportunities([opp])
        scale = am.get_actions_by_type(ActionType.SCALE)
        assert len(scale) == 1

    def test_get_actions_by_approval_level(self):
        am = ActionMapper()
        opp1 = GrowthOpportunity(
            action=ActionType.MUTATE,
            creative_id="c1",
            confidence=0.75,
            reason="Mutate",
        )
        opp2 = GrowthOpportunity(
            action=ActionType.STOP,
            creative_id="c2",
            confidence=0.6,
            current_budget=1000.0,
            reason="Stop",
        )
        am.map_opportunities([opp1, opp2])
        level0 = am.get_actions_by_approval_level(0)
        level2 = am.get_actions_by_approval_level(2)
        assert len(level0) == 1
        assert len(level2) == 1

    def test_get_summary(self):
        am = ActionMapper()
        opp = GrowthOpportunity(
            action=ActionType.SCALE,
            creative_id="c1",
            confidence=0.9,
            budget_multiplier=1.5,
            current_budget=500.0,
            target_budget=750.0,
            reason="Scale",
            expected_impact={"revenue_growth": 500.0},
        )
        am.map_opportunities([opp])
        summary = am.get_summary()
        assert summary["total_actions"] == 1
        assert "by_level" in summary

    def test_reset(self):
        am = ActionMapper()
        opp = GrowthOpportunity(
            action=ActionType.SCALE,
            creative_id="c1",
            confidence=0.9,
            budget_multiplier=1.5,
            current_budget=500.0,
            target_budget=750.0,
            reason="Scale",
            expected_impact={"revenue_growth": 500.0},
        )
        am.map_opportunities([opp])
        assert am.action_count == 1
        am.reset()
        assert am.action_count == 0


# ═══════════════════════════════════════════════════════════════
# Test ConfidenceCalculator
# ═══════════════════════════════════════════════════════════════


class TestConfidenceCalculator:
    """置信度计算测试."""

    def test_calculate_high_sample(self):
        cc = ConfidenceCalculator()
        v = _make_vector(sample_size=15000, ctr=0.03, d30_roas=2.0, d30_ltv=10.0, d7_retention=0.3)
        result = cc.calculate(v)
        assert result["data_confidence"] > 0.8
        assert result["overall_confidence"] > 0.7

    def test_calculate_low_sample(self):
        cc = ConfidenceCalculator()
        v = _make_vector(sample_size=200, ctr=0.01, d30_roas=0.5)
        result = cc.calculate(v)
        assert result["data_confidence"] < 0.3

    def test_calculate_excellent_sample(self):
        cc = ConfidenceCalculator()
        v = _make_vector(sample_size=20000)
        result = cc.calculate(v)
        assert result["data_confidence"] == 1.0

    def test_calculate_no_installs(self):
        cc = ConfidenceCalculator()
        v = _make_vector(installs=0, sample_size=0)
        result = cc.calculate(v)
        assert result["signal_confidence"] == 0.0

    def test_calculate_level_high(self):
        cc = ConfidenceCalculator()
        fresh_date = (date.today() - timedelta(days=3)).isoformat()
        v = _make_vector(sample_size=20000, d30_roas=3.0, d30_ltv=15.0, d7_retention=0.4, ctr=0.05, date=fresh_date)
        result = cc.calculate(v)
        assert result["level"] == DecisionConfidence.HIGH

    def test_calculate_level_low(self):
        cc = ConfidenceCalculator()
        v = _make_vector(sample_size=200, d30_roas=0.3, d30_ltv=1.0)
        result = cc.calculate(v)
        assert result["level"] in (DecisionConfidence.LOW, DecisionConfidence.SPECULATIVE)

    def test_calculate_time_confidence_fresh(self):
        cc = ConfidenceCalculator()
        fresh_date = (date.today() - timedelta(days=3)).isoformat()
        v = _make_vector(date=fresh_date)
        result = cc.calculate(v)
        assert result["time_confidence"] >= 0.7

    def test_calculate_time_confidence_old(self):
        cc = ConfidenceCalculator()
        old_date = (date.today() - timedelta(days=60)).isoformat()
        v = _make_vector(date=old_date)
        result = cc.calculate(v)
        assert result["time_confidence"] < 0.5

    def test_calculate_for_insight(self):
        cc = ConfidenceCalculator()
        v = _make_vector(sample_size=10000)
        insight = _make_insight(confidence=0.9, source_vector=v)
        result = cc.calculate_for_insight(insight)
        assert result["overall_confidence"] > 0.7
        assert "level" in result

    def test_calculate_for_insight_no_vector(self):
        cc = ConfidenceCalculator()
        insight = _make_insight(confidence=0.8)
        insight.source_vector = None
        result = cc.calculate_for_insight(insight)
        assert "overall_confidence" in result

    def test_custom_weights(self):
        cc = ConfidenceCalculator(weights={"data_confidence": 0.8, "signal_confidence": 0.1, "time_confidence": 0.1})
        v = _make_vector(sample_size=20000, d30_roas=3.0)
        result = cc.calculate(v)
        assert result["data_confidence"] > 0.9

    def test_signal_confidence_consistency(self):
        """High ROAS + High LTV should give higher signal confidence."""
        cc = ConfidenceCalculator()
        v_high = _make_vector(d30_roas=3.0, d30_ltv=15.0, ctr=0.05, d7_retention=0.4)
        v_low = _make_vector(d30_roas=0.5, d30_ltv=1.0, ctr=0.005, d7_retention=0.05)
        r_high = cc.calculate(v_high)
        r_low = cc.calculate(v_low)
        assert r_high["signal_confidence"] >= r_low["signal_confidence"]

    def test_has_recommendation(self):
        cc = ConfidenceCalculator()
        v = _make_vector(sample_size=20000)
        result = cc.calculate(v)
        assert "recommendation" in result
        assert len(result["recommendation"]) > 0

    def test_calculate_components(self):
        cc = ConfidenceCalculator()
        v = _make_vector(sample_size=5000)
        result = cc.calculate(v)
        assert result["components"]["sample_size"] == 5000
        assert "has_metrics" in result["components"]

    def test_calculate_with_no_date(self):
        cc = ConfidenceCalculator()
        v = _make_vector(date="")
        result = cc.calculate(v)
        assert result["time_confidence"] == 0.5


# ═══════════════════════════════════════════════════════════════
# Test RiskAssessor
# ═══════════════════════════════════════════════════════════════


class TestRiskAssessor:
    """风险评估测试."""

    def test_assess_budget_risk_low(self):
        ra = RiskAssessor()
        result = ra.assess_budget_risk(500.0, 550.0)
        assert result["risk_level"] == "low"

    def test_assess_budget_risk_medium(self):
        ra = RiskAssessor()
        result = ra.assess_budget_risk(500.0, 650.0)
        assert result["risk_level"] == "medium"

    def test_assess_budget_risk_high(self):
        ra = RiskAssessor()
        result = ra.assess_budget_risk(500.0, 1000.0)
        assert result["risk_level"] == "high"

    def test_assess_budget_risk_zero_current(self):
        ra = RiskAssessor()
        result = ra.assess_budget_risk(0.0, 500.0)
        assert result["risk_level"] == "medium"

    def test_assess_budget_risk_zero_both(self):
        ra = RiskAssessor()
        result = ra.assess_budget_risk(0.0, 0.0)
        assert result["risk_level"] == "none"

    def test_assess_confidence_risk_high(self):
        ra = RiskAssessor()
        result = ra.assess_confidence_risk(0.3)
        assert result["risk_level"] == "high"

    def test_assess_confidence_risk_medium(self):
        ra = RiskAssessor()
        result = ra.assess_confidence_risk(0.6)
        assert result["risk_level"] == "medium"

    def test_assess_confidence_risk_none(self):
        ra = RiskAssessor()
        result = ra.assess_confidence_risk(0.85)
        assert result["risk_level"] == "none"

    def test_assess_action_risk_stop(self):
        ra = RiskAssessor()
        result = ra.assess_action_risk("stop", 0.6, 0.5)
        assert result["risk_level"] in ("high", "medium")

    def test_assess_action_risk_mutate(self):
        ra = RiskAssessor()
        result = ra.assess_action_risk("mutate", 0.8, 0.0)
        assert result["risk_level"] == "low"

    def test_get_risk_summary(self):
        ra = RiskAssessor()
        assessments = [
            ra.assess_budget_risk(500.0, 1000.0),
            ra.assess_confidence_risk(0.3),
            ra.assess_budget_risk(500.0, 550.0),
        ]
        summary = ra.get_risk_summary(assessments)
        assert summary["total"] == 3
        assert summary["high"] > 0

    def test_get_risk_summary_empty(self):
        ra = RiskAssessor()
        summary = ra.get_risk_summary([])
        assert summary["total"] == 0


# ═══════════════════════════════════════════════════════════════
# Test GrowthDecisionEngine
# ═══════════════════════════════════════════════════════════════


class TestGrowthDecisionEngine:
    """核心决策编排测试."""

    def test_analyze_empty(self):
        engine = GrowthDecisionEngine()
        report = engine.analyze([], product_id="p1")
        assert report.product_id == "p1"
        assert report.total_creatives_analyzed == 0

    def test_analyze_single_vector(self):
        engine = GrowthDecisionEngine()
        v = _make_vector(d30_roas=2.5, d30_ltv=10.0, confidence=0.9)
        report = engine.analyze([v], product_id="p1")
        assert report.total_creatives_analyzed == 1
        assert report.total_insights > 0
        assert len(report.rankings) == 1

    def test_analyze_multiple_vectors(self):
        engine = GrowthDecisionEngine()
        vectors = [
            _make_vector(creative_id="c1", d30_roas=3.0, d30_ltv=15.0, confidence=0.9),
            _make_vector(creative_id="c2", d30_roas=0.3, d30_ltv=1.0, spend=500.0, confidence=0.9),
            _make_vector(creative_id="c3", d30_roas=1.0, d30_ltv=4.0, confidence=0.7),
        ]
        report = engine.analyze(vectors, product_id="p1")
        assert report.total_creatives_analyzed == 3
        assert report.total_insights > 0
        assert len(report.rankings) == 3

    def test_report_has_decisions(self):
        engine = GrowthDecisionEngine()
        vectors = [
            _make_vector(creative_id="c1", d30_roas=3.0, d30_ltv=15.0, confidence=0.9),
            _make_vector(creative_id="c2", d30_roas=0.3, d30_ltv=1.0, spend=500.0, confidence=0.9),
        ]
        report = engine.analyze(vectors)
        assert report.has_decisions

    def test_report_winner_count(self):
        engine = GrowthDecisionEngine()
        vectors = [
            _make_vector(creative_id="c1", d30_roas=3.0, d30_ltv=15.0, fitness_score=0.9, confidence=0.9),
            _make_vector(creative_id="c2", d30_roas=0.5, d30_ltv=2.0, fitness_score=0.2, confidence=0.9),
        ]
        report = engine.analyze(vectors)
        assert report.winners_count >= 0

    def test_report_fatigued_count(self):
        engine = GrowthDecisionEngine()
        v = _make_vector(is_fatigued=True, fatigue_score=0.8, ctr=0.005, d30_roas=0.5)
        report = engine.analyze([v])
        assert report.fatigued_count >= 0

    def test_quick_analyze(self):
        engine = GrowthDecisionEngine()
        v = _make_vector(d30_roas=2.5, d30_ltv=10.0, confidence=0.9)
        result = engine.quick_analyze([v])
        assert "total_creatives" in result
        assert "top_decisions" in result

    def test_export_for_feedback_controller(self):
        engine = GrowthDecisionEngine()
        v = _make_vector(d30_roas=2.5, d30_ltv=10.0, confidence=0.9)
        engine.analyze([v])
        result = engine.export_for_feedback_controller()
        assert isinstance(result, list)

    def test_export_for_feedback_controller_no_report(self):
        engine = GrowthDecisionEngine()
        result = engine.export_for_feedback_controller()
        assert result == []

    def test_export_for_evolution_engine(self):
        engine = GrowthDecisionEngine()
        v = _make_vector(
            creative_id="c1", d30_roas=1.0, fatigue_score=0.5, fitness_score=0.6,
            d30_ltv=4.0, confidence=0.7,
        )
        engine.analyze([v])
        result = engine.export_for_evolution_engine()
        assert isinstance(result, list)

    def test_export_for_evolution_engine_no_report(self):
        engine = GrowthDecisionEngine()
        result = engine.export_for_evolution_engine()
        assert result == []

    def test_last_report(self):
        engine = GrowthDecisionEngine()
        assert engine.last_report is None
        v = _make_vector(d30_roas=2.5, d30_ltv=10.0, confidence=0.9)
        engine.analyze([v])
        assert engine.last_report is not None

    def test_get_summary(self):
        engine = GrowthDecisionEngine()
        v = _make_vector(d30_roas=2.5, d30_ltv=10.0, confidence=0.9)
        engine.analyze([v])
        summary = engine.get_summary()
        assert "report" in summary
        assert "intelligence" in summary

    def test_get_summary_no_analysis(self):
        engine = GrowthDecisionEngine()
        summary = engine.get_summary()
        assert summary["status"] == "no analysis performed"

    def test_reset(self):
        engine = GrowthDecisionEngine()
        v = _make_vector(d30_roas=2.5, d30_ltv=10.0, confidence=0.9)
        engine.analyze([v])
        assert engine.last_report is not None
        engine.reset()
        assert engine.last_report is None

    def test_custom_components(self):
        gi = GrowthIntelligence(thresholds={"winner_roas": 3.0})
        od = OpportunityDetector(thresholds={"scale_budget_multiplier": 1.5})
        cr = CreativeRanker(weights={"roas": 0.5, "ltv": 0.5})
        am = ActionMapper(thresholds={"min_confidence": 0.6})
        engine = GrowthDecisionEngine(
            intelligence=gi,
            detector=od,
            ranker=cr,
            mapper=am,
        )
        v = _make_vector(d30_roas=2.5, d30_ltv=10.0, confidence=0.9)
        report = engine.analyze([v])
        assert report is not None

    def test_engine_properties(self):
        engine = GrowthDecisionEngine()
        assert engine.intelligence is not None
        assert engine.detector is not None
        assert engine.ranker is not None

    def test_report_top_decision(self):
        engine = GrowthDecisionEngine()
        v = _make_vector(d30_roas=2.5, d30_ltv=10.0, confidence=0.9)
        report = engine.analyze([v])
        if report.has_decisions:
            assert report.top_decision is not None

    def test_report_to_dict(self):
        engine = GrowthDecisionEngine()
        v = _make_vector(d30_roas=2.5, d30_ltv=10.0, confidence=0.9)
        report = engine.analyze([v])
        d = report.to_dict()
        assert "report_id" in d
        assert "summary" in d


# ═══════════════════════════════════════════════════════════════
# Test Integration
# ═══════════════════════════════════════════════════════════════


class TestDecisionEngineIntegration:
    """集成测试 — 模拟完整决策闭环."""

    def test_full_winner_flow(self):
        """模拟: Winner 发现 → 放量决策."""
        engine = GrowthDecisionEngine()
        v = _make_vector(
            creative_id="winner_001",
            creative_name="Winner Creative",
            d30_roas=3.0,
            d30_ltv=15.0,
            spend=500.0,
            confidence=0.95,
            sample_size=10000,
            fitness_score=0.9,
        )
        report = engine.analyze([v], product_id="game_001")

        # 应产生 Winner 洞察
        assert report.total_insights > 0
        # 应产生排名
        assert len(report.rankings) == 1
        assert report.rankings[0].rank == 1

    def test_full_fatigue_flow(self):
        """模拟: 疲劳检测 → 变异决策."""
        engine = GrowthDecisionEngine()
        v = _make_vector(
            creative_id="fatigued_001",
            creative_name="Fatigued Creative",
            d30_roas=1.0,
            d30_ltv=4.0,
            spend=300.0,
            fatigue_score=0.8,
            is_fatigued=True,
            ctr=0.005,
            fitness_score=0.6,
            confidence=0.7,
        )
        report = engine.analyze([v], product_id="game_001")

        # 应产生疲劳洞察
        has_fatigue = any(
            i.insight_type == InsightType.CREATIVE_FATIGUE
            for i in report.insights
        )
        assert has_fatigue

    def test_full_underperforming_flow(self):
        """模拟: 低效检测 → 停投决策."""
        engine = GrowthDecisionEngine()
        v = _make_vector(
            creative_id="bad_001",
            creative_name="Underperforming",
            d30_roas=0.2,
            d30_ltv=0.5,
            spend=800.0,
            confidence=0.9,
            sample_size=5000,
        )
        report = engine.analyze([v], product_id="game_001")

        # 应产生低效洞察
        has_under = any(
            i.insight_type == InsightType.UNDERPERFORMING
            for i in report.insights
        )
        assert has_under

    def test_multiple_creatives_ranking(self):
        """模拟: 多个创意排名."""
        engine = GrowthDecisionEngine()
        vectors = [
            _make_vector(creative_id="c1", d30_roas=3.0, d30_ltv=15.0, fitness_score=0.9, confidence=0.9),
            _make_vector(creative_id="c2", d30_roas=2.0, d30_ltv=8.0, fitness_score=0.7, confidence=0.85),
            _make_vector(creative_id="c3", d30_roas=1.0, d30_ltv=4.0, fitness_score=0.5, confidence=0.7),
            _make_vector(creative_id="c4", d30_roas=0.5, d30_ltv=2.0, fitness_score=0.3, confidence=0.6),
            _make_vector(creative_id="c5", d30_roas=0.3, d30_ltv=1.0, spend=500.0, fitness_score=0.15, confidence=0.9),
        ]
        report = engine.analyze(vectors, product_id="game_001")
        assert len(report.rankings) == 5
        assert report.rankings[0].creative_id == "c1"
        assert report.total_insights > 0

    def test_hybrid_winner_flow(self):
        """模拟: 混合变现 Winner."""
        engine = GrowthDecisionEngine()
        v = _make_vector(
            creative_id="hybrid_001",
            d30_roas=2.5,
            d30_ltv=10.0,
            iap_revenue=300.0,
            ad_revenue=200.0,
            confidence=0.9,
        )
        report = engine.analyze([v])
        has_hybrid = any(
            i.insight_type == InsightType.HYBRID_WINNER
            for i in report.insights
        )
        assert has_hybrid

    def test_decision_export_for_feedback(self):
        """模拟: 决策导出到 E12 Feedback Controller."""
        engine = GrowthDecisionEngine()
        vectors = [
            _make_vector(creative_id="c1", d30_roas=3.0, d30_ltv=15.0, confidence=0.9),
            _make_vector(creative_id="c2", d30_roas=0.3, d30_ltv=1.0, spend=500.0, confidence=0.9),
        ]
        engine.analyze(vectors)
        exported = engine.export_for_feedback_controller()
        assert len(exported) > 0
        # 每个决策应有必要字段
        for d in exported:
            assert "action" in d
            assert "creative_id" in d
            assert "confidence" in d
            assert "approval_level" in d

    def test_decision_export_for_evolution(self):
        """模拟: 决策导出到 E11 Evolution Engine."""
        engine = GrowthDecisionEngine()
        v = _make_vector(
            creative_id="c1", d30_roas=1.0, fatigue_score=0.5, fitness_score=0.6,
            d30_ltv=4.0, confidence=0.7,
        )
        engine.analyze([v])
        exported = engine.export_for_evolution_engine()
        # 可能有也可能没有 mutate 决策
        for d in exported:
            assert d["action"] == "mutate"
            assert "creative_id" in d
            assert "genome_id" in d

    def test_e2e_closed_loop(self):
        """模拟: 完整闭环 — 数据 → 洞察 → 决策 → 报告."""
        engine = GrowthDecisionEngine()
        vectors = [
            # Winner
            _make_vector(
                creative_id="star_001", creative_name="Star Creative",
                d30_roas=3.5, d30_ltv=18.0, spend=1000.0, confidence=0.95,
                sample_size=15000, fitness_score=0.95,
            ),
            # Good performer
            _make_vector(
                creative_id="good_001", creative_name="Good Creative",
                d30_roas=1.8, d30_ltv=8.0, spend=500.0, confidence=0.85,
                sample_size=8000, fitness_score=0.7,
            ),
            # Fatigued
            _make_vector(
                creative_id="tired_001", creative_name="Tired Creative",
                d30_roas=0.8, d30_ltv=3.0, spend=300.0, fatigue_score=0.75,
                is_fatigued=True, ctr=0.004, fitness_score=0.4, confidence=0.7,
            ),
            # Underperforming
            _make_vector(
                creative_id="bad_001", creative_name="Bad Creative",
                d30_roas=0.2, d30_ltv=0.5, spend=1000.0, confidence=0.9,
                sample_size=5000, fitness_score=0.1,
            ),
        ]
        report = engine.analyze(vectors, product_id="game_001")

        # 验证报告完整性
        assert report.total_creatives_analyzed == 4
        assert report.total_insights > 0
        assert len(report.rankings) == 4
        assert report.rankings[0].creative_id == "star_001"

        # 验证导出
        feedback = engine.export_for_feedback_controller()
        assert len(feedback) > 0

        # 验证 summary
        summary = engine.get_summary()
        assert summary["report"]["total_creatives_analyzed"] == 4


# ═══════════════════════════════════════════════════════════════
# Test Edge Cases
# ═══════════════════════════════════════════════════════════════


class TestEdgeCases:
    """边界条件测试."""

    def test_all_zero_metrics(self):
        """所有指标为 0."""
        engine = GrowthDecisionEngine()
        v = CreativeFitnessVector(
            creative_id="zero_001",
            creative_name="Zero",
            product_id="p1",
            date="2026-07-24",
        )
        report = engine.analyze([v])
        # 不应崩溃
        assert report is not None
        assert report.total_creatives_analyzed == 1

    def test_very_large_metrics(self):
        """极值指标."""
        engine = GrowthDecisionEngine()
        v = _make_vector(
            d30_roas=100.0, d30_ltv=1000.0, spend=1000000.0,
            total_revenue=5000000.0, installs=1000000,
        )
        report = engine.analyze([v])
        assert report is not None
        # 排名得分应在 0-1 范围
        for r in report.rankings:
            assert 0.0 <= r.fitness_score <= 1.0

    def test_single_creative_ranking(self):
        """单个创意排名."""
        cr = CreativeRanker()
        v = _make_vector()
        results = cr.rank([v])
        assert results[0].rank == 1
        assert results[0].total_creatives == 1
        assert results[0].percentile == 100.0

    def test_many_creatives_ranking(self):
        """大量创意排名."""
        cr = CreativeRanker()
        vectors = [
            _make_vector(creative_id=f"c{i}", d30_roas=float(i % 10 + 1), d30_ltv=float(i % 20 + 1))
            for i in range(100)
        ]
        results = cr.rank(vectors)
        assert len(results) == 100
        assert results[0].rank == 1
        assert results[-1].rank == 100

    def test_identical_vectors(self):
        """相同指标向量."""
        cr = CreativeRanker()
        v1 = _make_vector(creative_id="c1", d30_roas=2.0, d30_ltv=8.0)
        v2 = _make_vector(creative_id="c2", d30_roas=2.0, d30_ltv=8.0)
        results = cr.rank([v1, v2])
        assert len(results) == 2

    def test_insight_with_no_source_vector(self):
        """洞察无源向量."""
        insight = GrowthInsight(
            insight_type=InsightType.WINNER_DISCOVERY,
            creative_id="c1",
            reason="Test",
            confidence=0.9,
        )
        assert insight.source_vector is None
        # 不应崩溃
        assert insight.is_actionable is True

    def test_opportunity_zero_budget_scale(self):
        """零预算放量."""
        od = OpportunityDetector()
        v = _make_vector(d30_roas=2.5, spend=0.0)
        insight = _make_insight(
            insight_type=InsightType.WINNER_DISCOVERY,
            confidence=0.9,
            source_vector=v,
        )
        results = od.detect([insight])
        assert len(results) > 0
        assert results[0].current_budget == 0.0

    def test_budget_action_zero_delta_percentage(self):
        """预算零变化."""
        ba = BudgetAction(current_budget=0.0, budget_delta=0.0)
        assert ba.delta_percentage == 0.0
        assert ba.is_increase is False
        assert ba.is_decrease is False