"""E12.6.1 — Meta Decision Engine 测试。

覆盖:
  - Models: MetaDecisionType, DecisionContext, MetaDecision
  - DecisionPolicy: 7 条规则（Fatigue, ROAS Growth, Experiment Failure, Data, Population, Continue, Rollback）
  - DecisionEngine: 评估、排序、风险检查、置信度校准
  - DecisionExplainer: 解释生成、简短解释
  - Integration: Reality → Decision, Decision → E11 action
"""

import pytest
from datetime import datetime, timezone, timedelta

from market_ops.creative_vision_runtime.reality.meta_intelligence.meta_decision import (
    ContinueEvolutionRule,
    DecisionContext,
    DecisionExplainer,
    DecisionPolicy,
    ExperimentFailureRule,
    FatigueRule,
    InsufficientDataRule,
    MetaDecision,
    MetaDecisionEngine,
    MetaDecisionType,
    PopulationDegradationRule,
    RoasGrowthRule,
    RollbackRule,
    get_decision_priority,
)


# ── Helpers ───────────────────────────────────────────────


def make_context(**overrides) -> DecisionContext:
    """创建测试用 DecisionContext。"""
    defaults = {
        "product_id": "p04",
        "active_experiments": 0,
        "recent_roas": 1.0,
        "roas_trend": 0.0,
        "fatigue_score": 0.0,
        "prediction_confidence": 0.0,
        "knowledge_confidence": 0.0,
        "population_diversity": 0.5,
        "spend_last_7d": 0.0,
        "mutation_count": 0,
    }
    defaults.update(overrides)
    return DecisionContext(**defaults)


# ═══════════════════════════════════════════════════════════
# 1. Models (15 tests)
# ═══════════════════════════════════════════════════════════


