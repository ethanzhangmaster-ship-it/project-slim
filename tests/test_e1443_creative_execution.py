"""E14.4.3 Creative Execution Agent — 集成测试.

验证 Creative Agent 的执行能力:
  - CreativeExecutor (E14.4.3.1) — 40 tests
  - GeneratorBridge (E14.4.3.2) — 40 tests
  - ExperimentManager (E14.4.3.3) — 40 tests
  - RolloutController (E14.4.3.4) — 40 tests
  - Full Execution Pipeline (E14.4.3) — 25 tests
  - CreativeAgent Integration — 20 tests
  - Regression (E14.4.1/E14.4.2/E14.3/E14.2/E14.1) — 15 tests

总计: 220 个测试用例
"""

from __future__ import annotations

import pytest

from market_ops.creative_vision_runtime.growth_runtime.agent.communication import (
    MessageBus,
    AgentRegistry,
    StandardMessageType,
    create_message_bus,
    create_agent_registry,
    create_ua_agent_identity as comm_ua_identity,
    create_creative_agent_identity as comm_creative_identity,
)

from market_ops.creative_vision_runtime.growth_runtime.agent.creative_agent import (
    # analyzer (E14.4.1)
    CreativeAnalyzer,
    CreativeMetrics,
    CreativeDiagnosis,
    CreativeDiagnosisType,
    CreativeDiagnosisSeverity,
    create_creative_analyzer,
    # dna_engine (E14.4.1)
    DNAEngine,
    CreativeDNAProfile,
    CreativeGene,
    HookType,
    VisualStyle,
    EmotionType,
    # memory (E14.4.1)
    CreativeMemory,
    CreativeActionType,
    # creative_agent
    CreativeAgent,
    CreativeAgentState,
    create_creative_agent,
    # opportunity (E14.4.2.1)
    CreativeOpportunityType,
    CreativeSignal,
    OpportunityPriority,
    # strategy (E14.4.2.2)
    CreativeStrategy,
    CreativeStrategyType,
    GeneMutation,
    GeneMutationAction,
    # planner (E14.4.2.3)
    CreativePlan,
    MutationConfig,
    ExperimentConfig,
    ExperimentType,
    PlanStatus,
    BatchPlan,
    # executor (E14.4.3.1)
    CreativeExecutor,
    CreativeExecutionAction,
    ExecutionActionType,
    ExecutionStatus,
    ExecutionParameters,
    ExecutionBatch,
    create_executor,
    # generator_bridge (E14.4.3.2)
    GeneratorBridge,
    CreativeVariant,
    GenerationResult,
    VariantStatus,
    GeneratorType,
    create_generator_bridge,
    # experiment (E14.4.3.3)
    ExperimentManager,
    CreativeExperiment,
    ExperimentStatus,
    ExperimentResult,
    VariantMetrics,
    VariantGroupType,
    ExperimentReport,
    create_experiment_manager,
    # rollout (E14.4.3.4)
    RolloutController,
    RolloutDecision,
    RolloutStrategy,
    RolloutStatus,
    RolloutTrigger,
    RolloutReport,
    create_rollout_controller,
)


# ═══════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════


@pytest.fixture
def executor():
    return create_executor()


@pytest.fixture
def bridge():
    return create_generator_bridge()


@pytest.fixture
def experiment_manager():
    return create_experiment_manager()


@pytest.fixture
def rollout_controller():
    return create_rollout_controller()


@pytest.fixture
def agent():
    return create_creative_agent()


@pytest.fixture
def sample_plan():
    return CreativePlan(
        creative_id="C102",
        strategy_type=CreativeStrategyType.REFRESH_HOOK,
        population_size=5,
        generation_count=1,
        priority=OpportunityPriority.HIGH,
        status=PlanStatus.READY,
        mutation_configs=[
            MutationConfig(
                gene_category="hook",
                mutation_action=GeneMutationAction.CHANGE,
                target_values=["rescue_hook", "challenge_hook"],
            ),
        ],
        experiment_config=ExperimentConfig(
            experiment_type=ExperimentType.A_B_TEST,
            max_budget=500.0,
            min_duration_days=3,
            success_criteria={"min_roas": 1.2, "min_ctr": 0.02},
        ),
    )


@pytest.fixture
def sample_strategy():
    return CreativeStrategy(
        strategy_type=CreativeStrategyType.REFRESH_HOOK,
        target_creative_id="C102",
        mutation_plan=[
            GeneMutation(
                gene_category="hook",
                action=GeneMutationAction.CHANGE,
                current_value="before_after",
                target_values=["rescue_hook", "challenge_hook"],
            ),
            GeneMutation(
                gene_category="visual",
                action=GeneMutationAction.KEEP,
                current_value="fantasy",
            ),
        ],
        priority=OpportunityPriority.HIGH,
        expected_impact="CTR 提升 15-25%",
    )


@pytest.fixture
def sample_dna():
    return CreativeDNAProfile(
        creative_id="C102",
        creative_name="Test Creative",
        genes={
            "hook": CreativeGene(category="hook", value=HookType.BEFORE_AFTER),
            "visual": CreativeGene(category="visual", value=VisualStyle.FANTASY),
            "emotion": CreativeGene(category="emotion", value=EmotionType.EXCITEMENT),
        },
    )


@pytest.fixture
def sample_scale_plan():
    return CreativePlan(
        creative_id="C201",
        strategy_type=CreativeStrategyType.SCALE_WINNER,
        population_size=3,
        generation_count=1,
        priority=OpportunityPriority.CRITICAL,
        status=PlanStatus.READY,
        experiment_config=ExperimentConfig(
            experiment_type=ExperimentType.SCALE_UP,
            max_budget=2000.0,
            min_duration_days=5,
        ),
    )


@pytest.fixture
def sample_explore_plan():
    return CreativePlan(
        creative_id="C301",
        strategy_type=CreativeStrategyType.EXPLORE_NEW_DNA,
        population_size=8,
        generation_count=2,
        priority=OpportunityPriority.MEDIUM,
        status=PlanStatus.READY,
        mutation_configs=[
            MutationConfig(
                gene_category="visual",
                mutation_action=GeneMutationAction.EXPLORE,
                target_values=["realistic", "cartoon", "anime"],
            ),
        ],
        experiment_config=ExperimentConfig(
            experiment_type=ExperimentType.EXPLORATION,
            max_budget=300.0,
            min_duration_days=4,
        ),
    )


@pytest.fixture
def winner_variant_metrics():
    return VariantMetrics(
        variant_id="V001",
        creative_id="C201_V1",
        group_type=VariantGroupType.VARIANT,
        roas=2.5,
        ctr=0.04,
        cvr=0.08,
        fatigue=0.15,
        spend=500.0,
        revenue=1250.0,
        installs=3000,
        payer_rate=0.12,
        ltv=8.5,
    )


@pytest.fixture
def fatigue_variant_metrics():
    return VariantMetrics(
        variant_id="V002",
        creative_id="C102_V1",
        group_type=VariantGroupType.VARIANT,
        roas=0.8,
        ctr=0.015,
        cvr=0.03,
        fatigue=0.65,
        spend=300.0,
        revenue=240.0,
        installs=800,
        payer_rate=0.05,
        ltv=4.0,
    )


# ═══════════════════════════════════════════════════════════════
# E14.4.3.1 Creative Executor — 40 tests
# ═══════════════════════════════════════════════════════════════


