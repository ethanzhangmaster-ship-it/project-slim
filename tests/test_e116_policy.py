"""E11.6 — Evolution Policy Layer 测试。

测试范围：
  - EvolutionAction / MutationStrategy: 枚举值
  - EvolutionPolicyDecision: 数据模型 + 属性 + 自动填充 + 序列化
  - PopulationDecision: 数据模型 + 属性 + 序列化
  - PolicyResult: 批量结果 + 统计 + 过滤
  - PolicyRule: 规则评估 + 匹配/不匹配
  - Builtin Rules: 5 条内置规则逐条验证
  - StrategySelector: select + 方向映射 + fitness 细分 + 参数获取
  - PopulationPolicy: 5 种动作处理 + 批量
  - EvolutionPolicyEngine: decide + decide_with_population + 过滤 + 规则管理
  - Controller Integration: apply_learning_policy + apply_learning_policy_and_evolve
  - Full Pipeline: LearningSignal → PolicyDecision → PopulationDecision
  - Package exports
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from market_ops.creative_vision_runtime.autonomous_controller.policy.models import (
    EvolutionAction,
    MutationStrategy,
    EvolutionPolicyDecision,
    PopulationDecision,
    PolicyResult,
    MUTATION_RATE_MAP,
    TARGET_GENES_MAP,
)
from market_ops.creative_vision_runtime.autonomous_controller.policy.policy_rules import (
    PolicyRule,
    build_default_rules,
)
from market_ops.creative_vision_runtime.autonomous_controller.policy.strategy_selector import (
    StrategySelector,
)
from market_ops.creative_vision_runtime.autonomous_controller.policy.population_policy import (
    PopulationPolicy,
)
from market_ops.creative_vision_runtime.autonomous_controller.policy.policy_engine import (
    EvolutionPolicyEngine,
)
from market_ops.creative_vision_runtime.autonomous_controller.feedback.models import (
    LearningSignal,
    LearningDirection,
    FitnessScore,
    PerformanceSignal,
)


# ═══════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════

def _make_winner_signal(genome_id: str = "g_winner") -> LearningSignal:
    return LearningSignal(
        genome_id=genome_id,
        direction=LearningDirection.KEEP,
        confidence=0.92,
        insights=["Strong ROI performance", "High CTR engagement"],
        recommended_mutations=["Keep current gene configuration"],
    )


def _make_improve_signal(genome_id: str = "g_avg") -> LearningSignal:
    return LearningSignal(
        genome_id=genome_id,
        direction=LearningDirection.IMPROVE,
        confidence=0.65,
        insights=["Moderate performance across metrics"],
        recommended_mutations=["increase_hook_contrast"],
    )


def _make_failure_signal(genome_id: str = "g_low") -> LearningSignal:
    return LearningSignal(
        genome_id=genome_id,
        direction=LearningDirection.MUTATE,
        confidence=0.35,
        consecutive_failures=1,
        insights=["ROI underperforming", "Low CTR engagement"],
        recommended_mutations=[
            "increase_hook_contrast",
            "increase_transition_speed",
        ],
    )


def _make_dead_signal(genome_id: str = "g_dead") -> LearningSignal:
    return LearningSignal(
        genome_id=genome_id,
        direction=LearningDirection.MUTATE,
        confidence=0.15,
        consecutive_failures=3,
        insights=["ROI underperforming"],
    )


def _make_retire_signal(genome_id: str = "g_retired") -> LearningSignal:
    return LearningSignal(
        genome_id=genome_id,
        direction=LearningDirection.RETIRE,
        confidence=0.5,
        consecutive_failures=3,
    )


def _make_winner_fitness(genome_id: str = "g_winner") -> FitnessScore:
    return FitnessScore(
        genome_id=genome_id,
        overall_score=85.0,
        roi_score=100.0,
        ctr_score=100.0,
        cvr_score=100.0,
        revenue_score=80.0,
        rank=1,
    )


def _make_avg_fitness(genome_id: str = "g_avg") -> FitnessScore:
    return FitnessScore(
        genome_id=genome_id,
        overall_score=65.0,
        roi_score=60.0,
        ctr_score=60.0,
        cvr_score=60.0,
        revenue_score=80.0,
        rank=2,
    )


def _make_low_fitness(genome_id: str = "g_low") -> FitnessScore:
    return FitnessScore(
        genome_id=genome_id,
        overall_score=30.0,
        roi_score=20.0,
        ctr_score=20.0,
        cvr_score=20.0,
        revenue_score=40.0,
        rank=3,
    )


def _make_dead_fitness(genome_id: str = "g_dead") -> FitnessScore:
    return FitnessScore(
        genome_id=genome_id,
        overall_score=25.0,
        roi_score=20.0,
        ctr_score=20.0,
        cvr_score=20.0,
        revenue_score=40.0,
        rank=4,
    )


# ═══════════════════════════════════════════════════════════
# 1. Models — Enums
# ═══════════════════════════════════════════════════════════

class TestEvolutionAction:
    """EvolutionAction 枚举测试。"""

    def test_values(self):
        assert EvolutionAction.KEEP.value == "keep"
        assert EvolutionAction.EXPLOIT.value == "exploit"
        assert EvolutionAction.EXPLORE.value == "explore"
        assert EvolutionAction.MUTATE.value == "mutate"
        assert EvolutionAction.CROSSOVER.value == "crossover"
        assert EvolutionAction.RETIRE.value == "retire"


class TestMutationStrategy:
    """MutationStrategy 枚举测试。"""

    def test_values(self):
        assert MutationStrategy.SMALL.value == "small"
        assert MutationStrategy.MEDIUM.value == "medium"
        assert MutationStrategy.LARGE.value == "large"
        assert MutationStrategy.RADICAL.value == "radical"

    def test_mutation_rate_map(self):
        assert MUTATION_RATE_MAP[MutationStrategy.SMALL] == 0.1
        assert MUTATION_RATE_MAP[MutationStrategy.MEDIUM] == 0.3
        assert MUTATION_RATE_MAP[MutationStrategy.LARGE] == 0.6
        assert MUTATION_RATE_MAP[MutationStrategy.RADICAL] == 0.9

    def test_target_genes_map(self):
        assert "hook" in TARGET_GENES_MAP[MutationStrategy.SMALL]
        assert len(TARGET_GENES_MAP[MutationStrategy.SMALL]) == 1
        assert len(TARGET_GENES_MAP[MutationStrategy.MEDIUM]) == 3
        assert len(TARGET_GENES_MAP[MutationStrategy.LARGE]) == 5
        assert len(TARGET_GENES_MAP[MutationStrategy.RADICAL]) == 8


# ═══════════════════════════════════════════════════════════
# 2. Models — EvolutionPolicyDecision
# ═══════════════════════════════════════════════════════════

class TestEvolutionPolicyDecision:
    """EvolutionPolicyDecision 数据模型测试。"""

    def test_create_default(self):
        """默认创建：auto-generated decision_id。"""
        epd = EvolutionPolicyDecision()
        assert epd.decision_id.startswith("epd_")
        assert epd.action == EvolutionAction.KEEP
        assert epd.mutation_strategy == MutationStrategy.SMALL

    def test_create_with_values(self):
        """带值创建。"""
        epd = EvolutionPolicyDecision(
            genome_id="g001",
            action=EvolutionAction.EXPLOIT,
            mutation_strategy=MutationStrategy.SMALL,
            mutation_rate=0.1,
            target_genes=["hook"],
            confidence=0.92,
            reason="Winner genome, exploiting",
        )
        assert epd.genome_id == "g001"
        assert epd.action == EvolutionAction.EXPLOIT
        assert epd.mutation_rate == 0.1
        assert epd.target_genes == ["hook"]
        assert epd.confidence == 0.92

    def test_auto_fill_mutation_rate(self):
        """自动填充 mutation_rate 和 target_genes。"""
        epd = EvolutionPolicyDecision(
            genome_id="g001",
            action=EvolutionAction.EXPLORE,
            mutation_strategy=MutationStrategy.LARGE,
        )
        assert epd.mutation_rate == 0.6
        assert len(epd.target_genes) == 5

    def test_auto_fill_radical(self):
        """RADICAL 策略自动填充。"""
        epd = EvolutionPolicyDecision(
            genome_id="g001",
            action=EvolutionAction.EXPLORE,
            mutation_strategy=MutationStrategy.RADICAL,
        )
        assert epd.mutation_rate == 0.9
        assert len(epd.target_genes) == 8

    def test_is_active(self):
        """KEEP 以外都是 active。"""
        assert EvolutionPolicyDecision(action=EvolutionAction.EXPLOIT).is_active is True
        assert EvolutionPolicyDecision(action=EvolutionAction.MUTATE).is_active is True
        assert EvolutionPolicyDecision(action=EvolutionAction.EXPLORE).is_active is True
        assert EvolutionPolicyDecision(action=EvolutionAction.RETIRE).is_active is True
        assert EvolutionPolicyDecision(action=EvolutionAction.KEEP).is_active is False

    def test_is_retire(self):
        assert EvolutionPolicyDecision(action=EvolutionAction.RETIRE).is_retire is True
        assert EvolutionPolicyDecision(action=EvolutionAction.EXPLOIT).is_retire is False

    def test_to_dict(self):
        epd = EvolutionPolicyDecision(
            genome_id="g001",
            action=EvolutionAction.EXPLOIT,
            mutation_strategy=MutationStrategy.SMALL,
            mutation_rate=0.1,
            confidence=0.92,
            reason="test",
        )
        d = epd.to_dict()
        assert d["genome_id"] == "g001"
        assert d["action"] == "exploit"
        assert d["mutation_strategy"] == "small"
        assert d["mutation_rate"] == 0.1

    def test_repr(self):
        epd = EvolutionPolicyDecision(
            genome_id="g001",
            action=EvolutionAction.EXPLOIT,
            mutation_strategy=MutationStrategy.SMALL,
            mutation_rate=0.1,
        )
        r = repr(epd)
        assert "g001" in r
        assert "exploit" in r


# ═══════════════════════════════════════════════════════════
# 3. Models — PopulationDecision
# ═══════════════════════════════════════════════════════════

class TestPopulationDecision:
    """PopulationDecision 数据模型测试。"""

    def test_create_default(self):
        pd = PopulationDecision()
        assert pd.weight_change == 0.0
        assert pd.remove is False
        assert pd.clone_count == 0

    def test_create_remove(self):
        pd = PopulationDecision(genome_id="g001", remove=True, reason="dead genome")
        assert pd.is_remove is True
        assert pd.is_clone is False

    def test_create_clone(self):
        pd = PopulationDecision(genome_id="g001", clone_count=2, weight_change=0.2)
        assert pd.is_clone is True
        assert pd.is_remove is False

    def test_to_dict(self):
        pd = PopulationDecision(
            genome_id="g001",
            weight_change=0.2,
            clone_count=2,
            reason="winner",
        )
        d = pd.to_dict()
        assert d["genome_id"] == "g001"
        assert d["weight_change"] == 0.2
        assert d["clone_count"] == 2

    def test_repr_remove(self):
        pd = PopulationDecision(genome_id="g001", remove=True)
        assert "REMOVE" in repr(pd)

    def test_repr_clone(self):
        pd = PopulationDecision(genome_id="g001", clone_count=3)
        assert "CLONE x3" in repr(pd)

    def test_repr_weight(self):
        pd = PopulationDecision(genome_id="g001", weight_change=0.15)
        assert "+0.15" in repr(pd)


# ═══════════════════════════════════════════════════════════
# 4. Models — PolicyResult
# ═══════════════════════════════════════════════════════════

class TestPolicyResult:
    """PolicyResult 批量结果测试。"""

    def test_create_default(self):
        pr = PolicyResult()
        assert pr.decisions == []
        assert pr.population_decisions == []
        assert pr.active_count == 0
        assert pr.retire_count == 0

    def test_with_decisions(self):
        decisions = [
            EvolutionPolicyDecision(genome_id="g001", action=EvolutionAction.EXPLOIT),
            EvolutionPolicyDecision(genome_id="g002", action=EvolutionAction.KEEP),
            EvolutionPolicyDecision(genome_id="g003", action=EvolutionAction.RETIRE),
        ]
        pr = PolicyResult(decisions=decisions, summary={"total": 3})
        assert pr.active_count == 2
        assert pr.retire_count == 1

    def test_get_decisions_by_action(self):
        decisions = [
            EvolutionPolicyDecision(genome_id="g001", action=EvolutionAction.EXPLOIT),
            EvolutionPolicyDecision(genome_id="g002", action=EvolutionAction.EXPLOIT),
            EvolutionPolicyDecision(genome_id="g003", action=EvolutionAction.MUTATE),
        ]
        pr = PolicyResult(decisions=decisions)
        exploit = pr.get_decisions_by_action(EvolutionAction.EXPLOIT)
        assert len(exploit) == 2

    def test_to_dict(self):
        decisions = [EvolutionPolicyDecision(genome_id="g001")]
        pop = [PopulationDecision(genome_id="g001")]
        pr = PolicyResult(decisions=decisions, population_decisions=pop, summary={"a": 1})
        d = pr.to_dict()
        assert len(d["decisions"]) == 1
        assert len(d["population_decisions"]) == 1
        assert d["summary"] == {"a": 1}

    def test_repr(self):
        decisions = [EvolutionPolicyDecision(genome_id="g001", action=EvolutionAction.EXPLOIT)]
        pr = PolicyResult(decisions=decisions)
        r = repr(pr)
        assert "decisions=1" in r
        assert "active=1" in r


# ═══════════════════════════════════════════════════════════
# 5. PolicyRule
# ═══════════════════════════════════════════════════════════

class TestPolicyRule:
    """PolicyRule 规则评估测试。"""

    def test_rule_match(self):
        """条件匹配 → 返回决策。"""
        rule = PolicyRule(
            name="test_winner",
            priority=1,
            condition=lambda ls, f: ls.direction == LearningDirection.KEEP,
            action=EvolutionAction.EXPLOIT,
            strategy=MutationStrategy.SMALL,
            reason="Winner {genome_id}",
        )
        decision = rule.evaluate(
            _make_winner_signal("g001"),
            _make_winner_fitness("g001"),
        )
        assert decision is not None
        assert decision.action == EvolutionAction.EXPLOIT
        assert decision.genome_id == "g001"

    def test_rule_no_match(self):
        """条件不匹配 → 返回 None。"""
        rule = PolicyRule(
            name="test_winner",
            priority=1,
            condition=lambda ls, f: ls.direction == LearningDirection.KEEP,
            action=EvolutionAction.EXPLOIT,
            strategy=MutationStrategy.SMALL,
        )
        decision = rule.evaluate(
            _make_failure_signal("g001"),
            _make_low_fitness("g001"),
        )
        assert decision is None

    def test_rule_confidence_from_fitness(self):
        """置信度来自 fitness.overall_score / 100。"""
        rule = PolicyRule(
            name="test",
            priority=1,
            condition=lambda ls, f: True,
            action=EvolutionAction.EXPLOIT,
            strategy=MutationStrategy.SMALL,
        )
        fitness = FitnessScore(overall_score=85.0)
        decision = rule.evaluate(_make_winner_signal(), fitness)
        assert decision.confidence == 0.85

    def test_rule_confidence_from_signal(self):
        """无 fitness 时置信度来自 learning_signal.confidence。"""
        rule = PolicyRule(
            name="test",
            priority=1,
            condition=lambda ls, f: True,
            action=EvolutionAction.EXPLOIT,
            strategy=MutationStrategy.SMALL,
        )
        signal = LearningSignal(genome_id="g001", confidence=0.7)
        decision = rule.evaluate(signal, None)
        assert decision.confidence == 0.7

    def test_rule_reason_template(self):
        """reason 模板正确填充。"""
        rule = PolicyRule(
            name="test",
            priority=1,
            condition=lambda ls, f: True,
            action=EvolutionAction.EXPLOIT,
            strategy=MutationStrategy.SMALL,
            reason="Genome {genome_id} fitness={fitness}",
        )
        fitness = FitnessScore(genome_id="g001", overall_score=85.0)
        decision = rule.evaluate(_make_winner_signal("g001"), fitness)
        assert "g001" in decision.reason
        assert "85" in decision.reason

    def test_rule_repr(self):
        rule = PolicyRule(name="test", priority=5, action=EvolutionAction.EXPLOIT)
        r = repr(rule)
        assert "test" in r
        assert "exploit" in r


# ═══════════════════════════════════════════════════════════
# 6. Builtin Rules
# ═══════════════════════════════════════════════════════════

class TestBuiltinRules:
    """内置规则测试。"""

    def test_all_rules_built(self):
        rules = build_default_rules()
        assert len(rules) == 5

    def test_rules_priority_order(self):
        rules = build_default_rules()
        priorities = [r.priority for r in rules]
        assert priorities == sorted(priorities)

    def test_winner_rule_exploit(self):
        """Winner → EXPLOIT + SMALL。"""
        rule = build_default_rules()[1]  # winner_exploit
        decision = rule.evaluate(_make_winner_signal(), _make_winner_fitness())
        assert decision is not None
        assert decision.action == EvolutionAction.EXPLOIT
        assert decision.mutation_strategy == MutationStrategy.SMALL

    def test_winner_rule_no_trigger_without_fitness(self):
        """无 fitness 时 winner 规则不触发。"""
        rule = build_default_rules()[1]
        decision = rule.evaluate(_make_winner_signal(), None)
        assert decision is None

    def test_improvement_rule_mutate(self):
        """Average → MUTATE + MEDIUM。"""
        rule = build_default_rules()[2]  # improvement_mutate
        decision = rule.evaluate(_make_improve_signal(), _make_avg_fitness())
        assert decision is not None
        assert decision.action == EvolutionAction.MUTATE
        assert decision.mutation_strategy == MutationStrategy.MEDIUM

    def test_failure_rule_explore(self):
        """Failed → EXPLORE + LARGE。"""
        rule = build_default_rules()[3]  # failure_explore
        decision = rule.evaluate(_make_failure_signal(), _make_low_fitness())
        assert decision is not None
        assert decision.action == EvolutionAction.EXPLORE
        assert decision.mutation_strategy == MutationStrategy.LARGE

    def test_failure_rule_without_fitness(self):
        """无 fitness 时 failure 规则仍触发（仅检查 direction=MUTATE）。"""
        rule = build_default_rules()[3]
        decision = rule.evaluate(_make_failure_signal(), None)
        assert decision is not None
        assert decision.action == EvolutionAction.EXPLORE

    def test_dead_genome_rule_retire(self):
        """连续失败 >= 3 → RETIRE。"""
        rule = build_default_rules()[0]  # dead_genome_retire
        decision = rule.evaluate(_make_dead_signal(), _make_dead_fitness())
        assert decision is not None
        assert decision.action == EvolutionAction.RETIRE

    def test_dead_genome_rule_not_triggered(self):
        """连续失败 < 3 → 不触发。"""
        rule = build_default_rules()[0]
        signal = _make_failure_signal()  # failures=1
        decision = rule.evaluate(signal, None)
        assert decision is None

    def test_default_rule_always_matches(self):
        """默认规则总是匹配。"""
        rule = build_default_rules()[4]  # default_keep
        decision = rule.evaluate(LearningSignal(genome_id="g001"), None)
        assert decision is not None
        assert decision.action == EvolutionAction.KEEP


# ═══════════════════════════════════════════════════════════
# 7. StrategySelector
# ═══════════════════════════════════════════════════════════

class TestStrategySelector:
    """StrategySelector 测试。"""

    def test_select_keep(self):
        selector = StrategySelector()
        strategy = selector.select(_make_winner_signal())
        assert strategy == MutationStrategy.SMALL

    def test_select_improve(self):
        selector = StrategySelector()
        strategy = selector.select(_make_improve_signal())
        assert strategy == MutationStrategy.MEDIUM

    def test_select_failure(self):
        selector = StrategySelector()
        strategy = selector.select(_make_failure_signal())
        assert strategy == MutationStrategy.LARGE

    def test_refine_edge_improve_to_small(self):
        """接近 winner 但仍 IMPROVE → 降为 SMALL。"""
        selector = StrategySelector()
        signal = _make_improve_signal()
        fitness = FitnessScore(overall_score=78.0)  # >= 75
        strategy = selector.select(signal, fitness)
        assert strategy == MutationStrategy.SMALL

    def test_refine_deep_failure_to_radical(self):
        """深度失败 → RADICAL。"""
        selector = StrategySelector()
        signal = _make_failure_signal()
        fitness = FitnessScore(overall_score=15.0)  # <= 20
        strategy = selector.select(signal, fitness)
        assert strategy == MutationStrategy.RADICAL

    def test_refine_edge_failure_to_medium(self):
        """接近失败边缘 → 降为 MEDIUM。"""
        selector = StrategySelector()
        signal = _make_failure_signal()
        fitness = FitnessScore(overall_score=47.0)  # >= 45
        strategy = selector.select(signal, fitness)
        assert strategy == MutationStrategy.MEDIUM

    def test_select_batch(self):
        selector = StrategySelector()
        signals = [_make_winner_signal(), _make_improve_signal(), _make_failure_signal()]
        strategies = selector.select_batch(signals)
        assert len(strategies) == 3
        assert strategies[0] == MutationStrategy.SMALL
        assert strategies[1] == MutationStrategy.MEDIUM
        assert strategies[2] == MutationStrategy.LARGE

    def test_get_mutation_rate(self):
        assert StrategySelector.get_mutation_rate(MutationStrategy.SMALL) == 0.1
        assert StrategySelector.get_mutation_rate(MutationStrategy.MEDIUM) == 0.3
        assert StrategySelector.get_mutation_rate(MutationStrategy.LARGE) == 0.6

    def test_get_target_genes(self):
        genes = StrategySelector.get_target_genes(MutationStrategy.MEDIUM)
        assert "hook" in genes
        assert "visual" in genes
        assert "reward" in genes

    def test_get_strategy_params(self):
        params = StrategySelector.get_strategy_params(MutationStrategy.LARGE)
        assert params["strategy"] == "large"
        assert params["mutation_rate"] == 0.6
        assert len(params["target_genes"]) == 5

    def test_select_count(self):
        selector = StrategySelector()
        selector.select(_make_winner_signal())
        selector.select(_make_improve_signal())
        assert selector.select_count == 2

    def test_reset(self):
        selector = StrategySelector()
        selector.select(_make_winner_signal())
        selector.reset()
        assert selector.select_count == 0


# ═══════════════════════════════════════════════════════════
# 8. PopulationPolicy
# ═══════════════════════════════════════════════════════════

class TestPopulationPolicy:
    """PopulationPolicy 测试。"""

    def test_handle_keep(self):
        pp = PopulationPolicy()
        pd = EvolutionPolicyDecision(genome_id="g001", action=EvolutionAction.KEEP)
        decision = pp.decide(pd)
        assert decision.weight_change == 0.0
        assert decision.remove is False
        assert decision.clone_count == 0

    def test_handle_exploit(self):
        pp = PopulationPolicy()
        pd = EvolutionPolicyDecision(genome_id="g001", action=EvolutionAction.EXPLOIT)
        decision = pp.decide(pd)
        assert decision.weight_change > 0
        assert decision.clone_count == 2
        assert decision.remove is False
        assert decision.is_clone is True

    def test_handle_explore(self):
        pp = PopulationPolicy()
        pd = EvolutionPolicyDecision(genome_id="g001", action=EvolutionAction.EXPLORE)
        decision = pp.decide(pd)
        assert decision.weight_change < 0
        assert decision.remove is False
        assert decision.clone_count == 0

    def test_handle_mutate(self):
        pp = PopulationPolicy()
        pd = EvolutionPolicyDecision(genome_id="g001", action=EvolutionAction.MUTATE)
        decision = pp.decide(pd)
        assert decision.weight_change > 0
        assert decision.remove is False

    def test_handle_retire(self):
        pp = PopulationPolicy()
        pd = EvolutionPolicyDecision(genome_id="g001", action=EvolutionAction.RETIRE)
        decision = pp.decide(pd)
        assert decision.remove is True
        assert decision.is_remove is True

    def test_decide_batch(self):
        pp = PopulationPolicy()
        decisions = [
            EvolutionPolicyDecision(genome_id="g001", action=EvolutionAction.EXPLOIT),
            EvolutionPolicyDecision(genome_id="g002", action=EvolutionAction.RETIRE),
        ]
        results = pp.decide_batch(decisions)
        assert len(results) == 2
        assert results[0].is_clone
        assert results[1].is_remove

    def test_decide_count(self):
        pp = PopulationPolicy()
        pp.decide(EvolutionPolicyDecision(genome_id="g001", action=EvolutionAction.KEEP))
        pp.decide(EvolutionPolicyDecision(genome_id="g002", action=EvolutionAction.EXPLOIT))
        assert pp.decide_count == 2

    def test_reset(self):
        pp = PopulationPolicy()
        pp.decide(EvolutionPolicyDecision(genome_id="g001", action=EvolutionAction.KEEP))
        pp.reset()
        assert pp.decide_count == 0


# ═══════════════════════════════════════════════════════════
# 9. EvolutionPolicyEngine
# ═══════════════════════════════════════════════════════════

class TestEvolutionPolicyEngine:
    """EvolutionPolicyEngine 统一入口测试。"""

    def test_decide_winner(self):
        """Winner → EXPLOIT + SMALL。"""
        engine = EvolutionPolicyEngine()
        decision = engine.decide(_make_winner_signal(), _make_winner_fitness())
        assert decision.action == EvolutionAction.EXPLOIT
        assert decision.mutation_strategy == MutationStrategy.SMALL
        assert decision.mutation_rate == 0.1
        assert "hook" in decision.target_genes

    def test_decide_improvement(self):
        """Average → MUTATE + MEDIUM。"""
        engine = EvolutionPolicyEngine()
        decision = engine.decide(_make_improve_signal(), _make_avg_fitness())
        assert decision.action == EvolutionAction.MUTATE
        assert decision.mutation_strategy == MutationStrategy.MEDIUM

    def test_decide_failure(self):
        """Failed → EXPLORE + LARGE。"""
        engine = EvolutionPolicyEngine()
        decision = engine.decide(_make_failure_signal(), _make_low_fitness())
        assert decision.action == EvolutionAction.EXPLORE
        assert decision.mutation_strategy == MutationStrategy.LARGE

    def test_decide_dead(self):
        """连续失败 >= 3 → RETIRE。"""
        engine = EvolutionPolicyEngine()
        decision = engine.decide(_make_dead_signal(), _make_dead_fitness())
        assert decision.action == EvolutionAction.RETIRE

    def test_decide_default(self):
        """无匹配规则 → KEEP。"""
        engine = EvolutionPolicyEngine()
        signal = LearningSignal(genome_id="g_unknown", direction=LearningDirection.KEEP, confidence=0.5)
        decision = engine.decide(signal, None)
        assert decision.action == EvolutionAction.KEEP

    def test_decide_without_fitness(self):
        """无 fitness → 仍能正常决策。"""
        engine = EvolutionPolicyEngine()
        decision = engine.decide(_make_failure_signal(), None)
        assert decision.action == EvolutionAction.EXPLORE

    def test_decide_batch(self):
        engine = EvolutionPolicyEngine()
        signals = [_make_winner_signal(), _make_improve_signal(), _make_failure_signal()]
        fitness_map = {
            "g_winner": _make_winner_fitness(),
            "g_avg": _make_avg_fitness(),
            "g_low": _make_low_fitness(),
        }
        decisions = engine.decide_batch(signals, fitness_map)
        assert len(decisions) == 3
        assert decisions[0].action == EvolutionAction.EXPLOIT
        assert decisions[1].action == EvolutionAction.MUTATE
        assert decisions[2].action == EvolutionAction.EXPLORE

    def test_decide_with_population(self):
        """完整链路：LearningSignal → PolicyDecision + PopulationDecision。"""
        engine = EvolutionPolicyEngine()
        signals = [
            _make_winner_signal("g_w"),
            _make_improve_signal("g_a"),
            _make_failure_signal("g_l"),
        ]
        fitness_map = {
            "g_w": _make_winner_fitness("g_w"),
            "g_a": _make_avg_fitness("g_a"),
            "g_l": _make_low_fitness("g_l"),
        }
        result = engine.decide_with_population(signals, fitness_map)

        assert len(result.decisions) == 3
        assert len(result.population_decisions) == 3
        assert "total_genomes" in result.summary
        assert result.summary["total_genomes"] == 3
        assert result.summary["active_decisions"] == 3

        # Winner → clone
        pop_w = result.population_decisions[0]
        assert pop_w.is_clone
        # Improvement → weight increase
        pop_a = result.population_decisions[1]
        assert pop_a.weight_change > 0
        # Failure → weight decrease
        pop_l = result.population_decisions[2]
        assert pop_l.weight_change < 0

    def test_get_active_decisions(self):
        engine = EvolutionPolicyEngine()
        decisions = [
            EvolutionPolicyDecision(genome_id="g001", action=EvolutionAction.EXPLOIT),
            EvolutionPolicyDecision(genome_id="g002", action=EvolutionAction.KEEP),
            EvolutionPolicyDecision(genome_id="g003", action=EvolutionAction.MUTATE),
        ]
        active = engine.get_active_decisions(decisions)
        assert len(active) == 2

    def test_get_retire_decisions(self):
        engine = EvolutionPolicyEngine()
        decisions = [
            EvolutionPolicyDecision(genome_id="g001", action=EvolutionAction.RETIRE),
            EvolutionPolicyDecision(genome_id="g002", action=EvolutionAction.EXPLOIT),
        ]
        retired = engine.get_retire_decisions(decisions)
        assert len(retired) == 1

    def test_get_decisions_by_action(self):
        engine = EvolutionPolicyEngine()
        decisions = [
            EvolutionPolicyDecision(genome_id="g001", action=EvolutionAction.EXPLOIT),
            EvolutionPolicyDecision(genome_id="g002", action=EvolutionAction.EXPLOIT),
            EvolutionPolicyDecision(genome_id="g003", action=EvolutionAction.MUTATE),
        ]
        result = engine.get_decisions_by_action(decisions, EvolutionAction.EXPLOIT)
        assert len(result) == 2

    def test_add_rule(self):
        engine = EvolutionPolicyEngine()
        init_count = len(engine.get_rules())
        new_rule = PolicyRule(
            name="custom_rule",
            priority=5,
            condition=lambda ls, f: True,
            action=EvolutionAction.MUTATE,
            strategy=MutationStrategy.MEDIUM,
        )
        engine.add_rule(new_rule)
        assert len(engine.get_rules()) == init_count + 1

    def test_remove_rule(self):
        engine = EvolutionPolicyEngine()
        assert engine.remove_rule("winner_exploit") is True
        assert engine.remove_rule("nonexistent") is False

    def test_get_rules_sorted(self):
        engine = EvolutionPolicyEngine()
        rules = engine.get_rules()
        priorities = [r.priority for r in rules]
        assert priorities == sorted(priorities)

    def test_decide_count(self):
        engine = EvolutionPolicyEngine()
        engine.decide(_make_winner_signal(), _make_winner_fitness())
        engine.decide(_make_improve_signal(), _make_avg_fitness())
        assert engine.decide_count == 2

    def test_get_stats(self):
        engine = EvolutionPolicyEngine()
        engine.decide(_make_winner_signal(), _make_winner_fitness())
        stats = engine.get_stats()
        assert stats["decide_count"] == 1
        assert stats["rules_count"] == 5

    def test_reset(self):
        engine = EvolutionPolicyEngine()
        engine.decide(_make_winner_signal(), _make_winner_fitness())
        engine.reset()
        assert engine.decide_count == 0

    def test_dependency_injection(self):
        """支持自定义子组件注入。"""
        selector = StrategySelector()
        pop_policy = PopulationPolicy()
        engine = EvolutionPolicyEngine(
            strategy_selector=selector,
            population_policy=pop_policy,
        )
        decision = engine.decide(_make_winner_signal(), _make_winner_fitness())
        assert decision.action == EvolutionAction.EXPLOIT


# ═══════════════════════════════════════════════════════════
# 10. Controller Integration
# ═══════════════════════════════════════════════════════════

class TestControllerPolicyIntegration:
    """Controller apply_learning_policy 测试。"""

    @pytest.fixture
    def controller(self):
        from market_ops.creative_vision_runtime.intelligence.engine import (
            VisionIntelligenceEngine,
        )
        from market_ops.creative_vision_runtime.autonomous_controller.controller import (
            AutonomousCreativeController,
        )
        from market_ops.creative_vision_runtime.autonomous_controller.models import (
            ControllerConfig,
        )

        mock_intelligence = MagicMock(spec=VisionIntelligenceEngine)
        mock_intelligence.analyze_batch.return_value = {}
        mock_intelligence.extract_winner_dna.return_value = None

        config = ControllerConfig(max_cycles=1)
        return AutonomousCreativeController(
            intelligence_engine=mock_intelligence,
            config=config,
        )

    def test_apply_learning_policy(self, controller):
        """apply_learning_policy 返回 PolicyResult。"""
        signals = [
            _make_winner_signal("g_w"),
            _make_improve_signal("g_a"),
            _make_failure_signal("g_l"),
        ]
        fitness_map = {
            "g_w": _make_winner_fitness("g_w"),
            "g_a": _make_avg_fitness("g_a"),
            "g_l": _make_low_fitness("g_l"),
        }
        result = controller.apply_learning_policy(signals, fitness_map)

        assert isinstance(result, PolicyResult)
        assert len(result.decisions) == 3
        assert result.decisions[0].action == EvolutionAction.EXPLOIT
        assert result.decisions[1].action == EvolutionAction.MUTATE
        assert result.decisions[2].action == EvolutionAction.EXPLORE

    def test_apply_learning_policy_and_evolve(self, controller):
        """apply_learning_policy_and_evolve 返回 policy_result + cycles。"""
        signals = [
            _make_winner_signal("g_w"),
            _make_improve_signal("g_a"),
        ]
        fitness_map = {
            "g_w": _make_winner_fitness("g_w"),
            "g_a": _make_avg_fitness("g_a"),
        }
        output = controller.apply_learning_policy_and_evolve(
            learning_signals=signals,
            fitness_map=fitness_map,
            asset_ids=["a1", "a2"],
            genomes={"a1": {"genome_id": "g_w"}, "a2": {"genome_id": "g_a"}},
        )

        assert "policy_result" in output
        assert "cycles" in output
        assert isinstance(output["policy_result"], PolicyResult)
        # g_w=EXPLOIT(active) + g_a=MUTATE(active) → 2 cycles
        assert len(output["cycles"]) == 2

    def test_apply_learning_policy_and_evolve_all_keep(self, controller):
        """所有 KEEP → 无 cycle。"""
        signals = [
            LearningSignal(genome_id="g_k1", direction=LearningDirection.KEEP, confidence=0.5),
            LearningSignal(genome_id="g_k2", direction=LearningDirection.KEEP, confidence=0.5),
        ]
        output = controller.apply_learning_policy_and_evolve(
            learning_signals=signals,
            asset_ids=["a1"],
            genomes={"a1": {"genome_id": "g_k1"}},
        )
        assert len(output["cycles"]) == 0

    def test_policy_engine_property(self, controller):
        """policy_engine 属性可访问。"""
        from market_ops.creative_vision_runtime.autonomous_controller.policy.policy_engine import (
            EvolutionPolicyEngine,
        )
        assert isinstance(controller.policy_engine, EvolutionPolicyEngine)


# ═══════════════════════════════════════════════════════════
# 11. Full Pipeline
# ═══════════════════════════════════════════════════════════

class TestFullPipeline:
    """完整链路：LearningSignal → PolicyDecision → PopulationDecision。"""

    def test_pipeline_winner(self):
        """Winner → EXPLOIT + clone。"""
        engine = EvolutionPolicyEngine()
        result = engine.decide_with_population(
            [_make_winner_signal("g_w")],
            {"g_w": _make_winner_fitness("g_w")},
        )
        assert result.decisions[0].action == EvolutionAction.EXPLOIT
        assert result.decisions[0].mutation_strategy == MutationStrategy.SMALL
        assert result.population_decisions[0].is_clone

    def test_pipeline_improvement(self):
        """Average → MUTATE + weight increase。"""
        engine = EvolutionPolicyEngine()
        result = engine.decide_with_population(
            [_make_improve_signal("g_a")],
            {"g_a": _make_avg_fitness("g_a")},
        )
        assert result.decisions[0].action == EvolutionAction.MUTATE
        assert result.population_decisions[0].weight_change > 0

    def test_pipeline_failure(self):
        """Failed → EXPLORE + weight decrease。"""
        engine = EvolutionPolicyEngine()
        result = engine.decide_with_population(
            [_make_failure_signal("g_l")],
            {"g_l": _make_low_fitness("g_l")},
        )
        assert result.decisions[0].action == EvolutionAction.EXPLORE
        assert result.population_decisions[0].weight_change < 0

    def test_pipeline_dead(self):
        """Dead → RETIRE + remove。"""
        engine = EvolutionPolicyEngine()
        result = engine.decide_with_population(
            [_make_dead_signal("g_d")],
            {"g_d": _make_dead_fitness("g_d")},
        )
        assert result.decisions[0].action == EvolutionAction.RETIRE
        assert result.population_decisions[0].is_remove

    def test_pipeline_summary(self):
        """验证 summary 统计正确。"""
        engine = EvolutionPolicyEngine()
        result = engine.decide_with_population(
            [
                _make_winner_signal("g_w"),
                _make_improve_signal("g_a"),
                _make_failure_signal("g_l"),
                _make_dead_signal("g_d"),
            ],
            {
                "g_w": _make_winner_fitness("g_w"),
                "g_a": _make_avg_fitness("g_a"),
                "g_l": _make_low_fitness("g_l"),
                "g_d": _make_dead_fitness("g_d"),
            },
        )
        summary = result.summary
        assert summary["total_genomes"] == 4
        assert summary["active_decisions"] == 4
        assert summary["retire_decisions"] == 1
        assert summary["population_removes"] == 1
        assert summary["population_clones"] == 1


# ═══════════════════════════════════════════════════════════
# 12. Package Exports
# ═══════════════════════════════════════════════════════════

def test_package_exports():
    """__init__.py 导出所有核心类。"""
    import market_ops.creative_vision_runtime.autonomous_controller.policy as p

    assert hasattr(p, "EvolutionAction")
    assert hasattr(p, "MutationStrategy")
    assert hasattr(p, "EvolutionPolicyDecision")
    assert hasattr(p, "PopulationDecision")
    assert hasattr(p, "PolicyResult")
    assert hasattr(p, "PolicyRule")
    assert hasattr(p, "build_default_rules")
    assert hasattr(p, "StrategySelector")
    assert hasattr(p, "PopulationPolicy")
    assert hasattr(p, "EvolutionPolicyEngine")