class TestDecisionModels:
    """E12.6.1 数据模型测试。"""

    def test_decision_type_enum(self):
        """MetaDecisionType 枚举值。"""
        assert MetaDecisionType.ROLLBACK.value == "rollback"
        assert MetaDecisionType.STOP_EXPERIMENT.value == "stop_experiment"
        assert MetaDecisionType.START_EXPERIMENT.value == "start_experiment"
        assert MetaDecisionType.START_LEARNING.value == "start_learning"
        assert MetaDecisionType.CONTINUE_EVOLUTION.value == "continue_evolution"
        assert MetaDecisionType.SCALE_WINNER.value == "scale_winner"
        assert MetaDecisionType.WAIT.value == "wait"

    def test_decision_priority(self):
        """决策优先级排序。"""
        priorities = [
            get_decision_priority(MetaDecisionType.ROLLBACK),
            get_decision_priority(MetaDecisionType.STOP_EXPERIMENT),
            get_decision_priority(MetaDecisionType.START_EXPERIMENT),
            get_decision_priority(MetaDecisionType.WAIT),
        ]
        assert priorities[0] > priorities[1] > priorities[2] > priorities[3]

    def test_context_creation(self):
        """DecisionContext 创建。"""
        ctx = DecisionContext(product_id="p04", fatigue_score=0.85)
        assert ctx.product_id == "p04"
        assert ctx.fatigue_score == 0.85

    def test_context_properties(self):
        """DecisionContext 属性。"""
        ctx = make_context(fatigue_score=0.85, roas_trend=-0.18, population_diversity=0.65)
        assert ctx.is_fatigued
        assert ctx.is_roas_declining
        assert ctx.is_population_healthy

    def test_context_not_fatigued(self):
        """未疲劳判断。"""
        ctx = make_context(fatigue_score=0.50)
        assert not ctx.is_fatigued

    def test_context_roas_growing(self):
        """ROAS 增长判断。"""
        ctx = make_context(roas_trend=0.25)
        assert ctx.is_roas_growing
        assert not ctx.is_roas_declining

    def test_context_population_degraded(self):
        """种群退化判断。"""
        ctx = make_context(population_diversity=0.10)
        assert ctx.is_population_degraded
        assert not ctx.is_population_healthy

    def test_context_has_sufficient_data(self):
        """数据充足判断。"""
        ctx = make_context(prediction_confidence=0.75)
        assert ctx.has_sufficient_data

    def test_context_to_dict(self):
        """DecisionContext to_dict。"""
        ctx = make_context(product_id="p04", fatigue_score=0.85)
        d = ctx.to_dict()
        assert d["product_id"] == "p04"
        assert d["fatigue_score"] == 0.85
        assert d["is_fatigued"] is True

    def test_meta_decision_creation(self):
        """MetaDecision 创建。"""
        d = MetaDecision(
            product_id="p04",
            action=MetaDecisionType.START_EXPERIMENT,
            confidence=0.91,
            reasons=["fatigue detected"],
        )
        assert d.decision_id.startswith("MD_")
        assert d.action == MetaDecisionType.START_EXPERIMENT
        assert d.confidence == 0.91
        assert d.is_actionable
        assert d.is_high_confidence

    def test_meta_decision_not_actionable(self):
        """不可执行决策。"""
        d = MetaDecision(action=MetaDecisionType.WAIT, confidence=0.30)
        assert not d.is_actionable

    def test_meta_decision_is_risky(self):
        """高风险决策。"""
        d1 = MetaDecision(action=MetaDecisionType.ROLLBACK)
        assert d1.is_risky
        d2 = MetaDecision(action=MetaDecisionType.STOP_EXPERIMENT)
        assert d2.is_risky
        d3 = MetaDecision(action=MetaDecisionType.START_EXPERIMENT)
        assert not d3.is_risky

    def test_meta_decision_action_label(self):
        """决策动作标签。"""
        d = MetaDecision(action=MetaDecisionType.START_EXPERIMENT)
        assert "启动新实验" in d.action_label

    def test_meta_decision_to_dict(self):
        """MetaDecision to_dict。"""
        d = MetaDecision(
            product_id="p04",
            action=MetaDecisionType.START_EXPERIMENT,
            confidence=0.91,
            priority=80,
            reasons=["r1", "r2"],
        )
        dd = d.to_dict()
        assert dd["action"] == "start_experiment"
        assert dd["confidence"] == 0.91
        assert dd["reasons"] == ["r1", "r2"]

    def test_meta_decision_repr(self):
        """MetaDecision repr。"""
        d = MetaDecision(action=MetaDecisionType.START_EXPERIMENT, confidence=0.91)
        assert "start_experiment" in repr(d)


# ═══════════════════════════════════════════════════════════
# 2. DecisionPolicy (30 tests)
# ═══════════════════════════════════════════════════════════


class TestFatigueRule:
    """FatigueRule 测试。"""

    def test_triggers_on_high_fatigue(self):
        """高疲劳触发。"""
        rule = FatigueRule()
        ctx = make_context(fatigue_score=0.85, prediction_confidence=0.91)
        decision = rule.evaluate(ctx)
        assert decision is not None
        assert decision.action == MetaDecisionType.START_EXPERIMENT

    def test_no_trigger_low_fatigue(self):
        """低疲劳不触发。"""
        rule = FatigueRule()
        ctx = make_context(fatigue_score=0.50, prediction_confidence=0.91)
        decision = rule.evaluate(ctx)
        assert decision is None

    def test_no_trigger_low_confidence(self):
        """低置信度不触发。"""
        rule = FatigueRule()
        ctx = make_context(fatigue_score=0.85, prediction_confidence=0.40)
        decision = rule.evaluate(ctx)
        assert decision is None

    def test_rule_name(self):
        """规则名称。"""
        rule = FatigueRule()
        assert rule.rule_name == "FatigueRule"


