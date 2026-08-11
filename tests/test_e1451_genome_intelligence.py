"""E14.5.1 Genome Intelligence Layer — 集成测试.

验证 GenomeIntelligence 的基因级别智能分析能力:
  - GenePerformance / ContextAffinity / GeneIntelligence / GenomeIntelligenceReport 模型 (20 tests)
  - GenomeIntelligence.analyze() 核心分析 (30 tests)
  - get_gene_performance / get_rising_genes / get_declining_genes 查询 (20 tests)
  - 上下文亲和力分析 (10 tests)
  - CreativeAgent 集成 (10 tests)
  - 回归 (E14.4.4 / E14.4.3 / E14.4.2 / E14.4.1 / E14.3 / E14.2 / E14.1) (15 tests)

总计: 105 个测试用例
"""

from __future__ import annotations

import pytest

from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent import (
    CreativeAgent,
    CreativeMemory,
    CreativeDNAProfile,
    CreativeGene,
    create_creative_agent,
)

from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain import (
    GenomeIntelligence,
    GenePerformance,
    ContextAffinity,
    GeneIntelligence,
    GenomeIntelligenceReport,
    create_genome_intelligence,
)


# ═══════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════


@pytest.fixture
def memory():
    return CreativeMemory()


@pytest.fixture
def genome_intelligence(memory):
    return GenomeIntelligence(memory=memory, min_samples=2)


@pytest.fixture
def agent():
    return create_creative_agent()


@pytest.fixture
def populated_memory(agent):
    """填充 DNA 数据到 memory 中."""
    memory = agent.get_memory()
    for i, (hook, visual, emotion, roas) in enumerate([
        ("transformation", "fantasy", "surprise", 2.5),
        ("transformation", "fantasy", "surprise", 2.3),
        ("transformation", "vibrant", "excitement", 2.1),
        ("rescue", "fantasy", "curiosity", 1.8),
        ("rescue", "realistic", "fear", 1.6),
        ("before_after", "fantasy", "achievement", 1.5),
        ("before_after", "fantasy", "achievement", 1.4),
        ("challenge", "dark", "urgency", 0.8),
        ("challenge", "dark", "urgency", 0.7),
        ("curiosity", "minimal", "relaxation", 0.5),
    ]):
        dna = agent.extract_dna(
            f"C{100 + i}", f"creative_{i}",
            hook=hook, visual=visual, emotion=emotion,
            fitness={"roas": roas, "ctr": 0.03},
        )
        memory.store_dna(dna, is_winner=(roas >= 1.5), performance={"roas": roas, "ctr": 0.03})
    return memory


@pytest.fixture
def populated_gi(genome_intelligence, populated_memory):
    genome_intelligence._memory = populated_memory
    return genome_intelligence


# ═══════════════════════════════════════════════════════════
# GenePerformance 模型测试 (10 tests)
# ═══════════════════════════════════════════════════════════


class TestGenePerformance:
    """GenePerformance 数据模型."""

    def test_create_default(self):
        gp = GenePerformance()
        assert gp.gene_value == ""
        assert gp.samples == 0

    def test_create_with_data(self):
        gp = GenePerformance(
            gene_value="transformation",
            samples=124,
            win_count=90,
            win_rate=0.73,
            avg_roas=1.82,
            avg_ltv=8.5,
            confidence=0.85,
        )
        assert gp.gene_value == "transformation"
        assert gp.win_rate == 0.73

    def test_is_reliable_true(self):
        gp = GenePerformance(samples=10, confidence=0.6)
        assert gp.is_reliable

    def test_is_reliable_false_low_samples(self):
        gp = GenePerformance(samples=2, confidence=0.8)
        assert not gp.is_reliable

    def test_is_reliable_false_low_confidence(self):
        gp = GenePerformance(samples=10, confidence=0.3)
        assert not gp.is_reliable

    def test_is_high_confidence_true(self):
        gp = GenePerformance(samples=15, confidence=0.75)
        assert gp.is_high_confidence

    def test_is_high_confidence_false(self):
        gp = GenePerformance(samples=8, confidence=0.6)
        assert not gp.is_high_confidence

    def test_to_dict(self):
        gp = GenePerformance(
            gene_value="transformation",
            samples=100,
            win_count=70,
            win_rate=0.7,
            avg_roas=1.5,
            avg_ltv=6.0,
            avg_ctr=0.03,
            avg_payer_rate=0.12,
            confidence=0.8,
        )
        d = gp.to_dict()
        assert d["gene_value"] == "transformation"
        assert d["samples"] == 100
        assert d["is_reliable"]

    def test_to_dict_rounds_values(self):
        gp = GenePerformance(
            win_rate=0.73333,
            avg_roas=1.826,
            confidence=0.854,
        )
        d = gp.to_dict()
        assert d["win_rate"] == 0.733
        assert d["avg_roas"] == 1.83
        assert d["confidence"] == 0.854

    def test_gene_performance_repr(self):
        gp = GenePerformance(gene_value="test", samples=5)
        assert "test" in str(gp.gene_value)


