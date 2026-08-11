"""E11.8.1 — Strategy Planner Tests。

覆盖：
  - Models: StrategyType, MutationFocus, EvolutionObjective, EvolutionStrategy
  - ObjectiveEngine: build/build_single from feedback/knowledge/population
  - StrategyRules: evaluate (winner_exploit, fix_failure, population_collapse, scale_success, explore_new)
  - StrategyPlanner: plan/plan_single/plan_with_objective/summarize
  - Controller Integration: generate_strategy/plan_and_schedule
  - Full Pipeline: end-to-end strategy generation
  - Package Exports
"""

from __future__ import annotations

import pytest

from market_ops.creative_vision_runtime.autonomous_controller.strategy.models import (
    EvolutionObjective,
    EvolutionStrategy,
    Horizon,
    Intensity,
    MutationFocus,
    StrategyType,
)
from market_ops.creative_vision_runtime.autonomous_controller.strategy.objective_engine import (
    ObjectiveEngine,
)
from market_ops.creative_vision_runtime.autonomous_controller.strategy.strategy_rules import (
    StrategyRules,
)
from market_ops.creative_vision_runtime.autonomous_controller.strategy.strategy_planner import (
    EvolutionStrategyPlanner,
)

# ── Helpers ──────────────────────────────────────────────────


def _make_feedback(
    metrics: dict | None = None,
    max_fitness: float = 0.0,
    success_count: int = 0,
    failure_count: int = 0,
    avg_roi: float = 0.0,
    sample_count: int = 0,
    top_genomes: list | None = None,
    failing_genomes: list | None = None,
) -> dict:
    return {
        "metrics": metrics or {},
        "max_fitness": max_fitness,
        "success_count": success_count,
        "failure_count": failure_count,
        "avg_roi": avg_roi,
        "sample_count": sample_count,
        "top_genomes": top_genomes or [],
        "failing_genomes": failing_genomes or [],
    }


def _make_knowledge(mutation_perf: dict | None = None) -> dict:
    return {
        "mutation_performance": mutation_perf or {},
    }


def _make_population(
    diversity_score: float = 0.5,
    avg_fitness: float = 50.0,
    total_count: int = 10,
    elite_count: int = 2,
    elite_ids: list | None = None,
) -> dict:
    return {
        "diversity_score": diversity_score,
        "avg_fitness": avg_fitness,
        "total_count": total_count,
        "elite_count": elite_count,
        "elite_ids": elite_ids or [],
    }


# ═══════════════════════════════════════════════════════════════
# Models
# ═══════════════════════════════════════════════════════════════


class TestStrategyType:
    """StrategyType 枚举测试。"""

    def test_values(self):
        assert StrategyType.EXPLOIT_WINNER.value == "exploit_winner"
        assert StrategyType.EXPLORE_NEW.value == "explore_new"
        assert StrategyType.FIX_FAILURE.value == "fix_failure"
        assert StrategyType.DIVERSIFY.value == "diversify"
        assert StrategyType.SCALE_SUCCESS.value == "scale_success"

    def test_count(self):
        assert len(StrategyType) == 5


class TestMutationFocus:
    """MutationFocus 枚举测试。"""

    def test_values(self):
        assert MutationFocus.HOOK.value == "hook"
        assert MutationFocus.VISUAL.value == "visual"
        assert MutationFocus.GAMEPLAY.value == "gameplay"
        assert MutationFocus.REWARD.value == "reward"
        assert MutationFocus.PACING.value == "pacing"
        assert MutationFocus.FULL.value == "full"

    def test_count(self):
        assert len(MutationFocus) == 6


class TestHorizon:
    """Horizon 枚举测试。"""

    def test_values(self):
        assert Horizon.SHORT.value == "SHORT"
        assert Horizon.MEDIUM.value == "MEDIUM"
        assert Horizon.LONG.value == "LONG"


class TestIntensity:
    """Intensity 枚举测试。"""

    def test_values(self):
        assert Intensity.SMALL.value == "small"
        assert Intensity.MEDIUM.value == "medium"
        assert Intensity.LARGE.value == "large"
        assert Intensity.RADICAL.value == "radical"


