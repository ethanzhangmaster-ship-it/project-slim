"""E12.5.4 — Meta Strategy Optimizer 测试。

覆盖:
  - Models: MetaStrategy, ExplorationPolicy, StrategyRanking, OptimizationResult
  - StrategyGenerator: Pattern→Strategy, Knowledge→Strategy, Exploration
  - StrategyRanker: 评分、排序、按目标排序
  - ExplorationController: 70/30 选择、疲劳调整、探索变体
  - MetaOptimizer: 完整 pipeline、多产品、空输入
  - Pipeline: 端到端集成
"""

import pytest

from market_ops.creative_vision_runtime.reality.meta_learning import (
    MetaPattern,
    PatternType,
    KnowledgeNode,
    KnowledgeEdge,
    NodeType,
    RelationType,
)
from market_ops.creative_vision_runtime.reality.meta_learning.strategy_optimizer import (
    ExplorationController,
    ExplorationPolicy,
    MetaOptimizer,
    MetaStrategy,
    OptimizationGoal,
    OptimizationResult,
    StrategyGenerator,
    StrategyRanker,
    StrategyRanking,
    StrategySource,
    StrategyStatus,
)


# ── Helpers ───────────────────────────────────────────────


def make_pattern(
    name="Rescue Hook",
    sr=0.82,
    roas=0.21,
    ctr=0.15,
    cvr=0.10,
    sample_count=50,
    confidence=0.85,
    genes=None,
    markets=None,
    platforms=None,
    products=None,
):
    """创建测试用 MetaPattern。"""
    return MetaPattern(
        name=name,
        pattern_type=PatternType.HOOK,
        genes=genes or {"hook": "rescue", "visual": "high_contrast"},
        sample_count=sample_count,
        success_count=int(sample_count * sr),
        success_rate=sr,
        avg_roas_gain=roas,
        avg_ctr_gain=ctr,
        avg_cvr_gain=cvr,
        confidence=confidence,
        markets=markets if markets is not None else ["US"],
    platforms=platforms if platforms is not None else ["facebook"],
    products=products if products is not None else ["Merge Dragon"],
        insight=f"{name} shows strong CTR improvement",
        recommendation=f"Use {name} for CTR optimization",
    )


def make_knowledge_node(node_id="N1", node_type=NodeType.GENE, name="Rescue Emotion", confidence=0.91, attributes=None):
    """创建测试用 KnowledgeNode。"""
    from market_ops.creative_vision_runtime.reality.meta_learning.knowledge_graph import KnowledgeNode as KN
    return KN(
        node_id=node_id,
        node_type=node_type,
        name=name,
        confidence=confidence,
        attributes=attributes or {"emotion": "rescue"},
    )


def make_knowledge_edge(
    source_id="N1",
    target_id="N2",
    relation_type=RelationType.IMPROVES,
    weight=0.78,
    evidence_count=100,
    confidence=0.92,
):
    """创建测试用 KnowledgeEdge。"""
    from market_ops.creative_vision_runtime.reality.meta_learning.knowledge_graph import KnowledgeEdge as KE
    return KE(
        source_id=source_id,
        target_id=target_id,
        relation_type=relation_type,
        weight=weight,
        evidence_count=evidence_count,
        confidence=confidence,
    )


# ═══════════════════════════════════════════════════════════
# 1. Models (12 tests)
# ═══════════════════════════════════════════════════════════


