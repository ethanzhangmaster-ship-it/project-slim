"""E14.7.2 Growth Execution Engine — 集成测试.

验证 GrowthExecutionEngine 的增长执行能力:
  - Models: ExecutionStatus / ExecutionOutcome (20 tests)
  - Registry: 执行器注册/注销/查询 (20 tests)
  - Creative Executor: 创意生成/变异/变异体 (25 tests)
  - Meta Ads Executor: 推广/放量/降预算/暂停 (25 tests)
  - Experiment Executor: 启动/结束实验 (15 tests)
  - Batch Execution: 批量执行与并发控制 (15 tests)
  - Error Handling: 错误处理 (15 tests)
  - Regression E14.5/E14.6/E14.7.1: 集成回归 (15 tests)

总计: 150 个测试用例
"""

from __future__ import annotations

import pytest

from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.growth_execution_engine import (
    GrowthExecutionEngine,
    ExecutionStatus,
    ExecutionOutcome,
    BaseExecutor,
    CreativeExecutor,
    MetaAdsExecutor,
    ExperimentExecutor,
    EvolutionExecutor,
    NoOpExecutor,
    create_growth_execution_engine,
)
from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.growth_action_router import (
    GrowthAction,
    GrowthActionType,
    ActionPriority,
    ActionSource,
)


# ═══════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════

def _make_action(
    action_type: GrowthActionType = GrowthActionType.PROMOTE_WINNER,
    target_id: str = "target_001",
    confidence: float = 0.9,
    payload: dict | None = None,
) -> GrowthAction:
    return GrowthAction(
        action_type=action_type,
        target_id=target_id,
        confidence=confidence,
        payload=payload or {},
        source=ActionSource.EVOLUTION_SIGNAL,
    )


# ═══════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════

@pytest.fixture
def engine():
    """创建默认 GrowthExecutionEngine (已注册默认执行器)."""
    e = GrowthExecutionEngine()
    e.register_default_executors()
    return e


@pytest.fixture
def empty_engine():
    """创建空 GrowthExecutionEngine (无执行器)."""
    return GrowthExecutionEngine()


@pytest.fixture
def creative_executor():
    return CreativeExecutor()


@pytest.fixture
def meta_ads_executor():
    return MetaAdsExecutor()


@pytest.fixture
def experiment_executor():
    return ExperimentExecutor()


@pytest.fixture
def evolution_executor():
    return EvolutionExecutor()


@pytest.fixture
def noop_executor():
    return NoOpExecutor()


# ═══════════════════════════════════════════════════════════
# 1. Model Tests (20)
# ═══════════════════════════════════════════════════════════

class TestExecutionStatus:
    """ExecutionStatus 枚举测试."""

    def test_all_statuses_present(self):
        expected = {"pending", "running", "success", "failed", "partial"}
        actual = {s.value for s in ExecutionStatus}
        assert actual == expected

    def test_status_values(self):
        assert ExecutionStatus.PENDING.value == "pending"
        assert ExecutionStatus.RUNNING.value == "running"
        assert ExecutionStatus.SUCCESS.value == "success"
        assert ExecutionStatus.FAILED.value == "failed"
        assert ExecutionStatus.PARTIAL.value == "partial"


class TestExecutionOutcome:
    """ExecutionOutcome 数据模型测试."""

    def test_default_creation(self):
        outcome = ExecutionOutcome()
        assert outcome.execution_id.startswith("exec_")
        assert outcome.status == ExecutionStatus.PENDING
        assert outcome.output == {}
        assert outcome.error == ""
        assert outcome.duration_ms == 0

    def test_full_creation(self):
        outcome = ExecutionOutcome(
            action_id="ga_001",
            action_type="promote_winner",
            status=ExecutionStatus.SUCCESS,
            executor="MetaAdsExecutor",
            output={"campaign_id": "camp_001", "new_budget": 200.0},
            duration_ms=150,
        )
        assert outcome.action_id == "ga_001"
        assert outcome.action_type == "promote_winner"
        assert outcome.status == ExecutionStatus.SUCCESS
        assert outcome.executor == "MetaAdsExecutor"
        assert outcome.output["campaign_id"] == "camp_001"
        assert outcome.duration_ms == 150

    def test_is_success_property(self):
        outcome = ExecutionOutcome(status=ExecutionStatus.SUCCESS)
        assert outcome.is_success is True
        assert outcome.is_failed is False

    def test_is_failed_property(self):
        outcome = ExecutionOutcome(status=ExecutionStatus.FAILED)
        assert outcome.is_failed is True
        assert outcome.is_success is False

    def test_pending_not_success(self):
        outcome = ExecutionOutcome(status=ExecutionStatus.PENDING)
        assert outcome.is_success is False
        assert outcome.is_failed is False

    def test_error_message(self):
        outcome = ExecutionOutcome(
            status=ExecutionStatus.FAILED,
            error="Connection timeout",
        )
        assert outcome.error == "Connection timeout"
        assert outcome.is_failed is True

    def test_to_dict(self):
        outcome = ExecutionOutcome(
            action_id="ga_001",
            action_type="promote_winner",
            status=ExecutionStatus.SUCCESS,
            executor="MetaAdsExecutor",
            output={"new_budget": 200.0},
            duration_ms=150,
        )
        d = outcome.to_dict()
        assert d["execution_id"].startswith("exec_")
        assert d["action_id"] == "ga_001"
        assert d["action_type"] == "promote_winner"
        assert d["status"] == "success"
        assert d["executor"] == "MetaAdsExecutor"
        assert d["output"]["new_budget"] == 200.0
        assert d["duration_ms"] == 150
        assert d["is_success"] is True
        assert d["is_failed"] is False

    def test_to_dict_with_error(self):
        outcome = ExecutionOutcome(
            status=ExecutionStatus.FAILED,
            error="API rate limit exceeded",
        )
        d = outcome.to_dict()
        assert d["status"] == "failed"
        assert d["error"] == "API rate limit exceeded"
        assert d["is_failed"] is True

    def test_metadata_field(self):
        outcome = ExecutionOutcome(metadata={"retry_count": 3})
        assert outcome.metadata["retry_count"] == 3

    def test_created_at_auto_set(self):
        outcome = ExecutionOutcome()
        assert outcome.created_at != ""

    def test_unique_execution_id(self):
        o1 = ExecutionOutcome()
        o2 = ExecutionOutcome()
        assert o1.execution_id != o2.execution_id

    def test_failed_outcome_has_error(self):
        outcome = ExecutionOutcome(
            status=ExecutionStatus.FAILED,
            error="Budget exceeds limit",
        )
        assert outcome.error != ""
        assert outcome.is_failed is True

    def test_success_outcome_no_error(self):
        outcome = ExecutionOutcome(status=ExecutionStatus.SUCCESS)
        assert outcome.error == ""

    def test_partial_status(self):
        outcome = ExecutionOutcome(status=ExecutionStatus.PARTIAL)
        assert outcome.is_success is False
        assert outcome.is_failed is False