class TestEvolutionObjective:
    """EvolutionObjective 测试。"""

    def test_create_default(self):
        obj = EvolutionObjective()
        assert obj.objective_id.startswith("obj_")
        assert obj.metric == ""
        assert obj.priority == 0.0
        assert obj.horizon == Horizon.MEDIUM

    def test_create_full(self):
        obj = EvolutionObjective(
            metric="CTR",
            current_value=0.035,
            target_value=0.05,
            priority=0.8,
            horizon=Horizon.SHORT,
            reason="CTR underperforms",
        )
        assert obj.metric == "CTR"
        assert obj.current_value == 0.035
        assert obj.target_value == 0.05
        assert obj.priority == 0.8
        assert obj.reason == "CTR underperforms"

    def test_gap(self):
        obj = EvolutionObjective(metric="CTR", current_value=0.03, target_value=0.05)
        assert obj.gap == pytest.approx(0.02)

    def test_gap_no_negative(self):
        obj = EvolutionObjective(metric="CTR", current_value=0.06, target_value=0.05)
        assert obj.gap == 0.0

    def test_gap_pct(self):
        obj = EvolutionObjective(metric="CTR", current_value=0.03, target_value=0.05)
        assert obj.gap_pct == pytest.approx(0.4)

    def test_gap_pct_zero_target(self):
        obj = EvolutionObjective(metric="CTR", current_value=0.03, target_value=0.0)
        assert obj.gap_pct == 0.0

    def test_is_urgent_true(self):
        obj = EvolutionObjective(
            metric="CTR", priority=0.8, horizon=Horizon.SHORT
        )
        assert obj.is_urgent is True

    def test_is_urgent_false_low_priority(self):
        obj = EvolutionObjective(
            metric="CTR", priority=0.5, horizon=Horizon.SHORT
        )
        assert obj.is_urgent is False

    def test_is_urgent_false_medium(self):
        obj = EvolutionObjective(
            metric="CTR", priority=0.8, horizon=Horizon.MEDIUM
        )
        assert obj.is_urgent is False

    def test_to_dict(self):
        obj = EvolutionObjective(metric="ROI", current_value=1.0, target_value=1.5)
        d = obj.to_dict()
        assert d["metric"] == "ROI"
        assert d["gap"] == 0.5
        assert d["priority"] == 0.0

    def test_repr(self):
        obj = EvolutionObjective(metric="CTR", current_value=0.03, target_value=0.05, priority=0.8)
        r = repr(obj)
        assert "CTR" in r
        assert "0.030" in r
        assert "0.050" in r

    def test_metadata(self):
        obj = EvolutionObjective(metric="CTR", current_value=0.03, target_value=0.05,
                                 metadata={"source": "feedback"})
        assert obj.metadata["source"] == "feedback"

    def test_custom_id(self):
        obj = EvolutionObjective(objective_id="my_obj", metric="CTR")
        assert obj.objective_id == "my_obj"


class TestEvolutionStrategy:
    """EvolutionStrategy 测试。"""

    def test_create_default(self):
        s = EvolutionStrategy()
        assert s.strategy_id.startswith("strat_")
        assert s.strategy_type == StrategyType.EXPLORE_NEW
        assert s.objective is None
        assert s.mutation_focus == MutationFocus.FULL
        assert s.intensity == Intensity.MEDIUM

    def test_create_full(self):
        obj = EvolutionObjective(metric="CTR", current_value=0.03, target_value=0.05)
        s = EvolutionStrategy(
            strategy_type=StrategyType.EXPLOIT_WINNER,
            objective=obj,
            target_genomes=["g1", "g2"],
            mutation_focus=MutationFocus.HOOK,
            intensity=Intensity.SMALL,
            confidence=0.85,
            reason="Winner exploit",
        )
        assert s.strategy_type == StrategyType.EXPLOIT_WINNER
        assert s.objective == obj
        assert s.target_genomes == ["g1", "g2"]
        assert s.mutation_focus == MutationFocus.HOOK
        assert s.confidence == 0.85

    def test_is_high_confidence(self):
        s = EvolutionStrategy(confidence=0.8)
        assert s.is_high_confidence is True

    def test_is_low_confidence(self):
        s = EvolutionStrategy(confidence=0.5)
        assert s.is_high_confidence is False

    def test_is_exploit(self):
        s1 = EvolutionStrategy(strategy_type=StrategyType.EXPLOIT_WINNER)
        s2 = EvolutionStrategy(strategy_type=StrategyType.SCALE_SUCCESS)
        assert s1.is_exploit is True
        assert s2.is_exploit is True

    def test_is_not_exploit(self):
        s = EvolutionStrategy(strategy_type=StrategyType.EXPLORE_NEW)
        assert s.is_exploit is False

    def test_is_explore(self):
        s1 = EvolutionStrategy(strategy_type=StrategyType.EXPLORE_NEW)
        s2 = EvolutionStrategy(strategy_type=StrategyType.DIVERSIFY)
        assert s1.is_explore is True
        assert s2.is_explore is True

    def test_is_not_explore(self):
        s = EvolutionStrategy(strategy_type=StrategyType.FIX_FAILURE)
        assert s.is_explore is False

    def test_to_dict(self):
        obj = EvolutionObjective(metric="CTR", current_value=0.03, target_value=0.05)
        s = EvolutionStrategy(
            strategy_type=StrategyType.EXPLOIT_WINNER,
            objective=obj,
            mutation_focus=MutationFocus.HOOK,
            intensity=Intensity.SMALL,
        )
        d = s.to_dict()
        assert d["strategy_type"] == "exploit_winner"
        assert d["objective"] is not None
        assert d["mutation_focus"] == "hook"
        assert d["intensity"] == "small"

    def test_to_dict_no_objective(self):
        s = EvolutionStrategy()
        d = s.to_dict()
        assert d["objective"] is None

    def test_repr(self):
        s = EvolutionStrategy(
            strategy_type=StrategyType.EXPLOIT_WINNER,
            mutation_focus=MutationFocus.HOOK,
            intensity=Intensity.SMALL,
            confidence=0.85,
        )
        r = repr(s)
        assert "exploit_winner" in r
        assert "hook" in r

    def test_custom_id(self):
        s = EvolutionStrategy(strategy_id="my_strat")
        assert s.strategy_id == "my_strat"

    def test_metadata(self):
        s = EvolutionStrategy(metadata={"rule": "winner_exploit"})
        assert s.metadata["rule"] == "winner_exploit"

    def test_created_at(self):
        s = EvolutionStrategy()
        assert s.created_at != ""


