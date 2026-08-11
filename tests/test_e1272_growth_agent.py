"""E12.7.2 — Autonomous Growth Agent Test Suite。

覆盖:
  - TestModels:               模型测试 (20)
  - TestPerceptionLayer:      感知层测试 (20)
  - TestReasoningEngine:      推理引擎测试 (25)
  - TestHypothesisGenerator:  假设生成器测试 (20)
  - TestDecisionAdapter:      决策适配器测试 (20)
  - TestAutonomousGrowthAgent: Agent 控制器测试 (25)
  - TestIntegration:          集成测试 (10)

总计: 140 tests
"""

from __future__ import annotations

import pytest

from market_ops.creative_vision_runtime.growth_os.agent import (
    AgentDecision,
    AutonomousGrowthAgent,
    CreativeState,
    DecisionAdapter,
    GrowthHypothesis,
    GrowthObservation,
    HypothesisGenerator,
    HypothesisStatus,
    MarketState,
    ObservationSeverity,
    PerceptionLayer,
    ProductMetrics,
    ReasoningEngine,
    RootCause,
)
from market_ops.creative_vision_runtime.growth_os.kernel import (
    ActionType,
    EventPriority,
    GrowthAction,
    RuntimeManager,
)


# ── Helpers ─────────────────────────────────────────────────


def make_observation(
    product_id: str = "p04",
    roas: float = 0.6,
    ctr: float = 0.02,
    cpi: float = 3.0,
    fatigue: float = 0.75,
    diversity: float = 0.4,
    winner_ratio: float = 0.15,
    trend: float = 0.5,
    competition: float = 0.5,
) -> GrowthObservation:
    return GrowthObservation(
        product_id=product_id,
        metrics=ProductMetrics(
            roas=roas,
            ctr=ctr,
            cpi=cpi,
            revenue=10000,
            spend=15000,
            installs=1000,
            impressions=50000,
        ),
        creative_state=CreativeState(
            fatigue_score=fatigue,
            diversity_score=diversity,
            winner_ratio=winner_ratio,
            active_creatives=50,
            winning_creatives=5,
            total_creatives=100,
        ),
        market_state=MarketState(
            trend_score=trend,
            competition_score=competition,
        ),
    )


def make_root_cause(
    category: str = "creative_fatigue",
    confidence: float = 0.85,
) -> RootCause:
    return RootCause(
        category=category,
        description=f"Test description for {category}",
        confidence=confidence,
        evidence=["Signal: test_signal"],
        suggested_fix="Test fix suggestion",
    )


# ── TestModels ──────────────────────────────────────────────


class TestProductMetrics:
    def test_defaults(self):
        m = ProductMetrics()
        assert m.roas == 0.0
        assert m.cpi == 0.0

    def test_is_roas_healthy(self):
        assert ProductMetrics(roas=1.5).is_roas_healthy
        assert not ProductMetrics(roas=0.5).is_roas_healthy

    def test_is_spending(self):
        assert ProductMetrics(spend=1000, installs=100).is_spending
        assert not ProductMetrics(spend=0).is_spending

    def test_to_dict(self):
        m = ProductMetrics(roas=1.2, cpi=2.5)
        d = m.to_dict()
        assert d["roas"] == 1.2
        assert d["is_roas_healthy"] is True


class TestCreativeState:
    def test_defaults(self):
        c = CreativeState()
        assert c.fatigue_score == 0.0

    def test_is_fatigued(self):
        assert CreativeState(fatigue_score=0.8).is_fatigued
        assert not CreativeState(fatigue_score=0.5).is_fatigued

    def test_is_highly_fatigued(self):
        assert CreativeState(fatigue_score=0.9).is_highly_fatigued
        assert not CreativeState(fatigue_score=0.8).is_highly_fatigued

    def test_is_diverse(self):
        assert CreativeState(diversity_score=0.6).is_diverse
        assert not CreativeState(diversity_score=0.3).is_diverse


class TestMarketState:
    def test_is_declining(self):
        assert MarketState(trend_score=0.2).is_declining
        assert not MarketState(trend_score=0.5).is_declining

    def test_is_highly_competitive(self):
        assert MarketState(competition_score=0.8).is_highly_competitive
        assert not MarketState(competition_score=0.3).is_highly_competitive


class TestGrowthObservation:
    def test_auto_id(self):
        o = make_observation()
        assert o.observation_id.startswith("OBS_")

    def test_needs_attention(self):
        o = make_observation()
        o.severity = ObservationSeverity.WARNING
        assert o.needs_attention

    def test_is_urgent(self):
        o = make_observation()
        o.severity = ObservationSeverity.CRITICAL
        assert o.is_urgent

    def test_to_dict(self):
        o = make_observation()
        d = o.to_dict()
        assert d["product_id"] == "p04"
        assert "metrics" in d

    def test_repr(self):
        o = make_observation()
        r = repr(o)
        assert "p04" in r


