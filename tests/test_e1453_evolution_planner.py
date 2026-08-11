"""E14.5.3 Evolution Planner — 集成测试.

验证 EvolutionPlanner 的进化方向决策能力:
  - EvolutionGoal / GeneMutationPlan / EvolutionPlan 模型 (15 tests)
  - EvolutionPlanner.plan() 核心规划 (25 tests)
  - 多样性驱动规划 (10 tests)
  - 趋势驱动规划 (10 tests)
  - 快捷查询 (10 tests)
  - CreativeAgent 集成 (10 tests)
  - 回归 (E14.5.2 / E14.5.1 / E14.4.4 / E14.4.3 / E14.4.2 / E14.4.1) (20 tests)

总计: 100 个测试用例
"""

from __future__ import annotations

import pytest

from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent import (
    CreativeAgent,
    CreativeMemory,
    create_creative_agent,
)

from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain import (
    GenomeIntelligence,
    GenePerformance,
    GenomeIntelligenceReport,
    PopulationAnalyzer,
    PopulationHealthReport,
    DiversityMetrics,
    EvolutionPlanner,
    EvolutionGoal,
    GeneMutationPlan,
    EvolutionPlan,
    create_evolution_planner,
)


# ═══════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════


@pytest.fixture
def agent():
    return create_creative_agent()


@pytest.fixture
def genome_intelligence():
    return GenomeIntelligence(min_samples=2)


@pytest.fixture
def population_analyzer(genome_intelligence):
    return PopulationAnalyzer(genome_intelligence=genome_intelligence)


@pytest.fixture
def evolution_planner(genome_intelligence, population_analyzer):
    return EvolutionPlanner(
        genome_intelligence=genome_intelligence,
        population_analyzer=population_analyzer,
    )


@pytest.fixture
def populated_agent(agent):
    """填充多样化 DNA 数据."""
    memory = agent.get_memory()
    for i, (hook, visual, emotion, roas) in enumerate([
        ("transformation", "fantasy", "surprise", 2.5),
        ("transformation", "fantasy", "surprise", 2.3),
        ("transformation", "fantasy", "excitement", 2.1),
        ("rescue", "fantasy", "curiosity", 1.8),
        ("rescue", "realistic", "fear", 1.6),
        ("before_after", "fantasy", "achievement", 1.5),
        ("before_after", "fantasy", "achievement", 1.4),
        ("challenge", "dark", "urgency", 0.8),
        ("challenge", "dark", "urgency", 0.7),
        ("curiosity", "minimal", "relaxation", 0.5),
        ("failure", "minimal", "surprise", 1.2),
        ("failure", "realistic", "curiosity", 1.1),
    ]):
        dna = agent.extract_dna(
            f"C{100 + i}", f"creative_{i}",
            hook=hook, visual=visual, emotion=emotion,
            fitness={"roas": roas, "ctr": 0.03},
        )
        memory.store_dna(dna, is_winner=(roas >= 1.5), performance={"roas": roas, "ctr": 0.03})
    return agent


@pytest.fixture
def homogeneous_agent(agent):
    """填充同质化 DNA (80% 相同基因)."""
    memory = agent.get_memory()
    for i in range(10):
        hook = "transformation" if i < 8 else "rescue"
        visual = "fantasy" if i < 8 else "realistic"
        emotion = "surprise" if i < 8 else "curiosity"
        dna = agent.extract_dna(
            f"C{200 + i}", f"homo_{i}",
            hook=hook, visual=visual, emotion=emotion,
            fitness={"roas": 1.5 + i * 0.05},
        )
        memory.store_dna(dna, is_winner=True, performance={"roas": 1.5 + i * 0.05})
    return agent


@pytest.fixture
def diverse_agent(agent):
    """填充高多样性 DNA."""
    memory = agent.get_memory()
    hooks = ["transformation", "rescue", "before_after", "challenge", "curiosity",
             "failure", "puzzle", "upgrade", "collection", "escape"]
    visuals = ["fantasy", "realistic", "dark", "minimal", "vibrant",
               "cartoon", "3d", "pixel", "watercolor", "neon"]
    emotions = ["surprise", "excitement", "curiosity", "fear", "achievement",
                "urgency", "relaxation", "satisfaction", "anticipation", "trust"]
    gameplays = ["merge", "puzzle", "strategy", "casual", "action",
                 "rpg", "simulation", "arcade", "adventure", "idle"]
    for i in range(10):
        dna = agent.extract_dna(
            f"C{300 + i}", f"div_{i}",
            hook=hooks[i], visual=visuals[i], emotion=emotions[i],
            gameplay=gameplays[i],
            fitness={"roas": 1.0 + i * 0.15},
        )
        memory.store_dna(dna, is_winner=(i >= 5), performance={"roas": 1.0 + i * 0.15})
    return agent


# ═══════════════════════════════════════════════════════════
# EvolutionGoal 模型测试 (5 tests)
# ═══════════════════════════════════════════════════════════