# ═══════════════════════════════════════════════════════════════
# ObjectiveEngine
# ═══════════════════════════════════════════════════════════════


class TestObjectiveEngineFeedback:
    """ObjectiveEngine 从 feedback 构建目标。"""

    def test_build_from_feedback_ctr_low(self):
        engine = ObjectiveEngine()
        fb = _make_feedback(metrics={"CTR": 0.02})
        objs = engine.build(feedback=fb)
        assert len(objs) >= 1
        ctr_obj = [o for o in objs if o.metric == "CTR"][0]
        assert ctr_obj.current_value == 0.02
        assert ctr_obj.target_value == 0.05
        assert ctr_obj.priority > 0

    def test_build_from_feedback_roi_low(self):
        engine = ObjectiveEngine()
        fb = _make_feedback(metrics={"ROI": 0.8})
        objs = engine.build(feedback=fb)
        roi_obj = [o for o in objs if o.metric == "ROI"][0]
        assert roi_obj.current_value == 0.8
        assert roi_obj.target_value == 1.5

    def test_build_from_feedback_all_good(self):
        """指标达标时不生成目标。"""
        engine = ObjectiveEngine()
        fb = _make_feedback(metrics={"CTR": 0.06, "ROI": 2.0, "CVR": 0.15})
        objs = engine.build(feedback=fb)
        assert len(objs) == 0

    def test_build_from_feedback_multiple_metrics(self):
        engine = ObjectiveEngine()
        fb = _make_feedback(metrics={"CTR": 0.02, "ROI": 0.5, "CVR": 0.03})
        objs = engine.build(feedback=fb)
        assert len(objs) == 3

    def test_priority_sorted(self):
        engine = ObjectiveEngine()
        fb = _make_feedback(metrics={"CTR": 0.01, "ROI": 1.4})
        objs = engine.build(feedback=fb)
        # CTR has larger gap → higher priority
        assert objs[0].priority >= objs[-1].priority

    def test_sample_count_affects_priority(self):
        engine = ObjectiveEngine()
        fb_low = _make_feedback(metrics={"CTR": 0.005}, sample_count=50)
        fb_high = _make_feedback(metrics={"CTR": 0.005}, sample_count=500)
        objs_low = engine.build(feedback=fb_low)
        objs_high = engine.build(feedback=fb_high)
        assert objs_high[0].priority > objs_low[0].priority

    def test_feedback_metadata_source(self):
        engine = ObjectiveEngine()
        fb = _make_feedback(metrics={"CTR": 0.02})
        objs = engine.build(feedback=fb)
        assert objs[0].metadata["source"] == "feedback"

    def test_feedback_metadata_focus(self):
        engine = ObjectiveEngine()
        fb = _make_feedback(metrics={"CTR": 0.02})
        objs = engine.build(feedback=fb)
        assert objs[0].metadata["focus"] == "hook"

    def test_feedback_roi_metadata_focus(self):
        engine = ObjectiveEngine()
        fb = _make_feedback(metrics={"ROI": 0.5})
        objs = engine.build(feedback=fb)
        assert objs[0].metadata["focus"] == "reward"

    def test_empty_metrics(self):
        engine = ObjectiveEngine()
        fb = _make_feedback(metrics={})
        objs = engine.build(feedback=fb)
        assert len(objs) == 0

    def test_no_feedback(self):
        engine = ObjectiveEngine()
        objs = engine.build()
        assert len(objs) == 0


class TestObjectiveEngineKnowledge:
    """ObjectiveEngine 从 knowledge 构建目标。"""

    def test_low_success_rate(self):
        engine = ObjectiveEngine()
        k = _make_knowledge({"visual": {"success_rate": 0.2, "avg_gain": -10.0}})
        objs = engine.build(knowledge=k)
        assert len(objs) == 1
        assert objs[0].metric == "mutation:visual"
        assert objs[0].current_value == 0.2
        assert objs[0].target_value == 0.6

    def test_high_success_rate_no_objective(self):
        engine = ObjectiveEngine()
        k = _make_knowledge({"hook": {"success_rate": 0.9, "avg_gain": 20.0}})
        objs = engine.build(knowledge=k)
        assert len(objs) == 0

    def test_multiple_mutations(self):
        engine = ObjectiveEngine()
        k = _make_knowledge({
            "hook": {"success_rate": 0.8, "avg_gain": 15.0},
            "visual": {"success_rate": 0.2, "avg_gain": -10.0},
            "gameplay": {"success_rate": 0.3, "avg_gain": -5.0},
        })
        objs = engine.build(knowledge=k)
        assert len(objs) == 2  # visual and gameplay are low

    def test_knowledge_metadata(self):
        engine = ObjectiveEngine()
        k = _make_knowledge({"visual": {"success_rate": 0.2, "avg_gain": -10.0}})
        objs = engine.build(knowledge=k)
        assert objs[0].metadata["source"] == "knowledge"
        assert objs[0].metadata["mutation_type"] == "visual"


