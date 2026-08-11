"""E11.8.2 — Strategy Executor Tests。

覆盖：
  - Models: MutationOperation, MutationParameter, MutationPlan, ExecutionResult
  - MutationMapper: 5种 StrategyType 映射
  - ExecutionPlanner: Strategy → MutationPlan
  - StrategyExecutor: execute() with Scheduler
  - Controller Integration: execute_strategy(), plan_and_execute()
  - Full Pipeline
  - Package Exports
"""

from __future__ import annotations

import pytest

from market_ops.creative_vision_runtime.autonomous_controller.strategy.executor.models import (
    ExecutionResult,
    MutationOperation,
    MutationParameter,
    MutationPlan,
)
from market_ops.creative_vision_runtime.autonomous_controller.strategy.executor.mutation_mapper import (
    MutationMapper,
)
from market_ops.creative_vision_runtime.autonomous_controller.strategy.executor.execution_planner import (
    ExecutionPlanner,
)
from market_ops.creative_vision_runtime.autonomous_controller.strategy.executor.strategy_executor import (
    StrategyExecutor,
)
from market_ops.creative_vision_runtime.autonomous_controller.strategy.models import (
    EvolutionObjective,
    EvolutionStrategy,
    Intensity,
    MutationFocus,
    StrategyType,
)


# ── Helpers ──────────────────────────────────────────────────


def _make_strategy(
    strategy_type: StrategyType = StrategyType.EXPLORE_NEW,
    mutation_focus: MutationFocus = MutationFocus.HOOK,
    intensity: Intensity = Intensity.MEDIUM,
    confidence: float = 0.7,
    target_genomes: list | None = None,
) -> EvolutionStrategy:
    obj = EvolutionObjective(metric="CTR", current_value=0.03, target_value=0.05)
    return EvolutionStrategy(
        strategy_type=strategy_type,
        objective=obj,
        target_genomes=target_genomes or ["g1", "g2"],
        mutation_focus=mutation_focus,
        intensity=intensity,
        confidence=confidence,
        reason=f"Test {strategy_type.value}",
    )


# ═══════════════════════════════════════════════════════════════
# Models
# ═══════════════════════════════════════════════════════════════


class TestMutationOperation:
    """MutationOperation 枚举测试。"""

    def test_values(self):
        assert MutationOperation.MODIFY.value == "modify"
        assert MutationOperation.CREATE.value == "create"
        assert MutationOperation.CROSSOVER.value == "crossover"
        assert MutationOperation.RETIRE.value == "retire"
        assert MutationOperation.CLONE.value == "clone"

    def test_count(self):
        assert len(MutationOperation) == 5


class TestMutationParameter:
    """MutationParameter 测试。"""

    def test_create_default(self):
        p = MutationParameter()
        assert p.focus == ""
        assert p.intensity == 0.0
        assert p.target_gene == ""

    def test_create_full(self):
        p = MutationParameter(
            focus="hook",
            intensity=0.3,
            target_gene="hook_pattern",
            description="Improve hook",
        )
        assert p.focus == "hook"
        assert p.intensity == 0.3
        assert p.target_gene == "hook_pattern"

    def test_to_dict(self):
        p = MutationParameter(
            focus="hook",
            intensity=0.3,
            target_gene="opening_scene",
            description="Improve first 3 seconds",
        )
        d = p.to_dict()
        assert d["focus"] == "hook"
        assert d["intensity"] == 0.3
        assert d["target_gene"] == "opening_scene"

    def test_metadata(self):
        p = MutationParameter(
            metadata={"strategy_type": "exploit_winner"}
        )
        assert p.metadata["strategy_type"] == "exploit_winner"

    def test_repr(self):
        p = MutationParameter(focus="hook", target_gene="hook_pattern", intensity=0.3)
        r = repr(p)
        assert "hook" in r
        assert "hook_pattern" in r


