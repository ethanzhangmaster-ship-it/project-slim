"""E14.5.5 Fitness Prediction Engine — 集成测试.

验证 FitnessPredictor 的预测试筛选能力:
  - FitnessPrediction / FitnessPredictionReport 模型 (10 tests)
  - FitnessPredictor.predict() 核心预测 (20 tests)
  - predict_batch / filter_by_threshold / rank_by_fitness (15 tests)
  - select_top_candidates (10 tests)
  - 阈值与置信度 (10 tests)
  - 查询与报告 (10 tests)
  - CreativeAgent 集成 (10 tests)
  - 回归 (E14.5.4 / E14.5.3 / E14.5.2 / E14.5.1 / E14.4.4) (15 tests)

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
    GenomeIntelligenceReport,
    FitnessPredictor,
    FitnessPrediction,
    FitnessPredictionReport,
    create_fitness_predictor,
)
from market_ops.e11.genome.schema import CreativeGenome, GenomeLineage


# ═══════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════


@pytest.fixture
def agent_with_data():
    """创建带有 DNA 数据的 CreativeAgent."""
    agent = create_creative_agent()
    # 添加有历史表现的 DNA
    agent.extract_dna("C_001", "game_A", hook="transformation",
                       visual="fantasy", emotion="surprise",
                       gameplay="merge", fitness={"roas": 1.8, "ctr": 0.03})
    agent.extract_dna("C_002", "game_A", hook="transformation",
                       visual="fantasy", emotion="surprise",
                       gameplay="merge", fitness={"roas": 1.6, "ctr": 0.028})
    agent.extract_dna("C_003", "game_A", hook="transformation",
                       visual="fantasy", emotion="surprise",
                       gameplay="merge", fitness={"roas": 2.0, "ctr": 0.035})
    agent.extract_dna("C_004", "game_A", hook="rescue",
                       visual="real_world", emotion="relief",
                       gameplay="puzzle", fitness={"roas": 1.2, "ctr": 0.02})
    agent.extract_dna("C_005", "game_A", hook="discovery",
                       visual="cartoon", emotion="excitement",
                       gameplay="rpg", fitness={"roas": 0.9, "ctr": 0.018})
    return agent


@pytest.fixture
def genome_intelligence(agent_with_data):
    """创建 GenomeIntelligence."""
    return GenomeIntelligence(memory=agent_with_data.get_memory(), min_samples=2)


@pytest.fixture
def predictor(genome_intelligence):
    """创建 FitnessPredictor."""
    return FitnessPredictor(
        genome_intelligence=genome_intelligence,
        roas_threshold=1.0,
        ctr_threshold=0.015,
        confidence_threshold=0.3,
    )


@pytest.fixture
def sample_genome():
    """创建示例基因组（使用已知获胜基因值）."""
    return CreativeGenome(
        genome_id="test_genome_001",
        generation=1,
        genes={
            "hook": {"type": "transformation", "strength": 0.8},
            "visual": {"style": "fantasy", "composition": "centered"},
            "emotion": {"primary": "surprise"},
            "gameplay": {"mechanic": "merge"},
        },
        fitness={"roas": 1.5},
        lineage=GenomeLineage(source="winner_001", created_by="dna_mapper"),
    )


@pytest.fixture
def novel_genome():
    """创建新颖基因组（使用未见过的基因值）."""
    return CreativeGenome(
        genome_id="novel_genome_001",
        generation=1,
        genes={
            "hook": {"type": "unknown_hook", "strength": 0.5},
            "visual": {"style": "unknown_style", "composition": "centered"},
            "emotion": {"primary": "unknown_emotion"},
            "gameplay": {"mechanic": "unknown_mechanic"},
        },
        lineage=GenomeLineage(source="experiment", created_by="mutation"),
    )


@pytest.fixture
def sample_genomes():
    """创建多个示例基因组."""
    genomes = []
    for i in range(5):
        hooks = ["transformation", "rescue", "discovery", "transformation", "rescue"]
        visuals = ["fantasy", "real_world", "cartoon", "fantasy", "real_world"]
        genomes.append(CreativeGenome(
            genome_id=f"genome_{i:03d}",
            generation=1,
            genes={
                "hook": {"type": hooks[i], "strength": 0.7},
                "visual": {"style": visuals[i], "composition": "centered"},
                "emotion": {"primary": "surprise"},
                "gameplay": {"mechanic": "merge"},
            },
            lineage=GenomeLineage(source=f"winner_{i:03d}", created_by="dna_mapper"),
        ))
    return genomes


# ═══════════════════════════════════════════════════════════
# FitnessPrediction / FitnessPredictionReport 模型测试
# ═══════════════════════════════════════════════════════════


class TestFitnessPredictionModel:
    """FitnessPrediction 模型测试."""

    def test_create_default(self):
        p = FitnessPrediction()
        assert p.prediction_id.startswith("fp_")
        assert p.predicted_roas == 0.0
        assert p.confidence == 0.0

    def test_create_with_data(self):
        p = FitnessPrediction(
            genome_id="g_001",
            predicted_roas=1.5,
            predicted_ctr=0.03,
            confidence=0.8,
            pass_threshold=True,
        )
        assert p.genome_id == "g_001"
        assert p.predicted_roas == 1.5
        assert p.predicted_ctr == 0.03
        assert p.confidence == 0.8
        assert p.pass_threshold is True

    def test_is_pass_true(self):
        p = FitnessPrediction(pass_threshold=True)
        assert p.is_pass() is True

    def test_is_pass_false(self):
        p = FitnessPrediction(pass_threshold=False)
        assert p.is_pass() is False

    def test_is_high_confidence(self):
        p = FitnessPrediction(confidence=0.8)
        assert p.is_high_confidence() is True

    def test_is_low_confidence(self):
        p = FitnessPrediction(confidence=0.3)
        assert p.is_high_confidence() is False

    def test_to_dict(self):
        p = FitnessPrediction(
            genome_id="g_001",
            predicted_roas=1.5,
            predicted_ctr=0.03,
            confidence=0.8,
        )
        d = p.to_dict()
        assert d["genome_id"] == "g_001"
        assert d["predicted_roas"] == 1.5
        assert d["confidence"] == 0.8

    def test_to_dict_rounding(self):
        p = FitnessPrediction(
            predicted_roas=1.5,
            predicted_ctr=0.03,
            confidence=0.8,
        )
        d = p.to_dict()
        assert d["predicted_roas"] == 1.5
        assert d["predicted_ctr"] == 0.03
        assert d["confidence"] == 0.8

    def test_summary_not_empty(self):
        p = FitnessPrediction(summary="test summary")
        assert p.summary == "test summary"

    def test_created_at_not_empty(self):
        p = FitnessPrediction()
        assert p.created_at != ""


class TestFitnessPredictionReport:
    """FitnessPredictionReport 模型测试."""

    def test_create_default(self):
        r = FitnessPredictionReport()
        assert r.total_predicted == 0
        assert r.pass_rate == 0.0

    def test_to_dict(self):
        r = FitnessPredictionReport(
            total_predicted=10,
            passed_count=7,
            pass_rate=0.7,
        )
        d = r.to_dict()
        assert d["total_predicted"] == 10
        assert d["passed_count"] == 7
        assert d["pass_rate"] == 0.7


# ═══════════════════════════════════════════════════════════
# FitnessPredictor.predict() 核心测试
# ═══════════════════════════════════════════════════════════


class TestFitnessPredictorPredict:
    """核心预测逻辑测试."""

    def test_predict_returns_prediction(self, predictor, sample_genome):
        result = predictor.predict(sample_genome)
        assert isinstance(result, FitnessPrediction)

    def test_predict_has_roas(self, predictor, sample_genome):
        result = predictor.predict(sample_genome)
        assert result.predicted_roas > 0

    def test_predict_has_ctr(self, predictor, sample_genome):
        result = predictor.predict(sample_genome)
        assert result.predicted_ctr > 0

    def test_predict_has_confidence(self, predictor, sample_genome):
        result = predictor.predict(sample_genome)
        assert 0 <= result.confidence <= 1.0

    def test_predict_has_fitness_score(self, predictor, sample_genome):
        result = predictor.predict(sample_genome)
        assert result.fitness_score >= 0

    def test_predict_has_gene_contributions(self, predictor, sample_genome):
        result = predictor.predict(sample_genome)
        assert len(result.gene_contributions) > 0

    def test_predict_gene_contributions_structure(self, predictor, sample_genome):
        result = predictor.predict(sample_genome)
        for gene, contrib in result.gene_contributions.items():
            assert "gene_value" in contrib
            assert "weight" in contrib
            assert "roas" in contrib
            assert "confidence" in contrib

    def test_predict_known_genes_higher_confidence(self, predictor, sample_genome, novel_genome):
        known = predictor.predict(sample_genome)
        novel = predictor.predict(novel_genome)
        # 已知基因值应有更高置信度
        assert known.confidence >= novel.confidence

    def test_predict_with_empty_genome(self, predictor):
        genome = CreativeGenome(genome_id="empty")
        result = predictor.predict(genome)
        assert isinstance(result, FitnessPrediction)

    def test_predict_with_single_gene(self, predictor):
        genome = CreativeGenome(
            genome_id="single",
            genes={"hook": {"type": "transformation"}},
        )
        result = predictor.predict(genome)
        assert isinstance(result, FitnessPrediction)

    def test_predict_novel_uses_defaults(self, predictor, novel_genome):
        result = predictor.predict(novel_genome)
        # 新颖基因值应使用默认值
        assert result.predicted_roas > 0
        assert result.confidence < 0.5

    def test_predict_genome_id_preserved(self, predictor, sample_genome):
        result = predictor.predict(sample_genome)
        assert result.genome_id == sample_genome.genome_id

    def test_predict_summary_not_empty(self, predictor, sample_genome):
        result = predictor.predict(sample_genome)
        assert result.summary != ""

    def test_predict_idempotent(self, predictor, sample_genome):
        r1 = predictor.predict(sample_genome)
        r2 = predictor.predict(sample_genome)
        assert r1.predicted_roas == r2.predicted_roas
        assert r1.confidence == r2.confidence

    def test_predict_pass_threshold(self, predictor, sample_genome):
        result = predictor.predict(sample_genome)
        assert isinstance(result.pass_threshold, bool)

    def test_predict_with_custom_report(self, predictor, sample_genome, genome_intelligence):
        report = genome_intelligence.analyze()
        result = predictor.predict(sample_genome, genome_report=report)
        assert isinstance(result, FitnessPrediction)

    def test_predict_cpi_calculated(self, predictor, sample_genome):
        result = predictor.predict(sample_genome)
        assert result.predicted_cpi > 0

    def test_predict_ltv_calculated(self, predictor, sample_genome):
        result = predictor.predict(sample_genome)
        assert result.predicted_ltv > 0

    def test_predict_payer_rate_calculated(self, predictor, sample_genome):
        result = predictor.predict(sample_genome)
        assert result.predicted_payer_rate >= 0

    def test_predict_with_reward_gene(self, predictor):
        genome = CreativeGenome(
            genome_id="reward_test",
            genes={
                "hook": {"type": "transformation"},
                "reward": {"type": "iap"},
            },
        )
        result = predictor.predict(genome)
        assert "reward" in result.gene_contributions


# ═══════════════════════════════════════════════════════════
# predict_batch / filter / rank 测试
# ═══════════════════════════════════════════════════════════


class TestBatchFilterRank:
    """批量预测、筛选、排序测试."""

    def test_predict_batch(self, predictor, sample_genomes):
        results = predictor.predict_batch(sample_genomes)
        assert len(results) == len(sample_genomes)
        for r in results:
            assert isinstance(r, FitnessPrediction)

    def test_predict_batch_empty(self, predictor):
        results = predictor.predict_batch([])
        assert results == []

    def test_filter_by_threshold(self, predictor, sample_genomes):
        predictions = predictor.predict_batch(sample_genomes)
        passed = predictor.filter_by_threshold(predictions)
        assert len(passed) <= len(predictions)

    def test_filter_by_threshold_all(self, predictor, sample_genomes):
        predictions = predictor.predict_batch(sample_genomes)
        passed = predictor.filter_by_threshold(predictions)
        for p in passed:
            assert p.pass_threshold is True

    def test_rank_by_fitness(self, predictor, sample_genomes):
        predictions = predictor.predict_batch(sample_genomes)
        ranked = predictor.rank_by_fitness(predictions)
        if len(ranked) >= 2:
            for i in range(len(ranked) - 1):
                assert ranked[i].fitness_score >= ranked[i + 1].fitness_score

    def test_rank_by_fitness_top_n(self, predictor, sample_genomes):
        predictions = predictor.predict_batch(sample_genomes)
        ranked = predictor.rank_by_fitness(predictions, top_n=3)
        assert len(ranked) <= 3

    def test_select_top_candidates(self, predictor, sample_genomes):
        top = predictor.select_top_candidates(sample_genomes, top_n=3)
        assert len(top) <= 3
        for p in top:
            assert p.pass_threshold is True

    def test_select_top_candidates_sorted(self, predictor, sample_genomes):
        top = predictor.select_top_candidates(sample_genomes, top_n=5)
        if len(top) >= 2:
            for i in range(len(top) - 1):
                assert top[i].fitness_score >= top[i + 1].fitness_score

    def test_select_top_candidates_empty(self, predictor):
        top = predictor.select_top_candidates([])
        assert top == []

    def test_filter_by_threshold_empty(self, predictor):
        passed = predictor.filter_by_threshold([])
        assert passed == []

    def test_rank_by_fitness_empty(self, predictor):
        ranked = predictor.rank_by_fitness([])
        assert ranked == []

    def test_predict_batch_single(self, predictor, sample_genome):
        results = predictor.predict_batch([sample_genome])
        assert len(results) == 1

    def test_predict_batch_idempotent(self, predictor, sample_genomes):
        r1 = predictor.predict_batch(sample_genomes)
        r2 = predictor.predict_batch(sample_genomes)
        for a, b in zip(r1, r2):
            assert a.predicted_roas == b.predicted_roas

    def test_rank_preserves_all(self, predictor, sample_genomes):
        predictions = predictor.predict_batch(sample_genomes)
        ranked = predictor.rank_by_fitness(predictions)
        assert len(ranked) == len(predictions)

    def test_select_top_no_passing_returns_empty(self, predictor):
        # 创建全低分基因组
        low_genomes = [
            CreativeGenome(
                genome_id=f"low_{i}",
                genes={"hook": {"type": "unknown"}, "visual": {"style": "unknown"}},
            )
            for i in range(3)
        ]
        top = predictor.select_top_candidates(low_genomes, top_n=3)
        # 低分 + 低置信度应全部不通过
        assert len(top) == 0


# ═══════════════════════════════════════════════════════════
# 阈值与置信度测试
# ═══════════════════════════════════════════════════════════


class TestThresholdsAndConfidence:
    """阈值与置信度测试."""

    def test_custom_thresholds(self, genome_intelligence):
        p = FitnessPredictor(
            genome_intelligence=genome_intelligence,
            roas_threshold=2.0,
            ctr_threshold=0.05,
            confidence_threshold=0.8,
        )
        assert p._roas_threshold == 2.0
        assert p._ctr_threshold == 0.05
        assert p._confidence_threshold == 0.8

    def test_high_roas_threshold_blocks(self, genome_intelligence, sample_genome):
        p = FitnessPredictor(
            genome_intelligence=genome_intelligence,
            roas_threshold=10.0,  # 极高阈值
        )
        result = p.predict(sample_genome)
        assert result.pass_threshold is False

    def test_low_threshold_allows(self, genome_intelligence, sample_genome):
        p = FitnessPredictor(
            genome_intelligence=genome_intelligence,
            roas_threshold=0.1,
            ctr_threshold=0.001,
            confidence_threshold=0.1,
        )
        result = p.predict(sample_genome)
        assert result.pass_threshold is True

    def test_confidence_threshold_blocks_novel(self, genome_intelligence, novel_genome):
        p = FitnessPredictor(
            genome_intelligence=genome_intelligence,
            confidence_threshold=0.9,  # 极高置信度要求
        )
        result = p.predict(novel_genome)
        assert result.pass_threshold is False

    def test_confidence_increases_with_more_data(self, genome_intelligence):
        """更多数据应提升置信度."""
        p = FitnessPredictor(genome_intelligence=genome_intelligence)
        genome = CreativeGenome(
            genome_id="test",
            genes={
                "hook": {"type": "transformation"},
                "visual": {"style": "fantasy"},
                "emotion": {"primary": "surprise"},
                "gameplay": {"mechanic": "merge"},
            },
        )
        result = p.predict(genome)
        # transformation 有 3 个样本，fantasy 有 3 个样本 → 置信度应 > 0.3
        assert result.confidence > 0.3

    def test_no_data_returns_low_confidence(self, genome_intelligence):
        p = FitnessPredictor(genome_intelligence=genome_intelligence)
        genome = CreativeGenome(
            genome_id="no_data",
            genes={"hook": {"type": "nonexistent"}},
        )
        result = p.predict(genome)
        assert result.confidence < 0.5

    def test_create_fitness_predictor(self, genome_intelligence):
        p = create_fitness_predictor(genome_intelligence=genome_intelligence)
        assert isinstance(p, FitnessPredictor)

    def test_create_fitness_predictor_default(self):
        p = create_fitness_predictor()
        assert isinstance(p, FitnessPredictor)

    def test_create_fitness_predictor_custom_thresholds(self, genome_intelligence):
        p = create_fitness_predictor(
            genome_intelligence=genome_intelligence,
            roas_threshold=1.5,
            ctr_threshold=0.02,
            confidence_threshold=0.5,
        )
        assert p._roas_threshold == 1.5
        assert p._ctr_threshold == 0.02
        assert p._confidence_threshold == 0.5


# ═══════════════════════════════════════════════════════════
# 查询与报告测试
# ═══════════════════════════════════════════════════════════


class TestQueriesAndReports:
    """查询与报告测试."""

    def test_get_prediction(self, predictor, sample_genome):
        predictor.predict(sample_genome)
        found = predictor.get_prediction(sample_genome.genome_id)
        assert found is not None
        assert found.genome_id == sample_genome.genome_id

    def test_get_prediction_not_found(self, predictor):
        found = predictor.get_prediction("nonexistent")
        assert found is None

    def test_get_passed(self, predictor, sample_genomes):
        predictor.predict_batch(sample_genomes)
        passed = predictor.get_passed()
        assert isinstance(passed, list)

    def test_get_failed(self, predictor, sample_genomes):
        predictor.predict_batch(sample_genomes)
        failed = predictor.get_failed()
        assert isinstance(failed, list)

    def test_get_recent(self, predictor, sample_genomes):
        predictor.predict_batch(sample_genomes)
        recent = predictor.get_recent(3)
        assert len(recent) <= 3

    def test_get_recent_empty(self, predictor):
        recent = predictor.get_recent(5)
        assert recent == []

    def test_generate_report(self, predictor, sample_genomes):
        predictor.predict_batch(sample_genomes)
        report = predictor.generate_report()
        assert isinstance(report, FitnessPredictionReport)
        assert report.total_predicted > 0
        assert report.summary != ""

    def test_generate_report_empty(self, predictor):
        report = predictor.generate_report()
        assert isinstance(report, FitnessPredictionReport)
        assert report.total_predicted == 0

    def test_stats(self, predictor, sample_genomes):
        predictor.predict_batch(sample_genomes)
        stats = predictor.stats()
        assert stats["total_predictions"] > 0
        assert "passed_count" in stats
        assert "failed_count" in stats
        assert "roas_threshold" in stats

    def test_reset(self, predictor, sample_genomes):
        predictor.predict_batch(sample_genomes)
        assert predictor.stats()["total_predictions"] > 0
        predictor.reset()
        assert predictor.stats()["total_predictions"] == 0


# ═══════════════════════════════════════════════════════════
# CreativeAgent 集成测试
# ═══════════════════════════════════════════════════════════


class TestCreativeAgentE1455Integration:
    """CreativeAgent 集成测试."""

    def test_predictor_with_agent_data(self, agent_with_data):
        gi = GenomeIntelligence(memory=agent_with_data.get_memory(), min_samples=2)
        p = FitnessPredictor(genome_intelligence=gi)
        genome = CreativeGenome(
            genome_id="integration_test",
            genes={
                "hook": {"type": "transformation"},
                "visual": {"style": "fantasy"},
                "emotion": {"primary": "surprise"},
                "gameplay": {"mechanic": "merge"},
            },
        )
        result = p.predict(genome)
        assert isinstance(result, FitnessPrediction)

    def test_full_pipeline(self, agent_with_data):
        """完整流程: GI → Predict → Filter → Rank."""
        gi = GenomeIntelligence(memory=agent_with_data.get_memory(), min_samples=2)
        p = FitnessPredictor(genome_intelligence=gi)

        genomes = [
            CreativeGenome(
                genome_id=f"test_{i}",
                genes={
                    "hook": {"type": "transformation"},
                    "visual": {"style": "fantasy"},
                    "emotion": {"primary": "surprise"},
                    "gameplay": {"mechanic": "merge"},
                },
            )
            for i in range(5)
        ]

        top = p.select_top_candidates(genomes, top_n=3)
        assert len(top) <= 3

    def test_prediction_to_dict_roundtrip(self, predictor, sample_genome):
        result = predictor.predict(sample_genome)
        d = result.to_dict()
        assert d["genome_id"] == result.genome_id
        assert d["predicted_roas"] == pytest.approx(result.predicted_roas)

    def test_report_to_dict_roundtrip(self, predictor, sample_genomes):
        predictor.predict_batch(sample_genomes)
        report = predictor.generate_report()
        d = report.to_dict()
        assert d["total_predicted"] == report.total_predicted

    def test_predictor_with_multiple_genomes(self, predictor, sample_genomes):
        results = predictor.predict_batch(sample_genomes)
        assert len(results) == len(sample_genomes)
        ids = {r.genome_id for r in results}
        expected_ids = {g.genome_id for g in sample_genomes}
        assert ids == expected_ids

    def test_predictor_isolated(self, agent_with_data):
        """不同 predictor 实例独立."""
        gi1 = GenomeIntelligence(memory=agent_with_data.get_memory(), min_samples=2)
        p1 = FitnessPredictor(genome_intelligence=gi1)

        memory2 = CreativeMemory()
        gi2 = GenomeIntelligence(memory=memory2, min_samples=2)
        p2 = FitnessPredictor(genome_intelligence=gi2)

        genome = CreativeGenome(
            genome_id="iso_test",
            genes={"hook": {"type": "transformation"}},
        )
        p1.predict(genome)
        p2.predict(genome)

        assert p1.stats()["total_predictions"] == 1
        assert p2.stats()["total_predictions"] == 1

    def test_predictor_no_gi_uses_defaults(self):
        p = FitnessPredictor()
        genome = CreativeGenome(
            genome_id="no_gi",
            genes={"hook": {"type": "transformation"}},
        )
        result = p.predict(genome)
        assert isinstance(result, FitnessPrediction)
        # 没有 GI 时使用默认值
        assert result.predicted_roas > 0

    def test_gene_contributions_weights_sum(self, predictor, sample_genome):
        result = predictor.predict(sample_genome)
        total = sum(c["weight"] for c in result.gene_contributions.values())
        # 权重可能不完全是 1.0（reward 基因可能不在 genome 中）
        assert total > 0

    def test_predictor_stats_after_batch(self, predictor, sample_genomes):
        predictor.predict_batch(sample_genomes)
        stats = predictor.stats()
        assert stats["total_predictions"] == len(sample_genomes)
        assert stats["passed_count"] + stats["failed_count"] == len(sample_genomes)

    def test_select_top_candidates_respects_threshold(self, agent_with_data):
        gi = GenomeIntelligence(memory=agent_with_data.get_memory(), min_samples=2)
        # 极高阈值
        p = FitnessPredictor(
            genome_intelligence=gi,
            roas_threshold=100.0,
        )
        genomes = [
            CreativeGenome(
                genome_id=f"high_thresh_{i}",
                genes={"hook": {"type": "transformation"}},
            )
            for i in range(3)
        ]
        top = p.select_top_candidates(genomes, top_n=3)
        assert len(top) == 0


# ═══════════════════════════════════════════════════════════
# 回归测试
# ═══════════════════════════════════════════════════════════


class TestE1455Regression:
    """回归测试 — 确保 E14.5.4 / E14.5.3 / E14.5.2 / E14.5.1 / E14.4.4 稳定."""

    def test_e1454_adaptive_mutation(self):
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain import (
            AdaptiveMutationSelector,
            AdaptiveMutation,
            AdaptiveMutationReport,
        )
        assert AdaptiveMutationSelector is not None
        assert AdaptiveMutation is not None
        assert AdaptiveMutationReport is not None

    def test_e1454_selector_works(self):
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain import (
            AdaptiveMutationSelector,
            create_adaptive_mutation_selector,
        )
        s = create_adaptive_mutation_selector()
        mutations = s.select()
        assert isinstance(mutations, list)

    def test_e1453_evolution_planner(self):
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain import (
            EvolutionPlanner,
            EvolutionPlan,
        )
        assert EvolutionPlanner is not None
        assert EvolutionPlan is not None

    def test_e1453_plan_creation(self):
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain import (
            EvolutionPlanner,
            EvolutionPlan,
        )
        ep = EvolutionPlanner()
        plan = ep.plan()
        assert isinstance(plan, EvolutionPlan)

    def test_e1452_population_analyzer(self):
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain import (
            PopulationAnalyzer,
        )
        assert PopulationAnalyzer is not None

    def test_e1452_analyze_works(self):
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain import (
            PopulationAnalyzer,
            PopulationHealthReport,
        )
        pa = PopulationAnalyzer()
        report = pa.analyze()
        assert isinstance(report, PopulationHealthReport)

    def test_e1451_genome_intelligence(self):
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain import (
            GenomeIntelligence,
            GenomeIntelligenceReport,
        )
        assert GenomeIntelligence is not None
        assert GenomeIntelligenceReport is not None

    def test_e1451_report_works(self):
        gi = GenomeIntelligence()
        report = gi.analyze()
        assert isinstance(report, GenomeIntelligenceReport)

    def test_e1444_mutation_learning(self):
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.learning.mutation_learning import (
            MutationLearning,
        )
        assert MutationLearning is not None

    def test_e1444_reward_model(self):
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.learning.reward_model import (
            RewardModel,
        )
        assert RewardModel is not None

    def test_e1444_pattern_miner(self):
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.learning.pattern_miner import (
            PatternMiner,
        )
        assert PatternMiner is not None

    def test_e1444_strategy_memory(self):
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.learning.strategy_memory import (
            StrategyMemory,
        )
        assert StrategyMemory is not None

    def test_e1444_creative_policy(self):
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.learning.creative_policy import (
            CreativePolicy,
        )
        assert CreativePolicy is not None

    def test_e1444_learning_loop(self):
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.learning import (
            MutationLearning,
            RewardModel,
            PatternMiner,
            StrategyMemory,
            CreativePolicy,
        )
        assert MutationLearning is not None
        assert RewardModel is not None
        assert PatternMiner is not None
        assert StrategyMemory is not None
        assert CreativePolicy is not None

    def test_agent_creation(self):
        agent = create_creative_agent()
        assert isinstance(agent, CreativeAgent)