class TestObjectiveEnginePopulation:
    """ObjectiveEngine 从 population 构建目标。"""

    def test_diversity_collapse(self):
        engine = ObjectiveEngine()
        pop = _make_population(diversity_score=0.1, total_count=8)
        objs = engine.build(population=pop)
        assert len(objs) >= 1
        div_obj = [o for o in objs if o.metric == "Diversity"][0]
        assert div_obj.current_value == 0.1
        assert div_obj.horizon == Horizon.SHORT

    def test_diversity_ok(self):
        engine = ObjectiveEngine()
        pop = _make_population(diversity_score=0.5)
        objs = engine.build(population=pop)
        div_objs = [o for o in objs if o.metric == "Diversity"]
        assert len(div_objs) == 0

    def test_low_avg_fitness(self):
        engine = ObjectiveEngine()
        pop = _make_population(avg_fitness=30.0, total_count=5)
        objs = engine.build(population=pop)
        fit_objs = [o for o in objs if o.metric == "avg_fitness"]
        assert len(fit_objs) == 1
        assert fit_objs[0].current_value == 30.0

    def test_avg_fitness_ok(self):
        engine = ObjectiveEngine()
        pop = _make_population(avg_fitness=70.0, total_count=5)
        objs = engine.build(population=pop)
        fit_objs = [o for o in objs if o.metric == "avg_fitness"]
        assert len(fit_objs) == 0

    def test_population_metadata(self):
        engine = ObjectiveEngine()
        pop = _make_population(diversity_score=0.1, avg_fitness=30.0, total_count=5)
        objs = engine.build(population=pop)
        assert objs[0].metadata["source"] == "population"

    def test_empty_population(self):
        engine = ObjectiveEngine()
        pop = _make_population(diversity_score=0.5, avg_fitness=70.0, total_count=0)
        objs = engine.build(population=pop)
        assert len(objs) == 0


class TestObjectiveEngineCombined:
    """ObjectiveEngine 多源合并测试。"""

    def test_build_from_all_sources(self):
        engine = ObjectiveEngine()
        fb = _make_feedback(metrics={"CTR": 0.02})
        k = _make_knowledge({"visual": {"success_rate": 0.2, "avg_gain": -10.0}})
        pop = _make_population(diversity_score=0.1, avg_fitness=30.0, total_count=5)
        objs = engine.build(feedback=fb, knowledge=k, population=pop)
        assert len(objs) >= 3

    def test_build_single(self):
        engine = ObjectiveEngine()
        fb = _make_feedback(metrics={"CTR": 0.02})
        obj = engine.build_single(feedback=fb)
        assert obj is not None
        assert obj.metric == "CTR"

    def test_build_single_none(self):
        engine = ObjectiveEngine()
        obj = engine.build_single()
        assert obj is None

    def test_set_target(self):
        engine = ObjectiveEngine()
        engine.set_target("CTR", 0.08)
        assert engine.get_default_target("CTR") == 0.08

    def test_get_default_target(self):
        engine = ObjectiveEngine()
        assert engine.get_default_target("CTR") == 0.05
        assert engine.get_default_target("unknown") == 0.0

    def test_repr(self):
        engine = ObjectiveEngine()
        assert "ObjectiveEngine" in repr(engine)


# ═══════════════════════════════════════════════════════════════
# StrategyRules
# ═══════════════════════════════════════════════════════════════


class TestStrategyRulesWinnerExploit:
    """Rule: Winner Exploit。"""

    def test_winner_exploit_triggered(self):
        rules = StrategyRules()
        obj = EvolutionObjective(metric="CTR", current_value=0.03, target_value=0.05)
        fb = _make_feedback(max_fitness=85.0, success_count=6)
        s = rules.evaluate(obj, feedback=fb)
        assert s.strategy_type == StrategyType.EXPLOIT_WINNER
        assert s.intensity == Intensity.SMALL
        assert s.mutation_focus == MutationFocus.HOOK

    def test_winner_exploit_not_triggered_low_fitness(self):
        rules = StrategyRules()
        obj = EvolutionObjective(metric="CTR", current_value=0.03, target_value=0.05)
        fb = _make_feedback(max_fitness=70.0, success_count=6)
        s = rules.evaluate(obj, feedback=fb)
        assert s.strategy_type != StrategyType.EXPLOIT_WINNER

    def test_winner_exploit_not_triggered_low_count(self):
        rules = StrategyRules()
        obj = EvolutionObjective(metric="CTR", current_value=0.03, target_value=0.05)
        fb = _make_feedback(max_fitness=85.0, success_count=3)
        s = rules.evaluate(obj, feedback=fb)
        assert s.strategy_type != StrategyType.EXPLOIT_WINNER

    def test_winner_exploit_exact_boundary(self):
        rules = StrategyRules()
        obj = EvolutionObjective(metric="CTR", current_value=0.03, target_value=0.05)
        fb = _make_feedback(max_fitness=80.0, success_count=5)
        s = rules.evaluate(obj, feedback=fb)
        assert s.strategy_type == StrategyType.EXPLOIT_WINNER

    def test_winner_exploit_no_focus_metadata(self):
        """没有 focus metadata 时默认 HOOK。"""
        rules = StrategyRules()
        obj = EvolutionObjective(metric="avg_fitness", current_value=30.0, target_value=70.0)
        fb = _make_feedback(max_fitness=85.0, success_count=6)
        s = rules.evaluate(obj, feedback=fb)
        assert s.mutation_focus == MutationFocus.HOOK


