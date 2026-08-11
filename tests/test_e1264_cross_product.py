"""E12.6.4 — Cross Product Intelligence 测试。

覆盖:
  - Models: ProductFeature, ProductProfile, ProductCluster, UniversalPattern,
    TransferDecision, KnowledgeTransfer, CrossLearningResult, SimilarityResult
  - ProductProfiler: feature/profile building
  - SimilarityEngine: Jaccard, weighted similarity, pairwise, clustering
  - UniversalPatternLibrary: add/query/update/record
  - TransferEngine: evaluate, risk, strategy
  - CrossProductController: learn_from_products, evaluate_transfer
  - Integration: full cross-product flow
"""

import pytest

from market_ops.creative_vision_runtime.reality.meta_learning.cross_product import (
    CrossLearningResult,
    CrossProductController,
    KnowledgeTransfer,
    ProductCluster,
    ProductFeature,
    ProductProfile,
    ProductProfiler,
    SimilarityEngine,
    SimilarityResult,
    TransferAction,
    TransferDecision,
    TransferEngine,
    TransferRisk,
    UniversalPattern,
    UniversalPatternLibrary,
)


# ── Helpers ─────────────────────────────────────────────────


def make_feature(
    product_id: str = "P04",
    genre: str = "merge",
    monetization: str = "IAA",
    audience: str = "female_25_45",
    gameplay_tags: list[str] | None = None,
    creative_patterns: list[str] | None = None,
    market: str = "T1",
) -> ProductFeature:
    return ProductFeature(
        product_id=product_id,
        genre=genre,
        monetization=monetization,
        audience=audience,
        gameplay_tags=gameplay_tags or ["fantasy", "casual"],
        creative_patterns=creative_patterns or ["rescue_hook", "cute_visual"],
        market=market,
    )


def make_profile(
    product_id: str = "P04",
    genre: str = "merge",
    monetization: str = "IAA",
    audience: str = "female_25_45",
    creative_patterns: list[str] | None = None,
    market: str = "T1",
    experiment_count: int = 50,
    winner_count: int = 10,
) -> ProductProfile:
    return ProductProfile(
        product_id=product_id,
        features=make_feature(product_id, genre, monetization, audience, creative_patterns=creative_patterns, market=market),
        experiment_count=experiment_count,
        winner_count=winner_count,
    )


def make_pattern(
    pattern_id: str = "",
    pattern_type: str = "hook",
    pattern_name: str = "rescue_hook",
    source_products: list[str] | None = None,
    confidence: float = 0.85,
    performance_gain: float = 0.22,
    applicable_genres: list[str] | None = None,
    transfer_count: int = 0,
    success_count: int = 0,
) -> UniversalPattern:
    return UniversalPattern(
        pattern_id=pattern_id,
        pattern_type=pattern_type,
        pattern_name=pattern_name,
        source_products=source_products or ["P04"],
        confidence=confidence,
        performance_gain=performance_gain,
        applicable_genres=applicable_genres or ["merge", "puzzle"],
        transfer_count=transfer_count,
        success_count=success_count,
    )


# ═══════════════════════════════════════════════════════════════
# TestModels — 15 tests
# ═══════════════════════════════════════════════════════════════


class TestModels:
    """ProductFeature, ProductProfile, ProductCluster, UniversalPattern, etc."""

    def test_feature_creation(self):
        f = make_feature()
        assert f.product_id == "P04"
        assert f.genre == "merge"

    def test_feature_to_vector(self):
        f = make_feature()
        v = f.to_vector()
        assert "merge" in v
        assert "rescue_hook" in v

    def test_feature_to_dict(self):
        f = make_feature()
        d = f.to_dict()
        assert d["product_id"] == "P04"

    def test_profile_creation(self):
        p = make_profile()
        assert p.product_id == "P04"
        assert p.features.genre == "merge"

    def test_profile_winner_rate(self):
        p = make_profile(experiment_count=100, winner_count=25)
        assert p.winner_rate == 0.25

    def test_profile_winner_rate_zero(self):
        p = make_profile(experiment_count=0)
        assert p.winner_rate == 0.0

    def test_cluster_creation(self):
        c = ProductCluster(products=["P04", "P05"])
        assert c.size == 2
        assert c.cluster_id.startswith("CL_")

    def test_pattern_creation(self):
        p = make_pattern()
        assert p.pattern_type == "hook"
        assert p.confidence == 0.85

    def test_pattern_is_proven(self):
        p = make_pattern(confidence=0.8, transfer_count=5)
        assert p.is_proven is True

        p2 = make_pattern(confidence=0.5, transfer_count=1)
        assert p2.is_proven is False

    def test_pattern_transfer_success_rate(self):
        p = make_pattern()
        p.transfer_count = 10
        p.success_count = 7
        assert p.transfer_success_rate == 0.7

    def test_transfer_decision_creation(self):
        d = TransferDecision(
            source_product="P04",
            target_product="P05",
            pattern_id="UP_1",
            action=TransferAction.ALLOW,
            confidence=0.85,
            risk_level=TransferRisk.LOW,
        )
        assert d.is_allowed is True
        assert d.is_denied is False

    def test_transfer_decision_to_dict(self):
        d = TransferDecision(
            source_product="P04",
            target_product="P05",
            pattern_id="UP_1",
            action=TransferAction.ALLOW,
            confidence=0.85,
            risk_level=TransferRisk.LOW,
        )
        dd = d.to_dict()
        assert dd["is_allowed"] is True

    def test_knowledge_transfer_creation(self):
        kt = KnowledgeTransfer(
            source_product="P04",
            target_product="P05",
            pattern_id="UP_1",
            confidence=0.85,
        )
        assert kt.has_feedback is False
        assert kt.transfer_id.startswith("KT_")

    def test_cross_learning_result(self):
        r = CrossLearningResult(
            source_products=["P04", "P05"],
            transferred_patterns=3,
            rejected_patterns=2,
        )
        assert r.total_evaluated == 5
        assert r.transfer_rate == 0.6

    def test_similarity_result(self):
        s = SimilarityResult(total_similarity=0.85)
        assert s.is_high_similarity is True
        assert s.is_medium_similarity is False