class TestMutationPlan:
    """MutationPlan 测试。"""

    def test_create_default(self):
        plan = MutationPlan()
        assert plan.plan_id.startswith("plan_")
        assert plan.genome_ids == []
        assert plan.operations == []
        assert plan.mutations == []

    def test_create_full(self):
        plan = MutationPlan(
            strategy_id="strat_abc",
            genome_ids=["g1", "g2"],
            operations=[MutationOperation.MODIFY, MutationOperation.CLONE],
            mutations=[
                MutationParameter(focus="hook", target_gene="hook_pattern"),
                MutationParameter(focus="visual", target_gene="visual_style"),
            ],
            estimated_cost=2.5,
            priority=80,
        )
        assert plan.strategy_id == "strat_abc"
        assert plan.genome_ids == ["g1", "g2"]
        assert plan.operation_count == 2
        assert plan.mutation_count == 2
        assert plan.estimated_cost == 2.5
        assert plan.priority == 80

    def test_operation_count(self):
        plan = MutationPlan(operations=[MutationOperation.MODIFY])
        assert plan.operation_count == 1

    def test_mutation_count(self):
        plan = MutationPlan(mutations=[
            MutationParameter(),
            MutationParameter(),
            MutationParameter(),
        ])
        assert plan.mutation_count == 3

    def test_total_genomes(self):
        plan = MutationPlan(genome_ids=["g1", "g2", "g3"])
        assert plan.total_genomes == 3

    def test_is_create(self):
        plan = MutationPlan(operations=[MutationOperation.CREATE])
        assert plan.is_create is True
        assert plan.is_modify is False

    def test_is_modify(self):
        plan = MutationPlan(operations=[MutationOperation.MODIFY])
        assert plan.is_modify is True
        assert plan.is_create is False

    def test_to_dict(self):
        plan = MutationPlan(
            strategy_id="strat_abc",
            genome_ids=["g1"],
            operations=[MutationOperation.MODIFY],
            mutations=[MutationParameter(focus="hook", target_gene="hook_pattern")],
        )
        d = plan.to_dict()
        assert d["strategy_id"] == "strat_abc"
        assert d["operations"] == ["modify"]
        assert len(d["mutations"]) == 1

    def test_repr(self):
        plan = MutationPlan(
            operations=[MutationOperation.MODIFY],
            mutations=[MutationParameter()],
            genome_ids=["g1"],
        )
        r = repr(plan)
        assert "MutationPlan" in r

    def test_custom_id(self):
        plan = MutationPlan(plan_id="my_plan")
        assert plan.plan_id == "my_plan"

    def test_metadata(self):
        plan = MutationPlan(metadata={"source": "planner"})
        assert plan.metadata["source"] == "planner"


class TestExecutionResult:
    """ExecutionResult 测试。"""

    def test_create_default(self):
        r = ExecutionResult()
        assert r.plan_id == ""
        assert r.tasks_created == 0
        assert r.success is False

    def test_create_success(self):
        r = ExecutionResult(
            plan_id="plan_abc",
            strategy_id="strat_abc",
            tasks_created=5,
            task_ids=["t1", "t2", "t3", "t4", "t5"],
            success=True,
            reason="All tasks submitted",
        )
        assert r.tasks_created == 5
        assert r.success is True
        assert r.has_tasks is True

    def test_has_tasks(self):
        r = ExecutionResult(tasks_created=3)
        assert r.has_tasks is True

    def test_has_no_tasks(self):
        r = ExecutionResult(tasks_created=0)
        assert r.has_tasks is False

    def test_is_partial(self):
        r = ExecutionResult(tasks_created=3, success=False)
        assert r.is_partial is True

    def test_is_not_partial_full_success(self):
        r = ExecutionResult(tasks_created=3, success=True)
        assert r.is_partial is False

    def test_is_not_partial_no_tasks(self):
        r = ExecutionResult(tasks_created=0, success=False)
        assert r.is_partial is False

    def test_to_dict(self):
        r = ExecutionResult(
            plan_id="plan_abc",
            strategy_id="strat_abc",
            tasks_created=2,
            task_ids=["t1", "t2"],
            success=True,
        )
        d = r.to_dict()
        assert d["plan_id"] == "plan_abc"
        assert d["tasks_created"] == 2
        assert d["success"] is True

    def test_repr(self):
        r = ExecutionResult(plan_id="plan_abc", tasks_created=3, success=True)
        rep = repr(r)
        assert "plan_abc" in rep
        assert "3" in rep

    def test_metadata(self):
        r = ExecutionResult(metadata={"source": "executor"})
        assert r.metadata["source"] == "executor"


