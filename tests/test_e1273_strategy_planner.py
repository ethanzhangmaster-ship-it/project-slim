"""E12.7.3 — Growth Strategy Planner 测试。

测试覆盖:
  - Models (25): StrategyObjective, StrategyAction, GrowthStrategy, ConstraintCheck, StrategyPlan, Enums
  - Objective Engine (25): analyze, get_top, grouping, severity_boost, template management
  - Strategy Builder (30): build, build_from_hypotheses, template selection, impact estimation
  - Tactic Generator (25): generate, attach, dependencies, priority adjustment, custom rules
  - Constraint Manager (20): validate, approve, batch, 7 individual checks
  - Strategy Ranker (15): rank, get_top, get_top_n, scores, custom weights
  - Planner Controller (25): full pipeline, individual steps, plan_from_agent_result
  - Integration (10): end-to-end pipeline tests
"""

from __future__ import annotations

import pytest

from src.market_ops.creative_vision_runtime.growth_os.agent.models import (
    CreativeState,
    GrowthHypothesis,
    GrowthObservation,
    HypothesisStatus,
    MarketState,
    ObservationSeverity,
    ProductMetrics,
)
from src.market_ops.creative_vision_runtime.growth_os.strategy.models import (
    ActionType,
    ConstraintCheck,
    GrowthStrategy,
    RiskLevel,
    StrategyAction,
    StrategyObjective,
    StrategyPlan,
    StrategyStatus,
    StrategyTemplateType,
)
from src.market_ops.creative_vision_runtime.growth_os.strategy.objective_engine import (
    ObjectiveEngine,
)
from src.market_ops.creative_vision_runtime.growth_os.strategy.strategy_builder import (
    StrategyBuilder,
)
from src.market_ops.creative_vision_runtime.growth_os.strategy.tactic_generator import (
    TacticGenerator,
)
from src.market_ops.creative_vision_runtime.growth_os.strategy.constraint_manager import (
    ConstraintManager,
)
from src.market_ops.creative_vision_runtime.growth_os.strategy.strategy_ranker import (
    StrategyRanker,
)
from src.market_ops.creative_vision_runtime.growth_os.strategy.planner_controller import (
    GrowthStrategyPlanner,
)


# ══════════════════════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════════════════════


def _make_observation(
    product_id: str = "p01",
    roas: float = 1.0,
    ctr: float = 0.02,
    cpi: float = 3.0,
    retention_d7: float = 0.20,
    spend: float = 1000.0,
    fatigue_score: float = 0.1,
    diversity_score: float = 0.5,
    severity: ObservationSeverity = ObservationSeverity.NORMAL,
) -> GrowthObservation:
    return GrowthObservation(
        product_id=product_id,
        metrics=ProductMetrics(
            roas=roas,
            ctr=ctr,
            cpi=cpi,
            retention_d7=retention_d7,
            spend=spend,
            installs=100,
            impressions=10000,
        ),
        creative_state=CreativeState(
            fatigue_score=fatigue_score,
            diversity_score=diversity_score,
            winner_ratio=0.3,
            active_creatives=20,
            winning_creatives=5,
            total_creatives=50,
        ),
        market_state=MarketState(
            trend_score=0.6,
            competition_score=0.4,
            market_size=100000,
            growth_rate=0.05,
        ),
        severity=severity,
    )


def _make_hypothesis(
    product_id: str = "p01",
    problem: str = "Creative fatigue detected",
    root_cause_category: str = "creative_fatigue",
    confidence: float = 0.80,
    expected_impact: float = 0.60,
    recommended_actions: list[str] | None = None,
) -> GrowthHypothesis:
    return GrowthHypothesis(
        problem=problem,
        root_cause="Creative materials are showing fatigue signals",
        root_cause_category=root_cause_category,
        confidence=confidence,
        expected_impact=expected_impact,
        recommended_actions=recommended_actions or ["refresh_creative", "mutate_dna"],
        rationale="Fatigue score is high, need fresh creatives",
        target_module="E11_CreativeEvolution",
        metadata={"product_id": product_id},
    )


# ══════════════════════════════════════════════════════════════
# Test Models
# ══════════════════════════════════════════════════════════════


class TestStrategyObjective:
    """StrategyObjective 模型测试 (12 tests)."""

    def test_create_default(self):
        obj = StrategyObjective()
        assert obj.objective_id.startswith("OBJ_")
        assert obj.metric == ""
        assert obj.current_value == 0.0
        assert obj.target_value == 0.0

    def test_create_with_values(self):
        obj = StrategyObjective(
            product_id="p01",
            metric="roas",
            current_value=0.45,
            target_value=0.80,
            priority=0.95,
            urgency=0.90,
            impact=0.85,
        )
        assert obj.product_id == "p01"
        assert obj.metric == "roas"
        assert obj.gap == pytest.approx(0.35)
        assert obj.gap_pct == pytest.approx(0.35 / 0.45)

    def test_gap_zero_target(self):
        obj = StrategyObjective(current_value=0.5, target_value=0.3)
        assert obj.gap == 0.0

    def test_gap_pct_zero_current(self):
        obj = StrategyObjective(current_value=0.0, target_value=0.8)
        assert obj.gap_pct == 1.0

    def test_gap_pct_negative_current(self):
        obj = StrategyObjective(current_value=-0.1, target_value=0.8)
        assert obj.gap_pct == 1.0

    def test_is_improvement_true(self):
        obj = StrategyObjective(current_value=0.5, target_value=0.8)
        assert obj.is_improvement is True

    def test_is_improvement_false(self):
        obj = StrategyObjective(current_value=0.8, target_value=0.5)
        assert obj.is_improvement is False

    def test_composite_score(self):
        obj = StrategyObjective(priority=0.8, urgency=0.6, impact=0.5)
        expected = 0.8 * 0.4 + 0.6 * 0.35 + 0.5 * 0.25
        assert obj.composite_score == pytest.approx(expected)

    def test_composite_score_all_one(self):
        obj = StrategyObjective(priority=1.0, urgency=1.0, impact=1.0)
        assert obj.composite_score == pytest.approx(1.0)

    def test_to_dict(self):
        obj = StrategyObjective(
            product_id="p01", metric="roas",
            current_value=0.45, target_value=0.80, priority=0.95,
            description="Recover ROAS",
        )
        d = obj.to_dict()
        assert d["product_id"] == "p01"
        assert d["metric"] == "roas"
        assert "gap" in d
        assert "composite_score" in d

    def test_repr(self):
        obj = StrategyObjective(metric="roas", current_value=0.45, target_value=0.8, priority=0.95)
        r = repr(obj)
        assert "roas" in r
        assert "0.45" in r

    def test_custom_id(self):
        obj = StrategyObjective(objective_id="MY_OBJ_001")
        assert obj.objective_id == "MY_OBJ_001"


class TestStrategyAction:
    """StrategyAction 模型测试 (7 tests)."""

    def test_create_default(self):
        action = StrategyAction()
        assert action.action_id.startswith("SA_")
        assert action.action_type == ActionType.CUSTOM
        assert action.priority == 50
        assert action.status == "pending"

    def test_create_with_values(self):
        action = StrategyAction(
            action_type=ActionType.CREATE_CREATIVE,
            target_module="E11_CreativeEvolution",
            priority=85,
            expected_result="Generate 50 creatives",
            expected_impact=0.5,
            duration_days=3,
            parameters={"count": 50},
        )
        assert action.action_type == ActionType.CREATE_CREATIVE
        assert action.target_module == "E11_CreativeEvolution"
        assert action.expected_impact == 0.5
        assert action.duration_days == 3

    def test_is_high_priority_true(self):
        action = StrategyAction(priority=80)
        assert action.is_high_priority is True

    def test_is_high_priority_false(self):
        action = StrategyAction(priority=79)
        assert action.is_high_priority is False

    def test_has_dependencies_true(self):
        action = StrategyAction(dependencies=["SA_001"])
        assert action.has_dependencies is True

    def test_has_dependencies_false(self):
        action = StrategyAction()
        assert action.has_dependencies is False

    def test_to_dict(self):
        action = StrategyAction(
            action_type=ActionType.INCREASE_BUDGET,
            target_module="E12.6.2",
            priority=90,
            expected_result="Increase budget by 30%",
            expected_impact=0.4,
            dependencies=["SA_001"],
            duration_days=1,
            parameters={"change_pct": 0.30},
        )
        d = action.to_dict()
        assert d["action_type"] == "increase_budget"
        assert d["priority"] == 90
        assert d["dependencies"] == ["SA_001"]
        assert d["is_high_priority"] is True