class TestCreativeExecutor:
    """CreativeExecutor 单元测试."""

    # ── create_action ────────────────────────────────────────

    def test_create_action_from_plan(self, executor, sample_plan):
        action = executor.create_action(sample_plan)
        assert action.action_id != ""
        assert action.plan_id == sample_plan.plan_id
        assert action.creative_id == "C102"
        assert action.action_type == ExecutionActionType.GENERATE_VARIANTS
        assert action.status == ExecutionStatus.PENDING

    def test_create_action_with_scale_winner(self, executor, sample_scale_plan):
        action = executor.create_action(sample_scale_plan)
        assert action.action_type == ExecutionActionType.SCALE_CREATIVE
        assert action.priority == OpportunityPriority.CRITICAL

    def test_create_action_with_explore(self, executor, sample_explore_plan):
        action = executor.create_action(sample_explore_plan)
        assert action.action_type == ExecutionActionType.MUTATE_DNA
        assert action.priority == OpportunityPriority.MEDIUM

    def test_create_action_parameters(self, executor, sample_plan):
        action = executor.create_action(sample_plan)
        assert action.parameters is not None
        assert action.parameters.generator == "e11_evolution"
        assert action.parameters.count == 5
        assert action.parameters.generation == 1

    def test_create_action_parameters_count_from_plan(self, executor, sample_explore_plan):
        action = executor.create_action(sample_explore_plan)
        assert action.parameters.count == 8
        assert action.parameters.generation == 2

    def test_create_action_strategy_id_set(self, executor, sample_plan):
        action = executor.create_action(sample_plan)
        assert action.strategy_id == sample_plan.strategy_id

    # ── create_actions_from_batch ──────────────────────────────

    def test_create_batch_from_plans(self, executor, sample_plan, sample_scale_plan):
        batch = executor.create_actions_from_batch([sample_plan, sample_scale_plan])
        assert batch.total_actions == 2
        assert batch.pending == 2
        assert len(batch.actions) == 2

    def test_create_batch_filters_non_ready(self, executor, sample_plan):
        sample_plan.status = PlanStatus.DRAFT
        batch = executor.create_actions_from_batch([sample_plan])
        assert batch.total_actions == 0

    def test_create_batch_sorts_by_priority(self, executor, sample_plan, sample_scale_plan):
        batch = executor.create_actions_from_batch([sample_plan, sample_scale_plan])
        # CRITICAL should come before HIGH
        assert batch.actions[0].priority == OpportunityPriority.CRITICAL

    def test_create_batch_empty_plans(self, executor):
        batch = executor.create_actions_from_batch([])
        assert batch.total_actions == 0
        assert batch.action_count == 0

    def test_create_batch_summary(self, executor, sample_plan, sample_scale_plan):
        batch = executor.create_actions_from_batch([sample_plan, sample_scale_plan])
        assert "2" in batch.summary

    # ── execute / complete / fail ─────────────────────────────

    def test_execute_pending_action(self, executor, sample_plan):
        action = executor.create_action(sample_plan)
        result = executor.execute(action)
        assert result is True
        assert action.status == ExecutionStatus.EXECUTING
        assert action.started_at != ""

    def test_execute_non_pending_fails(self, executor, sample_plan):
        action = executor.create_action(sample_plan)
        executor.execute(action)
        result = executor.execute(action)  # 重复执行
        assert result is False

    def test_complete_executing_action(self, executor, sample_plan):
        action = executor.create_action(sample_plan)
        executor.execute(action)
        result = executor.complete(action, {"variants": 5})
        assert result is True
        assert action.status == ExecutionStatus.COMPLETED
        assert action.result == {"variants": 5}
        assert action.completed_at != ""

    def test_complete_non_executing_fails(self, executor, sample_plan):
        action = executor.create_action(sample_plan)
        result = executor.complete(action)
        assert result is False

    def test_fail_executing_action(self, executor, sample_plan):
        action = executor.create_action(sample_plan)
        executor.execute(action)
        result = executor.fail(action, "E11 connection error")
        assert result is True
        assert action.status == ExecutionStatus.FAILED
        assert action.error == "E11 connection error"

    def test_fail_pending_action(self, executor, sample_plan):
        action = executor.create_action(sample_plan)
        result = executor.fail(action)
        assert result is True
        assert action.status == ExecutionStatus.FAILED

    def test_fail_completed_action(self, executor, sample_plan):
        action = executor.create_action(sample_plan)
        executor.execute(action)
        executor.complete(action)
        result = executor.fail(action)
        assert result is False

    # ── rollback / cancel ─────────────────────────────────────

    def test_rollback_completed_action(self, executor, sample_plan):
        action = executor.create_action(sample_plan)
        executor.execute(action)
        executor.complete(action)
        result = executor.rollback(action)
        assert result is True
        assert action.status == ExecutionStatus.ROLLED_BACK

    def test_rollback_non_completed_fails(self, executor, sample_plan):
        action = executor.create_action(sample_plan)
        result = executor.rollback(action)
        assert result is False

    def test_cancel_pending_action(self, executor, sample_plan):
        action = executor.create_action(sample_plan)
        result = executor.cancel(action)
        assert result is True
        assert action.status == ExecutionStatus.CANCELLED

    def test_cancel_terminal_action_fails(self, executor, sample_plan):
        action = executor.create_action(sample_plan)
        executor.execute(action)
        executor.complete(action)
        result = executor.cancel(action)
        assert result is False

    # ── 查询 ──────────────────────────────────────────────────

    def test_get_action_by_id(self, executor, sample_plan):
        action = executor.create_action(sample_plan)
        found = executor.get_action(action.action_id)
        assert found is not None
        assert found.action_id == action.action_id

    def test_get_action_not_found(self, executor):
        assert executor.get_action("nonexistent") is None

    def test_get_actions_by_plan(self, executor, sample_plan, sample_scale_plan):
        executor.create_action(sample_plan)
        executor.create_action(sample_scale_plan)
        actions = executor.get_actions_by_plan(sample_plan.plan_id)
        assert len(actions) == 1

    def test_get_actions_by_creative(self, executor, sample_plan):
        executor.create_action(sample_plan)
        actions = executor.get_actions_by_creative("C102")
        assert len(actions) == 1

    def test_get_pending_actions(self, executor, sample_plan, sample_scale_plan):
        executor.create_action(sample_plan)
        executor.create_action(sample_scale_plan)
        pending = executor.get_pending_actions()
        assert len(pending) == 2

    def test_get_executing_actions(self, executor, sample_plan):
        action = executor.create_action(sample_plan)
        executor.execute(action)
        executing = executor.get_executing_actions()
        assert len(executing) == 1

    def test_get_completed_actions(self, executor, sample_plan):
        action = executor.create_action(sample_plan)
        executor.execute(action)
        executor.complete(action)
        completed = executor.get_completed_actions()
        assert len(completed) == 1

    def test_get_failed_actions(self, executor, sample_plan):
        action = executor.create_action(sample_plan)
        executor.fail(action)
        failed = executor.get_failed_actions()
        assert len(failed) == 1

    def test_get_history(self, executor, sample_plan):
        executor.create_action(sample_plan)
        history = executor.get_history()
        assert len(history) == 1

    # ── 属性 ──────────────────────────────────────────────────

    def test_action_is_pending(self, executor, sample_plan):
        action = executor.create_action(sample_plan)
        assert action.is_pending is True

    def test_action_is_completed(self, executor, sample_plan):
        action = executor.create_action(sample_plan)
        executor.execute(action)
        executor.complete(action)
        assert action.is_completed is True

    def test_action_is_failed(self, executor, sample_plan):
        action = executor.create_action(sample_plan)
        executor.fail(action)
        assert action.is_failed is True

    def test_action_is_terminal_completed(self, executor, sample_plan):
        action = executor.create_action(sample_plan)
        executor.execute(action)
        executor.complete(action)
        assert action.is_terminal is True

    def test_action_is_terminal_failed(self, executor, sample_plan):
        action = executor.create_action(sample_plan)
        executor.fail(action)
        assert action.is_terminal is True

    def test_action_summary(self, executor, sample_plan):
        action = executor.create_action(sample_plan)
        assert "GENERATE_VARIANTS" in action.summary or "generate_variants" in action.summary

    # ── stats / reset ─────────────────────────────────────────

    def test_executor_stats(self, executor, sample_plan, sample_scale_plan):
        executor.create_action(sample_plan)
        executor.create_action(sample_scale_plan)
        stats = executor.stats()
        assert stats["total"] == 2
        assert stats["pending"] == 2

    def test_executor_stats_empty(self, executor):
        stats = executor.stats()
        assert stats["total"] == 0

    def test_executor_reset(self, executor, sample_plan):
        executor.create_action(sample_plan)
        executor.reset()
        assert executor.stats()["total"] == 0

    # ── to_dict ───────────────────────────────────────────────

    def test_action_to_dict(self, executor, sample_plan):
        action = executor.create_action(sample_plan)
        d = action.to_dict()
        assert d["action_type"] == ExecutionActionType.GENERATE_VARIANTS.value
        assert d["creative_id"] == "C102"

    def test_batch_to_dict(self, executor, sample_plan):
        batch = executor.create_actions_from_batch([sample_plan])
        d = batch.to_dict()
        assert d["total_actions"] == 1


# ═══════════════════════════════════════════════════════════════
# E14.4.3.2 Generator Bridge — 40 tests
# ═══════════════════════════════════════════════════════════════