class TestRootCause:
    def test_auto_id(self):
        rc = RootCause()
        assert rc.cause_id.startswith("RC_")

    def test_is_high_confidence(self):
        assert RootCause(confidence=0.85).is_high_confidence
        assert not RootCause(confidence=0.70).is_high_confidence

    def test_is_low_confidence(self):
        assert RootCause(confidence=0.20).is_low_confidence
        assert not RootCause(confidence=0.50).is_low_confidence

    def test_to_dict(self):
        rc = make_root_cause()
        d = rc.to_dict()
        assert d["category"] == "creative_fatigue"


class TestGrowthHypothesis:
    def test_auto_id(self):
        h = GrowthHypothesis()
        assert h.hypothesis_id.startswith("HYP_")

    def test_is_actionable(self):
        h = GrowthHypothesis(confidence=0.6, expected_impact=0.3)
        assert h.is_actionable

    def test_not_actionable_low_confidence(self):
        h = GrowthHypothesis(confidence=0.3, expected_impact=0.5)
        assert not h.is_actionable

    def test_not_actionable_low_impact(self):
        h = GrowthHypothesis(confidence=0.8, expected_impact=0.05)
        assert not h.is_actionable

    def test_risk_adjusted_impact(self):
        h = GrowthHypothesis(confidence=0.8, expected_impact=0.5)
        assert h.risk_adjusted_impact == pytest.approx(0.4)

    def test_to_dict(self):
        h = GrowthHypothesis(problem="test", confidence=0.7)
        d = h.to_dict()
        assert d["problem"] == "test"


class TestAgentDecision:
    def test_auto_id(self):
        d = AgentDecision()
        assert d.decision_id.startswith("DEC_")

    def test_is_high_priority(self):
        assert AgentDecision(priority=90).is_high_priority
        assert not AgentDecision(priority=50).is_high_priority

    def test_is_actionable(self):
        assert AgentDecision(confidence=0.7, action_type="mutate").is_actionable
        assert not AgentDecision(confidence=0.3, action_type="").is_actionable

    def test_to_dict(self):
        d = AgentDecision(product_id="p04", action_type="mutate_dna")
        result = d.to_dict()
        assert result["product_id"] == "p04"


# ── TestPerceptionLayer ────────────────────────────────────


class TestPerceptionLayer:
    def test_perceive_basic(self):
        pl = PerceptionLayer()
        obs = pl.perceive("p04", {"roas": 1.2, "ctr": 0.03})
        assert obs.product_id == "p04"
        assert obs.metrics.roas == 1.2

    def test_perceive_creative_data(self):
        pl = PerceptionLayer()
        obs = pl.perceive("p04", creative_data={"fatigue_score": 0.85, "diversity_score": 0.3})
        assert obs.creative_state.fatigue_score == 0.85
        assert obs.creative_state.is_highly_fatigued

    def test_perceive_market_data(self):
        pl = PerceptionLayer()
        obs = pl.perceive("p04", market_data={"trend_score": 0.2, "competition_score": 0.8})
        assert obs.market_state.is_declining
        assert obs.market_state.is_highly_competitive

    def test_detect_roas_critical(self):
        pl = PerceptionLayer()
        obs = pl.perceive("p04", {"roas": 0.3})
        assert "roas_critical" in obs.signals

    def test_detect_roas_warning(self):
        pl = PerceptionLayer()
        obs = pl.perceive("p04", {"roas": 0.6})
        assert "roas_warning" in obs.signals

    def test_detect_ctr_low(self):
        pl = PerceptionLayer()
        obs = pl.perceive("p04", {"ctr": 0.005})
        assert "ctr_low" in obs.signals

    def test_detect_cpi_high(self):
        pl = PerceptionLayer()
        obs = pl.perceive("p04", {"cpi": 6.0})
        assert "cpi_high" in obs.signals

    def test_detect_creative_fatigue(self):
        pl = PerceptionLayer()
        obs = pl.perceive("p04", creative_data={"fatigue_score": 0.9})
        assert "creative_highly_fatigued" in obs.signals

    def test_detect_diversity_low(self):
        pl = PerceptionLayer()
        obs = pl.perceive("p04", creative_data={"diversity_score": 0.2})
        assert "creative_diversity_low" in obs.signals

    def test_detect_market_declining(self):
        pl = PerceptionLayer()
        obs = pl.perceive("p04", market_data={"trend_score": 0.2})
        assert "market_declining" in obs.signals

    def test_detect_market_competitive(self):
        pl = PerceptionLayer()
        obs = pl.perceive("p04", market_data={"competition_score": 0.8})
        assert "market_highly_competitive" in obs.signals

    def test_severity_normal(self):
        pl = PerceptionLayer()
        obs = pl.perceive("p04", {"roas": 1.5, "ctr": 0.05},
                          creative_data={"diversity_score": 0.5, "fatigue_score": 0.1})
        assert obs.severity == ObservationSeverity.NORMAL

    def test_severity_warning(self):
        pl = PerceptionLayer()
        # Single warning signal → WARNING
        obs = pl.perceive("p04", {"roas": 0.6}, creative_data={"fatigue_score": 0.5, "diversity_score": 0.5})
        assert obs.severity == ObservationSeverity.WARNING

    def test_severity_critical(self):
        pl = PerceptionLayer()
        obs = pl.perceive("p04", {"roas": 0.3}, creative_data={"fatigue_score": 0.9})
        assert obs.severity in (ObservationSeverity.CRITICAL, ObservationSeverity.FATAL)

    def test_summary_generated(self):
        pl = PerceptionLayer()
        obs = pl.perceive("p04", {"roas": 0.5})
        assert obs.summary != ""

    def test_get_latest_observation(self):
        pl = PerceptionLayer()
        pl.perceive("p04", {"roas": 1.0})
        pl.perceive("p04", {"roas": 0.5})
        obs = pl.get_latest_observation("p04")
        assert obs.metrics.roas == 0.5

    def test_get_latest_observation_not_found(self):
        pl = PerceptionLayer()
        assert pl.get_latest_observation("p99") is None

    def test_get_history(self):
        pl = PerceptionLayer()
        for i in range(5):
            pl.perceive("p04", {"roas": float(i)})
        assert len(pl.get_history("p04")) == 5

    def test_clear(self):
        pl = PerceptionLayer()
        pl.perceive("p04")
        pl.clear()
        assert pl.observation_count == 0