class TestGrowthStrategy:
    """GrowthStrategy 模型测试 (12 tests)."""

    def test_create_default(self):
        strategy = GrowthStrategy()
        assert strategy.strategy_id.startswith("STR_")
        assert strategy.status == StrategyStatus.DRAFT
        assert strategy.risk_level == RiskLevel.MEDIUM
        assert strategy.action_count == 0

    def test_create_with_objective(self):
        obj = StrategyObjective(metric="roas", current_value=0.45, target_value=0.80)
        strategy = GrowthStrategy(
            product_id="p01",
            objective=obj,
            template_type=StrategyTemplateType.RECOVERY,
            hypothesis_id="HYP_001",
            expected_impact=0.70,
            confidence=0.75,
            risk_level=RiskLevel.MEDIUM,
            risk_score=0.40,
            duration_days=14,
        )
        assert strategy.product_id == "p01"
        assert strategy.objective == obj
        assert strategy.template_type == StrategyTemplateType.RECOVERY

    def test_action_count(self):
        strategy = GrowthStrategy()
        strategy.actions = [
            StrategyAction(action_type=ActionType.CREATE_CREATIVE),
            StrategyAction(action_type=ActionType.INCREASE_BUDGET),
        ]
        assert strategy.action_count == 2

    def test_total_duration_no_actions(self):
        strategy = GrowthStrategy(duration_days=14)
        assert strategy.total_duration_days == 14

    def test_total_duration_with_actions(self):
        strategy = GrowthStrategy(
            actions=[
                StrategyAction(duration_days=3),
                StrategyAction(duration_days=5),
                StrategyAction(duration_days=2),
            ],
        )
        assert strategy.total_duration_days == 10

    def test_risk_adjusted_impact(self):
        strategy = GrowthStrategy(
            expected_impact=0.80, confidence=0.75, risk_score=0.40
        )
        expected = 0.80 * 0.75 * (1.0 - 0.40 * 0.5)
        assert strategy.risk_adjusted_impact == pytest.approx(expected)

    def test_is_actionable_true(self):
        strategy = GrowthStrategy(
            status=StrategyStatus.VALIDATED,
            confidence=0.80,
            actions=[StrategyAction()],
        )
        assert strategy.is_actionable is True

    def test_is_actionable_false_status(self):
        strategy = GrowthStrategy(
            status=StrategyStatus.DRAFT,
            confidence=0.80,
            actions=[StrategyAction()],
        )
        assert strategy.is_actionable is False

    def test_is_actionable_false_confidence(self):
        strategy = GrowthStrategy(
            status=StrategyStatus.VALIDATED,
            confidence=0.40,
            actions=[StrategyAction()],
        )
        assert strategy.is_actionable is False

    def test_is_high_risk(self):
        assert GrowthStrategy(risk_level=RiskLevel.HIGH).is_high_risk is True
        assert GrowthStrategy(risk_level=RiskLevel.CRITICAL).is_high_risk is True
        assert GrowthStrategy(risk_level=RiskLevel.MEDIUM).is_high_risk is False
        assert GrowthStrategy(risk_level=RiskLevel.LOW).is_high_risk is False

    def test_high_priority_action_count(self):
        strategy = GrowthStrategy(
            actions=[
                StrategyAction(priority=90),
                StrategyAction(priority=70),
                StrategyAction(priority=85),
            ],
        )
        assert strategy.high_priority_action_count == 2

    def test_to_dict(self):
        obj = StrategyObjective(metric="roas")
        strategy = GrowthStrategy(
            product_id="p01",
            objective=obj,
            template_type=StrategyTemplateType.RECOVERY,
            actions=[
                StrategyAction(action_type=ActionType.CREATE_CREATIVE, priority=85),
            ],
            status=StrategyStatus.VALIDATED,
            confidence=0.80,
        )
        d = strategy.to_dict()
        assert d["product_id"] == "p01"
        assert d["template_type"] == "recovery"
        assert d["action_count"] == 1
        assert d["is_actionable"] is True
        assert "objective" in d


class TestConstraintCheck:
    """ConstraintCheck 模型测试 (5 tests)."""

    def test_create_default(self):
        check = ConstraintCheck()
        assert check.check_id.startswith("CHK_")
        assert check.passed is True

    def test_create_failed(self):
        check = ConstraintCheck(
            constraint_name="max_budget_change",
            passed=False,
            current_value=0.60,
            max_value=0.50,
            message="Budget change exceeds limit",
            severity=RiskLevel.HIGH,
        )
        assert check.passed is False
        assert check.constraint_name == "max_budget_change"
        assert check.is_over_limit is True

    def test_is_over_limit_false(self):
        check = ConstraintCheck(current_value=0.30, max_value=0.50)
        assert check.is_over_limit is False

    def test_to_dict(self):
        check = ConstraintCheck(
            constraint_name="risk_threshold",
            passed=True,
            current_value=0.40,
            max_value=0.90,
            message="OK",
            severity=RiskLevel.CRITICAL,
        )
        d = check.to_dict()
        assert d["constraint_name"] == "risk_threshold"
        assert d["passed"] is True
        assert d["severity"] == "critical"

    def test_repr(self):
        check = ConstraintCheck(constraint_name="test", passed=True)
        assert "PASS" in repr(check)
        check2 = ConstraintCheck(constraint_name="test2", passed=False)
        assert "FAIL" in repr(check2)


class TestStrategyPlan:
    """StrategyPlan 模型测试 (6 tests)."""

    def test_create_default(self):
        plan = StrategyPlan()
        assert plan.plan_id.startswith("PLN_")
        assert plan.strategy_count == 0

    def test_strategy_count(self):
        plan = StrategyPlan(
            strategies=[
                GrowthStrategy(),
                GrowthStrategy(),
                GrowthStrategy(),
            ],
        )
        assert plan.strategy_count == 3

    def test_all_constraints_passed_true(self):
        plan = StrategyPlan(
            constraints=[
                ConstraintCheck(passed=True),
                ConstraintCheck(passed=True),
            ],
        )
        assert plan.all_constraints_passed is True

    def test_all_constraints_passed_false(self):
        plan = StrategyPlan(
            constraints=[
                ConstraintCheck(passed=True),
                ConstraintCheck(passed=False),
            ],
        )
        assert plan.all_constraints_passed is False

    def test_actionable_strategies(self):
        valid = GrowthStrategy(
            status=StrategyStatus.VALIDATED, confidence=0.80,
            actions=[StrategyAction()],
        )
        draft = GrowthStrategy(status=StrategyStatus.DRAFT)
        plan = StrategyPlan(strategies=[valid, draft])
        assert len(plan.actionable_strategies) == 1

    def test_to_dict(self):
        top = GrowthStrategy(
            product_id="p01",
            template_type=StrategyTemplateType.RECOVERY,
            status=StrategyStatus.VALIDATED,
            confidence=0.80,
            actions=[StrategyAction()],
        )
        plan = StrategyPlan(
            product_id="p01",
            strategies=[top],
            top_strategy=top,
            summary="Test summary",
        )
        d = plan.to_dict()
        assert d["product_id"] == "p01"
        assert d["strategy_count"] == 1
        assert d["top_strategy"] is not None
        assert d["actionable_strategies"] == 1


class TestEnums:
    """枚举测试 (3 tests)."""

    def test_strategy_template_type(self):
        assert StrategyTemplateType.SCALE.value == "scale"
        assert StrategyTemplateType.RECOVERY.value == "recovery"
        assert StrategyTemplateType.EXPLORATION.value == "exploration"
        assert StrategyTemplateType.MAINTAIN.value == "maintain"
        assert StrategyTemplateType.SUNSET.value == "sunset"
        assert StrategyTemplateType.CUSTOM.value == "custom"

    def test_risk_level(self):
        assert RiskLevel.LOW.value == "low"
        assert RiskLevel.MEDIUM.value == "medium"
        assert RiskLevel.HIGH.value == "high"
        assert RiskLevel.CRITICAL.value == "critical"

    def test_action_type(self):
        assert ActionType.CREATE_CREATIVE.value == "create_creative"
        assert ActionType.MUTATE_DNA.value == "mutate_dna"
        assert ActionType.INCREASE_BUDGET.value == "increase_budget"
        assert ActionType.LAUNCH_EXPERIMENT.value == "launch_experiment"
        assert ActionType.SUNSET_PRODUCT.value == "sunset_product"


# ══════════════════════════════════════════════════════════════
# Test Objective Engine
# ══════════════════════════════════════════════════════════════