class TestGeneratorBridge:
    """GeneratorBridge 单元测试."""

    # ── generate_variants ─────────────────────────────────────

    def test_generate_variants_mock(self, bridge, sample_plan, sample_strategy, sample_dna):
        result = bridge.generate_variants(sample_plan, sample_strategy, sample_dna)
        assert result.success is True
        assert result.total_generated == 5
        assert result.generator_type == GeneratorType.MOCK
        assert len(result.variants) == 5

    def test_generate_variants_plan_id(self, bridge, sample_plan, sample_strategy, sample_dna):
        result = bridge.generate_variants(sample_plan, sample_strategy, sample_dna)
        assert result.plan_id == sample_plan.plan_id

    def test_generate_variants_strategy_type(self, bridge, sample_plan, sample_strategy, sample_dna):
        result = bridge.generate_variants(sample_plan, sample_strategy, sample_dna)
        for v in result.variants:
            assert v.strategy_type == CreativeStrategyType.REFRESH_HOOK

    def test_generate_variants_parent_dna(self, bridge, sample_plan, sample_strategy, sample_dna):
        result = bridge.generate_variants(sample_plan, sample_strategy, sample_dna)
        for v in result.variants:
            assert v.parent_dna_id == sample_dna.dna_id

    def test_generate_variants_parent_creative(self, bridge, sample_plan, sample_strategy, sample_dna):
        result = bridge.generate_variants(sample_plan, sample_strategy, sample_dna)
        for v in result.variants:
            assert v.parent_creative_id == "C102"

    def test_generate_variants_generation(self, bridge, sample_plan, sample_strategy, sample_dna):
        result = bridge.generate_variants(sample_plan, sample_strategy, sample_dna)
        for v in result.variants:
            assert v.generation == 1

    def test_generate_variants_variant_status(self, bridge, sample_plan, sample_strategy, sample_dna):
        result = bridge.generate_variants(sample_plan, sample_strategy, sample_dna)
        for v in result.variants:
            assert v.status == VariantStatus.GENERATED

    def test_generate_variants_larger_population(self, bridge, sample_explore_plan, sample_strategy, sample_dna):
        result = bridge.generate_variants(sample_explore_plan, sample_strategy, sample_dna)
        assert result.total_generated == 8

    def test_generate_variants_without_dna(self, bridge, sample_plan, sample_strategy):
        result = bridge.generate_variants(sample_plan, sample_strategy)
        assert result.success is True
        assert result.total_generated == 5

    def test_generate_variants_unique_ids(self, bridge, sample_plan, sample_strategy, sample_dna):
        result = bridge.generate_variants(sample_plan, sample_strategy, sample_dna)
        ids = {v.variant_id for v in result.variants}
        assert len(ids) == 5  # 所有 ID 唯一

    # ── mutate_dna ────────────────────────────────────────────

    def test_mutate_dna(self, bridge, sample_strategy, sample_dna):
        variant = bridge.mutate_dna(
            sample_strategy, sample_dna,
            {"hook": "rescue_hook", "visual": "realistic"},
        )
        assert variant.parent_creative_id == sample_dna.creative_id
        assert variant.parent_dna_id == sample_dna.dna_id
        assert variant.strategy_type == sample_strategy.strategy_type
        assert "original" in variant.dna_delta
        assert "mutated" in variant.dna_delta

    def test_mutate_dna_delta_contents(self, bridge, sample_strategy, sample_dna):
        variant = bridge.mutate_dna(
            sample_strategy, sample_dna,
            {"hook": "rescue_hook"},
        )
        assert variant.dna_delta["mutated"] == {"hook": "rescue_hook"}
        assert variant.dna_delta["strategy"] == sample_strategy.strategy_type.value

    # ── clone_winner ──────────────────────────────────────────

    def test_clone_winner(self, bridge, sample_strategy, sample_dna):
        variant = bridge.clone_winner(sample_strategy, sample_dna, "C999")
        assert variant.parent_creative_id == "C999"
        assert variant.parent_dna_id == sample_dna.dna_id
        assert variant.strategy_type == CreativeStrategyType.COPY_WINNER_DNA
        assert variant.dna_delta["action"] == "clone_winner"

    def test_clone_winner_source_genes(self, bridge, sample_strategy, sample_dna):
        variant = bridge.clone_winner(sample_strategy, sample_dna, "C999")
        assert "source_genes" in variant.dna_delta
        assert "source_dna_id" in variant.dna_delta

    # ── DNA delta 构建 ────────────────────────────────────────

    def test_dna_delta_change_action(self, bridge, sample_plan, sample_strategy, sample_dna):
        result = bridge.generate_variants(sample_plan, sample_strategy, sample_dna)
        for v in result.variants:
            assert "hook" in v.dna_delta
            assert v.dna_delta["hook"]["action"] == "change"

    def test_dna_delta_keep_action(self, bridge, sample_plan, sample_strategy, sample_dna):
        result = bridge.generate_variants(sample_plan, sample_strategy, sample_dna)
        for v in result.variants:
            if "visual" in v.dna_delta:
                assert v.dna_delta["visual"]["action"] == "keep"

    def test_dna_delta_explore_action(self, bridge, sample_explore_plan, sample_strategy, sample_dna):
        explore_strategy = CreativeStrategy(
            strategy_type=CreativeStrategyType.EXPLORE_NEW_DNA,
            target_creative_id="C301",
            mutation_plan=[
                GeneMutation(
                    gene_category="visual",
                    action=GeneMutationAction.EXPLORE,
                    current_value="fantasy",
                    target_values=["realistic", "cartoon", "anime"],
                ),
            ],
            priority=OpportunityPriority.MEDIUM,
        )
        result = bridge.generate_variants(sample_explore_plan, explore_strategy, sample_dna)
        for v in result.variants:
            if "visual" in v.dna_delta:
                assert v.dna_delta["visual"]["action"] == "explore"

    # ── Variant to_dict ───────────────────────────────────────

    def test_variant_to_dict(self, bridge, sample_plan, sample_strategy, sample_dna):
        result = bridge.generate_variants(sample_plan, sample_strategy, sample_dna)
        d = result.variants[0].to_dict()
        assert "variant_id" in d
        assert "parent_creative_id" in d
        assert "strategy_type" in d

    def test_generation_result_to_dict(self, bridge, sample_plan, sample_strategy, sample_dna):
        result = bridge.generate_variants(sample_plan, sample_strategy, sample_dna)
        d = result.to_dict()
        assert d["total_generated"] == 5
        assert d["success"] is True

    # ── 查询 ──────────────────────────────────────────────────

    def test_get_variant_by_id(self, bridge, sample_plan, sample_strategy, sample_dna):
        result = bridge.generate_variants(sample_plan, sample_strategy, sample_dna)
        vid = result.variants[0].variant_id
        found = bridge.get_variant(vid)
        assert found is not None
        assert found.variant_id == vid

    def test_get_variant_not_found(self, bridge):
        assert bridge.get_variant("nonexistent") is None

    def test_get_variants_by_parent(self, bridge, sample_plan, sample_strategy, sample_dna):
        bridge.generate_variants(sample_plan, sample_strategy, sample_dna)
        variants = bridge.get_variants_by_parent("C102")
        assert len(variants) == 5

    def test_get_results(self, bridge, sample_plan, sample_strategy, sample_dna):
        bridge.generate_variants(sample_plan, sample_strategy, sample_dna)
        results = bridge.get_results()
        assert len(results) == 1

    def test_get_last_result(self, bridge, sample_plan, sample_strategy, sample_dna):
        bridge.generate_variants(sample_plan, sample_strategy, sample_dna)
        last = bridge.get_last_result()
        assert last is not None
        assert last.total_generated == 5

    # ── Variant properties ────────────────────────────────────

    def test_variant_count(self, bridge, sample_plan, sample_strategy, sample_dna):
        result = bridge.generate_variants(sample_plan, sample_strategy, sample_dna)
        assert result.variant_count == 5

    # ── stats / reset ─────────────────────────────────────────

    def test_bridge_stats(self, bridge, sample_plan, sample_strategy, sample_dna):
        bridge.generate_variants(sample_plan, sample_strategy, sample_dna)
        stats = bridge.stats()
        assert stats["total_variants"] == 5
        assert stats["total_results"] == 1
        assert stats["generator_type"] == "mock"

    def test_bridge_stats_empty(self, bridge):
        stats = bridge.stats()
        assert stats["total_variants"] == 0

    def test_bridge_reset(self, bridge, sample_plan, sample_strategy, sample_dna):
        bridge.generate_variants(sample_plan, sample_strategy, sample_dna)
        bridge.reset()
        assert bridge.stats()["total_variants"] == 0

    # ── GeneratorType ─────────────────────────────────────────

    def test_generator_type_enum(self):
        assert GeneratorType.E11_EVOLUTION.value == "e11_evolution"
        assert GeneratorType.LOVART.value == "lovart"
        assert GeneratorType.CLIP.value == "clip"
        assert GeneratorType.MOCK.value == "mock"

    def test_create_bridge_with_e11_type(self):
        bridge = create_generator_bridge(generator_type=GeneratorType.E11_EVOLUTION)
        assert bridge.stats()["generator_type"] == "e11_evolution"

    # ── VariantStatus ─────────────────────────────────────────

    def test_variant_status_enum(self):
        assert VariantStatus.GENERATED.value == "generated"
        assert VariantStatus.UPLOADED.value == "uploaded"
        assert VariantStatus.ACTIVE.value == "active"
        assert VariantStatus.WINNER.value == "winner"

    # ── 多策略生成 ────────────────────────────────────────────

    def test_multiple_strategies_generate(self, bridge, sample_plan, sample_strategy, sample_dna):
        result1 = bridge.generate_variants(sample_plan, sample_strategy, sample_dna)
        result2 = bridge.generate_variants(sample_plan, sample_strategy, sample_dna)
        assert len(bridge.get_results()) == 2
        assert bridge.stats()["total_variants"] == 10

    # ── 无 mutation plan 的生成 ────────────────────────────────

    def test_generate_without_mutation_plan(self, bridge, sample_plan, sample_dna):
        no_mutation_strategy = CreativeStrategy(
            strategy_type=CreativeStrategyType.REFRESH_HOOK,
            target_creative_id="C102",
            mutation_plan=[],
            priority=OpportunityPriority.HIGH,
        )
        result = bridge.generate_variants(sample_plan, no_mutation_strategy, sample_dna)
        assert result.success is True
        assert result.total_generated == 5

    # ── 工厂函数 ──────────────────────────────────────────────

    def test_create_generator_bridge_default(self):
        bridge = create_generator_bridge()
        assert isinstance(bridge, GeneratorBridge)
        assert bridge.stats()["generator_type"] == "mock"