# ═══════════════════════════════════════════════════════════════
# MutationMapper
# ═══════════════════════════════════════════════════════════════


class TestMutationMapperExploitWinner:
    """EXPLOIT_WINNER 映射测试。"""

    def test_operations(self):
        mapper = MutationMapper()
        s = _make_strategy(StrategyType.EXPLOIT_WINNER, MutationFocus.HOOK, Intensity.SMALL)
        result = mapper.map(s)
        assert MutationOperation.MODIFY in result["operations"]
        assert MutationOperation.CLONE in result["operations"]

    def test_focus_hook_generates_hook_genes(self):
        mapper = MutationMapper()
        s = _make_strategy(StrategyType.EXPLOIT_WINNER, MutationFocus.HOOK, Intensity.SMALL)
        result = mapper.map(s)
        genes = [m.target_gene for m in result["mutations"]]
        assert "hook_pattern" in genes
        assert "opening_scene" in genes

    def test_focus_visual_generates_visual_genes(self):
        mapper = MutationMapper()
        s = _make_strategy(StrategyType.EXPLOIT_WINNER, MutationFocus.VISUAL, Intensity.SMALL)
        result = mapper.map(s)
        genes = [m.target_gene for m in result["mutations"]]
        assert "visual_style" in genes
        assert "color_palette" in genes

    def test_small_intensity(self):
        mapper = MutationMapper()
        s = _make_strategy(StrategyType.EXPLOIT_WINNER, MutationFocus.HOOK, Intensity.SMALL)
        result = mapper.map(s)
        for m in result["mutations"]:
            assert m.intensity == pytest.approx(0.2)

    def test_medium_intensity(self):
        mapper = MutationMapper()
        s = _make_strategy(StrategyType.EXPLOIT_WINNER, MutationFocus.HOOK, Intensity.MEDIUM)
        result = mapper.map(s)
        for m in result["mutations"]:
            assert m.intensity == pytest.approx(0.4)


class TestMutationMapperFixFailure:
    """FIX_FAILURE 映射测试。"""

    def test_operations(self):
        mapper = MutationMapper()
        s = _make_strategy(StrategyType.FIX_FAILURE, MutationFocus.VISUAL, Intensity.LARGE)
        result = mapper.map(s)
        assert MutationOperation.MODIFY in result["operations"]
        assert MutationOperation.CROSSOVER in result["operations"]

    def test_large_intensity(self):
        mapper = MutationMapper()
        s = _make_strategy(StrategyType.FIX_FAILURE, MutationFocus.VISUAL, Intensity.LARGE)
        result = mapper.map(s)
        for m in result["mutations"]:
            assert m.intensity == pytest.approx(0.7)

    def test_fix_failure_defaults_to_full(self):
        """非 FULL 在 FIX_FAILURE 下也默认全维度。"""
        mapper = MutationMapper()
        s = _make_strategy(StrategyType.FIX_FAILURE, MutationFocus.HOOK, Intensity.LARGE)
        result = mapper.map(s)
        # HOOK mapped to FULL for failure repair
        genes = [m.target_gene for m in result["mutations"]]
        assert len(genes) > 3  # FULL has many genes