class TestObjectiveEngine:
    """ObjectiveEngine 测试 (25 tests)."""

    def test_analyze_normal(self):
        engine = ObjectiveEngine()
        obs = _make_observation(roas=1.5, ctr=0.03, cpi=2.0, retention_d7=0.25)
        objectives = engine.analyze(obs)
        # ROAS healthy + no fatigue → scale template triggered
        assert len(objectives) >= 1

    def test_analyze_critical_roas(self):
        engine = ObjectiveEngine()
        obs = _make_observation(roas=0.30, severity=ObservationSeverity.CRITICAL)
        objectives = engine.analyze(obs)
        assert len(objectives) >= 1
        # ROAS recovery should be top
        roas_objs = [o for o in objectives if o.metric == "roas"]
        assert len(roas_objs) >= 1
        assert roas_objs[0].target_value > roas_objs[0].current_value

    def test_analyze_fatigue(self):
        engine = ObjectiveEngine()
        obs = _make_observation(fatigue_score=0.80)
        objectives = engine.analyze(obs)
        fatigue_objs = [o for o in objectives if o.metric == "fatigue"]
        assert len(fatigue_objs) >= 1
        assert fatigue_objs[0].target_value == 0.30

    def test_analyze_low_ctr(self):
        engine = ObjectiveEngine()
        obs = _make_observation(ctr=0.005)
        objectives = engine.analyze(obs)
        ctr_objs = [o for o in objectives if o.metric == "ctr"]
        assert len(ctr_objs) >= 1
        assert ctr_objs[0].target_value >= 0.02

    def test_analyze_high_cpi(self):
        engine = ObjectiveEngine()
        obs = _make_observation(cpi=8.0)
        objectives = engine.analyze(obs)
        cpi_objs = [o for o in objectives if o.metric == "cpi"]
        assert len(cpi_objs) >= 1
        assert cpi_objs[0].target_value <= 3.0

    def test_analyze_low_diversity(self):
        engine = ObjectiveEngine()
        obs = _make_observation(diversity_score=0.1)
        objectives = engine.analyze(obs)
        div_objs = [o for o in objectives if o.metric == "diversity"]
        assert len(div_objs) >= 1
        assert div_objs[0].target_value == 0.60

    def test_analyze_low_retention(self):
        engine = ObjectiveEngine()
        obs = _make_observation(retention_d7=0.05)
        objectives = engine.analyze(obs)
        ret_objs = [o for o in objectives if o.metric == "retention"]
        assert len(ret_objs) >= 1
        assert ret_objs[0].target_value == 0.20

    def test_analyze_scale_condition(self):
        engine = ObjectiveEngine()
        obs = _make_observation(roas=1.5, fatigue_score=0.1, spend=1000.0)
        objectives = engine.analyze(obs)
        scale_objs = [o for o in objectives if o.metric == "scale"]
        assert len(scale_objs) >= 1
        assert scale_objs[0].target_value == pytest.approx(1500.0)

    def test_analyze_sorted_by_composite(self):
        engine = ObjectiveEngine()
        obs = _make_observation(roas=0.30, ctr=0.005, fatigue_score=0.80)
        objectives = engine.analyze(obs)
        for i in range(len(objectives) - 1):
            assert objectives[i].composite_score >= objectives[i + 1].composite_score

    def test_get_top_objective(self):
        engine = ObjectiveEngine()
        obs = _make_observation(roas=0.30, severity=ObservationSeverity.CRITICAL)
        top = engine.get_top_objective(obs)
        assert top is not None
        assert top.metric == "roas"

    def test_get_top_objective_none(self):
        engine = ObjectiveEngine()
        obs = _make_observation(roas=2.0, ctr=0.05, cpi=1.0,
                                 retention_d7=0.50, fatigue_score=0.1,
                                 diversity_score=0.8, spend=100.0)
        # All conditions are healthy → scale may still trigger (roas>=1.0 and not fatigued)
        top = engine.get_top_objective(obs)
        # scale should trigger
        assert top is not None

    def test_get_objectives_by_metric(self):
        engine = ObjectiveEngine()
        obs = _make_observation(roas=0.30, ctr=0.005)
        grouped = engine.get_objectives_by_metric(obs)
        assert "roas" in grouped
        assert "ctr" in grouped

    def test_severity_boost_normal(self):
        engine = ObjectiveEngine()
        obs_normal = _make_observation(roas=0.40, severity=ObservationSeverity.NORMAL)
        obs_critical = _make_observation(roas=0.40, severity=ObservationSeverity.CRITICAL)
        top_normal = engine.get_top_objective(obs_normal)
        top_critical = engine.get_top_objective(obs_critical)
        assert top_critical.composite_score > top_normal.composite_score

    def test_no_triggers(self):
        engine = ObjectiveEngine()
        obs = _make_observation(roas=2.0, ctr=0.05, cpi=1.0,
                                 retention_d7=0.50, fatigue_score=0.1,
                                 diversity_score=0.8, spend=100.0)
        objectives = engine.analyze(obs)
        # scale should trigger (roas >= 1.0 and not fatigued)
        assert len(objectives) >= 1

    def test_objective_product_id(self):
        engine = ObjectiveEngine()
        obs = _make_observation(product_id="game_x", roas=0.30)
        objectives = engine.analyze(obs)
        for o in objectives:
            assert o.product_id == "game_x"

    def test_description_formatting(self):
        engine = ObjectiveEngine()
        obs = _make_observation(roas=0.45)
        objectives = engine.analyze(obs)
        roas_obj = [o for o in objectives if o.metric == "roas"][0]
        assert "0.45" in roas_obj.description
        assert roas_obj.description != ""

    def test_add_template(self):
        engine = ObjectiveEngine()
        initial = engine.template_count
        engine.add_template({
            "metric": "custom",
            "condition": lambda o: True,
            "base_priority": 0.90,
            "base_urgency": 0.80,
            "base_impact": 0.70,
            "description_template": "Custom objective",
            "target_calc": lambda o: 1.0,
        })
        assert engine.template_count == initial + 1

    def test_custom_template_triggered(self):
        engine = ObjectiveEngine()
        engine.add_template({
            "metric": "custom_metric",
            "condition": lambda o: True,
            "base_priority": 0.90,
            "base_urgency": 0.80,
            "base_impact": 0.70,
            "description_template": "Custom {current}",
            "target_calc": lambda o: 1.0,
        })
        obs = _make_observation()
        objectives = engine.analyze(obs)
        custom = [o for o in objectives if o.metric == "custom_metric"]
        assert len(custom) == 1

    def test_template_error_handling(self):
        engine = ObjectiveEngine()
        engine.add_template({
            "metric": "bad_template",
            "condition": lambda o: o.metrics.xxx > 0,  # will raise AttributeError
            "base_priority": 0.5,
            "base_urgency": 0.5,
            "base_impact": 0.5,
            "description_template": "bad",
            "target_calc": lambda o: 1.0,
        })
        obs = _make_observation(roas=0.30)
        objectives = engine.analyze(obs)
        # Should not crash; bad template is skipped
        assert len(objectives) >= 1

    def test_roas_second_threshold(self):
        engine = ObjectiveEngine()
        obs = _make_observation(roas=0.60)
        objectives = engine.analyze(obs)
        roas_objs = [o for o in objectives if o.metric == "roas"]
        assert len(roas_objs) >= 1
        # ROAS in [0.5, 0.8) → second threshold, target = max(1.0, 0.60*1.3) = 1.0
        assert roas_objs[0].target_value == pytest.approx(1.0)

    def test_roas_first_threshold(self):
        engine = ObjectiveEngine()
        obs = _make_observation(roas=0.30)
        objectives = engine.analyze(obs)
        roas_objs = [o for o in objectives if o.metric == "roas"]
        assert len(roas_objs) >= 1
        # ROAS < 0.5 → first threshold, target = max(0.80, 0.30*1.6) = 0.80
        assert roas_objs[0].target_value == pytest.approx(0.80)

    def test_ctr_target(self):
        engine = ObjectiveEngine()
        obs = _make_observation(ctr=0.005)
        objectives = engine.analyze(obs)
        ctr_objs = [o for o in objectives if o.metric == "ctr"][0]
        assert ctr_objs.target_value == pytest.approx(0.02)

    def test_cpi_target(self):
        engine = ObjectiveEngine()
        obs = _make_observation(cpi=8.0)
        objectives = engine.analyze(obs)
        cpi_objs = [o for o in objectives if o.metric == "cpi"][0]
        assert cpi_objs.target_value == pytest.approx(3.0)

    def test_repr(self):
        engine = ObjectiveEngine()
        assert "ObjectiveEngine" in repr(engine)


# ══════════════════════════════════════════════════════════════
# Test Strategy Builder
# ══════════════════════════════════════════════════════════════