# ═══════════════════════════════════════════════════════════════
# E14.4.3.3 Experiment Manager — 40 tests
# ═══════════════════════════════════════════════════════════════


class TestExperimentManager:
    """ExperimentManager 单元测试."""

    # ── create_experiment ─────────────────────────────────────

    def test_create_experiment(self, experiment_manager, sample_plan):
        experiment = experiment_manager.create_experiment(sample_plan, ["V001", "V002"])
        assert experiment.experiment_id != ""
        assert experiment.plan_id == sample_plan.plan_id
        assert experiment.creative_id == "C102"
        assert experiment.status == ExperimentStatus.DRAFT
        assert experiment.variant_ids == ["V001", "V002"]

    def test_create_experiment_with_control(self, experiment_manager, sample_plan):
        experiment = experiment_manager.create_experiment(
            sample_plan, ["V001"], control_creative_id="C102",
        )
        assert experiment.control_group is not None
        assert experiment.control_group.creative_id == "C102"
        assert experiment.control_group.group_type == VariantGroupType.CONTROL

    def test_create_experiment_type(self, experiment_manager, sample_plan):
        experiment = experiment_manager.create_experiment(sample_plan)
        assert experiment.experiment_type == ExperimentType.A_B_TEST

    def test_create_experiment_budget(self, experiment_manager, sample_plan):
        experiment = experiment_manager.create_experiment(sample_plan)
        assert experiment.max_budget == 500.0

    def test_create_experiment_duration(self, experiment_manager, sample_plan):
        experiment = experiment_manager.create_experiment(sample_plan)
        assert experiment.min_duration_days == 3

    def test_create_experiment_success_criteria(self, experiment_manager, sample_plan):
        experiment = experiment_manager.create_experiment(sample_plan)
        assert experiment.success_criteria["min_roas"] == 1.2

    # ── start / pause / resume ────────────────────────────────

    def test_start_experiment(self, experiment_manager, sample_plan):
        experiment = experiment_manager.create_experiment(sample_plan)
        result = experiment_manager.start(experiment)
        assert result is True
        assert experiment.status == ExperimentStatus.RUNNING
        assert experiment.started_at != ""

    def test_start_non_draft_fails(self, experiment_manager, sample_plan):
        experiment = experiment_manager.create_experiment(sample_plan)
        experiment_manager.start(experiment)
        result = experiment_manager.start(experiment)  # 重复启动
        assert result is False

    def test_pause_running_experiment(self, experiment_manager, sample_plan):
        experiment = experiment_manager.create_experiment(sample_plan)
        experiment_manager.start(experiment)
        result = experiment_manager.pause(experiment)
        assert result is True
        assert experiment.status == ExperimentStatus.PAUSED

    def test_pause_non_running_fails(self, experiment_manager, sample_plan):
        experiment = experiment_manager.create_experiment(sample_plan)
        result = experiment_manager.pause(experiment)
        assert result is False

    def test_resume_paused_experiment(self, experiment_manager, sample_plan):
        experiment = experiment_manager.create_experiment(sample_plan)
        experiment_manager.start(experiment)
        experiment_manager.pause(experiment)
        result = experiment_manager.resume(experiment)
        assert result is True
        assert experiment.status == ExperimentStatus.RUNNING

    # ── collect_results ───────────────────────────────────────

    def test_collect_results(self, experiment_manager, sample_plan, winner_variant_metrics):
        experiment = experiment_manager.create_experiment(sample_plan)
        experiment_manager.start(experiment)
        result = experiment_manager.collect_results(
            experiment, [winner_variant_metrics],
        )
        assert result is True
        assert len(experiment.variant_groups) == 1

    def test_collect_results_non_running_fails(self, experiment_manager, sample_plan, winner_variant_metrics):
        experiment = experiment_manager.create_experiment(sample_plan)
        result = experiment_manager.collect_results(experiment, [winner_variant_metrics])
        assert result is False

    def test_collect_results_with_control(self, experiment_manager, sample_plan, winner_variant_metrics):
        experiment = experiment_manager.create_experiment(sample_plan)
        experiment_manager.start(experiment)
        control = VariantMetrics(
            creative_id="C102",
            group_type=VariantGroupType.CONTROL,
            roas=1.5, ctr=0.03, installs=1000,
        )
        experiment_manager.collect_results(experiment, [winner_variant_metrics], control)
        assert experiment.control_group is not None
        assert experiment.control_group.roas == 1.5

    # ── determine_winner ──────────────────────────────────────

    def test_determine_winner_found(self, experiment_manager, sample_plan, winner_variant_metrics):
        experiment = experiment_manager.create_experiment(sample_plan)
        experiment_manager.start(experiment)
        experiment_manager.collect_results(experiment, [winner_variant_metrics])
        result = experiment_manager.determine_winner(experiment)
        assert result == ExperimentResult.WINNER_FOUND
        assert experiment.winner_variant_id == winner_variant_metrics.variant_id
        assert experiment.status == ExperimentStatus.COMPLETED

    def test_determine_winner_no_variants(self, experiment_manager, sample_plan):
        experiment = experiment_manager.create_experiment(sample_plan)
        experiment_manager.start(experiment)
        result = experiment_manager.determine_winner(experiment)
        assert result == ExperimentResult.INCONCLUSIVE

    def test_determine_winner_insufficient_sample(self, experiment_manager, sample_plan):
        experiment = experiment_manager.create_experiment(sample_plan)
        experiment_manager.start(experiment)
        low_sample = VariantMetrics(
            variant_id="V001",
            creative_id="C102_V1",
            roas=2.0, ctr=0.04, fatigue=0.1, installs=200,  # < 500
        )
        experiment_manager.collect_results(experiment, [low_sample])
        result = experiment_manager.determine_winner(experiment)
        assert result == ExperimentResult.INCONCLUSIVE

    def test_determine_winner_all_failed(self, experiment_manager, sample_plan):
        experiment = experiment_manager.create_experiment(sample_plan)
        experiment_manager.start(experiment)
        failed = VariantMetrics(
            variant_id="V001",
            creative_id="C102_V1",
            roas=0.3, ctr=0.01, fatigue=0.2, installs=1000,
        )
        experiment_manager.collect_results(experiment, [failed])
        result = experiment_manager.determine_winner(experiment)
        assert result == ExperimentResult.ALL_FAILED

    def test_determine_winner_no_significant_diff(self, experiment_manager, sample_plan):
        experiment = experiment_manager.create_experiment(sample_plan)
        experiment_manager.start(experiment)
        mid = VariantMetrics(
            variant_id="V001",
            creative_id="C102_V1",
            roas=0.8, ctr=0.02, fatigue=0.3, installs=1000,
        )
        experiment_manager.collect_results(experiment, [mid])
        result = experiment_manager.determine_winner(experiment)
        assert result == ExperimentResult.NO_SIGNIFICANT_DIFF

    def test_determine_winner_with_control_beats(self, experiment_manager, sample_plan, winner_variant_metrics):
        experiment = experiment_manager.create_experiment(sample_plan)
        experiment_manager.start(experiment)
        control = VariantMetrics(
            creative_id="C102",
            group_type=VariantGroupType.CONTROL,
            roas=1.5, ctr=0.03, installs=1000,
        )
        experiment_manager.collect_results(experiment, [winner_variant_metrics], control)
        result = experiment_manager.determine_winner(experiment)
        assert result == ExperimentResult.WINNER_FOUND

    def test_determine_winner_fatigue_too_high(self, experiment_manager, sample_plan):
        experiment = experiment_manager.create_experiment(sample_plan)
        experiment_manager.start(experiment)
        fatigued = VariantMetrics(
            variant_id="V001",
            creative_id="C102_V1",
            roas=2.0, ctr=0.04, fatigue=0.7, installs=1000,  # 疲劳度 > 0.5
        )
        experiment_manager.collect_results(experiment, [fatigued])
        result = experiment_manager.determine_winner(experiment)
        assert result != ExperimentResult.WINNER_FOUND

    # ── complete / fail / cancel ──────────────────────────────

    def test_complete_experiment(self, experiment_manager, sample_plan):
        experiment = experiment_manager.create_experiment(sample_plan)
        result = experiment_manager.complete(experiment)
        assert result is True
        assert experiment.status == ExperimentStatus.COMPLETED

    def test_fail_experiment(self, experiment_manager, sample_plan):
        experiment = experiment_manager.create_experiment(sample_plan)
        result = experiment_manager.fail(experiment, "API error")
        assert result is True
        assert experiment.status == ExperimentStatus.FAILED
        assert "API error" in experiment.summary

    def test_cancel_experiment(self, experiment_manager, sample_plan):
        experiment = experiment_manager.create_experiment(sample_plan)
        result = experiment_manager.cancel(experiment)
        assert result is True
        assert experiment.status == ExperimentStatus.CANCELLED

    def test_cancel_completed_fails(self, experiment_manager, sample_plan):
        experiment = experiment_manager.create_experiment(sample_plan)
        experiment_manager.complete(experiment)
        result = experiment_manager.cancel(experiment)
        assert result is False

    # ── 属性 ──────────────────────────────────────────────────

    def test_experiment_is_active(self, experiment_manager, sample_plan):
        experiment = experiment_manager.create_experiment(sample_plan)
        experiment_manager.start(experiment)
        assert experiment.is_active is True

    def test_experiment_is_completed(self, experiment_manager, sample_plan):
        experiment = experiment_manager.create_experiment(sample_plan)
        experiment_manager.complete(experiment)
        assert experiment.is_completed is True

    def test_experiment_has_winner(self, experiment_manager, sample_plan, winner_variant_metrics):
        experiment = experiment_manager.create_experiment(sample_plan)
        experiment_manager.start(experiment)
        experiment_manager.collect_results(experiment, [winner_variant_metrics])
        experiment_manager.determine_winner(experiment)
        assert experiment.has_winner is True

    # ── 查询 ──────────────────────────────────────────────────

    def test_get_experiment(self, experiment_manager, sample_plan):
        experiment = experiment_manager.create_experiment(sample_plan)
        found = experiment_manager.get_experiment(experiment.experiment_id)
        assert found is not None

    def test_get_experiment_not_found(self, experiment_manager):
        assert experiment_manager.get_experiment("nonexistent") is None

    def test_get_experiments_by_plan(self, experiment_manager, sample_plan):
        experiment_manager.create_experiment(sample_plan)
        exps = experiment_manager.get_experiments_by_plan(sample_plan.plan_id)
        assert len(exps) == 1

    def test_get_experiments_by_creative(self, experiment_manager, sample_plan):
        experiment_manager.create_experiment(sample_plan)
        exps = experiment_manager.get_experiments_by_creative("C102")
        assert len(exps) == 1

    def test_get_active_experiments(self, experiment_manager, sample_plan):
        experiment = experiment_manager.create_experiment(sample_plan)
        experiment_manager.start(experiment)
        active = experiment_manager.get_active_experiments()
        assert len(active) == 1

    def test_get_completed_experiments(self, experiment_manager, sample_plan):
        experiment = experiment_manager.create_experiment(sample_plan)
        experiment_manager.complete(experiment)
        completed = experiment_manager.get_completed_experiments()
        assert len(completed) == 1

    def test_get_winners(self, experiment_manager, sample_plan, winner_variant_metrics):
        experiment = experiment_manager.create_experiment(sample_plan)
        experiment_manager.start(experiment)
        experiment_manager.collect_results(experiment, [winner_variant_metrics])
        experiment_manager.determine_winner(experiment)
        winners = experiment_manager.get_winners()
        assert len(winners) == 1

    # ── generate_report ───────────────────────────────────────

    def test_generate_report(self, experiment_manager, sample_plan):
        experiment_manager.create_experiment(sample_plan)
        report = experiment_manager.generate_report()
        assert report.total_experiments == 1
        assert isinstance(report, ExperimentReport)

    def test_generate_report_success_rate(self, experiment_manager, sample_plan, winner_variant_metrics):
        experiment = experiment_manager.create_experiment(sample_plan)
        experiment_manager.start(experiment)
        experiment_manager.collect_results(experiment, [winner_variant_metrics])
        experiment_manager.determine_winner(experiment)
        report = experiment_manager.generate_report()
        assert report.success_rate == 1.0

    # ── stats / reset ─────────────────────────────────────────

    def test_experiment_manager_stats(self, experiment_manager, sample_plan):
        experiment_manager.create_experiment(sample_plan)
        stats = experiment_manager.stats()
        assert stats["total"] == 1

    def test_experiment_manager_stats_empty(self, experiment_manager):
        stats = experiment_manager.stats()
        assert stats["total"] == 0

    def test_experiment_manager_reset(self, experiment_manager, sample_plan):
        experiment_manager.create_experiment(sample_plan)
        experiment_manager.reset()
        assert experiment_manager.stats()["total"] == 0


