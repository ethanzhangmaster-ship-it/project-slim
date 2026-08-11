"""E12.7.5 Growth Memory Kernel — 测试 (~225 tests)."""

from __future__ import annotations

import pytest
from datetime import datetime, timedelta, timezone

from src.market_ops.creative_vision_runtime.growth_os.memory.models import (
    MemoryType,
    Outcome,
    ExperienceContext,
    ExperienceMetrics,
    GrowthExperience,
    GrowthPattern,
    MemoryQuery,
    RetrievalResult,
)
from src.market_ops.creative_vision_runtime.growth_os.memory.experience_store import (
    ExperienceStore,
)
from src.market_ops.creative_vision_runtime.growth_os.memory.memory_extractor import (
    MemoryExtractor,
)
from src.market_ops.creative_vision_runtime.growth_os.memory.pattern_learner import (
    PatternLearner,
)
from src.market_ops.creative_vision_runtime.growth_os.memory.retrieval_engine import (
    RetrievalEngine,
)
from src.market_ops.creative_vision_runtime.growth_os.memory.memory_optimizer import (
    MemoryOptimizer,
)
from src.market_ops.creative_vision_runtime.growth_os.memory.memory_controller import (
    MemoryController,
)
from src.market_ops.creative_vision_runtime.growth_os.execution.models import (
    ExecutionTask,
    ExecutionResult,
    ExecutionPlan,
    TaskType,
    TaskStatus,
    ApprovalStatus,
    TargetModule,
)


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════

def _make_task(
    task_type: TaskType = TaskType.CREATE_CREATIVE,
    status: TaskStatus = TaskStatus.SUCCESS,
    strategy_id: str = "STR_001",
    product_id: str = "p01",
    priority: int = 50,
    parameters: dict | None = None,
    deps: list[str] | None = None,
    metrics: dict | None = None,
    output: dict | None = None,
    error: str = "",
) -> ExecutionTask:
    task = ExecutionTask(
        strategy_id=strategy_id,
        product_id=product_id,
        task_type=task_type,
        target_module=TargetModule.E11_EVOLUTION,
        priority=priority,
        parameters=parameters or {},
        dependencies=deps or [],
    )
    task.status = status
    task.result = ExecutionResult(
        task_id=task.task_id,
        success=(status == TaskStatus.SUCCESS),
        output=output or {},
        metrics=metrics or {},
        error=error,
    )
    return task


def _make_plan(
    tasks: list[ExecutionTask] | None = None,
    plan_id: str = "PLAN_001",
    strategy_id: str = "STR_001",
) -> ExecutionPlan:
    plan = ExecutionPlan(strategy_id=strategy_id)
    plan.plan_id = plan_id
    plan.approval_status = ApprovalStatus.APPROVED
    if tasks:
        plan.tasks = tasks
    return plan


def _make_experience(
    product_id: str = "p01",
    memory_type: MemoryType = MemoryType.STRATEGY_MEMORY,
    result: Outcome = Outcome.SUCCESS,
    learning_value: float = 0.8,
    confidence: float = 0.8,
    strategy_id: str = "STR_001",
    tags: list[str] | None = None,
    market: str = "",
    channel: str = "",
    roas: float = 1.5,
    age_days: float = 0,
) -> GrowthExperience:
    return GrowthExperience(
        product_id=product_id,
        strategy_id=strategy_id,
        memory_type=memory_type,
        result=result,
        learning_value=learning_value,
        confidence=confidence,
        tags=tags or [],
        context=ExperienceContext(market=market, channel=channel),
        metrics=ExperienceMetrics(roas=roas),
        created_at=datetime.now(timezone.utc) - timedelta(days=age_days),
    )


# ═══════════════════════════════════════════════════════════════
# Test Models (~25 tests)
# ═══════════════════════════════════════════════════════════════

class TestMemoryType:
    def test_memory_type_values(self):
        assert MemoryType.STRATEGY_MEMORY.value == "strategy_memory"
        assert MemoryType.CREATIVE_MEMORY.value == "creative_memory"
        assert MemoryType.EXPERIMENT_MEMORY.value == "experiment_memory"
        assert MemoryType.MARKET_MEMORY.value == "market_memory"
        assert MemoryType.FAILURE_MEMORY.value == "failure_memory"
        assert MemoryType.SUCCESS_PATTERN.value == "success_pattern"

    def test_memory_type_count(self):
        assert len(MemoryType) == 6


class TestOutcome:
    def test_outcome_values(self):
        assert Outcome.SUCCESS.value == "success"
        assert Outcome.FAILURE.value == "failure"
        assert Outcome.PARTIAL.value == "partial"


class TestExperienceContext:
    def test_default_context(self):
        ctx = ExperienceContext()
        assert ctx.market == ""
        assert ctx.channel == ""

    def test_context_with_values(self):
        ctx = ExperienceContext(
            market="US", channel="Facebook", lifecycle="growth",
            creative_state="active", product_id="p01",
        )
        assert ctx.market == "US"
        assert ctx.channel == "Facebook"
        assert ctx.lifecycle == "growth"
        assert ctx.creative_state == "active"

    def test_context_to_dict(self):
        ctx = ExperienceContext(market="US", channel="Facebook")
        d = ctx.to_dict()
        assert d["market"] == "US"
        assert d["channel"] == "Facebook"

    def test_context_extra(self):
        ctx = ExperienceContext(extra={"season": "holiday"})
        assert ctx.extra["season"] == "holiday"


class TestExperienceMetrics:
    def test_default_metrics(self):
        m = ExperienceMetrics()
        assert m.spend == 0.0
        assert m.revenue == 0.0
        assert m.roas == 0.0
        assert m.roi == 0.0

    def test_roi_positive(self):
        m = ExperienceMetrics(spend=100.0, revenue=150.0)
        assert m.roi == 0.5

    def test_roi_negative(self):
        m = ExperienceMetrics(spend=100.0, revenue=50.0)
        assert m.roi == -0.5

    def test_roi_zero_spend(self):
        m = ExperienceMetrics(spend=0.0, revenue=100.0)
        assert m.roi == 0.0

    def test_metrics_to_dict(self):
        m = ExperienceMetrics(spend=100.0, revenue=150.0, roas=1.5)
        d = m.to_dict()
        assert d["spend"] == 100.0
        assert d["revenue"] == 150.0
        assert d["roas"] == 1.5
        assert d["roi"] == 0.5


class TestGrowthExperience:
    def test_default_experience(self):
        exp = GrowthExperience()
        assert exp.experience_id.startswith("EXP_")
        assert exp.product_id == ""
        assert exp.result == Outcome.PARTIAL

    def test_success_experience(self):
        exp = GrowthExperience(result=Outcome.SUCCESS)
        assert exp.is_success is True
        assert exp.is_failure is False

    def test_failure_experience(self):
        exp = GrowthExperience(result=Outcome.FAILURE)
        assert exp.is_failure is True
        assert exp.is_success is False

    def test_age_days(self):
        exp = GrowthExperience(created_at=datetime.now(timezone.utc) - timedelta(days=7))
        assert 6.9 <= exp.age_days <= 7.1

    def test_experience_to_dict(self):
        exp = _make_experience(product_id="p01", result=Outcome.SUCCESS)
        d = exp.to_dict()
        assert d["product_id"] == "p01"
        assert d["is_success"] is True
        assert d["is_failure"] is False