class TestRoasGrowthRule:
    """RoasGrowthRule 测试。"""

    def test_triggers_on_roas_growth(self):
        """ROAS 增长触发。"""
        rule = RoasGrowthRule()
        ctx = make_context(roas_trend=0.25, fatigue_score=0.20, prediction_confidence=0.80)
        decision = rule.evaluate(ctx)
        assert decision is not None
        assert decision.action == MetaDecisionType.SCALE_WINNER

    def test_no_trigger_roas_decline(self):
        """ROAS 下降不触发。"""
        rule = RoasGrowthRule()
        ctx = make_context(roas_trend=-0.10, fatigue_score=0.20)
        decision = rule.evaluate(ctx)
        assert decision is None

    def test_no_trigger_high_fatigue(self):
        """高疲劳不触发（即使 ROAS 增长）。"""
        rule = RoasGrowthRule()
        ctx = make_context(roas_trend=0.25, fatigue_score=0.60)
        decision = rule.evaluate(ctx)
        assert decision is None


class TestExperimentFailureRule:
    """ExperimentFailureRule 测试。"""

    def test_triggers_on_roas_drop(self):
        """ROAS 大幅下降触发。"""
        rule = ExperimentFailureRule()
        ctx = make_context(active_experiments=3, roas_drop_pct=0.35)
        decision = rule.evaluate(ctx)
        assert decision is not None
        assert decision.action == MetaDecisionType.STOP_EXPERIMENT

    def test_triggers_on_roas_trend(self):
        """ROAS 趋势下降触发。"""
        rule = ExperimentFailureRule()
        ctx = make_context(active_experiments=2, roas_trend=-0.25)
        decision = rule.evaluate(ctx)
        assert decision is not None
        assert decision.action == MetaDecisionType.STOP_EXPERIMENT

    def test_no_trigger_no_experiments(self):
        """无实验时不触发。"""
        rule = ExperimentFailureRule()
        ctx = make_context(active_experiments=0, roas_drop_pct=0.40)
        decision = rule.evaluate(ctx)
        assert decision is None

    def test_no_trigger_small_drop(self):
        """小幅下降不触发。"""
        rule = ExperimentFailureRule()
        ctx = make_context(active_experiments=2, roas_drop_pct=0.10, roas_trend=-0.05)
        decision = rule.evaluate(ctx)
        assert decision is None


class TestInsufficientDataRule:
    """InsufficientDataRule 测试。"""

    def test_triggers_on_low_confidence(self):
        """低置信度触发。"""
        rule = InsufficientDataRule()
        ctx = make_context(prediction_confidence=0.30)
        decision = rule.evaluate(ctx)
        assert decision is not None
        assert decision.action == MetaDecisionType.WAIT

    def test_no_trigger_high_confidence(self):
        """高置信度不触发。"""
        rule = InsufficientDataRule()
        ctx = make_context(prediction_confidence=0.80)
        decision = rule.evaluate(ctx)
        assert decision is None


class TestPopulationDegradationRule:
    """PopulationDegradationRule 测试。"""

    def test_triggers_on_low_diversity(self):
        """低多样性触发。"""
        rule = PopulationDegradationRule()
        ctx = make_context(population_diversity=0.10)
        decision = rule.evaluate(ctx)
        assert decision is not None
        assert decision.action == MetaDecisionType.START_LEARNING

    def test_no_trigger_high_diversity(self):
        """高多样性不触发。"""
        rule = PopulationDegradationRule()
        ctx = make_context(population_diversity=0.50)
        decision = rule.evaluate(ctx)
        assert decision is None


class TestContinueEvolutionRule:
    """ContinueEvolutionRule 测试。"""

    def test_triggers_on_healthy_state(self):
        """健康状态触发。"""
        rule = ContinueEvolutionRule()
        ctx = make_context(
            population_diversity=0.50,
            fatigue_score=0.30,
            prediction_confidence=0.75,
        )
        decision = rule.evaluate(ctx)
        assert decision is not None
        assert decision.action == MetaDecisionType.CONTINUE_EVOLUTION

    def test_no_trigger_low_diversity(self):
        """低多样性不触发。"""
        rule = ContinueEvolutionRule()
        ctx = make_context(population_diversity=0.10, fatigue_score=0.30, prediction_confidence=0.75)
        decision = rule.evaluate(ctx)
        assert decision is None

    def test_no_trigger_high_fatigue(self):
        """高疲劳不触发。"""
        rule = ContinueEvolutionRule()
        ctx = make_context(population_diversity=0.50, fatigue_score=0.80, prediction_confidence=0.75)
        decision = rule.evaluate(ctx)
        assert decision is None