# ═══════════════════════════════════════════════════════════════
# E14.4.3.4 Rollout Controller — 40 tests
# ═══════════════════════════════════════════════════════════════


class TestRolloutController:
    """RolloutController 单元测试."""

    # ── evaluate_winner ───────────────────────────────────────

    def test_evaluate_winner_aggressive(self, rollout_controller, winner_variant_metrics):
        experiment = CreativeExperiment(creative_id="C201")
        decision = rollout_controller.evaluate_winner(experiment, winner_variant_metrics)
        assert decision is not None
        assert decision.rollout_strategy == RolloutStrategy.AGGRESSIVE
        assert decision.creative_id == "C201_V1"

    def test_evaluate_winner_gradual(self, rollout_controller):
        experiment = CreativeExperiment(creative_id="C500")
        mid_winner = VariantMetrics(
            variant_id="V001", creative_id="C500_V1",
            roas=1.8, ctr=0.035, fatigue=0.3, spend=500.0, installs=2000,
        )
        decision = rollout_controller.evaluate_winner(experiment, mid_winner)
        assert decision is not None
        assert decision.rollout_strategy == RolloutStrategy.GRADUAL

    def test_evaluate_winner_conservative(self, rollout_controller):
        experiment = CreativeExperiment(creative_id="C600")
        low_winner = VariantMetrics(
            variant_id="V001", creative_id="C600_V1",
            roas=1.2, ctr=0.025, fatigue=0.4, spend=300.0, installs=1500,
        )
        decision = rollout_controller.evaluate_winner(experiment, low_winner)
        assert decision is not None
        assert decision.rollout_strategy == RolloutStrategy.CONSERVATIVE

    def test_evaluate_winner_low_roas_rejected(self, rollout_controller):
        experiment = CreativeExperiment(creative_id="C700")
        low_roas = VariantMetrics(
            variant_id="V001", creative_id="C700_V1",
            roas=0.5, ctr=0.02, fatigue=0.2, spend=200.0, installs=1000,
        )
        decision = rollout_controller.evaluate_winner(experiment, low_roas)
        assert decision is None

    def test_evaluate_winner_high_fatigue_rejected(self, rollout_controller):
        experiment = CreativeExperiment(creative_id="C800")
        high_fatigue = VariantMetrics(
            variant_id="V001", creative_id="C800_V1",
            roas=2.0, ctr=0.04, fatigue=0.7, spend=500.0, installs=2000,
        )
        decision = rollout_controller.evaluate_winner(experiment, high_fatigue)
        assert decision is None

    def test_evaluate_winner_insufficient_sample(self, rollout_controller):
        experiment = CreativeExperiment(creative_id="C900")
        low_sample = VariantMetrics(
            variant_id="V001", creative_id="C900_V1",
            roas=2.0, ctr=0.04, fatigue=0.1, spend=100.0, installs=300,
        )
        decision = rollout_controller.evaluate_winner(experiment, low_sample)
        assert decision is None

    def test_evaluate_winner_budget_calculation(self, rollout_controller, winner_variant_metrics):
        experiment = CreativeExperiment(creative_id="C201")
        decision = rollout_controller.evaluate_winner(experiment, winner_variant_metrics)
        assert decision.target_budget > decision.current_budget
        assert decision.budget_increase_pct > 0

    def test_evaluate_winner_budget_cap(self, rollout_controller):
        experiment = CreativeExperiment(creative_id="C999")
        high_spend = VariantMetrics(
            variant_id="V001", creative_id="C999_V1",
            roas=3.0, ctr=0.05, fatigue=0.1, spend=4000.0, installs=5000,
        )
        decision = rollout_controller.evaluate_winner(experiment, high_spend)
        assert decision is not None
        assert decision.target_budget <= 5000.0  # max_budget cap

    def test_evaluate_winner_risk_level(self, rollout_controller, winner_variant_metrics):
        experiment = CreativeExperiment(creative_id="C201")
        decision = rollout_controller.evaluate_winner(experiment, winner_variant_metrics)
        assert 0.0 <= decision.risk_level <= 1.0

    def test_evaluate_winner_conditions(self, rollout_controller, winner_variant_metrics):
        experiment = CreativeExperiment(creative_id="C201")
        decision = rollout_controller.evaluate_winner(experiment, winner_variant_metrics)
        assert len(decision.conditions) > 0

    def test_evaluate_winner_reason(self, rollout_controller, winner_variant_metrics):
        experiment = CreativeExperiment(creative_id="C201")
        decision = rollout_controller.evaluate_winner(experiment, winner_variant_metrics)
        assert "ROAS" in decision.reason

    # ── approve / execute / complete / rollback ────────────────

    def test_approve_pending_decision(self, rollout_controller, winner_variant_metrics):
        experiment = CreativeExperiment(creative_id="C201")
        decision = rollout_controller.evaluate_winner(experiment, winner_variant_metrics)
        result = rollout_controller.approve(decision)
        assert result is True
        assert decision.status == RolloutStatus.APPROVED

    def test_approve_non_pending_fails(self, rollout_controller, winner_variant_metrics):
        experiment = CreativeExperiment(creative_id="C201")
        decision = rollout_controller.evaluate_winner(experiment, winner_variant_metrics)
        rollout_controller.approve(decision)
        result = rollout_controller.approve(decision)
        assert result is False

    def test_execute_approved_decision(self, rollout_controller, winner_variant_metrics):
        experiment = CreativeExperiment(creative_id="C201")
        decision = rollout_controller.evaluate_winner(experiment, winner_variant_metrics)
        rollout_controller.approve(decision)
        result = rollout_controller.execute(decision)
        assert result is True
        assert decision.status == RolloutStatus.EXECUTING
        assert decision.executed_at != ""

    def test_execute_pending_directly(self, rollout_controller, winner_variant_metrics):
        experiment = CreativeExperiment(creative_id="C201")
        decision = rollout_controller.evaluate_winner(experiment, winner_variant_metrics)
        result = rollout_controller.execute(decision)
        assert result is True
        assert decision.status == RolloutStatus.EXECUTING

    def test_complete_executing(self, rollout_controller, winner_variant_metrics):
        experiment = CreativeExperiment(creative_id="C201")
        decision = rollout_controller.evaluate_winner(experiment, winner_variant_metrics)
        rollout_controller.execute(decision)
        result = rollout_controller.complete(decision)
        assert result is True
        assert decision.status == RolloutStatus.COMPLETED

    def test_rollback_executing(self, rollout_controller, winner_variant_metrics):
        experiment = CreativeExperiment(creative_id="C201")
        decision = rollout_controller.evaluate_winner(experiment, winner_variant_metrics)
        rollout_controller.execute(decision)
        result = rollout_controller.rollback(decision)
        assert result is True
        assert decision.status == RolloutStatus.ROLLED_BACK

    def test_rollback_completed(self, rollout_controller, winner_variant_metrics):
        experiment = CreativeExperiment(creative_id="C201")
        decision = rollout_controller.evaluate_winner(experiment, winner_variant_metrics)
        rollout_controller.execute(decision)
        rollout_controller.complete(decision)
        result = rollout_controller.rollback(decision)
        assert result is True

    def test_rollback_pending_fails(self, rollout_controller, winner_variant_metrics):
        experiment = CreativeExperiment(creative_id="C201")
        decision = rollout_controller.evaluate_winner(experiment, winner_variant_metrics)
        result = rollout_controller.rollback(decision)
        assert result is False

    # ── evaluate_batch ────────────────────────────────────────

    def test_evaluate_batch(self, rollout_controller, winner_variant_metrics):
        exp1 = CreativeExperiment(creative_id="C201")
        exp2 = CreativeExperiment(creative_id="C202")
        decisions = rollout_controller.evaluate_batch([
            (exp1, winner_variant_metrics),
            (exp2, winner_variant_metrics),
        ])
        assert len(decisions) == 2

    def test_evaluate_batch_filters_invalid(self, rollout_controller):
        exp1 = CreativeExperiment(creative_id="C700")
        low_roas = VariantMetrics(
            variant_id="V001", creative_id="C700_V1",
            roas=0.5, ctr=0.02, fatigue=0.2, spend=200.0, installs=1000,
        )
        decisions = rollout_controller.evaluate_batch([(exp1, low_roas)])
        assert len(decisions) == 0

    # ── ua_action ─────────────────────────────────────────────

    def test_rollout_decision_ua_action(self, rollout_controller, winner_variant_metrics):
        experiment = CreativeExperiment(creative_id="C201")
        decision = rollout_controller.evaluate_winner(experiment, winner_variant_metrics)
        ua_action = decision.ua_action
        assert ua_action["action_type"] == "adjust_budget"
        assert ua_action["creative_id"] == "C201_V1"
        assert ua_action["strategy"] == "aggressive"

    # ── 查询 ──────────────────────────────────────────────────

    def test_get_decision(self, rollout_controller, winner_variant_metrics):
        experiment = CreativeExperiment(creative_id="C201")
        decision = rollout_controller.evaluate_winner(experiment, winner_variant_metrics)
        found = rollout_controller.get_decision(decision.decision_id)
        assert found is not None

    def test_get_decision_not_found(self, rollout_controller):
        assert rollout_controller.get_decision("nonexistent") is None

    def test_get_decisions_by_creative(self, rollout_controller, winner_variant_metrics):
        experiment = CreativeExperiment(creative_id="C201")
        rollout_controller.evaluate_winner(experiment, winner_variant_metrics)
        decisions = rollout_controller.get_decisions_by_creative("C201_V1")
        assert len(decisions) == 1

    def test_get_pending_decisions(self, rollout_controller, winner_variant_metrics):
        experiment = CreativeExperiment(creative_id="C201")
        rollout_controller.evaluate_winner(experiment, winner_variant_metrics)
        pending = rollout_controller.get_pending_decisions()
        assert len(pending) == 1

    def test_get_executing_decisions(self, rollout_controller, winner_variant_metrics):
        experiment = CreativeExperiment(creative_id="C201")
        decision = rollout_controller.evaluate_winner(experiment, winner_variant_metrics)
        rollout_controller.execute(decision)
        executing = rollout_controller.get_executing_decisions()
        assert len(executing) == 1

    def test_get_completed_decisions(self, rollout_controller, winner_variant_metrics):
        experiment = CreativeExperiment(creative_id="C201")
        decision = rollout_controller.evaluate_winner(experiment, winner_variant_metrics)
        rollout_controller.execute(decision)
        rollout_controller.complete(decision)
        completed = rollout_controller.get_completed_decisions()
        assert len(completed) == 1

    # ── generate_report ───────────────────────────────────────

    def test_generate_rollout_report(self, rollout_controller, winner_variant_metrics):
        experiment = CreativeExperiment(creative_id="C201")
        rollout_controller.evaluate_winner(experiment, winner_variant_metrics)
        report = rollout_controller.generate_report()
        assert report.total_decisions == 1
        assert isinstance(report, RolloutReport)

    # ── stats / reset ─────────────────────────────────────────

    def test_rollout_stats(self, rollout_controller, winner_variant_metrics):
        experiment = CreativeExperiment(creative_id="C201")
        rollout_controller.evaluate_winner(experiment, winner_variant_metrics)
        stats = rollout_controller.stats()
        assert stats["total"] == 1

    def test_rollout_stats_empty(self, rollout_controller):
        stats = rollout_controller.stats()
        assert stats["total"] == 0

    def test_rollout_reset(self, rollout_controller, winner_variant_metrics):
        experiment = CreativeExperiment(creative_id="C201")
        rollout_controller.evaluate_winner(experiment, winner_variant_metrics)
        rollout_controller.reset()
        assert rollout_controller.stats()["total"] == 0

    # ── 自定义配置 ────────────────────────────────────────────

    def test_rollout_custom_config(self):
        controller = create_rollout_controller(max_budget=10000.0, min_roas=1.5, max_fatigue=0.3)
        experiment = CreativeExperiment(creative_id="C201")
        mid = VariantMetrics(
            variant_id="V001", creative_id="C201_V1",
            roas=1.3, ctr=0.03, fatigue=0.2, spend=500.0, installs=2000,
        )
        decision = controller.evaluate_winner(experiment, mid)
        assert decision is None  # ROAS < min_roas=1.5

    # ── RolloutStrategy enum ──────────────────────────────────

    def test_rollout_strategy_enum(self):
        assert RolloutStrategy.GRADUAL.value == "gradual"
        assert RolloutStrategy.AGGRESSIVE.value == "aggressive"
        assert RolloutStrategy.CONSERVATIVE.value == "conservative"
        assert RolloutStrategy.MAINTAIN.value == "maintain"
        assert RolloutStrategy.HALT.value == "halt"

    # ── RolloutTrigger enum ───────────────────────────────────

    def test_rollout_trigger_enum(self):
        assert RolloutTrigger.EXPERIMENT_WINNER.value == "experiment_winner"
        assert RolloutTrigger.UA_FEEDBACK.value == "ua_feedback"
        assert RolloutTrigger.SUPERVISOR_APPROVAL.value == "supervisor"

    # ── RolloutDecision summary ───────────────────────────────

    def test_decision_summary(self, rollout_controller, winner_variant_metrics):
        experiment = CreativeExperiment(creative_id="C201")
        decision = rollout_controller.evaluate_winner(experiment, winner_variant_metrics)
        assert "C201_V1" in decision.summary