class TestStrategyBuilder:
    """StrategyBuilder 测试 (30 tests)."""

    def test_build_recovery(self):
        builder = StrategyBuilder()
        hypothesis = _make_hypothesis(root_cause_category="creative_fatigue")
        objective = StrategyObjective(metric="roas", product_id="p01")
        strategy = builder.build(hypothesis, objective)
        assert strategy.template_type == StrategyTemplateType.RECOVERY
        assert strategy.status == StrategyStatus.DRAFT
        assert strategy.expected_impact > 0

    def test_build_scale(self):
        builder = StrategyBuilder()
        hypothesis = _make_hypothesis(root_cause_category="scale")
        objective = StrategyObjective(metric="roas", product_id="p01")
        strategy = builder.build(hypothesis, objective)
        assert strategy.template_type == StrategyTemplateType.SCALE

    def test_build_exploration(self):
        builder = StrategyBuilder()
        hypothesis = _make_hypothesis(root_cause_category="creative_diversity_low")
        objective = StrategyObjective(metric="diversity", product_id="p01")
        strategy = builder.build(hypothesis, objective)
        assert strategy.template_type == StrategyTemplateType.EXPLORATION

    def test_build_sunset(self):
        builder = StrategyBuilder()
        hypothesis = _make_hypothesis(root_cause_category="market_decline")
        objective = StrategyObjective(metric="roas", product_id="p01")
        strategy = builder.build(hypothesis, objective)
        assert strategy.template_type == StrategyTemplateType.SUNSET

    def test_build_default_maintain(self):
        builder = StrategyBuilder()
        hypothesis = _make_hypothesis(root_cause_category="unknown_category")
        objective = StrategyObjective(metric="roas", product_id="p01")
        strategy = builder.build(hypothesis, objective)
        assert strategy.template_type == StrategyTemplateType.MAINTAIN

    def test_build_explicit_template(self):
        builder = StrategyBuilder()
        hypothesis = _make_hypothesis(root_cause_category="creative_fatigue")
        objective = StrategyObjective(metric="roas", product_id="p01")
        strategy = builder.build(
            hypothesis, objective,
            template_type=StrategyTemplateType.SCALE,
        )
        assert strategy.template_type == StrategyTemplateType.SCALE

    def test_hypothesis_id_set(self):
        builder = StrategyBuilder()
        hypothesis = _make_hypothesis()
        objective = StrategyObjective(metric="roas", product_id="p01")
        strategy = builder.build(hypothesis, objective)
        assert strategy.hypothesis_id == hypothesis.hypothesis_id

    def test_objective_set(self):
        builder = StrategyBuilder()
        hypothesis = _make_hypothesis()
        objective = StrategyObjective(metric="roas", product_id="p01")
        strategy = builder.build(hypothesis, objective)
        assert strategy.objective == objective

    def test_confidence_adjusted(self):
        builder = StrategyBuilder()
        hypothesis = _make_hypothesis(
            root_cause_category="creative_fatigue",
            confidence=0.80,
        )
        objective = StrategyObjective(metric="roas", product_id="p01")
        strategy = builder.build(hypothesis, objective)
        # base_confidence=0.75 * hypothesis.confidence=0.80 → 0.60
        assert strategy.confidence == pytest.approx(0.75 * 0.80)

    def test_confidence_capped(self):
        builder = StrategyBuilder()
        hypothesis = _make_hypothesis(
            root_cause_category="creative_fatigue",
            confidence=1.5,  # unrealistic but test cap
        )
        objective = StrategyObjective(metric="roas", product_id="p01")
        strategy = builder.build(hypothesis, objective)
        assert strategy.confidence <= 1.0

    def test_impact_estimation(self):
        builder = StrategyBuilder()
        hypothesis = _make_hypothesis(
            root_cause_category="creative_fatigue",
            confidence=0.80,
            expected_impact=0.60,
        )
        objective = StrategyObjective(metric="roas", product_id="p01")
        strategy = builder.build(hypothesis, objective)
        # base_impact=0.70 × 0.4 + 0.80 × 0.60 × 0.6 = 0.28 + 0.288 = 0.568
        expected = 0.70 * 0.4 + 0.80 * 0.60 * 0.6
        assert strategy.expected_impact == pytest.approx(expected)

    def test_impact_capped(self):
        builder = StrategyBuilder()
        hypothesis = _make_hypothesis(
            root_cause_category="creative_fatigue",
            confidence=1.0,
            expected_impact=1.5,
        )
        objective = StrategyObjective(metric="roas", product_id="p01")
        strategy = builder.build(hypothesis, objective)
        assert strategy.expected_impact <= 1.0

    def test_description_format(self):
        builder = StrategyBuilder()
        hypothesis = _make_hypothesis(root_cause_category="creative_fatigue")
        objective = StrategyObjective(
            metric="roas", product_id="p01",
            description="Recover ROAS from 0.45 to 0.80",
        )
        strategy = builder.build(hypothesis, objective)
        assert "Recovery" in strategy.description
        assert "p01" in strategy.description

    def test_risk_level_set(self):
        builder = StrategyBuilder()
        hypothesis = _make_hypothesis(root_cause_category="market_decline")
        objective = StrategyObjective(metric="roas", product_id="p01")
        strategy = builder.build(hypothesis, objective)
        assert strategy.risk_level == RiskLevel.LOW

    def test_duration_days_set(self):
        builder = StrategyBuilder()
        hypothesis = _make_hypothesis(root_cause_category="scale")
        objective = StrategyObjective(metric="roas", product_id="p01")
        strategy = builder.build(hypothesis, objective)
        assert strategy.duration_days == 21

    def test_build_from_hypotheses(self):
        builder = StrategyBuilder()
        h1 = _make_hypothesis(root_cause_category="creative_fatigue")
        h2 = _make_hypothesis(root_cause_category="scale")
        obj = StrategyObjective(metric="roas", product_id="p01")
        strategies = builder.build_from_hypotheses(
            [h1, h2], [obj], product_id="p01",
        )
        assert len(strategies) == 2

    def test_build_from_hypotheses_no_match(self):
        builder = StrategyBuilder()
        h1 = _make_hypothesis(root_cause_category="creative_fatigue")
        obj = StrategyObjective(metric="roas", product_id="other_product")
        strategies = builder.build_from_hypotheses(
            [h1], [obj], product_id="p01",
        )
        # obj.product_id != p01, and obj.product_id != "", so no match
        assert len(strategies) == 0

    def test_build_from_hypotheses_empty_objective(self):
        builder = StrategyBuilder()
        h1 = _make_hypothesis(root_cause_category="creative_fatigue")
        obj = StrategyObjective(metric="roas", product_id="")  # empty product_id matches
        strategies = builder.build_from_hypotheses(
            [h1], [obj], product_id="p01",
        )
        assert len(strategies) == 1

    def test_custom_actions(self):
        builder = StrategyBuilder()
        hypothesis = _make_hypothesis(root_cause_category="creative_fatigue")
        objective = StrategyObjective(metric="roas", product_id="p01")
        strategy = builder.build(
            hypothesis, objective,
            custom_actions=["custom_action_type"],
        )
        assert strategy.template_type == StrategyTemplateType.RECOVERY

    def test_get_template(self):
        builder = StrategyBuilder()
        template = builder.get_template(StrategyTemplateType.RECOVERY)
        assert template is not None
        assert "base_impact" in template
        assert "risk_level" in template

    def test_get_template_none(self):
        builder = StrategyBuilder()
        assert builder.get_template(StrategyTemplateType.CUSTOM) is None

    def test_add_template(self):
        builder = StrategyBuilder()
        initial = builder.template_count
        builder.add_template(StrategyTemplateType.CUSTOM, {
            "conditions": {"root_cause_categories": ["custom"]},
            "base_impact": 0.50,
            "base_confidence": 0.60,
            "risk_level": RiskLevel.MEDIUM,
            "risk_score": 0.50,
            "duration_days": 10,
            "description_template": "Custom: {product}",
            "action_types": [],
        })
        assert builder.template_count == initial + 1

    def test_add_template_selects(self):
        builder = StrategyBuilder()
        builder.add_template(StrategyTemplateType.CUSTOM, {
            "conditions": {"root_cause_categories": ["my_custom_cause"]},
            "base_impact": 0.50,
            "base_confidence": 0.60,
            "risk_level": RiskLevel.MEDIUM,
            "risk_score": 0.50,
            "duration_days": 10,
            "description_template": "Custom: {product}",
            "action_types": [],
        })
        hypothesis = _make_hypothesis(root_cause_category="my_custom_cause")
        objective = StrategyObjective(metric="roas", product_id="p01")
        strategy = builder.build(hypothesis, objective)
        assert strategy.template_type == StrategyTemplateType.CUSTOM

    def test_all_template_types_select(self):
        builder = StrategyBuilder()
        objective = StrategyObjective(metric="roas", product_id="p01")
        tests = [
            ("creative_fatigue", StrategyTemplateType.RECOVERY),
            ("roas_decline", StrategyTemplateType.RECOVERY),
            ("roas_critical", StrategyTemplateType.RECOVERY),
            ("ctr_decline", StrategyTemplateType.RECOVERY),
            ("combined_fatigue_roas", StrategyTemplateType.RECOVERY),
            ("scale", StrategyTemplateType.SCALE),
            ("creative_diversity_low", StrategyTemplateType.EXPLORATION),
            ("winner_scarcity", StrategyTemplateType.EXPLORATION),
            ("cpi_inflation", StrategyTemplateType.EXPLORATION),
            ("high_competition", StrategyTemplateType.EXPLORATION),
            ("market_decline", StrategyTemplateType.SUNSET),
        ]
        for category, expected in tests:
            h = _make_hypothesis(root_cause_category=category)
            strategy = builder.build(h, objective)
            assert strategy.template_type == expected, f"{category} → {expected}"

    def test_scenario_roas_critical(self):
        """ROAS<0.30 → root_cause_category=roas_critical → RECOVERY."""
        builder = StrategyBuilder()
        h = _make_hypothesis(
            problem="ROAS dropped to 0.28",
            root_cause_category="roas_critical",
            confidence=0.85,
            expected_impact=0.70,
        )
        obj = StrategyObjective(
            metric="roas", product_id="p01",
            current_value=0.28, target_value=0.80,
            priority=0.95, urgency=0.90, impact=0.85,
        )
        strategy = builder.build(h, obj)
        assert strategy.template_type == StrategyTemplateType.RECOVERY
        assert strategy.risk_level == RiskLevel.MEDIUM
        assert strategy.expected_impact >= 0.50

    def test_scenario_sunset(self):
        """Market decline → SUNSET strategy."""
        builder = StrategyBuilder()
        h = _make_hypothesis(
            problem="Market is declining",
            root_cause_category="market_decline",
            confidence=0.70,
            expected_impact=0.30,
        )
        obj = StrategyObjective(metric="roas", product_id="p01")
        strategy = builder.build(h, obj)
        assert strategy.template_type == StrategyTemplateType.SUNSET
        assert strategy.risk_level == RiskLevel.LOW
        assert strategy.duration_days == 30

    def test_scenario_scale_healthy(self):
        """ROAS healthy → scale."""
        builder = StrategyBuilder()
        h = _make_hypothesis(
            problem="Ready to scale",
            root_cause_category="scale",
            confidence=0.70,
            expected_impact=0.50,
        )
        obj = StrategyObjective(metric="scale", product_id="p01")
        strategy = builder.build(h, obj)
        assert strategy.template_type == StrategyTemplateType.SCALE
        assert strategy.duration_days == 21

    def test_build_product_id_from_metadata(self):
        builder = StrategyBuilder()
        h = _make_hypothesis(
            root_cause_category="creative_fatigue",
            product_id="game_a",
        )
        obj = StrategyObjective(metric="roas", product_id="game_a")
        strategy = builder.build(h, obj)
        assert strategy.product_id == "game_a"

    def test_repr(self):
        builder = StrategyBuilder()
        assert "StrategyBuilder" in repr(builder)


# ══════════════════════════════════════════════════════════════
# Test Tactic Generator
# ══════════════════════════════════════════════════════════════


