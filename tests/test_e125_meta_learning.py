"""E12.5.1 — Meta Learning Experience Memory 测试。

覆盖:
  - Models: ExperienceRecord, MutationDetail, ExperimentDetail,
            ContextDetail, ExperienceResult, ExperienceQuery, ExperienceStats,
            ExperiencePattern, enums
  - ExperienceStore: CRUD, query, stats, pattern extraction
  - ExperienceCollector: ExperimentRun+Evaluation → ExperienceRecord
  - Integration: 从 E12.4 数据完整收集
"""

import pytest

from market_ops.creative_vision_runtime.reality.meta_learning import (
    ContextDetail,
    ExperienceCollector,
    ExperienceOutcome,
    ExperiencePattern,
    ExperienceQuery,
    ExperienceRecord,
    ExperienceResult,
    ExperienceStats,
    ExperienceStore,
    ExperimentDetail,
    GeneCategory,
    MutationDetail,
    MutationType,
)
from market_ops.creative_vision_runtime.reality.feedback import (
    EvolutionLearningRecord,
    ExperimentEvaluation,
    ExperimentRun,
    ExperimentStatus,
    MutationIntent,
    MutationRequest,
)


# ── Helpers ───────────────────────────────────────────────


def make_mutation_detail(mt=MutationType.REFRESH_HOOK, changed=None):
    return MutationDetail(
        mutation_type=mt,
        changed_genes=changed or ["hook", "visual_style"],
        gene_before={"hook": "rescue_puppy"},
        gene_after={"hook": "save_dragon"},
        constraints={"keep": ["gameplay"], "change": ["hook", "visual_style"]},
    )


def make_experiment_detail(improvement=0.3, winner="v2"):
    return ExperimentDetail(
        baseline_metrics={"ctr": 0.021, "roas": 0.55},
        winner_metrics={"ctr": 0.030, "roas": 0.72},
        improvement=improvement,
        metrics_delta={"ctr": 0.43, "roas": 0.31},
        winner_id=winner,
        variant_count=3,
        confidence=0.85,
    )


def make_context(product="p04", market="US", platform="facebook"):
    return ContextDetail(
        product_id=product,
        product_name="Merge Witch",
        market=market,
        country="US",
        audience="25-45 Female",
        platform=platform,
        campaign_type="IAA",
    )


def make_result(outcome=ExperienceOutcome.SUCCESS, insight="Stronger hook improved ROAS"):
    return ExperienceResult(
        outcome=outcome,
        success=outcome in (ExperienceOutcome.SUCCESS, ExperienceOutcome.MARGINAL),
        insight=insight,
        key_finding="Winner v2: improvement +30%",
    )


def make_record(
    product="p04",
    creative="c001",
    mutation_type=MutationType.REFRESH_HOOK,
    improvement=0.3,
    outcome=ExperienceOutcome.SUCCESS,
    market="US",
):
    return ExperienceRecord(
        product_id=product,
        creative_id=creative,
        genome_id="g001",
        mutation=make_mutation_detail(mt=mutation_type),
        experiment=make_experiment_detail(improvement=improvement),
        context=make_context(product=product, market=market),
        result=make_result(outcome=outcome),
        related_ids={
            "experiment_id": "exp_001",
            "mutation_request_id": "mr_001",
        },
    )


def make_experiment_run(cid="c001", status=ExperimentStatus.COMPLETED, variants=3):
    return ExperimentRun(
        creative_id=cid,
        status=status,
        variants=[f"v{i}" for i in range(1, variants + 1)],
        metrics={
            "baseline": {"ctr": 0.021, "roas": 0.55},
            "variants": {"v2": {"ctr": 0.030, "roas": 0.72}},
        },
    )


def make_evaluation(winner="v2", improvement=0.3):
    return ExperimentEvaluation(
        experiment_id="exp_001",
        creative_id="c001",
        winner_id=winner,
        improvement_score=improvement,
        metrics_delta={"ctr": 0.43, "roas": 0.31},
        raw_metrics={
            "baseline": {"ctr": 0.021, "roas": 0.55},
            "v2": {"ctr": 0.030, "roas": 0.72},
        },
        learning_signal="Winner v2: CTR improved by 43%",
        confidence=0.85,
    )