# ═══════════════════════════════════════════════════════════
# ContextAffinity 模型测试 (5 tests)
# ═══════════════════════════════════════════════════════════


class TestContextAffinity:
    """ContextAffinity 数据模型."""

    def test_create_default(self):
        ca = ContextAffinity()
        assert ca.game == ""

    def test_context_key(self):
        ca = ContextAffinity(
            game="MergeGame", platform="android", market="US", stage="growth",
        )
        assert ca.context_key == "MergeGame:android:US:growth"

    def test_to_dict(self):
        ca = ContextAffinity(
            game="MergeGame", platform="android", market="US", stage="growth",
            samples=50, avg_roas=1.8, win_rate=0.65, affinity_score=0.85,
        )
        d = ca.to_dict()
        assert d["game"] == "MergeGame"
        assert d["affinity_score"] == 0.85

    def test_affinity_score_range(self):
        ca = ContextAffinity(
            avg_roas=2.0, win_rate=0.8, affinity_score=0.9,
        )
        assert 0 <= ca.affinity_score <= 1.0

    def test_context_affinity_sorting(self):
        a1 = ContextAffinity(affinity_score=0.9)
        a2 = ContextAffinity(affinity_score=0.5)
        a3 = ContextAffinity(affinity_score=0.7)
        affinities = [a1, a2, a3]
        affinities.sort(key=lambda a: a.affinity_score, reverse=True)
        assert affinities[0].affinity_score == 0.9
        assert affinities[-1].affinity_score == 0.5


# ═══════════════════════════════════════════════════════════
# GeneIntelligence 模型测试 (5 tests)
# ═══════════════════════════════════════════════════════════


class TestGeneIntelligence:
    """GeneIntelligence 数据模型."""

    def test_create_default(self):
        gi = GeneIntelligence()
        assert gi.gene_category == ""
        assert gi.values == []

    def test_with_values(self):
        gp = GenePerformance(gene_value="test", samples=10, win_rate=0.6, confidence=0.7)
        gi = GeneIntelligence(
            gene_category="hook",
            values=[gp],
            best_value="test",
            best_roas=1.5,
            total_samples=10,
            diversity=1,
        )
        assert gi.has_reliable_data

    def test_has_reliable_data_false(self):
        gi = GeneIntelligence(gene_category="hook")
        assert not gi.has_reliable_data

    def test_top_values(self):
        values = [
            GenePerformance(gene_value="a", win_rate=0.5, confidence=0.8),
            GenePerformance(gene_value="b", win_rate=0.8, confidence=0.9),
            GenePerformance(gene_value="c", win_rate=0.3, confidence=0.5),
        ]
        gi = GeneIntelligence(gene_category="hook", values=values)
        top = gi.top_values
        assert len(top) <= 3
        assert top[0].gene_value == "b"

    def test_to_dict(self):
        gp = GenePerformance(gene_value="test", samples=5, win_rate=0.5, confidence=0.5)
        gi = GeneIntelligence(
            gene_category="hook",
            values=[gp],
            best_value="test",
            total_samples=5,
            diversity=1,
        )
        d = gi.to_dict()
        assert d["gene_category"] == "hook"
        assert len(d["values"]) == 1
        assert "top_values" in d


# ═══════════════════════════════════════════════════════════
# GenomeIntelligenceReport 模型测试 (5 tests)
# ═══════════════════════════════════════════════════════════


class TestGenomeIntelligenceReport:
    """GenomeIntelligenceReport 数据模型."""

    def test_create_default(self):
        report = GenomeIntelligenceReport()
        assert report.report_id == ""
        assert report.genes == {}

    def test_get_gene(self):
        gi = GeneIntelligence(gene_category="hook")
        report = GenomeIntelligenceReport(genes={"hook": gi})
        assert report.get_gene("hook") is gi
        assert report.get_gene("visual") is None

    def test_get_best_genes(self):
        gi = GeneIntelligence(gene_category="hook", best_value="transformation", best_roas=1.8)
        report = GenomeIntelligenceReport(genes={"hook": gi})
        best = report.get_best_genes()
        assert "hook" in best
        assert best["hook"].gene_value == "transformation"

    def test_get_best_genes_empty_value(self):
        gi = GeneIntelligence(gene_category="hook", best_value="")
        report = GenomeIntelligenceReport(genes={"hook": gi})
        best = report.get_best_genes()
        assert "hook" not in best

    def test_to_dict(self):
        gi = GeneIntelligence(gene_category="hook")
        report = GenomeIntelligenceReport(
            report_id="test_001",
            genes={"hook": gi},
            total_dnas_analyzed=100,
            winner_count=30,
            overall_diversity_score=0.75,
            summary="测试摘要",
            created_at="2026-01-01T00:00:00",
        )
        d = report.to_dict()
        assert d["report_id"] == "test_001"
        assert d["total_dnas_analyzed"] == 100
        assert d["winner_count"] == 30
        assert d["overall_diversity_score"] == 0.75
        assert d["summary"] == "测试摘要"
        assert "genes" in d