# ═══════════════════════════════════════════════════════════════
# Full Execution Pipeline — 25 tests
# ═══════════════════════════════════════════════════════════════


class TestExecutionPipeline:
    """完整执行管道集成测试."""

    def test_plan_to_action_flow(self, agent, sample_plan):
        batch = agent.create_actions_from_batch([sample_plan])
        assert batch.total_actions >= 1
        action = batch.actions[0]
        assert action.action_type == ExecutionActionType.GENERATE_VARIANTS

    def test_plan_to_generate_flow(self, agent, sample_plan, sample_strategy, sample_dna):
        result = agent.generate_variants(sample_plan, sample_strategy, sample_dna)
        assert result.success is True
        assert result.total_generated == 5

    def test_plan_to_experiment_flow(self, agent, sample_plan):
        experiment = agent.start_experiment(sample_plan, ["V001", "V002"])
        assert experiment.status == ExperimentStatus.RUNNING
        assert experiment.creative_id == "C102"

    def test_experiment_to_winner_flow(self, agent, sample_plan, winner_variant_metrics):
        experiment = agent.start_experiment(sample_plan, ["V001"])
        result = agent.collect_experiment_results(experiment, [winner_variant_metrics])
        assert result == ExperimentResult.WINNER_FOUND

    def test_winner_to_rollout_flow(self, agent, winner_variant_metrics):
        experiment = CreativeExperiment(creative_id="C201")
        decision = agent.evaluate_rollout(experiment, winner_variant_metrics)
        assert decision is not None
        assert decision.rollout_strategy == RolloutStrategy.AGGRESSIVE

    def test_full_pipeline(self, agent, sample_plan, sample_strategy, sample_dna):
        strategy_map = {sample_plan.plan_id: sample_strategy}
        dna_map = {"C102": sample_dna}
        pipeline = agent.run_full_execution_pipeline(
            [sample_plan], strategy_map, dna_map,
        )
        assert pipeline["total_plans"] == 1
        assert pipeline["total_variants"] == 5
        assert pipeline["total_experiments"] == 1
        assert "batch" in pipeline
        assert "generation_results" in pipeline
        assert "experiments" in pipeline

    def test_full_pipeline_multiple_plans(self, agent, sample_plan, sample_scale_plan, sample_strategy, sample_dna):
        strategy_map = {
            sample_plan.plan_id: sample_strategy,
            sample_scale_plan.plan_id: sample_strategy,
        }
        dna_map = {"C102": sample_dna, "C201": sample_dna}
        pipeline = agent.run_full_execution_pipeline(
            [sample_plan, sample_scale_plan], strategy_map, dna_map,
        )
        assert pipeline["total_plans"] == 2

    def test_execute_rollout_via_agent(self, agent, winner_variant_metrics):
        experiment = CreativeExperiment(creative_id="C201")
        decision = agent.evaluate_rollout(experiment, winner_variant_metrics)
        success = agent.execute_rollout(decision)
        assert success is True
        assert decision.status == RolloutStatus.EXECUTING

    def test_rollback_rollout_via_agent(self, agent, winner_variant_metrics):
        experiment = CreativeExperiment(creative_id="C201")
        decision = agent.evaluate_rollout(experiment, winner_variant_metrics)
        agent.execute_rollout(decision)
        result = agent.rollback_rollout(decision)
        assert result is True
        assert decision.status == RolloutStatus.ROLLED_BACK

    def test_pipeline_state_transitions(self, agent, sample_plan, sample_strategy, sample_dna):
        strategy_map = {sample_plan.plan_id: sample_strategy}
        dna_map = {"C102": sample_dna}
        agent.run_full_execution_pipeline([sample_plan], strategy_map, dna_map)
        assert agent.state == CreativeAgentState.IDLE

    def test_generate_variants_state_transition(self, agent, sample_plan, sample_strategy, sample_dna):
        agent.generate_variants(sample_plan, sample_strategy, sample_dna)
        assert agent.state == CreativeAgentState.IDLE

    def test_experiment_lifecycle(self, agent, sample_plan, winner_variant_metrics):
        experiment = agent.start_experiment(sample_plan, ["V001"])
        assert experiment.is_active is True
        result = agent.collect_experiment_results(experiment, [winner_variant_metrics])
        assert result == ExperimentResult.WINNER_FOUND
        assert experiment.is_completed is True

    def test_pipeline_without_strategy_map(self, agent, sample_plan):
        pipeline = agent.run_full_execution_pipeline([sample_plan])
        assert pipeline["total_plans"] == 1
        assert pipeline["total_variants"] == 0  # 无策略则无生成

    def test_pipeline_empty_plans(self, agent):
        pipeline = agent.run_full_execution_pipeline([])
        assert pipeline["total_plans"] == 0
        assert pipeline["total_variants"] == 0

    # ── 子模块访问 ────────────────────────────────────────────

    def test_get_executor(self, agent):
        executor = agent.get_executor()
        assert isinstance(executor, CreativeExecutor)

    def test_get_generator_bridge(self, agent):
        bridge = agent.get_generator_bridge()
        assert isinstance(bridge, GeneratorBridge)

    def test_get_experiment_manager(self, agent):
        manager = agent.get_experiment_manager()
        assert isinstance(manager, ExperimentManager)

    def test_get_rollout_controller(self, agent):
        controller = agent.get_rollout_controller()
        assert isinstance(controller, RolloutController)

    # ── 工厂函数 ──────────────────────────────────────────────

    def test_create_executor_factory(self):
        executor = create_executor()
        assert isinstance(executor, CreativeExecutor)

    def test_create_experiment_manager_factory(self):
        manager = create_experiment_manager()
        assert isinstance(manager, ExperimentManager)

    def test_create_rollout_controller_factory(self):
        controller = create_rollout_controller()
        assert isinstance(controller, RolloutController)

    # ── 综合管道 ──────────────────────────────────────────────

    def test_complete_creative_growth_loop(self, agent, sample_plan, sample_strategy, sample_dna, winner_variant_metrics):
        """验证完整创意增长闭环: Plan → Generate → Experiment → Winner → Rollout."""
        # 1. Plan → Action
        batch = agent.create_actions_from_batch([sample_plan])
        assert batch.total_actions == 1

        # 2. Generate
        result = agent.generate_variants(sample_plan, sample_strategy, sample_dna)
        assert result.total_generated == 5

        # 3. Experiment
        variant_ids = [v.variant_id for v in result.variants]
        experiment = agent.start_experiment(sample_plan, variant_ids)
        assert experiment.is_active is True

        # 4. Collect + Winner
        winner_result = agent.collect_experiment_results(experiment, [winner_variant_metrics])
        assert winner_result == ExperimentResult.WINNER_FOUND

        # 5. Rollout
        decision = agent.evaluate_rollout(experiment, winner_variant_metrics)
        assert decision is not None
        assert decision.rollout_strategy == RolloutStrategy.AGGRESSIVE

        # 6. Execute Rollout
        success = agent.execute_rollout(decision)
        assert success is True

    def test_fatigue_creative_loop(self, agent, sample_plan, sample_strategy, sample_dna, fatigue_variant_metrics):
        """验证疲劳素材处理: 疲劳 → 生成变体 → 实验 → 无赢家."""
        # 1. Generate variants for fatigued creative
        result = agent.generate_variants(sample_plan, sample_strategy, sample_dna)
        assert result.total_generated == 5

        # 2. Start experiment
        variant_ids = [v.variant_id for v in result.variants]
        experiment = agent.start_experiment(sample_plan, variant_ids)
        assert experiment.is_active is True

        # 3. Collect results (fatigue variant → no winner)
        result = agent.collect_experiment_results(experiment, [fatigue_variant_metrics])
        assert result != ExperimentResult.WINNER_FOUND