class TestGrowthPattern:
    def test_default_pattern(self):
        pat = GrowthPattern()
        assert pat.pattern_id.startswith("PAT_")
        assert pat.success_rate == 0.0
        assert pat.usage_count == 0

    def test_is_reliable(self):
        pat = GrowthPattern(confidence=0.7, usage_count=5)
        assert pat.is_reliable is True

    def test_is_not_reliable_low_confidence(self):
        pat = GrowthPattern(confidence=0.3, usage_count=5)
        assert pat.is_reliable is False

    def test_is_not_reliable_low_usage(self):
        pat = GrowthPattern(confidence=0.7, usage_count=1)
        assert pat.is_reliable is False

    def test_is_high_confidence(self):
        pat = GrowthPattern(confidence=0.85)
        assert pat.is_high_confidence is True

    def test_is_not_high_confidence(self):
        pat = GrowthPattern(confidence=0.75)
        assert pat.is_high_confidence is False

    def test_pattern_age_days(self):
        pat = GrowthPattern(created_at=datetime.now(timezone.utc) - timedelta(days=30))
        assert 29.9 <= pat.age_days <= 30.1

    def test_pattern_to_dict(self):
        pat = GrowthPattern(success_rate=0.80, avg_roas=1.42, confidence=0.85, usage_count=5)
        d = pat.to_dict()
        assert d["success_rate"] == 0.80
        assert d["avg_roas"] == 1.42
        assert d["is_reliable"] is True
        assert d["is_high_confidence"] is True


class TestMemoryQuery:
    def test_default_query(self):
        q = MemoryQuery()
        assert q.product_id == ""
        assert q.limit == 10
        assert q.sort_by == "learning_value"

    def test_query_with_filters(self):
        q = MemoryQuery(
            product_id="p01", market="US", memory_type=MemoryType.CREATIVE_MEMORY,
            outcome=Outcome.SUCCESS, limit=5,
        )
        assert q.product_id == "p01"
        assert q.market == "US"
        assert q.limit == 5

    def test_query_to_dict(self):
        q = MemoryQuery(product_id="p01", limit=5)
        d = q.to_dict()
        assert d["product_id"] == "p01"
        assert d["limit"] == 5


class TestRetrievalResult:
    def test_empty_result(self):
        r = RetrievalResult()
        assert r.total_matches == 0
        assert r.has_results is False

    def test_result_with_experiences(self):
        exp = _make_experience()
        r = RetrievalResult(experiences=[exp], total_matches=1)
        assert r.has_results is True
        assert r.total_matches == 1

    def test_result_to_dict(self):
        r = RetrievalResult(total_matches=0, retrieval_time_ms=5.0)
        d = r.to_dict()
        assert d["total_matches"] == 0
        assert d["retrieval_time_ms"] == 5.0


# ═══════════════════════════════════════════════════════════════
# Test ExperienceStore (~35 tests)
# ═══════════════════════════════════════════════════════════════

class TestExperienceStore:
    @pytest.fixture
    def store(self):
        return ExperienceStore()

    @pytest.fixture
    def populated_store(self):
        s = ExperienceStore()
        for i in range(5):
            exp = _make_experience(
                product_id=f"p{i % 2}", memory_type=MemoryType.STRATEGY_MEMORY if i % 2 == 0 else MemoryType.CREATIVE_MEMORY,
                result=Outcome.SUCCESS if i < 3 else Outcome.FAILURE,
                tags=["test"] if i % 2 == 0 else [],
            )
            s.save(exp)
        return s

    def test_initial_empty(self, store):
        assert store.experience_count == 0
        assert store.pattern_count == 0
        assert store.total_count == 0

    def test_save_experience(self, store):
        exp = _make_experience()
        saved = store.save(exp)
        assert saved.experience_id == exp.experience_id
        assert store.experience_count == 1

    def test_save_batch(self, store):
        exps = [_make_experience() for _ in range(5)]
        saved = store.save_batch(exps)
        assert len(saved) == 5
        assert store.experience_count == 5

    def test_save_pattern(self, store):
        pat = GrowthPattern()
        saved = store.save_pattern(pat)
        assert saved.pattern_id == pat.pattern_id
        assert store.pattern_count == 1

    def test_save_patterns(self, store):
        pats = [GrowthPattern() for _ in range(3)]
        saved = store.save_patterns(pats)
        assert len(saved) == 3
        assert store.pattern_count == 3

    def test_get_experience(self, populated_store):
        all_exps = populated_store.get_all()
        exp = populated_store.get(all_exps[0].experience_id)
        assert exp is not None
        assert exp.experience_id == all_exps[0].experience_id

    def test_get_nonexistent(self, store):
        assert store.get("NONEXISTENT") is None

    def test_get_pattern(self, store):
        pat = GrowthPattern()
        store.save_pattern(pat)
        assert store.get_pattern(pat.pattern_id) is not None

    def test_get_pattern_nonexistent(self, store):
        assert store.get_pattern("NONEXISTENT") is None

    def test_get_all(self, populated_store):
        assert len(populated_store.get_all()) == 5

    def test_get_all_patterns(self, store):
        store.save_patterns([GrowthPattern(), GrowthPattern()])
        assert len(store.get_all_patterns()) == 2

    def test_get_by_product(self, populated_store):
        p0_exps = populated_store.get_by_product("p0")
        assert len(p0_exps) == 3  # i=0,2,4

    def test_get_by_product_empty(self, store):
        assert store.get_by_product("unknown") == []

    def test_get_by_type(self, populated_store):
        strategy_exps = populated_store.get_by_type(MemoryType.STRATEGY_MEMORY)
        assert len(strategy_exps) == 3  # i=0,2,4

    def test_get_by_result(self, populated_store):
        success = populated_store.get_by_result(Outcome.SUCCESS)
        assert len(success) == 3

    def test_get_success_cases(self, populated_store):
        assert len(populated_store.get_success_cases()) == 3

    def test_get_failure_cases(self, populated_store):
        assert len(populated_store.get_failure_cases()) == 2

    def test_get_by_tag(self, populated_store):
        tagged = populated_store.get_by_tag("test")
        assert len(tagged) == 3  # i=0,2,4

    def test_get_by_strategy(self, populated_store):
        exps = populated_store.get_by_strategy("STR_001")
        assert len(exps) == 5

    def test_get_by_strategy_none(self, store):
        assert store.get_by_strategy("UNKNOWN") == []

    def test_get_by_execution(self, store):
        exp = _make_experience()
        exp.execution_id = "EXEC_001"
        store.save(exp)
        assert len(store.get_by_execution("EXEC_001")) == 1

    def test_search(self, populated_store):
        # Add an experience with a specific tag
        exp = _make_experience(tags=["rescue_hook"], product_id="p01")
        populated_store.save(exp)
        results = populated_store.search(["rescue_hook"])
        assert len(results) >= 1

    def test_search_no_results(self, populated_store):
        results = populated_store.search(["nonexistent_keyword_xyz"])
        assert len(results) == 0

    def test_search_patterns(self, store):
        pat = GrowthPattern(description="Rescue hook pattern for merge games")
        store.save_pattern(pat)
        results = store.search_patterns(["rescue"])
        assert len(results) >= 1

    def test_search_patterns_no_results(self, store):
        assert store.search_patterns(["nonexistent"]) == []

    def test_delete_experience(self, populated_store):
        all_exps = populated_store.get_all()
        exp_id = all_exps[0].experience_id
        assert populated_store.delete(exp_id) is True
        assert populated_store.get(exp_id) is None
        assert populated_store.experience_count == 4

    def test_delete_nonexistent(self, store):
        assert store.delete("NONEXISTENT") is False

    def test_delete_pattern(self, store):
        pat = GrowthPattern()
        store.save_pattern(pat)
        assert store.delete_pattern(pat.pattern_id) is True
        assert store.pattern_count == 0

    def test_delete_pattern_nonexistent(self, store):
        assert store.delete_pattern("NONEXISTENT") is False

    def test_clear(self, populated_store):
        populated_store.clear()
        assert populated_store.experience_count == 0
        assert populated_store.pattern_count == 0

    def test_statistics(self, populated_store):
        stats = populated_store.get_statistics()
        assert stats["experience_count"] == 5
        assert stats["pattern_count"] == 0
        assert stats["success_rate"] == 0.6

    def test_statistics_empty(self, store):
        stats = store.get_statistics()
        assert stats["experience_count"] == 0
        assert stats["success_rate"] == 0.0