# ═══════════════════════════════════════════════════════════
# 2. Registry Tests (20)
# ═══════════════════════════════════════════════════════════

class TestRegistry:
    """执行器注册中心测试."""

    def test_default_executors_registered(self, engine):
        assert len(engine.registry) == 11  # 11 个动作类型

    def test_all_action_types_have_executor(self, engine):
        for action_type in GrowthActionType:
            ex = engine.get_executor(action_type)
            assert ex is not None, f"No executor for {action_type.value}"

    def test_get_executor_for_promote_winner(self, engine):
        ex = engine.get_executor(GrowthActionType.PROMOTE_WINNER)
        assert isinstance(ex, MetaAdsExecutor)

    def test_get_executor_for_create_variants(self, engine):
        ex = engine.get_executor(GrowthActionType.CREATE_VARIANTS)
        assert isinstance(ex, CreativeExecutor)

    def test_get_executor_for_start_experiment(self, engine):
        ex = engine.get_executor(GrowthActionType.START_EXPERIMENT)
        assert isinstance(ex, ExperimentExecutor)

    def test_get_executor_for_diversify(self, engine):
        ex = engine.get_executor(GrowthActionType.DIVERSIFY_POPULATION)
        assert isinstance(ex, EvolutionExecutor)

    def test_get_executor_for_hold(self, engine):
        ex = engine.get_executor(GrowthActionType.HOLD)
        assert isinstance(ex, NoOpExecutor)

    def test_register_custom_executor(self, empty_engine):
        custom = CreativeExecutor()
        empty_engine.register_executor(GrowthActionType.CREATE_CREATIVE, custom)
        assert empty_engine.get_executor(GrowthActionType.CREATE_CREATIVE) is custom

    def test_register_overwrites_existing(self, engine):
        old = engine.get_executor(GrowthActionType.PROMOTE_WINNER)
        new = MetaAdsExecutor()
        engine.register_executor(GrowthActionType.PROMOTE_WINNER, new)
        assert engine.get_executor(GrowthActionType.PROMOTE_WINNER) is new
        assert engine.get_executor(GrowthActionType.PROMOTE_WINNER) is not old

    def test_unregister_executor(self, engine):
        engine.unregister_executor(GrowthActionType.PROMOTE_WINNER)
        assert engine.get_executor(GrowthActionType.PROMOTE_WINNER) is None

    def test_unregister_nonexistent_no_error(self, empty_engine):
        empty_engine.unregister_executor(GrowthActionType.PROMOTE_WINNER)

    def test_get_executor_nonexistent(self, empty_engine):
        assert empty_engine.get_executor(GrowthActionType.PROMOTE_WINNER) is None

    def test_register_default_executors_idempotent(self, engine):
        count_before = len(engine.registry)
        engine.register_default_executors()
        # 注册可能会覆盖已存在的，但不会增加数量
        engine.register_default_executors()
        assert len(engine.registry) == count_before

    def test_creative_actions_share_executor(self, engine):
        ex1 = engine.get_executor(GrowthActionType.CREATE_CREATIVE)
        ex2 = engine.get_executor(GrowthActionType.MUTATE_CREATIVE)
        ex3 = engine.get_executor(GrowthActionType.CREATE_VARIANTS)
        assert ex1 is ex2 is ex3

    def test_meta_actions_share_executor(self, engine):
        ex1 = engine.get_executor(GrowthActionType.PROMOTE_WINNER)
        ex2 = engine.get_executor(GrowthActionType.SCALE_CAMPAIGN)
        ex3 = engine.get_executor(GrowthActionType.REDUCE_BUDGET)
        ex4 = engine.get_executor(GrowthActionType.PAUSE_CAMPAIGN)
        assert ex1 is ex2 is ex3 is ex4

    def test_experiment_actions_share_executor(self, engine):
        ex1 = engine.get_executor(GrowthActionType.START_EXPERIMENT)
        ex2 = engine.get_executor(GrowthActionType.END_EXPERIMENT)
        assert ex1 is ex2

    def test_executor_stats_initial(self, empty_engine):
        ex = CreativeExecutor()
        s = ex.stats()
        assert s["total"] == 0
        assert s["success"] == 0
        assert s["failure"] == 0
        assert s["success_rate"] == 0.0

    def test_executor_stats_after_execution(self, creative_executor):
        action = _make_action(GrowthActionType.CREATE_VARIANTS)
        creative_executor.execute(action)
        s = creative_executor.stats()
        assert s["total"] == 1
        assert s["success"] == 1

    def test_executor_name(self, creative_executor, meta_ads_executor):
        assert creative_executor.name == "CreativeExecutor"
        assert meta_ads_executor.name == "MetaAdsExecutor"

    def test_registry_property_returns_copy(self, engine):
        reg = engine.registry
        assert len(reg) == 11


# ═══════════════════════════════════════════════════════════
# 3. Creative Executor Tests (25)
# ═══════════════════════════════════════════════════════════