# ═══════════════════════════════════════════════════════════════
# CreativeAgent Integration — 20 tests
# ═══════════════════════════════════════════════════════════════


class TestCreativeAgentE1443Integration:
    """CreativeAgent E14.4.3 集成测试."""

    def test_agent_has_executor(self, agent):
        assert agent.get_executor() is not None

    def test_agent_has_generator_bridge(self, agent):
        assert agent.get_generator_bridge() is not None

    def test_agent_has_experiment_manager(self, agent):
        assert agent.get_experiment_manager() is not None

    def test_agent_has_rollout_controller(self, agent):
        assert agent.get_rollout_controller() is not None

    def test_agent_stats_includes_e1443(self, agent):
        stats = agent.stats()
        assert "executor" in stats
        assert "generator_bridge" in stats
        assert "experiment_manager" in stats
        assert "rollout_controller" in stats

    def test_agent_reset_clears_e1443(self, agent, sample_plan, sample_strategy, sample_dna):
        agent.generate_variants(sample_plan, sample_strategy, sample_dna)
        agent.reset()
        stats = agent.stats()
        assert stats["generator_bridge"]["total_variants"] == 0

    def test_agent_state_executing(self, agent, sample_plan, sample_strategy, sample_dna):
        """验证执行时状态切换."""
        # 状态在方法内部管理，完成后回到 IDLE
        agent.generate_variants(sample_plan, sample_strategy, sample_dna)
        assert agent.state == CreativeAgentState.IDLE

    def test_agent_executing_state_enum_exists(self):
        assert CreativeAgentState.EXECUTING.value == "executing"

    def test_agent_create_with_generator_type(self):
        agent = create_creative_agent()
        assert agent.get_generator_bridge() is not None
        assert agent.get_generator_bridge().stats()["generator_type"] == "mock"

    def test_strategy_pipeline_integration(self, agent, sample_plan, sample_strategy, sample_dna):
        """验证策略管道与执行管道集成."""
        # 策略管道 (E14.4.2)
        signals = [{"creative_id": "C102", "issue": "creative_fatigue", "confidence": 0.91}]
        opp_report = agent.detect_opportunities(signals)
        assert opp_report.total_opportunities >= 0

        # 执行管道 (E14.4.3)
        result = agent.generate_variants(sample_plan, sample_strategy, sample_dna)
        assert result.success is True

    def test_analyze_and_execute_flow(self, agent, sample_plan, sample_strategy, sample_dna):
        """验证分析→执行完整流程."""
        # E14.4.1: 分析
        rec = agent.quick_analysis("C102", roas=0.45, ctr=0.018, fatigue=0.82)
        assert rec.creative_id == "C102"
        assert rec.action is not None

        # E14.4.3: 执行
        result = agent.generate_variants(sample_plan, sample_strategy, sample_dna)
        assert result.success is True

    def test_variant_metrics_creation(self):
        vm = VariantMetrics(
            variant_id="V001",
            creative_id="C001",
            group_type=VariantGroupType.VARIANT,
            roas=1.5, ctr=0.03, cvr=0.05,
            fatigue=0.2, spend=300.0, revenue=450.0,
            installs=1000, payer_rate=0.08, ltv=6.0,
        )
        assert vm.to_dict()["roas"] == 1.5

    def test_execution_action_to_dict(self):
        action = CreativeExecutionAction(
            creative_id="C102",
            action_type=ExecutionActionType.GENERATE_VARIANTS,
            parameters=ExecutionParameters(count=5),
        )
        d = action.to_dict()
        assert d["creative_id"] == "C102"
        assert d["action_type"] == "generate_variants"
        assert d["parameters"]["count"] == 5

    def test_generation_result_properties(self):
        result = GenerationResult(
            total_generated=5,
            variants=[CreativeVariant() for _ in range(5)],
        )
        assert result.variant_count == 5
        assert result.success is True

    def test_experiment_properties(self):
        experiment = CreativeExperiment(
            creative_id="C102",
            variant_ids=["V001", "V002"],
        )
        assert experiment.variant_count == 0  # variant_groups 为空
        assert experiment.is_active is False
        assert experiment.has_winner is False

    def test_rollout_decision_properties(self, winner_variant_metrics):
        decision = RolloutDecision(
            creative_id="C201_V1",
            rollout_strategy=RolloutStrategy.AGGRESSIVE,
            current_budget=500.0,
            target_budget=1000.0,
            budget_increase_pct=1.0,
            risk_level=0.15,
        )
        assert "C201_V1" in decision.summary
        assert decision.ua_action["action_type"] == "adjust_budget"

    def test_batch_plan_to_dict(self, sample_plan):
        batch = BatchPlan(plans=[sample_plan])
        d = batch.to_dict()
        assert len(d["plans"]) == 1

    def test_experiment_report_to_dict(self):
        report = ExperimentReport(
            total_experiments=5, active=2, completed=3, winners_found=1,
        )
        d = report.to_dict()
        assert d["total_experiments"] == 5

    def test_rollout_report_to_dict(self):
        report = RolloutReport(
            total_decisions=3, executed=2, pending=1,
        )
        d = report.to_dict()
        assert d["total_decisions"] == 3

    def test_execution_batch_to_dict(self):
        batch = ExecutionBatch(
            total_actions=3, completed=2, failed=1, pending=0,
        )
        d = batch.to_dict()
        assert d["total_actions"] == 3