# ── TestReasoningEngine ────────────────────────────────────


class TestReasoningEngine:
    def test_analyze_fatigue(self):
        re = ReasoningEngine()
        obs = make_observation(fatigue=0.85)
        causes = re.analyze(obs)
        assert any(c.category == "creative_fatigue" for c in causes)

    def test_analyze_roas_critical(self):
        re = ReasoningEngine()
        obs = make_observation(roas=0.3)
        causes = re.analyze(obs)
        assert any(c.category == "roas_critical" for c in causes)

    def test_analyze_roas_decline(self):
        re = ReasoningEngine()
        obs = make_observation(roas=0.6)
        causes = re.analyze(obs)
        assert any(c.category == "roas_decline" for c in causes)

    def test_analyze_diversity_low(self):
        re = ReasoningEngine()
        obs = make_observation(diversity=0.2)
        causes = re.analyze(obs)
        assert any(c.category == "creative_diversity_low" for c in causes)

    def test_analyze_ctr_low(self):
        re = ReasoningEngine()
        obs = make_observation(ctr=0.005)
        causes = re.analyze(obs)
        assert any(c.category == "ctr_decline" for c in causes)

    def test_analyze_cpi_high(self):
        re = ReasoningEngine()
        obs = make_observation(cpi=6.0)
        causes = re.analyze(obs)
        assert any(c.category == "cpi_inflation" for c in causes)

    def test_analyze_market_decline(self):
        re = ReasoningEngine()
        obs = make_observation(trend=0.2)
        causes = re.analyze(obs)
        assert any(c.category == "market_decline" for c in causes)

    def test_analyze_high_competition(self):
        re = ReasoningEngine()
        obs = make_observation(competition=0.8)
        causes = re.analyze(obs)
        assert any(c.category == "high_competition" for c in causes)

    def test_analyze_combined(self):
        re = ReasoningEngine()
        obs = make_observation(fatigue=0.85, roas=0.5)
        causes = re.analyze(obs)
        assert any(c.category == "combined_fatigue_roas" for c in causes)

    def test_causes_sorted_by_confidence(self):
        re = ReasoningEngine()
        obs = make_observation(fatigue=0.85, roas=0.3, diversity=0.2, ctr=0.005)
        causes = re.analyze(obs)
        for i in range(len(causes) - 1):
            assert causes[i].confidence >= causes[i + 1].confidence

    def test_get_top_cause(self):
        re = ReasoningEngine()
        obs = make_observation(fatigue=0.85)
        top = re.get_top_cause(obs)
        assert top is not None
        assert top.category == "creative_fatigue"

    def test_get_top_cause_none(self):
        re = ReasoningEngine()
        obs = make_observation(roas=1.5, ctr=0.05, fatigue=0.1, diversity=0.8)
        top = re.get_top_cause(obs)
        assert top is None

    def test_get_causes_by_category(self):
        re = ReasoningEngine()
        obs = make_observation(fatigue=0.85, roas=0.3)
        grouped = re.get_causes_by_category(obs)
        assert "creative_fatigue" in grouped
        assert "roas_critical" in grouped

    def test_evidence_contains_signals(self):
        re = ReasoningEngine()
        obs = make_observation(fatigue=0.85)
        causes = re.analyze(obs)
        fatigue_cause = [c for c in causes if c.category == "creative_fatigue"][0]
        assert len(fatigue_cause.evidence) > 0

    def test_evidence_contains_metrics(self):
        re = ReasoningEngine()
        obs = make_observation(roas=0.3)
        causes = re.analyze(obs)
        roas_cause = [c for c in causes if c.category == "roas_critical"][0]
        assert any("ROAS" in e for e in roas_cause.evidence)

    def test_normal_observation_no_causes(self):
        re = ReasoningEngine()
        obs = make_observation(roas=1.5, ctr=0.05, fatigue=0.1, diversity=0.8,
                               cpi=2.0, trend=0.6, competition=0.3)
        causes = re.analyze(obs)
        assert len(causes) == 0

    def test_causes_have_suggested_fix(self):
        re = ReasoningEngine()
        obs = make_observation(fatigue=0.85)
        causes = re.analyze(obs)
        for c in causes:
            assert c.suggested_fix != ""

    def test_add_custom_rule(self):
        re = ReasoningEngine()
        re.add_rule({
            "condition": lambda o: o.metrics.roas > 2.0,
            "category": "high_roas",
            "description": "ROAS is very high",
            "base_confidence": 0.9,
            "suggested_fix": "Scale up",
            "evidence_signals": [],
        })
        obs = make_observation(roas=2.5)
        causes = re.analyze(obs)
        assert any(c.category == "high_roas" for c in causes)

    def test_get_diagnosis_history(self):
        re = ReasoningEngine()
        obs = make_observation(fatigue=0.85)
        re.analyze(obs)
        history = re.get_diagnosis_history()
        assert len(history) == 1

    def test_clear_history(self):
        re = ReasoningEngine()
        re.analyze(make_observation(fatigue=0.85))
        re.clear_history()
        assert len(re.get_diagnosis_history()) == 0

    def test_rule_count(self):
        re = ReasoningEngine()
        assert re.rule_count > 0

    def test_analyze_winner_scarcity(self):
        re = ReasoningEngine()
        obs = make_observation(winner_ratio=0.05)
        obs.creative_state.total_creatives = 50
        causes = re.analyze(obs)
        assert any(c.category == "winner_scarcity" for c in causes)

    def test_reasoning_repr(self):
        re = ReasoningEngine()
        r = repr(re)
        assert "ReasoningEngine" in r