def make_mutation_request(intent=MutationIntent.REFRESH_HOOK):
    return MutationRequest(
        creative_id="c001",
        intent=intent,
        dna_constraints={"keep": ["gameplay"], "change": ["hook", "visual_style"]},
        generation_count=20,
    )


# ═══════════════════════════════════════════════════════════
# 1. Models (20 tests)
# ═══════════════════════════════════════════════════════════


class TestModels:
    """E12.5.1 数据模型测试。"""

    def test_experience_record_creation(self):
        record = make_record()
        assert record.experience_id.startswith("exp_")
        assert record.product_id == "p04"
        assert record.creative_id == "c001"
        assert record.genome_id == "g001"

    def test_experience_record_properties(self):
        record = make_record(
            mutation_type=MutationType.REFRESH_HOOK,
            improvement=0.3,
        )
        assert record.mutation_type == MutationType.REFRESH_HOOK
        assert record.improvement == 0.3
        assert record.is_success is True
        assert record.changed_genes == ["hook", "visual_style"]
        assert record.winner_id == "v2"

    def test_experience_record_domain_key(self):
        record = make_record(product="p04", market="US")
        assert record.domain_key == "p04:US:facebook"

    def test_experience_record_to_dict(self):
        record = make_record()
        d = record.to_dict()
        assert d["product_id"] == "p04"
        assert d["is_success"] is True
        assert "mutation" in d
        assert "experiment" in d
        assert "context" in d
        assert "result" in d

    def test_experience_record_repr(self):
        record = make_record()
        r = repr(record)
        assert "ExperienceRecord" in r
        assert "p04" in r

    def test_mutation_detail_defaults(self):
        md = MutationDetail()
        assert md.mutation_type == MutationType.REFRESH_HOOK
        assert md.changed_genes == []
        assert md.gene_before == {}

    def test_mutation_detail_to_dict(self):
        md = make_mutation_detail()
        d = md.to_dict()
        assert d["mutation_type"] == "refresh_hook"
        assert "hook" in d["changed_genes"]

    def test_experiment_detail_to_dict(self):
        ed = make_experiment_detail()
        d = ed.to_dict()
        assert d["improvement"] == 0.3
        assert d["winner_id"] == "v2"
        assert d["variant_count"] == 3

    def test_context_detail_domain_key(self):
        ctx = ContextDetail(product_id="p04", market="US", platform="facebook")
        assert ctx.domain_key == "p04:US:facebook"

    def test_context_detail_domain_key_different(self):
        ctx = ContextDetail(product_id="p07", market="EU", platform="google")
        assert ctx.domain_key == "p07:EU:google"

    def test_context_detail_to_dict(self):
        ctx = make_context()
        d = ctx.to_dict()
        assert d["product_id"] == "p04"
        assert d["domain_key"] == "p04:US:facebook"

    def test_experience_result_success(self):
        result = ExperienceResult(
            outcome=ExperienceOutcome.SUCCESS, success=True,
            insight="Stronger hook", key_finding="Winner v2: +30%",
        )
        assert result.is_actionable is True
        assert result.success is True

    def test_experience_result_failure(self):
        result = ExperienceResult(
            outcome=ExperienceOutcome.FAILURE, success=False,
            failure_reason="All underperformed",
        )
        assert result.is_actionable is True
        assert result.success is False

    def test_experience_result_inconclusive(self):
        result = ExperienceResult(outcome=ExperienceOutcome.INCONCLUSIVE)
        assert result.is_actionable is False
        assert result.success is False

    def test_experience_enum_outcome_values(self):
        assert len(list(ExperienceOutcome)) == 4

    def test_gene_category_values(self):
        assert len(list(GeneCategory)) == 7
        assert GeneCategory.HOOK.value == "hook"
        assert GeneCategory.PSYCHOLOGY.value == "psychology"

    def test_mutation_type_values(self):
        assert len(list(MutationType)) == 5

    def test_experience_query_defaults(self):
        q = ExperienceQuery()
        assert q.limit == 100
        assert q.offset == 0

    def test_experience_query_matches_empty(self):
        """空查询匹配所有。"""
        q = ExperienceQuery()
        record = make_record()
        assert q.matches(record) is True

    def test_experience_query_matches_product(self):
        q = ExperienceQuery(product_id="p04")
        assert q.matches(make_record(product="p04")) is True
        assert q.matches(make_record(product="p07")) is False