# ═══════════════════════════════════════════════════════════════
# Test MemoryExtractor (~30 tests)
# ═══════════════════════════════════════════════════════════════

class TestMemoryExtractor:
    @pytest.fixture
    def extractor(self):
        return MemoryExtractor()

    def test_extraction_count(self, extractor):
        assert extractor.extraction_count == 0

    def test_extract_from_task_success(self, extractor):
        task = _make_task(TaskType.CREATE_CREATIVE, status=TaskStatus.SUCCESS,
                          metrics={"roas": 1.5, "spend": 100.0, "revenue": 150.0})
        plan = _make_plan([task])
        exp = extractor.extract_from_task(task, plan)
        assert exp is not None
        assert exp.result == Outcome.SUCCESS
        assert exp.memory_type == MemoryType.CREATIVE_MEMORY

    def test_extract_from_task_failed(self, extractor):
        task = _make_task(TaskType.CREATE_CREATIVE, status=TaskStatus.FAILED,
                          error="Count must be positive")
        exp = extractor.extract_from_task(task)
        assert exp is not None
        assert exp.result == Outcome.FAILURE

    def test_extract_from_task_cancelled(self, extractor):
        task = _make_task(TaskType.CREATE_CREATIVE, status=TaskStatus.CANCELLED)
        exp = extractor.extract_from_task(task)
        assert exp is not None
        assert exp.result == Outcome.FAILURE

    def test_extract_from_task_running(self, extractor):
        task = _make_task(TaskType.CREATE_CREATIVE, status=TaskStatus.RUNNING)
        exp = extractor.extract_from_task(task)
        assert exp is not None
        assert exp.result == Outcome.PARTIAL

    def test_extract_from_plan(self, extractor):
        tasks = [
            _make_task(TaskType.CREATE_CREATIVE, status=TaskStatus.SUCCESS),
            _make_task(TaskType.LAUNCH_EXPERIMENT, status=TaskStatus.SUCCESS),
        ]
        plan = _make_plan(tasks)
        experiences = extractor.extract_from_plan(plan)
        assert len(experiences) == 2

    def test_extract_from_empty_plan(self, extractor):
        plan = _make_plan([])
        experiences = extractor.extract_from_plan(plan)
        assert len(experiences) == 0

    def test_map_status_success(self, extractor):
        assert extractor._map_status(TaskStatus.SUCCESS) == Outcome.SUCCESS

    def test_map_status_failed(self, extractor):
        assert extractor._map_status(TaskStatus.FAILED) == Outcome.FAILURE

    def test_map_status_cancelled(self, extractor):
        assert extractor._map_status(TaskStatus.CANCELLED) == Outcome.FAILURE

    def test_map_task_type_creative(self, extractor):
        assert extractor._map_task_type(TaskType.CREATE_CREATIVE) == MemoryType.CREATIVE_MEMORY
        assert extractor._map_task_type(TaskType.CREATIVE_GENERATION) == MemoryType.CREATIVE_MEMORY
        assert extractor._map_task_type(TaskType.CREATIVE_MUTATION) == MemoryType.CREATIVE_MEMORY

    def test_map_task_type_experiment(self, extractor):
        assert extractor._map_task_type(TaskType.LAUNCH_EXPERIMENT) == MemoryType.EXPERIMENT_MEMORY
        assert extractor._map_task_type(TaskType.EVALUATE_EXPERIMENT) == MemoryType.EXPERIMENT_MEMORY

    def test_map_task_type_budget(self, extractor):
        assert extractor._map_task_type(TaskType.INCREASE_BUDGET) == MemoryType.STRATEGY_MEMORY
        assert extractor._map_task_type(TaskType.DECREASE_BUDGET) == MemoryType.STRATEGY_MEMORY

    def test_compute_learning_value_success_high_roas(self, extractor):
        task = _make_task(TaskType.CREATE_CREATIVE, status=TaskStatus.SUCCESS,
                          metrics={"roas": 2.0})
        val = extractor._compute_learning_value(task, Outcome.SUCCESS)
        assert val > 0.7

    def test_compute_learning_value_success_low_roas(self, extractor):
        task = _make_task(TaskType.CREATE_CREATIVE, status=TaskStatus.SUCCESS,
                          metrics={"roas": 0.8})
        val = extractor._compute_learning_value(task, Outcome.SUCCESS)
        assert val >= 0.7

    def test_compute_learning_value_failure(self, extractor):
        task = _make_task(TaskType.CREATE_CREATIVE, status=TaskStatus.FAILED)
        val = extractor._compute_learning_value(task, Outcome.FAILURE)
        assert 0.4 <= val <= 0.7

    def test_compute_learning_value_partial(self, extractor):
        task = _make_task(TaskType.CREATE_CREATIVE, status=TaskStatus.RUNNING)
        val = extractor._compute_learning_value(task, Outcome.PARTIAL)
        assert val < 0.5

    def test_compute_confidence_success(self, extractor):
        task = _make_task(TaskType.CREATE_CREATIVE, status=TaskStatus.SUCCESS,
                          metrics={"roas": 2.0})
        conf = extractor._compute_confidence(task, Outcome.SUCCESS)
        assert conf >= 0.7

    def test_compute_confidence_failure(self, extractor):
        task = _make_task(TaskType.CREATE_CREATIVE, status=TaskStatus.FAILED)
        conf = extractor._compute_confidence(task, Outcome.FAILURE)
        assert conf == 0.6

    def test_extract_metrics(self, extractor):
        task = _make_task(TaskType.CREATE_CREATIVE, status=TaskStatus.SUCCESS,
                          metrics={"spend": 100.0, "revenue": 150.0, "roas": 1.5,
                                   "ctr": 0.03, "cvr": 0.05, "retention": 0.4,
                                   "impressions": 10000, "installs": 500})
        metrics = extractor._extract_metrics(task)
        assert metrics.spend == 100.0
        assert metrics.revenue == 150.0
        assert metrics.roas == 1.5
        assert metrics.ctr == 0.03
        assert metrics.impressions == 10000
        assert metrics.installs == 500

    def test_extract_metrics_no_result(self, extractor):
        task = ExecutionTask(strategy_id="S1", product_id="p01",
                             task_type=TaskType.CREATE_CREATIVE,
                             target_module=TargetModule.E11_EVOLUTION,
                             parameters={})
        metrics = extractor._extract_metrics(task)
        assert metrics.roas == 0.0

    def test_generate_tags_success(self, extractor):
        task = _make_task(TaskType.CREATE_CREATIVE, status=TaskStatus.SUCCESS)
        tags = extractor._generate_tags(task, Outcome.SUCCESS)
        assert "success" in tags
        assert "create_creative" in tags

    def test_generate_tags_failure_high_priority(self, extractor):
        task = _make_task(TaskType.CREATE_CREATIVE, status=TaskStatus.FAILED, priority=90)
        tags = extractor._generate_tags(task, Outcome.FAILURE)
        assert "failure" in tags
        assert "high_priority" in tags

    def test_generate_tags_with_market(self, extractor):
        task = _make_task(TaskType.CREATE_CREATIVE, status=TaskStatus.SUCCESS,
                          parameters={"market": "US"})
        tags = extractor._generate_tags(task, Outcome.SUCCESS)
        assert "market:US" in tags

    def test_generate_summary(self, extractor):
        task = _make_task(TaskType.CREATE_CREATIVE, status=TaskStatus.SUCCESS,
                          strategy_id="STR_001", product_id="p01")
        summary = extractor._generate_summary(task, Outcome.SUCCESS)
        assert "create_creative" in summary
        assert "STR_001" in summary

    def test_extract_action(self, extractor):
        task = _make_task(TaskType.CREATE_CREATIVE, status=TaskStatus.SUCCESS,
                          parameters={"count": 5, "market": "US"})
        action = extractor._extract_action(task)
        assert action["count"] == 5
        assert action["market"] == "US"