# ── TestHypothesisGenerator ────────────────────────────────


class TestHypothesisGenerator:
    def test_generate_from_fatigue(self):
        hg = HypothesisGenerator()
        rc = make_root_cause("creative_fatigue", 0.85)
        h = hg.generate(rc, "p04")
        assert h is not None
        assert h.root_cause_category == "creative_fatigue"
        assert h.is_actionable

    def test_generate_from_roas_critical(self):
        hg = HypothesisGenerator()
        rc = make_root_cause("roas_critical", 0.9)
        h = hg.generate(rc, "p04")
        assert h is not None
        assert h.target_module == "E12.6.1_MetaDecision"

    def test_generate_from_ctr(self):
        hg = HypothesisGenerator()
        rc = make_root_cause("ctr_decline", 0.75)
        h = hg.generate(rc, "p04")
        assert h is not None
        assert h.target_module == "E11_CreativeEvolution"

    def test_generate_unknown_category(self):
        hg = HypothesisGenerator()
        rc = make_root_cause("unknown_category", 0.5)
        h = hg.generate(rc, "p04")
        assert h is None

    def test_generate_from_causes(self):
        hg = HypothesisGenerator()
        causes = [
            make_root_cause("creative_fatigue", 0.85),
            make_root_cause("roas_decline", 0.75),
        ]
        hypotheses = hg.generate_from_causes(causes, "p04")
        assert len(hypotheses) == 2

    def test_generate_from_observation(self):
        hg = HypothesisGenerator()
        causes = [make_root_cause("creative_fatigue", 0.85)]
        hypotheses = hg.generate_from_observation(causes, "p04")
        assert len(hypotheses) == 1

    def test_expected_impact_formula(self):
        hg = HypothesisGenerator()
        rc = make_root_cause("creative_fatigue", 0.80)
        h = hg.generate(rc, "p04")
        # base_impact=0.60 × confidence=0.80 × 0.85 = 0.408
        assert h.expected_impact == pytest.approx(0.408, abs=0.01)

    def test_get_top_hypothesis(self):
        hg = HypothesisGenerator()
        h1 = GrowthHypothesis(expected_impact=0.5, confidence=0.8)
        h2 = GrowthHypothesis(expected_impact=0.3, confidence=0.9)
        top = hg.get_top_hypothesis([h1, h2])
        # h1: 0.5*0.8=0.4, h2: 0.3*0.9=0.27
        assert top.hypothesis_id == h1.hypothesis_id

    def test_get_actionable_hypotheses(self):
        hg = HypothesisGenerator()
        h1 = GrowthHypothesis(confidence=0.6, expected_impact=0.3)
        h2 = GrowthHypothesis(confidence=0.3, expected_impact=0.5)
        h3 = GrowthHypothesis(confidence=0.8, expected_impact=0.05)
        actionable = hg.get_actionable_hypotheses([h1, h2, h3])
        assert len(actionable) == 1

    def test_hypothesis_has_actions(self):
        hg = HypothesisGenerator()
        rc = make_root_cause("creative_fatigue", 0.85)
        h = hg.generate(rc, "p04")
        assert len(h.recommended_actions) > 0

    def test_hypothesis_has_rationale(self):
        hg = HypothesisGenerator()
        rc = make_root_cause("creative_fatigue", 0.85)
        h = hg.generate(rc, "p04")
        assert h.rationale != ""

    def test_add_mapping(self):
        hg = HypothesisGenerator()
        hg.add_mapping("custom_cause", {
            "actions": ["test_action"],
            "target_module": "test_module",
            "base_impact": 0.5,
        })
        rc = make_root_cause("custom_cause", 0.7)
        h = hg.generate(rc, "p04")
        assert h is not None
        assert h.target_module == "test_module"

    def test_get_history(self):
        hg = HypothesisGenerator()
        rc = make_root_cause("creative_fatigue", 0.85)
        hg.generate(rc, "p04")
        assert len(hg.get_history()) == 1

    def test_clear_history(self):
        hg = HypothesisGenerator()
        hg.generate(make_root_cause("creative_fatigue"), "p04")
        hg.clear_history()
        assert len(hg.get_history()) == 0

    def test_generator_repr(self):
        hg = HypothesisGenerator()
        r = repr(hg)
        assert "HypothesisGenerator" in r

    def test_empty_hypotheses_top(self):
        hg = HypothesisGenerator()
        assert hg.get_top_hypothesis([]) is None

    def test_empty_hypotheses_actionable(self):
        hg = HypothesisGenerator()
        assert hg.get_actionable_hypotheses([]) == []

    def test_is_high_confidence(self):
        h = GrowthHypothesis(confidence=0.85)
        assert h.is_high_confidence

    def test_hypothesis_repr(self):
        h = GrowthHypothesis(problem="test problem", confidence=0.8)
        r = repr(h)
        assert "test problem" in r