# ═══════════════════════════════════════════════════════════
# 2. ExperienceStore (20 tests)
# ═══════════════════════════════════════════════════════════


class TestExperienceStore:
    """ExperienceStore — 持久化 + 查询 + 统计。"""

    def test_add_and_get(self):
        store = ExperienceStore()
        record = make_record()
        store.add(record)
        assert len(store) == 1
        assert store.get(record.experience_id) is record

    def test_add_batch(self):
        store = ExperienceStore()
        records = [
            make_record(creative="c001"),
            make_record(creative="c002"),
            make_record(creative="c003"),
        ]
        store.add_batch(records)
        assert len(store) == 3

    def test_get_not_found(self):
        store = ExperienceStore()
        assert store.get("nonexistent") is None

    def test_remove(self):
        store = ExperienceStore()
        record = make_record()
        store.add(record)
        assert store.remove(record.experience_id) is True
        assert len(store) == 0

    def test_remove_not_found(self):
        store = ExperienceStore()
        assert store.remove("nonexistent") is False

    def test_clear(self):
        store = ExperienceStore()
        store.add(make_record())
        store.add(make_record(creative="c002"))
        store.clear()
        assert len(store) == 0

    def test_query_by_product(self):
        store = ExperienceStore()
        store.add(make_record(product="p04"))
        store.add(make_record(product="p04", creative="c002"))
        store.add(make_record(product="p07"))
        results = store.query_by_product("p04")
        assert len(results) == 2

    def test_query_by_product_empty(self):
        store = ExperienceStore()
        store.add(make_record(product="p04"))
        results = store.query_by_product("p99")
        assert results == []

    def test_query_by_mutation_type(self):
        store = ExperienceStore()
        store.add(make_record(mutation_type=MutationType.REFRESH_HOOK))
        store.add(make_record(mutation_type=MutationType.FULL_REBUILD, creative="c002"))
        results = store.query_by_mutation_type(MutationType.REFRESH_HOOK)
        assert len(results) == 1

    def test_query_by_outcome(self):
        store = ExperienceStore()
        store.add(make_record(outcome=ExperienceOutcome.SUCCESS))
        store.add(make_record(outcome=ExperienceOutcome.FAILURE, creative="c002"))
        results = store.query_by_outcome(ExperienceOutcome.SUCCESS)
        assert len(results) == 1

    def test_query_successful(self):
        store = ExperienceStore()
        store.add(make_record(outcome=ExperienceOutcome.SUCCESS))
        store.add(make_record(outcome=ExperienceOutcome.MARGINAL, creative="c002"))
        store.add(make_record(outcome=ExperienceOutcome.FAILURE, creative="c003"))
        results = store.query_successful()
        # query_successful 只返回 SUCCESS 类型，MARGINAL 也是 is_success 但不是 SUCCESS outcome
        assert len(results) == 1
        assert results[0].result.outcome == ExperienceOutcome.SUCCESS

    def test_query_by_gene(self):
        store = ExperienceStore()
        store.add(make_record())
        store.add(make_record(
            creative="c002",
            mutation_type=MutationType.FULL_REBUILD,
        ))
        results = store.query_by_gene("hook")
        assert len(results) == 2

    def test_query_complex(self):
        """多条件查询。"""
        store = ExperienceStore()
        store.add(make_record(product="p04", mutation_type=MutationType.REFRESH_HOOK, outcome=ExperienceOutcome.SUCCESS))
        store.add(make_record(product="p04", mutation_type=MutationType.FULL_REBUILD, outcome=ExperienceOutcome.FAILURE, creative="c002"))
        store.add(make_record(product="p07", mutation_type=MutationType.REFRESH_HOOK, outcome=ExperienceOutcome.SUCCESS, creative="c003"))

        q = ExperienceQuery(
            product_id="p04",
            mutation_type=MutationType.REFRESH_HOOK,
            outcome=ExperienceOutcome.SUCCESS,
        )
        results = store.query(q)
        assert len(results) == 1
        assert results[0].creative_id == "c001"

    def test_query_limit(self):
        store = ExperienceStore()
        for i in range(10):
            store.add(make_record(creative=f"c{i:03d}"))
        results = store.query(ExperienceQuery(limit=5))
        assert len(results) == 5

    def test_query_min_improvement(self):
        store = ExperienceStore()
        store.add(make_record(improvement=0.3))
        store.add(make_record(improvement=0.05, creative="c002"))
        q = ExperienceQuery(min_improvement=0.1)
        results = store.query(q)
        assert len(results) == 1

    def test_get_stats(self):
        store = ExperienceStore()
        store.add(make_record(outcome=ExperienceOutcome.SUCCESS, improvement=0.3))
        store.add(make_record(outcome=ExperienceOutcome.MARGINAL, improvement=0.08, creative="c002"))
        store.add(make_record(outcome=ExperienceOutcome.FAILURE, improvement=-0.1, creative="c003"))
        stats = store.get_stats()
        assert stats.total_records == 3
        assert stats.success_count == 2
        assert stats.success_rate == pytest.approx(2 / 3)
        assert stats.best_improvement == 0.3

    def test_get_stats_empty(self):
        store = ExperienceStore()
        stats = store.get_stats()
        assert stats.total_records == 0
        assert stats.success_rate == 0.0

    def test_get_stats_by_product(self):
        store = ExperienceStore()
        store.add(make_record(product="p04"))
        store.add(make_record(product="p04", creative="c002"))
        store.add(make_record(product="p07"))
        stats_by_product = store.get_stats_by_product()
        assert "p04" in stats_by_product
        assert stats_by_product["p04"].total_records == 2

    def test_get_stats_by_mutation_type(self):
        store = ExperienceStore()
        store.add(make_record(mutation_type=MutationType.REFRESH_HOOK))
        store.add(make_record(mutation_type=MutationType.FULL_REBUILD, creative="c002"))
        stats_by_mt = store.get_stats_by_mutation_type()
        assert "refresh_hook" in stats_by_mt
        assert "full_rebuild" in stats_by_mt

    def test_extract_patterns(self):
        store = ExperienceStore()
        for i in range(5):
            store.add(make_record(
                creative=f"c{i:03d}",
                mutation_type=MutationType.REFRESH_HOOK,
                outcome=ExperienceOutcome.SUCCESS if i < 4 else ExperienceOutcome.FAILURE,
            ))
        patterns = store.extract_patterns(min_sample=3)
        assert len(patterns) > 0
        # 应该有 mutation_pattern 和 gene_pattern
        pattern_types = {p.pattern_type for p in patterns}
        assert "mutation_pattern" in pattern_types
        assert "gene_pattern" in pattern_types

    def test_extract_patterns_insufficient_sample(self):
        store = ExperienceStore()
        store.add(make_record())
        patterns = store.extract_patterns(min_sample=5)
        assert patterns == []

    def test_get_reliable_patterns(self):
        store = ExperienceStore()
        for i in range(5):
            store.add(make_record(
                creative=f"c{i:03d}",
                outcome=ExperienceOutcome.SUCCESS,
            ))
        reliable = store.get_reliable_patterns(min_sample=3)
        assert len(reliable) > 0
        assert all(p.is_reliable for p in reliable)

    def test_to_summary(self):
        store = ExperienceStore()
        store.add(make_record())
        store.add(make_record(product="p07", creative="c002"))
        summary = store.to_summary()
        assert summary["total_records"] == 2
        assert "p04" in summary["products"]
        assert "p07" in summary["products"]

    def test_len(self):
        store = ExperienceStore()
        assert len(store) == 0
        store.add(make_record())
        assert len(store) == 1

    def test_repr(self):
        store = ExperienceStore()
        store.add(make_record())
        r = repr(store)
        assert "ExperienceStore" in r
        assert "records=1" in r