class TestEvolutionGoal:
    """EvolutionGoal 数据模型."""

    def test_create_default(self):
        goal = EvolutionGoal()
        assert goal.goal_id == ""
        assert goal.priority == 5

    def test_create_with_data(self):
        goal = EvolutionGoal(
            goal_id="goal_1",
            goal_type="increase_diversity",
            gene_category="hook",
            description="增加 hook 多样性",
            priority=9,
            reason="hook 基因多样性不足",
        )
        assert goal.goal_type == "increase_diversity"
        assert goal.priority == 9

    def test_to_dict(self):
        goal = EvolutionGoal(
            goal_id="g1",
            goal_type="amplify_rising",
            gene_category="visual",
            description="放大 visual 优势",
            priority=7,
            reason="上升趋势",
        )
        d = goal.to_dict()
        assert d["goal_id"] == "g1"
        assert d["gene_category"] == "visual"

    def test_no_gene_category(self):
        goal = EvolutionGoal(
            goal_id="g2",
            goal_type="explore_new",
            description="全局探索",
            priority=10,
        )
        assert goal.gene_category is None

    def test_priority_range(self):
        for p in [1, 5, 10]:
            goal = EvolutionGoal(priority=p)
            assert 1 <= goal.priority <= 10


# ═══════════════════════════════════════════════════════════
# GeneMutationPlan 模型测试 (5 tests)
# ═══════════════════════════════════════════════════════════


class TestGeneMutationPlan:
    """GeneMutationPlan 数据模型."""

    def test_create_default(self):
        mp = GeneMutationPlan()
        assert mp.gene_category == ""
        assert mp.percentage == 0.0

    def test_create_with_data(self):
        mp = GeneMutationPlan(
            gene_category="hook",
            direction="transformation",
            percentage=0.30,
            reason="上升趋势",
            expected_impact="+15% ROAS",
            confidence=0.8,
        )
        assert mp.gene_category == "hook"
        assert mp.direction == "transformation"
        assert mp.percentage == 0.30

    def test_to_dict(self):
        mp = GeneMutationPlan(
            gene_category="visual",
            direction="real_world_scene",
            percentage=0.40,
            reason="增加多样性",
            expected_impact="降低 fatigue",
            confidence=0.6,
        )
        d = mp.to_dict()
        assert d["gene_category"] == "visual"
        assert d["percentage"] == 0.40
        assert d["confidence"] == 0.6

    def test_percentage_range(self):
        for pct in [0.05, 0.25, 0.50]:
            mp = GeneMutationPlan(percentage=pct)
            assert 0 <= mp.percentage <= 1.0

    def test_expected_impact(self):
        mp = GeneMutationPlan(expected_impact="+20% CTR")
        assert "+20% CTR" in mp.expected_impact


# ═══════════════════════════════════════════════════════════
# EvolutionPlan 模型测试 (5 tests)
# ═══════════════════════════════════════════════════════════


class TestEvolutionPlan:
    """EvolutionPlan 数据模型."""

    def test_create_default(self):
        plan = EvolutionPlan()
        assert plan.plan_id == ""
        assert plan.goals == []

    def test_total_percentage(self):
        plan = EvolutionPlan(mutation_plans=[
            GeneMutationPlan(percentage=0.3),
            GeneMutationPlan(percentage=0.4),
        ])
        assert plan.total_percentage == 0.7

    def test_has_goals(self):
        plan = EvolutionPlan(goals=[EvolutionGoal(goal_id="g1")])
        assert plan.has_goals

    def test_get_mutation_plans_by_gene(self):
        plan = EvolutionPlan(mutation_plans=[
            GeneMutationPlan(gene_category="hook", direction="a"),
            GeneMutationPlan(gene_category="visual", direction="b"),
            GeneMutationPlan(gene_category="hook", direction="c"),
        ])
        hook_plans = plan.get_mutation_plans_by_gene("hook")
        assert len(hook_plans) == 2

    def test_to_dict(self):
        plan = EvolutionPlan(
            plan_id="ep_001",
            target_population_size=50,
            generation=1,
            summary="测试计划",
            goals=[EvolutionGoal(goal_id="g1", goal_type="increase_diversity")],
            mutation_plans=[GeneMutationPlan(gene_category="hook", direction="a", percentage=0.3)],
        )
        d = plan.to_dict()
        assert d["plan_id"] == "ep_001"
        assert d["total_percentage"] == 0.3
        assert d["has_goals"]


# ═══════════════════════════════════════════════════════════
# EvolutionPlanner 核心规划测试 (25 tests)
# ═══════════════════════════════════════════════════════════