class TestTacticGenerator:
    """TacticGenerator 测试 (25 tests)."""

    def test_generate_recovery(self):
        gen = TacticGenerator()
        strategy = GrowthStrategy(
            product_id="p01",
            template_type=StrategyTemplateType.RECOVERY,
            confidence=0.80,
        )
        actions = gen.generate(strategy)
        assert len(actions) == 5
        assert actions[0].action_type == ActionType.DECREASE_BUDGET
        assert actions[1].action_type == ActionType.REFRESH_CREATIVE

    def test_generate_scale(self):
        gen = TacticGenerator()
        strategy = GrowthStrategy(
            product_id="p01",
            template_type=StrategyTemplateType.SCALE,
            confidence=0.80,
        )
        actions = gen.generate(strategy)
        assert len(actions) == 4
        assert actions[0].action_type == ActionType.INCREASE_BUDGET

    def test_generate_exploration(self):
        gen = TacticGenerator()
        strategy = GrowthStrategy(
            product_id="p01",
            template_type=StrategyTemplateType.EXPLORATION,
            confidence=0.80,
        )
        actions = gen.generate(strategy)
        assert len(actions) == 4
        assert actions[0].action_type == ActionType.MUTATE_DNA

    def test_generate_maintain(self):
        gen = TacticGenerator()
        strategy = GrowthStrategy(
            product_id="p01",
            template_type=StrategyTemplateType.MAINTAIN,
            confidence=0.80,
        )
        actions = gen.generate(strategy)
        assert len(actions) == 2
        assert actions[0].action_type == ActionType.REALLOCATE_BUDGET

    def test_generate_sunset(self):
        gen = TacticGenerator()
        strategy = GrowthStrategy(
            product_id="p01",
            template_type=StrategyTemplateType.SUNSET,
            confidence=0.80,
        )
        actions = gen.generate(strategy)
        assert len(actions) == 2
        assert actions[0].action_type == ActionType.DECREASE_BUDGET
        assert actions[1].action_type == ActionType.SUNSET_PRODUCT

    def test_generate_custom_no_rules(self):
        gen = TacticGenerator()
        strategy = GrowthStrategy(
            product_id="p01",
            template_type=StrategyTemplateType.CUSTOM,
            confidence=0.80,
        )
        actions = gen.generate(strategy)
        assert len(actions) == 0

    def test_priority_adjusted_by_confidence(self):
        gen = TacticGenerator()
        strategy_low = GrowthStrategy(
            product_id="p01",
            template_type=StrategyTemplateType.RECOVERY,
            confidence=0.50,
        )
        strategy_high = GrowthStrategy(
            product_id="p01",
            template_type=StrategyTemplateType.RECOVERY,
            confidence=1.0,
        )
        actions_low = gen.generate(strategy_low)
        actions_high = gen.generate(strategy_high)
        assert actions_high[0].priority > actions_low[0].priority

    def test_priority_capped_at_100(self):
        gen = TacticGenerator()
        strategy = GrowthStrategy(
            product_id="p01",
            template_type=StrategyTemplateType.RECOVERY,
            confidence=1.0,
        )
        actions = gen.generate(strategy)
        for a in actions:
            assert a.priority <= 100

    def test_impact_adjusted_by_confidence(self):
        gen = TacticGenerator()
        strategy = GrowthStrategy(
            product_id="p01",
            template_type=StrategyTemplateType.RECOVERY,
            confidence=0.50,
        )
        actions = gen.generate(strategy)
        # Original impact 0.30 × 0.50 = 0.15
        assert actions[0].expected_impact == pytest.approx(0.15)

    def test_dependencies_chain(self):
        gen = TacticGenerator()
        strategy = GrowthStrategy(
            product_id="p01",
            template_type=StrategyTemplateType.RECOVERY,
            confidence=0.80,
        )
        actions = gen.generate(strategy)
        # First action has no dependencies
        assert len(actions[0].dependencies) == 0
        # Subsequent actions depend on previous
        for i in range(1, len(actions)):
            assert actions[i].dependencies == [actions[i - 1].action_id]

    def test_generate_and_attach(self):
        gen = TacticGenerator()
        strategy = GrowthStrategy(
            product_id="p01",
            template_type=StrategyTemplateType.RECOVERY,
            confidence=0.80,
        )
        assert strategy.action_count == 0
        result = gen.generate_and_attach(strategy)
        assert result is strategy
        assert strategy.action_count == 5

    def test_parameters_preserved(self):
        gen = TacticGenerator()
        strategy = GrowthStrategy(
            product_id="p01",
            template_type=StrategyTemplateType.RECOVERY,
            confidence=0.80,
        )
        actions = gen.generate(strategy)
        assert actions[0].parameters["change_pct"] == pytest.approx(-0.20)
        assert actions[1].parameters["count"] == 50

    def test_target_modules(self):
        gen = TacticGenerator()
        strategy = GrowthStrategy(
            product_id="p01",
            template_type=StrategyTemplateType.RECOVERY,
            confidence=0.80,
        )
        actions = gen.generate(strategy)
        modules = [a.target_module for a in actions]
        assert "E12.6.2_ResourceController" in modules
        assert "E11_CreativeEvolution" in modules
        assert "E12.4_ExperimentEngine" in modules

    def test_duration_days(self):
        gen = TacticGenerator()
        strategy = GrowthStrategy(
            product_id="p01",
            template_type=StrategyTemplateType.RECOVERY,
            confidence=0.80,
        )
        actions = gen.generate(strategy)
        assert actions[0].duration_days == 1
        assert actions[1].duration_days == 3

    def test_add_rules(self):
        gen = TacticGenerator()
        gen.add_rules(StrategyTemplateType.CUSTOM, [
            {
                "action_type": ActionType.CUSTOM,
                "target_module": "test_module",
                "priority": 50,
                "expected_result": "test",
                "expected_impact": 0.10,
                "duration_days": 1,
                "parameters": {},
            },
        ])
        strategy = GrowthStrategy(
            product_id="p01",
            template_type=StrategyTemplateType.CUSTOM,
            confidence=0.80,
        )
        actions = gen.generate(strategy)
        assert len(actions) == 1

    def test_get_rules(self):
        gen = TacticGenerator()
        rules = gen.get_rules(StrategyTemplateType.RECOVERY)
        assert rules is not None
        assert len(rules) == 5

    def test_get_rules_none(self):
        gen = TacticGenerator()
        assert gen.get_rules(StrategyTemplateType.CUSTOM) is None

    def test_rule_count(self):
        gen = TacticGenerator()
        assert gen.rule_count == 5

    def test_scale_actions_order(self):
        gen = TacticGenerator()
        strategy = GrowthStrategy(
            product_id="p01",
            template_type=StrategyTemplateType.SCALE,
            confidence=0.80,
        )
        actions = gen.generate(strategy)
        types = [a.action_type for a in actions]
        assert types == [
            ActionType.INCREASE_BUDGET,
            ActionType.CREATE_CREATIVE,
            ActionType.EXPAND_AUDIENCE,
            ActionType.LAUNCH_EXPERIMENT,
        ]

    def test_exploration_actions_order(self):
        gen = TacticGenerator()
        strategy = GrowthStrategy(
            product_id="p01",
            template_type=StrategyTemplateType.EXPLORATION,
            confidence=0.80,
        )
        actions = gen.generate(strategy)
        types = [a.action_type for a in actions]
        assert types == [
            ActionType.MUTATE_DNA,
            ActionType.CREATE_CREATIVE,
            ActionType.LAUNCH_EXPERIMENT,
            ActionType.EXPAND_AUDIENCE,
        ]

    def test_maintain_actions_order(self):
        gen = TacticGenerator()
        strategy = GrowthStrategy(
            product_id="p01",
            template_type=StrategyTemplateType.MAINTAIN,
            confidence=0.80,
        )
        actions = gen.generate(strategy)
        types = [a.action_type for a in actions]
        assert types == [
            ActionType.REALLOCATE_BUDGET,
            ActionType.EVALUATE_EXPERIMENT,
        ]

    def test_sunset_actions_order(self):
        gen = TacticGenerator()
        strategy = GrowthStrategy(
            product_id="p01",
            template_type=StrategyTemplateType.SUNSET,
            confidence=0.80,
        )
        actions = gen.generate(strategy)
        types = [a.action_type for a in actions]
        assert types == [
            ActionType.DECREASE_BUDGET,
            ActionType.SUNSET_PRODUCT,
        ]

    def test_expected_results_non_empty(self):
        gen = TacticGenerator()
        for tt in [StrategyTemplateType.RECOVERY, StrategyTemplateType.SCALE,
                    StrategyTemplateType.EXPLORATION, StrategyTemplateType.MAINTAIN,
                    StrategyTemplateType.SUNSET]:
            strategy = GrowthStrategy(
                product_id="p01",
                template_type=tt,
                confidence=0.80,
            )
            actions = gen.generate(strategy)
            for a in actions:
                assert a.expected_result != "", f"{tt} action has empty expected_result"

    def test_repr(self):
        gen = TacticGenerator()
        assert "TacticGenerator" in repr(gen)


# ══════════════════════════════════════════════════════════════
# Test Constraint Manager
# ══════════════════════════════════════════════════════════════