class TestMutationMapperDiversify:
    """DIVERSIFY 映射测试。"""

    def test_operations(self):
        mapper = MutationMapper()
        s = _make_strategy(StrategyType.DIVERSIFY, MutationFocus.FULL, Intensity.RADICAL)
        result = mapper.map(s)
        assert MutationOperation.CREATE in result["operations"]
        assert len(result["operations"]) == 1

    def test_radical_intensity(self):
        mapper = MutationMapper()
        s = _make_strategy(StrategyType.DIVERSIFY, MutationFocus.FULL, Intensity.RADICAL)
        result = mapper.map(s)
        for m in result["mutations"]:
            assert m.intensity == pytest.approx(0.9)

    def test_full_focus_genes(self):
        mapper = MutationMapper()
        s = _make_strategy(StrategyType.DIVERSIFY, MutationFocus.FULL, Intensity.RADICAL)
        result = mapper.map(s)
        assert len(result["mutations"]) >= 6


class TestMutationMapperScaleSuccess:
    """SCALE_SUCCESS 映射测试。"""

    def test_operations(self):
        mapper = MutationMapper()
        s = _make_strategy(StrategyType.SCALE_SUCCESS, MutationFocus.REWARD, Intensity.MEDIUM)
        result = mapper.map(s)
        assert MutationOperation.CLONE in result["operations"]
        assert MutationOperation.MODIFY in result["operations"]

    def test_reward_genes(self):
        mapper = MutationMapper()
        s = _make_strategy(StrategyType.SCALE_SUCCESS, MutationFocus.REWARD, Intensity.MEDIUM)
        result = mapper.map(s)
        genes = [m.target_gene for m in result["mutations"]]
        assert "reward_timing" in genes
        assert "reward_amount" in genes


class TestMutationMapperExploreNew:
    """EXPLORE_NEW 映射测试。"""

    def test_operations(self):
        mapper = MutationMapper()
        s = _make_strategy(StrategyType.EXPLORE_NEW, MutationFocus.GAMEPLAY, Intensity.MEDIUM)
        result = mapper.map(s)
        assert MutationOperation.CREATE in result["operations"]

    def test_gameplay_genes(self):
        mapper = MutationMapper()
        s = _make_strategy(StrategyType.EXPLORE_NEW, MutationFocus.GAMEPLAY, Intensity.MEDIUM)
        result = mapper.map(s)
        genes = [m.target_gene for m in result["mutations"]]
        assert "gameplay_display" in genes


class TestMutationMapperEdgeCases:
    """边界情况测试。"""

    def test_pacing_focus(self):
        mapper = MutationMapper()
        s = _make_strategy(StrategyType.EXPLORE_NEW, MutationFocus.PACING, Intensity.MEDIUM)
        result = mapper.map(s)
        genes = [m.target_gene for m in result["mutations"]]
        assert "pacing_rhythm" in genes

    def test_all_focuses_have_genes(self):
        mapper = MutationMapper()
        for focus in MutationFocus:
            s = _make_strategy(StrategyType.EXPLORE_NEW, focus, Intensity.MEDIUM)
            result = mapper.map(s)
            assert len(result["mutations"]) >= 1, f"No genes for focus {focus}"

    def test_repr(self):
        mapper = MutationMapper()
        assert "MutationMapper" in repr(mapper)


# ═══════════════════════════════════════════════════════════════
# ExecutionPlanner
# ═══════════════════════════════════════════════════════════════