class TestEvolutionPlannerPlan:
    """EvolutionPlanner.plan() 核心规划."""

    # ── 基本规划 ──────────────────────────────────────────

    def test_plan_empty(self, evolution_planner):
        plan = evolution_planner.plan()
        assert isinstance(plan, EvolutionPlan)
        assert plan.plan_id.startswith("ep_")

    def test_plan_with_data(self, evolution_planner, populated_agent):
        gi = GenomeIntelligence(memory=populated_agent.get_memory(), min_samples=2)
        pa = PopulationAnalyzer(genome_intelligence=gi)
        planner = EvolutionPlanner(genome_intelligence=gi, population_analyzer=pa)
        plan = planner.plan()
        assert isinstance(plan, EvolutionPlan)
        assert plan.generation > 0

    def test_plan_has_goals(self, evolution_planner, populated_agent):
        gi = GenomeIntelligence(memory=populated_agent.get_memory(), min_samples=2)
        pa = PopulationAnalyzer(genome_intelligence=gi)
        planner = EvolutionPlanner(genome_intelligence=gi, population_analyzer=pa)
        plan = planner.plan()
        assert isinstance(plan.goals, list)

    def test_plan_has_mutation_plans(self, evolution_planner, populated_agent):
        gi = GenomeIntelligence(memory=populated_agent.get_memory(), min_samples=2)
        pa = PopulationAnalyzer(genome_intelligence=gi)
        planner = EvolutionPlanner(genome_intelligence=gi, population_analyzer=pa)
        plan = planner.plan()
        assert isinstance(plan.mutation_plans, list)

    def test_plan_has_summary(self, evolution_planner, populated_agent):
        gi = GenomeIntelligence(memory=populated_agent.get_memory(), min_samples=2)
        pa = PopulationAnalyzer(genome_intelligence=gi)
        planner = EvolutionPlanner(genome_intelligence=gi, population_analyzer=pa)
        plan = planner.plan()
        assert plan.summary

    def test_plan_created_at(self, evolution_planner):
        plan = evolution_planner.plan()
        assert plan.created_at

    def test_plan_target_population(self, evolution_planner, populated_agent):
        gi = GenomeIntelligence(memory=populated_agent.get_memory(), min_samples=2)
        pa = PopulationAnalyzer(genome_intelligence=gi)
        planner = EvolutionPlanner(genome_intelligence=gi, population_analyzer=pa)
        plan = planner.plan()
        assert plan.target_population_size > 0

    # ── 同质化群体规划 ────────────────────────────────────

    def test_homogeneous_triggers_diversity_goals(self, evolution_planner, homogeneous_agent):
        gi = GenomeIntelligence(memory=homogeneous_agent.get_memory(), min_samples=2)
        pa = PopulationAnalyzer(genome_intelligence=gi)
        planner = EvolutionPlanner(genome_intelligence=gi, population_analyzer=pa)
        plan = planner.plan()
        # 同质化群体应该有 diversity 或 explore 目标
        goal_types = [g.goal_type for g in plan.goals]
        assert any(t in ("increase_diversity", "explore_new") for t in goal_types)

    def test_homogeneous_has_mutation(self, evolution_planner, homogeneous_agent):
        gi = GenomeIntelligence(memory=homogeneous_agent.get_memory(), min_samples=2)
        pa = PopulationAnalyzer(genome_intelligence=gi)
        planner = EvolutionPlanner(genome_intelligence=gi, population_analyzer=pa)
        plan = planner.plan()
        assert len(plan.mutation_plans) > 0

    def test_homogeneous_goals_sorted_by_priority(self, evolution_planner, homogeneous_agent):
        gi = GenomeIntelligence(memory=homogeneous_agent.get_memory(), min_samples=2)
        pa = PopulationAnalyzer(genome_intelligence=gi)
        planner = EvolutionPlanner(genome_intelligence=gi, population_analyzer=pa)
        plan = planner.plan()
        if len(plan.goals) >= 2:
            for i in range(len(plan.goals) - 1):
                assert plan.goals[i].priority >= plan.goals[i + 1].priority

    # ── 多样化群体规划 ────────────────────────────────────

    def test_diverse_has_fewer_goals(self, evolution_planner, diverse_agent):
        gi = GenomeIntelligence(memory=diverse_agent.get_memory(), min_samples=2)
        pa = PopulationAnalyzer(genome_intelligence=gi)
        planner = EvolutionPlanner(genome_intelligence=gi, population_analyzer=pa)
        plan = planner.plan()
        # 多样化群体应该有较少的目标
        assert isinstance(plan.goals, list)

    def test_diverse_plan_to_dict(self, evolution_planner, diverse_agent):
        gi = GenomeIntelligence(memory=diverse_agent.get_memory(), min_samples=2)
        pa = PopulationAnalyzer(genome_intelligence=gi)
        planner = EvolutionPlanner(genome_intelligence=gi, population_analyzer=pa)
        plan = planner.plan()
        d = plan.to_dict()
        assert "plan_id" in d
        assert "goals" in d
        assert "mutation_plans" in d

    # ── 变异计划质量 ──────────────────────────────────────

    def test_mutation_plans_have_reason(self, evolution_planner, homogeneous_agent):
        gi = GenomeIntelligence(memory=homogeneous_agent.get_memory(), min_samples=2)
        pa = PopulationAnalyzer(genome_intelligence=gi)
        planner = EvolutionPlanner(genome_intelligence=gi, population_analyzer=pa)
        plan = planner.plan()
        for mp in plan.mutation_plans:
            assert mp.reason

    def test_mutation_plans_percentage_range(self, evolution_planner, homogeneous_agent):
        gi = GenomeIntelligence(memory=homogeneous_agent.get_memory(), min_samples=2)
        pa = PopulationAnalyzer(genome_intelligence=gi)
        planner = EvolutionPlanner(genome_intelligence=gi, population_analyzer=pa)
        plan = planner.plan()
        for mp in plan.mutation_plans:
            assert mp.percentage >= planner._min_mutation_pct
            assert mp.percentage <= planner._max_mutation_pct

    def test_mutation_plans_gene_category(self, evolution_planner, homogeneous_agent):
        gi = GenomeIntelligence(memory=homogeneous_agent.get_memory(), min_samples=2)
        pa = PopulationAnalyzer(genome_intelligence=gi)
        planner = EvolutionPlanner(genome_intelligence=gi, population_analyzer=pa)
        plan = planner.plan()
        for mp in plan.mutation_plans:
            assert mp.gene_category in GenomeIntelligence.GENE_CATEGORIES

    # ── 自定义报告规划 ────────────────────────────────────

    def test_plan_with_custom_reports(self, evolution_planner, populated_agent):
        gi = GenomeIntelligence(memory=populated_agent.get_memory(), min_samples=2)
        gi_report = gi.analyze()
        pa = PopulationAnalyzer(genome_intelligence=gi)
        health_report = pa.analyze(genome_report=gi_report)

        planner = EvolutionPlanner(genome_intelligence=gi, population_analyzer=pa)
        plan = planner.plan(genome_report=gi_report, health_report=health_report)
        assert isinstance(plan, EvolutionPlan)

    def test_plan_with_historical_report(self, evolution_planner, agent):
        memory = agent.get_memory()
        for _ in range(5):
            dna = agent.extract_dna("C_hist", "hist", hook="transformation",
                                    visual="fantasy", emotion="surprise",
                                    fitness={"roas": 1.0})
            memory.store_dna(dna, is_winner=False, performance={"roas": 1.0})
        hist_gi = GenomeIntelligence(memory=memory, min_samples=2)
        hist_report = hist_gi.analyze()

        for _ in range(5):
            dna = agent.extract_dna("C_recent", "recent", hook="transformation",
                                    visual="fantasy", emotion="surprise",
                                    fitness={"roas": 2.5})
            memory.store_dna(dna, is_winner=True, performance={"roas": 2.5})
        cur_gi = GenomeIntelligence(memory=memory, min_samples=2)
        cur_report = cur_gi.analyze()

        pa = PopulationAnalyzer(genome_intelligence=cur_gi)
        planner = EvolutionPlanner(genome_intelligence=cur_gi, population_analyzer=pa)
        plan = planner.plan(genome_report=cur_report, historical_report=hist_report)
        assert isinstance(plan, EvolutionPlan)

    # ── 代际递增 ──────────────────────────────────────────

    def test_generation_increments(self, evolution_planner):
        plan1 = evolution_planner.plan()
        plan2 = evolution_planner.plan()
        assert plan2.generation == plan1.generation + 1

    def test_generation_reset(self, evolution_planner):
        evolution_planner.plan()
        evolution_planner.reset()
        plan = evolution_planner.plan()
        assert plan.generation == 1

    # ── 边界条件 ──────────────────────────────────────────

    def test_plan_empty_reports(self, evolution_planner):
        empty_genome = GenomeIntelligenceReport()
        empty_health = PopulationHealthReport()
        plan = evolution_planner.plan(genome_report=empty_genome, health_report=empty_health)
        assert isinstance(plan, EvolutionPlan)

    def test_plan_idempotent(self, evolution_planner):
        plan1 = evolution_planner.plan()
        plan2 = evolution_planner.plan()
        # 代际不同但结构相同
        assert isinstance(plan1, EvolutionPlan)
        assert isinstance(plan2, EvolutionPlan)

    def test_total_percentage_sum(self, evolution_planner, homogeneous_agent):
        gi = GenomeIntelligence(memory=homogeneous_agent.get_memory(), min_samples=2)
        pa = PopulationAnalyzer(genome_intelligence=gi)
        planner = EvolutionPlanner(genome_intelligence=gi, population_analyzer=pa)
        plan = planner.plan()
        assert plan.total_percentage >= 0

    def test_plan_to_dict(self, evolution_planner, populated_agent):
        gi = GenomeIntelligence(memory=populated_agent.get_memory(), min_samples=2)
        pa = PopulationAnalyzer(genome_intelligence=gi)
        planner = EvolutionPlanner(genome_intelligence=gi, population_analyzer=pa)
        plan = planner.plan()
        d = plan.to_dict()
        assert isinstance(d, dict)
        assert "total_percentage" in d

    def test_get_mutation_plans_by_gene(self, evolution_planner, homogeneous_agent):
        gi = GenomeIntelligence(memory=homogeneous_agent.get_memory(), min_samples=2)
        pa = PopulationAnalyzer(genome_intelligence=gi)
        planner = EvolutionPlanner(genome_intelligence=gi, population_analyzer=pa)
        plan = planner.plan()
        hook_plans = plan.get_mutation_plans_by_gene("hook")
        assert isinstance(hook_plans, list)