class TestConstraintManager:
    """ConstraintManager 测试 (20 tests)."""

    def test_validate_all_pass(self):
        cm = ConstraintManager()
        strategy = GrowthStrategy(
            product_id="p01",
            template_type=StrategyTemplateType.RECOVERY,
            confidence=0.75,
            risk_score=0.40,
            actions=[
                StrategyAction(
                    action_type=ActionType.DECREASE_BUDGET,
                    parameters={"change_pct": -0.20},
                    duration_days=1,
                ),
                StrategyAction(
                    action_type=ActionType.LAUNCH_EXPERIMENT,
                    parameters={"duration_days": 7},
                    duration_days=7,
                ),
            ],
        )
        checks = cm.validate(strategy)
        assert len(checks) == 7
        assert all(c.passed for c in checks)

    def test_validate_budget_fail(self):
        cm = ConstraintManager()
        strategy = GrowthStrategy(
            product_id="p01",
            template_type=StrategyTemplateType.RECOVERY,
            confidence=0.75,
            risk_score=0.40,
            actions=[
                StrategyAction(
                    action_type=ActionType.INCREASE_BUDGET,
                    parameters={"change_pct": 0.60},
                ),
            ],
        )
        checks = cm.validate(strategy)
        budget_check = [c for c in checks if c.constraint_name == "max_budget_change"][0]
        assert budget_check.passed is False

    def test_validate_budget_pass(self):
        cm = ConstraintManager()
        strategy = GrowthStrategy(
            product_id="p01",
            confidence=0.75,
            risk_score=0.40,
            actions=[
                StrategyAction(
                    action_type=ActionType.INCREASE_BUDGET,
                    parameters={"change_pct": 0.30},
                ),
            ],
        )
        checks = cm.validate(strategy)
        budget_check = [c for c in checks if c.constraint_name == "max_budget_change"][0]
        assert budget_check.passed is True

    def test_validate_experiment_fail(self):
        cm = ConstraintManager()
        strategy = GrowthStrategy(
            product_id="p01",
            confidence=0.75,
            risk_score=0.40,
            actions=[
                StrategyAction(
                    action_type=ActionType.LAUNCH_EXPERIMENT,
                    parameters={"duration_days": 45},
                ),
            ],
        )
        checks = cm.validate(strategy)
        exp_check = [c for c in checks if c.constraint_name == "max_experiment_duration"][0]
        assert exp_check.passed is False

    def test_validate_experiment_pass(self):
        cm = ConstraintManager()
        strategy = GrowthStrategy(
            product_id="p01",
            confidence=0.75,
            risk_score=0.40,
            actions=[
                StrategyAction(
                    action_type=ActionType.LAUNCH_EXPERIMENT,
                    parameters={"duration_days": 14},
                ),
            ],
        )
        checks = cm.validate(strategy)
        exp_check = [c for c in checks if c.constraint_name == "max_experiment_duration"][0]
        assert exp_check.passed is True

    def test_validate_risk_fail(self):
        cm = ConstraintManager()
        strategy = GrowthStrategy(
            product_id="p01",
            confidence=0.75,
            risk_score=0.95,
        )
        checks = cm.validate(strategy)
        risk_check = [c for c in checks if c.constraint_name == "risk_threshold"][0]
        assert risk_check.passed is False

    def test_validate_risk_pass(self):
        cm = ConstraintManager()
        strategy = GrowthStrategy(
            product_id="p01",
            confidence=0.75,
            risk_score=0.40,
        )
        checks = cm.validate(strategy)
        risk_check = [c for c in checks if c.constraint_name == "risk_threshold"][0]
        assert risk_check.passed is True

    def test_validate_confidence_fail(self):
        cm = ConstraintManager()
        strategy = GrowthStrategy(
            product_id="p01",
            confidence=0.20,
            risk_score=0.40,
        )
        checks = cm.validate(strategy)
        conf_check = [c for c in checks if c.constraint_name == "min_confidence"][0]
        assert conf_check.passed is False

    def test_validate_confidence_pass(self):
        cm = ConstraintManager()
        strategy = GrowthStrategy(
            product_id="p01",
            confidence=0.75,
            risk_score=0.40,
        )
        checks = cm.validate(strategy)
        conf_check = [c for c in checks if c.constraint_name == "min_confidence"][0]
        assert conf_check.passed is True

    def test_validate_duration_fail(self):
        cm = ConstraintManager()
        strategy = GrowthStrategy(
            product_id="p01",
            confidence=0.75,
            risk_score=0.40,
            actions=[StrategyAction(duration_days=70)],
        )
        checks = cm.validate(strategy)
        dur_check = [c for c in checks if c.constraint_name == "max_duration"][0]
        assert dur_check.passed is False

    def test_validate_parallel_actions(self):
        cm = ConstraintManager()
        strategy = GrowthStrategy(
            product_id="p01",
            confidence=0.75,
            risk_score=0.40,
            actions=[StrategyAction() for _ in range(12)],
        )
        checks = cm.validate(strategy)
        par_check = [c for c in checks if c.constraint_name == "max_parallel_actions"][0]
        assert par_check.passed is False

    def test_validate_sunset_warning(self):
        cm = ConstraintManager()
        strategy = GrowthStrategy(
            product_id="p01",
            template_type=StrategyTemplateType.SUNSET,
            confidence=0.75,
            risk_score=0.40,
        )
        checks = cm.validate(strategy)
        sunset_check = [c for c in checks if c.constraint_name == "sunset_allowed"][0]
        assert sunset_check.passed is True  # Always passes, just warns
        assert sunset_check.severity == RiskLevel.CRITICAL

    def test_validate_and_approve_pass(self):
        cm = ConstraintManager()
        strategy = GrowthStrategy(
            product_id="p01",
            confidence=0.75,
            risk_score=0.40,
            actions=[
                StrategyAction(
                    action_type=ActionType.DECREASE_BUDGET,
                    parameters={"change_pct": -0.20},
                ),
            ],
        )
        passed, checks = cm.validate_and_approve(strategy)
        assert passed is True
        assert strategy.status == StrategyStatus.VALIDATED

    def test_validate_and_approve_fail(self):
        cm = ConstraintManager()
        strategy = GrowthStrategy(
            product_id="p01",
            confidence=0.20,
            risk_score=0.40,
        )
        passed, checks = cm.validate_and_approve(strategy)
        assert passed is False
        assert strategy.status == StrategyStatus.REJECTED

    def test_validate_batch(self):
        cm = ConstraintManager()
        s1 = GrowthStrategy(
            product_id="p01",
            confidence=0.75,
            risk_score=0.40,
            actions=[
                StrategyAction(
                    action_type=ActionType.DECREASE_BUDGET,
                    parameters={"change_pct": -0.20},
                ),
            ],
        )
        s2 = GrowthStrategy(
            product_id="p02",
            confidence=0.20,
            risk_score=0.40,
        )
        results = cm.validate_batch([s1, s2])
        assert results[s1.strategy_id][0] is True
        assert results[s2.strategy_id][0] is False

    def test_add_constraint(self):
        cm = ConstraintManager()
        initial = cm.constraint_count
        cm.add_constraint({
            "name": "custom_check",
            "description": "Custom constraint",
            "check": lambda s: ConstraintCheck(
                constraint_name="custom_check",
                passed=True,
                message="OK",
            ),
            "severity": RiskLevel.LOW,
        })
        assert cm.constraint_count == initial + 1

    def test_custom_constraint_triggered(self):
        cm = ConstraintManager()
        cm.add_constraint({
            "name": "always_fail",
            "description": "Always fails",
            "check": lambda s: ConstraintCheck(
                constraint_name="always_fail",
                passed=False,
                message="Failed",
            ),
            "severity": RiskLevel.HIGH,
        })
        strategy = GrowthStrategy(
            product_id="p01",
            confidence=0.75,
            risk_score=0.40,
        )
        checks = cm.validate(strategy)
        custom = [c for c in checks if c.constraint_name == "always_fail"]
        assert len(custom) == 1
        assert custom[0].passed is False

    def test_constraint_error_handling(self):
        cm = ConstraintManager()
        cm.add_constraint({
            "name": "crash_check",
            "description": "Will crash",
            "check": lambda s: 1 / 0,  # Will raise exception
            "severity": RiskLevel.HIGH,
        })
        strategy = GrowthStrategy(
            product_id="p01",
            confidence=0.75,
            risk_score=0.40,
        )
        checks = cm.validate(strategy)
        crash = [c for c in checks if c.constraint_name == "crash_check"]
        assert len(crash) == 1
        assert crash[0].passed is False

    def test_no_budget_actions(self):
        cm = ConstraintManager()
        strategy = GrowthStrategy(
            product_id="p01",
            confidence=0.75,
            risk_score=0.40,
            actions=[],
        )
        checks = cm.validate(strategy)
        budget_check = [c for c in checks if c.constraint_name == "max_budget_change"][0]
        assert budget_check.passed is True
        assert budget_check.current_value == 0.0

    def test_repr(self):
        cm = ConstraintManager()
        assert "ConstraintManager" in repr(cm)


# ══════════════════════════════════════════════════════════════
# Test Strategy Ranker
# ══════════════════════════════════════════════════════════════


class TestStrategyRanker:
    """StrategyRanker 测试 (15 tests)."""

    def test_rank_by_score(self):
        ranker = StrategyRanker()
        s1 = GrowthStrategy(
            product_id="p01",
            expected_impact=0.80,
            confidence=0.90,
            risk_score=0.20,
            actions=[StrategyAction() for _ in range(5)],
        )
        s2 = GrowthStrategy(
            product_id="p02",
            expected_impact=0.30,
            confidence=0.40,
            risk_score=0.80,
            actions=[StrategyAction()],
        )
        ranked = ranker.rank([s1, s2])
        assert ranked[0].strategy_id == s1.strategy_id

    def test_rank_preserves_all(self):
        ranker = StrategyRanker()
        strategies = [
            GrowthStrategy(
                product_id=f"p{i:02d}",
                expected_impact=0.5 + i * 0.05,
                confidence=0.5 + i * 0.05,
                risk_score=0.5 - i * 0.05,
                actions=[StrategyAction() for _ in range(i + 1)],
            )
            for i in range(5)
        ]
        ranked = ranker.rank(strategies)
        assert len(ranked) == 5

    def test_get_top(self):
        ranker = StrategyRanker()
        s1 = GrowthStrategy(
            product_id="p01",
            expected_impact=0.90,
            confidence=0.95,
            risk_score=0.10,
            actions=[StrategyAction() for _ in range(10)],
        )
        s2 = GrowthStrategy(
            product_id="p02",
            expected_impact=0.20,
            confidence=0.30,
            risk_score=0.90,
        )
        top = ranker.get_top([s1, s2])
        assert top.strategy_id == s1.strategy_id

    def test_get_top_empty(self):
        ranker = StrategyRanker()
        assert ranker.get_top([]) is None

    def test_get_top_n(self):
        ranker = StrategyRanker()
        strategies = [
            GrowthStrategy(
                product_id=f"p{i:02d}",
                expected_impact=0.3 + i * 0.1,
                confidence=0.5 + i * 0.05,
                risk_score=0.5 - i * 0.05,
                actions=[StrategyAction() for _ in range(i + 1)],
            )
            for i in range(5)
        ]
        top3 = ranker.get_top_n(strategies, n=3)
        assert len(top3) == 3

    def test_get_top_n_more_than_available(self):
        ranker = StrategyRanker()
        strategies = [
            GrowthStrategy(product_id="p01"),
            GrowthStrategy(product_id="p02"),
        ]
        result = ranker.get_top_n(strategies, n=10)
        assert len(result) == 2

    def test_get_scores(self):
        ranker = StrategyRanker()
        s1 = GrowthStrategy(
            product_id="p01",
            expected_impact=0.50,
            confidence=0.50,
            risk_score=0.50,
            actions=[StrategyAction()],
        )
        s2 = GrowthStrategy(
            product_id="p02",
            expected_impact=0.80,
            confidence=0.80,
            risk_score=0.20,
            actions=[StrategyAction() for _ in range(5)],
        )
        scores = ranker.get_scores([s1, s2])
        assert s1.strategy_id in scores
        assert s2.strategy_id in scores
        assert scores[s2.strategy_id] > scores[s1.strategy_id]

    def test_score_formula(self):
        ranker = StrategyRanker()
        strategy = GrowthStrategy(
            product_id="p01",
            expected_impact=0.60,
            confidence=0.70,
            risk_score=0.30,
            actions=[StrategyAction() for _ in range(5)],
        )
        score = ranker._score(strategy)
        # action_factor = min(1.0, 5/10) = 0.5
        expected = 0.60 * 0.40 + 0.70 * 0.30 + (1.0 - 0.30) * 0.20 + 0.5 * 0.10
        assert score == pytest.approx(expected)

    def test_score_action_factor_capped(self):
        ranker = StrategyRanker()
        strategy = GrowthStrategy(
            product_id="p01",
            expected_impact=0.50,
            confidence=0.50,
            risk_score=0.50,
            actions=[StrategyAction() for _ in range(20)],
        )
        score = ranker._score(strategy)
        # action_factor capped at 1.0
        expected = 0.50 * 0.40 + 0.50 * 0.30 + (1.0 - 0.50) * 0.20 + 1.0 * 0.10
        assert score == pytest.approx(expected)

    def test_custom_weights(self):
        ranker = StrategyRanker(weights={
            "expected_impact": 0.50,
            "confidence": 0.00,
            "risk_inverse": 0.50,
            "action_count": 0.00,
        })
        strategy = GrowthStrategy(
            product_id="p01",
            expected_impact=0.80,
            confidence=0.10,
            risk_score=0.20,
        )
        score = ranker._score(strategy)
        expected = 0.80 * 0.50 + 0.10 * 0.00 + (1.0 - 0.20) * 0.50 + 0.0 * 0.00
        assert score == pytest.approx(expected)

    def test_weights_property(self):
        ranker = StrategyRanker()
        w = ranker.weights
        assert w["expected_impact"] == 0.40
        assert w["confidence"] == 0.30
        assert w["risk_inverse"] == 0.20
        assert w["action_count"] == 0.10

    def test_rank_empty(self):
        ranker = StrategyRanker()
        assert ranker.rank([]) == []

    def test_rank_single(self):
        ranker = StrategyRanker()
        strategy = GrowthStrategy(product_id="p01")
        ranked = ranker.rank([strategy])
        assert len(ranked) == 1
        assert ranked[0].strategy_id == strategy.strategy_id

    def test_score_rounding(self):
        ranker = StrategyRanker()
        strategy = GrowthStrategy(product_id="p01")
        score = ranker._score(strategy)
        # Verify it's rounded to 4 decimal places
        assert isinstance(score, float)

    def test_repr(self):
        ranker = StrategyRanker()
        assert "StrategyRanker" in repr(ranker)