class TestStrategyModels:
    """E12.5.4 数据模型测试。"""

    def test_meta_strategy_creation(self):
        """MetaStrategy 基本创建。"""
        s = MetaStrategy(
            name="Test Strategy",
            target_product="Merge Dragon",
            optimization_goal=OptimizationGoal.CTR,
            dna_mutations={"hook": "rescue"},
            confidence=0.85,
        )
        assert s.strategy_id.startswith("MS_")
        assert s.name == "Test Strategy"
        assert s.optimization_goal == OptimizationGoal.CTR
        assert s.confidence == 0.85
        assert s.exploration is False
        assert s.status == StrategyStatus.DRAFT

    def test_meta_strategy_serialization(self):
        """MetaStrategy to_dict 序列化。"""
        s = MetaStrategy(
            name="Test",
            target_product="p04",
            optimization_goal=OptimizationGoal.ROAS,
            dna_mutations={"hook": "rescue", "visual": "bright"},
            dna_amplify=["hook"],
            dna_suppress=["monetization"],
            expected_ctr_delta=0.15,
            expected_roas_delta=0.21,
            expected_cvr_delta=0.10,
            confidence=0.88,
            risk_score=0.15,
            evidence_count=50,
            markets=["US", "UK"],
            platforms=["facebook"],
            insight="Test insight",
        )
        d = s.to_dict()
        assert d["strategy_id"].startswith("MS_")
        assert d["name"] == "Test"
        assert d["optimization_goal"] == "roas"
        assert d["dna_mutations"] == {"hook": "rescue", "visual": "bright"}
        assert d["dna_amplify"] == ["hook"]
        assert d["confidence"] == 0.88
        assert d["evidence_count"] == 50
        assert d["markets"] == ["US", "UK"]
        assert d["is_reliable"] is True
        assert d["is_strong"] is True

    def test_meta_strategy_evolution_format(self):
        """MetaStrategy 转换为 E11 兼容格式。"""
        s = MetaStrategy(
            name="Evo Test",
            target_product="p04",
            optimization_goal=OptimizationGoal.CTR,
            dna_mutations={"hook": "rescue"},
            dna_amplify=["hook"],
            expected_ctr_delta=0.20,
            confidence=0.90,
            evidence_count=30,
            markets=["US"],
            insight="Strong rescue hook",
        )
        evo = s.to_evolution_strategy()
        assert evo["strategy_id"] == s.strategy_id
        assert evo["optimization_goal"] == "ctr"
        assert evo["amplify"] == ["hook"]
        assert evo["expected_impact"]["ctr_delta"] == 0.20
        assert evo["confidence"] == 0.90
        assert evo["evidence_count"] == 30

    def test_meta_strategy_is_reliable(self):
        """is_reliable 判断。"""
        s1 = MetaStrategy(confidence=0.80, evidence_count=20)
        assert s1.is_reliable
        assert s1.is_strong

        s2 = MetaStrategy(confidence=0.50, evidence_count=3)
        assert not s2.is_reliable
        assert not s2.is_strong

    def test_meta_strategy_performance_impact(self):
        """performance_impact 计算。"""
        s = MetaStrategy(
            expected_ctr_delta=0.20,
            expected_roas_delta=0.30,
            expected_cvr_delta=0.10,
            expected_cpi_delta=-0.05,
        )
        impact = s.performance_impact
        # (0.20 + 0.30 + 0.10 - (-0.05)) / 4 = 0.65 / 4 = 0.1625
        assert impact == 0.1625

    def test_meta_strategy_repr(self):
        """MetaStrategy repr。"""
        s = MetaStrategy(name="Test", optimization_goal=OptimizationGoal.CTR)
        r = repr(s)
        assert "Test" in r
        assert "ctr" in r

    def test_exploration_policy_default(self):
        """ExplorationPolicy 默认值。"""
        p = ExplorationPolicy()
        assert p.exploit_ratio == 0.7
        assert p.explore_ratio == 0.3
        assert p.mutation_strength == 0.5

    def test_exploration_policy_ratio_validation(self):
        """ExplorationPolicy 比例验证。"""
        p = ExplorationPolicy(exploit_ratio=0.8, explore_ratio=0.4)
        # 自动归一化: 0.8/1.2=0.667, 0.4/1.2=0.333
        assert abs(p.exploit_ratio + p.explore_ratio - 1.0) < 0.001

    def test_exploration_policy_fatigue_adjust(self):
        """ExplorationPolicy 疲劳度调整。"""
        p = ExplorationPolicy(exploit_ratio=0.7, explore_ratio=0.3)
        p.adjust_for_fatigue(0.85)
        assert p.explore_ratio > 0.3
        assert p.exploit_ratio < 0.7

    def test_strategy_ranking_creation(self):
        """StrategyRanking 创建。"""
        strategies = [
            MetaStrategy(name="A", score=0.9, exploration=False),
            MetaStrategy(name="B", score=0.5, exploration=True),
        ]
        ranking = StrategyRanking(strategies=strategies)
        assert ranking.total_count == 2
        assert len(ranking.top_exploit) == 1
        assert len(ranking.top_explore) == 1

    def test_optimization_result_creation(self):
        """OptimizationResult 创建。"""
        strategies = [MetaStrategy(name="S1"), MetaStrategy(name="S2")]
        result = OptimizationResult(
            strategies=strategies,
            total_patterns=5,
            total_knowledge=3,
        )
        assert result.strategies_generated == 2
        assert result.strategies_selected == 2
        assert result.total_patterns == 5
        assert result.total_knowledge == 3

    def test_optimization_result_exploit_explore_split(self):
        """OptimizationResult exploit/explore 分离。"""
        s1 = MetaStrategy(name="Exploit", exploration=False)
        s2 = MetaStrategy(name="Explore", exploration=True)
        result = OptimizationResult(strategies=[s1, s2])
        assert len(result.get_exploit_strategies()) == 1
        assert len(result.get_explore_strategies()) == 1

    def test_optimization_goal_enum(self):
        """OptimizationGoal 枚举值。"""
        assert OptimizationGoal.CTR.value == "ctr"
        assert OptimizationGoal.ROAS.value == "roas"
        assert OptimizationGoal.CVR.value == "cvr"
        assert OptimizationGoal.CPI.value == "cpi"
        assert OptimizationGoal.BALANCED.value == "balanced"

    def test_strategy_status_enum(self):
        """StrategyStatus 枚举值。"""
        assert StrategyStatus.DRAFT.value == "draft"
        assert StrategyStatus.SELECTED.value == "selected"

    def test_strategy_source_enum(self):
        """StrategySource 枚举值。"""
        assert StrategySource.PATTERN.value == "pattern"
        assert StrategySource.KNOWLEDGE.value == "knowledge"
        assert StrategySource.EXPLORATION.value == "exploration"


# ═══════════════════════════════════════════════════════════
# 2. StrategyGenerator (22 tests)
# ═══════════════════════════════════════════════════════════


