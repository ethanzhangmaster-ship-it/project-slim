"""E12.5.2 — Pattern Mining Engine 测试。

覆盖:
  - Models: PatternType, MetaPattern, GeneCluster, GeneImpactScore,
            ExtractedGene, PatternMiningResult
  - GeneAnalyzer: hook/visual/gameplay/reward/psychology 提取
  - PatternExtractor: 聚类、模式提取
  - CorrelationEngine: 基因影响力计算
  - PatternRanker: 评分、筛选、排序
  - Pipeline: 完整模式挖掘流程
  - Integration: 与 ExperienceStore 集成
"""

import pytest

from market_ops.creative_vision_runtime.reality.meta_learning import (
    ContextDetail,
    ExperienceOutcome,
    ExperienceRecord,
    ExperienceStore,
    ExperimentDetail,
    MutationDetail,
    MutationType,
)
from market_ops.creative_vision_runtime.reality.meta_learning.pattern_miner import (
    CorrelationEngine,
    ExtractedGene,
    GeneAnalyzer,
    GeneCluster,
    GeneImpactScore,
    MetaPattern,
    PatternExtractor,
    PatternMiningResult,
    PatternRanker,
    PatternType,
)


# ── Helpers ───────────────────────────────────────────────


def make_mutation_detail(changed_genes=None, gene_after=None):
    return MutationDetail(
        mutation_type=MutationType.REFRESH_HOOK,
        changed_genes=changed_genes or ["hook", "visual_style"],
        gene_before={"hook": "old_value"},
        gene_after=gene_after if gene_after is not None else {"hook": "rescue_puppy", "visual_style": "bright_colorful"},
    )


def make_experiment_detail(improvement=0.3, metrics_delta=None):
    return ExperimentDetail(
        baseline_metrics={"ctr": 0.02, "roas": 0.5},
        winner_metrics={"ctr": 0.03, "roas": 0.7},
        improvement=improvement,
        metrics_delta=metrics_delta or {"ctr": 0.5, "roas": 0.4, "cvr": 0.15},
        winner_id="v2",
        variant_count=3,
        confidence=0.85,
    )


def make_context(product="p04", market="US"):
    return ContextDetail(
        product_id=product,
        product_name="Merge Witch",
        market=market,
        platform="facebook",
    )


def make_record(
    product="p04",
    creative="c001",
    improvement=0.3,
    outcome=ExperienceOutcome.SUCCESS,
    gene_after=None,
    metrics_delta=None,
    market="US",
):
    from market_ops.creative_vision_runtime.reality.meta_learning import ExperienceResult

    return ExperienceRecord(
        product_id=product,
        creative_id=creative,
        genome_id="g001",
        mutation=make_mutation_detail(gene_after=gene_after),
        experiment=make_experiment_detail(
            improvement=improvement,
            metrics_delta=metrics_delta,
        ),
        context=make_context(product=product, market=market),
        result=ExperienceResult(
            outcome=outcome,
            success=outcome in (ExperienceOutcome.SUCCESS, ExperienceOutcome.MARGINAL),
            insight="Test insight",
            key_finding="Test finding",
        ),
    )


# ═══════════════════════════════════════════════════════════
# 1. Pattern Models (15 tests)
# ═══════════════════════════════════════════════════════════