# ═══════════════════════════════════════════════════════════
# 3. ExperienceCollector (15 tests)
# ═══════════════════════════════════════════════════════════


class TestExperienceCollector:
    """ExperienceCollector — E12.4 数据 → ExperienceRecord。"""

    def test_collect_basic(self):
        collector = ExperienceCollector()
        exp = make_experiment_run()
        ev = make_evaluation()
        mr = make_mutation_request()

        record = collector.collect(
            experiment=exp,
            evaluation=ev,
            mutation_request=mr,
            product_id="p04",
            product_name="Merge Witch",
            market="US",
        )
        assert record.product_id == "p04"
        assert record.creative_id == "c001"
        assert record.mutation.mutation_type == MutationType.REFRESH_HOOK
        assert record.experiment.improvement == 0.3
        assert record.context.market == "US"
        assert record.result.outcome == ExperienceOutcome.SUCCESS

    def test_collect_success_outcome(self):
        collector = ExperienceCollector()
        record = collector.collect(
            experiment=make_experiment_run(),
            evaluation=make_evaluation(improvement=0.3),
            product_id="p04",
        )
        assert record.result.outcome == ExperienceOutcome.SUCCESS
        assert record.result.success is True

    def test_collect_marginal_outcome(self):
        collector = ExperienceCollector()
        record = collector.collect(
            experiment=make_experiment_run(),
            evaluation=make_evaluation(improvement=0.08),
            product_id="p04",
        )
        assert record.result.outcome == ExperienceOutcome.MARGINAL
        assert record.result.success is True

    def test_collect_failure_outcome(self):
        collector = ExperienceCollector()
        record = collector.collect(
            experiment=make_experiment_run(),
            # 有 winner_id 但 improvement 为负 → FAILURE
            evaluation=make_evaluation(winner="v2", improvement=-0.1),
            product_id="p04",
        )
        assert record.result.outcome == ExperienceOutcome.FAILURE
        assert record.result.success is False

    def test_collect_inconclusive_outcome(self):
        collector = ExperienceCollector()
        ev = make_evaluation(winner="", improvement=0.0)
        record = collector.collect(
            experiment=make_experiment_run(),
            evaluation=ev,
            product_id="p04",
        )
        assert record.result.outcome == ExperienceOutcome.INCONCLUSIVE

    def test_collect_with_learning_record(self):
        collector = ExperienceCollector()
        lr = EvolutionLearningRecord(
            prediction_id="rp_001",
            mutation_request_id="mr_001",
            experiment_id="exp_001",
            prediction_accuracy=0.85,
            mutation_success=True,
            insight="Stronger hook improved ROAS by 31%",
        )
        record = collector.collect(
            experiment=make_experiment_run(),
            evaluation=make_evaluation(),
            learning_record=lr,
            product_id="p04",
        )
        assert record.result.insight == "Stronger hook improved ROAS by 31%"
        assert "learning_record_id" in record.related_ids
        assert "prediction_id" in record.related_ids

    def test_collect_without_learning_record(self):
        collector = ExperienceCollector()
        record = collector.collect(
            experiment=make_experiment_run(),
            evaluation=make_evaluation(),
            product_id="p04",
        )
        assert record.result.insight == "Winner v2: CTR improved by 43%"

    def test_collect_with_gene_before_after(self):
        collector = ExperienceCollector()
        mr = make_mutation_request()
        record = collector.collect(
            experiment=make_experiment_run(),
            evaluation=make_evaluation(),
            mutation_request=mr,
            gene_before={"hook": "rescue_puppy"},
            gene_after={"hook": "save_dragon"},
            product_id="p04",
        )
        assert record.mutation.gene_before["hook"] == "rescue_puppy"
        assert record.mutation.gene_after["hook"] == "save_dragon"

    def test_collect_related_ids(self):
        collector = ExperienceCollector()
        record = collector.collect(
            experiment=make_experiment_run(),
            evaluation=make_evaluation(),
            mutation_request=make_mutation_request(),
            product_id="p04",
        )
        assert "experiment_id" in record.related_ids
        assert "evaluation_id" in record.related_ids
        assert "mutation_request_id" in record.related_ids

    def test_collect_batch(self):
        collector = ExperienceCollector()
        exps = [make_experiment_run(cid="c001"), make_experiment_run(cid="c002")]
        evs = [make_evaluation(), make_evaluation(winner="v1", improvement=0.15)]
        records = collector.collect_batch(
            experiments=exps,
            evaluations=evs,
            product_id="p04",
            market="US",
        )
        assert len(records) == 2
        assert records[0].creative_id == "c001"
        assert records[1].creative_id == "c002"

    def test_collect_from_learning_record(self):
        collector = ExperienceCollector()
        lr = EvolutionLearningRecord(
            prediction_id="rp_001",
            mutation_request_id="mr_001",
            experiment_id="exp_001",
            prediction_accuracy=0.90,
            mutation_success=True,
        )
        record = collector.collect_from_learning_record(
            learning_record=lr,
            experiment=make_experiment_run(),
            evaluation=make_evaluation(),
            mutation_request=make_mutation_request(),
            product_id="p04",
            market="US",
        )
        assert record.related_ids["learning_record_id"] == lr.record_id

    def test_collect_no_mutation_request(self):
        collector = ExperienceCollector()
        record = collector.collect(
            experiment=make_experiment_run(),
            evaluation=make_evaluation(),
            product_id="p04",
        )
        assert record.mutation.mutation_type == MutationType.REFRESH_HOOK
        assert record.mutation.changed_genes == []

    def test_collect_different_mutation_types(self):
        collector = ExperienceCollector()
        mr = make_mutation_request(intent=MutationIntent.FULL_REBUILD)
        record = collector.collect(
            experiment=make_experiment_run(),
            evaluation=make_evaluation(),
            mutation_request=mr,
            product_id="p04",
        )
        assert record.mutation.mutation_type == MutationType.FULL_REBUILD

    def test_collect_preserves_context(self):
        collector = ExperienceCollector()
        record = collector.collect(
            experiment=make_experiment_run(),
            evaluation=make_evaluation(),
            product_id="p04",
            product_name="Merge Witch",
            market="US",
            country="US",
            audience="25-45 Female",
            platform="facebook",
            campaign_type="IAA",
        )
        assert record.context.product_name == "Merge Witch"
        assert record.context.country == "US"
        assert record.context.audience == "25-45 Female"
        assert record.context.campaign_type == "IAA"

    def test_collect_key_finding(self):
        collector = ExperienceCollector()
        record = collector.collect(
            experiment=make_experiment_run(),
            evaluation=make_evaluation(),
            product_id="p04",
        )
        assert "Winner v2" in record.result.key_finding
        assert "+30%" in record.result.key_finding