# ── TestDecisionAdapter ────────────────────────────────────


class TestDecisionAdapter:
    def test_adapt_basic(self):
        da = DecisionAdapter()
        h = GrowthHypothesis(
            root_cause_category="creative_fatigue",
            confidence=0.85,
            expected_impact=0.5,
            target_module="E11_CreativeEvolution",
            rationale="test",
            recommended_actions=["action1"],
        )
        d = da.adapt(h)
        assert d.action_type == "mutate_dna"
        assert d.target_module == "E11_CreativeEvolution"

    def test_adapt_roas_critical(self):
        da = DecisionAdapter()
        h = GrowthHypothesis(
            root_cause_category="roas_critical",
            confidence=0.9,
            expected_impact=0.8,
            target_module="E12.6.1_MetaDecision",
            rationale="test",
        )
        d = da.adapt(h)
        assert d.action_type == "decrease_budget"

    def test_adapt_market_decline(self):
        da = DecisionAdapter()
        h = GrowthHypothesis(
            root_cause_category="market_decline",
            confidence=0.65,
            expected_impact=0.35,
            target_module="E12.6.5_PortfolioOptimizer",
            rationale="test",
        )
        d = da.adapt(h)
        assert d.action_type == "sunset_product"

    def test_adapt_batch(self):
        da = DecisionAdapter()
        hypotheses = [
            GrowthHypothesis(
                root_cause_category="roas_critical",
                confidence=0.9,
                expected_impact=0.8,
                target_module="test",
                rationale="test",
            ),
            GrowthHypothesis(
                root_cause_category="creative_fatigue",
                confidence=0.85,
                expected_impact=0.5,
                target_module="test",
                rationale="test",
            ),
        ]
        decisions = da.adapt_batch(hypotheses)
        assert len(decisions) == 2
        # 按优先级降序，roas_critical 应该在前面
        assert decisions[0].action_type == "decrease_budget"

    def test_priority_includes_confidence_boost(self):
        da = DecisionAdapter()
        h = GrowthHypothesis(
            root_cause_category="creative_fatigue",
            confidence=0.9,
            expected_impact=0.5,
            target_module="test",
            rationale="test",
        )
        d = da.adapt(h)
        # base_priority=70 + confidence_boost=9 = 79
        assert d.priority == 79

    def test_hypothesis_metadata_in_parameters(self):
        da = DecisionAdapter()
        h = GrowthHypothesis(
            root_cause_category="creative_fatigue",
            confidence=0.85,
            expected_impact=0.5,
            target_module="test",
            rationale="test",
            metadata={"product_id": "p04"},
        )
        d = da.adapt(h)
        assert d.parameters["expected_impact"] == 0.5

    def test_adapt_unknown_category(self):
        da = DecisionAdapter()
        h = GrowthHypothesis(
            root_cause_category="unknown",
            confidence=0.5,
            expected_impact=0.3,
            target_module="test",
            rationale="test",
        )
        d = da.adapt(h)
        assert d.action_type == "custom"

    def test_add_mapping(self):
        da = DecisionAdapter()
        da.add_mapping("custom_cause", {"action_type": "test_action", "priority": 99})
        h = GrowthHypothesis(
            root_cause_category="custom_cause",
            confidence=0.9,
            expected_impact=0.5,
            target_module="test",
            rationale="test",
        )
        d = da.adapt(h)
        assert d.action_type == "test_action"

    def test_get_history(self):
        da = DecisionAdapter()
        h = GrowthHypothesis(
            root_cause_category="creative_fatigue",
            confidence=0.85,
            expected_impact=0.5,
            target_module="test",
            rationale="test",
        )
        da.adapt(h)
        assert len(da.get_history()) == 1

    def test_get_high_priority_decisions(self):
        da = DecisionAdapter()
        h1 = GrowthHypothesis(
            root_cause_category="roas_critical",
            confidence=0.9,
            expected_impact=0.8,
            target_module="test",
            rationale="test",
        )
        h2 = GrowthHypothesis(
            root_cause_category="creative_fatigue",
            confidence=0.85,
            expected_impact=0.5,
            target_module="test",
            rationale="test",
        )
        da.adapt(h1)
        da.adapt(h2)
        high = da.get_high_priority_decisions()
        assert len(high) >= 1

    def test_clear_history(self):
        da = DecisionAdapter()
        h = GrowthHypothesis(
            root_cause_category="creative_fatigue",
            confidence=0.85,
            expected_impact=0.5,
            target_module="test",
            rationale="test",
        )
        da.adapt(h)
        da.clear_history()
        assert len(da.get_history()) == 0

    def test_decision_repr(self):
        d = AgentDecision(product_id="p04", action_type="mutate_dna", priority=70)
        r = repr(d)
        assert "p04" in r
        assert "mutate_dna" in r

    def test_adapter_repr(self):
        da = DecisionAdapter()
        r = repr(da)
        assert "DecisionAdapter" in r

    def test_observation_id_linked(self):
        da = DecisionAdapter()
        h = GrowthHypothesis(
            root_cause_category="creative_fatigue",
            confidence=0.85,
            expected_impact=0.5,
            target_module="test",
            rationale="test",
        )
        d = da.adapt(h, observation_id="OBS_123")
        assert d.observation_id == "OBS_123"

    def test_hypothesis_id_linked(self):
        da = DecisionAdapter()
        h = GrowthHypothesis(
            root_cause_category="creative_fatigue",
            confidence=0.85,
            expected_impact=0.5,
            target_module="test",
            rationale="test",
        )
        d = da.adapt(h)
        assert d.hypothesis_id == h.hypothesis_id