class TestStrategyRulesFixFailure:
    """Rule: Fix Failure。"""

    def test_fix_failure_triggered(self):
        rules = StrategyRules()
        obj = EvolutionObjective(metric="CTR", current_value=0.02, target_value=0.05)
        fb = _make_feedback(failure_count=5)
        s = rules.evaluate(obj, feedback=fb)
        assert s.strategy_type == StrategyType.FIX_FAILURE
        assert s.intensity == Intensity.LARGE

    def test_fix_failure_not_triggered(self):
        rules = StrategyRules()
        obj = EvolutionObjective(metric="CTR", current_value=0.02, target_value=0.05)
        fb = _make_feedback(failure_count=2)
        s = rules.evaluate(obj, feedback=fb)
        assert s.strategy_type != StrategyType.FIX_FAILURE

    def test_fix_failure_exact_boundary(self):
        rules = StrategyRules()
        obj = EvolutionObjective(metric="CTR", current_value=0.02, target_value=0.05)
        fb = _make_feedback(failure_count=3)
        s = rules.evaluate(obj, feedback=fb)
        assert s.strategy_type == StrategyType.FIX_FAILURE


class TestStrategyRulesPopulationCollapse:
    """Rule: Population Collapse。"""

    def test_population_collapse_triggered(self):
        rules = StrategyRules()
        obj = EvolutionObjective(metric="Diversity", current_value=0.1, target_value=0.3)
        pop = _make_population(diversity_score=0.1)
        s = rules.evaluate(obj, population=pop)
        assert s.strategy_type == StrategyType.DIVERSIFY
        assert s.intensity == Intensity.RADICAL
        assert s.mutation_focus == MutationFocus.FULL

    def test_population_collapse_not_triggered(self):
        rules = StrategyRules()
        obj = EvolutionObjective(metric="Diversity", current_value=0.4, target_value=0.5)
        pop = _make_population(diversity_score=0.4)
        s = rules.evaluate(obj, population=pop)
        assert s.strategy_type != StrategyType.DIVERSIFY

    def test_population_collapse_priority_over_failure(self):
        """Population collapse 优先级高于 fix_failure。"""
        rules = StrategyRules()
        obj = EvolutionObjective(metric="Diversity", current_value=0.1, target_value=0.3)
        fb = _make_feedback(failure_count=5)
        pop = _make_population(diversity_score=0.1)
        s = rules.evaluate(obj, feedback=fb, population=pop)
        assert s.strategy_type == StrategyType.DIVERSIFY

    def test_population_collapse_priority_over_winner(self):
        """Population collapse 优先级高于 winner exploit。"""
        rules = StrategyRules()
        obj = EvolutionObjective(metric="Diversity", current_value=0.1, target_value=0.3)
        fb = _make_feedback(max_fitness=85.0, success_count=6)
        pop = _make_population(diversity_score=0.1)
        s = rules.evaluate(obj, feedback=fb, population=pop)
        assert s.strategy_type == StrategyType.DIVERSIFY


class TestStrategyRulesScaleSuccess:
    """Rule: Scale Success。"""

    def test_scale_success_triggered(self):
        rules = StrategyRules()
        obj = EvolutionObjective(metric="CTR", current_value=0.03, target_value=0.05)
        fb = _make_feedback(avg_roi=2.0, success_count=12)
        s = rules.evaluate(obj, feedback=fb)
        assert s.strategy_type == StrategyType.SCALE_SUCCESS
        assert s.intensity == Intensity.MEDIUM

    def test_scale_success_not_triggered_low_roi(self):
        rules = StrategyRules()
        obj = EvolutionObjective(metric="CTR", current_value=0.03, target_value=0.05)
        fb = _make_feedback(avg_roi=1.2, success_count=12)
        s = rules.evaluate(obj, feedback=fb)
        assert s.strategy_type != StrategyType.SCALE_SUCCESS

    def test_scale_success_not_triggered_low_count(self):
        rules = StrategyRules()
        obj = EvolutionObjective(metric="CTR", current_value=0.03, target_value=0.05)
        fb = _make_feedback(avg_roi=2.0, success_count=8)
        s = rules.evaluate(obj, feedback=fb)
        assert s.strategy_type != StrategyType.SCALE_SUCCESS

    def test_scale_success_exact_boundary(self):
        rules = StrategyRules()
        obj = EvolutionObjective(metric="CTR", current_value=0.03, target_value=0.05)
        fb = _make_feedback(avg_roi=1.5, success_count=10)
        s = rules.evaluate(obj, feedback=fb)
        assert s.strategy_type == StrategyType.SCALE_SUCCESS