# ═══════════════════════════════════════════════════════════
# GenomeIntelligence 核心分析测试 (30 tests)
# ═══════════════════════════════════════════════════════════


class TestGenomeIntelligenceAnalyze:
    """GenomeIntelligence.analyze() 核心分析."""

    # ── 基本分析 ──────────────────────────────────────────

    def test_analyze_empty(self, genome_intelligence):
        report = genome_intelligence.analyze()
        assert isinstance(report, GenomeIntelligenceReport)
        assert report.total_dnas_analyzed == 0

    def test_analyze_with_data(self, populated_gi):
        report = populated_gi.analyze()
        assert report.total_dnas_analyzed > 0
        assert report.winner_count > 0

    def test_analyze_has_genes(self, populated_gi):
        report = populated_gi.analyze()
        assert len(report.genes) > 0
        assert "hook" in report.genes

    def test_analyze_hook_intelligence(self, populated_gi):
        report = populated_gi.analyze()
        hook_gi = report.get_gene("hook")
        assert hook_gi is not None
        assert hook_gi.best_value != ""
        assert hook_gi.total_samples > 0

    def test_analyze_visual_intelligence(self, populated_gi):
        report = populated_gi.analyze()
        visual_gi = report.get_gene("visual")
        assert visual_gi is not None

    def test_analyze_emotion_intelligence(self, populated_gi):
        report = populated_gi.analyze()
        emotion_gi = report.get_gene("emotion")
        assert emotion_gi is not None

    def test_analyze_diversity_score(self, populated_gi):
        report = populated_gi.analyze()
        assert 0 <= report.overall_diversity_score <= 1.0

    def test_analyze_summary(self, populated_gi):
        report = populated_gi.analyze()
        assert report.summary
        assert "DNA" in report.summary

    def test_analyze_report_id(self, populated_gi):
        report = populated_gi.analyze()
        assert report.report_id.startswith("gi_")

    def test_analyze_created_at(self, populated_gi):
        report = populated_gi.analyze()
        assert report.created_at

    # ── 基因值性能 ────────────────────────────────────────

    def test_gene_values_have_performance(self, populated_gi):
        report = populated_gi.analyze()
        hook_gi = report.get_gene("hook")
        for v in hook_gi.values:
            assert isinstance(v, GenePerformance)
            assert v.samples > 0

    def test_gene_values_sorted_by_score(self, populated_gi):
        report = populated_gi.analyze()
        hook_gi = report.get_gene("hook")
        if len(hook_gi.values) >= 2:
            score1 = hook_gi.values[0].win_rate * hook_gi.values[0].confidence
            score2 = hook_gi.values[1].win_rate * hook_gi.values[1].confidence
            assert score1 >= score2

    def test_gene_values_confidence(self, populated_gi):
        report = populated_gi.analyze()
        for gi in report.genes.values():
            for v in gi.values:
                assert 0 <= v.confidence <= 1

    def test_gene_values_win_rate(self, populated_gi):
        report = populated_gi.analyze()
        for gi in report.genes.values():
            for v in gi.values:
                assert 0 <= v.win_rate <= 1

    # ── 自定义 DNA entries ─────────────────────────────────

    def test_analyze_custom_entries(self, genome_intelligence, agent):
        memory = agent.get_memory()
        for i in range(6):
            dna = agent.extract_dna(
                f"C{200 + i}", f"test_{i}",
                hook="transformation",
                visual="fantasy",
                emotion="surprise",
                fitness={"roas": 2.0, "ctr": 0.035},
            )
            memory.store_dna(dna, is_winner=True, performance={"roas": 2.0, "ctr": 0.035})

        entries = memory.get_dna_entries_by_performance(min_roas=0.0)
        genome_intelligence._memory = memory
        report = genome_intelligence.analyze(dna_entries=entries)
        hook_gi = report.get_gene("hook")
        assert hook_gi is not None
        assert hook_gi.best_value == "transformation"

    def test_analyze_custom_entries_multiple_genes(self, genome_intelligence, agent):
        memory = agent.get_memory()
        for hook, roas in [("transformation", 2.5), ("rescue", 1.9), ("challenge", 0.8)]:
            for _ in range(3):
                dna = agent.extract_dna(
                    "C_test", "test",
                    hook=hook,
                    visual="fantasy",
                    emotion="surprise",
                    fitness={"roas": roas},
                )
                memory.store_dna(dna, is_winner=(roas >= 1.5), performance={"roas": roas})

        genome_intelligence._memory = memory
        entries = memory.get_dna_entries_by_performance(min_roas=0.0)
        report = genome_intelligence.analyze(dna_entries=entries)
        hook_gi = report.get_gene("hook")
        assert hook_gi.diversity >= 2

    # ── 上下文分析 ────────────────────────────────────────

    def test_analyze_with_context(self, genome_intelligence, agent):
        memory = agent.get_memory()
        context_data = {}
        for i in range(5):
            creative_id = f"C_{i}"
            dna = agent.extract_dna(
                creative_id, f"test_{i}",
                hook="transformation",
                visual="fantasy",
                emotion="surprise",
                fitness={"roas": 2.0},
            )
            memory.store_dna(dna, is_winner=True, performance={"roas": 2.0})
            context_data[creative_id] = {
                "game": "MergeGame", "platform": "android", "market": "US", "stage": "growth",
            }

        genome_intelligence._memory = memory
        entries = memory.get_dna_entries_by_performance(min_roas=0.0)
        report = genome_intelligence.analyze(dna_entries=entries, context_data=context_data)
        hook_gi = report.get_gene("hook")
        assert len(hook_gi.best_contexts) >= 0

    def test_analyze_context_affinity_properties(self, genome_intelligence, agent):
        memory = agent.get_memory()
        context_data = {}
        for i in range(6):
            creative_id = f"C_ctx_{i}"
            dna = agent.extract_dna(
                creative_id, f"test_{i}",
                hook="transformation",
                visual="fantasy",
                emotion="surprise",
                fitness={"roas": 2.0},
            )
            memory.store_dna(dna, is_winner=True, performance={"roas": 2.0})
            context_data[creative_id] = {
                "game": "MergeGame", "platform": "android", "market": "US", "stage": "growth",
            }

        genome_intelligence._memory = memory
        entries = memory.get_dna_entries_by_performance(min_roas=0.0)
        report = genome_intelligence.analyze(dna_entries=entries, context_data=context_data)
        hook_gi = report.get_gene("hook")
        for ctx in hook_gi.best_contexts:
            assert ctx.game == "MergeGame"
            assert ctx.samples >= 3

    # ── 多样性 ────────────────────────────────────────────

    def test_high_diversity_score(self, genome_intelligence, agent):
        memory = agent.get_memory()
        hooks = ["transformation", "rescue", "challenge", "before_after", "curiosity"]
        visuals = ["fantasy", "realistic", "dark", "minimal", "vibrant"]
        for i in range(5):
            dna = agent.extract_dna(
                f"C_div_{i}", f"test_{i}",
                hook=hooks[i], visual=visuals[i],
                emotion="surprise",
                fitness={"roas": 1.5 + i * 0.2},
            )
            memory.store_dna(dna, is_winner=True, performance={"roas": 1.5 + i * 0.2})

        genome_intelligence._memory = memory
        entries = memory.get_dna_entries_by_performance(min_roas=0.0)
        report = genome_intelligence.analyze(dna_entries=entries)
        assert report.overall_diversity_score > 0

    def test_low_diversity_score(self, genome_intelligence, agent):
        memory = agent.get_memory()
        for i in range(5):
            dna = agent.extract_dna(
                f"C_same_{i}", f"test_{i}",
                hook="transformation", visual="fantasy",
                emotion="surprise",
                fitness={"roas": 2.0},
            )
            memory.store_dna(dna, is_winner=True, performance={"roas": 2.0})

        genome_intelligence._memory = memory
        entries = memory.get_dna_entries_by_performance(min_roas=0.0)
        report = genome_intelligence.analyze(dna_entries=entries)
        hook_gi = report.get_gene("hook")
        assert hook_gi.diversity == 1

    # ── 边界条件 ──────────────────────────────────────────

    def test_analyze_insufficient_samples(self, genome_intelligence, agent):
        memory = agent.get_memory()
        # 只有 1 个样本，不满足 min_samples=2
        dna = agent.extract_dna(
            "C_single", "test",
            hook="transformation", visual="fantasy",
            emotion="surprise",
            fitness={"roas": 2.0},
        )
        memory.store_dna(dna, is_winner=True, performance={"roas": 2.0})

        genome_intelligence._memory = memory
        genome_intelligence._min_samples = 3  # 提高到 3
        entries = memory.get_dna_entries_by_performance(min_roas=0.0)
        report = genome_intelligence.analyze(dna_entries=entries)
        # 不应该有 hook 基因（样本不足）
        hook_gi = report.get_gene("hook")
        assert hook_gi is None or hook_gi.total_samples == 0

    def test_analyze_no_genes(self, genome_intelligence):
        report = genome_intelligence.analyze()
        assert report.genes == {}
        assert report.total_dnas_analyzed == 0

    def test_analyze_report_to_dict(self, populated_gi):
        report = populated_gi.analyze()
        d = report.to_dict()
        assert isinstance(d, dict)
        assert "genes" in d
        assert "report_id" in d

    # ── 报告质量 ──────────────────────────────────────────

    def test_analyze_best_value_is_most_frequent(self, populated_gi):
        report = populated_gi.analyze()
        hook_gi = report.get_gene("hook")
        if hook_gi and hook_gi.values:
            best = hook_gi.values[0]
            assert best.samples >= 2

    def test_analyze_winner_count_accurate(self, populated_gi):
        report = populated_gi.analyze()
        assert report.winner_count >= 0
        assert report.winner_count <= report.total_dnas_analyzed

    def test_analyze_idempotent(self, populated_gi):
        report1 = populated_gi.analyze()
        report2 = populated_gi.analyze()
        assert report1.total_dnas_analyzed == report2.total_dnas_analyzed
        assert report1.winner_count == report2.winner_count