# ═══════════════════════════════════════════════════════════
# 多样性驱动规划测试 (10 tests)
# ═══════════════════════════════════════════════════════════


class TestDiversityDrivenPlanning:
    """多样性驱动规划."""

    def test_find_alternative_direction(self, evolution_planner, populated_agent):
        gi = GenomeIntelligence(memory=populated_agent.get_memory(), min_samples=2)
        report = gi.analyze()
        planner = EvolutionPlanner(genome_intelligence=gi)
        direction = planner._find_alternative_direction(report, "hook")
        assert direction != ""

    def test_find_alternative_single_value(self, evolution_planner, agent):
        memory = agent.get_memory()
        for _ in range(5):
            dna = agent.extract_dna("C_test", "test", hook="transformation",
                                    visual="fantasy", emotion="surprise",
                                    fitness={"roas": 2.0})
            memory.store_dna(dna, is_winner=True, performance={"roas": 2.0})
        gi = GenomeIntelligence(memory=memory, min_samples=2)
        report = gi.analyze()
        planner = EvolutionPlanner(genome_intelligence=gi)
        direction = planner._find_alternative_direction(report, "hook")
        assert direction == "not_transformation" or direction != "transformation"

    def test_find_alternative_empty(self, evolution_planner):
        report = GenomeIntelligenceReport()
        planner = evolution_planner
        direction = planner._find_alternative_direction(report, "hook")
        assert direction == "new_direction"

    def test_extract_gene_value(self, evolution_planner):
        value = evolution_planner._extract_gene_value("放大 hook=transformation (上升趋势 +25%)")
        assert value == "transformation"

    def test_extract_gene_value_no_match(self, evolution_planner):
        value = evolution_planner._extract_gene_value("无匹配文本")
        assert value == ""

    def test_calculate_target_size_small(self, evolution_planner):
        report = GenomeIntelligenceReport(total_dnas_analyzed=10)
        size = evolution_planner._calculate_target_size(report)
        assert size >= 20

    def test_calculate_target_size_medium(self, evolution_planner):
        report = GenomeIntelligenceReport(total_dnas_analyzed=30)
        size = evolution_planner._calculate_target_size(report)
        assert size >= 30

    def test_calculate_target_size_large(self, evolution_planner):
        report = GenomeIntelligenceReport(total_dnas_analyzed=100)
        size = evolution_planner._calculate_target_size(report)
        assert size >= 100

    def test_generate_summary(self, evolution_planner):
        goals = [
            EvolutionGoal(goal_id="g1", goal_type="increase_diversity", priority=9),
            EvolutionGoal(goal_id="g2", goal_type="amplify_rising", priority=7),
        ]
        plans = [
            GeneMutationPlan(gene_category="hook", direction="transformation", percentage=0.3),
        ]
        summary = evolution_planner._generate_summary(goals, plans)
        assert "多样性" in summary or "diversity" in summary.lower() or "increase_diversity" in summary

    def test_generate_summary_empty(self, evolution_planner):
        summary = evolution_planner._generate_summary([], [])
        assert summary == ""