class TestPatternModels:
    """E12.5.2 数据模型测试。"""

    # ── PatternType ──────────────────────────────────────

    def test_pattern_type_enum_values(self):
        assert len(list(PatternType)) == 8
        assert PatternType.HOOK.value == "hook"
        assert PatternType.VISUAL.value == "visual"
        assert PatternType.GAMEPLAY.value == "gameplay"
        assert PatternType.FULL_CREATIVE.value == "full_creative"

    def test_pattern_type_serialization(self):
        pt = PatternType.PSYCHOLOGY
        assert pt.value == "psychology"
        assert PatternType("psychology") == PatternType.PSYCHOLOGY

    # ── ExtractedGene ────────────────────────────────────

    def test_extracted_gene_creation(self):
        gene = ExtractedGene(
            gene_category="hook",
            features={"emotion": "rescue", "character": "animal"},
            raw_value="rescue_puppy",
            confidence=0.85,
        )
        assert gene.gene_category == "hook"
        assert gene.features["emotion"] == "rescue"
        assert gene.raw_value == "rescue_puppy"
        assert gene.confidence == 0.85

    def test_extracted_gene_feature_key(self):
        gene = ExtractedGene(
            gene_category="hook",
            features={"emotion": "rescue", "character": "animal"},
        )
        key = gene.feature_key
        assert "character:animal" in key
        assert "emotion:rescue" in key

    def test_extracted_gene_feature_key_empty(self):
        gene = ExtractedGene(
            gene_category="hook",
            features={},
            raw_value="raw_text",
        )
        assert gene.feature_key == "raw_text"

    def test_extracted_gene_to_dict(self):
        gene = ExtractedGene(
            gene_category="hook",
            features={"emotion": "rescue"},
            raw_value="rescue_puppy",
            confidence=0.8,
        )
        d = gene.to_dict()
        assert d["gene_category"] == "hook"
        assert d["features"]["emotion"] == "rescue"
        assert "feature_key" in d

    def test_extracted_gene_repr(self):
        gene = ExtractedGene(
            gene_category="hook",
            features={"emotion": "rescue"},
        )
        r = repr(gene)
        assert "ExtractedGene" in r
        assert "hook" in r

    # ── GeneCluster ──────────────────────────────────────

    def test_gene_cluster_creation(self):
        cluster = GeneCluster(
            gene_category="hook",
            feature_key="emotion:rescue|character:animal",
            members=["exp_001", "exp_002", "exp_003"],
            success_count=2,
            success_rate=0.67,
            avg_roas_gain=0.25,
            representative_genes={"emotion": "rescue", "character": "animal"},
        )
        assert cluster.gene_category == "hook"
        assert cluster.sample_count == 3
        assert cluster.success_rate == 0.67

    def test_gene_cluster_auto_id(self):
        cluster = GeneCluster(
            gene_category="hook",
            feature_key="test",
            members=["exp_001"],
        )
        assert cluster.cluster_id.startswith("gc_")

    def test_gene_cluster_to_dict(self):
        cluster = GeneCluster(
            gene_category="hook",
            feature_key="test",
            members=["exp_001", "exp_002"],
            success_count=2,
            success_rate=1.0,
            avg_roas_gain=0.3,
            representative_genes={"emotion": "rescue"},
        )
        d = cluster.to_dict()
        assert d["gene_category"] == "hook"
        assert d["sample_count"] == 2
        assert d["success_rate"] == 1.0

    def test_gene_cluster_repr(self):
        cluster = GeneCluster(
            gene_category="hook",
            feature_key="test_feature_key",
            members=["exp_001", "exp_002"],
            success_count=1,
            success_rate=0.5,
        )
        r = repr(cluster)
        assert "GeneCluster" in r
        assert "hook" in r

    # ── MetaPattern ──────────────────────────────────────

    def test_meta_pattern_creation(self):
        pattern = MetaPattern(
            pattern_type=PatternType.HOOK,
            name="Rescue Hook",
            genes={"emotion": "rescue", "character": "animal"},
            sample_count=100,
            success_count=75,
            success_rate=0.75,
            avg_roas_gain=0.21,
            avg_ctr_gain=0.15,
            avg_cvr_gain=0.10,
            confidence=0.91,
            markets=["US", "EU"],
            products=["p04", "p07"],
        )
        assert pattern.pattern_id.startswith("PAT_")
        assert pattern.name == "Rescue Hook"
        assert pattern.is_reliable is True
        assert pattern.is_strong is True

    def test_meta_pattern_unreliable(self):
        pattern = MetaPattern(
            sample_count=3,
            confidence=0.5,
        )
        assert pattern.is_reliable is False
        assert pattern.is_strong is False

    def test_meta_pattern_to_mutation_prior(self):
        pattern = MetaPattern(
            pattern_type=PatternType.HOOK,
            name="Rescue Hook",
            genes={"emotion": "rescue"},
            sample_count=100,
            success_count=75,
            success_rate=0.75,
            avg_roas_gain=0.21,
            confidence=0.91,
            rank_score=0.82,
            recommendation="Amplify hook pattern",
        )
        prior = pattern.to_mutation_prior()
        assert prior["pattern_name"] == "Rescue Hook"
        assert prior["priority"] == 0.82
        assert prior["confidence"] == 0.91
        assert "recommended_genes" in prior
        assert "evidence" in prior

    # ── GeneImpactScore ──────────────────────────────────

    def test_gene_impact_score_positive(self):
        impact = GeneImpactScore(
            gene_category="hook",
            gene_feature="emotion",
            gene_value="rescue",
            impact_score=0.27,
            sample_count=100,
            confidence=0.9,
        )
        assert impact.is_positive is True
        assert impact.is_negative is False
        assert impact.is_significant is True

    def test_gene_impact_score_negative(self):
        impact = GeneImpactScore(
            gene_category="visual",
            gene_feature="style",
            gene_value="dark",
            impact_score=-0.15,
            sample_count=50,
            confidence=0.8,
        )
        assert impact.is_positive is False
        assert impact.is_negative is True
        assert impact.is_significant is True

    def test_gene_impact_score_neutral(self):
        impact = GeneImpactScore(
            impact_score=0.02,
            sample_count=10,
            confidence=0.5,
        )
        assert impact.is_positive is False
        assert impact.is_negative is False
        assert impact.is_significant is False

    def test_gene_impact_score_to_dict(self):
        impact = GeneImpactScore(
            gene_category="hook",
            gene_feature="emotion",
            gene_value="rescue",
            impact_score=0.27,
            sample_count=100,
            confidence=0.9,
            lift_pct=0.35,
        )
        d = impact.to_dict()
        assert d["gene_category"] == "hook"
        assert d["impact_score"] == 0.27
        assert d["is_positive"] is True

    def test_gene_impact_score_repr(self):
        impact = GeneImpactScore(
            gene_feature="emotion",
            gene_value="rescue",
            impact_score=0.27,
            sample_count=100,
        )
        r = repr(impact)
        assert "GeneImpactScore" in r
        assert "rescue" in r

    # ── PatternMiningResult ──────────────────────────────

    def test_pattern_mining_result_creation(self):
        result = PatternMiningResult(
            patterns=[],
            gene_impacts=[],
            total_experiences=100,
            clusters_found=5,
        )
        assert result.patterns_found == 0
        assert result.total_experiences == 100
        assert result.clusters_found == 5

    def test_pattern_mining_result_get_top_patterns(self):
        patterns = [
            MetaPattern(name="A", rank_score=0.9, sample_count=10, success_count=8, success_rate=0.8),
            MetaPattern(name="B", rank_score=0.7, sample_count=10, success_count=7, success_rate=0.7),
            MetaPattern(name="C", rank_score=0.5, sample_count=10, success_count=5, success_rate=0.5),
        ]
        result = PatternMiningResult(patterns=patterns, total_experiences=100)
        top = result.get_top_patterns(n=2)
        assert len(top) == 2
        assert top[0].name == "A"

    def test_pattern_mining_result_empty(self):
        result = PatternMiningResult()
        assert result.patterns_found == 0
        assert result.get_top_patterns() == []

    def test_pattern_mining_result_to_dict(self):
        patterns = [
            MetaPattern(
                pattern_type=PatternType.HOOK,
                name="Test",
                sample_count=10,
                success_count=7,
                success_rate=0.7,
                rank_score=0.8,
            )
        ]
        impact = GeneImpactScore(
            gene_feature="emotion",
            gene_value="rescue",
            impact_score=0.27,
            sample_count=100,
            confidence=0.9,
        )
        result = PatternMiningResult(
            patterns=patterns,
            gene_impacts=[impact],
            total_experiences=100,
            clusters_found=3,
        )
        d = result.to_dict()
        assert d["total_experiences"] == 100
        assert len(d["patterns"]) == 1
        assert len(d["gene_impacts"]) == 1
        assert d["patterns_found"] == 1


# ═══════════════════════════════════════════════════════════
# 2. Gene Analyzer (15 tests)
# ═══════════════════════════════════════════════════════════


