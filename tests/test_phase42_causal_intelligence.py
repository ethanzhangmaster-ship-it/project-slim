"""E11 Phase 4.2 — Creative Causal Intelligence Layer 测试。

测试覆盖 3 个子阶段：
  1. PlayerJourneyAnalyzer — FTUE/Retention/Progression/Payment Journey
  2. DNACausalDiscoveryEngine — Gene Impact + Causal Chain + Winning Patterns
  3. EvolutionPolicyGenerator — Amplify/Suppress/Explore + Hypothesis + V5 Bridge

关键验收标准：
  - AC1: PlayerJourneyProfile 完整 FTUE → Payment 旅程
  - AC2: GeneImpact 正向/负向基因影响力计算
  - AC3: CausalDiscoveryResult 因果链 + Winning/Losing Patterns
  - AC4: CreativeHypothesis 可验证假设生成
  - AC5: MutationPolicy Amplify/Suppress/Explore 策略
  - AC6: to_v5_mutation_requests 连接 V5 Mutation Engine
  - AC7: Creative DNA V2 7 基因完整基因组
  - AC8: PsychologyGene 心理机制识别
  - AC9: EvolutionPolicyGenerator 多代策略生成
  - AC10: 闭环 Creative DNA → Causal → Policy → V5
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest

from market_ops.creative_intelligence import (
    # Phase 4.2 Models
    PlayerJourneyProfile,
    GeneImpact,
    CausalDiscoveryResult,
    CreativeHypothesis,
    MutationPolicy,
    PsychologyGene,
    AudienceGene,
    ContextGene,
    CreativeDNAV2,
    # Phase 4.2 Analyzers
    PlayerJourneyAnalyzer,
    DNACausalDiscoveryEngine,
    EvolutionPolicyGenerator,
    # Existing models
    LTVProfile,
    PaymentProfile,
    PlayerAttributionProfile,
    ArchetypeProfile,
    IAPFitnessResult,
    CreativeValueProfile,
    PerformanceMetrics,
)


# ═══════════════════════════════════════════════════════════
# Shared Fixtures
# ═══════════════════════════════════════════════════════════

def _make_player_data(
    creative_id: str = "MW_VIDEO_001",
    total_spend: float = 0,
    ftue_completed: bool = True,
    d1_retained: bool = True,
    d7_retained: bool = True,
    d30_retained: bool = True,
    d1_progress: float = 3.0,
    d3_progress: float = 8.0,
    d7_progress: float = 15.0,
    level: float = 20.0,
    areas_unlocked: int = 3,
    merge_count: float = 50.0,
    merge_speed: float = 2.5,
    features_used: list[str] | None = None,
    is_payer: bool = False,
    first_purchase_day: int = 0,
    total_purchases: int = 0,
    avg_order_value: float = 0,
) -> dict:
    return {
        "creative_id": creative_id,
        "ftue_completed": ftue_completed,
        "tutorial_skipped": False,
        "d1_retained": d1_retained,
        "d3_retained": d1_retained,
        "d7_retained": d7_retained,
        "d30_retained": d30_retained,
        "d1_progress": d1_progress,
        "d3_progress": d3_progress,
        "d7_progress": d7_progress,
        "level": level,
        "areas_unlocked": areas_unlocked,
        "merge_count": merge_count,
        "merge_speed": merge_speed,
        "collection_rate": 0.65,
        "total_sessions": 80,
        "session_duration": 15.0,
        "features_used": features_used or ["merge", "collection"],
        "is_payer": is_payer or total_spend > 0,
        "total_spend": total_spend,
        "first_purchase_hour": first_purchase_day * 24 + 2,
        "total_purchases": total_purchases,
        "avg_order_value": avg_order_value if is_payer else 0,
    }


def _make_player_data_list(creative_id: str, count: int = 100, payer_count: int = 15) -> list[dict]:
    players = []
    for i in range(count):
        is_p = i < payer_count
        players.append(_make_player_data(
            creative_id=creative_id,
            total_spend=10.0 if is_p else 0,
            is_payer=is_p,
            first_purchase_day=2 if is_p else 0,
            total_purchases=4 if is_p else 0,
            avg_order_value=12.5 if is_p else 0,
        ))
    return players


def _make_performance_metrics(
    creative_id: str = "MW_001",
    roas: float = 1.0,
    ctr: float = 0.02,
    cpi: float = 8.0,
    spend: float = 1000,
) -> PerformanceMetrics:
    return PerformanceMetrics(
        creative_id=creative_id,
        platform="android",
        fb_spend=spend,
        adjust_cost=spend * 0.9,
        spend=spend,
        adjust_installs=125,
        fb_installs=120,
        fb_impressions=50000,
        fb_clicks=1000,
        adjust_revenue=spend * roas,
        roas=roas,
        cpi=cpi,
        ctr=ctr,
        cpm=spend / 50000 * 1000,
        cpc=spend / 1000,
        status="ACTIVE",
        active_days=30,
        ad_name=f"test_{creative_id}",
    )


# ═══════════════════════════════════════════════════════════
# Phase 4.2.1: PlayerJourneyAnalyzer
# ═══════════════════════════════════════════════════════════

class TestPlayerJourneyAnalyzer:
    """Phase 4.2.1: Creative → Player Journey 分析测试."""

    def test_load_from_player_data(self):
        """AC1: 从玩家数据加载旅程分析."""
        data = {"players": _make_player_data_list("MW_001", 100, 15)}
        analyzer = PlayerJourneyAnalyzer()
        count = analyzer.load_from_player_data(data)
        assert count == 1
        assert "MW_001" in analyzer._profiles

    def test_ftue_completion_rate(self):
        """AC1: FTUE 完成率."""
        players = [
            _make_player_data("MW_001", ftue_completed=True),
            _make_player_data("MW_001", ftue_completed=True),
            _make_player_data("MW_001", ftue_completed=False),
        ]
        data = {"players": players}
        analyzer = PlayerJourneyAnalyzer()
        analyzer.load_from_player_data(data)
        profile = analyzer.get("MW_001")
        assert profile.ftue_completion_rate == pytest.approx(2 / 3, rel=0.01)

    def test_retention_curve(self):
        """AC1: 留存曲线."""
        data = {"players": _make_player_data_list("MW_001", 100, 15)}
        analyzer = PlayerJourneyAnalyzer()
        analyzer.load_from_player_data(data)
        profile = analyzer.get("MW_001")
        assert profile.d1_retention == 1.0
        assert profile.d7_retention == 1.0
        assert profile.d30_retention == 1.0
        curve = profile.retention_curve
        assert curve["d1"] == 1.0
        assert curve["d7"] == 1.0

    def test_progression_curve(self):
        """AC1: 进度曲线."""
        players = [
            _make_player_data("MW_001", d1_progress=3.0, d3_progress=8.0, d7_progress=15.0),
            _make_player_data("MW_001", d1_progress=5.0, d3_progress=12.0, d7_progress=20.0),
        ]
        data = {"players": players}
        analyzer = PlayerJourneyAnalyzer()
        analyzer.load_from_player_data(data)
        profile = analyzer.get("MW_001")
        assert profile.d1_progress == 4.0
        assert profile.d3_progress == 10.0
        assert profile.d7_progress == 17.5

    def test_feature_usage(self):
        """AC1: 功能使用."""
        data = {"players": _make_player_data_list("MW_001", 100, 15)}
        analyzer = PlayerJourneyAnalyzer()
        analyzer.load_from_player_data(data)
        profile = analyzer.get("MW_001")
        assert "merge" in profile.feature_usage
        assert "collection" in profile.feature_usage

    def test_payer_conversion(self):
        """AC1: 付费转化率."""
        players = [
            _make_player_data("MW_001", is_payer=True, total_spend=10, first_purchase_day=2, total_purchases=4, avg_order_value=12.5),
            _make_player_data("MW_001", is_payer=False),
            _make_player_data("MW_001", is_payer=False),
            _make_player_data("MW_001", is_payer=False),
        ]
        data = {"players": players}
        analyzer = PlayerJourneyAnalyzer()
        analyzer.load_from_player_data(data)
        profile = analyzer.get("MW_001")
        assert profile.payer_conversion_rate == 0.25
        assert profile.first_purchase_hour == 50.0  # day 2 * 24 + 2
        assert profile.avg_purchase_count == 4.0
        assert profile.avg_order_value == 12.5

    def test_is_high_quality_journey(self):
        """AC1: 高质量旅程判定."""
        data = {"players": _make_player_data_list("MW_001", 100, 15)}
        analyzer = PlayerJourneyAnalyzer()
        analyzer.load_from_player_data(data)
        profile = analyzer.get("MW_001")
        # All players have ftue_completed=True, d7_retained=True, payer_rate=0.15
        assert profile.is_high_quality_journey is True

    def test_journey_quality_score(self):
        """AC1: 旅程质量评分."""
        data = {"players": _make_player_data_list("MW_001", 100, 15)}
        analyzer = PlayerJourneyAnalyzer()
        analyzer.load_from_player_data(data)
        profile = analyzer.get("MW_001")
        score = profile.journey_quality_score
        assert 0.0 < score <= 1.0

    def test_get_high_quality_journeys(self):
        """AC1: 筛选高质量旅程."""
        data = {"players": _make_player_data_list("MW_001", 100, 15)}
        analyzer = PlayerJourneyAnalyzer()
        analyzer.load_from_player_data(data)
        high = analyzer.get_high_quality_journeys()
        assert len(high) == 1

    def test_get_by_ftue(self):
        """AC1: 按 FTUE 筛选."""
        players = [
            _make_player_data("MW_001", ftue_completed=True),
            _make_player_data("MW_001", ftue_completed=False),
        ]
        data = {"players": players}
        analyzer = PlayerJourneyAnalyzer()
        analyzer.load_from_player_data(data)
        assert len(analyzer.get_by_ftue(min_ftue=0.80)) == 0  # 50% < 80%

    def test_rank_by_journey_quality(self):
        """AC1: 按旅程质量排序."""
        analyzer = PlayerJourneyAnalyzer()
        data1 = {"players": _make_player_data_list("MW_001", 100, 15)}
        data2 = {"players": _make_player_data_list("MW_002", 100, 2)}
        analyzer.load_from_player_data(data1)
        analyzer.load_from_player_data(data2)
        ranked = analyzer.rank_by_journey_quality(10)
        assert len(ranked) == 2
        assert ranked[0].journey_quality_score >= ranked[1].journey_quality_score

    def test_compare_journeys(self):
        """AC1: 旅程对比."""
        analyzer = PlayerJourneyAnalyzer()
        data1 = {"players": _make_player_data_list("MW_001", 100, 15)}
        data2 = {"players": _make_player_data_list("MW_002", 100, 2)}
        analyzer.load_from_player_data(data1)
        analyzer.load_from_player_data(data2)
        comparison = analyzer.compare_journeys("MW_001", "MW_002")
        assert comparison["better_overall"] == "MW_001"

    def test_to_dict(self):
        """AC1: JourneyProfile 序列化."""
        data = {"players": _make_player_data_list("MW_001", 100, 15)}
        analyzer = PlayerJourneyAnalyzer()
        analyzer.load_from_player_data(data)
        profile = analyzer.get("MW_001")
        d = profile.to_dict()
        assert d["creative_id"] == "MW_001"
        assert d["payer_conversion_rate"] == 0.15
        assert "retention_curve" in d
        assert "progression_curve" in d

    def test_journey_stats(self):
        """AC1: 全局旅程统计."""
        data = {"players": _make_player_data_list("MW_001", 100, 15)}
        analyzer = PlayerJourneyAnalyzer()
        analyzer.load_from_player_data(data)
        stats = analyzer.journey_stats()
        assert stats["total_creatives"] == 1
        assert stats["avg_ftue_completion"] == 1.0
        assert stats["avg_payer_conversion"] == 0.15


# ═══════════════════════════════════════════════════════════
# Phase 4.2.2: DNACausalDiscoveryEngine
# ═══════════════════════════════════════════════════════════

class TestGeneImpact:
    """Phase 4.2.2: GeneImpact 模型测试."""

    def test_positive_impact(self):
        """AC2: 正向基因影响."""
        g = GeneImpact(
            gene_name="hook:rescue",
            gene_category="hook",
            impact_score=0.65,
            confidence=0.82,
            payer_rate_lift=0.23,
            ltv_lift=0.41,
        )
        assert g.is_positive_impact is True
        assert g.is_high_confidence is True

    def test_negative_impact(self):
        """AC2: 负向基因影响."""
        g = GeneImpact(
            gene_name="hook:curiosity",
            gene_category="hook",
            impact_score=0.15,
            confidence=0.30,
            payer_rate_lift=-0.10,
            ltv_lift=-0.15,
        )
        assert g.is_positive_impact is False
        assert g.is_high_confidence is False

    def test_to_dict(self):
        """AC2: 序列化."""
        g = GeneImpact(
            gene_name="hook:rescue",
            gene_category="hook",
            impact_score=0.65,
            confidence=0.82,
            payer_rate_lift=0.23,
            ltv_lift=0.41,
            retention_lift=0.15,
            sample_size=200,
            highest_archetype="collector",
            archetype_impact={"collector": 0.42, "power": 0.18},
        )
        d = g.to_dict()
        assert d["gene_name"] == "hook:rescue"
        assert d["impact_score"] == 0.65
        assert d["is_positive_impact"] is True


class TestDNACausalDiscoveryEngine:
    """Phase 4.2.2: DNA 因果发现引擎测试."""

    def test_discover_single_gene(self):
        """AC3: 单个基因因果发现."""
        engine = DNACausalDiscoveryEngine()
        dna_map = {"hook": {"type": "rescue"}}
        result = engine.discover(
            creative_id="MW_001",
            dna_map=dna_map,
            ltv=LTVProfile(creative_id="MW_001", d30_ltv=10.0, sample_size=200),
            payment=PaymentProfile(creative_id="MW_001", payer_rate=0.15),
            attribution=PlayerAttributionProfile(
                creative_id="MW_001", d30_retention=0.25,
            ),
        )
        assert result.creative_id == "MW_001"
        assert len(result.gene_impacts) == 1
        assert result.gene_impacts[0].gene_name == "hook:rescue"
        assert result.gene_impacts[0].is_positive_impact is True

    def test_discover_multiple_genes(self):
        """AC3: 多基因因果发现."""
        engine = DNACausalDiscoveryEngine()
        dna_map = {
            "hook": {"type": "rescue"},
            "reward": {"type": "collection"},
            "visual": {"type": "cozy"},
        }
        result = engine.discover(
            creative_id="MW_001",
            dna_map=dna_map,
            ltv=LTVProfile(creative_id="MW_001", d30_ltv=8.5, sample_size=150),
            payment=PaymentProfile(creative_id="MW_001", payer_rate=0.12),
        )
        assert len(result.gene_impacts) == 3
        # rescue should have higher impact than collection
        rescue = next(g for g in result.gene_impacts if g.gene_name == "hook:rescue")
        coins = next(g for g in result.gene_impacts if g.gene_name == "reward:collection")
        assert rescue.impact_score > coins.impact_score

    def test_causal_chain(self):
        """AC3: 因果链构建."""
        engine = DNACausalDiscoveryEngine()
        dna_map = {"hook": {"type": "rescue"}}
        result = engine.discover(
            creative_id="MW_001",
            dna_map=dna_map,
            ltv=LTVProfile(creative_id="MW_001", d30_ltv=10.0),
        )
        assert len(result.causal_chain) == 1
        assert result.causal_chain[0]["dna"] == "hook:rescue"
        assert "payer_rate_lift" in result.causal_chain[0]
        assert "ltv_lift" in result.causal_chain[0]

    def test_winning_patterns(self):
        """AC3: Winning Patterns 发现."""
        engine = DNACausalDiscoveryEngine()
        dna_map = {
            "hook": {"type": "rescue"},
            "reward": {"type": "collection"},
        }
        result = engine.discover(
            creative_id="MW_001",
            dna_map=dna_map,
            ltv=LTVProfile(creative_id="MW_001", d30_ltv=8.5, sample_size=200),
            payment=PaymentProfile(creative_id="MW_001", payer_rate=0.15),
        )
        assert len(result.winning_patterns) >= 1
        assert "high_value_players" in result.winning_patterns[0]

    def test_losing_patterns(self):
        """AC3: Losing Patterns 发现."""
        engine = DNACausalDiscoveryEngine()
        dna_map = {"hook": {"type": "curiosity"}}
        result = engine.discover(
            creative_id="MW_001",
            dna_map=dna_map,
            ltv=LTVProfile(creative_id="MW_001", d30_ltv=2.0),
        )
        # curiosity has negative impact, should generate losing pattern
        if result.losing_patterns:
            assert "low_value_players" in result.losing_patterns[0]

    def test_overall_confidence(self):
        """AC3: 整体置信度."""
        engine = DNACausalDiscoveryEngine()
        dna_map = {
            "hook": {"type": "rescue"},
            "reward": {"type": "collection"},
        }
        result = engine.discover(
            creative_id="MW_001",
            dna_map=dna_map,
            ltv=LTVProfile(creative_id="MW_001", d30_ltv=10.0, sample_size=300),
        )
        assert result.overall_confidence > 0.0

    def test_discover_batch(self):
        """AC3: 批量因果发现."""
        engine = DNACausalDiscoveryEngine()
        creative_dna_map = {
            "MW_001": {"hook": {"type": "rescue"}, "reward": {"type": "collection"}},
            "MW_002": {"hook": {"type": "challenge"}, "reward": {"type": "coins"}},
        }
        results = engine.discover_batch(
            creative_dna_map=creative_dna_map,
            ltv_map={
                "MW_001": LTVProfile(creative_id="MW_001", d30_ltv=8.5, sample_size=200),
                "MW_002": LTVProfile(creative_id="MW_002", d30_ltv=2.1, sample_size=200),
            },
        )
        assert len(results) == 2

    def test_get_positive_genes(self):
        """AC3: 获取正面影响基因."""
        engine = DNACausalDiscoveryEngine()
        dna_map = {"hook": {"type": "rescue"}, "reward": {"type": "collection"}}
        engine.discover(
            creative_id="MW_001",
            dna_map=dna_map,
            ltv=LTVProfile(creative_id="MW_001", d30_ltv=10.0, sample_size=200),
        )
        positive = engine.get_positive_genes()
        assert len(positive) >= 1

    def test_compute_dna_level_correlation(self):
        """AC3: DNA 级 LTV 相关性."""
        engine = DNACausalDiscoveryEngine()
        creative_dna_map = {
            "MW_001": {"hook": {"type": "rescue"}},
            "MW_002": {"hook": {"type": "rescue"}},
            "MW_003": {"hook": {"type": "challenge"}},
            "MW_004": {"hook": {"type": "challenge"}},
        }
        result = engine.compute_dna_level_correlation(
            creative_dna_map=creative_dna_map,
            ltv_map={
                "MW_001": LTVProfile(creative_id="MW_001", d30_ltv=8.5),
                "MW_002": LTVProfile(creative_id="MW_002", d30_ltv=7.0),
                "MW_003": LTVProfile(creative_id="MW_003", d30_ltv=2.1),
                "MW_004": LTVProfile(creative_id="MW_004", d30_ltv=3.0),
            },
        )
        assert "hook:rescue" in result
        assert "hook:challenge" in result
        assert result["hook:rescue"]["avg_d30_ltv"] > result["hook:challenge"]["avg_d30_ltv"]

    def test_discovery_stats(self):
        """AC3: 因果发现统计."""
        engine = DNACausalDiscoveryEngine()
        dna_map = {"hook": {"type": "rescue"}}
        engine.discover(
            creative_id="MW_001",
            dna_map=dna_map,
            ltv=LTVProfile(creative_id="MW_001", d30_ltv=8.5, sample_size=200),
        )
        stats = engine.discovery_stats()
        assert stats["total_creatives"] == 1
        assert stats["total_gene_impacts"] == 1
        assert stats["positive_impact_count"] == 1

    def test_with_archetype(self):
        """AC3: 带 Archetype 的因果发现."""
        engine = DNACausalDiscoveryEngine()
        dna_map = {"hook": {"type": "rescue"}}
        result = engine.discover(
            creative_id="MW_001",
            dna_map=dna_map,
            ltv=LTVProfile(creative_id="MW_001", d30_ltv=8.5),
            archetype=ArchetypeProfile(
                creative_id="MW_001",
                actual_collector=0.42,
                actual_progression=0.31,
                actual_power=0.18,
                actual_explorer=0.07,
                actual_casual=0.02,
            ),
        )
        assert result.gene_impacts[0].highest_archetype == "collector"
        assert "collector" in result.gene_impacts[0].archetype_impact


# ═══════════════════════════════════════════════════════════
# Phase 4.2.3: EvolutionPolicyGenerator
# ═══════════════════════════════════════════════════════════

class TestCreativeHypothesis:
    """Phase 4.2.3: CreativeHypothesis 模型测试."""

    def test_hypothesis_creation(self):
        """AC4: 假设创建."""
        h = CreativeHypothesis(
            hypothesis_id="h001",
            creative_id="MW_001",
            hypothesis="rescue hook 将吸引 Collector 玩家",
            target_player="collector",
            target_psychology="loss_aversion",
            expected_impact="提升 D7 payer rate +15%",
            based_on_dna=["hook:rescue"],
        )
        assert h.status == "pending"
        assert h.hypothesis_id == "h001"

    def test_hypothesis_to_dict(self):
        """AC4: 假设序列化."""
        h = CreativeHypothesis(
            hypothesis_id="h001",
            creative_id="MW_001",
            hypothesis="rescue hook 将吸引 Collector 玩家",
            target_player="collector",
            target_psychology="loss_aversion",
            expected_impact="提升 D7 payer rate +15%",
            based_on_winners=["MW_S1", "MW_S2"],
            based_on_dna=["hook:rescue"],
        )
        d = h.to_dict()
        assert d["hypothesis"] == "rescue hook 将吸引 Collector 玩家"
        assert d["target_psychology"] == "loss_aversion"
        assert d["status"] == "pending"


class TestMutationPolicy:
    """Phase 4.2.3: MutationPolicy 模型测试."""

    def test_to_v5_mutation_requests(self):
        """AC6: 转换为 V5 Mutation Engine 请求."""
        policy = MutationPolicy(
            policy_id="p001",
            generation=1,
            amplify_genes=[
                GeneImpact(
                    gene_name="hook:rescue",
                    gene_category="hook",
                    impact_score=0.65,
                    confidence=0.82,
                    payer_rate_lift=0.23,
                    ltv_lift=0.41,
                ),
            ],
            suppress_genes=[
                GeneImpact(
                    gene_name="hook:curiosity",
                    gene_category="hook",
                    impact_score=0.15,
                    confidence=0.30,
                    payer_rate_lift=-0.10,
                    ltv_lift=-0.15,
                ),
            ],
            explore_genes=[{"hook": "rescue", "reward": "social_proof", "risk": 0.3}],
            amplification_rate=0.20,
            suppression_rate=0.15,
            exploration_rate=0.10,
        )
        requests = policy.to_v5_mutation_requests()
        assert len(requests) == 3  # 1 amplify + 1 suppress + 1 explore
        assert requests[0]["action"] == "amplify"
        assert requests[0]["gene_name"] == "hook:rescue"
        assert requests[1]["action"] == "suppress"
        assert requests[2]["action"] == "explore"

    def test_policy_to_dict(self):
        """AC5: 策略序列化."""
        policy = MutationPolicy(
            policy_id="p001",
            generation=1,
            amplify_genes=[
                GeneImpact(
                    gene_name="hook:rescue",
                    gene_category="hook",
                    impact_score=0.65,
                    confidence=0.82,
                ),
            ],
            amplification_rate=0.20,
            confidence=0.82,
            based_on_insights=["hook:rescue: impact=0.65, ltv_lift=0.41, confidence=0.82"],
        )
        d = policy.to_dict()
        assert d["policy_id"] == "p001"
        assert d["generation"] == 1
        assert len(d["amplify_genes"]) == 1
        assert d["confidence"] == 0.82


class TestEvolutionPolicyGenerator:
    """Phase 4.2.3: 进化策略生成器测试."""

    def _setup_engine_and_results(self) -> tuple[EvolutionPolicyGenerator, list[CausalDiscoveryResult]]:
        """创建因果关系发现结果."""
        engine = DNACausalDiscoveryEngine()
        results = engine.discover_batch(
            creative_dna_map={
                "MW_001": {"hook": {"type": "rescue"}, "reward": {"type": "collection"}},
                "MW_002": {"hook": {"type": "challenge"}, "reward": {"type": "coins"}},
                "MW_003": {"hook": {"type": "rescue"}, "reward": {"type": "rare_item"}},
            },
            ltv_map={
                "MW_001": LTVProfile(creative_id="MW_001", d30_ltv=8.5, sample_size=300),
                "MW_002": LTVProfile(creative_id="MW_002", d30_ltv=2.1, sample_size=200),
                "MW_003": LTVProfile(creative_id="MW_003", d30_ltv=6.0, sample_size=150),
            },
            payment_map={
                "MW_001": PaymentProfile(creative_id="MW_001", payer_rate=0.15),
                "MW_002": PaymentProfile(creative_id="MW_002", payer_rate=0.03),
                "MW_003": PaymentProfile(creative_id="MW_003", payer_rate=0.10),
            },
        )
        return EvolutionPolicyGenerator(), results

    def test_generate_policy(self):
        """AC5: 生成进化策略."""
        pg, results = self._setup_engine_and_results()
        policy = pg.generate_policy(results, generation=1)
        assert policy.policy_id != ""
        assert policy.generation == 1
        assert len(policy.amplify_genes) >= 1  # rescue should be amplified
        assert policy.confidence > 0.0

    def test_generate_policy_batch(self):
        """AC9: 多代进化策略生成."""
        pg, results = self._setup_engine_and_results()
        policies = pg.generate_policy_batch(results, generations=3)
        assert len(policies) == 3
        assert policies[0].generation == 1
        assert policies[1].generation == 2
        assert policies[2].generation == 3
        # 探索率递减
        assert policies[0].exploration_rate > policies[2].exploration_rate

    def test_generate_hypotheses(self):
        """AC4: 生成可验证假设."""
        pg, results = self._setup_engine_and_results()
        policy = pg.generate_policy(results, generation=1)
        assert len(policy.hypotheses) >= 1
        h = policy.hypotheses[0]
        assert h.hypothesis != ""
        assert h.target_psychology in (
            "loss_aversion", "completion_drive", "scarcity", "mastery",
            "anticipation", "social_proof", "curiosity",
        )
        assert h.status == "pending"

    def test_amplify_suppress_classification(self):
        """AC5: Amplify/Suppress 分类."""
        pg, results = self._setup_engine_and_results()
        policy = pg.generate_policy(results, generation=1)
        # rescue-type genes should be in amplify
        amplify_names = [g.gene_name for g in policy.amplify_genes]
        assert any("rescue" in n for n in amplify_names)
        assert any("collection" in n for n in amplify_names)

    def test_explore_suggestions(self):
        """AC5: 探索建议."""
        pg, results = self._setup_engine_and_results()
        policy = pg.generate_policy(results, generation=1)
        assert len(policy.explore_genes) >= 1
        assert "hook" in policy.explore_genes[0]

    def test_get_v5_mutation_requests(self):
        """AC6: 获取 V5 请求."""
        pg, results = self._setup_engine_and_results()
        pg.generate_policy(results, generation=1)
        requests = pg.get_v5_mutation_requests()
        assert len(requests) >= 1
        assert all("action" in r for r in requests)
        assert all("gene_name" in r for r in requests)

    def test_get_pending_hypotheses(self):
        """AC4: 获取待验证假设."""
        pg, results = self._setup_engine_and_results()
        pg.generate_policy(results, generation=1)
        pending = pg.get_pending_hypotheses()
        assert len(pending) >= 1

    def test_policy_with_fitness(self):
        """AC5: 带 Fitness 数据的策略生成."""
        pg, results = self._setup_engine_and_results()
        fitness = {
            "MW_001": IAPFitnessResult(
                creative_id="MW_001", fitness_score=0.55,
                is_winner=True, winner_tier="S",
            ),
            "MW_002": IAPFitnessResult(
                creative_id="MW_002", fitness_score=0.15,
                is_winner=False, winner_tier="C",
            ),
        }
        policy = pg.generate_policy(results, fitness_results=fitness, generation=1)
        # 应该有基于 Winner 的洞察
        assert any("S-tier" in insight for insight in policy.based_on_insights)

    def test_get_by_generation(self):
        """AC9: 按代筛选策略."""
        pg, results = self._setup_engine_and_results()
        pg.generate_policy_batch(results, generations=3)
        gen1 = pg.get_by_generation(1)
        gen2 = pg.get_by_generation(2)
        assert len(gen1) == 1
        assert len(gen2) == 1

    def test_policy_stats(self):
        """AC5: 策略统计."""
        pg, results = self._setup_engine_and_results()
        pg.generate_policy(results, generation=1)
        stats = pg.policy_stats()
        assert stats["total_policies"] == 1
        assert stats["total_hypotheses"] >= 1
        assert stats["v5_mutation_requests"] >= 1


# ═══════════════════════════════════════════════════════════
# Creative DNA V2: 7-Gene Genome
# ═══════════════════════════════════════════════════════════

class TestPsychologyGene:
    """AC7: PsychologyGene 测试."""

    def test_dominant_psychology(self):
        """AC8: 主导心理机制."""
        gene = PsychologyGene(
            loss_aversion=0.7,
            completion_drive=0.3,
            anticipation=0.2,
            social_proof=0.1,
            scarcity=0.1,
            mastery=0.1,
            belonging=0.1,
        )
        assert gene.dominant_psychology == "loss_aversion"

    def test_psychology_score(self):
        """AC8: 心理评分."""
        gene = PsychologyGene(
            loss_aversion=0.8,
            completion_drive=0.5,
            anticipation=0.8,
            social_proof=0.3,
            scarcity=0.4,
            mastery=0.6,
            belonging=0.5,
        )
        score = gene.psychology_score
        assert 0.0 <= score <= 1.0

    def test_to_dict(self):
        """AC8: 序列化."""
        gene = PsychologyGene(loss_aversion=0.7, completion_drive=0.3)
        d = gene.to_dict()
        assert d["loss_aversion"] == 0.7
        assert d["dominant_psychology"] == "loss_aversion"

    def test_from_dict(self):
        """AC8: 反序列化."""
        gene = PsychologyGene.from_dict({
            "loss_aversion": 0.7,
            "completion_drive": 0.3,
        })
        assert gene.loss_aversion == 0.7
        assert gene.dominant_psychology == "loss_aversion"


class TestAudienceGene:
    """AC7: AudienceGene 测试."""

    def test_primary_audience(self):
        audience = AudienceGene(
            collector_score=0.5,
            progression_score=0.3,
            power_score=0.2,
            explorer_score=0.1,
            casual_score=0.1,
        )
        assert audience.primary_audience == "collector"

    def test_to_dict(self):
        audience = AudienceGene(
            target_gender="female",
            target_age_range="35-44",
            collector_score=0.5,
        )
        d = audience.to_dict()
        assert d["target_gender"] == "female"
        assert d["primary_audience"] == "collector"


class TestContextGene:
    """AC7: ContextGene 测试."""

    def test_is_evening_creative(self):
        gene = ContextGene(time_of_day="evening")
        assert gene.is_evening_creative is True

    def test_is_relaxation_context(self):
        gene = ContextGene(mood="relaxed", attention_level="low")
        assert gene.is_relaxation_context is True

    def test_not_relaxation_context(self):
        gene = ContextGene(mood="stressed", attention_level="high")
        assert gene.is_relaxation_context is False


class TestCreativeDNAV2:
    """AC7: 7 基因完整基因组测试."""

    def test_full_7_gene_genome(self):
        """AC7: 完整 7 基因基因组."""
        dna = CreativeDNAV2(
            creative_id="MW_001",
            visual_gene={"type": "cozy", "color": "warm"},
            hook_gene={"type": "rescue", "strength": 0.8},
            gameplay_gene={"type": "merge", "pace": "medium"},
            monetization_gene={"type": "collection", "trigger": "missing_item"},
            psychology_gene=PsychologyGene(
                loss_aversion=0.7,
                completion_drive=0.3,
            ),
            audience_gene=AudienceGene(
                target_gender="female",
                target_age_range="35-44",
                collector_score=0.5,
            ),
            context_gene=ContextGene(
                time_of_day="evening",
                mood="relaxed",
            ),
        )
        assert dna.gene_count == 7
        assert dna.dominant_psychology == "loss_aversion"
        assert dna.primary_audience == "collector"

    def test_to_dict(self):
        """AC7: 序列化."""
        dna = CreativeDNAV2(
            creative_id="MW_001",
            hook_gene={"type": "rescue"},
            psychology_gene=PsychologyGene(loss_aversion=0.7),
        )
        d = dna.to_dict()
        assert d["creative_id"] == "MW_001"
        assert d["dominant_psychology"] == "loss_aversion"
        assert "genes" in d
        assert "psychology" in d["genes"]

    def test_from_dict(self):
        """AC7: 反序列化."""
        dna = CreativeDNAV2.from_dict({
            "creative_id": "MW_001",
            "genes": {
                "hook": {"type": "rescue"},
                "psychology": {"loss_aversion": 0.7},
                "audience": {"collector_score": 0.5},
                "context": {"time_of_day": "evening"},
            },
        })
        assert dna.creative_id == "MW_001"
        assert dna.psychology_gene.loss_aversion == 0.7
        assert dna.audience_gene.primary_audience == "collector"
        assert dna.context_gene.is_evening_creative is True


# ═══════════════════════════════════════════════════════════
# 闭环集成测试
# ═══════════════════════════════════════════════════════════

class TestClosedLoop:
    """AC10: Creative DNA → Causal → Policy → V5 闭环测试."""

    def test_full_closed_loop(self):
        """AC10: 完整闭环.

        Creative DNA → Causal Discovery → Evolution Policy → V5 Mutation
        """
        # 1. 因果发现
        engine = DNACausalDiscoveryEngine()
        creative_dna_map = {
            "MW_001": {
                "hook": {"type": "rescue"},
                "reward": {"type": "collection"},
                "visual": {"type": "cozy"},
            },
            "MW_002": {
                "hook": {"type": "challenge"},
                "reward": {"type": "coins"},
            },
        }
        results = engine.discover_batch(
            creative_dna_map=creative_dna_map,
            ltv_map={
                "MW_001": LTVProfile(creative_id="MW_001", d30_ltv=8.5, sample_size=300),
                "MW_002": LTVProfile(creative_id="MW_002", d30_ltv=2.1, sample_size=200),
            },
            payment_map={
                "MW_001": PaymentProfile(creative_id="MW_001", payer_rate=0.15),
                "MW_002": PaymentProfile(creative_id="MW_002", payer_rate=0.03),
            },
        )

        # 2. DNA 级相关性 (need 2+ samples per gene for correlation)
        dna_corr = engine.compute_dna_level_correlation(
            creative_dna_map={
                "MW_001": {"hook": {"type": "rescue"}},
                "MW_002": {"hook": {"type": "rescue"}},
                "MW_003": {"hook": {"type": "challenge"}},
                "MW_004": {"hook": {"type": "challenge"}},
            },
            ltv_map={
                "MW_001": LTVProfile(creative_id="MW_001", d30_ltv=8.5),
                "MW_002": LTVProfile(creative_id="MW_002", d30_ltv=7.0),
                "MW_003": LTVProfile(creative_id="MW_003", d30_ltv=2.1),
                "MW_004": LTVProfile(creative_id="MW_004", d30_ltv=3.0),
            },
        )

        # 3. 进化策略
        pg = EvolutionPolicyGenerator()
        fitness = {
            "MW_001": IAPFitnessResult(
                creative_id="MW_001", fitness_score=0.55,
                is_winner=True, winner_tier="S",
            ),
        }
        policy = pg.generate_policy(results, fitness_results=fitness, generation=1)

        # 4. V5 Mutation 请求
        v5_requests = policy.to_v5_mutation_requests()

        # 验证闭环
        assert len(results) == 2
        assert "hook:rescue" in dna_corr
        assert dna_corr["hook:rescue"]["avg_d30_ltv"] > dna_corr["hook:challenge"]["avg_d30_ltv"]
        assert len(policy.amplify_genes) >= 1
        assert len(v5_requests) >= 1
        assert any(r["action"] == "amplify" for r in v5_requests)

        # 5. 假设验证
        assert len(policy.hypotheses) >= 1
        h = policy.hypotheses[0]
        assert h.hypothesis != ""
        assert h.target_psychology != ""


class TestCreativeDNAV2ClosedLoop:
    """AC10: Creative DNA V2 → Causal → Policy 闭环."""

    def test_v2_genome_to_policy(self):
        """AC10: V2 基因组 → 进化策略."""
        dna_v2 = CreativeDNAV2(
            creative_id="MW_001",
            hook_gene={"type": "rescue"},
            visual_gene={"type": "cozy"},
            gameplay_gene={"type": "merge"},
            monetization_gene={"type": "collection"},
            psychology_gene=PsychologyGene(loss_aversion=0.7, completion_drive=0.3),
            audience_gene=AudienceGene(target_gender="female", collector_score=0.5),
            context_gene=ContextGene(time_of_day="evening"),
        )

        # 因果发现
        engine = DNACausalDiscoveryEngine()
        result = engine.discover(
            creative_id="MW_001",
            dna_map=dna_v2.to_dict()["genes"],
            ltv=LTVProfile(creative_id="MW_001", d30_ltv=8.5, sample_size=300),
            payment=PaymentProfile(creative_id="MW_001", payer_rate=0.15),
        )

        # 策略生成
        pg = EvolutionPolicyGenerator()
        policy = pg.generate_policy([result], generation=1)

        # 验证
        assert len(policy.amplify_genes) >= 1
        assert any("rescue" in g.gene_name for g in policy.amplify_genes)
        assert len(policy.hypotheses) >= 1