# ═══════════════════════════════════════════════════════════
# 4. ExperienceQuery (10 tests)
# ═══════════════════════════════════════════════════════════


class TestExperienceQuery:
    """ExperienceQuery 多条件匹配。"""

    def test_matches_product_id(self):
        q = ExperienceQuery(product_id="p04")
        assert q.matches(make_record(product="p04"))
        assert not q.matches(make_record(product="p07"))

    def test_matches_market(self):
        q = ExperienceQuery(market="US")
        assert q.matches(make_record(market="US"))
        assert not q.matches(make_record(market="EU"))

    def test_matches_platform(self):
        q = ExperienceQuery(platform="facebook")
        record = make_record()
        record.context.platform = "google"
        assert not q.matches(record)

    def test_matches_mutation_type(self):
        q = ExperienceQuery(mutation_type=MutationType.REFRESH_HOOK)
        assert q.matches(make_record(mutation_type=MutationType.REFRESH_HOOK))
        assert not q.matches(make_record(mutation_type=MutationType.FULL_REBUILD))

    def test_matches_outcome(self):
        q = ExperienceQuery(outcome=ExperienceOutcome.SUCCESS)
        assert q.matches(make_record(outcome=ExperienceOutcome.SUCCESS))
        assert not q.matches(make_record(outcome=ExperienceOutcome.FAILURE))

    def test_matches_changed_gene(self):
        q = ExperienceQuery(changed_gene="hook")
        assert q.matches(make_record())
        q2 = ExperienceQuery(changed_gene="nonexistent")
        assert not q2.matches(make_record())

    def test_matches_min_improvement(self):
        q = ExperienceQuery(min_improvement=0.2)
        assert q.matches(make_record(improvement=0.3))
        assert not q.matches(make_record(improvement=0.05))

    def test_matches_min_confidence(self):
        q = ExperienceQuery(min_confidence=0.8)
        record = make_record()
        assert q.matches(record)
        record.experiment.confidence = 0.5
        assert not q.matches(record)

    def test_matches_combined(self):
        q = ExperienceQuery(
            product_id="p04",
            market="US",
            mutation_type=MutationType.REFRESH_HOOK,
            outcome=ExperienceOutcome.SUCCESS,
        )
        assert q.matches(make_record(
            product="p04", market="US",
            mutation_type=MutationType.REFRESH_HOOK,
            outcome=ExperienceOutcome.SUCCESS,
        ))

    def test_matches_all_false_default(self):
        """空查询匹配所有。"""
        q = ExperienceQuery()
        assert q.matches(make_record())