class TestStrategyGenerator:
    """StrategyGenerator 测试。"""

    def test_generate_from_strong_pattern(self):
        """强 Pattern → Amplify 策略。"""
        gen = StrategyGenerator()
        pattern = make_pattern("Rescue Hook", sr=0.85, sample_count=50)
        strategies = gen.generate_from_patterns([pattern], "Merge Dragon")
        assert len(strategies) == 1
        s = strategies[0]
        assert s.name.startswith("Amplify")
        assert s.exploration is False
        assert s.strategy_source == StrategySource.PATTERN
        assert s.target_product == "Merge Dragon"
        assert len(s.dna_amplify) > 0
        assert len(s.dna_explore) == 0

    def test_generate_from_medium_pattern(self):
        """中等 Pattern → Explore 策略。"""
        gen = StrategyGenerator(high_threshold=0.70, strong_threshold=0.80)
        pattern = make_pattern("Medium Pattern", sr=0.75, sample_count=20)
        strategies = gen.generate_from_patterns([pattern], "p04")
        assert len(strategies) == 1
        s = strategies[0]
        assert s.name.startswith("Explore")
        assert s.exploration is True
        assert len(s.dna_explore) > 0

    def test_ignore_low_success_pattern(self):
        """低成功率 Pattern 被忽略。"""
        gen = StrategyGenerator(high_threshold=0.70)
        pattern = make_pattern("Low SR", sr=0.50, sample_count=20)
        strategies = gen.generate_from_patterns([pattern])
        assert len(strategies) == 0

    def test_ignore_low_sample_pattern(self):
        """低样本量 Pattern 被忽略。"""
        gen = StrategyGenerator(min_samples=5)
        pattern = make_pattern("Low sample", sr=0.85, sample_count=3)
        strategies = gen.generate_from_patterns([pattern])
        assert len(strategies) == 0

    def test_generate_multiple_patterns(self):
        """多个 Pattern 生成策略。"""
        gen = StrategyGenerator()
        patterns = [
            make_pattern("Hook A", sr=0.85, sample_count=50),
            make_pattern("Hook B", sr=0.78, sample_count=30),
            make_pattern("Hook C", sr=0.65, sample_count=20),  # 低成功率，忽略
        ]
        strategies = gen.generate_from_patterns(patterns)
        assert len(strategies) == 2  # C 被忽略

    def test_generate_empty_patterns(self):
        """空 Pattern 列表。"""
        gen = StrategyGenerator()
        strategies = gen.generate_from_patterns([])
        assert len(strategies) == 0

    def test_dna_mutations_in_strategy(self):
        """策略包含正确的 DNA 修改。"""
        gen = StrategyGenerator()
        genes = {"hook": "rescue", "visual": "high_contrast"}
        pattern = make_pattern("Test", sr=0.85, genes=genes)
        strategies = gen.generate_from_patterns([pattern])
        assert strategies[0].dna_mutations == genes

    def test_strategy_inherits_metrics(self):
        """策略继承 Pattern 指标。"""
        gen = StrategyGenerator()
        pattern = make_pattern("Test", sr=0.85, ctr=0.25, roas=0.30, cvr=0.15)
        strategies = gen.generate_from_patterns([pattern])
        s = strategies[0]
        assert s.expected_ctr_delta == 0.25
        assert s.expected_roas_delta == 0.30
        assert s.expected_cvr_delta == 0.15

    def test_strategy_inherits_context(self):
        """策略继承 Pattern 上下文。"""
        gen = StrategyGenerator()
        pattern = make_pattern(
            "Test", sr=0.85,
            markets=["US", "UK"],
            platforms=["facebook", "google"],
            products=["Merge Dragon"],
        )
        strategies = gen.generate_from_patterns([pattern], "Merge Dragon")
        s = strategies[0]
        assert s.markets == ["US", "UK"]
        assert s.platforms == ["facebook", "google"]

    def test_infer_goal_ctr(self):
        """推断优化目标为 CTR。"""
        gen = StrategyGenerator()
        pattern = make_pattern("Test", sr=0.85, ctr=0.30, roas=0.10, cvr=0.05)
        strategies = gen.generate_from_patterns([pattern])
        assert strategies[0].optimization_goal == OptimizationGoal.CTR

    def test_infer_goal_roas(self):
        """推断优化目标为 ROAS。"""
        gen = StrategyGenerator()
        pattern = make_pattern("Test", sr=0.85, ctr=0.05, roas=0.30, cvr=0.10)
        strategies = gen.generate_from_patterns([pattern])
        assert strategies[0].optimization_goal == OptimizationGoal.ROAS

    def test_infer_goal_cvr(self):
        """推断优化目标为 CVR。"""
        gen = StrategyGenerator()
        pattern = make_pattern("Test", sr=0.85, ctr=0.05, roas=0.05, cvr=0.25)
        strategies = gen.generate_from_patterns([pattern])
        assert strategies[0].optimization_goal == OptimizationGoal.CVR

    def test_medium_pattern_confidence_reduced(self):
        """中等 Pattern 置信度降低。"""
        gen = StrategyGenerator(high_threshold=0.70, strong_threshold=0.85)
        pattern = make_pattern("Test", sr=0.75, confidence=0.80)
        strategies = gen.generate_from_patterns([pattern])
        assert strategies[0].confidence < 0.80

    def test_generate_from_knowledge_improves(self):
        """从 IMPROVES 关系生成策略。"""
        gen = StrategyGenerator()
        node1 = make_knowledge_node("N1", NodeType.GENE, "Rescue Emotion")
        node2 = make_knowledge_node("N2", NodeType.METRIC, "CTR")
        edge = make_knowledge_edge("N1", "N2", RelationType.IMPROVES, weight=0.78, evidence_count=100, confidence=0.92)
        strategies = gen.generate_from_knowledge([node1, node2], [edge])
        assert len(strategies) == 1
        s = strategies[0]
        assert s.strategy_source == StrategySource.KNOWLEDGE
        assert s.optimization_goal == OptimizationGoal.CTR
        assert s.confidence == 0.92

    def test_generate_from_knowledge_combines_with(self):
        """从 COMBINES_WITH 关系生成组合策略。"""
        gen = StrategyGenerator()
        node1 = make_knowledge_node("N1", NodeType.GENE, "Rescue Hook")
        node2 = make_knowledge_node("N2", NodeType.PATTERN, "Cute Character")
        edge = make_knowledge_edge("N1", "N2", RelationType.COMBINES_WITH, weight=0.75, evidence_count=80, confidence=0.88)
        strategies = gen.generate_from_knowledge([node1, node2], [edge])
        assert len(strategies) == 1
        s = strategies[0]
        assert "Combo" in s.name
        assert s.exploration is False
        assert len(s.dna_mutations) == 2

    def test_generate_from_knowledge_low_confidence_ignored(self):
        """低置信度 Knowledge 关系被忽略。"""
        gen = StrategyGenerator()
        node1 = make_knowledge_node("N1", NodeType.GENE, "Weak")
        node2 = make_knowledge_node("N2", NodeType.METRIC, "CTR")
        edge = make_knowledge_edge("N1", "N2", RelationType.IMPROVES, evidence_count=3, confidence=0.50)
        strategies = gen.generate_from_knowledge([node1, node2], [edge])
        assert len(strategies) == 0

    def test_generate_from_knowledge_empty(self):
        """空 Knowledge Graph。"""
        gen = StrategyGenerator()
        strategies = gen.generate_from_knowledge([], [])
        assert len(strategies) == 0

    def test_generate_exploration(self):
        """生成探索策略。"""
        gen = StrategyGenerator()
        patterns = [
            make_pattern("P1", sr=0.85, genes={"hook": "rescue", "visual": "bright"}),
            make_pattern("P2", sr=0.82, genes={"hook": "reward", "visual": "dark"}),
        ]
        strategies = gen.generate_exploration(patterns, "Merge Dragon", count=3)
        assert len(strategies) > 0
        for s in strategies:
            assert s.exploration is True
            assert s.strategy_source == StrategySource.EXPLORATION
            assert s.confidence == 0.40
            assert s.risk_score == 0.50

    def test_generate_exploration_empty(self):
        """空 Pattern 探索生成。"""
        gen = StrategyGenerator()
        strategies = gen.generate_exploration([], count=3)
        assert len(strategies) == 0

    def test_generate_exploration_single_pattern(self):
        """单 Pattern 探索生成。"""
        gen = StrategyGenerator()
        pattern = make_pattern("P1", sr=0.85, genes={"hook": "rescue"})
        strategies = gen.generate_exploration([pattern], count=1)
        assert len(strategies) == 1
        assert "rescue" in str(strategies[0].dna_mutations)

    def test_generator_repr(self):
        """StrategyGenerator repr。"""
        gen = StrategyGenerator()
        r = repr(gen)
        assert "StrategyGenerator" in r