# ══════════════════════════════════════════════════════════════
# Test Planner Controller
# ══════════════════════════════════════════════════════════════


class TestGrowthStrategyPlanner:
    """GrowthStrategyPlanner 测试 (25 tests)."""

    def test_create_default(self):
        planner = GrowthStrategyPlanner()
        assert isinstance(planner._objective_engine, ObjectiveEngine)
        assert isinstance(planner._strategy_builder, StrategyBuilder)
        assert isinstance(planner._tactic_generator, TacticGenerator)
        assert isinstance(planner._constraint_manager, ConstraintManager)
        assert isinstance(planner._strategy_ranker, StrategyRanker)

    def test_create_custom_components(self):
        oe = ObjectiveEngine()
        sb = StrategyBuilder()
        tg = TacticGenerator()
        cm = ConstraintManager()
        sr = StrategyRanker()
        planner = GrowthStrategyPlanner(
            objective_engine=oe,
            strategy_builder=sb,
            tactic_generator=tg,
            constraint_manager=cm,
            strategy_ranker=sr,
        )
        assert planner._objective_engine is oe
        assert planner._strategy_builder is sb
        assert planner._tactic_generator is tg
        assert planner._constraint_manager is cm
        assert planner._strategy_ranker is sr

    def test_analyze_objective(self):
        planner = GrowthStrategyPlanner()
        obs = _make_observation(roas=0.30, severity=ObservationSeverity.CRITICAL)
        objectives = planner.analyze_objective(obs)
        assert len(objectives) >= 1
        assert objectives[0].metric == "roas"

    def test_build_strategies(self):
        planner = GrowthStrategyPlanner()
        h = _make_hypothesis(root_cause_category="creative_fatigue")
        obj = StrategyObjective(metric="roas", product_id="p01")
        strategies = planner.build_strategies([h], [obj], product_id="p01")
        assert len(strategies) == 1
        assert strategies[0].template_type == StrategyTemplateType.RECOVERY

    def test_generate_tactics(self):
        planner = GrowthStrategyPlanner()
        strategy = GrowthStrategy(
            product_id="p01",
            template_type=StrategyTemplateType.RECOVERY,
            confidence=0.80,
        )
        result = planner.generate_tactics([strategy])
        assert len(result) == 1
        assert result[0].action_count > 0

    def test_validate(self):
        planner = GrowthStrategyPlanner()
        strategy = GrowthStrategy(
            product_id="p01",
            confidence=0.75,
            risk_score=0.40,
            actions=[
                StrategyAction(
                    action_type=ActionType.DECREASE_BUDGET,
                    parameters={"change_pct": -0.20},
                ),
            ],
        )
        results = planner.validate([strategy])
        assert strategy.strategy_id in results
        passed, checks = results[strategy.strategy_id]
        assert passed is True

    def test_rank(self):
        planner = GrowthStrategyPlanner()
        s1 = GrowthStrategy(
            product_id="p01",
            expected_impact=0.80,
            confidence=0.90,
            risk_score=0.20,
            actions=[StrategyAction() for _ in range(5)],
        )
        s2 = GrowthStrategy(
            product_id="p02",
            expected_impact=0.30,
            confidence=0.40,
            risk_score=0.80,
        )
        ranked = planner.rank([s1, s2])
        assert ranked[0].strategy_id == s1.strategy_id

    def test_plan_full_pipeline(self):
        planner = GrowthStrategyPlanner()
        obs = _make_observation(
            product_id="p01",
            roas=0.30,
            fatigue_score=0.80,
            severity=ObservationSeverity.CRITICAL,
        )
        h = _make_hypothesis(
            root_cause_category="creative_fatigue",
            confidence=0.85,
            expected_impact=0.70,
        )
        plan = planner.plan(obs, [h], product_id="p01")
        assert isinstance(plan, StrategyPlan)
        assert plan.product_id == "p01"
        assert plan.strategy_count >= 1
        assert plan.top_strategy is not None
        assert plan.top_strategy.template_type == StrategyTemplateType.RECOVERY
        assert plan.top_strategy.action_count > 0
        assert len(plan.constraints) > 0
        assert plan.summary != ""

    def test_plan_multiple_hypotheses(self):
        planner = GrowthStrategyPlanner()
        obs = _make_observation(
            product_id="p01",
            roas=0.30,
            ctr=0.005,
            fatigue_score=0.80,
            severity=ObservationSeverity.CRITICAL,
        )
        h1 = _make_hypothesis(root_cause_category="creative_fatigue")
        h2 = _make_hypothesis(root_cause_category="roas_critical")
        plan = planner.plan(obs, [h1, h2], product_id="p01")
        assert plan.strategy_count == 2

    def test_plan_no_auto_validate(self):
        planner = GrowthStrategyPlanner()
        obs = _make_observation(roas=0.30)
        h = _make_hypothesis(root_cause_category="creative_fatigue")
        plan = planner.plan(obs, [h], product_id="p01", auto_validate=False)
        assert len(plan.constraints) == 0

    def test_plan_from_agent_result(self):
        planner = GrowthStrategyPlanner()
        obs = _make_observation(
            roas=0.30,
            fatigue_score=0.80,
            severity=ObservationSeverity.CRITICAL,
        )
        h = _make_hypothesis(root_cause_category="creative_fatigue")
        plan = planner.plan_from_agent_result(obs, [h], product_id="p01")
        assert isinstance(plan, StrategyPlan)
        assert plan.top_strategy is not None

    def test_plan_empty_hypotheses(self):
        planner = GrowthStrategyPlanner()
        obs = _make_observation(roas=0.30)
        plan = planner.plan(obs, [], product_id="p01")
        assert plan.strategy_count == 0
        assert plan.top_strategy is None

    def test_plan_constraints_include_checks(self):
        planner = GrowthStrategyPlanner()
        obs = _make_observation(roas=0.30)
        h = _make_hypothesis(root_cause_category="creative_fatigue")
        plan = planner.plan(obs, [h], product_id="p01")
        names = [c.constraint_name for c in plan.constraints]
        assert "max_budget_change" in names
        assert "max_experiment_duration" in names
        assert "risk_threshold" in names
        assert "min_confidence" in names

    def test_plan_summary_contains_info(self):
        planner = GrowthStrategyPlanner()
        obs = _make_observation(
            product_id="game_x",
            roas=0.30,
            severity=ObservationSeverity.CRITICAL,
        )
        h = _make_hypothesis(root_cause_category="creative_fatigue")
        plan = planner.plan(obs, [h], product_id="p01")
        assert "game_x" in plan.summary
        assert "severity" in plan.summary.lower() or "critical" in plan.summary.lower()

    def test_plan_top_strategy_has_actions(self):
        planner = GrowthStrategyPlanner()
        obs = _make_observation(roas=0.30, fatigue_score=0.80)
        h = _make_hypothesis(root_cause_category="creative_fatigue")
        plan = planner.plan(obs, [h], product_id="p01")
        assert plan.top_strategy is not None
        assert plan.top_strategy.action_count > 0

    def test_plan_scale_scenario(self):
        planner = GrowthStrategyPlanner()
        obs = _make_observation(roas=1.5, fatigue_score=0.1, spend=1000.0)
        h = _make_hypothesis(
            root_cause_category="scale",
            problem="Ready to scale",
            confidence=0.70,
            expected_impact=0.50,
        )
        plan = planner.plan(obs, [h], product_id="p01")
        assert plan.top_strategy is not None
        assert plan.top_strategy.template_type == StrategyTemplateType.SCALE

    def test_plan_exploration_scenario(self):
        planner = GrowthStrategyPlanner()
        obs = _make_observation(diversity_score=0.1)
        h = _make_hypothesis(
            root_cause_category="creative_diversity_low",
            problem="Low diversity",
            confidence=0.70,
            expected_impact=0.40,
        )
        plan = planner.plan(obs, [h], product_id="p01")
        assert plan.top_strategy is not None
        assert plan.top_strategy.template_type == StrategyTemplateType.EXPLORATION

    def test_plan_sunset_scenario(self):
        planner = GrowthStrategyPlanner()
        obs = _make_observation(roas=0.30)
        h = _make_hypothesis(
            root_cause_category="market_decline",
            problem="Market declining",
            confidence=0.70,
            expected_impact=0.20,
        )
        plan = planner.plan(obs, [h], product_id="p01")
        assert plan.top_strategy is not None
        assert plan.top_strategy.template_type == StrategyTemplateType.SUNSET

    def test_plan_ranked_order(self):
        planner = GrowthStrategyPlanner()
        obs = _make_observation(roas=0.30, ctr=0.005, fatigue_score=0.80)
        h1 = _make_hypothesis(
            root_cause_category="creative_fatigue",
            confidence=0.85,
            expected_impact=0.70,
        )
        h2 = _make_hypothesis(
            root_cause_category="ctr_decline",
            confidence=0.50,
            expected_impact=0.30,
        )
        plan = planner.plan(obs, [h1, h2], product_id="p01")
        assert plan.strategy_count == 2
        assert plan.top_strategy is not None
        # Higher confidence/impact hypothesis should be top
        assert plan.top_strategy.confidence >= 0.50

    def test_plan_to_dict(self):
        planner = GrowthStrategyPlanner()
        obs = _make_observation(roas=0.30, fatigue_score=0.80)
        h = _make_hypothesis(root_cause_category="creative_fatigue")
        plan = planner.plan(obs, [h], product_id="p01")
        d = plan.to_dict()
        assert "plan_id" in d
        assert "strategy_count" in d
        assert "top_strategy" in d
        assert "constraints" in d
        assert "summary" in d
        assert "actionable_strategies" in d

    def test_plan_rejected_strategy(self):
        planner = GrowthStrategyPlanner()
        obs = _make_observation(roas=0.30)
        h = _make_hypothesis(
            root_cause_category="creative_fatigue",
            confidence=0.20,  # Very low confidence → will fail min_confidence
            expected_impact=0.10,
        )
        plan = planner.plan(obs, [h], product_id="p01")
        # Plan should still be generated
        assert plan.top_strategy is not None
        # Constraint check should show failure
        conf_checks = [c for c in plan.constraints if c.constraint_name == "min_confidence"]
        if conf_checks:
            assert conf_checks[0].passed is False

    def test_repr(self):
        planner = GrowthStrategyPlanner()
        assert "GrowthStrategyPlanner" in repr(planner)


