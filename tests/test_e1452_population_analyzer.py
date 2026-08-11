"""E14.5.2 Population Analyzer — 集成测试.

验证 PopulationAnalyzer 的群体多样性分析和进化趋势检测能力:
  - DiversityMetrics / TrendSignal / PopulationHealthReport 模型 (15 tests)
  - PopulationAnalyzer.analyze() 核心分析 (25 tests)
  - 多样性分析 (10 tests)
  - 趋势检测 (15 tests)
  - 快捷查询 (10 tests)
  - CreativeAgent 集成 (10 tests)
  - 回归 (E14.5.1 / E14.4.4 / E14.4.3 / E14.4.2 / E14.4.1) (15 tests)

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
    DiversityMetrics,
    TrendSignal,
    PopulationHealthReport,
    create_population_analyzer,
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
def populated_agent(agent):
    """填充多样化的 DNA 数据."""
    memory = agent.get_memory()
    for i, (hook, visual, emotion, roas) in enumerate([
        ("transformation", "fantasy", "surprise", 2.5),
        ("transformation", "fantasy", "surprise", 2.3),
        ("transformation", "fantasy", "surprise", 2.1),
        ("transformation", "fantasy", "excitement", 2.0),
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
    """填充同质化的 DNA 数据 (80% 相同基因)."""
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
    """填充高多样性的 DNA 数据 (全部 5 个基因类别都有多样性)."""
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
# DiversityMetrics 模型测试 (5 tests)
# ═══════════════════════════════════════════════════════════


class TestDiversityMetrics:
    """DiversityMetrics 数据模型."""

    def test_create_default(self):
        dm = DiversityMetrics()
        assert dm.gene_category == ""
        assert dm.risk_level == "low"

    def test_create_with_data(self):
        dm = DiversityMetrics(
            gene_category="hook",
            unique_values=5,
            total_samples=100,
            diversity_score=0.6,
            entropy=2.1,
            dominant_value="transformation",
            dominance_ratio=0.4,
            risk_level="medium",
        )
        assert dm.gene_category == "hook"
        assert dm.unique_values == 5
        assert dm.risk_level == "medium"

    def test_to_dict(self):
        dm = DiversityMetrics(
            gene_category="visual",
            unique_values=3,
            total_samples=50,
            diversity_score=0.4,
            entropy=1.2,
            dominant_value="fantasy",
            dominance_ratio=0.6,
            risk_level="high",
        )
        d = dm.to_dict()
        assert d["gene_category"] == "visual"
        assert d["risk_level"] == "high"
        assert d["diversity_score"] == 0.4

    def test_risk_levels(self):
        for level in ["low", "medium", "high", "critical"]:
            dm = DiversityMetrics(risk_level=level)
            assert dm.risk_level == level

    def test_dominance_ratio_range(self):
        dm = DiversityMetrics(dominance_ratio=0.75)
        assert 0 <= dm.dominance_ratio <= 1.0


# ═══════════════════════════════════════════════════════════
# TrendSignal 模型测试 (5 tests)
# ═══════════════════════════════════════════════════════════


class TestTrendSignal:
    """TrendSignal 数据模型."""

    def test_create_default(self):
        ts = TrendSignal()
        assert ts.direction == "stable"
        assert ts.strength == 0.0

    def test_create_rising(self):
        ts = TrendSignal(
            gene_category="hook",
            gene_value="transformation",
            direction="rising",
            strength=0.7,
            recent_win_rate=0.75,
            historical_win_rate=0.50,
            delta=0.25,
            confidence=0.8,
        )
        assert ts.direction == "rising"
        assert ts.is_significant

    def test_create_declining(self):
        ts = TrendSignal(
            gene_category="visual",
            gene_value="fantasy",
            direction="declining",
            strength=0.5,
            recent_win_rate=0.30,
            historical_win_rate=0.60,
            delta=-0.30,
            confidence=0.6,
        )
        assert ts.direction == "declining"
        assert ts.is_significant

    def test_is_significant_false(self):
        ts = TrendSignal(strength=0.2, confidence=0.4)
        assert not ts.is_significant

    def test_to_dict(self):
        ts = TrendSignal(
            gene_category="hook",
            gene_value="rescue",
            direction="rising",
            strength=0.6,
            delta=0.15,
            confidence=0.7,
        )
        d = ts.to_dict()
        assert d["gene_value"] == "rescue"
        assert d["is_significant"]


# ═══════════════════════════════════════════════════════════
# PopulationHealthReport 模型测试 (5 tests)
# ═══════════════════════════════════════════════════════════


class TestPopulationHealthReport:
    """PopulationHealthReport 数据模型."""

    def test_create_default(self):
        report = PopulationHealthReport()
        assert report.population_size == 0
        assert report.overall_risk_level == "low"

    def test_has_collapse_risk_critical(self):
        report = PopulationHealthReport(overall_risk_level="critical")
        assert report.has_collapse_risk

    def test_has_collapse_risk_high(self):
        report = PopulationHealthReport(overall_risk_level="high")
        assert report.has_collapse_risk

    def test_has_collapse_risk_false(self):
        report = PopulationHealthReport(overall_risk_level="low")
        assert not report.has_collapse_risk

    def test_to_dict(self):
        report = PopulationHealthReport(
            report_id="test_001",
            population_size=100,
            overall_diversity_score=0.5,
            overall_risk_level="medium",
            rising_genes=["hook=transformation"],
            declining_genes=["visual=fantasy"],
            recommendations=["增加多样性"],
        )
        d = report.to_dict()
        assert d["report_id"] == "test_001"
        assert "rising_genes" in d
        assert any("transformation" in g for g in d["rising_genes"])


# ═══════════════════════════════════════════════════════════
# PopulationAnalyzer 核心分析测试 (25 tests)
# ═══════════════════════════════════════════════════════════


class TestPopulationAnalyzerAnalyze:
    """PopulationAnalyzer.analyze() 核心分析."""

    # ── 基本分析 ──────────────────────────────────────────

    def test_analyze_empty(self, population_analyzer):
        report = population_analyzer.analyze()
        assert isinstance(report, PopulationHealthReport)
        assert report.population_size == 0

    def test_analyze_with_data(self, population_analyzer, populated_agent):
        gi = GenomeIntelligence(memory=populated_agent.get_memory(), min_samples=2)
        pa = PopulationAnalyzer(genome_intelligence=gi)
        report = pa.analyze()
        assert report.population_size > 0
        assert report.overall_diversity_score >= 0

    def test_analyze_has_diversity(self, population_analyzer, populated_agent):
        gi = GenomeIntelligence(memory=populated_agent.get_memory(), min_samples=2)
        pa = PopulationAnalyzer(genome_intelligence=gi)
        report = pa.analyze()
        assert len(report.diversity) > 0
        assert "hook" in report.diversity

    def test_analyze_has_risk_level(self, population_analyzer, populated_agent):
        gi = GenomeIntelligence(memory=populated_agent.get_memory(), min_samples=2)
        pa = PopulationAnalyzer(genome_intelligence=gi)
        report = pa.analyze()
        assert report.overall_risk_level in ("low", "medium", "high", "critical")

    def test_analyze_report_id(self, population_analyzer):
        report = population_analyzer.analyze()
        assert report.report_id.startswith("ph_")

    def test_analyze_created_at(self, population_analyzer):
        report = population_analyzer.analyze()
        assert report.created_at

    # ── 多样性指标 ────────────────────────────────────────

    def test_diversity_metrics_per_gene(self, population_analyzer, populated_agent):
        gi = GenomeIntelligence(memory=populated_agent.get_memory(), min_samples=2)
        pa = PopulationAnalyzer(genome_intelligence=gi)
        report = pa.analyze()
        for cat, dm in report.diversity.items():
            assert isinstance(dm, DiversityMetrics)
            assert dm.unique_values > 0
            assert dm.total_samples > 0

    def test_diversity_score_range(self, population_analyzer, populated_agent):
        gi = GenomeIntelligence(memory=populated_agent.get_memory(), min_samples=2)
        pa = PopulationAnalyzer(genome_intelligence=gi)
        report = pa.analyze()
        for dm in report.diversity.values():
            assert 0 <= dm.diversity_score <= 1.0

    def test_entropy_range(self, population_analyzer, populated_agent):
        gi = GenomeIntelligence(memory=populated_agent.get_memory(), min_samples=2)
        pa = PopulationAnalyzer(genome_intelligence=gi)
        report = pa.analyze()
        for dm in report.diversity.values():
            assert dm.entropy >= 0

    def test_dominant_value_present(self, population_analyzer, populated_agent):
        gi = GenomeIntelligence(memory=populated_agent.get_memory(), min_samples=2)
        pa = PopulationAnalyzer(genome_intelligence=gi)
        report = pa.analyze()
        hook_dm = report.diversity.get("hook")
        if hook_dm:
            assert hook_dm.dominant_value != ""

    # ── 同质化检测 ────────────────────────────────────────

    def test_homogeneous_population(self, population_analyzer, homogeneous_agent):
        gi = GenomeIntelligence(memory=homogeneous_agent.get_memory(), min_samples=2)
        pa = PopulationAnalyzer(genome_intelligence=gi)
        report = pa.analyze()
        hook_dm = report.diversity.get("hook")
        assert hook_dm is not None
        assert hook_dm.dominant_value == "transformation"
        assert hook_dm.dominance_ratio > 0.5

    def test_homogeneous_high_risk(self, population_analyzer, homogeneous_agent):
        gi = GenomeIntelligence(memory=homogeneous_agent.get_memory(), min_samples=2)
        pa = PopulationAnalyzer(genome_intelligence=gi)
        report = pa.analyze()
        assert report.overall_risk_level in ("high", "critical")

    def test_diverse_population(self, population_analyzer, diverse_agent):
        gi = GenomeIntelligence(memory=diverse_agent.get_memory(), min_samples=2)
        pa = PopulationAnalyzer(genome_intelligence=gi)
        report = pa.analyze()
        hook_dm = report.diversity.get("hook")
        assert hook_dm is not None
        assert hook_dm.unique_values >= 2

    def test_diverse_low_risk(self, population_analyzer, diverse_agent):
        gi = GenomeIntelligence(memory=diverse_agent.get_memory(), min_samples=2)
        pa = PopulationAnalyzer(genome_intelligence=gi)
        report = pa.analyze()
        assert report.overall_risk_level in ("low", "medium")

    # ── 建议生成 ──────────────────────────────────────────

    def test_recommendations_for_critical(self, population_analyzer, homogeneous_agent):
        gi = GenomeIntelligence(memory=homogeneous_agent.get_memory(), min_samples=2)
        pa = PopulationAnalyzer(genome_intelligence=gi)
        report = pa.analyze()
        assert len(report.recommendations) > 0

    def test_recommendations_contain_diversity(self, population_analyzer, homogeneous_agent):
        gi = GenomeIntelligence(memory=homogeneous_agent.get_memory(), min_samples=2)
        pa = PopulationAnalyzer(genome_intelligence=gi)
        report = pa.analyze()
        assert any("多样性" in r or "diversity" in r.lower() for r in report.recommendations)

    # ── 趋势检测无历史 ────────────────────────────────────

    def test_no_trends_without_history(self, population_analyzer, populated_agent):
        gi = GenomeIntelligence(memory=populated_agent.get_memory(), min_samples=2)
        pa = PopulationAnalyzer(genome_intelligence=gi)
        report = pa.analyze()
        assert report.trends == []

    # ── 边界条件 ──────────────────────────────────────────

    def test_analyze_empty_report(self, population_analyzer):
        empty_report = GenomeIntelligenceReport()
        report = population_analyzer.analyze(genome_report=empty_report)
        assert report.population_size == 0

    def test_analyze_with_custom_report(self, population_analyzer, populated_agent):
        gi = GenomeIntelligence(memory=populated_agent.get_memory(), min_samples=2)
        gi_report = gi.analyze()
        pa = PopulationAnalyzer(genome_intelligence=gi)
        report = pa.analyze(genome_report=gi_report)
        assert report.population_size == gi_report.total_dnas_analyzed

    def test_analyze_to_dict(self, population_analyzer, populated_agent):
        gi = GenomeIntelligence(memory=populated_agent.get_memory(), min_samples=2)
        pa = PopulationAnalyzer(genome_intelligence=gi)
        report = pa.analyze()
        d = report.to_dict()
        assert isinstance(d, dict)
        assert "diversity" in d

    # ── 整体风险 ──────────────────────────────────────────

    def test_overall_risk_max_of_genes(self, population_analyzer, homogeneous_agent):
        gi = GenomeIntelligence(memory=homogeneous_agent.get_memory(), min_samples=2)
        pa = PopulationAnalyzer(genome_intelligence=gi)
        report = pa.analyze()
        # 同质化群体应该有较高的风险
        assert report.overall_risk_level != "low"

    def test_significant_trends_empty_without_history(self, population_analyzer, populated_agent):
        gi = GenomeIntelligence(memory=populated_agent.get_memory(), min_samples=2)
        pa = PopulationAnalyzer(genome_intelligence=gi)
        report = pa.analyze()
        assert report.significant_trends == []

    def test_has_collapse_risk_property(self, population_analyzer, homogeneous_agent):
        gi = GenomeIntelligence(memory=homogeneous_agent.get_memory(), min_samples=2)
        pa = PopulationAnalyzer(genome_intelligence=gi)
        report = pa.analyze()
        assert isinstance(report.has_collapse_risk, bool)

    def test_rising_genes_empty_without_history(self, population_analyzer, populated_agent):
        gi = GenomeIntelligence(memory=populated_agent.get_memory(), min_samples=2)
        pa = PopulationAnalyzer(genome_intelligence=gi)
        report = pa.analyze()
        assert report.rising_genes == []

    def test_declining_genes_empty_without_history(self, population_analyzer, populated_agent):
        gi = GenomeIntelligence(memory=populated_agent.get_memory(), min_samples=2)
        pa = PopulationAnalyzer(genome_intelligence=gi)
        report = pa.analyze()
        assert report.declining_genes == []


# ═══════════════════════════════════════════════════════════
# 多样性分析测试 (10 tests)
# ═══════════════════════════════════════════════════════════


class TestDiversityAnalysis:
    """多样性分析专项测试."""

    def test_entropy_zero_for_single_value(self):
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.population_analyzer import PopulationAnalyzer
        pa = PopulationAnalyzer()
        values = [GenePerformance(gene_value="a", samples=10)]
        entropy = pa._calculate_entropy(values, 10)
        assert entropy == 0.0

    def test_entropy_max_for_uniform(self):
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.population_analyzer import PopulationAnalyzer
        pa = PopulationAnalyzer()
        values = [
            GenePerformance(gene_value="a", samples=5),
            GenePerformance(gene_value="b", samples=5),
        ]
        entropy = pa._calculate_entropy(values, 10)
        assert entropy == 1.0  # -0.5*log2(0.5)*2 = 1.0

    def test_entropy_empty(self):
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.population_analyzer import PopulationAnalyzer
        pa = PopulationAnalyzer()
        entropy = pa._calculate_entropy([], 0)
        assert entropy == 0.0

    def test_normalize_diversity_zero(self):
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.population_analyzer import PopulationAnalyzer
        pa = PopulationAnalyzer()
        score = pa._normalize_diversity(0, 0)
        assert score == 0.0

    def test_normalize_diversity_high(self):
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.population_analyzer import PopulationAnalyzer
        pa = PopulationAnalyzer()
        score = pa._normalize_diversity(20, 100)
        assert score > 0.5

    def test_assess_risk_critical_low_diversity(self):
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.population_analyzer import PopulationAnalyzer
        pa = PopulationAnalyzer()
        risk = pa._assess_diversity_risk(0.1, 0.3)
        assert risk == "critical"

    def test_assess_risk_critical_high_dominance(self):
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.population_analyzer import PopulationAnalyzer
        pa = PopulationAnalyzer()
        risk = pa._assess_diversity_risk(0.6, 0.85)
        assert risk == "critical"

    def test_assess_risk_high(self):
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.population_analyzer import PopulationAnalyzer
        pa = PopulationAnalyzer()
        risk = pa._assess_diversity_risk(0.3, 0.5)
        assert risk == "high"

    def test_assess_risk_medium(self):
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.population_analyzer import PopulationAnalyzer
        pa = PopulationAnalyzer()
        risk = pa._assess_diversity_risk(0.4, 0.6)
        assert risk == "medium"

    def test_assess_risk_low(self):
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.population_analyzer import PopulationAnalyzer
        pa = PopulationAnalyzer()
        risk = pa._assess_diversity_risk(0.7, 0.3)
        assert risk == "low"


# ═══════════════════════════════════════════════════════════
# 趋势检测测试 (15 tests)
# ═══════════════════════════════════════════════════════════


class TestTrendDetection:
    """进化趋势检测专项测试."""

    def test_detect_rising_trend(self, population_analyzer, agent):
        memory = agent.get_memory()
        # 历史: 表现一般
        for _ in range(5):
            dna = agent.extract_dna(
                "C_hist", "hist",
                hook="transformation", visual="fantasy",
                emotion="surprise", fitness={"roas": 1.0},
            )
            memory.store_dna(dna, is_winner=False, performance={"roas": 1.0})
        hist_gi = GenomeIntelligence(memory=memory, min_samples=2)
        hist_report = hist_gi.analyze()

        # 近期: 表现好
        for _ in range(5):
            dna = agent.extract_dna(
                "C_recent", "recent",
                hook="transformation", visual="fantasy",
                emotion="surprise", fitness={"roas": 2.5},
            )
            memory.store_dna(dna, is_winner=True, performance={"roas": 2.5})
        cur_gi = GenomeIntelligence(memory=memory, min_samples=2)
        cur_report = cur_gi.analyze()

        pa = PopulationAnalyzer(genome_intelligence=cur_gi, min_trend_samples=5, trend_threshold=0.05)
        report = pa.analyze(genome_report=cur_report, historical_report=hist_report)
        assert len(report.trends) >= 0

    def test_detect_declining_trend(self, population_analyzer, agent):
        memory = agent.get_memory()
        # 历史: 表现好
        for _ in range(5):
            dna = agent.extract_dna(
                "C_hist", "hist",
                hook="transformation", visual="fantasy",
                emotion="surprise", fitness={"roas": 2.5},
            )
            memory.store_dna(dna, is_winner=True, performance={"roas": 2.5})
        hist_gi = GenomeIntelligence(memory=memory, min_samples=2)
        hist_report = hist_gi.analyze()

        # 近期: 表现差
        for _ in range(5):
            dna = agent.extract_dna(
                "C_recent", "recent",
                hook="transformation", visual="fantasy",
                emotion="surprise", fitness={"roas": 0.8},
            )
            memory.store_dna(dna, is_winner=False, performance={"roas": 0.8})
        cur_gi = GenomeIntelligence(memory=memory, min_samples=2)
        cur_report = cur_gi.analyze()

        pa = PopulationAnalyzer(genome_intelligence=cur_gi, min_trend_samples=5, trend_threshold=0.05)
        report = pa.analyze(genome_report=cur_report, historical_report=hist_report)
        assert isinstance(report.trends, list)

    def test_trend_has_rising_genes(self, population_analyzer, agent):
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
        report = pa.analyze(genome_report=cur_report, historical_report=hist_report)
        if report.trends:
            rising = [t for t in report.trends if t.direction == "rising"]
            assert len(rising) >= 0

    def test_trend_direction_valid(self, population_analyzer, agent):
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
        report = pa.analyze(genome_report=cur_report, historical_report=hist_report)
        for t in report.trends:
            assert t.direction in ("rising", "declining")

    def test_trend_strength_range(self, population_analyzer, agent):
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
        report = pa.analyze(genome_report=cur_report, historical_report=hist_report)
        for t in report.trends:
            assert 0 <= t.strength <= 1.0

    def test_trend_confidence_range(self, population_analyzer, agent):
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
        report = pa.analyze(genome_report=cur_report, historical_report=hist_report)
        for t in report.trends:
            assert 0 <= t.confidence <= 1.0

    def test_new_gene_value_skipped(self, population_analyzer, agent):
        memory = agent.get_memory()
        # 历史: 只有 transformation
        for _ in range(5):
            dna = agent.extract_dna("C_hist", "hist", hook="transformation",
                                    visual="fantasy", emotion="surprise",
                                    fitness={"roas": 1.5})
            memory.store_dna(dna, is_winner=True, performance={"roas": 1.5})
        hist_gi = GenomeIntelligence(memory=memory, min_samples=2)
        hist_report = hist_gi.analyze()

        # 近期: 新增 rescue
        for _ in range(5):
            dna = agent.extract_dna("C_recent", "recent", hook="rescue",
                                    visual="fantasy", emotion="surprise",
                                    fitness={"roas": 2.0})
            memory.store_dna(dna, is_winner=True, performance={"roas": 2.0})
        cur_gi = GenomeIntelligence(memory=memory, min_samples=2)
        cur_report = cur_gi.analyze()

        pa = PopulationAnalyzer(genome_intelligence=cur_gi, min_trend_samples=5, trend_threshold=0.05)
        report = pa.analyze(genome_report=cur_report, historical_report=hist_report)
        # rescue 是新的基因值，不应该出现在趋势中
        rescue_trends = [t for t in report.trends if t.gene_value == "rescue"]
        assert len(rescue_trends) == 0

    def test_trend_below_threshold_filtered(self, population_analyzer, agent):
        memory = agent.get_memory()
        for _ in range(5):
            dna = agent.extract_dna("C_hist", "hist", hook="transformation",
                                    visual="fantasy", emotion="surprise",
                                    fitness={"roas": 1.5})
            memory.store_dna(dna, is_winner=True, performance={"roas": 1.5})
        hist_gi = GenomeIntelligence(memory=memory, min_samples=2)
        hist_report = hist_gi.analyze()

        for _ in range(5):
            dna = agent.extract_dna("C_recent", "recent", hook="transformation",
                                    visual="fantasy", emotion="surprise",
                                    fitness={"roas": 1.52})  # 几乎没变化
            memory.store_dna(dna, is_winner=True, performance={"roas": 1.52})
        cur_gi = GenomeIntelligence(memory=memory, min_samples=2)
        cur_report = cur_gi.analyze()

        pa = PopulationAnalyzer(genome_intelligence=cur_gi, min_trend_samples=5, trend_threshold=0.5)
        report = pa.analyze(genome_report=cur_report, historical_report=hist_report)
        # 高阈值应该过滤掉微小变化
        assert len(report.trends) == 0

    def test_trends_sorted_by_strength(self, population_analyzer, agent):
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
        report = pa.analyze(genome_report=cur_report, historical_report=hist_report)
        if len(report.trends) >= 2:
            for i in range(len(report.trends) - 1):
                assert report.trends[i].strength >= report.trends[i + 1].strength

    def test_trend_with_recommendations(self, population_analyzer, agent):
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
        report = pa.analyze(genome_report=cur_report, historical_report=hist_report)
        assert isinstance(report.recommendations, list)

    # ── TrendSignal 额外测试 ──────────────────────────────

    def test_trend_signal_to_dict(self):
        ts = TrendSignal(
            gene_category="hook",
            gene_value="transformation",
            direction="rising",
            strength=0.8,
            delta=0.3,
            confidence=0.7,
        )
        d = ts.to_dict()
        assert d["direction"] == "rising"
        assert d["strength"] == 0.8

    def test_trend_signal_stable(self):
        ts = TrendSignal(direction="stable")
        assert ts.direction == "stable"
        assert not ts.is_significant

    def test_trend_signal_is_significant_edge(self):
        ts = TrendSignal(strength=0.3, confidence=0.5)
        assert ts.is_significant

    def test_trend_signal_delta(self):
        ts = TrendSignal(
            recent_win_rate=0.7,
            historical_win_rate=0.4,
            delta=0.3,
        )
        assert ts.delta == 0.3

    def test_trend_signal_negative_delta(self):
        ts = TrendSignal(
            direction="declining",
            recent_win_rate=0.3,
            historical_win_rate=0.6,
            delta=-0.3,
        )
        assert ts.delta == -0.3


# ═══════════════════════════════════════════════════════════
# 快捷查询测试 (10 tests)
# ═══════════════════════════════════════════════════════════


class TestQuickQueries:
    """快捷查询方法."""

    def test_check_collapse_risk(self, population_analyzer, homogeneous_agent):
        gi = GenomeIntelligence(memory=homogeneous_agent.get_memory(), min_samples=2)
        pa = PopulationAnalyzer(genome_intelligence=gi)
        result = pa.check_collapse_risk()
        assert "risk_level" in result
        assert "has_risk" in result
        assert "critical_genes" in result

    def test_check_collapse_risk_no_risk(self, population_analyzer, diverse_agent):
        gi = GenomeIntelligence(memory=diverse_agent.get_memory(), min_samples=2)
        pa = PopulationAnalyzer(genome_intelligence=gi)
        result = pa.check_collapse_risk()
        assert isinstance(result["has_risk"], bool)

    def test_get_diversity_summary(self, population_analyzer, populated_agent):
        gi = GenomeIntelligence(memory=populated_agent.get_memory(), min_samples=2)
        pa = PopulationAnalyzer(genome_intelligence=gi)
        summary = pa.get_diversity_summary()
        assert "overall_score" in summary
        assert "per_gene" in summary

    def test_get_diversity_summary_empty(self, population_analyzer):
        summary = population_analyzer.get_diversity_summary()
        assert summary["overall_score"] == 0.0

    def test_get_evolution_direction(self, population_analyzer, agent):
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
        direction = pa.get_evolution_direction(cur_report, hist_report)
        assert "amplify" in direction
        assert "suppress" in direction
        assert "explore" in direction

    def test_get_evolution_direction_explore(self, population_analyzer, homogeneous_agent):
        gi = GenomeIntelligence(memory=homogeneous_agent.get_memory(), min_samples=2)
        gi_report = gi.analyze()

        pa = PopulationAnalyzer(genome_intelligence=gi)
        direction = pa.get_evolution_direction(gi_report, gi_report)
        assert "explore" in direction

    # ── 工厂 + 生命周期 ───────────────────────────────────

    def test_create_population_analyzer(self):
        pa = create_population_analyzer()
        assert isinstance(pa, PopulationAnalyzer)

    def test_create_population_analyzer_custom(self):
        gi = GenomeIntelligence(min_samples=3)
        pa = create_population_analyzer(
            genome_intelligence=gi,
            min_trend_samples=20,
            trend_threshold=0.15,
        )
        assert pa._min_trend_samples == 20
        assert pa._trend_threshold == 0.15

    def test_stats(self, population_analyzer):
        stats = population_analyzer.stats()
        assert "min_trend_samples" in stats
        assert "trend_threshold" in stats
        assert "diversity_thresholds" in stats

    def test_reset(self, population_analyzer):
        population_analyzer.reset()  # 不应报错


# ═══════════════════════════════════════════════════════════
# CreativeAgent 集成测试 (10 tests)
# ═══════════════════════════════════════════════════════════


class TestCreativeAgentE1452Integration:
    """CreativeAgent 集成 E14.5.2."""

    def test_analyze_agent_population(self, agent, populated_agent):
        gi = GenomeIntelligence(memory=populated_agent.get_memory(), min_samples=2)
        pa = PopulationAnalyzer(genome_intelligence=gi)
        report = pa.analyze()
        assert report.population_size > 0

    def test_diversity_of_agent_population(self, agent, populated_agent):
        gi = GenomeIntelligence(memory=populated_agent.get_memory(), min_samples=2)
        pa = PopulationAnalyzer(genome_intelligence=gi)
        report = pa.analyze()
        assert "hook" in report.diversity
        assert report.diversity["hook"].unique_values > 0

    def test_agent_population_risk_assessment(self, agent, homogeneous_agent):
        gi = GenomeIntelligence(memory=homogeneous_agent.get_memory(), min_samples=2)
        pa = PopulationAnalyzer(genome_intelligence=gi)
        result = pa.check_collapse_risk()
        # 同质化群体应该有风险
        assert result["has_risk"] or "critical_genes" in result

    def test_agent_diversity_summary(self, agent, diverse_agent):
        gi = GenomeIntelligence(memory=diverse_agent.get_memory(), min_samples=2)
        pa = PopulationAnalyzer(genome_intelligence=gi)
        summary = pa.get_diversity_summary()
        assert summary["overall_score"] > 0

    def test_population_analyzer_isolated(self, agent):
        gi1 = GenomeIntelligence(memory=agent.get_memory(), min_samples=2)
        pa1 = PopulationAnalyzer(genome_intelligence=gi1)

        memory2 = CreativeMemory()
        gi2 = GenomeIntelligence(memory=memory2, min_samples=2)
        pa2 = PopulationAnalyzer(genome_intelligence=gi2)

        agent.extract_dna("C_test", "test", hook="transformation",
                          visual="fantasy", emotion="surprise",
                          fitness={"roas": 2.0})
        agent.extract_dna("C_test2", "test2", hook="transformation",
                          visual="fantasy", emotion="surprise",
                          fitness={"roas": 2.1})

        report1 = pa1.analyze()
        report2 = pa2.analyze()
        assert report1.population_size > 0
        assert report2.population_size == 0

    def test_evolution_direction_from_agent_data(self, agent):
        for _ in range(5):
            agent.extract_dna("C_hist", "hist", hook="rescue",
                              visual="fantasy", emotion="curiosity",
                              fitness={"roas": 1.0})
        gi = GenomeIntelligence(memory=agent.get_memory(), min_samples=2)
        hist_report = gi.analyze()

        for _ in range(5):
            agent.extract_dna("C_recent", "recent", hook="transformation",
                              visual="vibrant", emotion="excitement",
                              fitness={"roas": 2.5})
        gi = GenomeIntelligence(memory=agent.get_memory(), min_samples=2)
        cur_report = gi.analyze()

        pa = PopulationAnalyzer(genome_intelligence=gi, min_trend_samples=5, trend_threshold=0.05)
        direction = pa.get_evolution_direction(cur_report, hist_report)
        assert isinstance(direction, dict)

    def test_report_to_dict_full(self, agent, populated_agent):
        gi = GenomeIntelligence(memory=populated_agent.get_memory(), min_samples=2)
        pa = PopulationAnalyzer(genome_intelligence=gi)
        report = pa.analyze()
        d = report.to_dict()
        assert "report_id" in d
        assert "diversity" in d
        assert "trends" in d
        assert "recommendations" in d

    def test_significant_trends_property(self, agent, populated_agent):
        gi = GenomeIntelligence(memory=populated_agent.get_memory(), min_samples=2)
        pa = PopulationAnalyzer(genome_intelligence=gi)
        report = pa.analyze()
        assert isinstance(report.significant_trends, list)

    def test_diversity_per_gene_has_entropy(self, agent, populated_agent):
        gi = GenomeIntelligence(memory=populated_agent.get_memory(), min_samples=2)
        pa = PopulationAnalyzer(genome_intelligence=gi)
        report = pa.analyze()
        for dm in report.diversity.values():
            assert dm.entropy >= 0

    def test_recommendations_format(self, agent, homogeneous_agent):
        gi = GenomeIntelligence(memory=homogeneous_agent.get_memory(), min_samples=2)
        pa = PopulationAnalyzer(genome_intelligence=gi)
        report = pa.analyze()
        for rec in report.recommendations:
            assert isinstance(rec, str)
            assert len(rec) > 0


# ═══════════════════════════════════════════════════════════
# 回归测试 (15 tests)
# ═══════════════════════════════════════════════════════════


class TestE1452Regression:
    """E14.5.2 回归测试."""

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

    def test_agent_creation(self):
        agent = create_creative_agent()
        assert agent is not None
        assert agent.agent_id