# ═══════════════════════════════════════════════════════════
# 5. ExperienceStats (5 tests)
# ═══════════════════════════════════════════════════════════


class TestExperienceStats:
    """ExperienceStats 聚合统计。"""

    def test_stats_defaults(self):
        stats = ExperienceStats()
        assert stats.total_records == 0
        assert stats.success_rate == 0.0
        assert stats.mean_improvement == 0.0

    def test_stats_to_dict(self):
        stats = ExperienceStats(
            total_records=10,
            success_count=7,
            success_rate=0.7,
            by_mutation_type={"refresh_hook": 6, "full_rebuild": 4},
        )
        d = stats.to_dict()
        assert d["total_records"] == 10
        assert d["success_rate"] == 0.7

    def test_stats_repr(self):
        stats = ExperienceStats(
            total_records=10,
            success_rate=0.7,
            mean_improvement=0.15,
        )
        r = repr(stats)
        assert "total=10" in r
        assert "70%" in r

    def test_stats_top_insights(self):
        stats = ExperienceStats(
            top_insights=["insight_1", "insight_2"],
        )
        assert len(stats.top_insights) == 2

    def test_stats_by_gene(self):
        stats = ExperienceStats(
            by_gene={"hook": 5, "visual_style": 3},
        )
        assert stats.by_gene["hook"] == 5