class TestExecutionPlanner:
    """ExecutionPlanner 测试。"""

    def test_create_plan(self):
        planner = ExecutionPlanner()
        s = _make_strategy(StrategyType.EXPLOIT_WINNER, MutationFocus.HOOK, Intensity.SMALL)
        plan = planner.create_plan(s)
        assert isinstance(plan, MutationPlan)
        assert plan.plan_id.startswith("plan_")
        assert plan.strategy_id == s.strategy_id
        assert plan.operation_count >= 1
        assert plan.mutation_count >= 1

    def test_plan_has_estimated_cost(self):
        planner = ExecutionPlanner()
        s = _make_strategy(StrategyType.EXPLOIT_WINNER, MutationFocus.HOOK, Intensity.SMALL)
        plan = planner.create_plan(s)
        assert plan.estimated_cost > 0

    def test_plan_has_priority(self):
        planner = ExecutionPlanner()
        s = _make_strategy(StrategyType.DIVERSIFY, MutationFocus.FULL, Intensity.RADICAL, confidence=0.9)
        plan = planner.create_plan(s)
        assert plan.priority > 0
        assert plan.priority <= 100

    def test_create_plans_batch(self):
        planner = ExecutionPlanner()
        strategies = [
            _make_strategy(StrategyType.EXPLOIT_WINNER, MutationFocus.HOOK, Intensity.SMALL),
            _make_strategy(StrategyType.EXPLORE_NEW, MutationFocus.VISUAL, Intensity.MEDIUM),
        ]
        plans = planner.create_plans(strategies)
        assert len(plans) == 2
        assert plans[0].strategy_id == strategies[0].strategy_id
        assert plans[1].strategy_id == strategies[1].strategy_id

    def test_diversify_priority_higher_than_explore(self):
        planner = ExecutionPlanner()
        s_div = _make_strategy(StrategyType.DIVERSIFY, MutationFocus.FULL, Intensity.RADICAL, confidence=0.9)
        s_exp = _make_strategy(StrategyType.EXPLORE_NEW, MutationFocus.HOOK, Intensity.MEDIUM, confidence=0.9)
        plan_div = planner.create_plan(s_div)
        plan_exp = planner.create_plan(s_exp)
        assert plan_div.priority > plan_exp.priority

    def test_plan_metadata(self):
        planner = ExecutionPlanner()
        s = _make_strategy(StrategyType.EXPLOIT_WINNER, MutationFocus.HOOK, Intensity.SMALL)
        plan = planner.create_plan(s)
        assert plan.metadata["strategy_type"] == "exploit_winner"
        assert plan.metadata["mutation_focus"] == "hook"

    def test_dependency_injection(self):
        mapper = MutationMapper()
        planner = ExecutionPlanner(mutation_mapper=mapper)
        assert planner.mutation_mapper is mapper

    def test_repr(self):
        planner = ExecutionPlanner()
        assert "ExecutionPlanner" in repr(planner)


# ═══════════════════════════════════════════════════════════════
# StrategyExecutor
# ═══════════════════════════════════════════════════════════════


class MockScheduler:
    """Mock Scheduler 用于测试。"""

    def __init__(self, reject: bool = False):
        self.submitted: list[Any] = []
        self._reject = reject

    def submit(self, task):
        if self._reject:
            return ""
        self.submitted.append(task)
        return task.task_id