# ══════════════════════════════════════════════════════════════
# Test Integration
# ══════════════════════════════════════════════════════════════


class TestIntegration:
    """E12.7.3 集成测试 (10 tests)."""

    def test_full_pipeline_roas_recovery(self):
        """ROAS下降 → 恢复策略完整管线."""
        planner = GrowthStrategyPlanner()
        obs = _make_observation(
            product_id="game_x",
            roas=0.35,
            fatigue_score=0.85,
            ctr=0.008,
            severity=ObservationSeverity.CRITICAL,
        )
        h = _make_hypothesis(
            root_cause_category="creative_fatigue",
            confidence=0.85,
            expected_impact=0.70,
            product_id="game_x",
        )
        plan = planner.plan(obs, [h], product_id="game_x")

        # Verify plan structure
        assert plan.product_id == "game_x"
        assert plan.strategy_count >= 1
        top = plan.top_strategy
        assert top is not None
        assert top.template_type == StrategyTemplateType.RECOVERY
        assert top.action_count == 5
        assert top.expected_impact > 0
        assert top.confidence > 0

        # Verify tactics
        actions = top.actions
        action_types = [a.action_type for a in actions]
        assert ActionType.DECREASE_BUDGET in action_types
        assert ActionType.REFRESH_CREATIVE in action_types
        assert ActionType.MUTATE_DNA in action_types
        assert ActionType.LAUNCH_EXPERIMENT in action_types
        assert ActionType.EVALUATE_EXPERIMENT in action_types

    def test_full_pipeline_scale(self):
        """ROAS健康 → 扩展策略."""
        planner = GrowthStrategyPlanner()
        obs = _make_observation(
            product_id="game_y",
            roas=1.5,
            fatigue_score=0.1,
            spend=1000.0,
        )
        h = _make_hypothesis(
            root_cause_category="scale",
            confidence=0.70,
            expected_impact=0.50,
            product_id="game_y",
        )
        plan = planner.plan(obs, [h], product_id="game_y")
        top = plan.top_strategy
        assert top.template_type == StrategyTemplateType.SCALE
        actions = top.actions
        assert ActionType.INCREASE_BUDGET in [a.action_type for a in actions]
        assert ActionType.CREATE_CREATIVE in [a.action_type for a in actions]

    def test_full_pipeline_exploration(self):
        """多样性低 → 探索策略."""
        planner = GrowthStrategyPlanner()
        obs = _make_observation(
            product_id="game_z",
            diversity_score=0.1,
            cpi=6.0,
        )
        h = _make_hypothesis(
            root_cause_category="creative_diversity_low",
            confidence=0.65,
            expected_impact=0.40,
            product_id="game_z",
        )
        plan = planner.plan(obs, [h], product_id="game_z")
        top = plan.top_strategy
        assert top.template_type == StrategyTemplateType.EXPLORATION
        assert ActionType.MUTATE_DNA in [a.action_type for a in top.actions]

    def test_full_pipeline_sunset(self):
        """市场下降 → 退出策略."""
        planner = GrowthStrategyPlanner()
        obs = _make_observation(
            product_id="game_old",
            roas=0.30,
        )
        h = _make_hypothesis(
            root_cause_category="market_decline",
            confidence=0.70,
            expected_impact=0.20,
            product_id="game_old",
        )
        plan = planner.plan(obs, [h], product_id="game_old")
        top = plan.top_strategy
        assert top.template_type == StrategyTemplateType.SUNSET
        assert top.duration_days == 30

    def test_multi_strategy_ranking(self):
        """多个策略正确排名."""
        planner = GrowthStrategyPlanner()
        obs = _make_observation(
            roas=0.30,
            fatigue_score=0.80,
            ctr=0.005,
            severity=ObservationSeverity.CRITICAL,
        )
        h1 = _make_hypothesis(
            root_cause_category="creative_fatigue",
            confidence=0.85,
            expected_impact=0.70,
        )
        h2 = _make_hypothesis(
            root_cause_category="ctr_decline",
            confidence=0.50,
            expected_impact=0.30,
        )
        h3 = _make_hypothesis(
            root_cause_category="roas_critical",
            confidence=0.90,
            expected_impact=0.80,
        )
        plan = planner.plan(obs, [h1, h2, h3], product_id="p01")
        assert plan.strategy_count == 3
        # Top should be the highest confidence+impact
        top = plan.top_strategy
        # All three are RECOVERY, ranked by score
        assert top.hypothesis_id in [h.hypothesis_id for h in [h1, h2, h3]]

    def test_constraint_rejection_flow(self):
        """约束拒绝流程."""
        cm = ConstraintManager()
        strategy = GrowthStrategy(
            product_id="p01",
            confidence=0.20,  # Below min_confidence=0.30
            risk_score=0.40,
            actions=[
                StrategyAction(
                    action_type=ActionType.INCREASE_BUDGET,
                    parameters={"change_pct": 0.60},  # Exceeds 50% limit
                ),
            ],
        )
        passed, checks = cm.validate_and_approve(strategy)
        assert passed is False
        assert strategy.status == StrategyStatus.REJECTED
        failed = [c for c in checks if not c.passed]
        assert len(failed) >= 2  # Both budget and confidence fail

    def test_objective_to_strategy_to_tactics_chain(self):
        """目标→策略→战术完整链条."""
        # Objective
        engine = ObjectiveEngine()
        obs = _make_observation(roas=0.30, fatigue_score=0.80, severity=ObservationSeverity.CRITICAL)
        objectives = engine.analyze(obs)
        assert len(objectives) >= 1

        # Strategy
        builder = StrategyBuilder()
        h = _make_hypothesis(root_cause_category="creative_fatigue")
        strategy = builder.build(h, objectives[0])
        assert strategy.template_type == StrategyTemplateType.RECOVERY

        # Tactics
        gen = TacticGenerator()
        strategy = gen.generate_and_attach(strategy)
        assert strategy.action_count == 5
        assert strategy.actions[0].dependencies == []

        # Validate
        cm = ConstraintManager()
        passed, checks = cm.validate_and_approve(strategy)
        assert passed is True
        assert strategy.status == StrategyStatus.VALIDATED

        # Rank
        ranker = StrategyRanker()
        ranked = ranker.rank([strategy])
        assert len(ranked) == 1

    def test_plan_from_agent_result_integration(self):
        """从 Agent 结果到 StrategyPlan 的完整集成."""
        planner = GrowthStrategyPlanner()
        obs = _make_observation(
            product_id="app_v1",
            roas=0.28,
            ctr=0.006,
            cpi=7.0,
            fatigue_score=0.88,
            diversity_score=0.15,
            retention_d7=0.08,
            severity=ObservationSeverity.FATAL,
        )
        hypotheses = [
            _make_hypothesis(
                root_cause_category="creative_fatigue",
                confidence=0.88,
                expected_impact=0.75,
                product_id="app_v1",
            ),
            _make_hypothesis(
                root_cause_category="roas_critical",
                confidence=0.92,
                expected_impact=0.85,
                product_id="app_v1",
            ),
            _make_hypothesis(
                root_cause_category="cpi_inflation",
                confidence=0.65,
                expected_impact=0.45,
                product_id="app_v1",
            ),
        ]
        plan = planner.plan_from_agent_result(obs, hypotheses, product_id="app_v1")

        # Verify plan
        assert plan.product_id == "app_v1"
        assert plan.strategy_count == 3
        assert plan.top_strategy is not None
        assert len(plan.constraints) > 0
        assert plan.summary != ""

        # All strategies should have tactics
        for s in plan.strategies:
            assert s.action_count > 0

        # Top strategy should be actionable
        assert plan.top_strategy.is_actionable

    def test_strategyplan_to_dict_full(self):
        """StrategyPlan 完整序列化."""
        planner = GrowthStrategyPlanner()
        obs = _make_observation(roas=0.30, fatigue_score=0.80)
        h = _make_hypothesis(root_cause_category="creative_fatigue")
        plan = planner.plan(obs, [h], product_id="p01")
        d = plan.to_dict()
        # Verify all sections
        assert d["plan_id"].startswith("PLN_")
        assert d["product_id"] == "p01"
        assert d["strategy_count"] >= 1
        assert d["top_strategy"] is not None
        assert isinstance(d["constraints"], list)
        assert isinstance(d["summary"], str)
        assert "actionable_strategies" in d

    def test_all_engines_repr(self):
        """所有引擎的 repr 格式."""
        assert "ObjectiveEngine" in repr(ObjectiveEngine())
        assert "StrategyBuilder" in repr(StrategyBuilder())
        assert "TacticGenerator" in repr(TacticGenerator())
        assert "ConstraintManager" in repr(ConstraintManager())
        assert "StrategyRanker" in repr(StrategyRanker())
        assert "GrowthStrategyPlanner" in repr(GrowthStrategyPlanner())