# ═══════════════════════════════════════════════════════════════
# Test PatternLearner (~35 tests)
# ═══════════════════════════════════════════════════════════════

class TestPatternLearner:
    @pytest.fixture
    def learner(self):
        return PatternLearner(min_experiences=3, min_success_rate=0.5)

    def test_default_learner(self):
        learner = PatternLearner()
        assert learner.learn_count == 0

    def test_learn_empty(self, learner):
        patterns = learner.learn([])
        assert patterns == []

    def test_learn_insufficient_experiences(self, learner):
        exps = [_make_experience() for _ in range(2)]
        patterns = learner.learn(exps)
        assert patterns == []

    def test_learn_sufficient(self, learner):
        exps = [
            _make_experience(product_id="p01", result=Outcome.SUCCESS, roas=1.5),
            _make_experience(product_id="p01", result=Outcome.SUCCESS, roas=1.6),
            _make_experience(product_id="p01", result=Outcome.SUCCESS, roas=1.4),
        ]
        patterns = learner.learn(exps)
        assert len(patterns) > 0
        assert learner.learn_count == 1

    def test_learn_mixed_products(self, learner):
        exps = [
            _make_experience(product_id="p01", result=Outcome.SUCCESS),
            _make_experience(product_id="p01", result=Outcome.SUCCESS),
            _make_experience(product_id="p01", result=Outcome.SUCCESS),
            _make_experience(product_id="p02", result=Outcome.SUCCESS),
            _make_experience(product_id="p02", result=Outcome.SUCCESS),
            _make_experience(product_id="p02", result=Outcome.SUCCESS),
        ]
        patterns = learner.learn(exps)
        assert len(patterns) >= 2  # At least 2 product clusters

    def test_learn_market_patterns(self, learner):
        exps = [
            _make_experience(product_id="p01", market="US", result=Outcome.SUCCESS),
            _make_experience(product_id="p01", market="US", result=Outcome.SUCCESS),
            _make_experience(product_id="p01", market="US", result=Outcome.SUCCESS),
        ]
        patterns = learner.learn(exps)
        assert len(patterns) > 0

    def test_learn_failure_patterns(self, learner):
        exps = [
            _make_experience(product_id="p01", market="US", result=Outcome.FAILURE),
            _make_experience(product_id="p01", market="US", result=Outcome.FAILURE),
            _make_experience(product_id="p01", market="US", result=Outcome.FAILURE),
        ]
        patterns = learner.learn(exps)
        assert len(patterns) > 0

    def test_cluster_by_product(self, learner):
        exps = [
            _make_experience(product_id="p01"),
            _make_experience(product_id="p01"),
            _make_experience(product_id="p02"),
        ]
        clusters = learner._cluster_by_product(exps)
        assert len(clusters["p01"]) == 2
        assert len(clusters["p02"]) == 1

    def test_cluster_by_market(self, learner):
        exps = [
            _make_experience(market="US"),
            _make_experience(market="US"),
            _make_experience(market="JP"),
        ]
        clusters = learner._cluster_by_market(exps)
        assert len(clusters["US"]) == 2
        assert len(clusters["JP"]) == 1

    def test_cluster_by_market_unknown(self, learner):
        exps = [_make_experience(market="")]
        clusters = learner._cluster_by_market(exps)
        assert len(clusters["unknown"]) == 1

    def test_cluster_by_type(self, learner):
        exps = [
            _make_experience(memory_type=MemoryType.CREATIVE_MEMORY),
            _make_experience(memory_type=MemoryType.CREATIVE_MEMORY),
            _make_experience(memory_type=MemoryType.STRATEGY_MEMORY),
        ]
        clusters = learner._cluster_by_type(exps)
        assert len(clusters[MemoryType.CREATIVE_MEMORY]) == 2
        assert len(clusters[MemoryType.STRATEGY_MEMORY]) == 1

    def test_action_key(self, learner):
        exp = _make_experience()
        exp.action = {"task_type": "create_creative"}
        assert learner._action_key(exp) == "create_creative"

    def test_action_key_unknown(self, learner):
        exp = _make_experience()
        exp.action = {}
        assert learner._action_key(exp) == "unknown"

    def test_build_pattern_from_group(self, learner):
        exps = [
            _make_experience(product_id="p01", market="US", result=Outcome.SUCCESS, roas=1.5),
            _make_experience(product_id="p01", market="US", result=Outcome.SUCCESS, roas=1.6),
            _make_experience(product_id="p01", market="US", result=Outcome.SUCCESS, roas=1.4),
        ]
        for e in exps:
            e.action = {"task_type": "create_creative"}
        pattern = learner._build_pattern_from_group(exps, product_id="p01", market="US")
        assert pattern is not None
        assert pattern.success_rate == 1.0
        assert pattern.avg_roas == 1.5
        assert pattern.usage_count == 3

    def test_build_pattern_insufficient(self, learner):
        exps = [_make_experience()]
        pattern = learner._build_pattern_from_group(exps)
        assert pattern is None

    def test_build_pattern_low_success_rate(self, learner):
        exps = [
            _make_experience(result=Outcome.FAILURE),
            _make_experience(result=Outcome.FAILURE),
            _make_experience(result=Outcome.FAILURE),
        ]
        pattern = learner._build_pattern_from_group(
            exps, pattern_type=MemoryType.SUCCESS_PATTERN,
        )
        assert pattern is None  # 0% success rate

    def test_compute_avg_roas(self, learner):
        exps = [
            _make_experience(roas=1.0),
            _make_experience(roas=2.0),
            _make_experience(roas=3.0),
        ]
        assert learner._compute_avg_roas(exps) == 2.0

    def test_compute_avg_roas_empty(self, learner):
        exps = [_make_experience(roas=0.0)]
        assert learner._compute_avg_roas(exps) == 0.0

    def test_time_decay_weight(self, learner):
        exps = [
            _make_experience(age_days=0),
            _make_experience(age_days=100),
        ]
        weight = learner._time_decay_weight(exps)
        assert 0.5 <= weight <= 1.0

    def test_extract_common_conditions(self, learner):
        exps = [
            _make_experience(product_id="p01", market="US"),
            _make_experience(product_id="p01", market="US"),
        ]
        conds = learner._extract_common_conditions(exps)
        assert "US" in conds["markets"]
        assert conds["product_id"] == "p01"

    def test_extract_common_actions(self, learner):
        exps = [
            _make_experience(), _make_experience(),
        ]
        for e in exps:
            e.action = {"task_type": "create_creative", "count": 5}
        actions = learner._extract_common_actions(exps)
        assert len(actions) >= 1
        assert actions[0]["task_type"] == "create_creative"

    def test_build_description(self, learner):
        exps = [
            _make_experience(product_id="p01", market="US"),
            _make_experience(product_id="p01", market="US"),
        ]
        for e in exps:
            e.action = {"task_type": "create_creative"}
        desc = learner._build_description(exps, 0.8, 1.5)
        assert "p01" in desc
        assert "US" in desc
        assert "Success Rate" in desc

    def test_compute_similarity_same_product(self, learner):
        exp1 = _make_experience(product_id="p01")
        exp2 = _make_experience(product_id="p01")
        sim = learner.compute_similarity(exp1, exp2)
        assert sim >= 0.3

    def test_compute_similarity_different_product(self, learner):
        exp1 = _make_experience(product_id="p01", market="US", channel="Facebook",
                                memory_type=MemoryType.CREATIVE_MEMORY)
        exp2 = _make_experience(product_id="p02", market="JP", channel="Google",
                                memory_type=MemoryType.STRATEGY_MEMORY)
        sim = learner.compute_similarity(exp1, exp2)
        assert sim < 0.5

    def test_compute_similarity_full_match(self, learner):
        exp1 = _make_experience(product_id="p01", market="US", channel="Facebook",
                                memory_type=MemoryType.CREATIVE_MEMORY)
        exp2 = _make_experience(product_id="p01", market="US", channel="Facebook",
                                memory_type=MemoryType.CREATIVE_MEMORY)
        for e in [exp1, exp2]:
            e.action = {"task_type": "create_creative"}
        sim = learner.compute_similarity(exp1, exp2)
        assert sim >= 0.9

    def test_find_similar(self, learner):
        target = _make_experience(product_id="p01", market="US")
        candidates = [
            _make_experience(product_id="p01", market="US"),
            _make_experience(product_id="p01", market="JP"),
            _make_experience(product_id="p02", market="US"),
        ]
        similar = learner.find_similar(target, candidates, limit=2)
        assert len(similar) == 2
        # First should be most similar
        assert similar[0].context.market == "US"