class TestStrategyExecutor:
    """StrategyExecutor 测试。"""

    def test_execute_with_scheduler(self):
        scheduler = MockScheduler()
        executor = StrategyExecutor(scheduler=scheduler)
        s = _make_strategy(StrategyType.EXPLOIT_WINNER, MutationFocus.HOOK, Intensity.SMALL)
        result = executor.execute(s)
        assert result.success is True
        assert result.tasks_created > 0
        assert len(result.task_ids) > 0
        assert len(scheduler.submitted) > 0

    def test_execute_no_scheduler(self):
        executor = StrategyExecutor()
        s = _make_strategy(StrategyType.EXPLOIT_WINNER, MutationFocus.HOOK, Intensity.SMALL)
        result = executor.execute(s)
        assert result.success is False
        assert result.tasks_created == 0

    def test_execute_batch(self):
        scheduler = MockScheduler()
        executor = StrategyExecutor(scheduler=scheduler)
        strategies = [
            _make_strategy(StrategyType.EXPLOIT_WINNER, MutationFocus.HOOK, Intensity.SMALL),
            _make_strategy(StrategyType.EXPLORE_NEW, MutationFocus.VISUAL, Intensity.MEDIUM),
        ]
        results = executor.execute_batch(strategies)
        assert len(results) == 2
        assert all(r.success for r in results)

    def test_execute_creates_evolution_task(self):
        scheduler = MockScheduler()
        executor = StrategyExecutor(scheduler=scheduler)
        s = _make_strategy(StrategyType.EXPLOIT_WINNER, MutationFocus.HOOK, Intensity.SMALL)
        result = executor.execute(s)
        # Verify task structure
        for task in scheduler.submitted:
            assert task.genome_id != ""
            assert task.action in ("modify", "create", "clone", "crossover")
            assert task.priority > 0
            assert task.metadata["plan_id"] != ""

    def test_execute_result_has_plan_id(self):
        scheduler = MockScheduler()
        executor = StrategyExecutor(scheduler=scheduler)
        s = _make_strategy(StrategyType.EXPLOIT_WINNER, MutationFocus.HOOK, Intensity.SMALL)
        result = executor.execute(s)
        assert result.plan_id != ""

    def test_execute_result_has_strategy_id(self):
        scheduler = MockScheduler()
        executor = StrategyExecutor(scheduler=scheduler)
        s = _make_strategy(StrategyType.EXPLOIT_WINNER, MutationFocus.HOOK, Intensity.SMALL)
        result = executor.execute(s)
        assert result.strategy_id == s.strategy_id

    def test_execute_fix_failure(self):
        scheduler = MockScheduler()
        executor = StrategyExecutor(scheduler=scheduler)
        s = _make_strategy(StrategyType.FIX_FAILURE, MutationFocus.VISUAL, Intensity.LARGE)
        result = executor.execute(s)
        assert result.success is True
        assert result.tasks_created > 0

    def test_execute_diversify(self):
        scheduler = MockScheduler()
        executor = StrategyExecutor(scheduler=scheduler)
        s = _make_strategy(StrategyType.DIVERSIFY, MutationFocus.FULL, Intensity.RADICAL)
        result = executor.execute(s)
        assert result.success is True

    def test_execute_scale_success(self):
        scheduler = MockScheduler()
        executor = StrategyExecutor(scheduler=scheduler)
        s = _make_strategy(StrategyType.SCALE_SUCCESS, MutationFocus.REWARD, Intensity.MEDIUM)
        result = executor.execute(s)
        assert result.success is True

    def test_execute_explore_new(self):
        scheduler = MockScheduler()
        executor = StrategyExecutor(scheduler=scheduler)
        s = _make_strategy(StrategyType.EXPLORE_NEW, MutationFocus.GAMEPLAY, Intensity.MEDIUM)
        result = executor.execute(s)
        assert result.success is True

    def test_execute_with_target_genomes(self):
        scheduler = MockScheduler()
        executor = StrategyExecutor(scheduler=scheduler)
        s = _make_strategy(
            StrategyType.EXPLOIT_WINNER,
            MutationFocus.HOOK,
            Intensity.SMALL,
            target_genomes=["genome_A", "genome_B"],
        )
        result = executor.execute(s)
        # All tasks should use one of the target genomes
        for task in scheduler.submitted:
            assert task.genome_id in ("genome_A", "genome_B")

    def test_set_scheduler(self):
        executor = StrategyExecutor()
        assert executor.scheduler is None
        scheduler = MockScheduler()
        executor.set_scheduler(scheduler)
        assert executor.scheduler is scheduler

    def test_execute_empty_strategies(self):
        scheduler = MockScheduler()
        executor = StrategyExecutor(scheduler=scheduler)
        results = executor.execute_batch([])
        assert len(results) == 0

    def test_repr(self):
        executor = StrategyExecutor()
        assert "StrategyExecutor" in repr(executor)

    def test_create_genome_id_for_new(self):
        """CREATE 操作生成唯一的 genome_id。"""
        scheduler = MockScheduler()
        executor = StrategyExecutor(scheduler=scheduler)
        obj = EvolutionObjective(metric="CTR", current_value=0.03, target_value=0.05)
        s = EvolutionStrategy(
            strategy_type=StrategyType.EXPLORE_NEW,
            objective=obj,
            target_genomes=[],  # 空列表，不使用 helper 的 or 默认值
            mutation_focus=MutationFocus.FULL,
            intensity=Intensity.MEDIUM,
        )
        result = executor.execute(s)
        for task in scheduler.submitted:
            assert task.genome_id.startswith("new_genome_")

    def test_dependency_injection(self):
        planner = ExecutionPlanner()
        executor = StrategyExecutor(planner=planner)
        assert executor.planner is planner