class TestStrategyRulesExploreNew:
    """Rule: Explore New（兜底）。"""

    def test_explore_new_default(self):
        rules = StrategyRules()
        obj = EvolutionObjective(metric="CTR", current_value=0.03, target_value=0.05)
        s = rules.evaluate(obj)
        assert s.strategy_type == StrategyType.EXPLORE_NEW
        assert s.intensity == Intensity.MEDIUM

    def test_explore_new_with_sample_count(self):
        rules = StrategyRules()
        obj = EvolutionObjective(metric="CTR", current_value=0.03, target_value=0.05)
        fb = _make_feedback(sample_count=100)
        s = rules.evaluate(obj, feedback=fb)
        assert s.strategy_type == StrategyType.EXPLORE_NEW
        assert s.confidence > 0.3

    def test_explore_new_no_sample_count(self):
        rules = StrategyRules()
        obj = EvolutionObjective(metric="CTR", current_value=0.03, target_value=0.05)
        s = rules.evaluate(obj)
        assert s.confidence == 0.3


class TestStrategyRulesEvaluateMultiple:
    """evaluate_multiple 批量测试。"""

    def test_multiple_objectives(self):
        rules = StrategyRules()
        objs = [
            EvolutionObjective(metric="CTR", current_value=0.02, target_value=0.05),
            EvolutionObjective(metric="ROI", current_value=0.5, target_value=1.5),
        ]
        fb = _make_feedback(max_fitness=85.0, success_count=6)
        strategies = rules.evaluate_multiple(objs, feedback=fb)
        assert len(strategies) == 2
        assert strategies[0].strategy_type == StrategyType.EXPLOIT_WINNER

    def test_empty_objectives(self):
        rules = StrategyRules()
        strategies = rules.evaluate_multiple([])
        assert len(strategies) == 0


class TestStrategyRulesCustomThresholds:
    """自定义阈值测试。"""

    def test_custom_winner_fitness(self):
        rules = StrategyRules(winner_fitness=70.0)
        obj = EvolutionObjective(metric="CTR", current_value=0.03, target_value=0.05)
        fb = _make_feedback(max_fitness=75.0, success_count=6)
        s = rules.evaluate(obj, feedback=fb)
        assert s.strategy_type == StrategyType.EXPLOIT_WINNER

    def test_custom_failure_count(self):
        rules = StrategyRules(failure_count=2)
        obj = EvolutionObjective(metric="CTR", current_value=0.02, target_value=0.05)
        fb = _make_feedback(failure_count=2)
        s = rules.evaluate(obj, feedback=fb)
        assert s.strategy_type == StrategyType.FIX_FAILURE

    def test_custom_diversity_threshold(self):
        rules = StrategyRules(diversity_threshold=0.3)
        obj = EvolutionObjective(metric="Diversity", current_value=0.25, target_value=0.4)
        pop = _make_population(diversity_score=0.25)
        s = rules.evaluate(obj, population=pop)
        assert s.strategy_type == StrategyType.DIVERSIFY

    def test_repr(self):
        rules = StrategyRules()
        assert "StrategyRules" in repr(rules)


# ═══════════════════════════════════════════════════════════════
# StrategyPlanner
# ═══════════════════════════════════════════════════════════════


class TestStrategyPlanner:
    """EvolutionStrategyPlanner 测试。"""

    def test_plan_empty(self):
        planner = EvolutionStrategyPlanner()
        strategies = planner.plan()
        assert len(strategies) == 0

    def test_plan_from_feedback(self):
        planner = EvolutionStrategyPlanner()
        fb = _make_feedback(metrics={"CTR": 0.02})
        strategies = planner.plan(feedback=fb)
        assert len(strategies) >= 1
        assert strategies[0].objective is not None

    def test_plan_single(self):
        planner = EvolutionStrategyPlanner()
        fb = _make_feedback(metrics={"CTR": 0.02})
        s = planner.plan_single(feedback=fb)
        assert s is not None
        assert s.strategy_type in StrategyType

    def test_plan_single_none(self):
        planner = EvolutionStrategyPlanner()
        s = planner.plan_single()
        assert s is None

    def test_plan_with_objective(self):
        planner = EvolutionStrategyPlanner()
        obj = EvolutionObjective(metric="CTR", current_value=0.03, target_value=0.05)
        fb = _make_feedback(max_fitness=85.0, success_count=6)
        s = planner.plan_with_objective(obj, feedback=fb)
        assert s.strategy_type == StrategyType.EXPLOIT_WINNER
        assert s.objective == obj

    def test_plan_with_population_collapse(self):
        planner = EvolutionStrategyPlanner()
        pop = _make_population(diversity_score=0.1)
        strategies = planner.plan(population=pop)
        assert len(strategies) >= 1
        assert strategies[0].strategy_type == StrategyType.DIVERSIFY

    def test_plan_with_all_inputs(self):
        planner = EvolutionStrategyPlanner()
        fb = _make_feedback(metrics={"CTR": 0.02}, max_fitness=85.0, success_count=6)
        k = _make_knowledge({"visual": {"success_rate": 0.2, "avg_gain": -10.0}})
        pop = _make_population(diversity_score=0.5)
        strategies = planner.plan(feedback=fb, knowledge=k, population=pop)
        assert len(strategies) >= 1

    def test_dependency_injection(self):
        obj_engine = ObjectiveEngine()
        rules = StrategyRules()
        planner = EvolutionStrategyPlanner(
            objective_engine=obj_engine,
            strategy_rules=rules,
        )
        assert planner.objective_engine is obj_engine
        assert planner.strategy_rules is rules

    def test_repr(self):
        planner = EvolutionStrategyPlanner()
        assert "EvolutionStrategyPlanner" in repr(planner)