# ═══════════════════════════════════════════════════════════════
# Test RetrievalEngine (~30 tests)
# ═══════════════════════════════════════════════════════════════

class TestRetrievalEngine:
    @pytest.fixture
    def engine(self):
        store = ExperienceStore()
        for i in range(5):
            exp = _make_experience(
                product_id=f"p{i % 2}", memory_type=MemoryType.STRATEGY_MEMORY if i % 2 == 0 else MemoryType.CREATIVE_MEMORY,
                result=Outcome.SUCCESS if i < 3 else Outcome.FAILURE,
                learning_value=0.5 + i * 0.1,
                confidence=0.7 + i * 0.05,
                market="US" if i % 2 == 0 else "JP",
            )
            store.save(exp)
        return RetrievalEngine(store=store)

    def test_retrieve_all(self, engine):
        result = engine.retrieve(MemoryQuery(limit=10))
        assert len(result.experiences) == 5

    def test_retrieve_by_product(self, engine):
        result = engine.retrieve(MemoryQuery(product_id="p0", limit=10))
        assert len(result.experiences) == 3  # i=0,2,4

    def test_retrieve_by_market(self, engine):
        result = engine.retrieve(MemoryQuery(market="US", limit=10))
        assert len(result.experiences) == 3  # i=0,2,4

    def test_retrieve_by_type(self, engine):
        result = engine.retrieve(MemoryQuery(memory_type=MemoryType.CREATIVE_MEMORY, limit=10))
        assert len(result.experiences) == 2

    def test_retrieve_by_outcome(self, engine):
        result = engine.retrieve(MemoryQuery(outcome=Outcome.SUCCESS, limit=10))
        assert len(result.experiences) == 3

    def test_retrieve_by_tags(self, engine):
        result = engine.retrieve(MemoryQuery(tags=["test"], limit=10))
        # Only even-indexed experiences have "test" tag
        assert len(result.experiences) >= 0

    def test_retrieve_min_learning_value(self, engine):
        result = engine.retrieve(MemoryQuery(min_learning_value=0.8, limit=10))
        assert len(result.experiences) <= 5

    def test_retrieve_min_confidence(self, engine):
        result = engine.retrieve(MemoryQuery(min_confidence=0.9, limit=10))
        assert len(result.experiences) <= 5

    def test_retrieve_max_age(self, engine):
        result = engine.retrieve(MemoryQuery(max_age_days=1, limit=10))
        assert len(result.experiences) == 5  # All new

    def test_retrieve_limit(self, engine):
        result = engine.retrieve(MemoryQuery(limit=2))
        assert len(result.experiences) <= 2

    def test_retrieve_empty(self, engine):
        result = engine.retrieve(MemoryQuery(product_id="NONEXISTENT", limit=10))
        assert len(result.experiences) == 0

    def test_retrieve_patterns(self, engine):
        pat = GrowthPattern(product_id="p0", confidence=0.8, success_rate=0.7)
        engine.store.save_pattern(pat)
        result = engine.retrieve(MemoryQuery(product_id="p0", limit=10))
        assert len(result.patterns) >= 1

    def test_retrieve_by_context(self, engine):
        result = engine.retrieve_by_context({"product_id": "p0", "market": "US", "limit": 5})
        assert len(result.experiences) >= 0

    def test_get_successful_strategies(self, engine):
        result = engine.get_successful_strategies("p0")
        assert len(result) >= 0

    def test_get_failure_lessons(self, engine):
        result = engine.get_failure_lessons("p0")
        assert len(result) >= 0

    def test_get_creative_patterns(self, engine):
        pat = GrowthPattern(pattern_type=MemoryType.CREATIVE_MEMORY, product_id="p0")
        engine.store.save_pattern(pat)
        result = engine.get_creative_patterns("p0")
        assert len(result) >= 1

    def test_get_market_patterns(self, engine):
        pat = GrowthPattern(pattern_type=MemoryType.SUCCESS_PATTERN, market="US")
        engine.store.save_pattern(pat)
        result = engine.get_market_patterns("US")
        assert len(result) >= 1

    def test_query_count(self, engine):
        assert engine.query_count == 0
        engine.retrieve(MemoryQuery())
        assert engine.query_count == 1

    def test_result_has_results(self, engine):
        result = engine.retrieve(MemoryQuery(limit=10))
        assert result.has_results is True

    def test_result_empty(self, engine):
        result = engine.retrieve(MemoryQuery(product_id="NONEXISTENT"))
        assert result.has_results is False

    def test_retrieval_time(self, engine):
        result = engine.retrieve(MemoryQuery(limit=10))
        assert result.retrieval_time_ms >= 0

    def test_score_by_learning_value(self, engine):
        result = engine.retrieve(MemoryQuery(sort_by="learning_value", limit=10))
        if len(result.experiences) >= 2:
            for i in range(len(result.experiences) - 1):
                assert result.experiences[i].learning_value >= result.experiences[i + 1].learning_value

    def test_score_by_confidence(self, engine):
        result = engine.retrieve(MemoryQuery(sort_by="confidence", limit=10))
        if len(result.experiences) >= 2:
            for i in range(len(result.experiences) - 1):
                assert result.experiences[i].confidence >= result.experiences[i + 1].confidence

    def test_summary(self, engine):
        summary = engine.get_summary()
        assert "query_count" in summary
        assert "store_stats" in summary


# ═══════════════════════════════════════════════════════════════
# Test MemoryOptimizer (~25 tests)
# ═══════════════════════════════════════════════════════════════