# ═══════════════════════════════════════════════════════════
# 6. ExperiencePattern (5 tests)
# ═══════════════════════════════════════════════════════════


class TestExperiencePattern:
    """ExperiencePattern 经验模式。"""

    def test_pattern_creation(self):
        pat = ExperiencePattern(
            pattern_type="gene_pattern",
            description="Changing hook succeeds 78%",
            genes=["hook"],
            success_rate=0.78,
            avg_improvement=0.25,
            sample_size=50,
            confidence=0.75,
        )
        assert pat.pattern_id.startswith("pat_")
        assert pat.is_reliable is True

    def test_pattern_unreliable_low_sample(self):
        pat = ExperiencePattern(
            pattern_type="gene_pattern",
            sample_size=2,
            confidence=0.8,
        )
        assert pat.is_reliable is False

    def test_pattern_unreliable_low_confidence(self):
        pat = ExperiencePattern(
            pattern_type="gene_pattern",
            sample_size=10,
            confidence=0.3,
        )
        assert pat.is_reliable is False

    def test_pattern_to_dict(self):
        pat = ExperiencePattern(
            pattern_type="gene_pattern",
            success_rate=0.78,
            sample_size=50,
            confidence=0.75,
            evidence=["exp_001", "exp_002"],
        )
        d = pat.to_dict()
        assert d["pattern_type"] == "gene_pattern"
        assert d["evidence_count"] == 2
        assert d["is_reliable"] is True

    def test_pattern_repr(self):
        pat = ExperiencePattern(
            pattern_type="gene_pattern",
            success_rate=0.78,
            sample_size=50,
        )
        r = repr(pat)
        assert "gene_pattern" in r
        assert "78%" in r


# ═══════════════════════════════════════════════════════════
# 7. Integration (5 tests)
# ═══════════════════════════════════════════════════════════