# ═══════════════════════════════════════════════════════════════
# Controller Integration
# ═══════════════════════════════════════════════════════════════


class TestControllerExecutorIntegration:
    """Controller E11.8.2 集成测试。"""

    @pytest.fixture
    def controller(self):
        from unittest.mock import MagicMock
        from market_ops.creative_vision_runtime.autonomous_controller.controller import (
            AutonomousCreativeController,
        )
        engine = MagicMock()
        return AutonomousCreativeController(intelligence_engine=engine)

    def test_execute_strategy(self, controller):
        s = _make_strategy(StrategyType.EXPLOIT_WINNER, MutationFocus.HOOK, Intensity.SMALL)
        result = controller.execute_strategy(s)
        assert isinstance(result, ExecutionResult)
        assert result.strategy_id == s.strategy_id

    def test_execute_strategies(self, controller):
        strategies = [
            _make_strategy(StrategyType.EXPLOIT_WINNER, MutationFocus.HOOK, Intensity.SMALL),
            _make_strategy(StrategyType.EXPLORE_NEW, MutationFocus.VISUAL, Intensity.MEDIUM),
        ]
        results = controller.execute_strategies(strategies)
        assert len(results) == 2

    def test_plan_and_execute(self, controller):
        from market_ops.creative_vision_runtime.autonomous_controller.strategy.objective_engine import (
            ObjectiveEngine,
        )
        controller._strategy._objective_engine = ObjectiveEngine()
        result = controller.plan_and_execute(
            feedback={"metrics": {"CTR": 0.02}},
            tick=False,
        )
        assert "strategies" in result
        assert "execution_results" in result
        assert "total_tasks" in result

    def test_plan_and_execute_with_tick(self, controller):
        from market_ops.creative_vision_runtime.autonomous_controller.strategy.objective_engine import (
            ObjectiveEngine,
        )
        controller._strategy._objective_engine = ObjectiveEngine()
        result = controller.plan_and_execute(
            feedback={"metrics": {"CTR": 0.02}},
            tick=True,
        )
        assert "started_tasks" in result

    def test_plan_and_execute_with_signals(self, controller):
        from market_ops.creative_vision_runtime.autonomous_controller.strategy.objective_engine import (
            ObjectiveEngine,
        )
        from market_ops.creative_vision_runtime.autonomous_controller.feedback.models import (
            LearningSignal,
            LearningDirection,
        )
        controller._strategy._objective_engine = ObjectiveEngine()
        signals = [
            LearningSignal(
                genome_id="g1",
                direction=LearningDirection.MUTATE,
                confidence=0.7,
            )
        ]
        result = controller.plan_and_execute(
            feedback={"metrics": {"CTR": 0.02}},
            learning_signals=signals,
            tick=True,
        )
        assert "policy_result" in result
        assert "scheduler_result" in result

    def test_strategy_executor_property(self, controller):
        assert controller.strategy_executor is not None
        assert isinstance(controller.strategy_executor, StrategyExecutor)

    def test_constructor_injection(self):
        from unittest.mock import MagicMock
        from market_ops.creative_vision_runtime.autonomous_controller.controller import (
            AutonomousCreativeController,
        )
        engine = MagicMock()
        executor = StrategyExecutor()
        controller = AutonomousCreativeController(
            intelligence_engine=engine,
            strategy_executor=executor,
        )
        assert controller.strategy_executor is executor


# ═══════════════════════════════════════════════════════════════
# Full Pipeline
# ═══════════════════════════════════════════════════════════════