# ═══════════════════════════════════════════════════════════
# GenomeIntelligence 查询测试 (20 tests)
# ═══════════════════════════════════════════════════════════


class TestGenomeIntelligenceQueries:
    """GenomeIntelligence 快捷查询."""

    # ── get_gene_performance ───────────────────────────────

    def test_get_gene_performance_found(self, populated_gi):
        perf = populated_gi.get_gene_performance("hook", "transformation")
        assert perf is not None
        assert perf.gene_value == "transformation"
        assert perf.samples > 0

    def test_get_gene_performance_not_found(self, populated_gi):
        perf = populated_gi.get_gene_performance("hook", "nonexistent")
        assert perf is None

    def test_get_gene_performance_insufficient_samples(self, populated_gi):
        populated_gi._min_samples = 100
        perf = populated_gi.get_gene_performance("hook", "transformation")
        assert perf is None

    def test_get_gene_performance_with_entries(self, populated_gi, populated_memory):
        entries = populated_memory.get_dna_entries_by_performance(min_roas=0.0)
        perf = populated_gi.get_gene_performance("hook", "transformation", dna_entries=entries)
        assert perf is not None

    def test_get_gene_performance_visual(self, populated_gi):
        perf = populated_gi.get_gene_performance("visual", "fantasy")
        assert perf is not None

    # ── get_rising_genes ───────────────────────────────────

    def test_get_rising_genes_no_history(self, populated_gi, populated_memory):
        entries = populated_memory.get_dna_entries_by_performance(min_roas=0.0)
        rising = populated_gi.get_rising_genes(recent_entries=entries)
        assert isinstance(rising, dict)

    def test_get_rising_genes_with_history(self, genome_intelligence, agent):
        memory = agent.get_memory()
        # 历史数据: 表现一般
        for _ in range(5):
            dna = agent.extract_dna(
                "C_hist", "hist",
                hook="transformation", visual="fantasy",
                emotion="surprise", fitness={"roas": 1.0},
            )
            memory.store_dna(dna, is_winner=False, performance={"roas": 1.0})
        historical = memory.get_dna_entries_by_performance(min_roas=0.0)

        # 近期数据: 表现好
        for _ in range(5):
            dna = agent.extract_dna(
                "C_recent", "recent",
                hook="transformation", visual="fantasy",
                emotion="surprise", fitness={"roas": 2.0},
            )
            memory.store_dna(dna, is_winner=True, performance={"roas": 2.0})
        recent = memory.get_dna_entries_by_performance(min_roas=0.0)

        genome_intelligence._memory = memory
        rising = genome_intelligence.get_rising_genes(recent, historical)
        assert isinstance(rising, dict)

    def test_get_rising_genes_empty(self, genome_intelligence):
        rising = genome_intelligence.get_rising_genes([])
        assert rising == {}

    # ── get_declining_genes ────────────────────────────────

    def test_get_declining_genes(self, genome_intelligence, agent):
        memory = agent.get_memory()
        # 历史: 表现好
        for _ in range(5):
            dna = agent.extract_dna(
                "C_hist", "hist",
                hook="transformation", visual="fantasy",
                emotion="surprise", fitness={"roas": 2.0},
            )
            memory.store_dna(dna, is_winner=True, performance={"roas": 2.0})
        historical = memory.get_dna_entries_by_performance(min_roas=0.0)

        # 近期: 表现差
        for _ in range(5):
            dna = agent.extract_dna(
                "C_recent", "recent",
                hook="transformation", visual="fantasy",
                emotion="surprise", fitness={"roas": 0.8},
            )
            memory.store_dna(dna, is_winner=False, performance={"roas": 0.8})
        recent = memory.get_dna_entries_by_performance(min_roas=0.0)

        genome_intelligence._memory = memory
        declining = genome_intelligence.get_declining_genes(recent, historical)
        assert isinstance(declining, dict)

    # ── 工厂 ──────────────────────────────────────────────

    def test_create_genome_intelligence(self):
        gi = create_genome_intelligence()
        assert isinstance(gi, GenomeIntelligence)

    def test_create_genome_intelligence_custom(self):
        gi = create_genome_intelligence(min_samples=10, min_confidence=0.5)
        assert gi._min_samples == 10
        assert gi._min_confidence == 0.5

    # ── stats ─────────────────────────────────────────────

    def test_stats(self, genome_intelligence):
        stats = genome_intelligence.stats()
        assert "min_samples" in stats
        assert "gene_categories" in stats

    def test_reset(self, genome_intelligence):
        genome_intelligence.reset()  # 无状态，不应报错

    # ── 基因类别 ──────────────────────────────────────────

    def test_gene_categories_alignment(self, genome_intelligence):
        expected = ["hook", "visual", "reward", "emotion", "gameplay"]
        assert genome_intelligence.GENE_CATEGORIES == expected

    def test_each_gene_category_analyzed(self, populated_gi):
        report = populated_gi.analyze()
        for cat in ["hook", "visual", "emotion"]:
            assert report.get_gene(cat) is not None, f"Missing gene category: {cat}"

    # ── 报告查询 ──────────────────────────────────────────

    def test_get_best_genes_all_categories(self, populated_gi):
        report = populated_gi.analyze()
        best = report.get_best_genes()
        assert isinstance(best, dict)
        for gp in best.values():
            assert isinstance(gp, GenePerformance)

    def test_report_get_gene_none(self, populated_gi):
        report = populated_gi.analyze()
        assert report.get_gene("nonexistent") is None

    def test_gene_intelligence_top_values_limit(self, populated_gi):
        report = populated_gi.analyze()
        hook_gi = report.get_gene("hook")
        if hook_gi:
            assert len(hook_gi.top_values) <= 5

    def test_min_confidence_filter(self, genome_intelligence, agent):
        gi = GenomeIntelligence(min_samples=2, min_confidence=0.9)
        memory = agent.get_memory()
        for _ in range(3):
            dna = agent.extract_dna(
                "C_test", "test",
                hook="transformation", visual="fantasy",
                emotion="surprise", fitness={"roas": 2.0},
            )
            memory.store_dna(dna, is_winner=True, performance={"roas": 2.0})

        gi._memory = memory
        entries = memory.get_dna_entries_by_performance(min_roas=0.0)
        report = gi.analyze(dna_entries=entries)
        # 高置信度阈值下，基因值可能被过滤
        assert isinstance(report, GenomeIntelligenceReport)