class TestIntegration:
    """完整集成：E12.4 → E12.5.1。"""

    def test_full_pipeline_collect_to_store(self):
        """完整流程：收集 → 存储 → 查询 → 统计。"""
        collector = ExperienceCollector()
        store = ExperienceStore()

        # 收集多条经验
        records = [
            collector.collect(
                experiment=make_experiment_run(cid="c001"),
                evaluation=make_evaluation(improvement=0.3),
                mutation_request=make_mutation_request(),
                product_id="p04", market="US",
            ),
            collector.collect(
                experiment=make_experiment_run(cid="c002"),
                evaluation=make_evaluation(improvement=-0.1, winner=""),
                mutation_request=make_mutation_request(intent=MutationIntent.FULL_REBUILD),
                product_id="p04", market="US",
            ),
            collector.collect(
                experiment=make_experiment_run(cid="c003"),
                evaluation=make_evaluation(improvement=0.2),
                mutation_request=make_mutation_request(),
                product_id="p07", market="EU",
            ),
        ]

        # 存储
        store.add_batch(records)
        assert len(store) == 3

        # 按产品查询
        p04_records = store.query_by_product("p04")
        assert len(p04_records) == 2

        # 统计
        stats = store.get_stats()
        assert stats.total_records == 3
        assert stats.success_count == 2

    def test_multi_product_experience(self):
        """多产品经验积累。"""
        collector = ExperienceCollector()
        store = ExperienceStore()

        products = ["p04", "p07", "p08"]
        for i, pid in enumerate(products):
            for j in range(3):
                record = collector.collect(
                    experiment=make_experiment_run(cid=f"{pid}_c{j}"),
                    evaluation=make_evaluation(improvement=0.2 + 0.05 * j),
                    product_id=pid, market="US",
                )
                store.add(record)

        stats_by_product = store.get_stats_by_product()
        assert len(stats_by_product) == 3
        for pid in products:
            assert pid in stats_by_product
            assert stats_by_product[pid].total_records == 3

    def test_pattern_extraction_multi_product(self):
        """多产品模式提取。"""
        collector = ExperienceCollector()
        store = ExperienceStore()

        for i in range(5):
            record = collector.collect(
                experiment=make_experiment_run(cid=f"c{i:03d}"),
                evaluation=make_evaluation(improvement=0.3),
                mutation_request=make_mutation_request(),
                product_id="p04", market="US",
            )
            store.add(record)

        patterns = store.extract_patterns(min_sample=3)
        assert len(patterns) > 0
        assert any(p.pattern_type == "context_pattern" for p in patterns)

    def test_store_summary_integration(self):
        """存储摘要包含完整信息。"""
        collector = ExperienceCollector()
        store = ExperienceStore()

        record = collector.collect(
            experiment=make_experiment_run(),
            evaluation=make_evaluation(),
            mutation_request=make_mutation_request(),
            product_id="p04", market="US",
        )
        store.add(record)

        summary = store.to_summary()
        assert "p04" in summary["products"]
        assert "US" in summary["markets"]
        assert "refresh_hook" in summary["mutation_types"]
        assert "success" in summary["outcomes"]
        assert "hook" in summary["genes"]

    def test_evolution_learning_to_experience(self):
        """EvolutionLearningRecord → ExperienceRecord 完整链路。"""
        lf = LearningFeedback()
        lr = lf.record_evolution(
            prediction_id="rp_001",
            mutation_request_id="mr_001",
            experiment_id="exp_001",
            prediction_accuracy=0.85,
            mutation_success=True,
            winner_dna={"hook": "rescue"},
            insight="Stronger rescue hook",
        )

        collector = ExperienceCollector()
        record = collector.collect_from_learning_record(
            learning_record=lr,
            experiment=make_experiment_run(),
            evaluation=make_evaluation(),
            mutation_request=make_mutation_request(),
            product_id="p04",
            market="US",
        )

        assert record.result.insight == "Stronger rescue hook"
        assert record.related_ids["learning_record_id"] == lr.record_id
        assert record.related_ids["prediction_id"] == "rp_001"

        store = ExperienceStore()
        store.add(record)
        assert len(store) == 1
        assert store.query_successful()[0].result.insight == "Stronger rescue hook"


# 需要 LearningFeedback 导入
from market_ops.creative_vision_runtime.reality.feedback import LearningFeedback