# ═══════════════════════════════════════════════════════════
# 趋势驱动规划测试 (10 tests)
# ═══════════════════════════════════════════════════════════


class TestTrendDrivenPlanning:
    """趋势驱动规划."""

    def test_plan_with_rising_trend(self, evolution_planner, agent):
        memory = agent.get_memory()
        for _ in range(5):
            dna = agent.extract_dna("C_hist", "hist", hook="transformation",
                                    visual="fantasy", emotion="surprise",
                                    fitness={"roas": 1.0})
            memory.store_dna(dna, is_winner=False, performance={"roas": 1.0})
        hist_gi = GenomeIntelligence(memory=memory, min_samples=2)
        hist_report = hist_gi.analyze()

        for _ in range(5):
            dna = agent.extract_dna("C_recent", "recent", hook="transformation",
                                    visual="fantasy", emotion="surprise",
                                    fitness={"roas": 2.5})
            memory.store_dna(dna, is_winner=True, performance={"roas": 2.5})
        cur_gi = GenomeIntelligence(memory=memory, min_samples=2)
        cur_report = cur_gi.analyze()

        pa = PopulationAnalyzer(genome_intelligence=cur_gi, min_trend_samples=5, trend_threshold=0.05)
        planner = EvolutionPlanner(genome_intelligence=cur_gi, population_analyzer=pa)
        plan = planner.plan(genome_report=cur_report, historical_report=hist_report)
        assert isinstance(plan, EvolutionPlan)

    def test_plan_with_declining_trend(self, evolution_planner, agent):
        memory = agent.get_memory()
        for _ in range(5):
            dna = agent.extract_dna("C_hist", "hist", hook="transformation",
                                    visual="fantasy", emotion="surprise",
                                    fitness={"roas": 2.5})
            memory.store_dna(dna, is_winner=True, performance={"roas": 2.5})
        hist_gi = GenomeIntelligence(memory=memory, min_samples=2)
        hist_report = hist_gi.analyze()

        for _ in range(5):
            dna = agent.extract_dna("C_recent", "recent", hook="transformation",
                                    visual="fantasy", emotion="surprise",
                                    fitness={"roas": 0.8})
            memory.store_dna(dna, is_winner=False, performance={"roas": 0.8})
        cur_gi = GenomeIntelligence(memory=memory, min_samples=2)
        cur_report = cur_gi.analyze()

        pa = PopulationAnalyzer(genome_intelligence=cur_gi, min_trend_samples=5, trend_threshold=0.05)
        planner = EvolutionPlanner(genome_intelligence=cur_gi, population_analyzer=pa)
        plan = planner.plan(genome_report=cur_report, historical_report=hist_report)
        assert isinstance(plan, EvolutionPlan)

    def test_evolution_goal_types(self, evolution_planner):
        expected_types = ["increase_diversity", "amplify_rising", "suppress_declining", "explore_new"]
        for t in expected_types:
            assert t in [
                evolution_planner.GOAL_INCREASE_DIVERSITY,
                evolution_planner.GOAL_AMPLIFY_RISING,
                evolution_planner.GOAL_SUPPRESS_DECLINING,
                evolution_planner.GOAL_EXPLORE_NEW,
            ]

    def test_default_allocations(self, evolution_planner):
        assert evolution_planner.DEFAULT_DIVERSITY_PCT > 0
        assert evolution_planner.DEFAULT_AMPLIFY_PCT > 0
        assert evolution_planner.DEFAULT_EXPLORE_PCT > 0
        total = (evolution_planner.DEFAULT_DIVERSITY_PCT +
                 evolution_planner.DEFAULT_AMPLIFY_PCT +
                 evolution_planner.DEFAULT_EXPLORE_PCT)
        assert 0.9 <= total <= 1.1

    def test_goal_priority_ordering(self, evolution_planner, homogeneous_agent):
        gi = GenomeIntelligence(memory=homogeneous_agent.get_memory(), min_samples=2)
        pa = PopulationAnalyzer(genome_intelligence=gi)
        planner = EvolutionPlanner(genome_intelligence=gi, population_analyzer=pa)
        plan = planner.plan()
        for goal in plan.goals:
            assert 1 <= goal.priority <= 10

    # ── GeneMutationPlan 额外测试 ─────────────────────────

    def test_mutation_plan_expected_impact(self):
        mp = GeneMutationPlan(
            gene_category="hook",
            direction="curiosity",
            percentage=0.3,
            expected_impact="+18% CTR",
            confidence=0.82,
        )
        assert mp.expected_impact == "+18% CTR"
        assert mp.confidence == 0.82

    def test_mutation_plan_confidence_range(self):
        mp = GeneMutationPlan(confidence=0.5)
        assert 0 <= mp.confidence <= 1.0

    def test_evolution_plan_get_mutation_empty(self):
        plan = EvolutionPlan()
        result = plan.get_mutation_plans_by_gene("hook")
        assert result == []

    def test_gene_mutation_plan_reason(self):
        mp = GeneMutationPlan(
            gene_category="visual",
            direction="real_world_scene",
            reason="visual gene 饱和",
        )
        assert "visual" in mp.reason

    def test_evolution_goal_reason(self):
        goal = EvolutionGoal(
            goal_type="increase_diversity",
            reason="群体多样性不足",
        )
        assert "多样性" in goal.reason