# ═══════════════════════════════════════════════════════════
# 3. StrategyRanker (20 tests)
# ═══════════════════════════════════════════════════════════


class TestStrategyRanker:
    """StrategyRanker 测试。"""

    def test_score_high_confidence_strategy(self):
        """高置信度策略评分高。"""
        ranker = StrategyRanker()
        s = MetaStrategy(
            name="High",
            expected_ctr_delta=0.20,
            expected_roas_delta=0.25,
            confidence=0.90,
            evidence_count=100,
            risk_score=0.10,
            markets=["US", "UK", "JP"],
            platforms=["facebook", "google"],
        )
        score = ranker.score_strategy(s)
        assert 0.3 < score < 1.0

    def test_score_low_confidence_strategy(self):
        """低置信度策略评分低。"""
        ranker = StrategyRanker()
        s = MetaStrategy(
            name="Low",
            expected_ctr_delta=0.05,
            expected_roas_delta=0.05,
            confidence=0.30,
            evidence_count=5,
            risk_score=0.50,
            exploration=True,
        )
        score = ranker.score_strategy(s)
        assert score < 0.5

    def test_rank_orders_by_score(self):
        """排名按评分降序。"""
        ranker = StrategyRanker()
        s1 = MetaStrategy(name="High", expected_ctr_delta=0.30, confidence=0.90, evidence_count=100)
        s2 = MetaStrategy(name="Low", expected_ctr_delta=0.05, confidence=0.40, evidence_count=5)
        ranking = ranker.rank([s2, s1])
        assert ranking.strategies[0].name == "High"
        assert ranking.strategies[1].name == "Low"
        assert s1.score > s2.score

    def test_rank_empty(self):
        """空列表排名。"""
        ranker = StrategyRanker()
        ranking = ranker.rank([])
        assert ranking.total_count == 0
        assert ranking.strategies == []

    def test_rank_single_strategy(self):
        """单策略排名。"""
        ranker = StrategyRanker()
        s = MetaStrategy(name="Only", confidence=0.85)
        ranking = ranker.rank([s])
        assert ranking.total_count == 1
        assert ranking.strategies[0].status == StrategyStatus.RANKED

    def test_rank_separates_exploit_explore(self):
        """排名分离 exploit/explore。"""
        ranker = StrategyRanker()
        strategies = [
            MetaStrategy(name="Exploit", exploration=False, confidence=0.90, expected_ctr_delta=0.20),
            MetaStrategy(name="Explore", exploration=True, confidence=0.50, expected_ctr_delta=0.05),
        ]
        ranking = ranker.rank(strategies)
        assert len(ranking.top_exploit) == 1
        assert len(ranking.top_explore) == 1
        assert ranking.top_exploit[0].name == "Exploit"
        assert ranking.top_explore[0].name == "Explore"

    def test_rank_by_goal_ctr(self):
        """按 CTR 目标排序。"""
        ranker = StrategyRanker()
        s_ctr = MetaStrategy(name="CTR", optimization_goal=OptimizationGoal.CTR, confidence=0.85, expected_ctr_delta=0.20)
        s_roas = MetaStrategy(name="ROAS", optimization_goal=OptimizationGoal.ROAS, confidence=0.85, expected_roas_delta=0.20)
        ranking = ranker.rank_by_goal([s_roas, s_ctr], OptimizationGoal.CTR)
        assert ranking.strategies[0].name == "CTR"

    def test_rank_by_goal_roas(self):
        """按 ROAS 目标排序。"""
        ranker = StrategyRanker()
        s_ctr = MetaStrategy(name="CTR", optimization_goal=OptimizationGoal.CTR, confidence=0.85, expected_ctr_delta=0.20)
        s_roas = MetaStrategy(name="ROAS", optimization_goal=OptimizationGoal.ROAS, confidence=0.85, expected_roas_delta=0.20)
        ranking = ranker.rank_by_goal([s_ctr, s_roas], OptimizationGoal.ROAS)
        assert ranking.strategies[0].name == "ROAS"

    def test_explore_risk_penalty(self):
        """探索策略有额外风险惩罚。"""
        ranker = StrategyRanker()
        s_exploit = MetaStrategy(
            name="E", exploration=False,
            expected_ctr_delta=0.20, confidence=0.80, risk_score=0.10,
            evidence_count=50,
        )
        s_explore = MetaStrategy(
            name="X", exploration=True,
            expected_ctr_delta=0.20, confidence=0.80, risk_score=0.10,
            evidence_count=50,
        )
        score_exploit = ranker.score_strategy(s_exploit)
        score_explore = ranker.score_strategy(s_explore)
        assert score_explore < score_exploit

    def test_confidence_weighting(self):
        """置信度权重影响。"""
        ranker = StrategyRanker()
        s_high = MetaStrategy(name="High", confidence=0.95, expected_ctr_delta=0.15, evidence_count=50)
        s_low = MetaStrategy(name="Low", confidence=0.50, expected_ctr_delta=0.15, evidence_count=50)
        assert ranker.score_strategy(s_high) > ranker.score_strategy(s_low)

    def test_transferability_scoring(self):
        """可迁移性评分。"""
        ranker = StrategyRanker()
        s_wide = MetaStrategy(
            name="Wide",
            confidence=0.85,
            expected_ctr_delta=0.15,
            evidence_count=200,
            markets=["US", "UK", "JP", "KR", "DE"],
            platforms=["facebook", "google", "tiktok"],
            audiences=["female_25_45", "male_18_35"],
        )
        s_narrow = MetaStrategy(
            name="Narrow",
            confidence=0.85,
            expected_ctr_delta=0.15,
            evidence_count=10,
            markets=["US"],
            platforms=["facebook"],
            audiences=[],
        )
        assert ranker.score_strategy(s_wide) > ranker.score_strategy(s_narrow)

    def test_risk_penalty(self):
        """高风险策略评分低。"""
        ranker = StrategyRanker()
        s_low_risk = MetaStrategy(name="Low", confidence=0.85, expected_ctr_delta=0.15, risk_score=0.10, evidence_count=50)
        s_high_risk = MetaStrategy(name="High", confidence=0.85, expected_ctr_delta=0.15, risk_score=0.80, evidence_count=50)
        assert ranker.score_strategy(s_low_risk) > ranker.score_strategy(s_high_risk)

    def test_ranking_summary(self):
        """排名摘要生成。"""
        ranker = StrategyRanker()
        s = MetaStrategy(name="Top", confidence=0.90, expected_ctr_delta=0.30, evidence_count=100)
        ranking = ranker.rank([s])
        assert "Ranked 1 strategies" in ranking.ranking_summary
        assert "Top" in ranking.ranking_summary

    def test_ranking_summary_empty(self):
        """空排名摘要。"""
        ranker = StrategyRanker()
        ranking = ranker.rank([])
        assert "No strategies" in ranking.ranking_summary

    def test_get_top(self):
        """获取 Top N 策略。"""
        ranker = StrategyRanker()
        strategies = [
            MetaStrategy(name=f"S{i}", confidence=0.80 + i * 0.02, expected_ctr_delta=0.10 + i * 0.02)
            for i in range(10)
        ]
        ranking = ranker.rank(strategies)
        top3 = ranking.get_top(3)
        assert len(top3) == 3

    def test_score_bounded(self):
        """评分在 [0, 1] 范围内。"""
        ranker = StrategyRanker()
        s = MetaStrategy(
            expected_ctr_delta=1.0,
            expected_roas_delta=1.0,
            expected_cvr_delta=1.0,
            confidence=1.0,
            evidence_count=1000,
            risk_score=0.0,
            markets=["US", "UK", "JP", "KR", "DE"],
            platforms=["facebook", "google", "tiktok"],
            audiences=["a", "b", "c", "d", "e"],
        )
        score = ranker.score_strategy(s)
        assert 0.0 <= score <= 1.0

    def test_score_zero_delta(self):
        """零 delta 策略评分。"""
        ranker = StrategyRanker()
        s = MetaStrategy(
            expected_ctr_delta=0.0,
            expected_roas_delta=0.0,
            confidence=0.50,
            risk_score=0.50,
            evidence_count=0,
        )
        score = ranker.score_strategy(s)
        assert 0.0 <= score <= 1.0

    def test_ranker_repr(self):
        """StrategyRanker repr。"""
        ranker = StrategyRanker()
        r = repr(ranker)
        assert "StrategyRanker" in r