class TestCreativeExecutor:
    """CreativeExecutor 测试."""

    def test_execute_create_creative(self, creative_executor):
        action = _make_action(GrowthActionType.CREATE_CREATIVE, target_id="genome_base")
        outcome = creative_executor.execute(action)
        assert outcome.is_success is True
        assert len(outcome.output["generated_genomes"]) == 1
        assert outcome.output["generated_genomes"][0].startswith("genome_new_")

    def test_execute_mutate_creative(self, creative_executor):
        action = _make_action(GrowthActionType.MUTATE_CREATIVE, target_id="genome_base")
        outcome = creative_executor.execute(action)
        assert outcome.is_success is True
        assert len(outcome.output["generated_genomes"]) == 1
        assert "genome_base_mut_" in outcome.output["generated_genomes"][0]

    def test_execute_create_variants(self, creative_executor):
        action = _make_action(
            GrowthActionType.CREATE_VARIANTS,
            target_id="genome_001",
            payload={"variant_count": 5},
        )
        outcome = creative_executor.execute(action)
        assert outcome.is_success is True
        assert len(outcome.output["generated_genomes"]) == 5
        assert outcome.output["count"] == 5

    def test_create_variants_default_count(self, creative_executor):
        action = _make_action(GrowthActionType.CREATE_VARIANTS)
        outcome = creative_executor.execute(action)
        assert outcome.output["count"] == 3

    def test_create_variants_names(self, creative_executor):
        action = _make_action(GrowthActionType.CREATE_VARIANTS, target_id="genome_001")
        outcome = creative_executor.execute(action)
        for i, gid in enumerate(outcome.output["generated_genomes"]):
            assert gid == f"genome_001_v{i+1}"

    def test_execute_unsupported_action(self, creative_executor):
        action = _make_action(GrowthActionType.PROMOTE_WINNER)
        outcome = creative_executor.execute(action)
        assert outcome.is_failed is True
        assert "Unsupported" in outcome.error

    def test_generated_genomes_tracked(self, creative_executor):
        action = _make_action(GrowthActionType.CREATE_VARIANTS, target_id="g001")
        creative_executor.execute(action)
        creative_executor.execute(action)
        assert len(creative_executor.generated_genomes) == 6

    def test_validate_supported_action(self, creative_executor):
        action = _make_action(GrowthActionType.CREATE_VARIANTS)
        assert creative_executor.validate(action) is True

    def test_validate_unsupported_action(self, creative_executor):
        action = _make_action(GrowthActionType.PROMOTE_WINNER)
        assert creative_executor.validate(action) is False

    def test_output_contains_source(self, creative_executor):
        action = _make_action(GrowthActionType.CREATE_VARIANTS, target_id="genome_source")
        outcome = creative_executor.execute(action)
        assert outcome.output["source"] == "genome_source"

    def test_output_contains_gene_category(self, creative_executor):
        action = _make_action(
            GrowthActionType.CREATE_VARIANTS,
            payload={"gene_category": "hook", "variant_count": 2},
        )
        outcome = creative_executor.execute(action)
        assert outcome.output["gene_category"] == "hook"

    def test_output_contains_exploration_direction(self, creative_executor):
        action = _make_action(
            GrowthActionType.CREATE_VARIANTS,
            payload={"exploration_direction": "rescue"},
        )
        outcome = creative_executor.execute(action)
        assert outcome.output["exploration_direction"] == "rescue"

    def test_duration_ms_recorded(self, creative_executor):
        action = _make_action(GrowthActionType.CREATE_VARIANTS)
        outcome = creative_executor.execute(action)
        assert outcome.duration_ms >= 0

    def test_executor_name_in_outcome(self, creative_executor):
        action = _make_action(GrowthActionType.CREATE_VARIANTS)
        outcome = creative_executor.execute(action)
        assert outcome.executor == "CreativeExecutor"

    def test_action_id_in_outcome(self, creative_executor):
        action = _make_action(GrowthActionType.CREATE_VARIANTS)
        outcome = creative_executor.execute(action)
        assert outcome.action_id == action.action_id

    def test_create_creative_no_target(self, creative_executor):
        action = _make_action(GrowthActionType.CREATE_CREATIVE, target_id="")
        outcome = creative_executor.execute(action)
        assert outcome.is_success is True
        assert len(outcome.output["generated_genomes"]) == 1

    def test_mutate_creative_no_target(self, creative_executor):
        action = _make_action(GrowthActionType.MUTATE_CREATIVE, target_id="")
        outcome = creative_executor.execute(action)
        assert outcome.is_success is True
        assert "base_genome_mut_" in outcome.output["generated_genomes"][0]

    def test_create_variants_no_target(self, creative_executor):
        action = _make_action(GrowthActionType.CREATE_VARIANTS, target_id="")
        outcome = creative_executor.execute(action)
        assert outcome.is_success is True
        assert outcome.output["source"] == "base_genome"

    def test_create_variants_large_count(self, creative_executor):
        action = _make_action(
            GrowthActionType.CREATE_VARIANTS,
            payload={"variant_count": 100},
        )
        outcome = creative_executor.execute(action)
        assert outcome.output["count"] == 100

    def test_create_variants_single(self, creative_executor):
        action = _make_action(
            GrowthActionType.CREATE_VARIANTS,
            payload={"variant_count": 1},
        )
        outcome = creative_executor.execute(action)
        assert outcome.output["count"] == 1

    def test_stats_after_multiple_executions(self, creative_executor):
        for _ in range(5):
            action = _make_action(GrowthActionType.CREATE_VARIANTS)
            creative_executor.execute(action)
        s = creative_executor.stats()
        assert s["total"] == 5
        assert s["success"] == 5

    def test_stats_after_mixed_executions(self, creative_executor):
        creative_executor.execute(_make_action(GrowthActionType.CREATE_VARIANTS))
        creative_executor.execute(_make_action(GrowthActionType.PROMOTE_WINNER))
        s = creative_executor.stats()
        assert s["total"] == 2
        assert s["success"] == 1
        assert s["failure"] == 1

    def test_execution_id_unique_per_call(self, creative_executor):
        o1 = creative_executor.execute(_make_action(GrowthActionType.CREATE_VARIANTS))
        o2 = creative_executor.execute(_make_action(GrowthActionType.CREATE_VARIANTS))
        assert o1.execution_id != o2.execution_id

    def test_create_creative_output_format(self, creative_executor):
        action = _make_action(GrowthActionType.CREATE_CREATIVE, target_id="g001")
        outcome = creative_executor.execute(action)
        assert "generated_genomes" in outcome.output
        assert "count" in outcome.output
        assert outcome.output["count"] == 1


# ═══════════════════════════════════════════════════════════
# 4. Meta Ads Executor Tests (25)
# ═══════════════════════════════════════════════════════════