# ── TestAutonomousGrowthAgent ──────────────────────────────


class TestAutonomousGrowthAgent:
    def test_observe(self):
        agent = AutonomousGrowthAgent()
        obs = agent.observe("p04", {"roas": 0.5})
        assert obs.product_id == "p04"
        assert obs.metrics.roas == 0.5

    def test_analyze(self):
        agent = AutonomousGrowthAgent()
        agent.observe("p04", {"roas": 0.3}, creative_data={"fatigue_score": 0.85})
        causes = agent.analyze()
        assert len(causes) > 0

    def test_generate_hypotheses(self):
        agent = AutonomousGrowthAgent()
        agent.observe("p04", {"roas": 0.3}, creative_data={"fatigue_score": 0.85})
        agent.analyze()
        hypotheses = agent.generate_hypotheses(product_id="p04")
        assert len(hypotheses) > 0

    def test_decide(self):
        agent = AutonomousGrowthAgent()
        agent.observe("p04", {"roas": 0.3}, creative_data={"fatigue_score": 0.85})
        agent.analyze()
        agent.generate_hypotheses(product_id="p04")
        decisions = agent.decide()
        assert len(decisions) > 0

    def test_act(self):
        agent = AutonomousGrowthAgent()
        d = AgentDecision(
            product_id="p04",
            action_type="mutate_dna",
            confidence=0.85,
            priority=80,
            target_module="E11_CreativeEvolution",
        )
        actions = agent.act([d])
        assert len(actions) == 1
        assert isinstance(actions[0], GrowthAction)

    def test_act_not_actionable(self):
        agent = AutonomousGrowthAgent()
        d = AgentDecision(
            product_id="p04",
            action_type="mutate_dna",
            confidence=0.3,
            priority=50,
            target_module="test",
        )
        actions = agent.act([d])
        assert len(actions) == 0

    def test_run_full_pipeline(self):
        agent = AutonomousGrowthAgent()
        result = agent.run(
            "p04",
            metrics={"roas": 0.3, "ctr": 0.005},
            creative_data={"fatigue_score": 0.85, "diversity_score": 0.2},
            market_data={"trend_score": 0.4},
        )
        assert "observation" in result
        assert "causes" in result
        assert "hypotheses" in result
        assert "decisions" in result
        assert "summary" in result

    def test_run_with_auto_act(self):
        agent = AutonomousGrowthAgent()
        result = agent.run(
            "p04",
            metrics={"roas": 0.3},
            creative_data={"fatigue_score": 0.85},
            auto_act=True,
        )
        assert len(result["actions"]) > 0

    def test_run_normal_observation(self):
        agent = AutonomousGrowthAgent()
        result = agent.run(
            "p04",
            metrics={"roas": 1.5, "ctr": 0.05},
            creative_data={"fatigue_score": 0.1, "diversity_score": 0.8},
        )
        assert len(result["causes"]) == 0
        assert len(result["decisions"]) == 0

    def test_get_last_observation(self):
        agent = AutonomousGrowthAgent()
        agent.observe("p04", {"roas": 0.5})
        assert agent.get_last_observation() is not None

    def test_get_last_causes(self):
        agent = AutonomousGrowthAgent()
        agent.observe("p04", {"roas": 0.3}, creative_data={"fatigue_score": 0.85})
        agent.analyze()
        assert len(agent.get_last_causes()) > 0

    def test_get_last_hypotheses(self):
        agent = AutonomousGrowthAgent()
        agent.observe("p04", {"roas": 0.3}, creative_data={"fatigue_score": 0.85})
        agent.analyze()
        agent.generate_hypotheses(product_id="p04")
        assert len(agent.get_last_hypotheses()) > 0

    def test_get_last_decisions(self):
        agent = AutonomousGrowthAgent()
        agent.observe("p04", {"roas": 0.3}, creative_data={"fatigue_score": 0.85})
        agent.analyze()
        agent.generate_hypotheses(product_id="p04")
        agent.decide()
        assert len(agent.get_last_decisions()) > 0

    def test_get_top_decision(self):
        agent = AutonomousGrowthAgent()
        agent.observe("p04", {"roas": 0.3}, creative_data={"fatigue_score": 0.85})
        agent.analyze()
        agent.generate_hypotheses(product_id="p04")
        agent.decide()
        top = agent.get_top_decision()
        assert top is not None
        assert top.priority > 0

    def test_get_top_decision_empty(self):
        agent = AutonomousGrowthAgent()
        assert agent.get_top_decision() is None

    def test_get_status(self):
        agent = AutonomousGrowthAgent()
        status = agent.get_status()
        assert status["has_observation"] is False
        agent.observe("p04", {"roas": 0.5})
        status = agent.get_status()
        assert status["has_observation"] is True

    def test_run_batch(self):
        agent = AutonomousGrowthAgent()
        results = agent.run_batch([
            {
                "product_id": "p04",
                "metrics": {"roas": 0.3},
                "creative_data": {"fatigue_score": 0.85},
            },
            {
                "product_id": "p05",
                "metrics": {"roas": 1.5, "ctr": 0.05},
                "creative_data": {"fatigue_score": 0.1, "diversity_score": 0.8},
            },
        ])
        assert "p04" in results
        assert "p05" in results
        assert len(results["p04"]["causes"]) > 0
        assert len(results["p05"]["causes"]) == 0

    def test_agent_repr(self):
        agent = AutonomousGrowthAgent()
        r = repr(agent)
        assert "AutonomousGrowthAgent" in r

    def test_custom_components(self):
        agent = AutonomousGrowthAgent(
            runtime=RuntimeManager(),
            perception=PerceptionLayer(),
            reasoning=ReasoningEngine(),
            hypothesis_generator=HypothesisGenerator(),
            decision_adapter=DecisionAdapter(),
        )
        obs = agent.observe("p04", {"roas": 0.3})
        assert obs is not None

    def test_fatigue_detection_in_pipeline(self):
        agent = AutonomousGrowthAgent()
        result = agent.run(
            "p04",
            metrics={"roas": 0.8, "ctr": 0.02},
            creative_data={"fatigue_score": 0.88, "diversity_score": 0.25},
        )
        causes = result["causes"]
        assert any(c.category == "creative_fatigue" for c in causes)