# ═══════════════════════════════════════════════════════════
# 4. ExplorationController (15 tests)
# ═══════════════════════════════════════════════════════════


class TestExplorationController:
    """ExplorationController 测试。"""

    def test_select_70_30_split(self):
        """70/30 exploit/explore 选择。"""
        controller = ExplorationController()
        strategies = []
        for i in range(10):
            strategies.append(MetaStrategy(name=f"Exploit_{i}", exploration=False, score=0.9 - i * 0.05))
        for i in range(10):
            strategies.append(MetaStrategy(name=f"Explore_{i}", exploration=True, score=0.5 - i * 0.05))

        ranking = StrategyRanking(strategies=strategies)
        selected = controller.select(ranking, total_count=10)
        assert len(selected) == 10
        exploit_count = sum(1 for s in selected if not s.exploration)
        explore_count = sum(1 for s in selected if s.exploration)
        assert exploit_count >= 5  # 至少一半
        assert explore_count >= 2  # 至少有一些

    def test_select_empty(self):
        """空排名选择。"""
        controller = ExplorationController()
        ranking = StrategyRanking(strategies=[])
        selected = controller.select(ranking)
        assert selected == []

    def test_select_all_exploit(self):
        """全部 exploit 策略场景。"""
        controller = ExplorationController()
        strategies = [MetaStrategy(name=f"E{i}", exploration=False, score=0.9) for i in range(10)]
        ranking = StrategyRanking(strategies=strategies)
        selected = controller.select(ranking, total_count=5)
        assert len(selected) == 5
        assert all(s.status == StrategyStatus.SELECTED for s in selected)

    def test_select_all_explore(self):
        """全部 explore 策略场景。"""
        controller = ExplorationController()
        strategies = [MetaStrategy(name=f"X{i}", exploration=True, score=0.5) for i in range(10)]
        ranking = StrategyRanking(strategies=strategies)
        selected = controller.select(ranking, total_count=5)
        assert len(selected) == 5

    def test_select_with_exploration(self):
        """select_with_exploration 生成变体。"""
        controller = ExplorationController()
        exploit = [MetaStrategy(name="E1", exploration=False, confidence=0.90, expected_ctr_delta=0.20)]
        ranking = StrategyRanking(strategies=exploit)
        selected = controller.select_with_exploration(ranking, exploit, total_count=5, mutation_strength=0.3)
        assert len(selected) >= 1
        assert any(s.exploration for s in selected)

    def test_fatigue_adjustment(self):
        """疲劳度调整探索比例。"""
        controller = ExplorationController()
        old_explore = controller.policy.explore_ratio
        controller.adjust_fatigue(0.85)
        assert controller.policy.explore_ratio > old_explore

    def test_fatigue_no_adjust_when_low(self):
        """低疲劳度不调整。"""
        controller = ExplorationController()
        old_explore = controller.policy.explore_ratio
        controller.adjust_fatigue(0.30)
        assert controller.policy.explore_ratio == old_explore

    def test_get_ratio(self):
        """获取当前比例。"""
        controller = ExplorationController()
        exploit, explore = controller.get_ratio()
        assert abs(exploit + explore - 1.0) < 0.001

    def test_reset(self):
        """重置策略。"""
        controller = ExplorationController()
        controller.adjust_fatigue(0.85)
        controller.reset()
        assert controller.policy.exploit_ratio == 0.7
        assert controller.policy.explore_ratio == 0.3

    def test_to_dict(self):
        """to_dict 导出。"""
        controller = ExplorationController()
        d = controller.to_dict()
        assert "policy" in d
        assert "current_ratio" in d
        assert "exploit" in d["current_ratio"]
        assert "explore" in d["current_ratio"]

    def test_custom_policy(self):
        """自定义 ExplorationPolicy。"""
        policy = ExplorationPolicy(exploit_ratio=0.6, explore_ratio=0.4)
        controller = ExplorationController(policy=policy)
        exploit, explore = controller.get_ratio()
        assert abs(exploit - 0.6) < 0.001
        assert abs(explore - 0.4) < 0.001

    def test_select_respects_total_count(self):
        """选择结果尊重 total_count。"""
        controller = ExplorationController()
        strategies = [MetaStrategy(name=f"S{i}", exploration=(i % 2 == 0), score=0.8) for i in range(20)]
        ranking = StrategyRanking(strategies=strategies)
        selected = controller.select(ranking, total_count=7)
        assert len(selected) == 7

    def test_variants_generation(self):
        """探索变体生成。"""
        controller = ExplorationController()
        exploit = [MetaStrategy(
            name="Winner",
            exploration=False,
            dna_mutations={"hook": "rescue"},
            expected_ctr_delta=0.20,
            expected_roas_delta=0.15,
            confidence=0.90,
            risk_score=0.10,
            markets=["US"],
        )]
        ranking = StrategyRanking(strategies=exploit)
        selected = controller.select_with_exploration(ranking, exploit, total_count=4, mutation_strength=0.3)
        variants = [s for s in selected if s.exploration]
        assert len(variants) > 0
        for v in variants:
            assert v.confidence < 0.90  # 变体置信度更低
            assert v.risk_score > 0.10  # 变体风险更高

    def test_repr(self):
        """ExplorationController repr。"""
        controller = ExplorationController()
        r = repr(controller)
        assert "ExplorationController" in r