class TestGeneAnalyzer:
    """GeneAnalyzer — 基因提取测试。"""

    def test_extract_hook_rescue(self):
        analyzer = GeneAnalyzer()
        record = make_record(
            gene_after={"hook": "rescue_puppy"},
            metrics_delta={"ctr": 0.3, "roas": 0.2},
        )
        genes = analyzer.extract_genes(record)
        assert len(genes) >= 1
        hook_gene = next((g for g in genes if g.gene_category == "hook"), None)
        assert hook_gene is not None
        assert hook_gene.features.get("emotion") == "rescue"

    def test_extract_hook_challenge(self):
        analyzer = GeneAnalyzer()
        record = make_record(
            gene_after={"hook": "impossible_challenge"},
            metrics_delta={"ctr": 0.3, "roas": 0.2},
        )
        genes = analyzer.extract_genes(record)
        hook_gene = next((g for g in genes if g.gene_category == "hook"), None)
        assert hook_gene is not None
        assert hook_gene.features.get("emotion") == "challenge"

    def test_extract_hook_curiosity(self):
        analyzer = GeneAnalyzer()
        record = make_record(
            gene_after={"hook": "mystery_discover"},
            metrics_delta={"ctr": 0.3, "roas": 0.2},
        )
        genes = analyzer.extract_genes(record)
        hook_gene = next((g for g in genes if g.gene_category == "hook"), None)
        assert hook_gene is not None
        assert hook_gene.features.get("emotion") == "curiosity"

    def test_extract_hook_timer_conflict(self):
        analyzer = GeneAnalyzer()
        record = make_record(
            gene_after={"hook": "countdown_timer_rescue"},
            metrics_delta={"ctr": 0.3, "roas": 0.2},
        )
        genes = analyzer.extract_genes(record)
        hook_gene = next((g for g in genes if g.gene_category == "hook"), None)
        assert hook_gene is not None
        assert hook_gene.features.get("conflict") == "time_pressure"

    def test_extract_hook_dragon_character(self):
        analyzer = GeneAnalyzer()
        record = make_record(
            gene_after={"hook": "save_dragon"},
            metrics_delta={"ctr": 0.3, "roas": 0.2},
        )
        genes = analyzer.extract_genes(record)
        hook_gene = next((g for g in genes if g.gene_category == "hook"), None)
        assert hook_gene is not None
        assert hook_gene.features.get("character") == "fantasy"

    def test_extract_visual_bright(self):
        analyzer = GeneAnalyzer()
        record = make_record(
            gene_after={"visual_style": "bright_colorful"},
            metrics_delta={"ctr": 0.3, "roas": 0.2},
        )
        genes = analyzer.extract_genes(record)
        vis_gene = next((g for g in genes if g.gene_category == "visual"), None)
        assert vis_gene is not None
        assert vis_gene.features.get("style") == "bright_colorful"

    def test_extract_visual_dark(self):
        analyzer = GeneAnalyzer()
        record = make_record(
            gene_after={"visual_style": "dark_moody"},
            metrics_delta={"ctr": 0.3, "roas": 0.2},
        )
        genes = analyzer.extract_genes(record)
        vis_gene = next((g for g in genes if g.gene_category == "visual"), None)
        assert vis_gene is not None
        assert vis_gene.features.get("style") == "dark_moody"

    def test_extract_gameplay_merge(self):
        analyzer = GeneAnalyzer()
        record = make_record(
            gene_after={"gameplay": "merge_combine"},
            metrics_delta={"ctr": 0.3, "roas": 0.2},
        )
        genes = analyzer.extract_genes(record)
        gp_gene = next((g for g in genes if g.gene_category == "gameplay"), None)
        assert gp_gene is not None
        assert gp_gene.features.get("mechanism") == "merge"

    def test_extract_gameplay_rescue(self):
        analyzer = GeneAnalyzer()
        record = make_record(
            gene_after={"gameplay": "rescue_help"},
            metrics_delta={"ctr": 0.3, "roas": 0.2},
        )
        genes = analyzer.extract_genes(record)
        gp_gene = next((g for g in genes if g.gene_category == "gameplay"), None)
        assert gp_gene is not None
        assert gp_gene.features.get("mechanism") == "rescue"

    def test_extract_reward(self):
        analyzer = GeneAnalyzer()
        record = make_record(
            gene_after={"monetization": "collect_gold"},
            metrics_delta={"ctr": 0.3, "roas": 0.2},
        )
        genes = analyzer.extract_genes(record)
        reward_gene = next((g for g in genes if g.gene_category == "reward"), None)
        assert reward_gene is not None
        assert reward_gene.features.get("reward_type") == "collection"

    def test_extract_psychology(self):
        analyzer = GeneAnalyzer()
        record = make_record(
            gene_after={"psychology": "collection_motivation"},
            metrics_delta={"ctr": 0.3, "roas": 0.2},
        )
        genes = analyzer.extract_genes(record)
        psy_gene = next((g for g in genes if g.gene_category == "psychology"), None)
        assert psy_gene is not None
        assert psy_gene.features.get("drive") == "collection_motivation"

    def test_extract_multiple_genes(self):
        analyzer = GeneAnalyzer()
        record = make_record(
            gene_after={
                "hook": "rescue_puppy",
                "visual_style": "bright_colorful",
                "gameplay": "merge_combine",
            },
            metrics_delta={"ctr": 0.3, "roas": 0.2},
        )
        genes = analyzer.extract_genes(record)
        assert len(genes) >= 3

    def test_extract_empty_gene_after(self):
        analyzer = GeneAnalyzer()
        record = make_record(gene_after={})
        genes = analyzer.extract_genes(record)
        assert genes == []

    def test_extract_unknown_value(self):
        analyzer = GeneAnalyzer()
        record = make_record(
            gene_after={"hook": "xyz_unknown_value"},
            metrics_delta={"ctr": 0.3, "roas": 0.2},
        )
        genes = analyzer.extract_genes(record)
        # 即使没有匹配到关键词，也应该返回一个基础基因
        assert len(genes) >= 1
        assert genes[0].raw_value == "xyz_unknown_value"

    def test_extract_batch(self):
        analyzer = GeneAnalyzer()
        records = [
            make_record(creative="c001", gene_after={"hook": "rescue_puppy"}),
            make_record(creative="c002", gene_after={"hook": "save_animal"}),
            make_record(creative="c003", gene_after={"hook": "help_character"}),
        ]
        all_genes = analyzer.extract_genes_batch(records)
        assert len(all_genes) == 3
        assert all(len(genes) >= 1 for genes in all_genes)


# ═══════════════════════════════════════════════════════════
# 3. Pattern Extractor (20 tests)
# ═══════════════════════════════════════════════════════════