class TestRollbackRule:
    """RollbackRule 测试。"""

    def test_triggers_on_critical_decline(self):
        """严重下降触发。"""
        rule = RollbackRule()
        ctx = make_context(roas_trend=-0.40, recent_roas=0.60)
        decision = rule.evaluate(ctx)
        assert decision is not None
        assert decision.action == MetaDecisionType.ROLLBACK

    def test_no_trigger_roas_ok(self):
        """ROAS 正常不触发。"""
        rule = RollbackRule()
        ctx = make_context(roas_trend=-0.40, recent_roas=1.20)
        decision = rule.evaluate(ctx)
        assert decision is None

    def test_no_trigger_trend_ok(self):
        """趋势正常不触发。"""
        rule = RollbackRule()
        ctx = make_context(roas_trend=-0.10, recent_roas=0.60)
        decision = rule.evaluate(ctx)
        assert decision is None


class TestDecisionPolicyBase:
    """DecisionPolicy 基类测试。"""

    def test_policy_repr(self):
        """Policy repr。"""
        rule = FatigueRule()
        assert "FatigueRule" in repr(rule)


# ═══════════════════════════════════════════════════════════
# 3. DecisionEngine (35 tests)
# ═══════════════════════════════════════════════════════════


class TestDecisionEngine:
    """MetaDecisionEngine 测试。"""

    def test_decide_fatigue_scenario(self):
        """疲劳场景决策。"""
        engine = MetaDecisionEngine()
        ctx = make_context(
            fatigue_score=0.85,
            prediction_confidence=0.91,
            population_diversity=0.65,
        )
        decision = engine.decide(ctx)
        assert decision.action == MetaDecisionType.START_EXPERIMENT
        assert decision.confidence > 0.50

    def test_decide_roas_growth_scenario(self):
        """ROAS 增长场景决策。"""
        engine = MetaDecisionEngine()
        ctx = make_context(
            roas_trend=0.25,
            fatigue_score=0.20,
            prediction_confidence=0.80,
            population_diversity=0.25,  # 低于 0.30，避免 ContinueEvolution 触发
        )
        decision = engine.decide(ctx)
        assert decision.action == MetaDecisionType.SCALE_WINNER

    def test_decide_rollback_scenario(self):
        """回滚场景决策。"""
        engine = MetaDecisionEngine()
        ctx = make_context(
            roas_trend=-0.40,
            recent_roas=0.55,
            active_experiments=3,
        )
        decision = engine.decide(ctx)
        assert decision.action == MetaDecisionType.ROLLBACK

    def test_decide_experiment_failure_scenario(self):
        """实验失败场景决策。"""
        engine = MetaDecisionEngine()
        ctx = make_context(
            active_experiments=5,
            roas_drop_pct=0.50,  # 更高以确保置信度通过风险检查
            recent_roas=0.80,
        )
        decision = engine.decide(ctx)
        assert decision.action == MetaDecisionType.STOP_EXPERIMENT

    def test_decide_population_degradation_scenario(self):
        """种群退化场景决策。"""
        engine = MetaDecisionEngine()
        ctx = make_context(
            population_diversity=0.10,
            prediction_confidence=0.70,
        )
        decision = engine.decide(ctx)
        assert decision.action == MetaDecisionType.START_LEARNING

    def test_decide_insufficient_data_scenario(self):
        """数据不足场景决策。"""
        engine = MetaDecisionEngine()
        ctx = make_context(prediction_confidence=0.30)
        decision = engine.decide(ctx)
        assert decision.action == MetaDecisionType.WAIT

    def test_decide_continue_evolution_scenario(self):
        """持续进化场景决策。"""
        engine = MetaDecisionEngine()
        ctx = make_context(
            population_diversity=0.50,
            fatigue_score=0.30,
            prediction_confidence=0.75,
        )
        decision = engine.decide(ctx)
        assert decision.action == MetaDecisionType.CONTINUE_EVOLUTION

    def test_decide_empty_context(self):
        """空上下文返回 WAIT。"""
        engine = MetaDecisionEngine()
        ctx = make_context()
        decision = engine.decide(ctx)
        assert decision is not None
        assert decision.action in (MetaDecisionType.WAIT, MetaDecisionType.CONTINUE_EVOLUTION)

    def test_rollback_wins_over_experiment(self):
        """ROLLBACK 优先级高于 START_EXPERIMENT。"""
        engine = MetaDecisionEngine()
        ctx = make_context(
            roas_trend=-0.40,
            recent_roas=0.55,
            fatigue_score=0.85,
            prediction_confidence=0.91,
            active_experiments=3,
        )
        decision = engine.decide(ctx)
        assert decision.action == MetaDecisionType.ROLLBACK

    def test_stop_experiment_wins_over_start(self):
        """STOP_EXPERIMENT 优先级高于 START_EXPERIMENT。"""
        engine = MetaDecisionEngine()
        ctx = make_context(
            active_experiments=5,
            roas_drop_pct=0.50,  # 更高以确保 STOP 置信度 > 0.40
            fatigue_score=0.85,
            prediction_confidence=0.91,
        )
        decision = engine.decide(ctx)
        assert decision.action == MetaDecisionType.STOP_EXPERIMENT

    def test_evaluate_all(self):
        """evaluate_all 返回所有匹配的决策。"""
        engine = MetaDecisionEngine()
        ctx = make_context(
            fatigue_score=0.85,
            prediction_confidence=0.91,
            population_diversity=0.10,
            active_experiments=3,
            roas_drop_pct=0.35,
        )
        decisions = engine.evaluate_all(ctx)
        assert len(decisions) > 1

    def test_rank_by_priority(self):
        """按优先级排序。"""
        engine = MetaDecisionEngine()
        decisions = [
            MetaDecision(action=MetaDecisionType.WAIT, priority=10),
            MetaDecision(action=MetaDecisionType.ROLLBACK, priority=100),
            MetaDecision(action=MetaDecisionType.START_EXPERIMENT, priority=80),
        ]
        ranked = engine.rank_by_priority(decisions)
        assert ranked[0].action == MetaDecisionType.ROLLBACK
        assert ranked[-1].action == MetaDecisionType.WAIT

    def test_get_top_decisions(self):
        """获取 Top N 决策。"""
        engine = MetaDecisionEngine()
        decisions = [
            MetaDecision(action=MetaDecisionType.ROLLBACK, priority=100, confidence=0.90),
            MetaDecision(action=MetaDecisionType.START_EXPERIMENT, priority=80, confidence=0.85),
            MetaDecision(action=MetaDecisionType.START_LEARNING, priority=70, confidence=0.80),
            MetaDecision(action=MetaDecisionType.WAIT, priority=10, confidence=0.50),
        ]
        top = engine.get_top_decisions(decisions, n=3)
        assert len(top) == 3
        assert top[0].action == MetaDecisionType.ROLLBACK

    def test_risk_check_filters_low_confidence(self):
        """风险检查过滤低置信度决策。"""
        engine = MetaDecisionEngine(risk_confidence_min=0.60)
        decisions = [
            MetaDecision(action=MetaDecisionType.START_EXPERIMENT, confidence=0.91),
            MetaDecision(action=MetaDecisionType.WAIT, confidence=0.30),
        ]
        filtered = engine._risk_check(decisions)
        assert len(filtered) == 1

    def test_is_decision_safe(self):
        """决策安全性判断。"""
        engine = MetaDecisionEngine()
        d1 = MetaDecision(action=MetaDecisionType.START_EXPERIMENT, confidence=0.91)
        d2 = MetaDecision(action=MetaDecisionType.ROLLBACK, confidence=0.50)
        assert engine.is_decision_safe(d1)
        assert not engine.is_decision_safe(d2)

    def test_calibrate_confidence(self):
        """置信度校准。"""
        engine = MetaDecisionEngine()
        ctx = make_context(
            spend_last_7d=10000,
            active_experiments=5,
            mutation_count=10,
            knowledge_confidence=0.80,
            prediction_confidence=0.85,
        )
        decision = MetaDecision(action=MetaDecisionType.START_EXPERIMENT, confidence=0.91)
        calibrated = engine.calibrate_confidence(decision, ctx)
        assert calibrated.confidence > 0.80

    def test_calibrate_confidence_low_data(self):
        """低数据量时置信度降低。"""
        engine = MetaDecisionEngine()
        ctx = make_context()
        decision = MetaDecision(action=MetaDecisionType.START_EXPERIMENT, confidence=0.91)
        calibrated = engine.calibrate_confidence(decision, ctx)
        assert calibrated.confidence < 0.91

    def test_custom_policies(self):
        """自定义策略集。"""
        custom_policies = [FatigueRule()]
        engine = MetaDecisionEngine(policies=custom_policies)
        ctx = make_context(fatigue_score=0.85, prediction_confidence=0.91)
        decision = engine.decide(ctx)
        assert decision.action == MetaDecisionType.START_EXPERIMENT

    def test_engine_repr(self):
        """Engine repr。"""
        engine = MetaDecisionEngine()
        assert "MetaDecisionEngine" in repr(engine)