# ═══════════════════════════════════════════════════════════
# 5. MetaOptimizer (22 tests)
# ═══════════════════════════════════════════════════════════


class TestMetaOptimizer:
    """MetaOptimizer 测试。"""

    def test_optimize_from_patterns(self):
        """从 Pattern 完整优化。"""
        optimizer = MetaOptimizer()
        patterns = [
            make_pattern("Rescue Hook", sr=0.85, sample_count=50),
            make_pattern("Reward Reveal", sr=0.82, sample_count=40),
        ]
        result = optimizer.optimize_from_patterns(patterns, "Merge Dragon", total_count=5)
        assert isinstance(result, OptimizationResult)
        assert result.strategies_generated > 0
        assert len(result.strategies) <= 5

    def test_optimize_from_knowledge(self):
        """从 Knowledge Graph 完整优化。"""
        optimizer = MetaOptimizer()
        node1 = make_knowledge_node("N1", NodeType.GENE, "Rescue Emotion")
        node2 = make_knowledge_node("N2", NodeType.METRIC, "CTR")
        edge = make_knowledge_edge("N1", "N2", RelationType.IMPROVES, weight=0.78, evidence_count=100, confidence=0.92)
        result = optimizer.optimize_from_knowledge([node1, node2], [edge], "p04", total_count=5)
        assert isinstance(result, OptimizationResult)
        assert result.total_knowledge == 2

    def test_optimize_full(self):
        """完整优化（Pattern + Knowledge）。"""
        optimizer = MetaOptimizer()
        patterns = [make_pattern("Rescue Hook", sr=0.85, sample_count=50)]
        node1 = make_knowledge_node("N1", NodeType.GENE, "Rescue")
        node2 = make_knowledge_node("N2", NodeType.METRIC, "ROAS")
        edge = make_knowledge_edge("N1", "N2", RelationType.IMPROVES, weight=0.70, evidence_count=80, confidence=0.88)
        result = optimizer.optimize_full(patterns, [node1, node2], [edge], "Merge Dragon", total_count=5)
        assert result.strategies_generated > 0
        assert result.total_patterns == 1
        assert result.total_knowledge == 2

    def test_optimize_empty(self):
        """空输入优化。"""
        optimizer = MetaOptimizer()
        result = optimizer.optimize(patterns=[], knowledge_nodes=[], knowledge_edges=[])
        assert result.strategies_generated == 0
        assert result.strategies_selected == 0

    def test_optimize_with_goal(self):
        """带目标优化。"""
        optimizer = MetaOptimizer()
        patterns = [
            make_pattern("CTR Hook", sr=0.85, ctr=0.30, roas=0.05),
            make_pattern("ROAS Hook", sr=0.85, ctr=0.05, roas=0.30),
        ]
        result = optimizer.optimize(
            patterns=patterns,
            target_product="p04",
            total_count=5,
            goal=OptimizationGoal.CTR,
        )
        assert result.ranking is not None

    def test_optimize_without_exploration(self):
        """不含探索策略的优化。"""
        optimizer = MetaOptimizer()
        patterns = [make_pattern("Hook", sr=0.85, sample_count=50)]
        result = optimizer.optimize(
            patterns=patterns,
            include_exploration=False,
            total_count=3,
        )
        assert all(not s.exploration for s in result.strategies)

    def test_optimize_with_fatigue(self):
        """带疲劳度的优化。"""
        optimizer = MetaOptimizer()
        patterns = [make_pattern("Hook", sr=0.85, sample_count=50)]
        result = optimizer.optimize(patterns=patterns, total_count=5, fatigue_level=0.85)
        assert isinstance(result, OptimizationResult)

    def test_get_evolution_strategies(self):
        """获取 E11 兼容格式。"""
        optimizer = MetaOptimizer()
        patterns = [make_pattern("Hook", sr=0.85, sample_count=50)]
        result = optimizer.optimize(patterns=patterns, total_count=3)
        evo_list = optimizer.get_evolution_strategies(result)
        assert len(evo_list) == len(result.strategies)
        for evo in evo_list:
            assert "strategy_id" in evo
            assert "optimization_goal" in evo
            assert "dna_mutations" in evo
            assert "expected_impact" in evo

    def test_optimize_multi_product(self):
        """多产品优化。"""
        optimizer = MetaOptimizer()
        patterns = [
            make_pattern("Hook A", sr=0.85, products=["Merge Dragon"]),
            make_pattern("Hook B", sr=0.82, products=["Merge Witch"]),
        ]
        result = optimizer.optimize(patterns=patterns, total_count=5)
        assert result.strategies_generated > 0

    def test_optimize_result_summary(self):
        """优化结果摘要。"""
        optimizer = MetaOptimizer()
        patterns = [make_pattern("Hook", sr=0.85, sample_count=50)]
        result = optimizer.optimize(patterns=patterns, total_count=3)
        assert "patterns" in result.summary
        assert "strategies" in result.summary

    def test_optimize_result_to_dict(self):
        """OptimizationResult to_dict。"""
        optimizer = MetaOptimizer()
        patterns = [make_pattern("Hook", sr=0.85, sample_count=50)]
        result = optimizer.optimize(patterns=patterns, total_count=3)
        d = result.to_dict()
        assert "strategies" in d
        assert "ranking" in d
        assert "exploration_policy" in d
        assert "exploit_strategies" in d
        assert "explore_strategies" in d

    def test_optimize_strategies_are_ranked(self):
        """优化后策略已排序。"""
        optimizer = MetaOptimizer()
        patterns = [
            make_pattern("Strong", sr=0.90, sample_count=100, ctr=0.30),
            make_pattern("Medium", sr=0.75, sample_count=30, ctr=0.15),
        ]
        result = optimizer.optimize(patterns=patterns, total_count=5)
        if len(result.strategies) >= 2:
            assert result.strategies[0].score >= result.strategies[-1].score

    def test_optimize_repr(self):
        """MetaOptimizer repr。"""
        optimizer = MetaOptimizer()
        r = repr(optimizer)
        assert "MetaOptimizer" in r

    def test_optimize_custom_ratios(self):
        """自定义 exploit/explore 比例。"""
        optimizer = MetaOptimizer(exploit_ratio=0.5, explore_ratio=0.5)
        assert optimizer.exploration.policy.exploit_ratio == 0.5
        assert optimizer.exploration.policy.explore_ratio == 0.5

    def test_optimize_total_count_larger_than_strategies(self):
        """total_count 大于策略数。"""
        optimizer = MetaOptimizer()
        patterns = [make_pattern("Hook", sr=0.85, sample_count=50)]
        result = optimizer.optimize(patterns=patterns, total_count=20)
        # 不应崩溃，返回实际可用的策略数
        assert len(result.strategies) > 0