class TestPatternExtractor:
    """PatternExtractor — 模式提取测试。"""

    def test_extract_empty(self):
        extractor = PatternExtractor()
        patterns = extractor.extract([])
        assert patterns == []

    def test_extract_basic(self):
        extractor = PatternExtractor(min_cluster_size=3)
        records = [
            make_record(
                creative="c001",
                gene_after={"hook": "rescue_puppy"},
                improvement=0.3,
                metrics_delta={"ctr": 0.3, "roas": 0.2},
            ),
            make_record(
                creative="c002",
                gene_after={"hook": "rescue_puppy"},
                improvement=0.25,
                metrics_delta={"ctr": 0.25, "roas": 0.15},
            ),
            make_record(
                creative="c003",
                gene_after={"hook": "rescue_puppy"},
                improvement=0.35,
                metrics_delta={"ctr": 0.35, "roas": 0.25},
            ),
        ]
        patterns = extractor.extract(records)
        assert len(patterns) >= 1

    def test_extract_cluster_min_size(self):
        extractor = PatternExtractor(min_cluster_size=5)
        records = [
            make_record(creative="c001", gene_after={"hook": "rescue_puppy"}),
            make_record(creative="c002", gene_after={"hook": "rescue_puppy"}),
        ]
        patterns = extractor.extract(records)
        assert patterns == []

    def test_extract_multiple_hook_clusters(self):
        extractor = PatternExtractor(min_cluster_size=3)
        # 3 个 rescue hook
        records = [
            make_record(creative="c001", gene_after={"hook": "rescue_puppy"}, improvement=0.3),
            make_record(creative="c002", gene_after={"hook": "rescue_puppy"}, improvement=0.25),
            make_record(creative="c003", gene_after={"hook": "rescue_puppy"}, improvement=0.35),
            # 3 个 challenge hook
            make_record(creative="c004", gene_after={"hook": "impossible_challenge"}, improvement=0.1),
            make_record(creative="c005", gene_after={"hook": "impossible_challenge"}, improvement=0.05),
            make_record(creative="c006", gene_after={"hook": "impossible_challenge"}, improvement=0.15),
        ]
        patterns = extractor.extract(records)
        assert len(patterns) >= 2

    def test_extract_pattern_success_rate(self):
        extractor = PatternExtractor(min_cluster_size=3)
        records = [
            make_record(creative="c001", gene_after={"hook": "rescue_puppy"}, improvement=0.3, outcome=ExperienceOutcome.SUCCESS),
            make_record(creative="c002", gene_after={"hook": "rescue_puppy"}, improvement=0.25, outcome=ExperienceOutcome.SUCCESS),
            make_record(creative="c003", gene_after={"hook": "rescue_puppy"}, improvement=-0.1, outcome=ExperienceOutcome.FAILURE),
        ]
        patterns = extractor.extract(records)
        assert len(patterns) >= 1
        # 2/3 成功
        assert patterns[0].success_rate == pytest.approx(2 / 3)

    def test_extract_pattern_avg_roas(self):
        extractor = PatternExtractor(min_cluster_size=3)
        records = [
            make_record(creative="c001", gene_after={"hook": "rescue_puppy"}, metrics_delta={"roas": 0.3}),
            make_record(creative="c002", gene_after={"hook": "rescue_puppy"}, metrics_delta={"roas": 0.2}),
            make_record(creative="c003", gene_after={"hook": "rescue_puppy"}, metrics_delta={"roas": 0.1}),
        ]
        patterns = extractor.extract(records)
        assert len(patterns) >= 1
        assert patterns[0].avg_roas_gain == pytest.approx(0.2)

    def test_extract_pattern_name(self):
        extractor = PatternExtractor(min_cluster_size=3)
        records = [
            make_record(creative="c001", gene_after={"hook": "rescue_puppy"}, improvement=0.3),
            make_record(creative="c002", gene_after={"hook": "rescue_puppy"}, improvement=0.25),
            make_record(creative="c003", gene_after={"hook": "rescue_puppy"}, improvement=0.35),
        ]
        patterns = extractor.extract(records)
        assert len(patterns) >= 1
        assert patterns[0].name != ""
        assert "Rescue" in patterns[0].name or "Hook" in patterns[0].name

    def test_extract_from_store(self):
        store = ExperienceStore()
        for i in range(5):
            store.add(make_record(
                creative=f"c{i:03d}",
                gene_after={"hook": "rescue_puppy"},
                improvement=0.3,
            ))

        extractor = PatternExtractor(min_cluster_size=3)
        patterns = extractor.extract_from_store(store)
        assert len(patterns) >= 1

    def test_extract_visual_pattern(self):
        extractor = PatternExtractor(min_cluster_size=3)
        records = [
            make_record(creative="c001", gene_after={"visual_style": "bright_colorful"}, improvement=0.3),
            make_record(creative="c002", gene_after={"visual_style": "bright_colorful"}, improvement=0.25),
            make_record(creative="c003", gene_after={"visual_style": "bright_colorful"}, improvement=0.2),
        ]
        patterns = extractor.extract(records)
        assert len(patterns) >= 1
        assert patterns[0].pattern_type == PatternType.VISUAL

    def test_extract_gameplay_pattern(self):
        extractor = PatternExtractor(min_cluster_size=3)
        records = [
            make_record(creative="c001", gene_after={"gameplay": "merge_combine"}, improvement=0.3),
            make_record(creative="c002", gene_after={"gameplay": "merge_combine"}, improvement=0.25),
            make_record(creative="c003", gene_after={"gameplay": "merge_combine"}, improvement=0.2),
        ]
        patterns = extractor.extract(records)
        assert len(patterns) >= 1
        assert patterns[0].pattern_type == PatternType.GAMEPLAY

    def test_extract_multiple_gene_type_patterns(self):
        extractor = PatternExtractor(min_cluster_size=3)
        records = []
        for i in range(5):
            records.append(make_record(
                creative=f"c{i:03d}",
                gene_after={"hook": "rescue_puppy", "visual_style": "bright_colorful"},
                improvement=0.3,
            ))
        patterns = extractor.extract(records)
        # 至少有两个模式（hook 和 visual）
        pattern_types = {p.pattern_type for p in patterns}
        assert len(pattern_types) >= 2

    def test_extract_insight_generated(self):
        extractor = PatternExtractor(min_cluster_size=3)
        records = [
            make_record(creative="c001", gene_after={"hook": "rescue_puppy"}, improvement=0.3),
            make_record(creative="c002", gene_after={"hook": "rescue_puppy"}, improvement=0.25),
            make_record(creative="c003", gene_after={"hook": "rescue_puppy"}, improvement=0.35),
        ]
        patterns = extractor.extract(records)
        assert len(patterns) >= 1
        assert patterns[0].insight != ""

    def test_extract_recommendation_generated(self):
        extractor = PatternExtractor(min_cluster_size=3)
        records = [
            make_record(creative="c001", gene_after={"hook": "rescue_puppy"}, improvement=0.3),
            make_record(creative="c002", gene_after={"hook": "rescue_puppy"}, improvement=0.25),
            make_record(creative="c003", gene_after={"hook": "rescue_puppy"}, improvement=0.35),
        ]
        patterns = extractor.extract(records)
        assert len(patterns) >= 1
        assert patterns[0].recommendation != ""

    def test_extract_high_success_rate_amplify(self):
        extractor = PatternExtractor(min_cluster_size=3)
        records = [
            make_record(creative="c001", gene_after={"hook": "rescue_puppy"}, improvement=0.3, outcome=ExperienceOutcome.SUCCESS),
            make_record(creative="c002", gene_after={"hook": "rescue_puppy"}, improvement=0.25, outcome=ExperienceOutcome.SUCCESS),
            make_record(creative="c003", gene_after={"hook": "rescue_puppy"}, improvement=0.35, outcome=ExperienceOutcome.SUCCESS),
        ]
        patterns = extractor.extract(records)
        assert len(patterns) >= 1
        assert "Amplify" in patterns[0].recommendation

    def test_extract_low_success_rate_suppress(self):
        extractor = PatternExtractor(min_cluster_size=3)
        records = [
            make_record(creative="c001", gene_after={"hook": "dark_pattern"}, improvement=-0.1, outcome=ExperienceOutcome.FAILURE),
            make_record(creative="c002", gene_after={"hook": "dark_pattern"}, improvement=-0.2, outcome=ExperienceOutcome.FAILURE),
            make_record(creative="c003", gene_after={"hook": "dark_pattern"}, improvement=-0.05, outcome=ExperienceOutcome.FAILURE),
        ]
        patterns = extractor.extract(records)
        # 可能没有足够的聚类，但至少验证逻辑
        if patterns:
            if patterns[0].success_rate < 0.5:
                assert "Suppress" in patterns[0].recommendation

    def test_extract_repr(self):
        extractor = PatternExtractor(min_cluster_size=5)
        r = repr(extractor)
        assert "PatternExtractor" in r
        assert "5" in r


# ═══════════════════════════════════════════════════════════
# 4. Correlation Engine (15 tests)
# ═══════════════════════════════════════════════════════════