class TestStrategyPlannerSummarize:
    """summarize 测试。"""

    def test_empty(self):
        planner = EvolutionStrategyPlanner()
        summary = planner.summarize([])
        assert summary["total"] == 0
        assert summary["top_strategy"] is None

    def test_with_strategies(self):
        planner = EvolutionStrategyPlanner()
        obj = EvolutionObjective(metric="CTR", current_value=0.03, target_value=0.05)
        strategies = [
            EvolutionStrategy(strategy_type=StrategyType.EXPLOIT_WINNER, objective=obj, confidence=0.8),
            EvolutionStrategy(strategy_type=StrategyType.EXPLORE_NEW, objective=obj, confidence=0.5),
        ]
        summary = planner.summarize(strategies)
        assert summary["total"] == 2
        assert summary["by_type"]["exploit_winner"] == 1
        assert summary["by_type"]["explore_new"] == 1
        assert summary["exploit_count"] == 1
        assert summary["explore_count"] == 1
        assert summary["avg_confidence"] == 0.65

    def test_by_focus(self):
        planner = EvolutionStrategyPlanner()
        strategies = [
            EvolutionStrategy(mutation_focus=MutationFocus.HOOK),
            EvolutionStrategy(mutation_focus=MutationFocus.HOOK),
            EvolutionStrategy(mutation_focus=MutationFocus.VISUAL),
        ]
        summary = planner.summarize(strategies)
        assert summary["by_focus"]["hook"] == 2
        assert summary["by_focus"]["visual"] == 1

    def test_top_strategy(self):
        planner = EvolutionStrategyPlanner()
        strategies = [
            EvolutionStrategy(strategy_type=StrategyType.FIX_FAILURE, confidence=0.9),
            EvolutionStrategy(strategy_type=StrategyType.EXPLORE_NEW, confidence=0.3),
        ]
        summary = planner.summarize(strategies)
        assert summary["top_strategy"] == strategies[0]


# ═══════════════════════════════════════════════════════════════
# Controller Integration
# ═══════════════════════════════════════════════════════════════


class TestControllerStrategyIntegration:
    """Controller E11.8.1 集成测试。"""

    @pytest.fixture
    def controller(self):
        from unittest.mock import MagicMock
        from market_ops.creative_vision_runtime.autonomous_controller.controller import (
            AutonomousCreativeController,
        )
        engine = MagicMock()
        return AutonomousCreativeController(intelligence_engine=engine)

    def test_generate_strategy(self, controller):
        fb = _make_feedback(metrics={"CTR": 0.02})
        strategies = controller.generate_strategy(feedback=fb)
        assert len(strategies) >= 1
        assert all(isinstance(s, EvolutionStrategy) for s in strategies)

    def test_generate_strategy_single(self, controller):
        fb = _make_feedback(metrics={"CTR": 0.02})
        s = controller.generate_strategy_single(feedback=fb)
        assert s is not None
        assert isinstance(s, EvolutionStrategy)

    def test_generate_strategy_empty(self, controller):
        strategies = controller.generate_strategy()
        assert len(strategies) == 0

    def test_plan_and_schedule(self, controller):
        fb = _make_feedback(metrics={"CTR": 0.02})
        result = controller.plan_and_schedule(feedback=fb)
        assert "strategies" in result
        assert "strategy_summary" in result
        assert len(result["strategies"]) >= 1

    def test_plan_and_schedule_with_signals(self, controller):
        from market_ops.creative_vision_runtime.autonomous_controller.feedback.models import (
            LearningSignal,
            LearningDirection,
        )
        fb = _make_feedback(metrics={"CTR": 0.02})
        signals = [
            LearningSignal(
                genome_id="g1",
                direction=LearningDirection.MUTATE,
                confidence=0.7,
            )
        ]
        result = controller.plan_and_schedule(
            feedback=fb,
            learning_signals=signals,
        )
        assert "policy_result" in result
        assert "scheduler_result" in result

    def test_strategy_planner_property(self, controller):
        assert controller.strategy_planner is not None
        assert isinstance(controller.strategy_planner, EvolutionStrategyPlanner)

    def test_constructor_injection(self):
        from unittest.mock import MagicMock
        from market_ops.creative_vision_runtime.autonomous_controller.controller import (
            AutonomousCreativeController,
        )
        engine = MagicMock()
        planner = EvolutionStrategyPlanner()
        controller = AutonomousCreativeController(
            intelligence_engine=engine,
            strategy_planner=planner,
        )
        assert controller.strategy_planner is planner


# ═══════════════════════════════════════════════════════════════
# Full Pipeline
# ═══════════════════════════════════════════════════════════════