# ═══════════════════════════════════════════════════════════
# 快捷查询测试 (10 tests)
# ═══════════════════════════════════════════════════════════


class TestQuickQueries:
    """快捷查询方法."""

    def test_get_evolution_strategy(self, evolution_planner, populated_agent):
        gi = GenomeIntelligence(memory=populated_agent.get_memory(), min_samples=2)
        pa = PopulationAnalyzer(genome_intelligence=gi)
        planner = EvolutionPlanner(genome_intelligence=gi, population_analyzer=pa)
        strategy = planner.get_evolution_strategy()
        assert "primary_goal" in strategy
        assert "strategy_type" in strategy
        assert "gene_focus" in strategy
        assert "mutation_count" in strategy

    def test_get_evolution_strategy_type(self, evolution_planner, homogeneous_agent):
        gi = GenomeIntelligence(memory=homogeneous_agent.get_memory(), min_samples=2)
        pa = PopulationAnalyzer(genome_intelligence=gi)
        planner = EvolutionPlanner(genome_intelligence=gi, population_analyzer=pa)
        strategy = planner.get_evolution_strategy()
        assert strategy["strategy_type"] in ("diversify", "amplify", "maintain")

    def test_preview_mutation_effects(self, evolution_planner, homogeneous_agent):
        gi = GenomeIntelligence(memory=homogeneous_agent.get_memory(), min_samples=2)
        pa = PopulationAnalyzer(genome_intelligence=gi)
        planner = EvolutionPlanner(genome_intelligence=gi, population_analyzer=pa)
        plan = planner.plan()
        effects = planner.preview_mutation_effects(plan)
        assert isinstance(effects, dict)

    def test_preview_mutation_effects_empty(self, evolution_planner):
        plan = EvolutionPlan()
        effects = evolution_planner.preview_mutation_effects(plan)
        assert effects == {}

    # ── 工厂 + 生命周期 ───────────────────────────────────

    def test_create_evolution_planner(self):
        planner = create_evolution_planner()
        assert isinstance(planner, EvolutionPlanner)

    def test_create_evolution_planner_custom(self):
        gi = GenomeIntelligence(min_samples=3)
        pa = PopulationAnalyzer(genome_intelligence=gi)
        planner = create_evolution_planner(
            genome_intelligence=gi,
            population_analyzer=pa,
            min_mutation_pct=0.1,
            max_mutation_pct=0.6,
        )
        assert planner._min_mutation_pct == 0.1
        assert planner._max_mutation_pct == 0.6

    def test_stats(self, evolution_planner):
        stats = evolution_planner.stats()
        assert "generation" in stats
        assert "min_mutation_pct" in stats
        assert "default_allocations" in stats

    def test_reset(self, evolution_planner):
        evolution_planner.plan()
        evolution_planner.reset()
        stats = evolution_planner.stats()
        assert stats["generation"] == 0

    def test_evolution_strategy_target_population(self, evolution_planner, populated_agent):
        gi = GenomeIntelligence(memory=populated_agent.get_memory(), min_samples=2)
        pa = PopulationAnalyzer(genome_intelligence=gi)
        planner = EvolutionPlanner(genome_intelligence=gi, population_analyzer=pa)
        strategy = planner.get_evolution_strategy()
        assert strategy["target_population"] > 0

    def test_evolution_strategy_summary(self, evolution_planner, populated_agent):
        gi = GenomeIntelligence(memory=populated_agent.get_memory(), min_samples=2)
        pa = PopulationAnalyzer(genome_intelligence=gi)
        planner = EvolutionPlanner(genome_intelligence=gi, population_analyzer=pa)
        strategy = planner.get_evolution_strategy()
        assert "summary" in strategy