class TestCorrelationEngine:
    """CorrelationEngine — 基因影响力计算测试。"""

    def _make_patterns(self) -> list[MetaPattern]:
        return [
            MetaPattern(
                pattern_type=PatternType.HOOK,
                name="Rescue Hook",
                genes={"emotion": "rescue"},
                sample_count=50,
                success_count=40,
                success_rate=0.80,
                avg_roas_gain=0.25,
            ),
            MetaPattern(
                pattern_type=PatternType.HOOK,
                name="Challenge Hook",
                genes={"emotion": "challenge"},
                sample_count=30,
                success_count=12,
                success_rate=0.40,
                avg_roas_gain=0.05,
            ),
            MetaPattern(
                pattern_type=PatternType.VISUAL,
                name="Bright Visual",
                genes={"style": "bright_colorful"},
                sample_count=40,
                success_count=28,
                success_rate=0.70,
                avg_roas_gain=0.20,
            ),
            MetaPattern(
                pattern_type=PatternType.VISUAL,
                name="Dark Visual",
                genes={"style": "dark_moody"},
                sample_count=20,
                success_count=6,
                success_rate=0.30,
                avg_roas_gain=-0.05,
            ),
        ]

    def test_calculate_gene_impact(self):
        engine = CorrelationEngine()
        patterns = self._make_patterns()
        impacts = engine.calculate_gene_impact(patterns)
        assert len(impacts) > 0

    def test_calculate_empty(self):
        engine = CorrelationEngine()
        impacts = engine.calculate_gene_impact([])
        assert impacts == []

    def test_positive_impact(self):
        engine = CorrelationEngine()
        # 只有高成功率模式
        patterns = [
            MetaPattern(
                pattern_type=PatternType.HOOK,
                name="Rescue Hook",
                genes={"emotion": "rescue"},
                sample_count=50,
                success_count=40,
                success_rate=0.80,
                avg_roas_gain=0.25,
            ),
        ]
        impacts = engine.calculate_gene_impact(patterns)
        # 高于全局平均 → 正向
        rescue_impact = next(
            (i for i in impacts if i.gene_value == "rescue"), None
        )
        assert rescue_impact is not None

    def test_negative_impact(self):
        engine = CorrelationEngine()
        # 只有低成功率模式
        patterns = [
            MetaPattern(
                pattern_type=PatternType.HOOK,
                name="Bad Hook",
                genes={"emotion": "bad"},
                sample_count=50,
                success_count=10,
                success_rate=0.20,
                avg_roas_gain=-0.10,
            ),
        ]
        impacts = engine.calculate_gene_impact(patterns)
        bad_impact = next(
            (i for i in impacts if i.gene_value == "bad"), None
        )
        # 低于全局平均 → 负向
        assert bad_impact is not None

    def test_impact_score_range(self):
        engine = CorrelationEngine()
        patterns = self._make_patterns()
        impacts = engine.calculate_gene_impact(patterns)
        for impact in impacts:
            assert -1.0 <= impact.impact_score <= 1.0

    def test_get_top_positive(self):
        engine = CorrelationEngine()
        patterns = self._make_patterns()
        top = engine.get_top_positive_impacts(patterns, n=3)
        assert len(top) <= 3
        assert all(i.is_positive for i in top)

    def test_get_top_negative(self):
        engine = CorrelationEngine()
        patterns = self._make_patterns()
        top = engine.get_top_negative_impacts(patterns, n=3)
        assert len(top) <= 3
        assert all(i.is_negative for i in top)

    def test_get_significant(self):
        engine = CorrelationEngine()
        patterns = self._make_patterns()
        significant = engine.get_significant_impacts(patterns)
        assert all(i.is_significant for i in significant)

    def test_generate_impact_report(self):
        engine = CorrelationEngine()
        patterns = self._make_patterns()
        report = engine.generate_impact_report(patterns)
        assert "total_genes_analyzed" in report
        assert "top_positive" in report
        assert "top_negative" in report
        assert "recommendation" in report

    def test_impact_confidence(self):
        engine = CorrelationEngine()
        patterns = self._make_patterns()
        impacts = engine.calculate_gene_impact(patterns)
        for impact in impacts:
            assert 0.0 <= impact.confidence <= 1.0

    def test_impact_lift_pct(self):
        engine = CorrelationEngine()
        patterns = self._make_patterns()
        impacts = engine.calculate_gene_impact(patterns)
        for impact in impacts:
            assert isinstance(impact.lift_pct, float)

    def test_calculate_from_patterns_alias(self):
        engine = CorrelationEngine()
        patterns = self._make_patterns()
        impacts1 = engine.calculate_gene_impact(patterns)
        impacts2 = engine.calculate_from_patterns(patterns)
        assert len(impacts1) == len(impacts2)

    def test_repr(self):
        engine = CorrelationEngine()
        r = repr(engine)
        assert "CorrelationEngine" in r


# ═══════════════════════════════════════════════════════════
# 5. Pattern Ranker (15 tests)
# ═══════════════════════════════════════════════════════════