class TestMetaAdsExecutor:
    """MetaAdsExecutor 测试."""

    def test_execute_promote_winner(self, meta_ads_executor):
        action = _make_action(
            GrowthActionType.PROMOTE_WINNER,
            target_id="camp_001",
            payload={"budget_multiplier": 2.0, "scale_reason": "High ROAS"},
        )
        outcome = meta_ads_executor.execute(action)
        assert outcome.is_success is True
        assert outcome.output["action"] == "budget_increased"
        assert outcome.output["new_budget"] == 200.0

    def test_execute_scale_campaign(self, meta_ads_executor):
        action = _make_action(
            GrowthActionType.SCALE_CAMPAIGN,
            target_id="camp_002",
            payload={"budget_multiplier": 1.5},
        )
        outcome = meta_ads_executor.execute(action)
        assert outcome.is_success is True
        assert outcome.output["action"] == "scaled"
        assert outcome.output["new_budget"] == 150.0

    def test_execute_reduce_budget(self, meta_ads_executor):
        action = _make_action(
            GrowthActionType.REDUCE_BUDGET,
            target_id="camp_003",
            payload={"budget_multiplier": 0.5, "reduce_reason": "Low ROAS"},
        )
        outcome = meta_ads_executor.execute(action)
        assert outcome.is_success is True
        assert outcome.output["action"] == "budget_reduced"
        assert outcome.output["new_budget"] == 50.0

    def test_execute_pause_campaign(self, meta_ads_executor):
        action = _make_action(
            GrowthActionType.PAUSE_CAMPAIGN,
            target_id="camp_004",
            payload={"reason": "High fatigue", "auto_resume_days": 7},
        )
        outcome = meta_ads_executor.execute(action)
        assert outcome.is_success is True
        assert outcome.output["action"] == "paused"
        assert outcome.output["auto_resume_days"] == 7

    def test_campaign_state_after_promote(self, meta_ads_executor):
        action = _make_action(
            GrowthActionType.PROMOTE_WINNER,
            target_id="camp_001",
            payload={"budget_multiplier": 2.0},
        )
        meta_ads_executor.execute(action)
        camp = meta_ads_executor.get_campaign("camp_001")
        assert camp is not None
        assert camp["status"] == "active"
        assert camp["budget"] == 200.0

    def test_campaign_state_after_pause(self, meta_ads_executor):
        action = _make_action(
            GrowthActionType.PAUSE_CAMPAIGN,
            target_id="camp_001",
            payload={"reason": "Pause test"},
        )
        meta_ads_executor.execute(action)
        camp = meta_ads_executor.get_campaign("camp_001")
        assert camp["status"] == "paused"
        assert camp["paused"] is True

    def test_campaign_state_after_reduce(self, meta_ads_executor):
        action = _make_action(
            GrowthActionType.REDUCE_BUDGET,
            target_id="camp_001",
            payload={"budget_multiplier": 0.3},
        )
        meta_ads_executor.execute(action)
        camp = meta_ads_executor.get_campaign("camp_001")
        assert camp["budget"] == 30.0
        assert camp["reduced"] is True

    def test_campaign_not_found(self, meta_ads_executor):
        assert meta_ads_executor.get_campaign("nonexistent") is None

    def test_execute_unsupported_action(self, meta_ads_executor):
        action = _make_action(GrowthActionType.CREATE_VARIANTS)
        outcome = meta_ads_executor.execute(action)
        assert outcome.is_failed is True

    def test_validate_missing_target(self, meta_ads_executor):
        action = _make_action(GrowthActionType.PROMOTE_WINNER, target_id="")
        assert meta_ads_executor.validate(action) is False

    def test_validate_has_target(self, meta_ads_executor):
        action = _make_action(GrowthActionType.PROMOTE_WINNER, target_id="camp_001")
        assert meta_ads_executor.validate(action) is True

    def test_validate_unsupported_action(self, meta_ads_executor):
        action = _make_action(GrowthActionType.CREATE_VARIANTS)
        assert meta_ads_executor.validate(action) is False

    def test_campaigns_property(self, meta_ads_executor):
        action = _make_action(
            GrowthActionType.PROMOTE_WINNER,
            target_id="camp_a",
            payload={"budget_multiplier": 2.0},
        )
        meta_ads_executor.execute(action)
        camps = meta_ads_executor.campaigns
        assert "camp_a" in camps
        assert camps["camp_a"]["budget"] == 200.0

    def test_budget_increase_chain(self, meta_ads_executor):
        action = _make_action(
            GrowthActionType.PROMOTE_WINNER,
            target_id="camp_chain",
            payload={"budget_multiplier": 2.0},
        )
        meta_ads_executor.execute(action)  # 100 → 200
        meta_ads_executor.execute(action)  # 200 → 400
        camp = meta_ads_executor.get_campaign("camp_chain")
        assert camp["budget"] == 400.0

    def test_budget_reduce_chain(self, meta_ads_executor):
        action = _make_action(
            GrowthActionType.REDUCE_BUDGET,
            target_id="camp_chain2",
            payload={"budget_multiplier": 0.5},
        )
        meta_ads_executor.execute(action)  # 100 → 50
        meta_ads_executor.execute(action)  # 50 → 25
        camp = meta_ads_executor.get_campaign("camp_chain2")
        assert camp["budget"] == 25.0

    def test_promote_winner_budget_calculation(self, meta_ads_executor):
        action = _make_action(
            GrowthActionType.PROMOTE_WINNER,
            target_id="camp_001",
            payload={"budget_multiplier": 3.0},
        )
        outcome = meta_ads_executor.execute(action)
        assert outcome.output["new_budget"] == 300.0
        assert outcome.output["previous_budget"] == 100.0

    def test_scale_campaign_output(self, meta_ads_executor):
        action = _make_action(
            GrowthActionType.SCALE_CAMPAIGN,
            target_id="camp_001",
            payload={"budget_multiplier": 1.8},
        )
        outcome = meta_ads_executor.execute(action)
        assert outcome.output["campaign_id"] == "camp_001"
        assert outcome.output["new_budget"] == 180.0

    def test_pause_campaign_auto_resume(self, meta_ads_executor):
        action = _make_action(
            GrowthActionType.PAUSE_CAMPAIGN,
            target_id="camp_001",
            payload={"auto_resume_days": 14},
        )
        outcome = meta_ads_executor.execute(action)
        assert outcome.output["auto_resume_days"] == 14

    def test_duration_ms_recorded(self, meta_ads_executor):
        action = _make_action(
            GrowthActionType.PROMOTE_WINNER,
            target_id="camp_001",
        )
        outcome = meta_ads_executor.execute(action)
        assert outcome.duration_ms >= 0

    def test_action_id_in_outcome(self, meta_ads_executor):
        action = _make_action(GrowthActionType.PROMOTE_WINNER, target_id="camp_001")
        outcome = meta_ads_executor.execute(action)
        assert outcome.action_id == action.action_id

    def test_executor_name_in_outcome(self, meta_ads_executor):
        action = _make_action(GrowthActionType.PROMOTE_WINNER, target_id="camp_001")
        outcome = meta_ads_executor.execute(action)
        assert outcome.executor == "MetaAdsExecutor"

    def test_stats_after_multiple_executions(self, meta_ads_executor):
        for _ in range(3):
            meta_ads_executor.execute(
                _make_action(GrowthActionType.PROMOTE_WINNER, target_id="camp_001")
            )
        s = meta_ads_executor.stats()
        assert s["total"] == 3
        assert s["success"] == 3

    def test_default_budget_for_new_campaign(self, meta_ads_executor):
        action = _make_action(
            GrowthActionType.PROMOTE_WINNER,
            target_id="camp_new",
            payload={"budget_multiplier": 1.0},
        )
        outcome = meta_ads_executor.execute(action)
        assert outcome.output["previous_budget"] == 100.0  # default

    def test_reduce_budget_no_multiplier(self, meta_ads_executor):
        action = _make_action(GrowthActionType.REDUCE_BUDGET, target_id="camp_001")
        outcome = meta_ads_executor.execute(action)
        assert outcome.output["new_budget"] == 100.0  # default multiplier 1.0