class TestFullPipeline:
    """端到端执行流程。"""

    def test_strategy_to_execution_pipeline(self):
        """Strategy → Mapper → Plan → Executor → Task 完整链路。"""
        mapper = MutationMapper()
        planner = ExecutionPlanner(mutation_mapper=mapper)
        scheduler = MockScheduler()
        executor = StrategyExecutor(planner=planner, scheduler=scheduler)

        s = _make_strategy(StrategyType.EXPLOIT_WINNER, MutationFocus.HOOK, Intensity.SMALL)
        result = executor.execute(s)

        assert result.success is True
        assert result.tasks_created >= 3  # HOOK has 3 genes
        assert len(scheduler.submitted) == result.tasks_created

    def test_all_strategy_types_execute(self):
        """所有 StrategyType 都能成功执行。"""
        scheduler = MockScheduler()
        executor = StrategyExecutor(scheduler=scheduler)

        for st in StrategyType:
            s = _make_strategy(st, MutationFocus.HOOK, Intensity.MEDIUM)
            result = executor.execute(s)
            assert result.tasks_created > 0, f"Failed for {st}"

    def test_plan_contains_correct_operations(self):
        """验证 MutationPlan 包含正确的操作。"""
        planner = ExecutionPlanner()

        # EXPLOIT_WINNER
        plan = planner.create_plan(
            _make_strategy(StrategyType.EXPLOIT_WINNER, MutationFocus.HOOK, Intensity.SMALL)
        )
        assert MutationOperation.MODIFY in plan.operations
        assert MutationOperation.CLONE in plan.operations

        # DIVERSIFY
        plan = planner.create_plan(
            _make_strategy(StrategyType.DIVERSIFY, MutationFocus.FULL, Intensity.RADICAL)
        )
        assert MutationOperation.CREATE in plan.operations

        # FIX_FAILURE
        plan = planner.create_plan(
            _make_strategy(StrategyType.FIX_FAILURE, MutationFocus.VISUAL, Intensity.LARGE)
        )
        assert MutationOperation.MODIFY in plan.operations
        assert MutationOperation.CROSSOVER in plan.operations

    def test_execution_result_reason(self):
        scheduler = MockScheduler()
        executor = StrategyExecutor(scheduler=scheduler)
        s = _make_strategy(StrategyType.EXPLOIT_WINNER, MutationFocus.HOOK, Intensity.SMALL)
        result = executor.execute(s)
        assert "Created" in result.reason
        assert "tasks" in result.reason.lower()

    def test_controller_full_pipeline(self):
        """Controller 完整 Planner → Executor 链路。"""
        from unittest.mock import MagicMock
        from market_ops.creative_vision_runtime.autonomous_controller.controller import (
            AutonomousCreativeController,
        )
        from market_ops.creative_vision_runtime.autonomous_controller.strategy.objective_engine import (
            ObjectiveEngine,
        )
        engine = MagicMock()
        controller = AutonomousCreativeController(intelligence_engine=engine)
        controller._strategy._objective_engine = ObjectiveEngine()

        result = controller.plan_and_execute(
            feedback={"metrics": {"CTR": 0.02, "ROI": 0.5}},
            tick=True,
        )
        assert result["total_tasks"] >= 0
        assert "execution_results" in result
        assert "strategies" in result


# ═══════════════════════════════════════════════════════════════
# Package Exports
# ═══════════════════════════════════════════════════════════════


class TestPackageExports:
    """包导出测试。"""

    def test_exports_executor_models(self):
        from market_ops.creative_vision_runtime.autonomous_controller.strategy.executor import (
            MutationOperation,
            MutationParameter,
            MutationPlan,
            ExecutionResult,
        )
        assert MutationOperation is not None
        assert MutationParameter is not None
        assert MutationPlan is not None
        assert ExecutionResult is not None

    def test_exports_executor_engines(self):
        from market_ops.creative_vision_runtime.autonomous_controller.strategy.executor import (
            MutationMapper,
            ExecutionPlanner,
            StrategyExecutor,
        )
        assert MutationMapper is not None
        assert ExecutionPlanner is not None
        assert StrategyExecutor is not None