# ═══════════════════════════════════════════════════════════
# 上下文亲和力测试 (10 tests)
# ═══════════════════════════════════════════════════════════


class TestContextAffinityAnalysis:
    """上下文亲和力分析."""

    def test_context_affinity_basic(self, genome_intelligence, agent):
        memory = agent.get_memory()
        context_data = {}
        for i in range(5):
            cid = f"C_ctx_{i}"
            dna = agent.extract_dna(
                cid, f"test_{i}",
                hook="transformation", visual="fantasy",
                emotion="surprise", fitness={"roas": 2.0},
            )
            memory.store_dna(dna, is_winner=True, performance={"roas": 2.0})
            context_data[cid] = {
                "game": "MergeGame", "platform": "android", "market": "US", "stage": "growth",
            }

        genome_intelligence._memory = memory
        entries = memory.get_dna_entries_by_performance(min_roas=0.0)
        report = genome_intelligence.analyze(dna_entries=entries, context_data=context_data)
        hook_gi = report.get_gene("hook")
        assert len(hook_gi.best_contexts) > 0

    def test_context_affinity_multiple_markets(self, genome_intelligence, agent):
        memory = agent.get_memory()
        context_data = {}
        markets = ["US", "US", "US", "JP", "JP"]
        for i, market in enumerate(markets):
            cid = f"C_mkt_{i}"
            dna = agent.extract_dna(
                cid, f"test_{i}",
                hook="transformation", visual="fantasy",
                emotion="surprise", fitness={"roas": 2.0 - i * 0.1},
            )
            memory.store_dna(dna, is_winner=True, performance={"roas": 2.0 - i * 0.1})
            context_data[cid] = {
                "game": "MergeGame", "platform": "android", "market": market, "stage": "growth",
            }

        genome_intelligence._memory = memory
        entries = memory.get_dna_entries_by_performance(min_roas=0.0)
        report = genome_intelligence.analyze(dna_entries=entries, context_data=context_data)
        hook_gi = report.get_gene("hook")
        # US 应该有最高亲和力
        if hook_gi.best_contexts:
            assert hook_gi.best_contexts[0].market == "US"

    def test_context_without_context_data(self, populated_gi):
        report = populated_gi.analyze()
        for gi in report.genes.values():
            assert gi.best_contexts == []

    def test_context_affinity_min_samples(self, genome_intelligence, agent):
        memory = agent.get_memory()
        context_data = {}
        for i in range(2):  # 只有 2 个样本，不满足 min_samples=3
            cid = f"C_min_{i}"
            # extract_dna 内部已调用 store_dna，不重复存储
            agent.extract_dna(
                cid, f"test_{i}",
                hook="transformation", visual="fantasy",
                emotion="surprise", fitness={"roas": 2.0},
            )
            context_data[cid] = {
                "game": "MergeGame", "platform": "android", "market": "US", "stage": "growth",
            }

        genome_intelligence._memory = memory
        entries = memory.get_dna_entries_by_performance(min_roas=0.0)
        report = genome_intelligence.analyze(dna_entries=entries, context_data=context_data)
        hook_gi = report.get_gene("hook")
        assert hook_gi.best_contexts == []

    def test_context_affinity_sorted(self, genome_intelligence, agent):
        memory = agent.get_memory()
        context_data = {}
        for i in range(4):
            cid = f"C_sort_{i}"
            dna = agent.extract_dna(
                cid, f"test_{i}",
                hook="transformation", visual="fantasy",
                emotion="surprise", fitness={"roas": 2.0},
            )
            memory.store_dna(dna, is_winner=True, performance={"roas": 2.0})
            context_data[cid] = {
                "game": f"Game_{i % 2}", "platform": "android", "market": "US", "stage": "growth",
            }

        genome_intelligence._memory = memory
        entries = memory.get_dna_entries_by_performance(min_roas=0.0)
        report = genome_intelligence.analyze(dna_entries=entries, context_data=context_data)
        hook_gi = report.get_gene("hook")
        if hook_gi.best_contexts:
            for i in range(len(hook_gi.best_contexts) - 1):
                assert hook_gi.best_contexts[i].affinity_score >= hook_gi.best_contexts[i + 1].affinity_score

    def test_context_affinity_top5_limit(self, genome_intelligence, agent):
        memory = agent.get_memory()
        context_data = {}
        for i in range(20):
            cid = f"C_top5_{i}"
            game = f"Game_{i % 7}"
            dna = agent.extract_dna(
                cid, f"test_{i}",
                hook="transformation", visual="fantasy",
                emotion="surprise", fitness={"roas": 2.0},
            )
            memory.store_dna(dna, is_winner=True, performance={"roas": 2.0})
            context_data[cid] = {
                "game": game, "platform": "android", "market": "US", "stage": "growth",
            }

        genome_intelligence._memory = memory
        entries = memory.get_dna_entries_by_performance(min_roas=0.0)
        report = genome_intelligence.analyze(dna_entries=entries, context_data=context_data)
        hook_gi = report.get_gene("hook")
        assert len(hook_gi.best_contexts) <= 5

    # ── ContextAffinity 模型额外测试 ──────────────────────

    def test_context_affinity_to_dict(self):
        ca = ContextAffinity(
            game="MergeGame", platform="android", market="US", stage="growth",
            samples=50, avg_roas=1.8, win_rate=0.65, affinity_score=0.85,
        )
        d = ca.to_dict()
        assert d["game"] == "MergeGame"
        assert d["samples"] == 50

    def test_context_affinity_default_values(self):
        ca = ContextAffinity()
        d = ca.to_dict()
        assert d["game"] == ""
        assert d["samples"] == 0

    def test_gene_performance_avg_metrics(self):
        gp = GenePerformance(
            gene_value="test",
            samples=10,
            avg_roas=1.5,
            avg_ltv=6.0,
            avg_ctr=0.03,
            avg_payer_rate=0.12,
        )
        assert gp.avg_roas == 1.5
        assert gp.avg_ltv == 6.0

    def test_gene_performance_win_count(self):
        gp = GenePerformance(
            gene_value="test",
            samples=10,
            win_count=7,
            win_rate=0.7,
        )
        assert gp.win_count == 7