# ═══════════════════════════════════════════════════════════
# 4. DecisionExplainer (12 tests)
# ═══════════════════════════════════════════════════════════


class TestDecisionExplainer:
    """DecisionExplainer 测试。"""

    def test_explain_start_experiment(self):
        """解释 START_EXPERIMENT。"""
        explainer = DecisionExplainer()
        ctx = make_context(fatigue_score=0.85, prediction_confidence=0.91)
        decision = MetaDecision(
            product_id="p04",
            action=MetaDecisionType.START_EXPERIMENT,
            confidence=0.91,
            reasons=["fatigue detected", "confidence high"],
            expected_impact=0.20,
        )
        explanation = explainer.explain(decision, ctx)
        assert "启动新实验" in explanation
        assert "fatigue" in explanation
        assert "91%" in explanation

    def test_explain_rollback(self):
        """解释 ROLLBACK。"""
        explainer = DecisionExplainer()
        decision = MetaDecision(
            action=MetaDecisionType.ROLLBACK,
            confidence=0.85,
            reasons=["ROAS critical decline"],
            expected_impact=0.20,
        )
        explanation = explainer.explain(decision)
        assert "回滚" in explanation
        assert "ROAS" in explanation

    def test_explain_wait(self):
        """解释 WAIT。"""
        explainer = DecisionExplainer()
        decision = MetaDecision(
            action=MetaDecisionType.WAIT,
            confidence=0.60,
            reasons=["insufficient data"],
        )
        explanation = explainer.explain(decision)
        assert "等待" in explanation
        assert "insufficient" in explanation

    def test_explain_short(self):
        """简短解释。"""
        explainer = DecisionExplainer()
        decision = MetaDecision(
            action=MetaDecisionType.START_EXPERIMENT,
            confidence=0.91,
            reasons=["fatigue detected"],
        )
        short = explainer.explain_short(decision)
        assert "启动新实验" in short
        assert "91%" in short

    def test_explain_with_context(self):
        """带上下文的解释。"""
        explainer = DecisionExplainer()
        ctx = make_context(
            product_id="p04",
            recent_roas=1.25,
            roas_trend=-0.18,
            fatigue_score=0.82,
            population_diversity=0.65,
            active_experiments=3,
            spend_last_7d=10000,
        )
        decision = MetaDecision(
            action=MetaDecisionType.START_EXPERIMENT,
            confidence=0.91,
            reasons=["fatigue"],
        )
        explanation = explainer.explain(decision, ctx)
        assert "p04" in explanation
        assert "1.25" in explanation
        assert "82%" in explanation

    def test_explainer_repr(self):
        """Explainer repr。"""
        explainer = DecisionExplainer()
        assert "DecisionExplainer" in repr(explainer)