# ═══════════════════════════════════════════════════════════
# 5. Experiment Executor Tests (15)
# ═══════════════════════════════════════════════════════════

class TestExperimentExecutor:
    """ExperimentExecutor 测试."""

    def test_execute_start_experiment(self, experiment_executor):
        action = _make_action(
            GrowthActionType.START_EXPERIMENT,
            target_id="exp_001",
            payload={
                "experiment_name": "Hook Test",
                "hypothesis": "Rescue hook improves CTR",
                "duration_days": 7,
                "budget": 500.0,
            },
        )
        outcome = experiment_executor.execute(action)
        assert outcome.is_success is True
        assert outcome.output["action"] == "started"
        assert outcome.output["experiment_id"] == "exp_001"

    def test_execute_end_experiment(self, experiment_executor):
        action = _make_action(
            GrowthActionType.START_EXPERIMENT,
            target_id="exp_001",
        )
        experiment_executor.execute(action)
        action_end = _make_action(
            GrowthActionType.END_EXPERIMENT,
            target_id="exp_001",
        )
        outcome = experiment_executor.execute(action_end)
        assert outcome.is_success is True
        assert outcome.output["action"] == "ended"

    def test_end_experiment_changes_status(self, experiment_executor):
        experiment_executor.execute(
            _make_action(GrowthActionType.START_EXPERIMENT, target_id="exp_001")
        )
        experiment_executor.execute(
            _make_action(GrowthActionType.END_EXPERIMENT, target_id="exp_001")
        )
        exp = experiment_executor.get_experiment("exp_001")
        assert exp["status"] == "completed"

    def test_experiment_state_after_start(self, experiment_executor):
        action = _make_action(
            GrowthActionType.START_EXPERIMENT,
            target_id="exp_001",
            payload={"experiment_name": "Test", "duration_days": 14},
        )
        experiment_executor.execute(action)
        exp = experiment_executor.get_experiment("exp_001")
        assert exp["status"] == "running"
        assert exp["name"] == "Test"
        assert exp["duration_days"] == 14

    def test_experiment_not_found(self, experiment_executor):
        assert experiment_executor.get_experiment("nonexistent") is None

    def test_execute_unsupported_action(self, experiment_executor):
        action = _make_action(GrowthActionType.PROMOTE_WINNER)
        outcome = experiment_executor.execute(action)
        assert outcome.is_failed is True

    def test_start_experiment_no_target(self, experiment_executor):
        action = _make_action(GrowthActionType.START_EXPERIMENT, target_id="")
        outcome = experiment_executor.execute(action)
        assert outcome.is_success is True
        assert outcome.output["experiment_id"].startswith("exp_")

    def test_end_experiment_no_target(self, experiment_executor):
        action = _make_action(GrowthActionType.END_EXPERIMENT, target_id="")
        outcome = experiment_executor.execute(action)
        assert outcome.is_success is True

    def test_experiments_property(self, experiment_executor):
        experiment_executor.execute(
            _make_action(GrowthActionType.START_EXPERIMENT, target_id="exp_a")
        )
        experiment_executor.execute(
            _make_action(GrowthActionType.START_EXPERIMENT, target_id="exp_b")
        )
        exps = experiment_executor.experiments
        assert "exp_a" in exps
        assert "exp_b" in exps

    def test_start_experiment_budget_default(self, experiment_executor):
        action = _make_action(GrowthActionType.START_EXPERIMENT, target_id="exp_001")
        experiment_executor.execute(action)
        exp = experiment_executor.get_experiment("exp_001")
        assert exp["budget"] == 100.0

    def test_validate_supported_action(self, experiment_executor):
        assert experiment_executor.validate(
            _make_action(GrowthActionType.START_EXPERIMENT)
        ) is True

    def test_validate_unsupported_action(self, experiment_executor):
        assert experiment_executor.validate(
            _make_action(GrowthActionType.PROMOTE_WINNER)
        ) is False

    def test_end_nonexistent_experiment(self, experiment_executor):
        action = _make_action(GrowthActionType.END_EXPERIMENT, target_id="no_such_exp")
        outcome = experiment_executor.execute(action)
        assert outcome.is_success is True
        exp = experiment_executor.get_experiment("no_such_exp")
        assert exp["status"] == "completed"

    def test_stats_after_executions(self, experiment_executor):
        experiment_executor.execute(
            _make_action(GrowthActionType.START_EXPERIMENT, target_id="exp_001")
        )
        experiment_executor.execute(
            _make_action(GrowthActionType.END_EXPERIMENT, target_id="exp_001")
        )
        s = experiment_executor.stats()
        assert s["total"] == 2
        assert s["success"] == 2

    def test_duration_ms_recorded(self, experiment_executor):
        action = _make_action(GrowthActionType.START_EXPERIMENT)
        outcome = experiment_executor.execute(action)
        assert outcome.duration_ms >= 0


# ═══════════════════════════════════════════════════════════
# 6. Evolution / NoOp Executor Tests (10)
# ═══════════════════════════════════════════════════════════

class TestEvolutionExecutor:
    """EvolutionExecutor 测试."""

    def test_execute_diversify_population(self, evolution_executor):
        action = _make_action(
            GrowthActionType.DIVERSIFY_POPULATION,
            target_id="pop_001",
            payload={"count": 5, "diversity_target": "hook"},
        )
        outcome = evolution_executor.execute(action)
        assert outcome.is_success is True
        assert outcome.output["action"] == "diversified"
        assert outcome.output["count"] == 5
        assert len(outcome.output["generated_genomes"]) == 5

    def test_diversify_default_count(self, evolution_executor):
        action = _make_action(GrowthActionType.DIVERSIFY_POPULATION)
        outcome = evolution_executor.execute(action)
        assert outcome.output["count"] == 5

    def test_population_state_after_diversify(self, evolution_executor):
        action = _make_action(
            GrowthActionType.DIVERSIFY_POPULATION,
            target_id="pop_001",
            payload={"count": 3},
        )
        evolution_executor.execute(action)
        pop = evolution_executor.get_population("pop_001")
        assert pop is not None
        assert pop["count"] == 3
        assert len(pop["genome_ids"]) == 3

    def test_population_not_found(self, evolution_executor):
        assert evolution_executor.get_population("nonexistent") is None

    def test_execute_unsupported_action(self, evolution_executor):
        action = _make_action(GrowthActionType.PROMOTE_WINNER)
        outcome = evolution_executor.execute(action)
        assert outcome.is_failed is True

    def test_validate_supported(self, evolution_executor):
        assert evolution_executor.validate(
            _make_action(GrowthActionType.DIVERSIFY_POPULATION)
        ) is True

    def test_validate_unsupported(self, evolution_executor):
        assert evolution_executor.validate(
            _make_action(GrowthActionType.PROMOTE_WINNER)
        ) is False

    def test_populations_property(self, evolution_executor):
        evolution_executor.execute(
            _make_action(GrowthActionType.DIVERSIFY_POPULATION, target_id="pop_a")
        )
        pops = evolution_executor.populations
        assert "pop_a" in pops