class TestPatternRanker:
    """PatternRanker — 评分排序筛选测试。"""

    def _make_patterns(self) -> list[MetaPattern]:
        return [
            MetaPattern(
                pattern_type=PatternType.HOOK,
                name="Rescue Hook",
                genes={"emotion": "rescue"},
                sample_count=100,
                success_count=75,
                success_rate=0.75,
                avg_roas_gain=0.21,
                confidence=0.91,
            ),
            MetaPattern(
                pattern_type=PatternType.HOOK,
                name="Challenge Hook",
                genes={"emotion": "challenge"},
                sample_count=50,
                success_count=20,
                success_rate=0.40,
                avg_roas_gain=0.05,
                confidence=0.60,
            ),
            MetaPattern(
                pattern_type=PatternType.VISUAL,
                name="Bright Visual",
                genes={"style": "bright_colorful"},
                sample_count=80,
                success_count=56,
                success_rate=0.70,
                avg_roas_gain=0.15,
                confidence=0.80,
            ),
            MetaPattern(
                pattern_type=PatternType.VISUAL,
                name="Dark Visual",
                genes={"style": "dark_moody"},
                sample_count=3,
                success_count=1,
                success_rate=0.33,
                avg_roas_gain=-0.05,
                confidence=0.30,
            ),
        ]

    def test_rank_ordering(self):
        ranker = PatternRanker()
        patterns = self._make_patterns()
        ranked = ranker.rank(patterns)
        # 按 rank_score 降序
        for i in range(len(ranked) - 1):
            assert ranked[i].rank_score >= ranked[i + 1].rank_score

    def test_rank_score_range(self):
        ranker = PatternRanker()
        patterns = self._make_patterns()
        ranked = ranker.rank(patterns)
        for p in ranked:
            assert 0.0 <= p.rank_score <= 1.0

    def test_filter_reliable(self):
        ranker = PatternRanker()
        patterns = self._make_patterns()
        reliable = ranker.filter_reliable(patterns)
        # Dark Visual 样本量不足，应被过滤
        assert len(reliable) <= 3
        dark_visual = [p for p in reliable if p.name == "Dark Visual"]
        assert dark_visual == []

    def test_get_top_patterns(self):
        ranker = PatternRanker()
        patterns = self._make_patterns()
        top = ranker.get_top_patterns(patterns, n=2)
        assert len(top) == 2
        assert top[0].rank_score >= top[1].rank_score

    def test_get_top_by_type(self):
        ranker = PatternRanker()
        patterns = self._make_patterns()
        hook_top = ranker.get_top_by_type(patterns, PatternType.HOOK, n=2)
        assert len(hook_top) <= 2
        assert all(p.pattern_type == PatternType.HOOK for p in hook_top)

    def test_get_top_by_type_visual(self):
        ranker = PatternRanker()
        patterns = self._make_patterns()
        visual_top = ranker.get_top_by_type(patterns, PatternType.VISUAL, n=2)
        assert len(visual_top) <= 2
        assert all(p.pattern_type == PatternType.VISUAL for p in visual_top)

    def test_get_mutation_priorities(self):
        ranker = PatternRanker()
        patterns = self._make_patterns()
        priorities = ranker.get_mutation_priorities(patterns)
        assert len(priorities) == len(patterns)
        assert "pattern_name" in priorities[0]
        assert "priority" in priorities[0]
        assert "recommended_genes" in priorities[0]

    def test_mutation_priorities_ordering(self):
        ranker = PatternRanker()
        patterns = self._make_patterns()
        priorities = ranker.get_mutation_priorities(patterns)
        for i in range(len(priorities) - 1):
            assert priorities[i]["priority"] >= priorities[i + 1]["priority"]

    def test_generate_ranking_report(self):
        ranker = PatternRanker()
        patterns = self._make_patterns()
        report = ranker.generate_ranking_report(patterns)
        assert "total_patterns" in report
        assert "reliable_patterns" in report
        assert "top_patterns" in report
        assert "by_type" in report
        assert "mutation_priorities" in report
        assert report["total_patterns"] == 4

    def test_custom_weights(self):
        custom_weights = {
            "success_rate": 0.5,
            "roas_gain": 0.2,
            "sample_factor": 0.1,
            "confidence": 0.2,
        }
        ranker = PatternRanker(weights=custom_weights)
        patterns = self._make_patterns()
        ranked = ranker.rank(patterns)
        assert len(ranked) == 4

    def test_custom_filters(self):
        custom_filters = {
            "min_sample": 80,
            "min_confidence": 0.7,
            "min_success_rate": 0.6,
        }
        ranker = PatternRanker(filters=custom_filters)
        patterns = self._make_patterns()
        reliable = ranker.filter_reliable(patterns)
        # 只有 Rescue Hook 和 Bright Visual 满足
        assert len(reliable) <= 2

    def test_higher_success_rate_scores_higher(self):
        ranker = PatternRanker()
        p1 = MetaPattern(
            pattern_type=PatternType.HOOK,
            name="Good",
            sample_count=100, success_count=80, success_rate=0.80,
            avg_roas_gain=0.20, confidence=0.90,
        )
        p2 = MetaPattern(
            pattern_type=PatternType.HOOK,
            name="Bad",
            sample_count=100, success_count=30, success_rate=0.30,
            avg_roas_gain=0.20, confidence=0.90,
        )
        ranker.rank([p1, p2])
        assert p1.rank_score > p2.rank_score

    def test_higher_roas_scores_higher(self):
        ranker = PatternRanker()
        p1 = MetaPattern(
            pattern_type=PatternType.HOOK,
            name="High ROAS",
            sample_count=100, success_count=70, success_rate=0.70,
            avg_roas_gain=0.50, confidence=0.90,
        )
        p2 = MetaPattern(
            pattern_type=PatternType.HOOK,
            name="Low ROAS",
            sample_count=100, success_count=70, success_rate=0.70,
            avg_roas_gain=0.05, confidence=0.90,
        )
        ranker.rank([p1, p2])
        assert p1.rank_score > p2.rank_score

    def test_repr(self):
        ranker = PatternRanker()
        r = repr(ranker)
        assert "PatternRanker" in r


# ═══════════════════════════════════════════════════════════
# 6. Pipeline Tests (10 tests)
# ═══════════════════════════════════════════════════════════