# ═══════════════════════════════════════════════════════════
# 5. Integration (20 tests)
# ═══════════════════════════════════════════════════════════


class TestIntegration:
    """集成测试。"""

    def test_fatigue_to_experiment_flow(self):
        """疲劳 → 启动实验 完整流程。"""
        engine = MetaDecisionEngine()
        explainer = DecisionExplainer()
        ctx = make_context(
            product_id="p04",
            fatigue_score=0.87,
            prediction_confidence=0.91,
            population_diversity=0.65,
            active_experiments=2,
            spend_last_7d=15000,
        )
        decision = engine.decide(ctx)
        assert decision.action == MetaDecisionType.START_EXPERIMENT
        explanation = explainer.explain(decision, ctx)
        assert len(explanation) > 100

    def test_roas_decline_to_rollback_flow(self):
        """ROAS 下降 → 回滚 完整流程。"""
        engine = MetaDecisionEngine()
        ctx = make_context(
            product_id="p04",
            roas_trend=-0.45,
            recent_roas=0.55,
            active_experiments=3,
            prediction_confidence=0.80,
        )
        decision = engine.decide(ctx)
        assert decision.action == MetaDecisionType.ROLLBACK

    def test_healthy_to_continue_evolution_flow(self):
        """健康状态 → 持续进化 完整流程。"""
        engine = MetaDecisionEngine()
        ctx = make_context(
            product_id="p04",
            population_diversity=0.55,
            fatigue_score=0.25,
            prediction_confidence=0.80,
            roas_trend=0.05,
        )
        decision = engine.decide(ctx)
        assert decision.action == MetaDecisionType.CONTINUE_EVOLUTION

    def test_decision_has_reasons(self):
        """决策包含理由。"""
        engine = MetaDecisionEngine()
        ctx = make_context(
            fatigue_score=0.85,
            prediction_confidence=0.91,
            active_experiments=2,
        )
        decision = engine.decide(ctx)
        assert len(decision.reasons) > 0

    def test_decision_has_expected_impact(self):
        """决策包含预期影响。"""
        engine = MetaDecisionEngine()
        ctx = make_context(fatigue_score=0.85, prediction_confidence=0.91)
        decision = engine.decide(ctx)
        assert decision.expected_impact > 0

    def test_multi_rule_conflict_priority(self):
        """多规则冲突时优先级正确。"""
        engine = MetaDecisionEngine()
        ctx = make_context(
            roas_trend=-0.40,
            recent_roas=0.55,
            fatigue_score=0.85,
            prediction_confidence=0.91,
            population_diversity=0.10,
            active_experiments=3,
            roas_drop_pct=0.35,
        )
        # ROLLBACK 应该是最优先的
        decision = engine.decide(ctx)
        assert decision.action == MetaDecisionType.ROLLBACK

    def test_decision_context_snapshot(self):
        """决策包含上下文快照。"""
        engine = MetaDecisionEngine()
        ctx = make_context(fatigue_score=0.85, prediction_confidence=0.91)
        decision = engine.decide(ctx)
        assert "fatigue_score" in decision.context_snapshot
        assert decision.context_snapshot["fatigue_score"] == 0.85

    def test_complex_realistic_scenario(self):
        """复杂真实场景。"""
        engine = MetaDecisionEngine()
        ctx = DecisionContext(
            product_id="P04",
            active_experiments=5,
            recent_roas=1.25,
            roas_trend=-0.18,
            fatigue_score=0.82,
            prediction_confidence=0.91,
            knowledge_confidence=0.85,
            population_diversity=0.65,
            spend_last_7d=25000,
            mutation_count=15,
            ctr_trend=-0.12,
            roas_drop_pct=0.0,
            experiment_success_rate=0.60,
            budget_remaining=50000,
            market_condition="stable",
        )
        decision = engine.decide(ctx)
        assert decision is not None
        assert decision.action in (
            MetaDecisionType.START_EXPERIMENT,
            MetaDecisionType.STOP_EXPERIMENT,
        )

    def test_decision_to_dict_for_e11(self):
        """决策转换为 E11 可用的格式。"""
        engine = MetaDecisionEngine()
        ctx = make_context(fatigue_score=0.85, prediction_confidence=0.91)
        decision = engine.decide(ctx)
        d = decision.to_dict()
        assert "action" in d
        assert "confidence" in d
        assert "priority" in d
        assert "is_actionable" in d