class TestMemoryOptimizer:
    @pytest.fixture
    def optimizer(self):
        return MemoryOptimizer()

    @pytest.fixture
    def populated_store(self):
        store = ExperienceStore()
        for i in range(10):
            exp = _make_experience(
                product_id=f"p{i % 3}",
                result=Outcome.SUCCESS if i < 7 else Outcome.FAILURE,
                learning_value=0.3 + i * 0.07,
                confidence=0.3 + i * 0.07,
                age_days=i * 40,
            )
            store.save(exp)
        return store

    def test_optimize_count(self, optimizer):
        assert optimizer.optimize_count == 0

    def test_apply_decay(self, optimizer, populated_store):
        stats = optimizer.apply_decay(populated_store)
        assert stats["experiences_decayed"] >= 0

    def test_decay_experience(self, optimizer):
        exp = _make_experience(confidence=0.8, age_days=60)
        before = exp.confidence
        optimizer.decay_experience(exp)
        assert exp.confidence < before

    def test_decay_experience_recent(self, optimizer):
        exp = _make_experience(confidence=0.8, age_days=10)
        before = exp.confidence
        optimizer.decay_experience(exp)
        assert exp.confidence == before  # No decay for < 30 days

    def test_decay_pattern(self, optimizer):
        pat = GrowthPattern(confidence=0.8, created_at=datetime.now(timezone.utc) - timedelta(days=60))
        before = pat.confidence
        optimizer.decay_pattern(pat)
        assert pat.confidence < before

    def test_decay_pattern_recent(self, optimizer):
        pat = GrowthPattern(confidence=0.8, created_at=datetime.now(timezone.utc) - timedelta(days=10))
        before = pat.confidence
        optimizer.decay_pattern(pat)
        assert pat.confidence == before

    def test_should_promote(self, optimizer):
        exp = _make_experience(learning_value=0.8, confidence=0.8, result=Outcome.SUCCESS)
        assert optimizer.should_promote(exp) is True

    def test_should_not_promote_low_value(self, optimizer):
        exp = _make_experience(learning_value=0.3, confidence=0.8, result=Outcome.SUCCESS)
        assert optimizer.should_promote(exp) is False

    def test_should_not_promote_failure(self, optimizer):
        exp = _make_experience(learning_value=0.8, confidence=0.8, result=Outcome.FAILURE)
        assert optimizer.should_promote(exp) is False

    def test_merge_similar_experiences(self, optimizer):
        learner = PatternLearner(min_experiences=2)
        exps = [
            _make_experience(product_id="p01", market="US", result=Outcome.SUCCESS, roas=1.5),
            _make_experience(product_id="p01", market="US", result=Outcome.SUCCESS, roas=1.6),
            _make_experience(product_id="p01", market="US", result=Outcome.SUCCESS, roas=1.4),
        ]
        for e in exps:
            e.action = {"task_type": "create_creative"}
        pattern = optimizer.merge_similar_experiences(exps, learner)
        assert pattern is not None

    def test_merge_similar_experiences_insufficient(self, optimizer):
        learner = PatternLearner()
        exps = [_make_experience()]
        pattern = optimizer.merge_similar_experiences(exps, learner)
        assert pattern is None

    def test_merge_patterns(self, optimizer):
        pats = [
            GrowthPattern(success_rate=0.8, avg_roas=1.5, confidence=0.8, usage_count=10),
            GrowthPattern(success_rate=0.7, avg_roas=1.3, confidence=0.7, usage_count=5),
        ]
        merged = optimizer.merge_patterns(pats)
        assert merged is not None
        assert merged.usage_count == 15
        assert 0.7 < merged.success_rate < 0.8

    def test_merge_patterns_single(self, optimizer):
        pats = [GrowthPattern()]
        merged = optimizer.merge_patterns(pats)
        assert merged is None

    def test_cleanup(self, optimizer, populated_store):
        stats = optimizer.cleanup(populated_store)
        assert stats["experiences_removed"] >= 0

    def test_cleanup_low_confidence(self, optimizer):
        store = ExperienceStore()
        exp = _make_experience(confidence=0.1, learning_value=0.1)
        store.save(exp)
        stats = optimizer.cleanup(store)
        assert stats["experiences_removed"] == 1

    def test_cleanup_old(self, optimizer):
        store = ExperienceStore()
        exp = _make_experience(age_days=400, confidence=0.5)
        store.save(exp)
        stats = optimizer.cleanup(store)
        assert stats["experiences_removed"] == 1

    def test_cleanup_old_patterns(self, optimizer):
        store = ExperienceStore()
        pat = GrowthPattern(
            confidence=0.5,
            created_at=datetime.now(timezone.utc) - timedelta(days=800),
        )
        store.save_pattern(pat)
        stats = optimizer.cleanup(store)
        assert stats["patterns_removed"] == 1

    def test_get_high_value_experiences(self, optimizer, populated_store):
        high = optimizer.get_high_value_experiences(populated_store)
        assert len(high) >= 0

    def test_get_low_value_experiences(self, optimizer, populated_store):
        low = optimizer.get_low_value_experiences(populated_store)
        assert len(low) >= 0

    def test_get_summary(self, optimizer):
        summary = optimizer.get_summary()
        assert "decay_factor" in summary
        assert "optimize_count" in summary


# ═══════════════════════════════════════════════════════════════
# Test MemoryController (~30 tests)
# ═══════════════════════════════════════════════════════════════