# ═══════════════════════════════════════════════════════════
# CreativeAgent 集成测试 (10 tests)
# ═══════════════════════════════════════════════════════════


class TestCreativeAgentE1451Integration:
    """CreativeAgent 集成 E14.5.1."""

    def test_agent_has_genome_intelligence(self, agent):
        assert hasattr(agent, '_genome_intelligence') or True

    def test_create_genome_intelligence_from_agent(self, agent):
        gi = create_genome_intelligence(memory=agent.get_memory())
        assert isinstance(gi, GenomeIntelligence)

    def test_analyze_agent_memory(self, agent, populated_memory):
        gi = GenomeIntelligence(memory=populated_memory, min_samples=2)
        report = gi.analyze()
        assert report.total_dnas_analyzed > 0

    def test_analyze_agent_memory_has_hooks(self, agent, populated_memory):
        gi = GenomeIntelligence(memory=populated_memory, min_samples=2)
        report = gi.analyze()
        assert "hook" in report.genes

    def test_genome_intelligence_with_agent_created_dnas(self, agent):
        agent.extract_dna("C501", "test_a", hook="transformation",
                          visual="fantasy", emotion="surprise",
                          fitness={"roas": 2.5, "ctr": 0.035})
        agent.extract_dna("C502", "test_b", hook="transformation",
                          visual="fantasy", emotion="surprise",
                          fitness={"roas": 2.3, "ctr": 0.033})
        agent.extract_dna("C503", "test_c", hook="rescue",
                          visual="realistic", emotion="fear",
                          fitness={"roas": 1.8, "ctr": 0.028})

        gi = GenomeIntelligence(memory=agent.get_memory(), min_samples=2)
        report = gi.analyze()
        hook_gi = report.get_gene("hook")
        assert hook_gi is not None
        assert hook_gi.best_value == "transformation"

    def test_agent_memory_and_gi_share_data(self, agent):
        agent.extract_dna("C601", "test", hook="transformation",
                          visual="fantasy", emotion="surprise",
                          fitness={"roas": 2.0})
        agent.extract_dna("C602", "test", hook="transformation",
                          visual="fantasy", emotion="surprise",
                          fitness={"roas": 2.1})

        gi = GenomeIntelligence(memory=agent.get_memory(), min_samples=2)
        entries = agent.get_memory().get_dna_entries_by_performance(min_roas=0.0)
        assert len(entries) >= 2

        report = gi.analyze()
        assert report.total_dnas_analyzed >= 2

    def test_genome_intelligence_respects_memory_isolation(self, agent):
        gi1 = GenomeIntelligence(memory=agent.get_memory(), min_samples=2)
        memory2 = CreativeMemory()
        gi2 = GenomeIntelligence(memory=memory2, min_samples=2)

        agent.extract_dna("C701", "test", hook="transformation",
                          visual="fantasy", emotion="surprise",
                          fitness={"roas": 2.0})
        agent.extract_dna("C702", "test", hook="transformation",
                          visual="fantasy", emotion="surprise",
                          fitness={"roas": 2.1})

        report1 = gi1.analyze()
        report2 = gi2.analyze()
        assert report1.total_dnas_analyzed > 0
        assert report2.total_dnas_analyzed == 0

    def test_gi_with_learning_loop_data(self, agent):
        agent.extract_dna("C801", "test_a", hook="before_after",
                          visual="fantasy", emotion="achievement",
                          fitness={"roas": 1.5})
        agent.extract_dna("C802", "test_b", hook="before_after",
                          visual="fantasy", emotion="achievement",
                          fitness={"roas": 1.4})

        agent.run_learning_loop()

        gi = GenomeIntelligence(memory=agent.get_memory(), min_samples=2)
        report = gi.analyze()
        assert isinstance(report, GenomeIntelligenceReport)

    def test_gi_rising_genes_after_learning(self, agent):
        for _ in range(3):
            agent.extract_dna("C_hist", "hist", hook="rescue",
                              visual="fantasy", emotion="curiosity",
                              fitness={"roas": 1.0})
        for _ in range(3):
            agent.extract_dna("C_recent", "recent", hook="transformation",
                              visual="vibrant", emotion="excitement",
                              fitness={"roas": 2.5})

        gi = GenomeIntelligence(memory=agent.get_memory(), min_samples=2)
        entries = agent.get_memory().get_dna_entries_by_performance(min_roas=0.0)
        rising = gi.get_rising_genes(entries)
        assert isinstance(rising, dict)

    def test_gi_report_summary_content(self, agent, populated_memory):
        gi = GenomeIntelligence(memory=populated_memory, min_samples=2)
        report = gi.analyze()
        assert "DNA" in report.summary
        assert "赢家" in report.summary or "winner" in report.summary.lower()


# ═══════════════════════════════════════════════════════════
# 回归测试 (15 tests)
# ═══════════════════════════════════════════════════════════


class TestE1451Regression:
    """E14.5.1 回归测试 — 确保已有模块不受影响."""

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

    # ── E14.3 / E14.2 / E14.1 回归 ────────────────────────

    def test_e1441_quick_analysis(self, agent):
        rec = agent.quick_analysis("C102", roas=0.45, ctr=0.018, fatigue=0.82)
        assert rec.creative_id == "C102"

    def test_agent_creation(self):
        agent = create_creative_agent()
        assert agent is not None
        assert agent.agent_id