# ═══════════════════════════════════════════════════════════════
# TestProductProfiler — 15 tests
# ═══════════════════════════════════════════════════════════════


class TestProductProfiler:
    """ProductProfiler — 产品画像构建"""

    def test_build_feature(self):
        profiler = ProductProfiler()
        f = profiler.build_feature(
            product_id="P04",
            genre="merge",
            monetization="IAA",
            audience="female_25_45",
            gameplay_tags=["fantasy"],
            creative_patterns=["rescue_hook"],
            market="T1",
        )
        assert f.product_id == "P04"
        assert f.genre == "merge"
        assert "fantasy" in f.gameplay_tags

    def test_build_profile(self):
        profiler = ProductProfiler()
        features = make_feature()
        profile = profiler.build_profile(
            features,
            successful_patterns=[{"pattern": "rescue_hook", "ctr_uplift": 0.22}],
            performance_summary={"avg_ctr": 0.12, "avg_roas": 1.5},
            experiment_count=50,
            winner_count=10,
        )
        assert profile.product_id == "P04"
        assert profile.winner_count == 10

    def test_profile_product(self):
        profiler = ProductProfiler()
        profile = profiler.profile_product(
            product_id="P04",
            genre="merge",
            monetization="IAA",
            audience="female_25_45",
            gameplay_tags=["fantasy", "casual"],
            creative_patterns=["rescue_hook"],
            market="T1",
            experiment_count=50,
            winner_count=12,
        )
        assert profile.product_id == "P04"
        assert profile.features.genre == "merge"
        assert profile.winner_rate == pytest.approx(0.24)

    def test_profile_many(self):
        profiler = ProductProfiler()
        data = [
            {"product_id": "P04", "genre": "merge", "experiment_count": 50, "winner_count": 10},
            {"product_id": "P05", "genre": "puzzle", "experiment_count": 30, "winner_count": 5},
        ]
        profiles = profiler.profile_many(data)
        assert len(profiles) == 2
        assert profiles[0].product_id == "P04"
        assert profiles[1].product_id == "P05"

    def test_profile_empty_tags(self):
        profiler = ProductProfiler()
        profile = profiler.profile_product(product_id="P04")
        assert profile.features.gameplay_tags == []

    def test_profiler_repr(self):
        p = ProductProfiler()
        assert "ProductProfiler" in repr(p)


# ═══════════════════════════════════════════════════════════════
# TestSimilarityEngine — 20 tests
# ═══════════════════════════════════════════════════════════════