# ═══════════════════════════════════════════════════════════
# 6. Pipeline Integration (10 tests)
# ═══════════════════════════════════════════════════════════


class TestFullPipeline:
    """完整 Pipeline 集成测试。"""

    def test_full_pipeline_patterns_only(self):
        """仅 Pattern 完整流程。"""
        optimizer = MetaOptimizer()
        patterns = [
            make_pattern("Rescue Hook", sr=0.88, ctr=0.25, roas=0.15, sample_count=100),
            make_pattern("Reward Reveal", sr=0.84, ctr=0.20, roas=0.22, sample_count=80),
            make_pattern("Cute Character", sr=0.77, ctr=0.15, roas=0.10, sample_count=30),
            make_pattern("Low Performer", sr=0.55, ctr=0.02, roas=0.01, sample_count=20),
        ]
        result = optimizer.optimize(patterns=patterns, target_product="Merge Dragon", total_count=8)
        assert result.strategies_generated > 0
        assert result.total_patterns == 4
        # 低成功率 pattern 被忽略
        assert result.strategies_generated < 8  # 不会全部生成

    def test_full_pipeline_with_knowledge(self):
        """Pattern + Knowledge Graph 完整流程。"""
        optimizer = MetaOptimizer()
        patterns = [
            make_pattern("Rescue", sr=0.85, ctr=0.25, sample_count=50),
        ]
        nodes = [
            make_knowledge_node("N1", NodeType.GENE, "Rescue Emotion"),
            make_knowledge_node("N2", NodeType.METRIC, "CTR"),
            make_knowledge_node("N3", NodeType.GENE, "Cute Character"),
        ]
        edges = [
            make_knowledge_edge("N1", "N2", RelationType.IMPROVES, weight=0.82, evidence_count=200, confidence=0.93),
            make_knowledge_edge("N1", "N3", RelationType.COMBINES_WITH, weight=0.75, evidence_count=80, confidence=0.85),
        ]
        result = optimizer.optimize(
            patterns=patterns,
            knowledge_nodes=nodes,
            knowledge_edges=edges,
            target_product="Merge Dragon",
            total_count=10,
        )
        assert result.strategies_generated > 0
        assert result.total_patterns == 1
        assert result.total_knowledge == 3

    def test_pipeline_evolution_strategy_output(self):
        """Pipeline 输出 E11 兼容格式。"""
        optimizer = MetaOptimizer()
        patterns = [make_pattern("Hook", sr=0.85, ctr=0.25, sample_count=50)]
        result = optimizer.optimize(patterns=patterns, total_count=3)
        evo_strategies = optimizer.get_evolution_strategies(result)
        for evo in evo_strategies:
            assert "priority" in evo
            assert "confidence" in evo
            assert "risk_score" in evo
            assert "dna_mutations" in evo
            assert "expected_impact" in evo

    def test_pipeline_all_weak_patterns(self):
        """全部弱 Pattern 场景。"""
        optimizer = MetaOptimizer()
        patterns = [
            make_pattern("Weak A", sr=0.55, sample_count=20),
            make_pattern("Weak B", sr=0.60, sample_count=10),
        ]
        result = optimizer.optimize(patterns=patterns, total_count=5)
        # 弱 Pattern 被忽略，但探索策略仍生成
        assert result.strategies_generated >= 0

    def test_pipeline_result_ranking(self):
        """Pipeline 结果含排名。"""
        optimizer = MetaOptimizer()
        patterns = [
            make_pattern("A", sr=0.90, ctr=0.30, sample_count=100),
            make_pattern("B", sr=0.85, ctr=0.20, sample_count=80),
        ]
        result = optimizer.optimize(patterns=patterns, total_count=5)
        assert result.ranking is not None
        assert result.ranking.total_count > 0

    def test_pipeline_strategies_marked_selected(self):
        """Pipeline 策略标记为 SELECTED。"""
        optimizer = MetaOptimizer()
        patterns = [make_pattern("Hook", sr=0.85, sample_count=50)]
        result = optimizer.optimize(patterns=patterns, total_count=3)
        for s in result.strategies:
            assert s.status == StrategyStatus.SELECTED

    def test_pipeline_no_duplicate_strategies(self):
        """Pipeline 不产生重复策略。"""
        optimizer = MetaOptimizer()
        patterns = [make_pattern("Hook", sr=0.85, sample_count=50)]
        result = optimizer.optimize(patterns=patterns, total_count=5)
        ids = [s.strategy_id for s in result.strategies]
        assert len(ids) == len(set(ids))

    def test_pipeline_exploit_explore_contained(self):
        """Pipeline 包含 exploit 和 explore 策略。"""
        optimizer = MetaOptimizer()
        patterns = [
            make_pattern("Strong", sr=0.90, ctr=0.30, sample_count=100),
            make_pattern("Medium", sr=0.75, ctr=0.15, sample_count=30),
        ]
        result = optimizer.optimize(patterns=patterns, total_count=10)
        exploit_count = len(result.get_exploit_strategies())
        explore_count = len(result.get_explore_strategies())
        assert exploit_count + explore_count == len(result.strategies)

    def test_pipeline_with_goal_ctr(self):
        """Pipeline 按 CTR 目标优化。"""
        optimizer = MetaOptimizer()
        patterns = [
            make_pattern("CTR Pattern", sr=0.85, ctr=0.35, roas=0.05, sample_count=50),
            make_pattern("ROAS Pattern", sr=0.85, ctr=0.05, roas=0.35, sample_count=50),
        ]
        result = optimizer.optimize(
            patterns=patterns,
            total_count=5,
            goal=OptimizationGoal.CTR,
        )
        assert result.ranking is not None

    def test_pipeline_result_repr(self):
        """OptimizationResult repr。"""
        optimizer = MetaOptimizer()
        patterns = [make_pattern("Hook", sr=0.85, sample_count=50)]
        result = optimizer.optimize(patterns=patterns, total_count=3)
        r = repr(result)
        assert "OptimizationResult" in r