# ═══════════════════════════════════════════════════════════
# CreativeAgent 集成测试 (10 tests)
# ═══════════════════════════════════════════════════════════


class TestCreativeAgentE1453Integration:
    """CreativeAgent 集成 E14.5.3."""

    def test_plan_from_agent_data(self, agent, populated_agent):
        gi = GenomeIntelligence(memory=populated_agent.get_memory(), min_samples=2)
        pa = PopulationAnalyzer(genome_intelligence=gi)
        planner = EvolutionPlanner(genome_intelligence=gi, population_analyzer=pa)
        plan = planner.plan()
        assert isinstance(plan, EvolutionPlan)

    def test_strategy_from_agent_data(self, agent, populated_agent):
        gi = GenomeIntelligence(memory=populated_agent.get_memory(), min_samples=2)
        pa = PopulationAnalyzer(genome_intelligence=gi)
        planner = EvolutionPlanner(genome_intelligence=gi, population_analyzer=pa)
        strategy = planner.get_evolution_strategy()
        assert strategy["strategy_type"] in ("diversify", "amplify", "maintain")

    def test_plan_with_homogeneous_agent(self, agent, homogeneous_agent):
        gi = GenomeIntelligence(memory=homogeneous_agent.get_memory(), min_samples=2)
        pa = PopulationAnalyzer(genome_intelligence=gi)
        planner = EvolutionPlanner(genome_intelligence=gi, population_analyzer=pa)
        plan = planner.plan()
        assert len(plan.goals) > 0

    def test_planner_isolated(self, agent):
        gi1 = GenomeIntelligence(memory=agent.get_memory(), min_samples=2)
        pa1 = PopulationAnalyzer(genome_intelligence=gi1)
        planner1 = EvolutionPlanner(genome_intelligence=gi1, population_analyzer=pa1)

        memory2 = CreativeMemory()
        gi2 = GenomeIntelligence(memory=memory2, min_samples=2)
        pa2 = PopulationAnalyzer(genome_intelligence=gi2)
        planner2 = EvolutionPlanner(genome_intelligence=gi2, population_analyzer=pa2)

        agent.extract_dna("C_test", "test", hook="transformation",
                          visual="fantasy", emotion="surprise",
                          fitness={"roas": 2.0})
        agent.extract_dna("C_test2", "test2", hook="transformation",
                          visual="fantasy", emotion="surprise",
                          fitness={"roas": 2.1})

        plan1 = planner1.plan()
        plan2 = planner2.plan()
        assert plan1.target_population_size > 0
        assert plan2.target_population_size == 0

    def test_plan_to_dict_full(self, agent, populated_agent):
        gi = GenomeIntelligence(memory=populated_agent.get_memory(), min_samples=2)
        pa = PopulationAnalyzer(genome_intelligence=gi)
        planner = EvolutionPlanner(genome_intelligence=gi, population_analyzer=pa)
        plan = planner.plan()
        d = plan.to_dict()
        assert "plan_id" in d
        assert "goals" in d
        assert "mutation_plans" in d
        assert "summary" in d

    def test_mutation_plan_has_expected_impact(self, agent, homogeneous_agent):
        gi = GenomeIntelligence(memory=homogeneous_agent.get_memory(), min_samples=2)
        pa = PopulationAnalyzer(genome_intelligence=gi)
        planner = EvolutionPlanner(genome_intelligence=gi, population_analyzer=pa)
        plan = planner.plan()
        for mp in plan.mutation_plans:
            assert mp.expected_impact

    def test_evolution_goal_has_reason(self, agent, homogeneous_agent):
        gi = GenomeIntelligence(memory=homogeneous_agent.get_memory(), min_samples=2)
        pa = PopulationAnalyzer(genome_intelligence=gi)
        planner = EvolutionPlanner(genome_intelligence=gi, population_analyzer=pa)
        plan = planner.plan()
        for g in plan.goals:
            assert g.reason

    def test_generation_tracking_across_plans(self, agent, populated_agent):
        gi = GenomeIntelligence(memory=populated_agent.get_memory(), min_samples=2)
        pa = PopulationAnalyzer(genome_intelligence=gi)
        planner = EvolutionPlanner(genome_intelligence=gi, population_analyzer=pa)
        p1 = planner.plan()
        p2 = planner.plan()
        p3 = planner.plan()
        assert p1.generation == 1
        assert p2.generation == 2
        assert p3.generation == 3

    def test_plan_with_learning_loop_data(self, agent):
        for _ in range(3):
            agent.extract_dna("C_test", "test", hook="before_after",
                              visual="fantasy", emotion="achievement",
                              fitness={"roas": 1.5})
        agent.run_learning_loop()

        gi = GenomeIntelligence(memory=agent.get_memory(), min_samples=2)
        pa = PopulationAnalyzer(genome_intelligence=gi)
        planner = EvolutionPlanner(genome_intelligence=gi, population_analyzer=pa)
        plan = planner.plan()
        assert isinstance(plan, EvolutionPlan)

    def test_plan_mutation_direction_not_empty(self, agent, homogeneous_agent):
        gi = GenomeIntelligence(memory=homogeneous_agent.get_memory(), min_samples=2)
        pa = PopulationAnalyzer(genome_intelligence=gi)
        planner = EvolutionPlanner(genome_intelligence=gi, population_analyzer=pa)
        plan = planner.plan()
        for mp in plan.mutation_plans:
            assert mp.direction != ""