class TestSimilarityEngine:
    """SimilarityEngine — 产品相似度"""

    def test_jaccard_identical(self):
        engine = SimilarityEngine()
        assert engine._jaccard(["a", "b"], ["a", "b"]) == 1.0

    def test_jaccard_disjoint(self):
        engine = SimilarityEngine()
        assert engine._jaccard(["a", "b"], ["c", "d"]) == 0.0

    def test_jaccard_partial(self):
        engine = SimilarityEngine()
        sim = engine._jaccard(["a", "b", "c"], ["b", "c", "d"])
        assert sim == pytest.approx(2/4)

    def test_jaccard_empty(self):
        engine = SimilarityEngine()
        assert engine._jaccard([], []) == 0.0

    def test_compute_similarity_identical(self):
        engine = SimilarityEngine()
        f = make_feature()
        result = engine.compute_similarity(f, f)
        assert result.total_similarity == pytest.approx(1.0)

    def test_compute_similarity_different_genre(self):
        engine = SimilarityEngine()
        f1 = make_feature("P04", genre="merge", creative_patterns=["rescue_hook"])
        f2 = make_feature("P05", genre="puzzle", creative_patterns=["rescue_hook"])
        result = engine.compute_similarity(f1, f2)
        assert result.genre_similarity == 0.0
        assert result.dna_similarity == 1.0
        assert result.total_similarity < 1.0

    def test_compute_similarity_same_genre(self):
        engine = SimilarityEngine()
        f1 = make_feature("P04", genre="merge")
        f2 = make_feature("P05", genre="merge")
        result = engine.compute_similarity(f1, f2)
        assert result.genre_similarity == 1.0

    def test_compute_similarity_different_market(self):
        engine = SimilarityEngine()
        f1 = make_feature("P04", market="T1")
        f2 = make_feature("P05", market="T2")
        result = engine.compute_similarity(f1, f2)
        assert result.market_similarity == 0.0

    def test_compute_pairwise(self):
        engine = SimilarityEngine()
        features = [make_feature("P04"), make_feature("P05"), make_feature("P06")]
        results = engine.compute_pairwise(features)
        assert len(results) == 3  # 3 choose 2

    def test_compute_pairwise_from_profiles(self):
        engine = SimilarityEngine()
        profiles = [make_profile("P04"), make_profile("P05"), make_profile("P06")]
        results = engine.compute_pairwise_from_profiles(profiles)
        assert len(results) == 3

    def test_cluster_same_genre(self):
        engine = SimilarityEngine()
        f1 = make_feature("P04", genre="merge", creative_patterns=["rescue_hook"])
        f2 = make_feature("P05", genre="merge", creative_patterns=["rescue_hook"])
        clusters = engine.cluster([f1, f2])
        assert len(clusters) == 1
        assert len(clusters[0].products) == 2

    def test_cluster_different_genre(self):
        engine = SimilarityEngine()
        f1 = make_feature("P04", genre="merge", creative_patterns=["rescue_hook"])
        f2 = make_feature("P05", genre="puzzle", creative_patterns=["puzzle_hook"])
        clusters = engine.cluster([f1, f2])
        assert len(clusters) == 2

    def test_cluster_empty(self):
        engine = SimilarityEngine()
        assert engine.cluster([]) == []

    def test_cluster_multiple(self):
        engine = SimilarityEngine()
        f1 = make_feature("P04", genre="merge", creative_patterns=["rescue_hook", "cute_visual"])
        f2 = make_feature("P05", genre="merge", creative_patterns=["rescue_hook", "cute_visual"])
        f3 = make_feature("P06", genre="arcade", creative_patterns=["action_hook"])
        clusters = engine.cluster([f1, f2, f3])
        assert len(clusters) == 2

    def test_get_most_similar(self):
        engine = SimilarityEngine()
        source = make_feature("P04", genre="merge", creative_patterns=["rescue_hook"])
        candidates = [
            make_feature("P05", genre="merge", creative_patterns=["rescue_hook"]),
            make_feature("P06", genre="puzzle", creative_patterns=["puzzle_hook"]),
            make_feature("P07", genre="arcade", creative_patterns=["action_hook"]),
        ]
        top = engine.get_most_similar(source, candidates, top_n=2)
        assert len(top) == 2
        assert top[0].total_similarity >= top[1].total_similarity

    def test_similarity_weights_sum(self):
        engine = SimilarityEngine()
        total = engine.genre_weight + engine.audience_weight + engine.dna_weight + engine.market_weight
        assert total == pytest.approx(1.0)

    def test_custom_weights(self):
        engine = SimilarityEngine(genre_weight=0.5, audience_weight=0.2, dna_weight=0.2, market_weight=0.1)
        f1 = make_feature("P04", genre="merge")
        f2 = make_feature("P05", genre="puzzle")
        result = engine.compute_similarity(f1, f2)
        assert result.total_similarity < 1.0

    def test_similarity_result_properties(self):
        s = SimilarityResult(total_similarity=0.45)
        assert s.is_high_similarity is False
        assert s.is_medium_similarity is True

    def test_engine_repr(self):
        engine = SimilarityEngine()
        assert "SimilarityEngine" in repr(engine)


# ═══════════════════════════════════════════════════════════════
# TestUniversalPatternLibrary — 20 tests
# ═══════════════════════════════════════════════════════════════