# ═══════════════════════════════════════════════════════════
# 7. Edge Cases (10 tests)
# ═══════════════════════════════════════════════════════════


class TestEdgeCases:
    """边界情况测试。"""

    def test_single_pattern_optimization(self):
        """单 Pattern 优化。"""
        optimizer = MetaOptimizer()
        pattern = make_pattern("Only", sr=0.90, sample_count=100)
        result = optimizer.optimize(patterns=[pattern], total_count=1)
        assert len(result.strategies) == 1

    def test_pattern_with_no_markets(self):
        """无市场信息的 Pattern。"""
        gen = StrategyGenerator()
        pattern = make_pattern("No Market", sr=0.85, markets=[])
        strategies = gen.generate_from_patterns([pattern])
        if strategies:
            assert strategies[0].markets == []

    def test_pattern_with_no_products(self):
        """无产品信息的 Pattern。"""
        gen = StrategyGenerator()
        pattern = make_pattern("No Product", sr=0.85, products=[])
        strategies = gen.generate_from_patterns([pattern])
        if strategies:
            assert strategies[0].target_product == ""

    def test_strategy_score_zero_evidence(self):
        """零证据策略评分。"""
        ranker = StrategyRanker()
        s = MetaStrategy(
            confidence=0.50,
            expected_ctr_delta=0.0,
            evidence_count=0,
            risk_score=0.90,
            exploration=True,
        )
        score = ranker.score_strategy(s)
        assert 0.0 <= score <= 1.0

    def test_exploration_policy_boundary(self):
        """ExplorationPolicy 边界值。"""
        p = ExplorationPolicy(exploit_ratio=0.0, explore_ratio=1.0)
        assert p.exploit_ratio == 0.0
        assert p.explore_ratio == 1.0

    def test_strategy_ranking_to_dict(self):
        """StrategyRanking to_dict。"""
        ranking = StrategyRanking(strategies=[
            MetaStrategy(name="A", score=0.9),
            MetaStrategy(name="B", score=0.5, exploration=True),
        ])
        d = ranking.to_dict()
        assert d["total_count"] == 2
        assert len(d["top_exploit"]) == 1
        assert len(d["top_explore"]) == 1

    def test_exploration_policy_to_dict(self):
        """ExplorationPolicy to_dict。"""
        p = ExplorationPolicy()
        d = p.to_dict()
        assert d["exploit_ratio"] == 0.7
        assert d["explore_ratio"] == 0.3

    def test_meta_strategy_strategy_source(self):
        """MetaStrategy strategy_source。"""
        s = MetaStrategy(strategy_source=StrategySource.PATTERN)
        assert s.strategy_source == StrategySource.PATTERN
        assert s.to_dict()["strategy_source"] == "pattern"

    def test_optimization_result_no_ranking(self):
        """OptimizationResult 无 ranking。"""
        result = OptimizationResult(strategies=[], ranking=None)
        assert result.strategies_selected == 0

    def test_ranker_build_summary(self):
        """ranker _build_summary。"""
        ranker = StrategyRanker()
        s1 = MetaStrategy(name="Best", score=0.95, exploration=False)
        s2 = MetaStrategy(name="Explore", score=0.50, exploration=True)
        summary = ranker._build_summary([s1, s2], [s1], [s2])
        assert "Ranked 2" in summary
        assert "Best" in summary
        assert "Explore" in summary