# ── TestIntegration ────────────────────────────────────────


class TestIntegration:
    def test_full_pipeline_fatigue_to_action(self):
        """完整流程：疲劳检测 → 假设 → 决策 → 动作。"""
        agent = AutonomousGrowthAgent()
        result = agent.run(
            "p04",
            metrics={"roas": 0.5, "ctr": 0.015, "cpi": 4.0},
            creative_data={
                "fatigue_score": 0.85,
                "diversity_score": 0.25,
                "winner_ratio": 0.08,
                "active_creatives": 30,
                "winning_creatives": 2,
                "total_creatives": 50,
            },
            auto_act=True,
        )
        assert len(result["causes"]) >= 2  # fatigue + diversity + winner + roas
        assert len(result["hypotheses"]) >= 2
        assert len(result["decisions"]) >= 2
        assert len(result["actions"]) >= 2

    def test_roas_critical_emergency(self):
        """ROAS 危急场景。"""
        agent = AutonomousGrowthAgent()
        result = agent.run(
            "p06",
            metrics={"roas": 0.2, "ctr": 0.005, "cpi": 8.0},
            creative_data={"fatigue_score": 0.9, "diversity_score": 0.15},
            market_data={"trend_score": 0.2, "competition_score": 0.85},
            auto_act=True,
        )
        decisions = result["decisions"]
        # 最高优先级应该是 roas_critical
        top = decisions[0]
        assert top.action_type == "decrease_budget"

    def test_normal_product_no_actions(self):
        """正常产品不产生动作。"""
        agent = AutonomousGrowthAgent()
        result = agent.run(
            "p04",
            metrics={"roas": 1.5, "ctr": 0.04, "cpi": 2.0},
            creative_data={"fatigue_score": 0.1, "diversity_score": 0.7},
            market_data={"trend_score": 0.6, "competition_score": 0.3},
            auto_act=True,
        )
        assert len(result["causes"]) == 0
        assert len(result["actions"]) == 0

    def test_perception_to_reasoning_chain(self):
        """感知 → 推理链路。"""
        pl = PerceptionLayer()
        re = ReasoningEngine()

        obs = pl.perceive("p04", {"roas": 0.3}, creative_data={"fatigue_score": 0.85})
        assert obs.severity in (ObservationSeverity.CRITICAL, ObservationSeverity.FATAL)

        causes = re.analyze(obs)
        assert len(causes) > 0
        assert "roas_critical" in [c.category for c in causes]

    def test_reasoning_to_hypothesis_chain(self):
        """推理 → 假设链路。"""
        re = ReasoningEngine()
        hg = HypothesisGenerator()

        obs = make_observation(fatigue=0.85, roas=0.5)
        causes = re.analyze(obs)
        hypotheses = hg.generate_from_causes(causes, "p04")

        assert len(hypotheses) > 0
        for h in hypotheses:
            assert h.recommended_actions
            assert h.target_module

    def test_hypothesis_to_decision_chain(self):
        """假设 → 决策链路。"""
        hg = HypothesisGenerator()
        da = DecisionAdapter()

        rc = make_root_cause("creative_fatigue", 0.85)
        hypothesis = hg.generate(rc, "p04")
        decision = da.adapt(hypothesis, "OBS_001")

        assert decision.action_type == "mutate_dna"
        assert decision.product_id == "p04"
        assert decision.hypothesis_id == hypothesis.hypothesis_id

    def test_decision_to_action_chain(self):
        """决策 → 动作链路。"""
        agent = AutonomousGrowthAgent()
        decision = AgentDecision(
            product_id="p04",
            action_type="mutate_dna",
            confidence=0.85,
            priority=80,
            target_module="E11_CreativeEvolution",
            parameters={"dna_target": "hook"},
        )
        actions = agent.act([decision])
        assert len(actions) == 1
        assert actions[0].action_type == ActionType.MUTATE_DNA

    def test_batch_run_different_severities(self):
        """不同严重程度的产品应有不同处理。"""
        agent = AutonomousGrowthAgent()
        results = agent.run_batch([
            {
                "product_id": "p04",
                "metrics": {"roas": 0.2},
                "creative_data": {"fatigue_score": 0.9},
            },
            {
                "product_id": "p05",
                "metrics": {"roas": 1.8},
                "creative_data": {"fatigue_score": 0.1},
            },
        ])
        p04_causes = len(results["p04"]["causes"])
        p05_causes = len(results["p05"]["causes"])
        assert p04_causes > p05_causes

    def test_signal_passthrough(self):
        """已知信号透传。"""
        agent = AutonomousGrowthAgent()
        obs = agent.observe("p04", {"roas": 0.5}, signals=["manual_alert"])
        assert "manual_alert" in obs.signals

    def test_perception_layer_repr(self):
        pl = PerceptionLayer()
        pl.perceive("p04")
        r = repr(pl)
        assert "PerceptionLayer" in r