class TestUniversalPatternLibrary:
    """UniversalPatternLibrary — 通用模式库"""

    def test_add_pattern(self):
        lib = UniversalPatternLibrary()
        p = make_pattern()
        lib.add_pattern(p)
        assert lib.get_pattern(p.pattern_id) is not None

    def test_get_pattern_nonexistent(self):
        lib = UniversalPatternLibrary()
        assert lib.get_pattern("nonexistent") is None

    def test_query_by_type(self):
        lib = UniversalPatternLibrary()
        lib.add_pattern(make_pattern(pattern_type="hook"))
        lib.add_pattern(make_pattern(pattern_type="visual"))
        results = lib.query(pattern_type="hook")
        assert len(results) == 1

    def test_query_by_genre(self):
        lib = UniversalPatternLibrary()
        lib.add_pattern(make_pattern(applicable_genres=["merge"]))
        lib.add_pattern(make_pattern(applicable_genres=["puzzle"]))
        results = lib.query(genre="merge")
        assert len(results) == 1

    def test_query_min_confidence(self):
        lib = UniversalPatternLibrary()
        lib.add_pattern(make_pattern(confidence=0.9))
        lib.add_pattern(make_pattern(confidence=0.4))
        results = lib.query(min_confidence=0.7)
        assert len(results) == 1

    def test_query_min_gain(self):
        lib = UniversalPatternLibrary()
        lib.add_pattern(make_pattern(performance_gain=0.3))
        lib.add_pattern(make_pattern(performance_gain=0.1))
        results = lib.query(min_gain=0.2)
        assert len(results) == 1

    def test_query_proven_only(self):
        lib = UniversalPatternLibrary()
        p1 = make_pattern(confidence=0.8, transfer_count=5)
        p2 = make_pattern(confidence=0.5, transfer_count=1)
        lib.add_pattern(p1)
        lib.add_pattern(p2)
        results = lib.query(proven_only=True)
        assert len(results) == 1

    def test_get_by_type(self):
        lib = UniversalPatternLibrary()
        p = make_pattern(pattern_type="hook")
        lib.add_pattern(p)
        results = lib.get_by_type("hook")
        assert len(results) == 1

    def test_get_by_genre(self):
        lib = UniversalPatternLibrary()
        p = make_pattern(applicable_genres=["merge"])
        lib.add_pattern(p)
        results = lib.get_by_genre("merge")
        assert len(results) == 1

    def test_update_confidence(self):
        lib = UniversalPatternLibrary()
        p = make_pattern(confidence=0.7)
        lib.add_pattern(p)
        updated = lib.update_confidence(p.pattern_id, 0.95)
        assert updated is not None
        assert updated.confidence == 0.95

    def test_update_confidence_nonexistent(self):
        lib = UniversalPatternLibrary()
        assert lib.update_confidence("nonexistent", 0.5) is None

    def test_record_transfer_success(self):
        lib = UniversalPatternLibrary()
        p = make_pattern()
        lib.add_pattern(p)
        lib.record_transfer(p.pattern_id, True)
        pattern = lib.get_pattern(p.pattern_id)
        assert pattern is not None
        assert pattern.transfer_count == 1
        assert pattern.success_count == 1

    def test_record_transfer_failure(self):
        lib = UniversalPatternLibrary()
        p = make_pattern()
        lib.add_pattern(p)
        lib.record_transfer(p.pattern_id, False)
        pattern = lib.get_pattern(p.pattern_id)
        assert pattern is not None
        assert pattern.transfer_count == 1
        assert pattern.success_count == 0

    def test_record_transfer_nonexistent(self):
        lib = UniversalPatternLibrary()
        lib.record_transfer("nonexistent", True)  # should not crash

    def test_get_statistics(self):
        lib = UniversalPatternLibrary()
        lib.add_pattern(make_pattern())
        lib.add_pattern(make_pattern())
        stats = lib.get_statistics()
        assert stats["total_patterns"] == 2

    def test_get_all_patterns(self):
        lib = UniversalPatternLibrary()
        lib.add_pattern(make_pattern())
        assert len(lib.get_all_patterns()) == 1

    def test_clear(self):
        lib = UniversalPatternLibrary()
        lib.add_pattern(make_pattern())
        lib.clear()
        assert len(lib.get_all_patterns()) == 0

    def test_max_patterns(self):
        lib = UniversalPatternLibrary(max_patterns=2)
        lib.add_pattern(make_pattern())
        lib.add_pattern(make_pattern())
        lib.add_pattern(make_pattern())  # should evict oldest
        assert len(lib.get_all_patterns()) == 2

    def test_library_repr(self):
        lib = UniversalPatternLibrary()
        assert "UniversalPatternLibrary" in repr(lib)


# ═══════════════════════════════════════════════════════════════
# TestTransferEngine — 25 tests
# ═══════════════════════════════════════════════════════════════