# ═══════════════════════════════════════════════════════════════
# Regression Tests — 15 tests
# ═══════════════════════════════════════════════════════════════


class TestE1443Regression:
    """E14.4.3 回归测试 — 确保 E14.4.1 / E14.4.2 / E14.3 / E14.2 / E14.1 不受影响."""

    # ── E14.4.1 回归 ──────────────────────────────────────────

    def test_e1441_analyze_creative(self, agent):
        rec = agent.quick_analysis("C102", roas=0.45, ctr=0.018, fatigue=0.82)
        assert rec.creative_id == "C102"
        assert rec.action is not None

    def test_e1441_extract_dna(self, agent):
        dna = agent.extract_dna("C102", "test", hook="before_after", visual="fantasy")
        assert dna.creative_id == "C102"

    def test_e1441_compare_dna(self, agent):
        dna1 = agent.extract_dna("C102", "a", hook="before_after", visual="fantasy")
        dna2 = agent.extract_dna("C103", "b", hook="rescue", visual="realistic")
        comparison = agent.compare_dna(dna1, dna2)
        assert comparison is not None

    # ── E14.4.2 回归 ──────────────────────────────────────────

    def test_e1442_detect_opportunities(self, agent):
        signals = [{"creative_id": "C102", "issue": "creative_fatigue", "confidence": 0.91}]
        report = agent.detect_opportunities(signals)
        assert report is not None

    def test_e1442_generate_strategies(self, agent):
        signals = [{"creative_id": "C102", "issue": "creative_fatigue", "confidence": 0.91}]
        opp_report = agent.detect_opportunities(signals)
        if opp_report.opportunities:
            strategy_report = agent.generate_strategies(opp_report.opportunities)
            assert strategy_report is not None

    def test_e1442_plan_creative_batch(self, agent):
        signals = [{"creative_id": "C102", "issue": "creative_fatigue", "confidence": 0.91}]
        opp_report = agent.detect_opportunities(signals)
        if opp_report.opportunities:
            strategy_report = agent.generate_strategies(opp_report.opportunities)
            batch = agent.plan_creative_batch(strategy_report.strategies)
            assert batch is not None

    def test_e1442_evaluate_creative_strategy(self, agent):
        strategy = CreativeStrategy(
            strategy_type=CreativeStrategyType.REFRESH_HOOK,
            target_creative_id="C102",
            mutation_plan=[],
            priority=OpportunityPriority.HIGH,
        )
        before = {"roas": 0.8, "ctr": 0.02}
        after = {"roas": 1.2, "ctr": 0.03}
        outcome = agent.evaluate_creative_strategy(strategy, before, after)
        assert outcome is not None

    def test_e1442_full_strategy_pipeline(self, agent):
        signals = [{"creative_id": "C102", "issue": "creative_fatigue", "confidence": 0.91}]
        pipeline = agent.run_full_strategy_pipeline(signals)
        assert "opportunities" in pipeline
        assert "strategies" in pipeline
        assert "plans" in pipeline

    # ── E14.3 回归 ────────────────────────────────────────────

    def test_e1443_agent_communication(self):
        """验证 E14.1 通信协议不受影响."""
        bus = create_message_bus()
        registry = create_agent_registry()
        assert bus is not None
        assert registry is not None

    def test_e1443_agent_identity(self):
        ua_id = comm_ua_identity()
        creative_id = comm_creative_identity()
        assert ua_id.role.value == "ua"
        assert creative_id.role.value == "creative"

    # ── E14.4.1 核心功能回归 ──────────────────────────────────

    def test_e1441_analyze_batch(self, agent):
        metrics_list = [
            {"creative_id": "C102", "roas": 0.45, "ctr": 0.018, "fatigue": 0.82},
            {"creative_id": "C201", "roas": 2.5, "ctr": 0.04, "fatigue": 0.15},
        ]
        report = agent.analyze_creative_batch(metrics_list)
        assert report is not None
        assert len(report.recommendations) >= 1

    def test_e1441_winner_dna(self, agent):
        dna = agent.extract_dna("C201", "winner", hook="rescue", visual="fantasy",
                                 fitness={"roas": 2.5, "ctr": 0.04})
        winner_report = agent.extract_winner_dna()
        assert winner_report is not None

    # ── E14.4.2 子模块访问 ────────────────────────────────────

    def test_e1442_submodule_access(self, agent):
        assert agent.get_opportunity_engine() is not None
        assert agent.get_strategy_engine() is not None
        assert agent.get_planner() is not None
        assert agent.get_evaluator() is not None

    # ── E14.3 UA Agent 回归 ──────────────────────────────────

    def test_e1443_ua_creative_communication(self, agent):
        """验证 UA Agent → Creative Agent 通信管道."""
        ua_id = comm_ua_identity()
        creative_id = comm_creative_identity()
        bus = create_message_bus()
        registry = create_agent_registry()
        registry.register(ua_id)
        registry.register(creative_id)
        assert registry.get(ua_id.agent_id) is not None
        assert registry.get(creative_id.agent_id) is not None

    # ── 全局重置 ──────────────────────────────────────────────

    def test_agent_full_reset(self, agent, sample_plan, sample_strategy, sample_dna):
        agent.generate_variants(sample_plan, sample_strategy, sample_dna)
        agent.reset()
        stats = agent.stats()
        assert stats["executor"]["total"] == 0
        assert stats["generator_bridge"]["total_variants"] == 0
        assert stats["experiment_manager"]["total"] == 0
        assert stats["rollout_controller"]["total"] == 0