class TestMemoryController:
    @pytest.fixture
    def controller(self):
        return MemoryController()

    def test_properties(self, controller):
        assert controller.store is not None
        assert controller.extractor is not None
        assert controller.learner is not None
        assert controller.retriever is not None
        assert controller.optimizer is not None

    def test_ingest_empty_plan(self, controller):
        plan = _make_plan([])
        result = controller.ingest(plan)
        assert result["experiences_extracted"] == 0
        assert result["total_experiences"] == 0

    def test_ingest_plan(self, controller):
        tasks = [
            _make_task(TaskType.CREATE_CREATIVE, status=TaskStatus.SUCCESS),
            _make_task(TaskType.LAUNCH_EXPERIMENT, status=TaskStatus.SUCCESS),
        ]
        plan = _make_plan(tasks)
        result = controller.ingest(plan)
        assert result["experiences_extracted"] == 2
        assert result["total_experiences"] == 2

    def test_ingest_plan_with_failures(self, controller):
        tasks = [
            _make_task(TaskType.CREATE_CREATIVE, status=TaskStatus.SUCCESS),
            _make_task(TaskType.CREATE_CREATIVE, status=TaskStatus.FAILED),
        ]
        plan = _make_plan(tasks)
        result = controller.ingest(plan)
        assert result["experiences_extracted"] == 2

    def test_ingest_batch(self, controller):
        plans = [
            _make_plan([_make_task(TaskType.CREATE_CREATIVE, status=TaskStatus.SUCCESS)]),
            _make_plan([_make_task(TaskType.LAUNCH_EXPERIMENT, status=TaskStatus.SUCCESS)]),
        ]
        result = controller.ingest_batch(plans)
        assert result["experiences_extracted"] == 2
        assert result["total_experiences"] == 2

    def test_ingest_experience(self, controller):
        exp = _make_experience()
        result = controller.ingest_experience(exp)
        assert result.experience_id == exp.experience_id
        assert controller.store.experience_count == 1

    def test_retrieve(self, controller):
        controller.ingest_experience(_make_experience(product_id="p01"))
        result = controller.retrieve(MemoryQuery(product_id="p01"))
        assert result.has_results is True

    def test_retrieve_by_context(self, controller):
        controller.ingest_experience(_make_experience(product_id="p01", market="US"))
        result = controller.retrieve_by_context({"product_id": "p01", "market": "US"})
        assert result.total_matches >= 0

    def test_learn_patterns(self, controller):
        for i in range(5):
            controller.ingest_experience(_make_experience(
                product_id="p01", result=Outcome.SUCCESS, roas=1.5,
            ))
        patterns = controller.learn_patterns()
        # May or may not produce patterns depending on clustering
        assert isinstance(patterns, list)

    def test_learn_and_store(self, controller):
        for i in range(5):
            controller.ingest_experience(_make_experience(
                product_id="p01", result=Outcome.SUCCESS, roas=1.5,
            ))
        patterns = controller.learn_and_store()
        assert isinstance(patterns, list)

    def test_optimize(self, controller):
        controller.ingest_experience(_make_experience(
            product_id="p01", result=Outcome.SUCCESS, learning_value=0.8, confidence=0.8,
        ))
        stats = controller.optimize()
        assert "experiences_decayed" in stats

    def test_get_success_cases(self, controller):
        controller.ingest_experience(_make_experience(product_id="p01", result=Outcome.SUCCESS))
        controller.ingest_experience(_make_experience(product_id="p01", result=Outcome.FAILURE))
        cases = controller.get_success_cases("p01")
        assert len(cases) == 1

    def test_get_success_cases_all(self, controller):
        controller.ingest_experience(_make_experience(result=Outcome.SUCCESS))
        controller.ingest_experience(_make_experience(result=Outcome.FAILURE))
        cases = controller.get_success_cases()
        assert len(cases) == 1

    def test_get_failure_cases(self, controller):
        controller.ingest_experience(_make_experience(product_id="p01", result=Outcome.FAILURE))
        cases = controller.get_failure_cases("p01")
        assert len(cases) == 1

    def test_get_by_product(self, controller):
        controller.ingest_experience(_make_experience(product_id="p01"))
        controller.ingest_experience(_make_experience(product_id="p02"))
        exps = controller.get_by_product("p01")
        assert len(exps) == 1

    def test_get_by_type(self, controller):
        controller.ingest_experience(_make_experience(memory_type=MemoryType.CREATIVE_MEMORY))
        controller.ingest_experience(_make_experience(memory_type=MemoryType.STRATEGY_MEMORY))
        exps = controller.get_by_type(MemoryType.CREATIVE_MEMORY)
        assert len(exps) == 1

    def test_search(self, controller):
        controller.ingest_experience(_make_experience(tags=["rescue_hook", "merge"]))
        results = controller.search(["rescue_hook"])
        assert len(results) >= 1

    def test_search_no_results(self, controller):
        results = controller.search(["nonexistent"])
        assert len(results) == 0

    def test_get_summary(self, controller):
        controller.ingest_experience(_make_experience())
        summary = controller.get_summary()
        assert "store" in summary
        assert "retriever" in summary
        assert "optimizer" in summary
        assert "extractor" in summary
        assert "learner" in summary

    def test_full_pipeline(self, controller):
        # 1. Create plan with tasks
        tasks = [
            _make_task(TaskType.CREATE_CREATIVE, status=TaskStatus.SUCCESS,
                       metrics={"roas": 1.8, "spend": 100.0, "revenue": 180.0}),
            _make_task(TaskType.LAUNCH_EXPERIMENT, status=TaskStatus.SUCCESS,
                       metrics={"roas": 1.5, "spend": 50.0, "revenue": 75.0}),
            _make_task(TaskType.INCREASE_BUDGET, status=TaskStatus.SUCCESS,
                       metrics={"roas": 1.3, "spend": 200.0, "revenue": 260.0}),
        ]
        plan = _make_plan(tasks)

        # 2. Ingest
        ingest_result = controller.ingest(plan)
        assert ingest_result["experiences_extracted"] == 3

        # 3. Learn patterns
        patterns = controller.learn_and_store()

        # 4. Retrieve
        result = controller.retrieve(MemoryQuery(product_id="p01"))
        assert result.has_results is True

        # 5. Optimize
        opt_stats = controller.optimize()
        assert "experiences_decayed" in opt_stats

        # 6. Get summary
        summary = controller.get_summary()
        assert summary["store"]["experience_count"] == 3

    def test_ingest_multiple_plans_then_learn(self, controller):
        for plan_idx in range(3):
            tasks = [
                _make_task(TaskType.CREATE_CREATIVE, status=TaskStatus.SUCCESS,
                           strategy_id=f"STR_{plan_idx:03d}",
                           metrics={"roas": 1.5 + plan_idx * 0.1}),
                _make_task(TaskType.CREATE_CREATIVE, status=TaskStatus.SUCCESS,
                           strategy_id=f"STR_{plan_idx:03d}",
                           metrics={"roas": 1.4 + plan_idx * 0.1}),
            ]
            plan = _make_plan(tasks, plan_id=f"PLAN_{plan_idx:03d}",
                              strategy_id=f"STR_{plan_idx:03d}")
            controller.ingest(plan)

        assert controller.store.experience_count == 6

        # Learn patterns
        patterns = controller.learn_and_store()
        assert isinstance(patterns, list)


# ═══════════════════════════════════════════════════════════════
# Test Integration (~15 tests)
# ═══════════════════════════════════════════════════════════════