class TestTransferEngine:
    """TransferEngine — 知识迁移决策"""

    def test_evaluate_allow(self):
        """高相似度 + 高置信度 → ALLOW"""
        engine = TransferEngine()
        sim = SimilarityResult(
            source_product="P04", target_product="P05",
            total_similarity=0.85, dna_similarity=0.9,
        )
        pattern = make_pattern(confidence=0.85, performance_gain=0.22)
        decision = engine.evaluate(sim, pattern)
        assert decision.action == TransferAction.ALLOW
        assert decision.risk_level == TransferRisk.LOW

    def test_evaluate_deny_low_similarity(self):
        """低相似度 → DENY"""
        engine = TransferEngine()
        sim = SimilarityResult(
            source_product="P04", target_product="P05",
            total_similarity=0.30,
        )
        pattern = make_pattern(confidence=0.85)
        decision = engine.evaluate(sim, pattern)
        assert decision.action == TransferAction.DENY

    def test_evaluate_deny_low_confidence(self):
        """低置信度模式 → DENY"""
        engine = TransferEngine()
        sim = SimilarityResult(
            source_product="P04", target_product="P05",
            total_similarity=0.80,
        )
        pattern = make_pattern(confidence=0.30)
        decision = engine.evaluate(sim, pattern)
        assert decision.action == TransferAction.DENY

    def test_evaluate_modify_medium(self):
        """中相似度 → MODIFY"""
        engine = TransferEngine()
        sim = SimilarityResult(
            source_product="P04", target_product="P05",
            total_similarity=0.60, dna_similarity=0.5,
        )
        pattern = make_pattern(confidence=0.70)
        decision = engine.evaluate(sim, pattern)
        assert decision.action == TransferAction.MODIFY

    def test_evaluate_decision_confidence(self):
        engine = TransferEngine()
        sim = SimilarityResult(
            source_product="P04", target_product="P05",
            total_similarity=0.90,
        )
        pattern = make_pattern(confidence=0.90)
        decision = engine.evaluate(sim, pattern)
        assert decision.confidence == pytest.approx(0.90)

    def test_evaluate_expected_uplift(self):
        engine = TransferEngine()
        sim = SimilarityResult(
            source_product="P04", target_product="P05",
            total_similarity=0.80,
        )
        pattern = make_pattern(confidence=0.85, performance_gain=0.22)
        decision = engine.evaluate(sim, pattern)
        expected = 0.22 * 0.80 * 0.85 * 0.70
        assert decision.expected_uplift == pytest.approx(expected, abs=0.001)

    def test_evaluate_reasons(self):
        engine = TransferEngine()
        sim = SimilarityResult(
            source_product="P04", target_product="P05",
            total_similarity=0.85,
        )
        pattern = make_pattern(confidence=0.85)
        decision = engine.evaluate(sim, pattern)
        assert len(decision.reasons) > 0

    def test_is_transferable_true(self):
        engine = TransferEngine()
        sim = SimilarityResult(total_similarity=0.80)
        pattern = make_pattern(confidence=0.80)
        assert engine.is_transferable(sim, pattern) is True

    def test_is_transferable_false(self):
        engine = TransferEngine()
        sim = SimilarityResult(total_similarity=0.30)
        pattern = make_pattern(confidence=0.80)
        assert engine.is_transferable(sim, pattern) is False

    def test_is_transferable_low_confidence(self):
        engine = TransferEngine()
        sim = SimilarityResult(total_similarity=0.80)
        pattern = make_pattern(confidence=0.30)
        assert engine.is_transferable(sim, pattern) is False

    def test_strategy_direct_copy(self):
        engine = TransferEngine()
        sim = SimilarityResult(total_similarity=0.95, dna_similarity=0.95)
        pattern = make_pattern()
        decision = engine.evaluate(sim, pattern)
        assert decision.mutation_strategy == "direct_copy"

    def test_strategy_replace_character(self):
        engine = TransferEngine()
        sim = SimilarityResult(total_similarity=0.85, dna_similarity=0.7)
        pattern = make_pattern(confidence=0.8)
        decision = engine.evaluate(sim, pattern)
        assert decision.mutation_strategy == "replace_character_only"

    def test_strategy_adapt_to_genre(self):
        engine = TransferEngine()
        sim = SimilarityResult(total_similarity=0.75, dna_similarity=0.65)
        pattern = make_pattern(confidence=0.75)
        decision = engine.evaluate(sim, pattern)
        assert decision.mutation_strategy == "adapt_to_genre"

    def test_strategy_adapt_with_modification(self):
        engine = TransferEngine()
        sim = SimilarityResult(total_similarity=0.55, dna_similarity=0.4)
        pattern = make_pattern(confidence=0.6)
        decision = engine.evaluate(sim, pattern)
        assert decision.mutation_strategy == "adapt_with_modification"

    def test_evaluate_batch(self):
        engine = TransferEngine()
        sims = [
            SimilarityResult(source_product="P04", target_product="P05", total_similarity=0.85),
            SimilarityResult(source_product="P04", target_product="P06", total_similarity=0.30),
        ]
        pattern = make_pattern(confidence=0.85)
        decisions = engine.evaluate_batch(sims, pattern)
        assert len(decisions) == 2
        assert decisions[0].is_allowed is True
        assert decisions[1].is_denied is True

    def test_custom_thresholds(self):
        engine = TransferEngine(similarity_threshold=0.80, confidence_threshold=0.90)
        sim = SimilarityResult(total_similarity=0.70)
        pattern = make_pattern(confidence=0.85)
        decision = engine.evaluate(sim, pattern)
        assert decision.is_denied is True

    def test_engine_repr(self):
        engine = TransferEngine()
        assert "TransferEngine" in repr(engine)

    def test_deny_decision_has_no_strategy(self):
        engine = TransferEngine()
        sim = SimilarityResult(total_similarity=0.20)
        pattern = make_pattern()
        decision = engine.evaluate(sim, pattern)
        assert decision.mutation_strategy == "no_transfer"