class TestNoOpExecutor:
    """NoOpExecutor 测试."""

    def test_execute_hold(self, noop_executor):
        action = _make_action(GrowthActionType.HOLD)
        outcome = noop_executor.execute(action)
        assert outcome.is_success is True
        assert outcome.output["action"] == "hold"

    def test_validate_always_true(self, noop_executor):
        assert noop_executor.validate(_make_action(GrowthActionType.HOLD)) is True
        assert noop_executor.validate(_make_action(GrowthActionType.PROMOTE_WINNER)) is True


# ═══════════════════════════════════════════════════════════
# 7. Engine Execution Tests (15)
# ═══════════════════════════════════════════════════════════

class TestEngineExecution:
    """GrowthExecutionEngine 核心执行测试."""

    def test_execute_promote_winner(self, engine):
        action = _make_action(
            GrowthActionType.PROMOTE_WINNER,
            target_id="camp_001",
            payload={"budget_multiplier": 2.0},
        )
        outcome = engine.execute(action)
        assert outcome.is_success is True
        assert outcome.executor == "MetaAdsExecutor"

    def test_execute_create_variants(self, engine):
        action = _make_action(
            GrowthActionType.CREATE_VARIANTS,
            target_id="genome_001",
            payload={"variant_count": 3},
        )
        outcome = engine.execute(action)
        assert outcome.is_success is True
        assert outcome.output["count"] == 3

    def test_execute_start_experiment(self, engine):
        action = _make_action(
            GrowthActionType.START_EXPERIMENT,
            target_id="exp_001",
            payload={"experiment_name": "Test"},
        )
        outcome = engine.execute(action)
        assert outcome.is_success is True
        assert outcome.executor == "ExperimentExecutor"

    def test_execute_diversify_population(self, engine):
        action = _make_action(GrowthActionType.DIVERSIFY_POPULATION, target_id="pop_001")
        outcome = engine.execute(action)
        assert outcome.is_success is True
        assert outcome.executor == "EvolutionExecutor"

    def test_execute_hold(self, engine):
        action = _make_action(GrowthActionType.HOLD)
        outcome = engine.execute(action)
        assert outcome.is_success is True
        assert outcome.executor == "NoOpExecutor"

    def test_execute_no_registered_executor(self, empty_engine):
        action = _make_action(GrowthActionType.PROMOTE_WINNER)
        outcome = empty_engine.execute(action)
        assert outcome.is_failed is True
        assert "No executor registered" in outcome.error

    def test_execute_batch(self, engine):
        actions = [
            _make_action(GrowthActionType.PROMOTE_WINNER, target_id="camp_001"),
            _make_action(GrowthActionType.CREATE_VARIANTS, target_id="genome_001"),
            _make_action(GrowthActionType.START_EXPERIMENT, target_id="exp_001"),
        ]
        outcomes = engine.execute_batch(actions)
        assert len(outcomes) == 3
        assert all(o.is_success for o in outcomes)

    def test_execute_batch_respects_max_concurrent(self, engine):
        actions = [_make_action(GrowthActionType.PROMOTE_WINNER, target_id=f"camp_{i}") for i in range(20)]
        outcomes = engine.execute_batch(actions)
        assert len(outcomes) <= engine._max_concurrent

    def test_execute_batch_empty(self, engine):
        outcomes = engine.execute_batch([])
        assert outcomes == []

    def test_execution_history_tracked(self, engine):
        engine.execute(_make_action(GrowthActionType.PROMOTE_WINNER, target_id="camp_001"))
        engine.execute(_make_action(GrowthActionType.CREATE_VARIANTS))
        history = engine.get_execution_history()
        assert len(history) == 2

    def test_get_executions_by_status(self, engine):
        engine.execute(_make_action(GrowthActionType.PROMOTE_WINNER, target_id="camp_001"))
        success = engine.get_executions_by_status(ExecutionStatus.SUCCESS)
        assert len(success) == 1

    def test_get_executions_by_executor(self, engine):
        engine.execute(_make_action(GrowthActionType.PROMOTE_WINNER, target_id="camp_001"))
        engine.execute(_make_action(GrowthActionType.CREATE_VARIANTS))
        meta = engine.get_executions_by_executor("MetaAdsExecutor")
        creative = engine.get_executions_by_executor("CreativeExecutor")
        assert len(meta) == 1
        assert len(creative) == 1

    def test_reset_clears_all(self, engine):
        engine.execute(_make_action(GrowthActionType.PROMOTE_WINNER, target_id="camp_001"))
        engine.reset()
        assert len(engine.get_execution_history()) == 0
        assert len(engine.registry) == 0

    def test_create_with_factory(self):
        engine = create_growth_execution_engine()
        assert len(engine.registry) == 11
        outcome = engine.execute(
            _make_action(GrowthActionType.PROMOTE_WINNER, target_id="camp_001")
        )
        assert outcome.is_success is True

    def test_create_without_defaults(self):
        engine = create_growth_execution_engine(register_defaults=False)
        assert len(engine.registry) == 0


# ═══════════════════════════════════════════════════════════
# 8. Error Handling Tests (15)
# ═══════════════════════════════════════════════════════════