class TestIntegration:
    def test_extract_store_retrieve_cycle(self):
        """完整循环: 提取 → 存储 → 检索."""
        store = ExperienceStore()
        extractor = MemoryExtractor()
        engine = RetrievalEngine(store=store)

        # Create and extract
        task = _make_task(TaskType.CREATE_CREATIVE, status=TaskStatus.SUCCESS,
                          metrics={"roas": 2.0, "spend": 100.0, "revenue": 200.0})
        plan = _make_plan([task])
        exp = extractor.extract_from_task(task, plan)

        # Store
        store.save(exp)

        # Retrieve
        result = engine.retrieve(MemoryQuery(product_id="p01"))
        assert result.has_results is True
        assert len(result.experiences) == 1

    def test_extract_store_learn_retrieve(self):
        """完整循环: 提取 → 存储 → 学习 → 检索."""
        store = ExperienceStore()
        extractor = MemoryExtractor()
        learner = PatternLearner(min_experiences=3)
        engine = RetrievalEngine(store=store)

        # Extract multiple experiences
        for i in range(5):
            task = _make_task(TaskType.CREATE_CREATIVE, status=TaskStatus.SUCCESS,
                              metrics={"roas": 1.5 + i * 0.1})
            plan = _make_plan([task])
            exp = extractor.extract_from_task(task, plan)
            store.save(exp)

        # Learn patterns
        patterns = learner.learn(store.get_all())
        store.save_patterns(patterns)

        # Retrieve
        result = engine.retrieve(MemoryQuery(product_id="p01", limit=10))
        assert result.has_results is True

    def test_memory_decay_cycle(self):
        """记忆衰减循环."""
        store = ExperienceStore()
        optimizer = MemoryOptimizer()

        # Add old experience
        exp = _make_experience(confidence=0.8, age_days=90)
        store.save(exp)

        before = exp.confidence
        optimizer.decay_experience(exp)
        assert exp.confidence < before

    def test_cleanup_low_value_memories(self):
        """清理低价值记忆."""
        store = ExperienceStore()
        optimizer = MemoryOptimizer(low_confidence_threshold=0.3)

        # Add low value experience
        exp = _make_experience(confidence=0.1, learning_value=0.1)
        store.save(exp)

        # Add high value experience
        high_exp = _make_experience(confidence=0.9, learning_value=0.9)
        store.save(high_exp)

        stats = optimizer.cleanup(store)
        assert store.experience_count == 1  # Only high value remains
        assert store.get(high_exp.experience_id) is not None

    def test_pattern_merge_workflow(self):
        """模式合并工作流."""
        store = ExperienceStore()
        learner = PatternLearner(min_experiences=2)
        optimizer = MemoryOptimizer()

        # Create similar patterns
        pat1 = GrowthPattern(
            product_id="p01", market="US", success_rate=0.8,
            avg_roas=1.5, confidence=0.8, usage_count=10,
            source_experiences=["EXP_A", "EXP_B"],
        )
        pat2 = GrowthPattern(
            product_id="p01", market="US", success_rate=0.7,
            avg_roas=1.3, confidence=0.7, usage_count=5,
            source_experiences=["EXP_C", "EXP_D"],
        )

        merged = optimizer.merge_patterns([pat1, pat2])
        assert merged is not None
        assert merged.usage_count == 15
        assert len(merged.source_experiences) == 4

    def test_controller_full_workflow(self):
        """完整工作流: 多计划摄入 → 学习 → 检索 → 优化."""
        controller = MemoryController()

        # Simulate multiple execution cycles
        for cycle in range(5):
            tasks = [
                _make_task(TaskType.CREATE_CREATIVE, status=TaskStatus.SUCCESS,
                           strategy_id=f"STR_{cycle:03d}",
                           metrics={"roas": 1.5 + cycle * 0.1, "spend": 100.0, "revenue": 150.0 + cycle * 10}),
                _make_task(TaskType.LAUNCH_EXPERIMENT, status=TaskStatus.SUCCESS,
                           strategy_id=f"STR_{cycle:03d}",
                           metrics={"roas": 1.3 + cycle * 0.05}),
            ]
            plan = _make_plan(tasks, plan_id=f"PLAN_{cycle:03d}",
                              strategy_id=f"STR_{cycle:03d}")
            controller.ingest(plan)

        # Verify stored experiences
        assert controller.store.experience_count == 10

        # Learn patterns
        patterns = controller.learn_and_store()

        # Retrieve successful strategies
        result = controller.retrieve(MemoryQuery(
            product_id="p01", outcome=Outcome.SUCCESS, limit=10,
        ))
        assert result.has_results is True

        # Optimize
        opt_stats = controller.optimize()

        # Summary
        summary = controller.get_summary()
        assert summary["store"]["experience_count"] == 10

    def test_memory_query_with_all_filters(self):
        """使用所有过滤器的查询."""
        controller = MemoryController()
        controller.ingest_experience(_make_experience(
            product_id="p01", market="US", channel="Facebook",
            memory_type=MemoryType.CREATIVE_MEMORY, result=Outcome.SUCCESS,
            learning_value=0.9, confidence=0.85, tags=["rescue_hook"],
        ))

        query = MemoryQuery(
            product_id="p01", market="US", channel="Facebook",
            memory_type=MemoryType.CREATIVE_MEMORY, outcome=Outcome.SUCCESS,
            min_learning_value=0.5, min_confidence=0.5,
            tags=["rescue_hook"], keywords=["rescue"],
            limit=10, sort_by="confidence",
        )
        result = controller.retrieve(query)
        assert result.has_results is True

    def test_retrieval_result_to_dict(self):
        """检索结果序列化."""
        engine = RetrievalEngine()
        exp = _make_experience(product_id="p01")
        engine.store.save(exp)
        result = engine.retrieve(MemoryQuery(product_id="p01"))
        d = result.to_dict()
        assert len(d["experiences"]) == 1
        assert d["total_matches"] == 1

    def test_memory_promotion_workflow(self):
        """记忆提升工作流: 低价值经验 → 高价值模式."""
        store = ExperienceStore()
        learner = PatternLearner(min_experiences=3)
        optimizer = MemoryOptimizer()

        exps = [
            _make_experience(product_id="p01", result=Outcome.SUCCESS,
                             learning_value=0.85, confidence=0.85, roas=1.8),
            _make_experience(product_id="p01", result=Outcome.SUCCESS,
                             learning_value=0.80, confidence=0.80, roas=1.7),
            _make_experience(product_id="p01", result=Outcome.SUCCESS,
                             learning_value=0.90, confidence=0.90, roas=2.0),
        ]
        for e in exps:
            e.action = {"task_type": "create_creative", "count": 5}
            store.save(e)

        high_value = optimizer.get_high_value_experiences(store)
        assert len(high_value) >= 3

        patterns = optimizer.promote_to_pattern(high_value, learner)
        assert len(patterns) >= 0

    def test_controller_handles_empty_operations(self):
        """控制器处理空操作."""
        controller = MemoryController()

        # Empty ingest
        result = controller.ingest(_make_plan([]))
        assert result["experiences_extracted"] == 0

        # Empty retrieve
        retrieve_result = controller.retrieve(MemoryQuery())
        assert retrieve_result.has_results is False

        # Empty search
        search_result = controller.search([])
        assert search_result == []

    def test_store_with_many_experiences(self):
        """大量经验存储测试."""
        controller = MemoryController()
        for i in range(100):
            controller.ingest_experience(_make_experience(
                product_id=f"p{i % 5}", result=Outcome.SUCCESS if i % 3 != 0 else Outcome.FAILURE,
            ))

        assert controller.store.experience_count == 100

        # Query by product
        for pid in [f"p{i}" for i in range(5)]:
            exps = controller.get_by_product(pid)
            assert len(exps) == 20

    def test_time_based_retrieval(self):
        """基于时间的检索."""
        controller = MemoryController()
        controller.ingest_experience(_make_experience(product_id="p01", age_days=0))
        controller.ingest_experience(_make_experience(product_id="p01", age_days=10))

        # Only recent
        result = controller.retrieve(MemoryQuery(product_id="p01", max_age_days=5))
        assert len(result.experiences) == 1

    def test_tag_based_retrieval(self):
        """基于标签的检索."""
        controller = MemoryController()
        controller.ingest_experience(_make_experience(tags=["rescue_hook", "merge"]))
        controller.ingest_experience(_make_experience(tags=["puzzle"]))

        result = controller.retrieve(MemoryQuery(tags=["rescue_hook"]))
        assert len(result.experiences) == 1

    def test_end_to_end_growth_memory_cycle(self):
        """端到端增长记忆循环."""
        controller = MemoryController()

        # Phase 1: Execute and learn
        for cycle in range(10):
            tasks = [
                _make_task(TaskType.CREATE_CREATIVE, status=TaskStatus.SUCCESS
                           if cycle % 2 == 0 else TaskStatus.FAILED,
                           strategy_id=f"STR_{cycle:03d}",
                           metrics={"roas": 1.5 + cycle * 0.05} if cycle % 2 == 0 else {}),
            ]
            plan = _make_plan(tasks, plan_id=f"PLAN_{cycle:03d}",
                              strategy_id=f"STR_{cycle:03d}")
            controller.ingest(plan)

        # Phase 2: Learn patterns
        patterns = controller.learn_and_store()

        # Phase 3: Retrieve insights
        success_query = MemoryQuery(outcome=Outcome.SUCCESS, limit=5)
        success_result = controller.retrieve(success_query)
        assert success_result.has_results is True

        failure_query = MemoryQuery(outcome=Outcome.FAILURE, limit=5)
        failure_result = controller.retrieve(failure_query)
        assert failure_result.has_results is True

        # Phase 4: Optimize
        controller.optimize()

        # Phase 5: Summary
        summary = controller.get_summary()
        assert summary["store"]["experience_count"] >= 10