class TestFullPipeline:
    """端到端策略生成流程。"""

    def test_feedback_to_strategy_pipeline(self):
        """Feedback → Objective → Strategy 完整链路。"""
        engine = ObjectiveEngine()
        rules = StrategyRules()

        fb = _make_feedback(
            metrics={"CTR": 0.025, "ROI": 0.8},
            max_fitness=85.0,
            success_count=6,
            sample_count=200,
        )

        objs = engine.build(feedback=fb)
        assert len(objs) >= 2

        for obj in objs:
            strategy = rules.evaluate(obj, feedback=fb)
            assert strategy is not None
            assert strategy.strategy_type in StrategyType
            assert strategy.confidence > 0

    def test_population_collapse_pipeline(self):
        """Population Collapse → DIVERSIFY 完整链路。"""
        engine = ObjectiveEngine()
        rules = StrategyRules()

        pop = _make_population(diversity_score=0.08, avg_fitness=25.0, total_count=5)
        objs = engine.build(population=pop)
        assert len(objs) >= 1

        strategy = rules.evaluate(objs[0], population=pop)
        assert strategy.strategy_type == StrategyType.DIVERSIFY
        assert strategy.intensity == Intensity.RADICAL
        assert strategy.mutation_focus == MutationFocus.FULL

    def test_failure_repair_pipeline(self):
        """Failure → FIX_FAILURE 完整链路。"""
        engine = ObjectiveEngine()
        rules = StrategyRules()

        fb = _make_feedback(
            metrics={"ROI": 0.3},
            failure_count=5,
            sample_count=50,
        )
        objs = engine.build(feedback=fb)
        assert len(objs) >= 1

        strategy = rules.evaluate(objs[0], feedback=fb)
        assert strategy.strategy_type == StrategyType.FIX_FAILURE
        assert strategy.intensity == Intensity.LARGE

    def test_scale_success_pipeline(self):
        """Scale Success 完整链路。"""
        engine = ObjectiveEngine()
        rules = StrategyRules()

        fb = _make_feedback(
            metrics={"CTR": 0.04},
            avg_roi=2.5,
            success_count=15,
            max_fitness=90.0,
        )
        objs = engine.build(feedback=fb)
        # CTR 0.04 < 0.05, so there should be at least 1 objective
        if objs:
            strategy = rules.evaluate(objs[0], feedback=fb)
            # Scale success takes priority over winner exploit
            # Since we have avg_roi=2.5 and success_count=15, scale_success fires
            # But if there's a population collapse trigger, that wins
            assert strategy.strategy_type in (
                StrategyType.SCALE_SUCCESS,
                StrategyType.EXPLOIT_WINNER,
            )

    def test_knowledge_informs_strategy(self):
        """Knowledge 数据影响策略方向。"""
        engine = ObjectiveEngine()
        rules = StrategyRules()

        k = _make_knowledge({
            "visual": {"success_rate": 0.15, "avg_gain": -15.0},
            "hook": {"success_rate": 0.85, "avg_gain": 20.0},
        })
        objs = engine.build(knowledge=k)
        assert len(objs) >= 1

        # visual 低成功率 → 生成修复目标
        visual_obj = [o for o in objs if "visual" in o.metric]
        assert len(visual_obj) == 1

        strategy = rules.evaluate(visual_obj[0])
        assert strategy.strategy_type == StrategyType.EXPLORE_NEW
        assert strategy.mutation_focus == MutationFocus.VISUAL

    def test_planner_full_pipeline(self):
        """Planner 完整多源端到端。"""
        planner = EvolutionStrategyPlanner()
        fb = _make_feedback(
            metrics={"CTR": 0.02, "ROI": 0.6},
            max_fitness=85.0,
            success_count=6,
            sample_count=200,
        )
        k = _make_knowledge({"visual": {"success_rate": 0.2, "avg_gain": -10.0}})
        pop = _make_population(diversity_score=0.4, avg_fitness=55.0, total_count=10)

        strategies = planner.plan(feedback=fb, knowledge=k, population=pop)
        assert len(strategies) >= 1

        # 验证策略输出结构
        for s in strategies:
            assert s.strategy_id != ""
            assert s.strategy_type in StrategyType
            assert s.objective is not None
            assert s.confidence >= 0.0
            assert s.reason != ""


# ═══════════════════════════════════════════════════════════════
# Package Exports
# ═══════════════════════════════════════════════════════════════


class TestPackageExports:
    """包导出测试。"""

    def test_exports_models(self):
        from market_ops.creative_vision_runtime.autonomous_controller.strategy import (
            StrategyType,
            MutationFocus,
            Horizon,
            Intensity,
            EvolutionObjective,
            EvolutionStrategy,
        )
        assert StrategyType is not None
        assert MutationFocus is not None
        assert Horizon is not None
        assert Intensity is not None
        assert EvolutionObjective is not None
        assert EvolutionStrategy is not None

    def test_exports_engines(self):
        from market_ops.creative_vision_runtime.autonomous_controller.strategy import (
            ObjectiveEngine,
            StrategyRules,
            EvolutionStrategyPlanner,
        )
        assert ObjectiveEngine is not None
        assert StrategyRules is not None
        assert EvolutionStrategyPlanner is not None