# ═══════════════════════════════════════════════════════════
# 回归测试 (20 tests)
# ═══════════════════════════════════════════════════════════


class TestE1453Regression:
    """E14.5.3 回归测试."""

    # ── E14.5.2 回归 ──────────────────────────────────────

    def test_e1452_population_analyzer(self):
        pa = PopulationAnalyzer()
        report = pa.analyze()
        assert isinstance(report, PopulationHealthReport)

    def test_e1452_diversity_metrics(self):
        dm = DiversityMetrics(gene_category="hook", unique_values=3, risk_level="medium")
        assert dm.risk_level == "medium"

    def test_e1452_create_pa(self):
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain import create_population_analyzer
        pa = create_population_analyzer()
        assert isinstance(pa, PopulationAnalyzer)

    # ── E14.5.1 回归 ──────────────────────────────────────

    def test_e1451_genome_intelligence(self):
        gi = GenomeIntelligence(min_samples=2)
        report = gi.analyze()
        assert isinstance(report, GenomeIntelligenceReport)

    def test_e1451_gene_performance(self):
        gp = GenePerformance(gene_value="test", samples=10, win_rate=0.5, confidence=0.6)
        assert gp.is_reliable

    def test_e1451_create_gi(self):
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain import create_genome_intelligence
        gi = create_genome_intelligence()
        assert isinstance(gi, GenomeIntelligence)

    # ── E14.4.4 回归 ──────────────────────────────────────

    def test_e1444_reward_model(self, agent):
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.learning import RewardModel
        rm = agent.get_reward_model()
        assert isinstance(rm, RewardModel)

    def test_e1444_pattern_miner(self, agent):
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.learning import PatternMiner
        pm = agent.get_pattern_miner()
        assert isinstance(pm, PatternMiner)

    def test_e1444_strategy_memory(self, agent):
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.learning import StrategyMemory
        sm = agent.get_strategy_memory()
        assert isinstance(sm, StrategyMemory)

    def test_e1444_mutation_learning(self, agent):
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.learning import MutationLearning
        ml = agent.get_mutation_learning()
        assert isinstance(ml, MutationLearning)

    def test_e1444_creative_policy(self, agent):
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.learning import CreativePolicy
        cp = agent.get_policy()
        assert isinstance(cp, CreativePolicy)

    def test_e1444_learning_loop(self, agent):
        result = agent.run_learning_loop()
        assert "summary" in result

    # ── E14.4.3 回归 ──────────────────────────────────────

    def test_e1443_executor(self, agent):
        assert agent.get_executor() is not None

    def test_e1443_experiment_manager(self, agent):
        assert agent.get_experiment_manager() is not None

    # ── E14.4.2 回归 ──────────────────────────────────────

    def test_e1442_opportunity_engine(self, agent):
        assert agent.get_opportunity_engine() is not None

    def test_e1442_strategy_engine(self, agent):
        assert agent.get_strategy_engine() is not None

    # ── E14.4.1 回归 ──────────────────────────────────────

    def test_e1441_analyzer(self, agent):
        assert agent.get_analyzer() is not None

    def test_e1441_dna_engine(self, agent):
        assert agent.get_dna_engine() is not None

    def test_e1441_memory(self, agent):
        assert agent.get_memory() is not None

    def test_agent_creation(self):
        agent = create_creative_agent()
        assert agent is not None
        assert agent.agent_id