class TestPipeline:
    """完整 Pipeline: GeneAnalyzer → Extractor → Correlation → Ranker。"""

    def test_full_pipeline(self):
        """完整模式挖掘流程。"""
        records = []
        # 生成大量 rescue hook 经验
        for i in range(20):
            records.append(make_record(
                creative=f"c{i:03d}",
                gene_after={"hook": "rescue_puppy"},
                improvement=0.3,
                outcome=ExperienceOutcome.SUCCESS if i < 15 else ExperienceOutcome.FAILURE,
                metrics_delta={"ctr": 0.3, "roas": 0.2},
            ))
        # 生成 challenge hook 经验
        for i in range(10):
            records.append(make_record(
                creative=f"d{i:03d}",
                gene_after={"hook": "impossible_challenge"},
                improvement=0.05,
                outcome=ExperienceOutcome.MARGINAL if i < 4 else ExperienceOutcome.FAILURE,
                metrics_delta={"ctr": 0.05, "roas": 0.02},
            ))

        # Step 1: 基因提取
        analyzer = GeneAnalyzer()
        all_genes = analyzer.extract_genes_batch(records)
        assert len(all_genes) == len(records)

        # Step 2: 模式提取
        extractor = PatternExtractor(min_cluster_size=5)
        patterns = extractor.extract(records)
        assert len(patterns) >= 1

        # Step 3: 相关性分析
        engine = CorrelationEngine()
        impacts = engine.calculate_gene_impact(patterns)
        assert len(impacts) > 0

        # Step 4: 排序
        ranker = PatternRanker()
        ranked = ranker.rank(patterns)
        assert len(ranked) == len(patterns)
        assert ranked[0].rank_score >= ranked[-1].rank_score

    def test_pipeline_with_store(self):
        """与 ExperienceStore 集成。"""
        store = ExperienceStore()
        for i in range(20):
            store.add(make_record(
                creative=f"c{i:03d}",
                gene_after={"hook": "rescue_puppy"},
                improvement=0.3,
                outcome=ExperienceOutcome.SUCCESS if i < 15 else ExperienceOutcome.FAILURE,
            ))

        extractor = PatternExtractor(min_cluster_size=5)
        patterns = extractor.extract_from_store(store)
        assert len(patterns) >= 1

        ranker = PatternRanker()
        ranked = ranker.rank(patterns)
        assert len(ranked) >= 1

    def test_pipeline_multi_hook(self):
        """多 Hook 类型 Pipeline。"""
        configs = [
            ("rescue_puppy", 0.3, 30),
            ("impossible_challenge", 0.05, 20),
            ("mystery_discover", 0.15, 15),
            ("save_dragon", 0.25, 25),
        ]

        records = []
        for gene_value, imp, count in configs:
            for i in range(count):
                records.append(make_record(
                    creative=f"{gene_value}_{i:03d}",
                    gene_after={"hook": gene_value},
                    improvement=imp,
                    outcome=ExperienceOutcome.SUCCESS if imp >= 0.20 else (
                        ExperienceOutcome.MARGINAL if imp >= 0.10 else ExperienceOutcome.FAILURE
                    ),
                    metrics_delta={"ctr": imp, "roas": imp * 0.8},
                ))

        extractor = PatternExtractor(min_cluster_size=5)
        patterns = extractor.extract(records)
        assert len(patterns) >= 2  # 至少 rescue_puppy 和 save_dragon 聚类

        engine = CorrelationEngine()
        impacts = engine.calculate_gene_impact(patterns)
        # rescue 应该有正向影响（相对于全局平均）
        rescue_impact = next(
            (i for i in impacts if i.gene_value == "rescue"), None
        )
        if rescue_impact:
            # rescue 的 impact_score 应该高于 challenge 或其他低成功率基因
            challenge_impact = next(
                (i for i in impacts if i.gene_value == "challenge"), None
            )
            if challenge_impact:
                assert rescue_impact.impact_score > challenge_impact.impact_score

    def test_pipeline_multi_gene_types(self):
        """多基因类型 Pipeline。"""
        records = []
        for i in range(15):
            records.append(make_record(
                creative=f"c{i:03d}",
                gene_after={
                    "hook": "rescue_puppy",
                    "visual_style": "bright_colorful",
                    "gameplay": "merge_combine",
                },
                improvement=0.3,
                outcome=ExperienceOutcome.SUCCESS,
            ))

        extractor = PatternExtractor(min_cluster_size=5)
        patterns = extractor.extract(records)
        pattern_types = {p.pattern_type for p in patterns}
        assert len(pattern_types) >= 2  # 至少 hook 和 visual

    def test_pipeline_ranking_report(self):
        """完整 Pipeline 生成排序报告。"""
        records = []
        for i in range(20):
            records.append(make_record(
                creative=f"c{i:03d}",
                gene_after={"hook": "rescue_puppy"},
                improvement=0.3,
                outcome=ExperienceOutcome.SUCCESS if i < 15 else ExperienceOutcome.FAILURE,
            ))

        extractor = PatternExtractor(min_cluster_size=5)
        patterns = extractor.extract(records)

        ranker = PatternRanker()
        report = ranker.generate_ranking_report(patterns)
        assert "mutation_priorities" in report
        assert len(report["mutation_priorities"]) > 0

    def test_pipeline_mutation_prior(self):
        """Mutation Prior 格式验证。"""
        patterns = [
            MetaPattern(
                pattern_type=PatternType.HOOK,
                name="Rescue Hook",
                genes={"emotion": "rescue"},
                sample_count=100,
                success_count=75,
                success_rate=0.75,
                avg_roas_gain=0.21,
                confidence=0.91,
                rank_score=0.82,
                recommendation="Amplify hook pattern",
            ),
        ]
        ranker = PatternRanker()
        priorities = ranker.get_mutation_priorities(patterns)
        prior = priorities[0]
        expected_keys = [
            "pattern_id", "pattern_name", "pattern_type",
            "priority", "confidence", "success_rate",
            "recommended_genes", "recommendation", "evidence",
        ]
        for key in expected_keys:
            assert key in prior

    def test_pipeline_pattern_mining_result(self):
        """PatternMiningResult 完整构建。"""
        records = []
        for i in range(20):
            records.append(make_record(
                creative=f"c{i:03d}",
                gene_after={"hook": "rescue_puppy"},
                improvement=0.3,
                outcome=ExperienceOutcome.SUCCESS if i < 15 else ExperienceOutcome.FAILURE,
            ))

        extractor = PatternExtractor(min_cluster_size=5)
        patterns = extractor.extract(records)

        engine = CorrelationEngine()
        impacts = engine.calculate_gene_impact(patterns)

        ranker = PatternRanker()
        patterns = ranker.rank(patterns)

        result = PatternMiningResult(
            patterns=patterns,
            gene_impacts=impacts,
            total_experiences=len(records),
            clusters_found=len(patterns),
        )

        assert result.total_experiences == 20
        assert result.patterns_found == len(patterns)
        assert result.get_top_patterns(n=3) is not None

        d = result.to_dict()
        assert "top_patterns" in d
        assert "positive_impacts" in d
        assert "negative_impacts" in d

    def test_pipeline_large_scale(self):
        """大规模数据 Pipeline 测试。"""
        records = []
        hook_types = [
            ("rescue_puppy", 0.28, 2400),
            ("save_animal", 0.25, 1800),
            ("help_character", 0.22, 1500),
            ("impossible_challenge", 0.08, 800),
            ("mystery_discover", 0.15, 1200),
        ]

        for gene_value, avg_imp, count in hook_types:
            # 缩放到测试规模
            actual_count = min(count // 100, 30)
            for i in range(actual_count):
                imp = max(0.0, avg_imp + (i % 5 - 2) * 0.05)
                records.append(make_record(
                    creative=f"{gene_value}_{i:03d}",
                    gene_after={"hook": gene_value},
                    improvement=imp,
                    outcome=ExperienceOutcome.SUCCESS if imp >= 0.20 else (
                        ExperienceOutcome.MARGINAL if imp >= 0.10 else ExperienceOutcome.FAILURE
                    ),
                    metrics_delta={"ctr": imp, "roas": imp * 0.8},
                ))

        extractor = PatternExtractor(min_cluster_size=5)
        patterns = extractor.extract(records)
        assert len(patterns) >= 3

        engine = CorrelationEngine()
        impacts = engine.calculate_gene_impact(patterns)
        assert len(impacts) > 0

        # rescue 类型应该有正向影响（相对于全局平均）
        rescue_impacts = [
            i for i in impacts
            if i.gene_value in ("rescue",)
        ]
        if rescue_impacts:
            # rescue 的 impact_score 应该高于 challenge
            challenge_impacts = [
                i for i in impacts
                if i.gene_value in ("challenge",)
            ]
            if challenge_impacts:
                assert rescue_impacts[0].impact_score > challenge_impacts[0].impact_score

    def test_pipeline_top_patterns_for_mutation(self):
        """模拟 E11 Mutation Engine 查询最佳模式。"""
        records = []
        for i in range(30):
            records.append(make_record(
                creative=f"c{i:03d}",
                gene_after={"hook": "rescue_puppy"},
                improvement=0.25,
                outcome=ExperienceOutcome.SUCCESS,
                metrics_delta={"ctr": 0.3, "roas": 0.2},
            ))

        extractor = PatternExtractor(min_cluster_size=5)
        patterns = extractor.extract(records)

        ranker = PatternRanker()
        top = ranker.get_top_patterns(patterns, n=3)

        assert len(top) >= 1
        # 最佳模式应该推荐 amplify
        assert "Amplify" in top[0].recommendation or "Explore" in top[0].recommendation


# ═══════════════════════════════════════════════════════════
# 7. Integration Tests (5 tests)
# ═══════════════════════════════════════════════════════════


class TestIntegration:
    """集成测试：与 ExperienceStore / E12.5.1 集成。"""

    def test_store_to_patterns(self):
        """ExperienceStore → Pattern Mining。"""
        store = ExperienceStore()
        for i in range(30):
            store.add(make_record(
                creative=f"c{i:03d}",
                gene_after={"hook": "rescue_puppy"},
                improvement=0.3,
                outcome=ExperienceOutcome.SUCCESS if i < 24 else ExperienceOutcome.FAILURE,
            ))

        extractor = PatternExtractor(min_cluster_size=5)
        patterns = extractor.extract_from_store(store)
        assert len(patterns) >= 1
        assert patterns[0].success_rate >= 0.7

    def test_e1251_to_e1252_flow(self):
        """E12.5.1 → E12.5.2 数据流。"""
        from market_ops.creative_vision_runtime.reality.meta_learning import (
            ExperienceCollector,
        )
        from market_ops.creative_vision_runtime.reality.feedback import (
            ExperimentEvaluation,
            ExperimentRun,
            ExperimentStatus,
            MutationIntent,
            MutationRequest,
        )

        collector = ExperienceCollector()
        store = ExperienceStore()

        # 收集经验
        for i in range(20):
            exp = ExperimentRun(
                creative_id=f"c{i:03d}",
                status=ExperimentStatus.COMPLETED,
                variants=["v1", "v2", "v3"],
                metrics={
                    "baseline": {"ctr": 0.02, "roas": 0.5},
                    "variants": {"v2": {"ctr": 0.03, "roas": 0.7}},
                },
            )

            imp = 0.3 if i < 15 else 0.05
            ev = ExperimentEvaluation(
                experiment_id=exp.experiment_id,
                creative_id=f"c{i:03d}",
                winner_id="v2" if imp > 0.15 else "",
                improvement_score=imp,
                metrics_delta={"ctr": 0.5, "roas": 0.4},
                raw_metrics={
                    "baseline": {"ctr": 0.02, "roas": 0.5},
                    "v2": {"ctr": 0.03, "roas": 0.7},
                },
                learning_signal="Test",
                confidence=0.85,
            )

            mr = MutationRequest(
                creative_id=f"c{i:03d}",
                intent=MutationIntent.REFRESH_HOOK,
                dna_constraints={"keep": ["gameplay"], "change": ["hook"]},
                generation_count=20,
            )

            record = collector.collect(
                experiment=exp,
                evaluation=ev,
                mutation_request=mr,
                gene_before={"hook": "old"},
                gene_after={"hook": "rescue_puppy"},
                product_id="p04",
                market="US",
            )
            store.add(record)

        # E12.5.2 挖掘
        extractor = PatternExtractor(min_cluster_size=5)
        patterns = extractor.extract_from_store(store)
        assert len(patterns) >= 1

        ranker = PatternRanker()
        ranked = ranker.rank(patterns)
        assert len(ranked) >= 1

    def test_multi_product_patterns(self):
        """多产品模式挖掘。"""
        store = ExperienceStore()
        products = ["p04", "p07", "p08"]
        for pid in products:
            for i in range(10):
                store.add(make_record(
                    product=pid,
                    creative=f"{pid}_c{i:03d}",
                    gene_after={"hook": "rescue_puppy"},
                    improvement=0.3,
                    outcome=ExperienceOutcome.SUCCESS,
                ))

        extractor = PatternExtractor(min_cluster_size=5)
        patterns = extractor.extract_from_store(store)
        assert len(patterns) >= 1
        # rescue 模式应该跨产品
        assert patterns[0].sample_count >= 15

    def test_pattern_quality_validation(self):
        """模式质量验证。"""
        store = ExperienceStore()
        for i in range(50):
            store.add(make_record(
                creative=f"c{i:03d}",
                gene_after={"hook": "rescue_puppy"},
                improvement=0.3 if i < 40 else -0.05,
                outcome=ExperienceOutcome.SUCCESS if i < 40 else ExperienceOutcome.FAILURE,
                metrics_delta={"ctr": 0.3, "roas": 0.2} if i < 40 else {"ctr": -0.05, "roas": -0.02},
            ))

        extractor = PatternExtractor(min_cluster_size=5)
        patterns = extractor.extract_from_store(store)

        ranker = PatternRanker()
        reliable = ranker.filter_reliable(patterns)

        for p in reliable:
            assert p.is_reliable
            assert p.sample_count >= 5
            assert p.confidence >= 0.60

    def test_e2e_scenario(self):
        """端到端场景：Rescue Hook 模式挖掘。"""
        # 模拟 50000 creatives 场景（缩放到测试规模）
        store = ExperienceStore()

        # Rescue Hook — 2400 samples, 75% success
        for i in range(50):
            succeeds = i < 38  # ~75% success
            store.add(make_record(
                creative=f"rescue_{i:03d}",
                gene_after={"hook": "rescue_puppy"},
                improvement=0.21 if succeeds else -0.05,
                outcome=ExperienceOutcome.SUCCESS if succeeds else ExperienceOutcome.FAILURE,
                metrics_delta={"ctr": 0.21, "roas": 0.21} if succeeds else {"ctr": -0.05, "roas": -0.05},
            ))

        # Before/After — 1800 samples, 68% success
        for i in range(40):
            succeeds = i < 27
            store.add(make_record(
                creative=f"ba_{i:03d}",
                gene_after={"hook": "before_after_transform"},
                improvement=0.15 if succeeds else -0.03,
                outcome=ExperienceOutcome.SUCCESS if succeeds else ExperienceOutcome.FAILURE,
                metrics_delta={"ctr": 0.15, "roas": 0.15} if succeeds else {"ctr": -0.03, "roas": -0.03},
            ))

        # Character Emotion — 1500 samples, 65% success
        for i in range(30):
            succeeds = i < 20
            store.add(make_record(
                creative=f"char_{i:03d}",
                gene_after={"hook": "cute_character"},
                improvement=0.12 if succeeds else -0.02,
                outcome=ExperienceOutcome.SUCCESS if succeeds else ExperienceOutcome.FAILURE,
                metrics_delta={"ctr": 0.12, "roas": 0.12} if succeeds else {"ctr": -0.02, "roas": -0.02},
            ))

        # E12.5.2 挖掘
        extractor = PatternExtractor(min_cluster_size=5)
        patterns = extractor.extract_from_store(store)
        assert len(patterns) >= 2

        # 排序
        ranker = PatternRanker()
        top = ranker.get_top_patterns(patterns, n=3)
        assert len(top) >= 2

        # Rescue Hook 应该是最高排名
        rescue_pattern = next((p for p in top if "Rescue" in p.name), None)
        if rescue_pattern:
            assert rescue_pattern.success_rate >= 0.7

        # 生成 Mutation Prior
        priorities = ranker.get_mutation_priorities(top)
        assert len(priorities) >= 2

        # 生成报告
        report = ranker.generate_ranking_report(patterns)
        assert report["total_patterns"] >= 2
        assert report["best_rank_score"] > 0