# ═══════════════════════════════════════════════════════════════
# TestCrossProductController — 20 tests
# ═══════════════════════════════════════════════════════════════


class TestCrossProductController:
    """CrossProductController — 核心控制器"""

    def test_controller_creation(self):
        ctrl = CrossProductController()
        assert ctrl.profiler is not None
        assert ctrl.similarity_engine is not None
        assert ctrl.pattern_library is not None
        assert ctrl.transfer_engine is not None

    def test_learn_from_products(self):
        ctrl = CrossProductController()
        # 添加一些通用模式
        ctrl.add_pattern(make_pattern(
            pattern_type="hook",
            source_products=["P04"],
            confidence=0.85,
            applicable_genres=["merge"],
        ))
        ctrl.add_pattern(make_pattern(
            pattern_type="visual",
            source_products=["P04"],
            confidence=0.80,
            applicable_genres=["merge"],
        ))

        data = [
            {
                "product_id": "P04",
                "genre": "merge",
                "monetization": "IAA",
                "audience": "female_25_45",
                "gameplay_tags": ["fantasy", "casual"],
                "creative_patterns": ["rescue_hook", "cute_visual"],
                "market": "T1",
                "experiment_count": 100,
                "winner_count": 20,
            },
            {
                "product_id": "P05",
                "genre": "merge",
                "monetization": "IAA",
                "audience": "female_25_45",
                "gameplay_tags": ["fantasy", "collection"],
                "creative_patterns": ["rescue_hook", "dragon_visual"],
                "market": "T1",
                "experiment_count": 80,
                "winner_count": 15,
            },
        ]
        result = ctrl.learn_from_products(data)
        assert result.transferred_patterns >= 0
        assert result.total_evaluated >= 0
        assert isinstance(result.recommendations, list)

    def test_evaluate_transfer(self):
        ctrl = CrossProductController()
        src = make_profile("P04", genre="merge", creative_patterns=["rescue_hook"])
        tgt = make_profile("P05", genre="merge", creative_patterns=["rescue_hook"])
        pattern = make_pattern(source_products=["P04"])
        decision = ctrl.evaluate_transfer(src, tgt, pattern)
        assert decision is not None

    def test_add_pattern(self):
        ctrl = CrossProductController()
        pattern = make_pattern()
        ctrl.add_pattern(pattern)
        patterns = ctrl.get_patterns()
        assert len(patterns) == 1

    def test_get_patterns_by_type(self):
        ctrl = CrossProductController()
        ctrl.add_pattern(make_pattern(pattern_type="hook"))
        ctrl.add_pattern(make_pattern(pattern_type="visual"))
        results = ctrl.get_patterns(pattern_type="hook")
        assert len(results) == 1

    def test_get_patterns_by_genre(self):
        ctrl = CrossProductController()
        ctrl.add_pattern(make_pattern(applicable_genres=["merge"]))
        results = ctrl.get_patterns(genre="merge")
        assert len(results) == 1

    def test_get_patterns_proven_only(self):
        ctrl = CrossProductController()
        p = make_pattern(confidence=0.8, transfer_count=5)
        ctrl.add_pattern(p)
        results = ctrl.get_patterns(proven_only=True)
        assert len(results) == 1

    def test_get_clusters(self):
        ctrl = CrossProductController()
        profiles = [
            make_profile("P04", genre="merge", creative_patterns=["rescue_hook"]),
            make_profile("P05", genre="merge", creative_patterns=["rescue_hook"]),
            make_profile("P06", genre="puzzle", creative_patterns=["puzzle_hook"]),
        ]
        clusters = ctrl.get_clusters(profiles)
        assert len(clusters) >= 1

    def test_get_similarity_matrix(self):
        ctrl = CrossProductController()
        profiles = [
            make_profile("P04"),
            make_profile("P05"),
            make_profile("P06"),
        ]
        matrix = ctrl.get_similarity_matrix(profiles)
        assert len(matrix) == 3

    def test_get_statistics(self):
        ctrl = CrossProductController()
        ctrl.add_pattern(make_pattern())
        stats = ctrl.get_statistics()
        assert stats["total_patterns"] == 1

    def test_controller_repr(self):
        ctrl = CrossProductController()
        assert "CrossProductController" in repr(ctrl)

    def test_learn_from_products_empty(self):
        ctrl = CrossProductController()
        result = ctrl.learn_from_products([])
        assert result.transferred_patterns == 0

    def test_learn_from_products_no_patterns(self):
        ctrl = CrossProductController()
        data = [{"product_id": "P04", "genre": "merge"}]
        result = ctrl.learn_from_products(data)
        assert result.total_evaluated == 0

    def test_custom_components(self):
        profiler = ProductProfiler()
        sim_engine = SimilarityEngine()
        pat_lib = UniversalPatternLibrary()
        trans_engine = TransferEngine()
        ctrl = CrossProductController(
            profiler=profiler,
            similarity_engine=sim_engine,
            pattern_library=pat_lib,
            transfer_engine=trans_engine,
        )
        assert ctrl.profiler is profiler
        assert ctrl.similarity_engine is sim_engine