class TestErrorHandling:
    """错误处理测试."""

    def test_unsupported_action_returns_failed(self, engine):
        class FakeAction:
            action_type = "nonexistent"
            action_id = "ga_fake"
            action_type_value = "nonexistent"
        # 使用实际不存在的动作类型 — 通过 unregister 后执行
        engine.unregister_executor(GrowthActionType.PROMOTE_WINNER)
        action = _make_action(GrowthActionType.PROMOTE_WINNER)
        outcome = engine.execute(action)
        assert outcome.is_failed is True

    def test_creative_executor_unsupported(self, creative_executor):
        outcome = creative_executor.execute(
            _make_action(GrowthActionType.PAUSE_CAMPAIGN)
        )
        assert outcome.is_failed is True
        assert "Unsupported" in outcome.error

    def test_meta_ads_executor_unsupported(self, meta_ads_executor):
        outcome = meta_ads_executor.execute(
            _make_action(GrowthActionType.CREATE_VARIANTS)
        )
        assert outcome.is_failed is True

    def test_experiment_executor_unsupported(self, experiment_executor):
        outcome = experiment_executor.execute(
            _make_action(GrowthActionType.PROMOTE_WINNER)
        )
        assert outcome.is_failed is True

    def test_evolution_executor_unsupported(self, evolution_executor):
        outcome = evolution_executor.execute(
            _make_action(GrowthActionType.PROMOTE_WINNER)
        )
        assert outcome.is_failed is True

    def test_meta_ads_missing_target(self, meta_ads_executor):
        action = _make_action(GrowthActionType.PROMOTE_WINNER, target_id="")
        assert meta_ads_executor.validate(action) is False

    def test_creative_accepts_missing_target(self, creative_executor):
        action = _make_action(GrowthActionType.CREATE_VARIANTS, target_id="")
        assert creative_executor.validate(action) is True

    def test_failed_execution_in_stats(self, engine):
        engine.unregister_executor(GrowthActionType.PROMOTE_WINNER)
        engine.execute(_make_action(GrowthActionType.PROMOTE_WINNER))
        stats = engine.stats()
        assert stats["failed"] >= 1

    def test_error_message_in_outcome(self, engine):
        engine.unregister_executor(GrowthActionType.PROMOTE_WINNER)
        outcome = engine.execute(_make_action(GrowthActionType.PROMOTE_WINNER))
        assert outcome.error != ""
        assert "No executor" in outcome.error

    def test_mixed_batch_with_failures(self, engine):
        engine.unregister_executor(GrowthActionType.PROMOTE_WINNER)
        outcomes = engine.execute_batch([
            _make_action(GrowthActionType.PROMOTE_WINNER),
            _make_action(GrowthActionType.CREATE_VARIANTS),
        ])
        successes = [o for o in outcomes if o.is_success]
        failures = [o for o in outcomes if o.is_failed]
        assert len(successes) == 1
        assert len(failures) == 1

    def test_stats_success_rate_with_failures(self, engine):
        engine.unregister_executor(GrowthActionType.PROMOTE_WINNER)
        engine.execute(_make_action(GrowthActionType.PROMOTE_WINNER))
        engine.execute(_make_action(GrowthActionType.CREATE_VARIANTS))
        s = engine.stats()
        assert s["success_rate"] == 0.5

    def test_stats_by_status(self, engine):
        engine.unregister_executor(GrowthActionType.PROMOTE_WINNER)
        engine.execute(_make_action(GrowthActionType.PROMOTE_WINNER))
        engine.execute(_make_action(GrowthActionType.CREATE_VARIANTS))
        s = engine.stats()
        assert "success" in s["by_status"]
        assert "failed" in s["by_status"]

    def test_stats_by_executor_detail(self, engine):
        engine.execute(_make_action(GrowthActionType.PROMOTE_WINNER, target_id="camp_001"))
        engine.execute(_make_action(GrowthActionType.PROMOTE_WINNER, target_id="camp_002"))
        s = engine.stats()
        assert "MetaAdsExecutor" in s["by_executor"]
        assert s["by_executor"]["MetaAdsExecutor"]["total"] == 2

    def test_executor_stats_in_engine_stats(self, engine):
        engine.execute(_make_action(GrowthActionType.PROMOTE_WINNER, target_id="camp_001"))
        s = engine.stats()
        assert "executor_stats" in s
        assert "MetaAdsExecutor" in s["executor_stats"]


# ═══════════════════════════════════════════════════════════
# 9. Regression E14.5/E14.6/E14.7.1 Tests (15)
# ═══════════════════════════════════════════════════════════