# ═══════════════════════════════════════════════════════════
# 6. Edge Cases (10 tests)
# ═══════════════════════════════════════════════════════════


class TestEdgeCases:
    """边界情况测试。"""

    def test_context_all_max_values(self):
        """所有值最大。"""
        ctx = DecisionContext(
            product_id="p04",
            active_experiments=100,
            recent_roas=10.0,
            roas_trend=1.0,
            fatigue_score=1.0,
            prediction_confidence=1.0,
            knowledge_confidence=1.0,
            population_diversity=1.0,
            spend_last_7d=1000000,
            mutation_count=1000,
            roas_drop_pct=1.0,
        )
        engine = MetaDecisionEngine()
        decision = engine.decide(ctx)
        assert decision is not None

    def test_context_all_min_values(self):
        """所有值最小。"""
        ctx = DecisionContext(
            product_id="",
            active_experiments=0,
            recent_roas=0.0,
            roas_trend=-1.0,
            fatigue_score=0.0,
            prediction_confidence=0.0,
            knowledge_confidence=0.0,
            population_diversity=0.0,
            spend_last_7d=0.0,
            mutation_count=0,
            roas_drop_pct=0.0,
        )
        engine = MetaDecisionEngine()
        decision = engine.decide(ctx)
        assert decision is not None

    def test_engine_with_no_policies(self):
        """无策略引擎。"""
        engine = MetaDecisionEngine(policies=[])
        ctx = make_context(fatigue_score=0.85)
        decision = engine.decide(ctx)
        assert decision.action == MetaDecisionType.WAIT

    def test_fatigue_at_boundary(self):
        """疲劳度边界值。"""
        rule = FatigueRule()
        ctx = make_context(fatigue_score=0.80, prediction_confidence=0.80)
        decision = rule.evaluate(ctx)
        assert decision is not None

    def test_fatigue_just_below_boundary(self):
        """疲劳度正好低于边界。"""
        rule = FatigueRule()
        ctx = make_context(fatigue_score=0.79, prediction_confidence=0.91)
        decision = rule.evaluate(ctx)
        assert decision is None

    def test_roas_growth_at_boundary(self):
        """ROAS 增长边界值。"""
        rule = RoasGrowthRule()
        ctx = make_context(roas_trend=0.15, fatigue_score=0.20)
        decision = rule.evaluate(ctx)
        assert decision is None  # 0.15 不大于 0.15

    def test_rollback_just_below(self):
        """回滚正好低于边界。"""
        rule = RollbackRule()
        ctx = make_context(roas_trend=-0.30, recent_roas=0.70)
        decision = rule.evaluate(ctx)
        assert decision is None  # -0.30 不小于 -0.30

    def test_empty_decision_reasons(self):
        """空理由决策。"""
        d = MetaDecision(action=MetaDecisionType.WAIT)
        assert d.reasons == []
        assert d.is_actionable is False

    def test_decision_priority_zero(self):
        """优先级为 0 的决策。"""
        d = MetaDecision(action=MetaDecisionType.WAIT)
        assert d.priority == 10  # WAIT 优先级为 10

    def test_engine_default_handles_none_context(self):
        """引擎处理极端上下文。"""
        engine = MetaDecisionEngine()
        ctx = DecisionContext()
        decision = engine.decide(ctx)
        assert decision is not None
        assert isinstance(decision, MetaDecision)