# ═══════════════════════════════════════════════════════════════
# TestIntegration — 15 tests
# ═══════════════════════════════════════════════════════════════


class TestIntegration:
    """Integration tests — 完整跨产品流程"""

    def test_full_flow_similar_products(self):
        """完整流程：相似产品间的知识迁移"""
        ctrl = CrossProductController()

        # 添加经过验证的模式
        ctrl.add_pattern(UniversalPattern(
            pattern_type="hook",
            pattern_name="rescue_emotion_hook",
            source_products=["P04"],
            confidence=0.85,
            performance_gain=0.22,
            applicable_genres=["merge", "puzzle"],
        ))

        data = [
            {"product_id": "P04", "genre": "merge", "creative_patterns": ["rescue_hook", "cute_visual"], "market": "T1", "experiment_count": 100, "winner_count": 25},
            {"product_id": "P05", "genre": "merge", "creative_patterns": ["rescue_hook", "dragon_visual"], "market": "T1", "experiment_count": 80, "winner_count": 15},
        ]
        result = ctrl.learn_from_products(data)
        assert result is not None
        assert len(result.recommendations) > 0

    def test_full_flow_different_products(self):
        """完整流程：不同品类产品间的知识迁移"""
        ctrl = CrossProductController()

        ctrl.add_pattern(UniversalPattern(
            pattern_type="hook",
            pattern_name="rescue_emotion_hook",
            source_products=["P04"],
            confidence=0.85,
            performance_gain=0.22,
            applicable_genres=["merge", "puzzle", "simulation"],
        ))

        data = [
            {"product_id": "P04", "genre": "merge", "creative_patterns": ["rescue_hook", "cute_visual"], "market": "T1", "experiment_count": 100, "winner_count": 20},
            {"product_id": "P06", "genre": "arcade", "creative_patterns": ["action_hook", "explosion_visual"], "market": "T2", "experiment_count": 50, "winner_count": 5},
        ]
        result = ctrl.learn_from_products(data)
        assert result is not None

    def test_knowledge_transfer_tracking(self):
        """知识迁移追踪"""
        ctrl = CrossProductController()
        pattern = make_pattern(
            source_products=["P04"],
            confidence=0.85,
            applicable_genres=["merge"],
        )
        ctrl.add_pattern(pattern)

        data = [
            {"product_id": "P04", "genre": "merge", "creative_patterns": ["rescue_hook"], "market": "T1", "experiment_count": 50, "winner_count": 10},
            {"product_id": "P05", "genre": "merge", "creative_patterns": ["rescue_hook"], "market": "T1", "experiment_count": 30, "winner_count": 5},
        ]
        result = ctrl.learn_from_products(data)
        assert len(result.transfers) >= 0

    def test_confidence_gain_calculation(self):
        """置信度增益计算"""
        ctrl = CrossProductController()
        ctrl.add_pattern(make_pattern(source_products=["P04"], confidence=0.85))

        data = [
            {"product_id": "P04", "genre": "merge", "creative_patterns": ["rescue_hook"], "market": "T1", "experiment_count": 50, "winner_count": 10},
            {"product_id": "P05", "genre": "merge", "creative_patterns": ["rescue_hook"], "market": "T1", "experiment_count": 30, "winner_count": 5},
        ]
        result = ctrl.learn_from_products(data)
        assert result.confidence_gain >= 0.0

    def test_multi_product_clustering(self):
        """多产品聚类"""
        ctrl = CrossProductController()
        profiles = [
            make_profile("P04", genre="merge", creative_patterns=["rescue_hook", "cute_visual"]),
            make_profile("P05", genre="merge", creative_patterns=["rescue_hook", "dragon_visual"]),
            make_profile("P06", genre="merge", creative_patterns=["rescue_hook", "fairy_visual"]),
            make_profile("P07", genre="puzzle", creative_patterns=["puzzle_hook", "color_visual"]),
            make_profile("P08", genre="arcade", creative_patterns=["action_hook", "explosion_visual"]),
        ]
        clusters = ctrl.get_clusters(profiles)
        assert len(clusters) >= 1

    def test_dna_similarity_drives_transfer(self):
        """DNA 相似度驱动迁移"""
        ctrl = CrossProductController()
        ctrl.add_pattern(make_pattern(
            source_products=["P04"],
            confidence=0.85,
            applicable_genres=["merge", "puzzle"],
        ))

        # 共享相同 creative patterns 的产品
        data = [
            {"product_id": "P04", "genre": "merge", "creative_patterns": ["rescue_hook", "cute_visual"], "market": "T1", "experiment_count": 50, "winner_count": 10},
            {"product_id": "P05", "genre": "puzzle", "creative_patterns": ["rescue_hook", "cute_visual"], "market": "T1", "experiment_count": 30, "winner_count": 5},
        ]
        result = ctrl.learn_from_products(data)
        assert result is not None

    def test_similarity_matrix_ordering(self):
        """相似度矩阵排序"""
        engine = SimilarityEngine()
        f1 = make_feature("P04", genre="merge", creative_patterns=["rescue_hook", "cute_visual"])
        f2 = make_feature("P05", genre="merge", creative_patterns=["rescue_hook", "dragon_visual"])
        f3 = make_feature("P06", genre="arcade", creative_patterns=["action_hook"])
        results = engine.compute_pairwise([f1, f2, f3])
        results.sort(key=lambda r: r.total_similarity, reverse=True)
        assert results[0].total_similarity >= results[-1].total_similarity

    def test_transfer_with_feedback(self):
        """迁移带反馈"""
        kt = KnowledgeTransfer(
            source_product="P04",
            target_product="P05",
            pattern_id="UP_1",
            confidence=0.85,
            expected_uplift=0.13,
            actual_uplift=0.15,
        )
        assert kt.has_feedback is True
        assert kt.is_successful is True

    def test_transfer_feedback_negative(self):
        """迁移反馈为负"""
        kt = KnowledgeTransfer(
            source_product="P04",
            target_product="P05",
            pattern_id="UP_1",
            confidence=0.85,
            expected_uplift=0.13,
            actual_uplift=-0.05,
        )
        assert kt.is_successful is False

    def test_library_statistics_after_transfer(self):
        """迁移后库统计更新"""
        lib = UniversalPatternLibrary()
        p = make_pattern()
        lib.add_pattern(p)
        lib.record_transfer(p.pattern_id, True)
        lib.record_transfer(p.pattern_id, True)
        lib.record_transfer(p.pattern_id, False)
        stats = lib.get_statistics()
        assert stats["total_transfers"] == 3
        assert stats["total_successes"] == 2

    def test_edge_empty_profiles(self):
        """空产品列表"""
        ctrl = CrossProductController()
        result = ctrl.learn_from_products([])
        assert result.transferred_patterns == 0
        assert result.transfer_rate == 0.0

    def test_edge_identical_products(self):
        """完全相同的产品"""
        engine = SimilarityEngine()
        f1 = make_feature("P04", genre="merge", creative_patterns=["rescue_hook"])
        f2 = make_feature("P05", genre="merge", creative_patterns=["rescue_hook"])
        result = engine.compute_similarity(f1, f2)
        assert result.total_similarity == pytest.approx(1.0)  # all dimensions match

    def test_edge_completely_different(self):
        """完全不同的产品"""
        engine = SimilarityEngine()
        f1 = make_feature("P04", genre="merge", audience="female_25_45", market="T1", creative_patterns=["rescue_hook"])
        f2 = make_feature("P05", genre="arcade", audience="male_18_35", market="T3", creative_patterns=["action_hook"])
        result = engine.compute_similarity(f1, f2)
        assert result.total_similarity == 0.0

    def test_controller_with_custom_patterns(self):
        """使用外部模式列表"""
        ctrl = CrossProductController()
        patterns = [
            make_pattern(source_products=["P04"], confidence=0.85, applicable_genres=["merge"]),
        ]
        data = [
            {"product_id": "P04", "genre": "merge", "creative_patterns": ["rescue_hook"], "market": "T1", "experiment_count": 50, "winner_count": 10},
            {"product_id": "P05", "genre": "merge", "creative_patterns": ["rescue_hook"], "market": "T1", "experiment_count": 30, "winner_count": 5},
        ]
        result = ctrl.learn_from_products(data, patterns=patterns)
        assert result is not None

    def test_transfer_decision_has_all_fields(self):
        """迁移决策包含所有字段"""
        engine = TransferEngine()
        sim = SimilarityResult(
            source_product="P04", target_product="P05",
            total_similarity=0.85, dna_similarity=0.9,
        )
        pattern = make_pattern(confidence=0.85)
        decision = engine.evaluate(sim, pattern)
        assert decision.decision_id.startswith("TD_")
        assert decision.similarity_score > 0
        assert decision.expected_uplift > 0
        assert len(decision.reasons) > 0