class TestRegressionE145E146E1471:
    """E14.5/E14.6/E14.7.1 集成回归测试."""

    def test_router_to_engine_flow(self, engine):
        """验证 Router → Engine 完整流程."""
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.feedback_controller import (
            EvolutionSignal,
            SignalAction,
        )
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.growth_action_router import (
            GrowthActionRouter,
        )
        router = GrowthActionRouter()
        signal = EvolutionSignal(
            action=SignalAction.AMPLIFY,
            gene_category="hook",
            target_value="genome_007",
            confidence=0.92,
            expected_impact="ROAS +15%",
        )
        route_result = router.route(signal, target_id="genome_007")
        action = route_result.action
        outcome = engine.execute(action)
        assert outcome.is_success is True
        assert outcome.action_type == "promote_winner"

    def test_suppress_to_reduce_budget_flow(self, engine):
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.feedback_controller import (
            EvolutionSignal,
            SignalAction,
        )
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.growth_action_router import (
            GrowthActionRouter,
        )
        router = GrowthActionRouter()
        signal = EvolutionSignal(
            action=SignalAction.SUPPRESS,
            gene_category="monetization",
            target_value="camp_003",
            confidence=0.85,
            expected_impact="ROAS -20%",
        )
        result = router.route(signal, target_id="camp_003")
        outcome = engine.execute(result.action)
        assert outcome.is_success is True
        assert outcome.executor == "MetaAdsExecutor"

    def test_explore_to_create_variants_flow(self, engine):
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.feedback_controller import (
            EvolutionSignal,
            SignalAction,
        )
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.growth_action_router import (
            GrowthActionRouter,
        )
        router = GrowthActionRouter()
        signal = EvolutionSignal(
            action=SignalAction.EXPLORE,
            gene_category="gameplay",
            target_value="genome_005",
            confidence=0.75,
            expected_impact="New direction",
        )
        result = router.route(signal, target_id="genome_005")
        outcome = engine.execute(result.action)
        assert outcome.is_success is True
        assert outcome.executor == "CreativeExecutor"

    def test_retest_to_start_experiment_flow(self, engine):
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.feedback_controller import (
            EvolutionSignal,
            SignalAction,
        )
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.growth_action_router import (
            GrowthActionRouter,
        )
        router = GrowthActionRouter()
        signal = EvolutionSignal(
            action=SignalAction.RETEST,
            gene_category="monetization",
            target_value="genome_005",
            confidence=0.7,
            expected_impact="Need more data",
        )
        result = router.route(signal, target_id="genome_005")
        outcome = engine.execute(result.action)
        assert outcome.is_success is True
        assert outcome.executor == "ExperimentExecutor"

    def test_maintain_to_hold_flow(self, engine):
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.feedback_controller import (
            EvolutionSignal,
            SignalAction,
        )
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.growth_action_router import (
            GrowthActionRouter,
        )
        router = GrowthActionRouter()
        signal = EvolutionSignal(
            action=SignalAction.MAINTAIN,
            confidence=0.55,
        )
        result = router.route(signal)
        outcome = engine.execute(result.action)
        assert outcome.is_success is True
        assert outcome.executor == "NoOpExecutor"

    def test_full_autonomous_loop(self, engine):
        """完整自主闭环: Signal → Router → Engine."""
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.feedback_controller import (
            EvolutionSignal,
            SignalAction,
        )
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.growth_action_router import (
            GrowthActionRouter,
        )
        router = GrowthActionRouter()
        signals = [
            EvolutionSignal(action=SignalAction.AMPLIFY, gene_category="hook",
                          target_value="genome_001", confidence=0.92, expected_impact="ROAS +15%"),
            EvolutionSignal(action=SignalAction.SUPPRESS, gene_category="monetization",
                          target_value="camp_003", confidence=0.85, expected_impact="ROAS -20%"),
            EvolutionSignal(action=SignalAction.EXPLORE, gene_category="gameplay",
                          target_value="genome_005", confidence=0.75, expected_impact="New direction"),
            EvolutionSignal(action=SignalAction.RETEST, gene_category="visual",
                          target_value="genome_008", confidence=0.7, expected_impact="Need data"),
            EvolutionSignal(action=SignalAction.MAINTAIN, confidence=0.55, expected_impact=""),
        ]
        results = router.route_batch(signals)
        actions = [r.action for r in results]
        outcomes = engine.execute_batch(actions)
        success_count = sum(1 for o in outcomes if o.is_success)
        assert success_count >= 4

    def test_engine_stats_after_loop(self, engine):
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.feedback_controller import (
            EvolutionSignal,
            SignalAction,
        )
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.growth_action_router import (
            GrowthActionRouter,
        )
        router = GrowthActionRouter()
        signal = EvolutionSignal(
            action=SignalAction.AMPLIFY,
            target_value="genome_001",
            confidence=0.92,
            expected_impact="ROAS +15%",
        )
        result = router.route(signal)
        engine.execute(result.action)
        s = engine.stats()
        assert s["total_executions"] == 1
        assert s["success"] == 1
        assert s["success_rate"] == 1.0

    def test_engine_registry_actions(self, engine):
        s = engine.stats()
        assert "registry_actions" in s
        assert "promote_winner" in s["registry_actions"]
        assert "create_variants" in s["registry_actions"]
        assert "start_experiment" in s["registry_actions"]
        assert "hold" in s["registry_actions"]

    def test_multiple_routes_to_engine(self, engine):
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.feedback_controller import (
            EvolutionSignal,
            SignalAction,
        )
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.growth_action_router import (
            GrowthActionRouter,
        )
        router = GrowthActionRouter()
        for i in range(5):
            signal = EvolutionSignal(
                action=SignalAction.AMPLIFY,
                target_value=f"genome_{i:03d}",
                confidence=0.9,
                expected_impact=f"ROAS +{10+i}%",
            )
            result = router.route(signal)
            outcome = engine.execute(result.action)
            assert outcome.is_success is True

    def test_engine_creative_followed_by_meta(self, engine):
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.feedback_controller import (
            EvolutionSignal,
            SignalAction,
        )
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.growth_action_router import (
            GrowthActionRouter,
        )
        router = GrowthActionRouter()
        # 先创建变体
        explore_signal = EvolutionSignal(
            action=SignalAction.EXPLORE,
            target_value="genome_001",
            confidence=0.8,
            expected_impact="Explore hook",
        )
        explore_result = router.route(explore_signal)
        creative_outcome = engine.execute(explore_result.action)
        assert creative_outcome.is_success is True
        assert creative_outcome.executor == "CreativeExecutor"

        # 再推广 winner
        amplify_signal = EvolutionSignal(
            action=SignalAction.AMPLIFY,
            target_value="genome_001",
            confidence=0.92,
            expected_impact="ROAS +15%",
        )
        amplify_result = router.route(amplify_signal)
        meta_outcome = engine.execute(amplify_result.action)
        assert meta_outcome.is_success is True
        assert meta_outcome.executor == "MetaAdsExecutor"

    def test_engine_opportunity_to_execution(self, engine):
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.feedback_controller import (
            EvolutionSignal,
            SignalAction,
        )
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.growth_action_router import (
            GrowthActionRouter,
        )
        router = GrowthActionRouter()
        signal = EvolutionSignal(
            action=SignalAction.AMPLIFY,
            target_value="genome_001",
            confidence=0.92,
            expected_impact="ROAS +15%",
        )
        result = router.route(signal)
        outcome = engine.execute(result.action)
        assert outcome.is_success is True
        assert outcome.output["action"] == "budget_increased"

    def test_engine_validation_preserved(self, engine):
        """验证 Router 的验证结果在 Engine 中保持一致."""
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.feedback_controller import (
            EvolutionSignal,
            SignalAction,
        )
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.growth_action_router import (
            GrowthActionRouter,
        )
        router = GrowthActionRouter()
        signal = EvolutionSignal(
            action=SignalAction.AMPLIFY,
            target_value="genome_001",
            confidence=0.92,
            expected_impact="ROAS +15%",
        )
        result = router.route(signal)
        assert result.validation_passed is True
        outcome = engine.execute(result.action)
        assert outcome.is_success is True

    def test_engine_execution_history_after_loop(self, engine):
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.feedback_controller import (
            EvolutionSignal,
            SignalAction,
        )
        from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent.evolution_brain.growth_action_router import (
            GrowthActionRouter,
        )
        router = GrowthActionRouter()
        for signal_action in SignalAction:
            signal = EvolutionSignal(
                action=signal_action,
                target_value="genome_001",
                confidence=0.8,
                expected_impact="Test",
            )
            result = router.route(signal)
            engine.execute(result.action)
        history = engine.get_execution_history()
        assert len(history) == 5

    def test_engine_total_executions_match(self, engine):
        engine.execute(_make_action(GrowthActionType.PROMOTE_WINNER, target_id="camp_001"))
        engine.execute(_make_action(GrowthActionType.CREATE_VARIANTS))
        engine.execute(_make_action(GrowthActionType.HOLD))
        s = engine.stats()
        assert s["total_executions"] == 3
        assert s["registered_executors"] == 11